"""Authored deterministic scenarios; not natural-dialogue benchmark evidence."""
import pytest

from src.accounts import Accounts, AuthenticationError
from src.conversations import Conversations


@pytest.fixture
def service(tmp_path):
    a = Accounts(tmp_path / 'accounts.db')
    a.register('alice', 'a unique long password')
    token = a.login('alice', 'a unique long password')
    s = Conversations(a, token, tmp_path / 'users')
    yield s, a, tmp_path
    s.close()
    a.close()


def test_selection_policy_and_general_extraction():
    from src.memory.selection import extract_candidates, SelectionPolicy
    claims = extract_candidates('My project named atlas deadline is 2026-11-01. My laptop brand is Lenovo.', '2026-10-01')
    assert [(c.entity, c.attribute, c.value) for c in claims] == [('project', 'deadline', '2026-11-01'), ('laptop', 'brand', 'lenovo')]
    policy = SelectionPolicy()
    assert policy.evaluate(claims[0], []).outcome == 'promote'
    assert SelectionPolicy({'minimum_usefulness': .99}).evaluate(claims[0], []).outcome == 'history_only'
    assert not extract_candidates('Hello! What color is my car? Maybe my car is blue.', '2026-10-01')
    assert extract_candidates('My project version is 3.14.', '2026-10-01')[0].value == '3.14'


def test_automatic_turn_general_temporal_and_provenance(service):
    s, _, _ = service
    cid = s.create()
    s.chat(cid, 'Hello!', timestamp='2026-10-01')
    assert not s.memories()
    s.chat(cid, 'My project named atlas deadline is 2026-11-01. My laptop brand is Lenovo.', timestamp='2026-10-01')
    s.chat(cid, 'My project named atlas deadline is 2026-12-01.', timestamp='2026-10-10')
    other = s.create()
    answer = s.chat(other, 'What is the previous deadline for project named atlas?').answer
    assert answer.value == '2026-11-01'
    assert answer.evidence[0]['extractor'] == 'general-explicit-rules-v3'
    assert answer.evidence[0]['timestamp'] and answer.evidence[0]['ingested_at']
    assert answer.evidence[0]['conversation_references'][0]['conversation_id'] == cid
    assert s.chat(other, 'What brand is my laptop?').answer.value == 'lenovo'
    assert not s.chat(other, 'What brand is my watch?').answer.found
    assert not s.chat(other, 'What is my project budget?').answer.found
    assert not s.chat(other, 'What is my laptop price?').answer.found


def test_duplicates_questions_uncertainty_and_identity(service):
    s, _, _ = service
    cid = s.create()
    s.chat(cid, 'My project named atlas model is CLIP.', timestamp='2026-10-01')
    count = len(s.memories())
    r = s.chat(cid, 'My project named atlas model is CLIP.', timestamp='2026-10-02')
    assert r.selections[0]['outcome'] == 'duplicate'
    assert len(s.memories()) == count
    s.chat(cid, 'My project named beta model is YOLO.', timestamp='2026-10-02')
    assert not s.chat(cid, 'What is my project model?').answer.found
    s.chat(cid, 'My project model is BERT.', timestamp='2026-10-03')
    assert s.selection_history()[-1]['outcome'] == 'clarify'
    assert s.chat(cid, 'What is the model for project named atlas?').answer.value == 'clip'
    s.chat(cid, 'Maybe my laptop brand is Apple.', timestamp='2026-10-04')
    assert len(s.memories()) == count + 1


def test_reopen_isolation_and_reversible_forgetting(service):
    s, a, root = service
    cid = s.create()
    s.chat(cid, 'Alice is my supervisor.', timestamp='2026-10-01')
    s.chat(cid, 'My document named thesis status is draft.', timestamp='2026-10-01')
    rid = next(r['memory_id'] for r in s.memories() if r['entity'] == 'document')
    s.set_memory_visibility(rid, False, 'no longer useful')
    assert not s.chat(cid, 'What is the status of document named thesis?').answer.found
    s.set_memory_visibility(rid, True, 'restore')
    reopened = Conversations(a, s.token, root / 'users')
    assert reopened.chat(reopened.create(), 'Who is my supervisor?').answer.value == 'alice'
    assert reopened.chat(cid, 'What is the status of document named thesis?').answer.value == 'draft'
    assert reopened.selection_history()
    a.register('bobby', 'another unique long password')
    bob = Conversations(a, a.login('bobby', 'another unique long password'), root / 'users')
    assert not bob.chat(bob.create(), 'Who is my supervisor?').answer.found
    with pytest.raises(AuthenticationError):
        bob.set_memory_visibility(rid, False)
    bob.close()
    reopened.close()


def test_image_crosscheck_and_both_decisions(service):
    from PIL import Image
    s, _, _ = service
    for choice, expected in [('red', 'red'), ('white', 'white')]:
        cid = s.create()
        # Separate explicit identities keep the two resolution scenarios apart.
        ref = 'first car' if choice == 'red' else 'second car'
        s.chat(cid, f'My {ref} is red.', timestamp='2026-10-01')
        result = s.chat(cid, f'My {ref} is red.', image=Image.new('RGB', (64,64), 'white'), timestamp='2026-10-10')
        assert result.observations
        assert s.chat(cid, f'What color is my {ref} now?').answer.status == 'uncertain'
        pending = s.pending(cid)[0]
        s.resolve(cid, pending, choice, 'controlled automatic-flow check')
        assert s.chat(cid, f'What color is my {ref} now?').answer.value == expected
        assert s.chat(cid, f'What color was my {ref} originally?').answer.value == 'red'
    assert len(s.audit()) == 2
    cid = s.create()
    s.chat(cid, 'My mug named desk is red.', timestamp='2026-10-01')
    s.chat(cid, 'My mug named desk is red.', image=Image.new('RGB',(64,64),'white'), timestamp='2026-10-10')
    uncertain = s.chat(cid, 'What color is my mug named desk?').answer
    assert uncertain.status == 'uncertain'
    mug_ids = {r['memory_id'] for r in s.memories() if r['entity'] == 'mug'}
    assert uncertain.evidence and all(e['memory_id'] in mug_ids for e in uncertain.evidence)


def test_failed_cv_does_not_lose_text_and_transaction_rollback(service, monkeypatch):
    s, _, _ = service
    cid = s.create()
    r = s.chat(cid, 'My car is blue.', image=b'not an image', timestamp='2026-10-01')
    assert any('unavailable' in n for o in r.observations for n in o.notes)
    assert s.chat(cid, 'What color is my car?').answer.value == 'blue'
    before = len(s.transcript(cid))
    monkeypatch.setattr(s, '_link', lambda *a: (_ for _ in ()).throw(RuntimeError('link failure')))
    with pytest.raises(RuntimeError):
        s.chat(cid, 'My laptop brand is Lenovo.', timestamp='2026-10-02')
    assert len(s.transcript(cid)) == before
    assert not any(r['entity'] == 'laptop' for r in s.memories())


def test_general_values_multiple_attributes_and_category_independence(service):
    s, _, _ = service
    cid = s.create()
    s.chat(cid, 'My project named atlas model is Gold. My project named atlas status is active.', timestamp='2026-10-01')
    assert s.chat(cid, 'What model is project named atlas?').answer.value == 'gold'
    s.chat(cid, 'My project named atlas model is Yellow.', timestamp='2026-10-02')
    assert s.chat(cid, 'What was the previous model for project named atlas?').answer.value == 'gold'
    s.chat(cid, 'My mug named desk is green.', timestamp='2026-10-01')
    assert s.chat(cid, 'What color is my mug named desk?').answer.value == 'green'
    assert s.chat(cid, 'What is the status of project named atlas?').answer.value == 'active'
    s.chat(cid, 'My document named atlas status is draft.', timestamp='2026-10-01')
    assert s.chat(cid, 'What is the status of document named atlas?').answer.value == 'draft'
    s.remember(cid, 'My car is red.', timestamp='2026-10-01')
    s.remember(cid, 'My project model is Gold.', timestamp='2026-10-02')
    assert s.chat(cid, 'What color is my car now?').answer.value == 'red'
    from PIL import Image
    from src.memory.schema import Claim
    r = s.agent.remember('My laptop brand is Lenovo.', Image.new('RGB',(64,64),'red'),
        timestamp='2026-10-03', explicit_claim=Claim('laptop','brand','lenovo',
            confidence=.9, source_text='My laptop brand is Lenovo.'))
    assert r.candidate.agreement is None
    assert r.candidate.visual.supports_state is False
    assert s.agent.verification_request(r) is None


def test_automatic_red_blue_black_and_late_evidence(service):
    s, _, _ = service
    cid = s.create()
    for color, day in [('red','01'),('blue','20'),('black','25'),('blue','10')]:
        s.chat(cid, f'My car is {color}.', timestamp=f'2026-10-{day}')
    assert s.chat(cid, 'What color is my car now?').answer.value == 'black'
    assert s.chat(cid, 'What color was my car previously?').answer.value == 'blue'
    assert s.chat(cid, 'What color was my car originally?').answer.value == 'red'
    assert s.chat(cid, 'What color was my car on 2026-10-15?').answer.value == 'blue'
    assert s.chat(cid, 'Show my car color history.').answer.value == ['red','blue','black']


def test_configurable_policy_and_forgetting_cannot_be_bypassed(service):
    s, _, _ = service
    cid = s.create()
    s.chat(cid, 'My car is red.', timestamp='2026-10-01')
    rid = s.memories()[0]['memory_id']
    s.set_memory_visibility(rid, False)
    assert not s.ask(cid, 'What color is my car?').found
    assert not s.chat(cid, 'Tell me about my car.').answer.found
    from src.memory.selection import SelectionPolicy, extract_candidates
    policy = SelectionPolicy()
    for text, expected in [('My laptop password is example.', 'reject'), ('My user mood is happy.', 'history_only')]:
        assert policy.evaluate(extract_candidates(text, '2026-10-01')[0], []).outcome == expected
