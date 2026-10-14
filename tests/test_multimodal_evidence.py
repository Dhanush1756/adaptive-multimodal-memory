"""Deterministic Phase 2 evidence-linking and retrieval regression tests."""
from __future__ import annotations

from PIL import Image

from src.agent.reasoning import MemoryAgent
from src.config import load_config
from src.cv.detection import Detection
from src.data.synthetic import render_object
from src.memory.schema import Action


def _agent(path=":memory:"):
    return MemoryAgent(load_config(), db_path=path, light=True, use_intent_model=False)


def _remember(agent, text, color, day):
    return agent.remember(text, render_object("car", color), f"2026-10-{day:02d}", f"d{day}")


def test_selected_current_and_historical_states_return_their_own_visual_evidence():
    agent = _agent()
    try:
        _remember(agent, "My car is red.", "red", 1)
        _remember(agent, "I repainted my car blue.", "blue", 10)
        current = agent.ask("How do you know my car is blue?")
        original = agent.ask("How do you know what color my car was originally?")
        assert {e["visual_value"] for e in current.evidence if e["modality"] == "image"} == {"blue"}
        assert {e["visual_value"] for e in original.evidence if e["modality"] == "image"} == {"red"}
        assert {e["timestamp"] for e in current.evidence} == {"2026-10-10T00:00:00"}
        assert {e["timestamp"] for e in original.evidence} == {"2026-10-01T00:00:00"}
    finally:
        agent.store.close()


def test_qa_uses_image_retriever_hits_not_a_direct_state_walk(monkeypatch):
    agent = _agent()
    try:
        _remember(agent, "My car is red.", "red", 1)
        calls = []
        real = agent.retriever.image_retriever.for_records

        def spy(records):
            calls.append([r.memory_id for r in records])
            return real(records)

        monkeypatch.setattr(agent.retriever.image_retriever, "for_records", spy)
        answer = agent.ask("How do you know my car is red?")
        assert calls == [[agent.timeline_for("car")[0].memory_id]]
        assert any(e["modality"] == "image" for e in answer.evidence)
    finally:
        agent.store.close()


def test_matching_detector_marks_visual_evidence_verified(monkeypatch):
    agent = _agent()
    try:
        monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
            Detection("car", "car", [0, 0, 320, 240], .92),
        ])
        result = agent.remember("My car is blue.", Image.new("RGB", (64, 64), (30, 30, 220)), "2026-10-01", "d1")
        ve = agent.timeline_for("car")[0].visual_evidence[0]
        assert result.decision.action == Action.ADD
        assert ve.association_status == "verified"
        assert ve.label == "car"
    finally:
        agent.store.close()


def test_mismatched_or_ambiguous_detection_does_not_confirm_or_conflict(monkeypatch):
    agent = _agent()
    try:
        monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
            Detection("laptop", "laptop", [1, 1, 40, 40], .92),
        ])
        result = _remember(agent, "My car is blue.", "red", 1)
        record = agent.timeline_for("car")[0]
        assert result.decision.action == Action.ADD
        assert record.visual_evidence == []
        assert any("image association unavailable" in note for note in result.notes)

        monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
            Detection("car", "car", [0, 0, 140, 240], .92),
            Detection("car", "car", [160, 0, 320, 240], .91),
        ])
        result = _remember(agent, "I repainted my car blue.", "red", 2)
        assert result.decision.action == Action.MERGE
        assert agent.timeline_for("car")[-1].visual_evidence == []
        assert any("image association unavailable" in note for note in result.notes)
    finally:
        agent.store.close()


def test_failed_visual_analysis_keeps_text_memory_and_reports_uncertainty(monkeypatch):
    agent = _agent()
    try:
        def fail(*args, **kwargs):
            raise ValueError("bad image")

        monkeypatch.setattr(agent.comp.visual, "analyze", fail)
        result = _remember(agent, "My car is red.", "red", 1)
        assert result.decision.action == Action.ADD
        assert agent.ask("What color is my car now?").value == "red"
        assert any("image analysis unavailable (ValueError)" in note for note in result.notes)
    finally:
        agent.store.close()


def test_missing_source_timestamp_is_marked_as_an_ingestion_time_fallback():
    agent = _agent()
    try:
        result = agent.remember("My car is red.", session_id="no-time")
        assert result.decision.action == Action.ADD
        assert any("source timestamp was missing" in note for note in result.notes)
        assert agent.timeline_for("car")[0].timestamp == result.timestamp
    finally:
        agent.store.close()


def test_persisted_visual_provenance_and_legacy_json_are_readable(tmp_path):
    path = str(tmp_path / "memory.db")
    agent = _agent(path)
    try:
        _remember(agent, "My car is red.", "red", 1)
        ev = agent.timeline_for("car")[0].visual_evidence[0]
        assert ev.association_status == "contextual"
        assert ev.supports_state is False
    finally:
        agent.store.close()
    reopened = _agent(path)
    try:
        ev = reopened.timeline_for("car")[0].visual_evidence[0]
        assert ev.association_status == "contextual"
        assert ev.supports_state is False
        assert ev.timestamp == "2026-10-01T00:00:00" and ev.session_id == "d1"
    finally:
        reopened.store.close()
