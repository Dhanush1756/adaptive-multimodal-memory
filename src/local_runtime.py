"""Bounded, loopback-only Ollama transport. Never installs or pulls a model."""
import ipaddress
import json
import math
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class LocalModelUnavailable(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LocalModelUnavailable('Local runtime redirects are disabled.')


class OllamaLocal:
    def __init__(self, endpoint='http://127.0.0.1:11434', timeout=30, probe_timeout=.5):
        parsed = urlsplit(endpoint)
        try:
            local = ipaddress.ip_address(parsed.hostname).is_loopback
        except (ValueError, TypeError):
            local = False
        if (not local or parsed.scheme != 'http' or parsed.username or parsed.password
                or parsed.path not in {'','/'} or parsed.query or parsed.fragment):
            raise ValueError('Ollama endpoint must be an HTTP loopback IP without credentials or a path.')
        self.endpoint, self.timeout, self.probe_timeout = endpoint.rstrip('/'), timeout, probe_timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def _request(self, route, payload=None, probe=False):
        request = Request(self.endpoint + route,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json'})
        try:
            with self.opener.open(request, timeout=self.probe_timeout if probe else self.timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('Oversize runtime response')
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get('error'):
                raise ValueError('Runtime error')
            return result
        except Exception:
            # Do not expose prompts, server exception bodies or local paths.
            raise LocalModelUnavailable('Local Ollama request failed; deterministic/lexical fallback is active.') from None

    def models(self):
        result = self._request('/api/tags', probe=True)
        rows = result.get('models')
        if not isinstance(rows, list):
            raise LocalModelUnavailable('Ollama returned an invalid model inventory.')
        return rows

    def identify(self, name, rows=None):
        if not isinstance(name, str) or 'cloud' in name.lower() or len(name) > 160:
            raise LocalModelUnavailable('Only locally installed models are supported.')
        rows = self.models() if rows is None else rows
        row = next((r for r in rows if r.get('name') == name or r.get('model') == name), None)
        if not row or not isinstance(row.get('digest'), str) or not row['digest']:
            raise LocalModelUnavailable('Required local model is not installed; follow the setup guide.')
        details = self._request('/api/show', {'model':name}, probe=True)
        if (row.get('remote_model') or row.get('remote_host') or details.get('remote_model')
                or details.get('remote_host') or not isinstance(details.get('model_info'), dict)
                or not details['model_info']):
            raise LocalModelUnavailable('Remote or unverifiable model definitions are refused.')
        return {'name':name, 'digest':row['digest'], 'details':details.get('details',{}),
                'capabilities':details.get('capabilities',[])}

    def chat(self, model, messages, schema=None, max_tokens=384):
        if (not isinstance(messages,list) or not 1 <= len(messages) <= 8
                or any(not isinstance(m,dict) or not isinstance(m.get('content'),str) for m in messages)
                or sum(len(m['content']) for m in messages)>6000
                or not isinstance(max_tokens,int) or not 1 <= max_tokens <= 512):
            raise ValueError('Local chat input/output exceeds the bounded prototype budget.')
        result = self._request('/api/chat', {'model':model, 'messages':messages,
            'stream':False, 'think':False, 'format':schema or 'json', 'keep_alive':'0',
            'options':{'temperature':0, 'seed':13, 'num_ctx':2048, 'num_predict':max_tokens,
                       'num_gpu':0,'num_thread':4}})
        message = result.get('message',{}).get('content')
        if not isinstance(message, str):
            raise LocalModelUnavailable('Local chat response was invalid.')
        return json.loads(message), {k:result.get(k) for k in
            ('total_duration','load_duration','eval_count','eval_duration','prompt_eval_count')}

    def embed(self, model, texts):
        if not 1 <= len(texts) <= 16 or any(len(t) > 2000 for t in texts):
            raise ValueError('Embedding inputs exceed the bounded local batch.')
        result = self._request('/api/embed', {'model':model, 'input':texts,
            'truncate':False, 'keep_alive':'0','options':{'num_gpu':0,'num_thread':4}})
        vectors = result.get('embeddings')
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise LocalModelUnavailable('Local embedding response was invalid.')
        dimension = None
        for vector in vectors:
            if not isinstance(vector,list) or not 1 <= len(vector) <= 4096:
                raise LocalModelUnavailable('Invalid embedding dimensions.')
            if dimension is not None and dimension != len(vector):
                raise LocalModelUnavailable('Mixed embedding dimensions.')
            if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in vector):
                raise LocalModelUnavailable('Non-finite embedding values.')
            if sum(v*v for v in vector) <= 0:
                raise LocalModelUnavailable('Zero embedding vector.')
            dimension = len(vector)
        return vectors
