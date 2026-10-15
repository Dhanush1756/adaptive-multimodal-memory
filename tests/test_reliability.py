"""Phase 1 regressions: event time, persistence, isolation and atomic updates.

All databases/images belong to tmp_path. No model downloads or user data are used.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest
from PIL import Image

from src.agent.reasoning import MemoryAgent
from src.config import load_config
from src.data.synthetic import render_object
from src.memory.schema import Action, Candidate, Claim, Status
from src.memory.store import MemoryStore
from src.memory.update import MemoryEngine


@pytest.fixture
def make_agent(tmp_path):
    agents = []

    def make(name="memory", **kwargs):
        cfg = load_config()
        cfg["paths"]["db_path"] = str(tmp_path / f"{name}.db")
        cfg["paths"]["image_dir"] = str(tmp_path / f"{name}_images")
        options = dict(db_path=cfg["paths"]["db_path"], image_dir=cfg["paths"]["image_dir"],
                       light=True, use_intent_model=False)
        options.update(kwargs)
        agent = MemoryAgent(cfg, **options)
        agents.append(agent)
        return agent

    yield make
    for agent in agents:
        agent.store.close()


def snapshot(agent):
    return [r.to_dict() for r in agent.store.all()]


def test_late_blue_observation_extends_state_using_event_time(make_agent):
    agent = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01", session_id="red")
    blue = agent.remember("My car is blue.", timestamp="2026-10-20", session_id="blue20")
    assert agent.ask("What color was my car on 2026-10-15?").value == "red"

    late = agent.remember("My car is blue.", timestamp="2026-10-10", session_id="blue10")
    assert late.decision.action == Action.MERGE
    assert late.decision.memory_id == blue.decision.memory_id
    assert agent.ask("What color was my car on 2026-10-15?").value == "blue"
    assert agent.ask("What color was my car on 2026-10-09?").value == "red"
    red, blue_state = agent.timeline_for("car")
    assert blue_state.timestamp == "2026-10-10T00:00:00"
    assert blue_state.previous_memory_id == red.memory_id
    assert (red.status, blue_state.status) == (Status.HISTORICAL, Status.CURRENT)
    assert {e.timestamp for e in blue_state.text_evidence} == {
        "2026-10-10T00:00:00", "2026-10-20T00:00:00"}


def test_later_support_does_not_backdate_blue(make_agent):
    agent = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01")
    agent.remember("I repainted my car blue.", timestamp="2026-10-20")
    # Arrival/reference time is Oct 30; the explicitly described event is Oct 20.
    result = agent.remember("I repainted my car blue on 2026-10-20.", timestamp="2026-10-30")
    assert result.decision.action == Action.MERGE
    assert agent.ask("What color was my car on 2026-10-15?").value == "red"
    assert agent.timeline_for("car")[-1].timestamp == "2026-10-20T00:00:00"
    assert agent.timeline_for("car")[-1].text_evidence[-1].timestamp == "2026-10-30T00:00:00"


def test_late_historical_evidence_does_not_replace_newest_state(make_agent):
    agent = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01")
    agent.remember("My car is blue.", timestamp="2026-10-20")
    agent.remember("My car is black.", timestamp="2026-10-25")
    agent.remember("My car is blue.", timestamp="2026-10-10")
    assert agent.ask("What color is my car now?").value == "black"
    assert agent.ask("What color was my car on 2026-10-15?").value == "blue"
    chain = agent.timeline_for("car")
    assert [r.value for r in chain] == ["red", "blue", "black"]
    assert chain[2].previous_memory_id == chain[1].memory_id


def test_store_creates_missing_parent_directory(tmp_path):
    db = tmp_path / "new" / "nested" / "memory.db"
    store = MemoryStore(str(db))
    try:
        assert db.is_file()
        assert store.stats()["TOTAL"] == 0
    finally:
        store.close()


def test_existing_sqlite_schema_migrates_ingestion_provenance(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE memory (
        memory_id TEXT PRIMARY KEY, seq INTEGER NOT NULL, session_id TEXT,
        entity TEXT NOT NULL, entity_id TEXT NOT NULL, attribute TEXT NOT NULL,
        value TEXT NOT NULL, timestamp TEXT NOT NULL, confidence REAL,
        status TEXT NOT NULL, previous_memory_id TEXT, event TEXT,
        conflicting_value TEXT, text_evidence TEXT, visual_evidence TEXT,
        source TEXT, entity_ref TEXT DEFAULT '')"""
    )
    conn.close()

    agent = MemoryAgent(load_config(), db_path=str(db), light=True, use_intent_model=False)
    try:
        columns = {row[1] for row in agent.store.conn.execute("PRAGMA table_info(memory)")}
        assert "ingested_at" in columns
        agent.remember("My car is red.", timestamp="2026-10-01", session_id="legacy-upgrade")
        record = agent.timeline_for("car")[0]
        assert record.ingested_at
        assert record.text_evidence[0].evidence_id == "TXT_legacy-upgrade"
    finally:
        agent.store.close()


@pytest.mark.parametrize("relative", [False, True])
def test_agent_honors_configured_database_path(tmp_path, monkeypatch, relative):
    import src.config as config

    cfg = load_config()
    db = tmp_path / "configured" / "memory.db"
    cfg["paths"]["db_path"] = "configured/memory.db" if relative else str(db)
    cfg["paths"]["image_dir"] = str(tmp_path / "images")
    monkeypatch.setattr(config, "ROOT", str(tmp_path))
    agent = MemoryAgent(cfg, light=True, use_intent_model=False)
    try:
        agent.remember("My car is red.", timestamp="2026-10-01")
        assert db.is_file()
        assert Path(agent.store.db_path).resolve() == db.resolve()
    finally:
        agent.store.close()


def test_file_database_reopens_with_states_links_and_evidence(make_agent):
    agent = make_agent()
    for color, day in [("red", 1), ("blue", 10), ("black", 20)]:
        agent.remember(f"My car is {color}.", render_object("car", color),
                       f"2026-10-{day:02d}T10:00:00", session_id=f"day{day}")
    before = snapshot(agent)
    agent.store.close()
    reopened = make_agent()
    assert snapshot(reopened) == before
    assert reopened.ask("What color is my car now?").value == "black"
    assert reopened.ask("What color was my car before?").value == "blue"
    assert reopened.ask("What color was my car originally?").value == "red"
    answer = reopened.ask("Show the evidence for my car.")
    assert {e["session_id"] for e in answer.evidence} == {"day20"}
    assert answer.value == "black"
    for rec in reopened.timeline_for("car"):
        assert len(rec.text_evidence) == len(rec.visual_evidence) == 1
        assert Path(rec.visual_evidence[0].image_path).is_file()
        assert rec.text_evidence[0].embedding and rec.visual_evidence[0].embedding


def test_merged_visual_evidence_keeps_its_own_date_and_session(make_agent):
    agent = make_agent()
    for sid, date in [("blue20", "2026-10-20"), ("blue10", "2026-10-10")]:
        agent.remember("My car is blue.", render_object("car", "blue"), date, sid)
    agent.store.close()
    reopened = make_agent()
    evidence = reopened.ask("Show the evidence for my car.").evidence
    for modality in ("text", "image"):
        assert {e["session_id"]: e["timestamp"] for e in evidence if e["modality"] == modality} == {
            "blue20": "2026-10-20T00:00:00", "blue10": "2026-10-10T00:00:00"}


def test_merged_session_ids_are_not_reused_after_reopen(make_agent):
    agent = make_agent()
    agent.remember("My car is blue.", timestamp="2026-10-01", session_id="first")
    agent.remember("My car is blue.", timestamp="2026-10-02", session_id="support")
    agent.store.close()
    reopened = make_agent()
    result = reopened.remember("My car is red.", timestamp="2026-10-03", session_id="support")
    assert result.session_id != "support"
    assert reopened.timeline_for("car")[0].text_evidence[-1].session_id == "support"


def test_two_agents_do_not_share_memory_or_reset(make_agent):
    first, second = make_agent("first"), make_agent("second")
    first.remember("My car is red.", timestamp="2026-10-01")
    second.remember("My car is blue.", timestamp="2026-10-02")
    assert first.ask("What color is my car now?").value == "red"
    assert second.ask("What color is my car now?").value == "blue"
    first.reset()
    assert not first.ask("What color is my car now?").found
    assert second.ask("What color is my car now?").value == "blue"
    second.store.close()
    assert make_agent("second").ask("What color is my car now?").value == "blue"


def test_failed_transition_rolls_back_all_database_changes(make_agent, monkeypatch):
    agent = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01")
    before = snapshot(agent)
    original = agent.store.set_previous

    def fail_after_write(memory_id, previous_id):
        original(memory_id, previous_id)
        raise RuntimeError("injected chain failure")

    with monkeypatch.context() as m:
        m.setattr(agent.store, "set_previous", fail_after_write)
        with pytest.raises(RuntimeError, match="injected chain failure"):
            agent.remember("My car is blue.", timestamp="2026-10-10")
    assert snapshot(agent) == before
    assert snapshot(make_agent()) == before  # verify from another SQLite connection too
    agent.remember("My car is black.", timestamp="2026-10-20")
    assert [r.value for r in agent.timeline_for("car")] == ["red", "black"]


def test_failed_merge_rolls_back_evidence_and_state_start(make_agent, monkeypatch):
    agent = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01")
    agent.remember("My car is blue.", timestamp="2026-10-20")
    before = snapshot(agent)

    def fail(*args):
        raise RuntimeError("injected merge failure")

    monkeypatch.setattr(agent.store, "set_confidence", fail)
    with pytest.raises(RuntimeError, match="injected merge failure"):
        agent.remember("My car is blue.", timestamp="2026-10-10")
    assert snapshot(agent) == before
    assert snapshot(make_agent()) == before


def test_failed_image_save_does_not_commit_a_state(make_agent, monkeypatch):
    agent = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01")
    before = snapshot(agent)

    def fail(*args, **kwargs):
        raise OSError("injected image write failure")

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(OSError, match="injected image write failure"):
        agent.remember("My car is blue.", render_object("car", "blue"), "2026-10-10")
    assert snapshot(agent) == before
    assert not list(agent.image_dir.glob("*.png"))


def test_images_never_collide_across_agents_or_resets(make_agent, tmp_path):
    first = make_agent("first", image_dir=str(tmp_path / "shared_images"))
    second = make_agent("second", image_dir=str(tmp_path / "shared_images"))
    first.remember("My car is red.", render_object("car", "red"), "2026-10-01", "same")
    old_path = Path(first.timeline_for("car")[0].visual_evidence[0].image_path)
    old_bytes = old_path.read_bytes()
    second.remember("My car is blue.", render_object("car", "blue"), "2026-10-02", "same")
    second_path = Path(second.timeline_for("car")[0].visual_evidence[0].image_path)
    assert second_path != old_path
    assert old_path.read_bytes() == old_bytes
    second.reset()
    second.remember("My car is black.", render_object("car", "black"), "2026-10-03", "same")
    new_path = Path(second.timeline_for("car")[0].visual_evidence[0].image_path)
    assert new_path not in (old_path, second_path)
    assert old_path.read_bytes() == old_bytes


@pytest.mark.parametrize("shared_connection", [False, True])
def test_concurrent_engine_writers_preserve_one_complete_chain(tmp_path, shared_connection):
    path = str(tmp_path / "concurrent.db")
    first = MemoryStore(path)
    second = first if shared_connection else MemoryStore(path)
    barrier = Barrier(2)

    def candidate(value, day):
        return Candidate(session_id=f"day{day}", timestamp=f"2026-10-{day:02d}", confidence=0.95,
                         claim=Claim("car", "color", value, confidence=0.95,
                                     source_text=f"My car is {value}."))

    def write(store, value, day):
        barrier.wait(timeout=10)
        return MemoryEngine(store).process(candidate(value, day))

    try:
        MemoryEngine(first).process(candidate("red", 1))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write, first, "blue", 10), pool.submit(write, second, "black", 20)]
            decisions = [future.result(timeout=15) for future in futures]
        chain = first.query("car_001", "color")
        assert len({d.memory_id for d in decisions}) == 2
        assert [r.value for r in chain] == ["red", "blue", "black"]
        assert [r.status for r in chain] == [Status.HISTORICAL, Status.HISTORICAL, Status.CURRENT]
        assert [r.previous_memory_id for r in chain] == [None, chain[0].memory_id, chain[1].memory_id]
        assert all(len(r.text_evidence) == 1 for r in chain)
    finally:
        first.close()
        if second is not first:
            second.close()


def test_other_connection_cannot_see_an_incomplete_transition(make_agent, monkeypatch):
    agent = make_agent()
    observer = make_agent()
    agent.remember("My car is red.", timestamp="2026-10-01")
    before = snapshot(observer)
    original = agent.store.set_previous
    observations = []

    def observe_during_chain_update(memory_id, previous_id):
        original(memory_id, previous_id)
        observations.append(snapshot(observer))

    monkeypatch.setattr(agent.store, "set_previous", observe_during_chain_update)
    agent.remember("My car is blue.", timestamp="2026-10-10")
    assert observations and all(observation == before for observation in observations)
    assert observer.ask("What color is my car now?").value == "blue"


def test_legacy_image_evidence_stays_readable_after_earlier_merge(make_agent):
    agent = make_agent()
    agent.remember("My car is blue.", render_object("car", "blue"), "2026-10-20", "legacy")
    rec = agent.timeline_for("car")[0]
    legacy = rec.visual_evidence[0].to_dict()
    legacy.pop("timestamp")
    legacy.pop("session_id")
    legacy.pop("ingested_at")
    legacy.pop("detector_model")
    legacy.pop("attribute_model")
    legacy.pop("embedding_model")
    legacy["image_id"] = "IMG_legacy"
    # Reproduce the original JSON format inside this test's temporary database.
    agent.store.conn.execute("UPDATE memory SET visual_evidence=? WHERE memory_id=?",
                             (json.dumps([legacy]), rec.memory_id))
    agent.store.close()
    reopened = make_agent()
    reopened.remember("My car is blue.", timestamp="2026-10-10")
    visual = next(e for e in reopened.ask("Show the evidence for my car.").evidence
                  if e["modality"] == "image")
    assert visual["timestamp"] == "2026-10-20T00:00:00"
    assert visual["session_id"] == "legacy"
    assert visual["image_path"] == legacy["image_path"]
    assert visual["detector_model"] == ""
    assert visual["ingested_at"] == reopened.timeline_for("car")[0].ingested_at
    assert reopened.timeline_for("car")[0].timestamp == "2026-10-10T00:00:00"


def test_benchmark_agents_never_open_configured_user_database(tmp_path):
    from src.agent.reasoning import build_components
    from src.evaluation.ablations import build_systems

    cfg = load_config()
    db = tmp_path / "untouched.db"
    cfg["paths"]["db_path"] = str(db)
    factories = build_systems(build_components(cfg, light=True), cfg)
    for name in ("D_proposed_no_linking", "E_proposed", "E_text_input_only", "E_image_input_only"):
        system = factories[name]()
        agent = getattr(system, "inner", system)
        try:
            system.reset()
            assert agent.store.db_path == ":memory:"
            assert agent.image_dir is None
        finally:
            agent.store.close()
    assert not db.exists()


def test_streamlit_browser_sessions_are_isolated_and_persistent(tmp_path, monkeypatch):
    st = pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    import src.agent.reasoning as reasoning
    import src.config as config

    cfg = load_config()
    cfg["paths"]["db_path"] = str(tmp_path / "ui" / "memory.db")
    cfg["paths"]["image_dir"] = str(tmp_path / "ui_images")
    monkeypatch.setattr(config, "load_config", lambda: deepcopy(cfg))
    build = reasoning.build_components
    monkeypatch.setattr(reasoning, "build_components", lambda cfg=None, light=False: build(cfg, light=True))
    monkeypatch.setattr(reasoning, "load_intent_model", lambda: None)
    st.cache_resource.clear()
    app = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
    first, second = AppTest.from_file(app), AppTest.from_file(app)

    def click(at, label):
        next(b for b in at.button if b.label == label).click().run()
        assert not at.exception

    try:
        first.run()
        assert not first.exception
        next(t for t in first.text_input if t.label == "What happened?").set_value("My car is red.")
        click(first, "Store")
        second.run()
        assert not second.exception
        assert any("Nothing stored yet" in i.value for i in second.info)
        next(t for t in second.text_input if t.label == "What happened?").set_value("My car is blue.")
        click(second, "Store")
        a, b = first.session_state["memory_agent"], second.session_state["memory_agent"]
        assert a is not b
        assert a.store.db_path != b.store.db_path
        assert Path(a.store.db_path).is_file() and Path(b.store.db_path).is_file()
        assert a.ask("What color is my car now?").value == "red"
        assert b.ask("What color is my car now?").value == "blue"
        first.run()
        assert first.session_state["memory_agent"] is a
        # Changing model mode must keep the same session's stored memory.
        first.toggle[0].set_value(not first.toggle[0].value).run()
        assert not first.exception
        assert first.session_state["memory_agent"].ask("What color is my car now?").value == "red"
        click(first, "Reset memory")
        second.run()
        assert not second.exception
        assert second.session_state["memory_agent"].ask("What color is my car now?").value == "blue"
    finally:
        for at in (first, second):
            if "memory_agent" in at.session_state:
                at.session_state["memory_agent"].store.close()
        st.cache_resource.clear()
