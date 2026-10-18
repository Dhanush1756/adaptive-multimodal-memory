"""Offline tests: fake HTTPS responses, never Groq inference or quality evidence."""
import io
import json
import time
from urllib.error import HTTPError, URLError

import pytest

from src.groq_provider import GroqChat, RefuseRedirect, REPLY_SCHEMA
from src.local_runtime import LocalModelUnavailable


class Response(io.BytesIO):
    pass


def envelope(value,finish='stop'):
    return {'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value)}}],
            'usage':{'prompt_tokens':12,'completion_tokens':7,'total_tokens':19}}


class StubHTTPS:
    def __init__(self,handler):
        self.handler,self.calls = handler,[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        return Response(json.dumps(self.handler(request)).encode())


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('AEGM_ALLOW_EXTERNAL_LLM','1')
    monkeypatch.setenv('GROQ_API_KEY','disposable-test-key-not-real')
    runtime = GroqChat()
    runtime.opener = StubHTTPS(lambda request:envelope({'reply':'Hello','state_ids':[]}))
    return runtime


@pytest.mark.parametrize('key,consent',[('', '1'),('fixture-key','0'),('','0')])
def test_requires_both_consent_and_key_before_network(transport,monkeypatch,key,consent):
    monkeypatch.setenv('GROQ_API_KEY',key)
    monkeypatch.setenv('AEGM_ALLOW_EXTERNAL_LLM',consent)
    with pytest.raises(LocalModelUnavailable):
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'hello'}])
    assert not transport.opener.calls


def test_https_schema_budget_and_no_key_in_results(transport):
    output,usage = transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'hello'}])
    request,timeout = transport.opener.calls[0]
    payload = json.loads(request.data)
    assert request.full_url == 'https://api.groq.com/openai/v1/chat/completions'
    assert payload['response_format']['json_schema']['strict'] is True
    assert payload['max_completion_tokens'] == 384 and payload['reasoning_effort'] == 'low'
    assert 'tools' not in payload and timeout == 20
    assert request.get_header('User-agent') == 'adaptive-evidence-grounded-memory/1.0'
    assert output == {'reply':'Hello','state_ids':[]}
    assert usage['total_tokens'] == 19
    assert 'disposable-test-key' not in json.dumps([payload,output,usage,transport.identify(payload['model'])])
    assert transport.identify(payload['model'])['live_verified'] is False


@pytest.mark.parametrize('code',[400,401,403,404,429,500,503])
def test_http_errors_sanitized_no_retries_or_provider_switch(transport,code):
    def fail(request):
        raise HTTPError(request.full_url,code,'secret-provider-body',{'Retry-After':'120'},
                        io.BytesIO(b'disposable-test-key-not-real private prompt'))
    transport.opener.handler = fail
    with pytest.raises(LocalModelUnavailable) as error:
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'private prompt'}])
    assert 'private prompt' not in str(error.value) and 'secret' not in str(error.value)
    assert 'Groq HTTP '+str(code) in str(error.value)
    if code == 401:
        assert 'authentication failed' in str(error.value)
    if code == 400:
        assert 'schema' in str(error.value)
    if code == 403:
        assert 'access forbidden' in str(error.value)
    if code in {429,503}:
        assert transport.retry_at-time.monotonic()>115
    with pytest.raises(LocalModelUnavailable):
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'hello'}])
    assert len(transport.opener.calls)==1


@pytest.mark.parametrize('failure',[TimeoutError('credential'),URLError('private prompt')])
def test_network_and_timeout_are_generic(transport,failure):
    def fail(request):
        raise failure
    transport.opener.handler = fail
    with pytest.raises(LocalModelUnavailable,match='network, timeout'):
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'hello'}])


@pytest.mark.parametrize('result',[
    envelope({'reply':'Hello','state_ids':[]},'length'),
    envelope({'reply':'Hello','state_ids':[],'extra':'injected'}),
    envelope({'reply':12,'state_ids':[]}),
    envelope({'reply':'Hello','state_ids':['s']*33}),
    {'choices':[]},
    {'choices':[{'finish_reason':'stop','message':{'content':'not JSON'}}]}])
def test_invalid_structured_output_falls_back(transport,result):
    transport.opener.handler = lambda request:result
    with pytest.raises(LocalModelUnavailable):
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'hello'}])


def test_redirect_and_large_context_refused(transport):
    with pytest.raises(LocalModelUnavailable):
        RefuseRedirect().redirect_request(None,None,None,None,None,None)
    with pytest.raises(LocalModelUnavailable):
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'x'*6001}])
    assert not transport.opener.calls


def test_credential_in_prompt_never_transmitted(transport):
    with pytest.raises(LocalModelUnavailable,match='Credential'):
        transport.chat('openai/gpt-oss-20b',[{'role':'user','content':'key disposable-test-key-not-real'}])
    assert not transport.opener.calls


def test_retry_after_http_date_and_invalid_value(transport):
    from datetime import datetime,timedelta,timezone
    from email.utils import format_datetime
    transport._cooldown(format_datetime(datetime.now(timezone.utc)+timedelta(seconds=90)))
    assert transport.retry_at-time.monotonic()>85
    transport._cooldown('invalid')
    assert 25<transport.retry_at-time.monotonic()<=30


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    from src.accounts import Accounts
    from src.conversations import Conversations
    from src.config import load_config
    monkeypatch.setenv('AEGM_LLM_PROVIDER','groq')
    monkeypatch.setenv('AEGM_ALLOW_EXTERNAL_LLM','1')
    monkeypatch.setenv('GROQ_API_KEY','disposable-test-key-not-real')
    monkeypatch.setenv('GROQ_MODEL','openai/gpt-oss-20b')
    accounts = Accounts(tmp_path/'accounts.db')
    accounts.register('alice','disposable test password')
    cfg = load_config()
    service = Conversations(accounts,accounts.login('alice','disposable test password'),tmp_path/'users',cfg=cfg)
    service.local.remote.opener = StubHTTPS(lambda request:envelope({'claims':[]}))
    yield service,accounts,tmp_path
    service.close()
    accounts.close()


def candidate(text,value='peanuts',advice='consider'):
    return {'claims':[{'entity':'user','entity_ref':'self','attribute':'allergy','value':value,
        'evidence_quote':text,'assertion':'explicit','memory_advice':advice}]}


def test_candidates_cached_but_event_time_revalidated(workspace):
    service,_,_ = workspace
    text = 'I have an allergy to peanuts.'
    remote = service.local.remote
    remote.opener.handler = lambda request:envelope(candidate(text))
    first,meta = service.local.extract(text,'2026-10-01',[])
    second,_ = service.local.extract(text,'2026-10-02',[])
    assert len(remote.opener.calls)==1
    assert first[0].resolved_time != second[0].resolved_time
    assert service.local.last_extraction['runtime_timing']['cache_hit']
    assert next(iter(meta.values()))['verified'] is False
    assert next(iter(meta.values()))['provider']=='groq'


@pytest.mark.parametrize('advice,stored',[('consider',True),('history_only',False)])
def test_advisory_selection_is_not_verification_and_persists(workspace,advice,stored):
    service,accounts,path = workspace
    text = 'I have an allergy to peanuts.'
    service.local.remote.opener.handler = lambda request:envelope(candidate(text,advice=advice))
    cid = service.create()
    service.chat(cid,text,timestamp='2026-10-01')
    assert bool(service.memories()) is stored
    audit = json.loads(service.selection_history()[0]['candidate_json'])['extraction']
    assert audit['verified'] is False and audit['advice']==advice
    if stored:
        assert service.memories()[0]['text_evidence'][0]['extractor'].startswith('groq:')
    from src.conversations import Conversations
    reopened = Conversations(accounts,service.token,path/'users')
    try:
        assert bool(reopened.memories()) is stored
    finally:
        reopened.close()


def test_grounded_response_uncertainty_and_separate_embedding_fallback(workspace):
    service,_,_ = workspace
    cid = service.create()
    service.local.remote.opener.handler = lambda request:envelope({'claims':[]})
    service.chat(cid,'My car is red.',timestamp='2026-10-01')
    calls = service.local.remote.opener.calls
    def reply(request):
        payload = json.loads(request.data)
        assert 'all-minilm' not in payload['model']
        assert 'disposable-test-key' not in json.dumps(payload)
        ids = [row['memory_id'] for row in service.memories()]
        return envelope({'reply':'Your car is currently red.','state_ids':ids})
    service.local.remote.opener.handler = reply
    turn = service.chat(cid,'What color is my car now?')
    assert turn.answer.value=='red' and service.local.last_response['method']=='groq-llm'
    assert turn.answer.evidence and service.local.last_retrieval['method']=='lexical'
    count = len(calls)
    unknown = service.chat(cid,'What color is my phone?')
    assert not unknown.answer.found and len(calls)==count
    assert service.local.embedding is None


def test_provider_failure_cannot_lose_valid_text_or_create_model_facts(workspace):
    service,_,_ = workspace
    def fail(request):
        raise TimeoutError('sensitive text')
    service.local.remote.opener.handler = fail
    cid = service.create()
    service.chat(cid,'My car is red.',timestamp='2026-10-01')
    assert service.memories()[0]['value']=='red'
    turn = service.chat(cid,'What color is my car now?')
    assert turn.answer.value=='red' and service.local.last_response['method']=='deterministic-fallback'


def test_groq_account_context_and_cache_are_isolated(workspace):
    from src.conversations import Conversations
    service,accounts,path = workspace
    alice = service.create()
    service.local.remote.opener.handler = lambda request:envelope({'claims':[]})
    service.chat(alice,'My laptop brand is AliceSecret.',timestamp='2026-10-01')
    accounts.register('bob','another disposable password')
    bob = Conversations(accounts,accounts.login('bob','another disposable password'),path/'users')
    try:
        def inspect(request):
            assert 'alicesecret' not in request.data.decode().lower()
            return envelope(candidate('I have an allergy to peanuts.'))
        bob.local.remote.opener = StubHTTPS(inspect)
        bob.chat(bob.create(),'I have an allergy to peanuts.',timestamp='2026-10-01')
        assert bob.memories()[0]['value']=='peanuts'
        assert service.memories()[0]['value']=='alicesecret'
        assert bob.local.extraction_cache is not service.local.extraction_cache
    finally:
        bob.close()


def test_missing_key_app_status_and_rules_fallback(workspace,monkeypatch):
    service,_,_ = workspace
    monkeypatch.delenv('GROQ_API_KEY')
    cid = service.create()
    service.chat(cid,'My car is red.',timestamp='2026-10-01')
    assert service.chat(cid,'What color is my car?').answer.value=='red'
    assert 'GROQ_API_KEY missing' in service.local.status()['status']
    assert not service.local.remote.opener.calls


def test_groq_cannot_choose_conflict_or_restore_forgotten_memory(workspace):
    from PIL import Image
    service,_,_ = workspace
    service.local.remote.opener.handler = lambda request:envelope({'claims':[]})
    cid = service.create()
    service.chat(cid,'My first car is red.',timestamp='2026-10-01')
    service.chat(cid,'My first car is red.',Image.new('RGB',(64,64),'white'),timestamp='2026-10-02')
    count = len(service.local.remote.opener.calls)
    assert service.chat(cid,'What color is my first car?').answer.status=='uncertain'
    assert len(service.local.remote.opener.calls)==count
    assert service.pending(cid)
    item = service.memories()[0]
    service.set_memory_visibility(item['memory_id'],False,rationale='offline test')
    # Hidden facts cannot be supplied to response generation or retrieved as answers.
    assert not service.chat(cid,'What color is my first car?').answer.found
    assert len(service.local.remote.opener.calls)==count
