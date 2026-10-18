"""Local Track C behavior. Synthetic statements are not natural-dialogue evidence."""
import sqlite3

import pytest
from PIL import Image

from src.accounts import Accounts, AuthenticationError
from src.conversations import Conversations


@pytest.fixture
def setup(tmp_path):
    accounts = Accounts(tmp_path / "registry.db")
    accounts.register("alice", "Alice strong password 123")
    accounts.register("bobby", "Bobby strong password 456")
    token = accounts.login("alice", "Alice strong password 123")
    service = Conversations(accounts, token, tmp_path / "users")
    # All tests use Light mode and disposable SQLite only.
    yield accounts, token, service, tmp_path
    service.close()
    accounts.close()


def test_password_hashing_logout_expiry_and_history(tmp_path):
    clock = [100.0]
    a = Accounts(tmp_path / "auth.db", ttl=10, clock=lambda: clock[0])
    uid = a.register("alice", "a long unique password")
    token = a.login("alice", "a long unique password")
    assert a.identity(token) == uid
    row = a.db.execute("SELECT * FROM accounts").fetchone()
    assert row["password_hash"] != b"a long unique password"
    assert token not in repr(list(a.db.execute("SELECT * FROM logins")))
    assert "token_hash" not in a.history(token)[0]
    a.logout(token)
    with pytest.raises(AuthenticationError):
        a.identity(token)
    token = a.login("alice", "a long unique password")
    clock[0] = 111
    with pytest.raises(AuthenticationError):
        a.identity(token)
    a.close()


def test_login_throttle_and_unknown_accounts(tmp_path):
    a = Accounts(tmp_path / "auth.db")
    a.register("alice", "a long unique password")
    for _ in range(5):
        with pytest.raises(AuthenticationError, match="Login failed"):
            a.login("alice", "wrong")
    with pytest.raises(AuthenticationError, match="Login failed"):
        a.login("alice", "a long unique password")
    with pytest.raises(AuthenticationError, match="Login failed"):
        a.login("unknown", "wrong")
    a.close()


def test_cross_login_reopen_and_isolation(setup):
    a, token, s, path = setup
    cid = s.create("first discussion")
    s.remember(cid, "My car is red.", timestamp="2026-10-01")
    s.remember(cid, "My project model is CLIP.", timestamp="2026-10-01")
    uid = s.uid
    a.logout(token)
    with pytest.raises(AuthenticationError):
        s.transcript(cid)
    s.close()
    a.close()
    # Reopen both the identity registry and user memory, like a process restart.
    reopened_auth = Accounts(path / "registry.db")
    alice_token = reopened_auth.login("alice", "Alice strong password 123")
    alice = Conversations(reopened_auth, alice_token, path / "users")
    assert alice.uid == uid
    assert alice.ask(alice.create("return visit"), "What color is my car now?").value == "red"
    answer = alice.ask(cid, "Which model did we decide to train?")
    assert answer.value == "clip"
    assert any(e["conversation_references"][0]["conversation_id"] == cid for e in answer.evidence)
    bob_token = reopened_auth.login("bobby", "Bobby strong password 456")
    bob = Conversations(reopened_auth, bob_token, path / "users")
    assert not bob.list()
    with pytest.raises(AuthenticationError):
        bob.transcript(cid)
    with pytest.raises(AuthenticationError):
        Conversations(reopened_auth, "f" * 32, path / "users")
    assert not bob.ask(bob.create(), "What color is my car now?").found
    bob.close()
    alice.close()
    reopened_auth.close()


def test_project_temporal_multi_claim_and_intervening_turns(setup):
    _, _, s, _ = setup
    first = s.create()
    s.remember(first, "My project model is CLIP. My requirement is offline inference.", timestamp="2026-10-01")
    for i in range(30):
        s.remember(first, f"Unrelated message number {i}.", timestamp="2026-10-02")
    second = s.create()
    s.remember(second, "My project model is YOLO.", timestamp="2026-10-10")
    assert s.ask(second, "Which model did we decide to train?").value == "yolo"
    prev = s.ask(second, "What was my previous project model?")
    assert prev.value == "clip"
    assert {e["conversation_references"][0]["conversation_id"] for e in prev.evidence} == {first, second}
    assert s.ask(second, "What was my project model on 2026-10-05?").value == "clip"
    assert s.ask(second, "What is my requirement?").value == "offline inference"
    assert not s.ask(second, "What is my bike color?").found
    assert s.summarize(second)
    assert s.summaries(second)[0]["source_message_ids"]
    assert any(e["memory_id"] for e in s.events(second))


def test_transaction_rolls_back_messages_and_facts(setup, monkeypatch):
    _, _, s, _ = setup
    cid = s.create()
    original = s._link
    def fail(*args):
        original(*args)
        raise RuntimeError("simulated storage failure")
    monkeypatch.setattr(s, "_link", fail)
    with pytest.raises(RuntimeError):
        s.remember(cid, "My car is red.", timestamp="2026-10-01")
    assert not s.transcript(cid)
    assert not s.memories()


def test_image_transcript_failure_rolls_back_only_new_upload(setup, monkeypatch):
    _, _, s, _ = setup
    cid = s.create()
    s.remember(cid, "My car is red.", Image.new("RGB", (64, 64), "red"), "2026-10-01")
    existing = set(s.agent.image_dir.glob("*.png"))
    def fail(*args):
        raise RuntimeError("simulated link failure")
    monkeypatch.setattr(s, "_link", fail)
    with pytest.raises(RuntimeError):
        s.remember(cid, "My car is blue.", Image.new("RGB", (64, 64), "blue"), "2026-10-10")
    assert set(s.agent.image_dir.glob("*.png")) == existing
    assert len(s.memories()) == 1


def test_corroboration_does_not_reassign_original_evidence(setup):
    _, _, s, _ = setup
    original, corroborating = s.create(), s.create()
    s.remember(original, "My project model is CLIP.", timestamp="2026-10-01")
    s.remember(corroborating, "My project model is CLIP.", timestamp="2026-10-05")
    answer = s.ask(corroborating, "Which model did we decide to train?")
    assert len(answer.evidence) == 2
    refs = [e["conversation_references"] for e in answer.evidence]
    assert all(len(r) == 1 for r in refs)
    assert {r[0]["conversation_id"] for r in refs} == {original, corroborating}


def test_unknown_project_attribute_abstains_and_named_projects_are_separate(setup):
    _, _, s, _ = setup
    cid = s.create()
    s.remember(cid, "My project named alpha model is CLIP.", timestamp="2026-10-01")
    s.remember(cid, "My project named beta model is YOLO.", timestamp="2026-10-02")
    assert not s.ask(cid, "Which model did we decide to train?").found
    assert s.ask(cid, "What is the model for project named alpha?").value == "clip"
    assert s.ask(cid, "What is the model for project named beta?").value == "yolo"
    assert not s.ask(cid, "What is my project budget?").found


def test_uncertain_and_quoted_project_statements_remain_transcript_only(setup):
    _, _, s, _ = setup
    cid = s.create()
    for text in ("Maybe my project model is CLIP.", "If my project model is CLIP.",
                 "She said my project model is CLIP.", "Which model did we decide to train?"):
        s.remember(cid, text, timestamp="2026-10-01")
    assert not s.ask(cid, "Which model did we decide to train?").found
    assert len(s.transcript(cid)) == 10


@pytest.mark.parametrize("choice", ["red", "white"])
def test_authenticated_resolution_and_reopen(setup, choice):
    a, token, s, path = setup
    cid = s.create()
    result = s.remember(cid, "My car is red.", Image.new("RGB", (128, 128), "white"), "2026-10-01")
    assert s.agent.verification_request(result)
    s.resolve(cid, result, choice, "Reviewed in test")
    assert len(s.audit()) == 1
    assert s.ask(cid, "What color is my car now?").value == choice
    reopened = Conversations(a, token, path / "users")
    assert reopened.audit()[0]["rationale"] == "Reviewed in test"
    assert reopened.ask(cid, "What color was my car originally?").value == "red"
    assert not reopened.pending(cid)
    reopened.close()


def test_unresolved_observation_survives_restart_and_cannot_be_resolved_twice(setup):
    a, token, s, path = setup
    cid = s.create()
    s.remember(cid, "My car is red.", Image.new("RGB", (64, 64), "white"), "2026-10-01")
    reopened = Conversations(a, token, path / "users")
    pending = reopened.pending(cid)
    assert len(pending) == 1
    reopened.resolve(cid, pending[0], "white", "After reopen")
    with pytest.raises(AuthenticationError):
        reopened.resolve(cid, pending[0], "white")
    assert len(reopened.audit()) == 1
    reopened.close()


def test_schema_addition_preserves_existing_memory(setup):
    a, token, s, path = setup
    cid = s.create()
    s.remember(cid, "My car is red.", timestamp="2026-10-01")
    db = s.agent.store.db_path
    before = s.agent.store.all()[0].to_dict()
    other = Conversations(a, token, path / "users")
    assert other.agent.store.all()[0].to_dict() == before
    other.close()
    assert sqlite3.connect(db).execute("PRAGMA integrity_check").fetchone()[0] == "ok"
