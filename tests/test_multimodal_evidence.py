"""Deterministic Phase 2 evidence-linking and retrieval regression tests."""
from __future__ import annotations

from PIL import Image
import pytest

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


def test_contextual_image_is_cross_checked_without_rewriting_text_state():
    agent = _agent()
    try:
        result = _remember(agent, "My car is red.", "white", 1)
        record = agent.timeline_for("car")[0]

        assert result.decision.action == Action.ADD
        assert result.candidate.agreement == 0.0
        assert record.value == "red"
        assert record.visual_evidence[0].value == "white"
        assert record.visual_evidence[0].supports_state is False
        assert any("cross-check warning" in note.lower() for note in result.notes)
        assert any("text says 'red'" in note.lower() and "appears 'white'" in note.lower()
                   for note in result.notes)
    finally:
        agent.store.close()


def test_image_only_contextual_observation_attaches_without_changing_known_state():
    agent = _agent()
    try:
        agent.remember("My car is red.", timestamp="2026-10-01", session_id="text")
        result = agent.remember(
            "", render_object("car", "white"), "2026-10-02", "ask-image",
        )
        record = agent.timeline_for("car")[0]

        assert result.decision.action == Action.MERGE
        assert record.value == "red"
        assert len(record.visual_evidence) == 1
        visual = record.visual_evidence[0]
        assert visual.value == "white"
        assert visual.association_status == "contextual"
        assert visual.supports_state is False
        assert visual.timestamp == "2026-10-02T00:00:00"
        assert visual.session_id == "ask-image"
        assert "state remains 'red'" in result.decision.reason.lower()
    finally:
        agent.store.close()


def test_human_verification_can_accept_contextual_image_value():
    agent = _agent()
    try:
        result = _remember(agent, "My car is red.", "white", 1)
        request = agent.verification_request(result)
        assert request is not None
        assert request["memory_value"] == "red"
        assert request["image_value"] == "white"

        verified = agent.verify(result, "white")
        assert verified.decision.action == Action.UPDATE
        assert agent.ask("What color is my car now?").value == "white"
        assert [r.value for r in agent.timeline_for("car")] == ["red", "white"]
    finally:
        agent.store.close()


def test_contextual_text_choice_freezes_original_evidence_snapshot():
    agent = _agent()
    try:
        disagreement = _remember(agent, "My car is red.", "white", 1)
        source_id = disagreement.decision.memory_id
        assert len(agent.store.get(source_id).text_evidence) == 1
        verified = agent.verify(disagreement, "red", rationale="the text is authoritative")
        assert verified.decision.memory_id == source_id
        # The confirmation merges into the live state, while the audit snapshot
        # remains exactly the evidence that existed when the choice was made.
        assert len(agent.store.get(source_id).text_evidence) == 2
        audit = agent.conflict_audit()[0]
        assert len(audit["original_text_evidence"]) == 1
        assert len(audit["original_visual_evidence"]) == 1
        assert audit["rationale"] == "the text is authoritative"
    finally:
        agent.store.close()


def test_human_verification_resolves_detector_verified_conflict(monkeypatch, tmp_path):
    path = str(tmp_path / "verified.db")
    agent = _agent(path)
    conflict_id = None
    try:
        monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
            Detection("car", "car", [0, 0, 320, 240], .95),
        ])
        agent.remember("My car is red.", timestamp="2026-10-01", session_id="red")
        conflict = agent.remember(
            "My car is blue.", render_object("car", "red"), "2026-10-02", "conflict",
        )
        assert conflict.decision.action == Action.CONTRADICTORY
        assert agent.ask("What color is my car now?").status == "uncertain"

        verified = agent.verify(conflict, "blue", actor="reviewer", rationale="photo lighting is misleading")
        assert verified.decision.action == Action.UPDATE
        conflict_id = conflict.decision.memory_id
        resolved = agent.store.get(conflict_id)
        assert resolved.status.value == "RESOLVED"
        answer = agent.ask("What color is my car now?")
        assert answer.value == "blue"
        assert answer.status == "answered"
        assert "conflicting evidence" not in answer.text.lower()
        audit = agent.conflict_audit()
        assert len(audit) == 1
        assert audit[0]["original_conflict_id"] == conflict_id
        assert audit[0]["resulting_memory_id"] == verified.decision.memory_id
        assert audit[0]["selected_value"] == "blue"
        assert audit[0]["selected_source"] == "text_or_memory"
        assert audit[0]["actor"] == "reviewer"
        assert audit[0]["rationale"] == "photo lighting is misleading"
        assert audit[0]["original_text_evidence"]
        assert audit[0]["original_visual_evidence"]
        before_retry = [r.to_dict() for r in agent.store.all()]
        with pytest.raises(ValueError, match="unresolved|already been resolved"):
            agent.verify(conflict, "red")
        assert [r.to_dict() for r in agent.store.all()] == before_retry
        assert len(agent.store.resolutions()) == 1
    finally:
        agent.store.close()

    reopened = _agent(path)
    try:
        assert reopened.store.get(conflict_id).status.value == "RESOLVED"
        answer = reopened.ask("What color is my car now?")
        assert answer.value == "blue" and answer.status == "answered"
        audit = reopened.conflict_audit()
        assert len(audit) == 1 and audit[0]["actor"] == "reviewer"
        assert len(audit[0]["original_text_evidence"]) == 1
        assert len(audit[0]["original_visual_evidence"]) == 1
    finally:
        reopened.store.close()


@pytest.mark.parametrize(
    ("accepted", "expected_source", "expected_current"),
    [("blue", "text_or_memory", "blue"), ("white", "image", "white")],
)
def test_both_verified_conflict_choices_preserve_history_and_reopen(
    monkeypatch, tmp_path, accepted, expected_source, expected_current,
):
    path = str(tmp_path / f"{accepted}.db")
    agent = _agent(path)
    try:
        monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
            Detection("car", "car", [0, 0, image.width, image.height], .99),
        ])
        agent.remember("My car is red.", timestamp="2026-10-01", session_id="initial")
        conflict = agent.remember(
            "My car is blue.", Image.new("RGB", (64, 64), "white"),
            "2026-10-05", "disagreement",
        )
        conflict_id = conflict.decision.memory_id
        assert conflict.decision.action == Action.CONTRADICTORY
        verified = agent.verify(conflict, accepted, actor="test_reviewer")
        assert agent.ask("What color is my car now?").value == expected_current
        assert agent.ask("What color was my car originally?").value == "red"
        audit = agent.conflict_audit()[0]
        assert audit["selected_source"] == expected_source
        assert audit["resulting_memory_id"] == verified.decision.memory_id
        assert audit["original_text_evidence"] and audit["original_visual_evidence"]
    finally:
        agent.store.close()

    reopened = _agent(path)
    try:
        assert reopened.ask("What color is my car now?").value == expected_current
        assert reopened.ask("What color was my car originally?").value == "red"
        assert reopened.store.get(conflict_id).status.value == "RESOLVED"
        audit = reopened.conflict_audit()
        assert len(audit) == 1 and audit[0]["selected_source"] == expected_source
    finally:
        reopened.store.close()


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


def test_unified_evidence_exposes_event_ingestion_and_extractor_provenance():
    agent = _agent()
    try:
        result = _remember(agent, "My car is red.", "red", 1)
        record = agent.timeline_for("car")[0]
        answer = agent.ask("Which text and image support my car color?")
        text = next(e for e in answer.evidence if e["modality"] == "text")
        image = next(e for e in answer.evidence if e["modality"] == "image")

        assert record.ingested_at and record.ingested_at == result.candidate.ingested_at
        assert text["evidence_id"] == "TXT_d1"
        assert text["timestamp"] == "2026-10-01T00:00:00"
        assert text["ingested_at"] == record.ingested_at
        assert text["extractor"] == "rules-v1"
        assert image["evidence_id"].startswith("IMG_")
        assert image["ingested_at"] == record.ingested_at
        assert image["detector_model"] == "none (whole-image fallback)"
        assert image["attribute_model"] == "hsv"
        assert image["embedding_model"] == "color-histogram"
    finally:
        agent.store.close()


def test_conflict_question_reports_unresolved_then_resolved_disagreement(monkeypatch):
    agent = _agent()
    try:
        monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
            Detection("car", "car", [0, 0, 320, 240], .95),
        ])
        agent.remember("My car is red.", timestamp="2026-10-01", session_id="base")
        conflict = agent.remember(
            "My car is blue.", render_object("car", "red"), "2026-10-02", "conflict",
        )

        answer = agent.ask("Do the text and image disagree about my car?")
        assert answer.intent == "CONFLICT"
        assert answer.value == "yes" and answer.status == "uncertain"
        assert "human verification" in answer.text.lower()
        assert any(e["role"] == "conflicting" for e in answer.evidence)

        agent.verify(conflict, "blue")
        resolved = agent.ask("Is there any text-image conflict for my car?")
        assert resolved.intent == "CONFLICT"
        assert resolved.value == "no" and resolved.status == "answered"
        assert "no unresolved" in resolved.text.lower()
    finally:
        agent.store.close()
