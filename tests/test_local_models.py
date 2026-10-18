"""Offline protocol tests use explicit fakes, never real LLM performance evidence."""
import pytest
from src.local_runtime import OllamaLocal, LocalModelUnavailable


@pytest.mark.parametrize('url',['https://api.example.com','http://localhost:11434','http://192.168.1.2:11434',
    'http://127.0.0.1:11434/foo','http://user:password@127.0.0.1:11434'])
def test_runtime_refuses_remote_and_credential_endpoints(url):
    with pytest.raises(ValueError):
        OllamaLocal(url)


def test_transport_never_pulls_or_uses_remote_model(monkeypatch):
    runtime = OllamaLocal()
    calls = []
    def response(route, payload=None, probe=False):
        calls.append(route)
        return {'remote_host':'https://example.com', 'model_info':{'architecture':'test'}}
    monkeypatch.setattr(runtime, '_request', response)
    with pytest.raises(LocalModelUnavailable):
        runtime.identify('local:latest', [{'name':'local:latest','digest':'hash'}])
    assert calls == ['/api/show']


def test_runtime_embedding_validation(monkeypatch):
    runtime = OllamaLocal()
    for vectors in ([[0,0]], [[float('nan'),1]], [[1],[1,2]]):
        monkeypatch.setattr(runtime,'_request',lambda *a,**k:{'embeddings':vectors})
        with pytest.raises(LocalModelUnavailable):
            runtime.embed('all-minilm:latest',['text'] * len(vectors))


class FakeRuntime:
    """Explicit deterministic mock; its vectors/responses are not model inference."""
    def __init__(self):
        self.digest = 'fake-version-1'
        self.output = {'claims':[]}
        self.fail_embedding = False
        self.prompts = []
    def models(self):
        return []
    def identify(self,name,rows=None):
        return {'name':name,'digest':self.digest,'capabilities':['mock']}
    def chat(self,model,messages,schema=None,max_tokens=None):
        self.prompts.append(messages)
        return self.output, {}
    def embed(self,model,texts):
        if self.fail_embedding:
            raise LocalModelUnavailable('Injected embedding failure')
        return [[1.,0.,0.] if any(w in t.lower() for w in ['brand','make','maker']) else
                [0.,1.,0.] if any(w in t.lower() for w in ['deadline','due']) else [0.,0.,1.] for t in texts]


@pytest.fixture
def local_service(tmp_path):
    from src.accounts import Accounts
    from src.conversations import Conversations
    registry = Accounts(tmp_path/'registry.db')
    registry.register('alice','a long disposable password')
    service = Conversations(registry,registry.login('alice','a long disposable password'),tmp_path/'users')
    runtime = FakeRuntime()
    service.local.enabled, service.local.client = True,runtime
    service.local.status(refresh=True)
    yield service,runtime,registry,tmp_path
    service.close()
    registry.close()


def proposal(text, value='peanuts', assertion='explicit'):
    return {'claims':[{'entity':'user','entity_ref':'self','attribute':'allergy','value':value,
                      'evidence_quote':text,'assertion':assertion}]}


def test_local_extraction_is_grounded_candidate_with_provenance(local_service):
    s,r,_,_ = local_service
    text = 'I have an allergy to peanuts.'
    r.output = proposal(text)
    s.chat(s.create(),text,timestamp='2026-10-01')
    memory = s.memories()[0]
    assert memory['value'] == 'peanuts'
    assert 'unverified-candidate' in memory['text_evidence'][0]['extractor']
    import json
    audit = json.loads(s.selection_history()[0]['candidate_json'])
    assert audit['extraction']['digest'] == 'fake-version-1'
    assert audit['extraction']['verified'] is False


@pytest.mark.parametrize('text,value,assertion',[
    ('Maybe I have an allergy to peanuts.','peanuts','explicit'),
    ('I do not have an allergy to peanuts.','peanuts','explicit'),
    ('I have an allergy to peanuts.','walnuts','explicit'),
    ('I have an allergy to peanuts.','peanuts','inferred')])
def test_model_cannot_turn_hedges_negation_or_inference_into_facts(local_service,text,value,assertion):
    s,r,_,_ = local_service
    r.output = proposal(text,value,assertion)
    s.chat(s.create(),text,timestamp='2026-10-01')
    assert not s.memories()


def test_weaker_model_update_requires_explicit_correction(local_service):
    s,r,_,_ = local_service
    cid = s.create()
    s.chat(cid,'My user allergy is peanuts.',timestamp='2026-10-01')
    r.output = proposal('I have an allergy to walnuts.','walnuts')
    turn = s.chat(cid,'I have an allergy to walnuts.',timestamp='2026-10-02')
    assert turn.selections[0]['outcome'] == 'clarify'
    assert len(s.memories()) == 1


def test_semantic_paraphrase_reuses_temporal_selection_and_evidence(local_service):
    s,r,_,_ = local_service
    cid = s.create()
    s.chat(cid,'My laptop brand is Lenovo.',timestamp='2026-10-01')
    s.chat(cid,'My project named atlas deadline is 2026-11-01.',timestamp='2026-10-01')
    s.chat(cid,'My project named atlas deadline is 2026-12-01.',timestamp='2026-10-10')
    lexical = s._automatic_answer('Which make is my laptop?')
    assert not lexical.found
    answer = s.chat(s.create(),'Which make is my laptop?').answer
    assert answer.value == 'lenovo'
    assert answer.evidence[0]['conversation_references'][0]['conversation_id'] == cid
    assert s.local.last_retrieval['method'] == 'local-semantic-plus-temporal'
    assert s.chat(cid,'When is project named atlas due?').answer.value == '2026-12-01'
    assert s.chat(cid,'What was the previous due date for project named atlas?').answer.value == '2026-11-01'
    assert not s.chat(cid,'What brand is my watch?').answer.found


def test_index_reopen_failure_version_change_and_forgetting(local_service):
    s,r,registry,root = local_service
    cid = s.create()
    s.chat(cid,'My laptop brand is Lenovo.',timestamp='2026-10-01')
    first = s.local.reindex()
    from src.conversations import Conversations
    reopened = Conversations(registry,s.token,root/'users')
    assert reopened.local.index.active()['generation_id'] == first['generation_id']
    reopened.close()
    r.fail_embedding = True
    with pytest.raises(LocalModelUnavailable):
        s.local.reindex(force=True)
    assert s.local.index.active()['generation_id'] == first['generation_id']
    r.fail_embedding = False
    r.digest = 'fake-version-2'
    s.local.status(refresh=True)
    second = s.local.reindex()
    assert second['generation_id'] != first['generation_id']
    assert second['model_digest'] == 'fake-version-2'
    assert s.db.execute('SELECT COUNT(*) FROM local_embedding_generations').fetchone()[0] == 2
    s.set_memory_visibility(s.memories()[0]['memory_id'],False)
    assert not s.chat(cid,'Which make is my laptop?').answer.found


def test_local_index_account_isolation_and_identity_ambiguity(local_service):
    s,r,registry,root = local_service
    cid = s.create()
    for ref in ['alpha','beta']:
        s.chat(cid,f'My project named {ref} deadline is 2026-12-01.',timestamp='2026-10-01')
    assert not s.chat(cid,'When is my project due?').answer.found
    s.local.reindex()
    registry.register('bobby','another disposable password')
    from src.conversations import Conversations
    from src.accounts import AuthenticationError
    bob = Conversations(registry,registry.login('bobby','another disposable password'),root/'users')
    bob.local.enabled,bob.local.client = True,r
    bob.local.status(refresh=True)
    assert bob.local.index.active() is None
    r.output = {'reply':'Project alpha is due 2026-12-01.','state_ids':[]}
    bob_answer = bob.chat(bob.create(),'When is project named alpha due?').answer
    assert not bob_answer.found and '2026-12-01' not in bob_answer.text
    with pytest.raises(AuthenticationError):
        bob.chat(cid,'Show the project memories')
    bob.close()


def test_local_response_cannot_invent_memory_or_bypass_forgetting(local_service):
    s,r,_,_ = local_service
    cid = s.create()
    s.chat(cid,'My laptop brand is Lenovo.',timestamp='2026-10-01')
    r.output = {'reply':'Your brand is Apple.', 'state_ids':['M001']}
    assert s.chat(cid,'What brand is my laptop?').answer.value == 'lenovo'
    assert 'Apple' not in s.transcript(cid)[-1]['content']
    r.output = {'reply':'Your brand is lenovo.', 'state_ids':['M001']}
    answer = s.chat(cid,'What brand is my laptop?').answer
    assert answer.text == 'Your brand is lenovo.'
    assert s.local.last_response['method'] == 'local-llm'
    s.set_memory_visibility('M001',False)
    assert not s.chat(cid,'What brand is my laptop?').answer.found
    r.output = {'reply':'The laptop brand is lenovo.', 'state_ids':[]}
    assert 'lenovo' not in s.chat(cid,'What brand is the laptop?').answer.text.lower()


def test_real_http_protocol_against_explicit_stub_server(monkeypatch):
    """Real HTTP transport, synthetic server responses; no Ollama inference."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    import json
    routes = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def do_GET(self):
            self.send({'models':[{'name':'test:local','digest':'stub-hash'}]})
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            routes.append(self.path)
            if self.path == '/api/show':
                self.send({'model_info':{'general.architecture':'stub'}})
            elif self.path == '/api/chat':
                assert body['think'] is False and body['stream'] is False
                self.send({'message':{'content':'{"reply":"hello","state_ids":[]}'}})
            elif self.path == '/api/embed':
                assert body['truncate'] is False
                self.send({'embeddings':[[1.,0.] for _ in body['input']]})
            else:
                self.send_response(400)
                self.end_headers()
        def send(self,body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        monkeypatch.setenv('HTTP_PROXY','http://192.0.2.1:1')
        runtime = OllamaLocal(f'http://127.0.0.1:{server.server_port}')
        assert runtime.identify('test:local')['digest'] == 'stub-hash'
        assert runtime.chat('test:local',[{'role':'user','content':'hello'}])[0]['reply'] == 'hello'
        assert runtime.embed('test:local',['text']) == [[1.,0.]]
        assert routes == ['/api/show','/api/chat','/api/embed']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_local_only_detector_does_not_attempt_missing_weight_download(tmp_path):
    from src.cv.detection import ObjectDetector
    detector = ObjectDetector({'cv':{'local_files_only':True,'yolo_weights':str(tmp_path/'absent.pt')}})
    assert detector.model is None


@pytest.mark.parametrize('text,attribute,value',[
    ('I live in Bengaluru.','location','bengaluru'),
    ('I enjoy tea.','preference','tea'),
    ('I do not use cloud APIs.','constraint','do not use cloud apis'),
    ('Project atlas is due on 2026-12-01.','deadline','2026-12-01'),
    ('Project atlas must run offline.','requirement','run offline'),
    ('My supervisor is Alice.','supervisor','alice')])
def test_expanded_deterministic_fallback(text,attribute,value):
    from src.memory.selection import extract_candidates
    claims = extract_candidates(text,'2026-10-01')
    assert len(claims)==1 and claims[0].attribute == attribute and claims[0].value == value


def test_semantic_search_cannot_bypass_an_unresolved_image_conflict(local_service):
    from PIL import Image
    s,r,_,_ = local_service
    cid = s.create()
    s.chat(cid,'My car is red.',timestamp='2026-10-01')
    s.chat(cid,'My car is red.',Image.new('RGB',(64,64),'white'),timestamp='2026-10-10')
    assert s.chat(cid,'What hue is my car?').answer.status == 'uncertain'
    assert s.pending(cid)


def test_changed_query_dimension_falls_back_without_mutating_index(local_service,monkeypatch):
    s,r,_,_ = local_service
    cid = s.create()
    s.chat(cid,'My laptop brand is Lenovo.',timestamp='2026-10-01')
    original = s.local.reindex()
    monkeypatch.setattr(r,'embed',lambda model,texts:[[1.,0.] for t in texts])
    assert not s.chat(cid,'Which make is my laptop?').answer.found
    assert s.local.last_retrieval['method'] == 'lexical-fallback'
    assert s.local.index.active()['generation_id'] == original['generation_id']


def test_chat_budget_refuses_oversize_input_before_transport(monkeypatch):
    runtime = OllamaLocal()
    monkeypatch.setattr(runtime,'_request',lambda *a,**k:pytest.fail('Oversize input reached transport'))
    with pytest.raises(ValueError):
        runtime.chat('local:fixture',[{'role':'user','content':'x'*6001}])


def test_questions_without_punctuation_do_not_become_facts(local_service):
    from src.memory.selection import extract_candidates
    s,r,_,_ = local_service
    for text in ['Is my car red','What brand is my laptop','Can you remember my car color']:
        assert not extract_candidates(text,'2026-10-01')
    assert not extract_candidates('Actually, is my car red','2026-10-01')
    assert extract_candidates('Remember that my car is red','2026-10-01')[0].value == 'red'
    r.output = proposal('Is my car red','red')
    s.chat(s.create(),'Is my car red',timestamp='2026-10-01')
    assert not s.memories()
