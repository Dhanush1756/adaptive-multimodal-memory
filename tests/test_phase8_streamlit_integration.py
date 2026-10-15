"""Phase 8 user-facing integration regressions.

Streamlit tests run in Light mode with temporary SQLite/image paths.  The visual
case intentionally uses detector-free contextual evidence; it is not a real-model
inference test.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

from src.agent.reasoning import MemoryAgent
from src.config import load_config
from src.cv.detection import Detection
from src.data.synthetic import render_object
from src.memory.schema import Status
from src.memory.store import MemoryStore


@pytest.fixture()
def app_test(tmp_path, monkeypatch):
    pytest.importorskip("streamlit")
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

    app = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
    at = AppTest.from_file(app).run()
    assert not at.exception
    yield at
    if "memory_agent" in at.session_state:
        at.session_state["memory_agent"].store.close()


def _input(at, label):
    return next(item for item in at.text_input if item.label == label)


def _click(at, label):
    next(button for button in at.button if button.label == label).click().run()
    assert not at.exception


def _store(at, text, day, session_id):
    _input(at, "What happened?").set_value(text)
    next(item for item in at.date_input if item.label == "Date").set_value(date(2026, 10, day))
    _input(at, "Session id (optional)").set_value(session_id)
    _click(at, "Store")


def _ask(at, question):
    _input(at, "Question").set_value(question)
    _click(at, "Ask")
    return [item.value for item in at.markdown], [item.value for item in at.caption]


def _png_bytes(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_streamlit_red_blue_black_queries_timeline_and_evidence(app_test):
    at = app_test
    _store(at, "My car is red.", 1, "red-source")
    _store(at, "I repainted my car blue.", 10, "blue-source")
    _store(at, "I painted my car black.", 20, "black-source")

    timeline_text = "\n".join(item.value for item in at.markdown)
    assert all(value in timeline_text for value in ("red", "blue", "black"))
    assert "2026-10-01" in timeline_text and "2026-10-20" in timeline_text
    agent = at.session_state["memory_agent"]
    chain = agent.timeline_for("car")
    assert [r.status for r in chain] == [Status.HISTORICAL, Status.HISTORICAL, Status.CURRENT]
    assert [r.previous_memory_id for r in chain] == [None, chain[0].memory_id, chain[1].memory_id]

    cases = {
        "What color is my car now?": "currently black",
        "What color was my car before?": "was blue",
        "What color was my car originally?": "originally red",
    }
    for question, expected in cases.items():
        markdown, captions = _ask(at, question)
        assert expected in "\n".join(markdown).lower()
        assert any("status: answered" in text for text in captions)

    markdown, _ = _ask(at, "Show me the history of my car's color.")
    answer = "\n".join(markdown).lower()
    assert "timeline:" in answer and all(value in answer for value in ("red", "blue", "black"))

    markdown, _ = _ask(at, "What color was my car on 2026-10-15?")
    assert "was blue" in "\n".join(markdown).lower()

    markdown, _ = _ask(at, "How do you know my car is black?")
    evidence = "\n".join(markdown)
    assert "black-source" in evidence and "2026-10-20" in evidence


def test_streamlit_two_car_timelines_are_separate_and_ambiguous_query_abstains(app_test):
    at = app_test
    _store(at, "My first car is red.", 1, "first-source")
    _store(at, "My second car is blue.", 2, "second-source")

    rendered = "\n".join(item.value for item in at.markdown).lower()
    assert "car_001" in rendered and "first car" in rendered and "red" in rendered
    assert "car_002" in rendered and "second car" in rendered and "blue" in rendered

    selector = next(item for item in at.selectbox if item.label == "Timeline entity")
    selector.select("car_001").run()
    assert not at.exception
    rendered = "\n".join(item.value for item in at.markdown).lower()
    assert "car_001" in rendered and "car_002" not in rendered
    selector = next(item for item in at.selectbox if item.label == "Timeline entity")
    selector.select("car_002").run()
    assert not at.exception
    rendered = "\n".join(item.value for item in at.markdown).lower()
    assert "car_002" in rendered and "car_001" not in rendered

    first, _ = _ask(at, "What colour is my first car?")
    assert "currently red" in "\n".join(first).lower()
    second, _ = _ask(at, "What colour is my second car?")
    assert "currently blue" in "\n".join(second).lower()
    ambiguous, captions = _ask(at, "What colour is my car?")
    assert "don't have enough" in "\n".join(ambiguous).lower()
    assert any("status: abstained" in text and "found: False" in text for text in captions)
    unknown, captions = _ask(at, "What colour is my phone?")
    assert "don't have enough" in "\n".join(unknown).lower()
    assert any("status: abstained" in text for text in captions)


def test_streamlit_displays_contextual_image_as_non_supporting(app_test):
    at = app_test
    agent = at.session_state["memory_agent"]
    result = agent.remember(
        "My car is blue.", Image.new("RGB", (64, 64), "red"),
        "2026-10-05", "mixed-source",
    )
    assert result.image["association_status"] == "contextual"
    assert agent.timeline_for("car")[0].visual_evidence[0].supports_state is False
    at.run()
    markdown, _ = _ask(at, "How do you know my car is blue?")
    evidence = "\n".join(markdown)
    assert "mixed-source" in evidence and "2026-10-05" in evidence
    assert "contextual, non-supporting" in evidence
    answer = agent.ask("How do you know my car is blue?")
    assert all("IMG_" not in evidence_id for evidence_id in answer.supporting_evidence_ids)
    assert answer.value == "blue"


def test_streamlit_ask_accepts_image_only_and_stores_contextual_provenance(app_test):
    at = app_test
    _store(at, "My car is red.", 1, "red-source")

    uploader = next(item for item in at.file_uploader if item.label == "Image to ask about (optional)")
    uploader.set_value(("white-car.png", _png_bytes(render_object("car", "white")), "image/png"))
    next(item for item in at.date_input if item.label == "Image date").set_value(date(2026, 10, 2))
    _click(at, "Ask")

    agent = at.session_state["memory_agent"]
    record = agent.timeline_for("car")[0]
    assert record.value == "red"
    assert len(record.visual_evidence) == 1
    assert record.visual_evidence[0].value == "white"
    assert record.visual_evidence[0].supports_state is False
    assert at.session_state["last_ask_image"].decision.action.value == "MERGE"
    rendered_warnings = "\n".join(item.value for item in at.warning).lower()
    assert "appears 'white'" in rendered_warnings and "state remains 'red'" in rendered_warnings


def test_streamlit_surfaces_controlled_conflict_as_uncertain(app_test, monkeypatch):
    """Controlled detector output exercises UI plumbing, not detector accuracy."""
    at = app_test
    agent = at.session_state["memory_agent"]
    monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
        Detection("car", "car", [40, 78, 280, 207], 0.95),
    ])
    agent.remember("My car is red.", render_object("car", "red"), "2026-10-01", "red")
    conflict = agent.remember("My car is blue.", render_object("car", "red"), "2026-10-05", "conflict")
    assert conflict.decision.action.value == "CONTRADICTORY"
    at.run()

    markdown, captions = _ask(at, "What color is my car now?")
    rendered = "\n".join(markdown).lower()
    assert "currently red" in rendered and "conflicting evidence" in rendered
    assert any("status: uncertain" in text for text in captions)
    assert any("Conflict" in item.value for item in at.warning)


def test_streamlit_surfaces_cv_failure_note_while_retaining_text(app_test, monkeypatch):
    at = app_test
    agent = at.session_state["memory_agent"]

    def fail(*args, **kwargs):
        raise ValueError("controlled unreadable image")

    monkeypatch.setattr(agent.comp.visual, "analyze", fail)
    result = agent.remember(
        "My phone is green.", Image.new("RGB", (32, 32), "green"),
        "2026-10-07", "bad-image",
    )
    at.session_state["last"] = result
    at.run()
    assert agent.ask("What color is my phone now?").value == "green"
    assert any("image analysis unavailable (ValueError)" in item.value for item in at.caption)


def test_file_reopen_preserves_identity_timelines(tmp_path):
    db = tmp_path / "persisted" / "memory.db"
    first = MemoryAgent(db_path=str(db), light=True, image_dir=str(tmp_path / "images"))
    first.remember("My first car is red.", timestamp="2026-10-01", session_id="first")
    first.remember("My second car is blue.", timestamp="2026-10-02", session_id="second")
    first.store.close()

    reopened = MemoryAgent(db_path=str(db), light=True, image_dir=str(tmp_path / "images"))
    try:
        assert reopened.ask("What colour is my first car?").value == "red"
        assert reopened.ask("What colour is my second car?").value == "blue"
        assert [r.value for r in reopened.timeline_for("car", entity_ref="first car")] == ["red"]
        assert [r.value for r in reopened.timeline_for("car", entity_ref="second car")] == ["blue"]
    finally:
        reopened.store.close()


def test_pre_entity_ref_database_migrates_without_losing_history(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE memory (
            memory_id TEXT PRIMARY KEY, seq INTEGER NOT NULL, session_id TEXT,
            entity TEXT NOT NULL, entity_id TEXT NOT NULL, attribute TEXT NOT NULL,
            value TEXT NOT NULL, timestamp TEXT NOT NULL, confidence REAL,
            status TEXT NOT NULL, previous_memory_id TEXT, event TEXT,
            conflicting_value TEXT, text_evidence TEXT, visual_evidence TEXT, source TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO memory VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("M001", 1, "legacy", "car", "car_001", "color", "red",
         "2026-10-01T00:00:00", 0.9, "CURRENT", None, None, None,
         json.dumps([{"text": "My car is red.", "session_id": "legacy",
                      "timestamp": "2026-10-01T00:00:00", "confidence": 0.9,
                      "embedding": None}]), "[]", "user_interaction"),
    )
    conn.commit()
    conn.close()

    store = MemoryStore(str(db))
    try:
        columns = {row[1] for row in store.conn.execute("PRAGMA table_info(memory)")}
        assert "entity_ref" in columns
        records = store.all()
        assert len(records) == 1 and records[0].value == "red"
        assert records[0].entity_ref == "" and records[0].text_evidence[0].session_id == "legacy"
    finally:
        store.close()
