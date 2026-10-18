"""Explicit importance is independent of truth and account visibility."""
import pytest
from src.accounts import Accounts, AuthenticationError
from src.conversations import Conversations
from src.memory.selection import SelectionPolicy, extract_candidates


@pytest.fixture
def service(tmp_path):
    accounts = Accounts(tmp_path / 'accounts.db')
    accounts.register('alice', 'a unique long password')
    s = Conversations(accounts, accounts.login('alice', 'a unique long password'), tmp_path / 'users')
    yield s, accounts, tmp_path
    s.close()
    accounts.close()


def test_explicit_usefulness_preserves_confidence_gate():
    claim = extract_candidates('My laptop mood is happy.', '2026-10-01')[0]
    policy = SelectionPolicy()
    assert policy.evaluate(claim, []).outcome == 'history_only'
    assert policy.evaluate(claim, [], explicit=True).usefulness == 1
    claim.confidence = .1
    assert policy.evaluate(claim, [], explicit=True).outcome == 'clarify'


def test_pin_low_usefulness_duplicate_unpin_and_restart(service):
    s, accounts, root = service
    cid = s.create()
    s.chat(cid, 'My laptop mood is happy.', timestamp='2026-10-01')
    assert not s.memories()
    turn = s.chat(cid, 'My laptop mood is happy.', timestamp='2026-10-01', remember=True)
    assert turn.selections[0]['pinned']
    assert turn.selections[0]['confidence'] == .9
    rid = s.memories()[0]['memory_id']
    s.chat(cid, 'Remember that my laptop mood is happy.', timestamp='2026-10-02')
    assert len(s.memories()) == 1
    assert len(s.priority_history()) == 1
    reopened = Conversations(accounts, s.token, root / 'users')
    try:
        assert reopened.chat(cid, 'Show my pinned memories').answer.found
        assert reopened.priority_history()[0]['source_message_id']
        reopened.set_memory_visibility(rid, False)
        assert not reopened.chat(cid, 'Show my pinned memories').answer.found
        reopened.set_memory_visibility(rid, True)
        reopened.set_memory_priority(rid, False)
        assert not reopened.chat(cid, 'Show my pinned memories').answer.found
        assert len(reopened.memories()) == 1
    finally:
        reopened.close()


def test_verbatim_note_and_sensitive_guard(service):
    s, _, _ = service
    cid = s.create()
    source = 'Bring the handmade folder to the Friday review'
    turn = s.chat(cid, source, timestamp='2026-10-01', remember=True)
    assert 'verbatim note' in turn.answer.text
    record = s.agent.store.all()[0]
    assert record.text_evidence[0].text == source
    assert record.text_evidence[0].extractor == 'user-requested-note-v1'
    assert record.text_evidence[0].ingested_at != record.timestamp
    assert s.chat(cid, 'Show my saved notes').answer.found
    s.chat(cid, 'Remember this API key: dummy-value', remember=True)
    assert len(s.memories()) == 1


def test_priority_cannot_cross_account_or_invent_identity(service):
    s, accounts, root = service
    cid = s.create()
    s.chat(cid, 'My first car is red.', timestamp='2026-10-01', remember=True)
    s.chat(cid, 'My second car is blue.', timestamp='2026-10-01')
    result = s.chat(cid, 'My car is black.', timestamp='2026-10-02', remember=True)
    assert result.selections[0]['outcome'] == 'clarify'
    accounts.register('bobby', 'another unique long password')
    bob = Conversations(accounts, accounts.login('bobby', 'another unique long password'), root / 'users')
    try:
        assert not bob.priority_history()
        with pytest.raises(AuthenticationError):
            bob.set_memory_priority(s.memories()[0]['memory_id'])
    finally:
        bob.close()


def test_priority_preserves_temporal_history_and_conflict_abstention(service):
    from PIL import Image
    s, _, _ = service
    cid = s.create()
    for value, day in [('red', '01'), ('blue', '10'), ('black', '20')]:
        s.chat(cid, f'My car is {value}.', timestamp=f'2026-10-{day}', remember=True)
    assert s.chat(cid, 'What color is my car now?').answer.value == 'black'
    assert s.chat(cid, 'What color was my car previously?').answer.value == 'blue'
    assert s.chat(cid, 'What color was my car originally?').answer.value == 'red'
    s.chat(cid, 'My car is black.', Image.new('RGB', (80, 80), 'white'), timestamp='2026-10-21')
    answer = s.chat(cid, 'Show my pinned memories').answer
    assert not answer.found
    assert 'unresolved disagreements' in answer.text


def test_pin_is_atomic_with_message_and_memory_write(service, monkeypatch):
    s, _, _ = service
    cid = s.create()
    original = s.set_memory_priority
    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('fixture interruption')
    monkeypatch.setattr(s, 'set_memory_priority', interrupted)
    with pytest.raises(RuntimeError, match='fixture interruption'):
        s.chat(cid, 'My car is red.', remember=True)
    assert not s.memories()
    assert not s.priority_history()
    assert not s.selection_history()
    assert not s.transcript(cid)


@pytest.mark.parametrize('choice', ['red', 'white'])
def test_pin_after_human_resolution(service, choice):
    from PIL import Image
    s, accounts, root = service
    cid = s.create()
    turn = s.chat(cid, 'My car is red.', Image.new('RGB', (80, 80), 'white'),
                  timestamp='2026-10-01', remember=True)
    assert not s.priority_history()
    assert s.pending(cid)
    s.resolve(cid, turn.observations[0], choice, 'Reviewed fixture')
    assert s.priority_history()
    reopened = Conversations(accounts, s.token, root / 'users')
    try:
        assert reopened.chat(cid, 'What color is my car?').answer.value == choice
        assert reopened.priority_history()[0]['actor'] == 'authenticated_user'
    finally:
        reopened.close()
