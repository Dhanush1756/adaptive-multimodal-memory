"""Groq OpenAI-compatible transport. No SDK, downloads or implicit network probes."""
import argparse
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from .local_runtime import LocalModelUnavailable


REPLY_SCHEMA = {'type':'object','properties':{'reply':{'type':'string'},
    'state_ids':{'type':'array','items':{'type':'string'}}},
    'required':['reply','state_ids'],'additionalProperties':False}


class RefuseRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LocalModelUnavailable('Provider redirect refused; deterministic fallback active.')


def validate(value, schema):
    """Validate the bounded JSON subset used by this application, independently of Groq."""
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value,dict) or set(value) != set(schema['required']):
            raise ValueError('Invalid object')
        for name, child in schema['properties'].items():
            validate(value[name],child)
    elif kind == 'array':
        if not isinstance(value,list) or len(value) > schema.get('maxItems',32):
            raise ValueError('Invalid array')
        for item in value:
            validate(item,schema['items'])
    elif kind == 'string':
        if not isinstance(value,str) or len(value)>6000:
            raise ValueError('Invalid string')
        if 'enum' in schema and value not in schema['enum']:
            raise ValueError('Invalid enum')
    else:
        raise ValueError('Unsupported schema')


class GroqChat:
    endpoint = 'https://api.groq.com/openai/v1'
    provider = 'groq'

    def __init__(self, timeout=20):
        try:
            timeout = float(timeout)
            self.timeout = min(60,max(1,timeout)) if math.isfinite(timeout) else 20
        except (ValueError,TypeError):
            self.timeout = 20
        # No proxy from the environment, redirects, tools or alternative endpoint.
        self.opener = build_opener(ProxyHandler({}),RefuseRedirect())
        self.retry_at = 0
        self.last_status = 'Not tested; no live inference has been performed.'

    def identify(self,name,rows=None):
        """Configuration identity only; never implies a live model/weight verification."""
        if not isinstance(name,str) or not re.fullmatch(r'[\w./-]{1,160}',name):
            raise LocalModelUnavailable('Invalid GROQ_MODEL setting.')
        if os.environ.get('AEGM_ALLOW_EXTERNAL_LLM') != '1':
            raise LocalModelUnavailable('Groq disabled: explicit external-call opt-in required; deterministic fallback active.')
        if not os.environ.get('GROQ_API_KEY','').strip():
            raise LocalModelUnavailable('GROQ_API_KEY missing; deterministic fallback active.')
        return {'name':name,'digest':'provider-alias:'+name,'provider':'groq',
                'version_kind':'mutable provider model alias, not a weight digest',
                'live_verified':False}

    def _cooldown(self,header):
        try:
            seconds = float(header)
        except (ValueError,TypeError):
            try:
                seconds = (parsedate_to_datetime(header)-datetime.now(timezone.utc)).total_seconds()
            except Exception:
                seconds = 30
        if not math.isfinite(seconds):
            seconds = 30
        # No sleeping or automatic retries. Respect long Retry-After intervals too.
        self.retry_at = time.monotonic()+max(1,seconds)

    def chat(self,model,messages,schema=None,max_tokens=384):
        self.identify(model)  # consent/key are rechecked on EVERY request
        from .privacy import sensitivity
        if any(sensitivity(m['content']) != 'ordinary' for m in messages
               if isinstance(m,dict) and isinstance(m.get('content'),str)):
            raise LocalModelUnavailable('Sensitive content blocked before external processing; deterministic fallback active.')
        if time.monotonic()<self.retry_at:
            raise LocalModelUnavailable('Groq cooling down after a provider error; deterministic fallback active.')
        if (not isinstance(messages,list) or not 1<=len(messages)<=8
                or any(not isinstance(m,dict) or m.get('role') not in {'system','user','assistant'}
                       or not isinstance(m.get('content'),str) for m in messages)
                or sum(len(m['content']) for m in messages)>6000
                or not isinstance(max_tokens,int) or not 1<=max_tokens<=512):
            raise LocalModelUnavailable('Provider context exceeds the configured budget; fallback active.')
        if any(os.environ['GROQ_API_KEY'].strip() in m['content'] for m in messages):
            raise LocalModelUnavailable('Credential found in conversational context; provider request refused.')
        schema = schema or REPLY_SCHEMA
        payload = {'model':model,'messages':messages,'stream':False,
            'temperature':0,'max_completion_tokens':max_tokens,
            'response_format':{'type':'json_schema','json_schema':{
                'name':'memory_result','strict':True,'schema':schema}}}
        if model in {'openai/gpt-oss-20b','openai/gpt-oss-120b'}:
            payload['reasoning_effort'] = 'low'
        request = Request(self.endpoint+'/chat/completions',data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json',
                     'Accept':'application/json',
                     'User-Agent':'adaptive-evidence-grounded-memory/1.0',
                     'Authorization':'Bearer '+os.environ['GROQ_API_KEY'].strip()})
        try:
            with self.opener.open(request,timeout=self.timeout) as response:
                raw = response.read(256*1024+1)
            if len(raw)>256*1024:
                raise ValueError('Oversized response')
            result = json.loads(raw)
            choice = result['choices'][0]
            if choice.get('finish_reason') != 'stop' or choice['message'].get('refusal'):
                raise ValueError('Incomplete or refused output')
            output = json.loads(choice['message']['content'])
            validate(output,schema)
            usage = result.get('usage',{})
            # Expose numerical token usage only, never prompts, headers or raw errors.
            timing = {k:v for k,v in usage.items() if k in
                      {'prompt_tokens','completion_tokens','total_tokens'} and type(v) is int}
            self.last_status = 'A provider response passed transport/schema checks.'
            return output,timing
        except HTTPError as error:
            code = error.code
            if code in {429,503}:
                self._cooldown(error.headers.get('Retry-After'))
            else:
                self._cooldown(30)
            hints = {
                400:'request rejected; check structured-output schema, model parameters and token budget',
                401:'authentication failed; check that the clipboard contains the complete active Groq API key',
                403:'access forbidden; check organization/model permissions or network access restrictions',
                404:'model or endpoint unavailable; check GROQ_MODEL and model access',
                413:'request too large; reduce context',
                422:'request could not be processed; check schema and model compatibility',
                429:'rate limited; respecting Retry-After',
                500:'provider internal error; retry later',
                502:'provider gateway error; retry later',
                503:'provider temporarily unavailable; respecting cooldown',
            }
            # Status plus locally authored hints only. Never print provider bodies,
            # which may contain prompts, credentials or generated output.
            self.last_status = ('Groq HTTP '+str(code)+': '+hints.get(code,'provider request failed')+
                                '; deterministic fallback active.')
            error.close()
            raise LocalModelUnavailable(self.last_status) from None
        except Exception:
            self._cooldown(30)
            self.last_status = 'Groq network, timeout or structured-output failure; deterministic fallback active.'
            raise LocalModelUnavailable(self.last_status) from None


def main():
    parser = argparse.ArgumentParser(description='Explicit Groq inference probe; may consume provider quota.')
    parser.add_argument('--allow-live-request',action='store_true')
    args = parser.parse_args()
    if not args.allow_live_request:
        parser.error('No request made. Explicit --allow-live-request is required.')
    try:
        output,usage = GroqChat().chat(os.environ.get('GROQ_MODEL','openai/gpt-oss-20b'),
            [{'role':'system','content':'Return JSON with reply equal to OK and an empty state_ids array.'},
             {'role':'user','content':'Connection test; no personal data.'}])
        if output != {'reply':'OK','state_ids':[]}:
            raise LocalModelUnavailable('Provider schema succeeded but the connection probe content did not match.')
        print(json.dumps({'result':'PASS: actual Groq inference','usage':usage}))
    except LocalModelUnavailable as error:
        parser.exit(1,str(error)+'\n')


if __name__ == '__main__':
    main()
