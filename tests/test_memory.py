"""Unit tests for the adaptive memory engine (brief milestones 1, 2, 5 and contradiction handling).

These tests need no ML models: candidates are built by hand.
"""
import pytest

from src.memory.schema import Action, Candidate, Claim, Status, TextEvidence, VisualEvidence
from src.memory.state_tracker import conflicts, timeline, transitions
from src.memory.store import MemoryStore
from src.memory.update import MemoryEngine

CFG = {
    "nlp": {"tracked_entities": ["car", "laptop"], "tracked_attributes": ["color"]},
    "memory": {"min_claim_confidence": 0.3, "conflict_text_conf": 0.6, "conflict_visual_conf": 0.6},
}


def cand(value, ts, text=True, img=None, text_conf=0.95, img_conf=0.9, event=None, entity="car", session="S"):
    claim = (
        Claim(entity, "color", value, event=event, confidence=text_conf, source_text=f"my {entity} is {value}")
        if text
        else None
    )
    visual = (
        VisualEvidence(
            image_id=f"IMG_{img}_{ts}", label=entity, value=img, confidence=img_conf, detection_confidence=0.9
        )
        if img
        else None
    )
    return Candidate(
        session_id=session,
        timestamp=ts,
        claim=claim,
        text_evidence=TextEvidence(claim.source_text, session, ts, text_conf) if claim else None,
        visual=visual,
        agreement=1.0 if (claim and visual and claim.value == visual.value) else None,
        confidence=text_conf if text else img_conf,
    )


@pytest.fixture()
def engine():
    store = MemoryStore(":memory:")
    return MemoryEngine(store, CFG)


# ---------------------------------------------------------------- milestone 1 / 2
def test_add_then_update_keeps_history(engine):
    d1 = engine.process(cand("red", "2026-10-01", img="red"))
    assert d1.action == Action.ADD

    d2 = engine.process(cand("blue", "2026-10-10", img="blue", event="repaint"))
    assert d2.action == Action.UPDATE
    assert d2.previous_value == "red"
    assert d2.superseded_memory_id == d1.memory_id

    cur = engine.store.current("car_001", "color")
    assert cur.value == "blue" and cur.status == Status.CURRENT
    assert cur.previous_memory_id == d1.memory_id

    old = engine.store.get(d1.memory_id)
    assert old.value == "red" and old.status == Status.HISTORICAL  # never deleted


def test_timeline_and_transition(engine):
    engine.process(cand("red", "2026-10-01"))
    engine.process(cand("blue", "2026-10-10", event="repaint"))
    engine.process(cand("black", "2026-10-20", event="repaint"))

    chain = timeline(engine.store, "car_001", "color")
    assert [r.value for r in chain] == ["red", "blue", "black"]
    assert [r.status for r in chain] == [Status.HISTORICAL, Status.HISTORICAL, Status.CURRENT]

    tr = transitions(engine.store, "car_001", "color")
    assert [(t["from_value"], t["to_value"]) for t in tr] == [("red", "blue"), ("blue", "black")]
    assert tr[0]["event"] == "repaint"


# ------------------------------------------------------------------------ MERGE
def test_same_value_merges_evidence_not_duplicates(engine):
    d1 = engine.process(cand("blue", "2026-10-01"))
    d2 = engine.process(cand("blue", "2026-10-02", img="blue"))
    assert d2.action == Action.MERGE
    assert d2.memory_id == d1.memory_id
    assert len(engine.store.all()) == 1
    rec = engine.store.get(d1.memory_id)
    assert len(rec.text_evidence) == 2 and len(rec.visual_evidence) == 1
    assert rec.confidence > 0.95  # corroboration raises confidence


# ----------------------------------------------------------------- CONTRADICTORY
def test_text_vs_image_conflict_does_not_overwrite(engine):
    engine.process(cand("red", "2026-10-01", img="red"))
    d = engine.process(cand("blue", "2026-10-10", img="red", text_conf=0.9, img_conf=0.88))
    assert d.action == Action.CONTRADICTORY

    cur = engine.store.current("car_001", "color")
    assert cur.value == "red"  # chain untouched
    bad = conflicts(engine.store, "car_001", "color")
    assert len(bad) == 1
    assert bad[0].value == "blue" and bad[0].conflicting_value == "red"
    assert bad[0].text_evidence and bad[0].visual_evidence  # both sources preserved


def test_weak_visual_disagreement_is_not_a_conflict(engine):
    engine.process(cand("red", "2026-10-01"))
    d = engine.process(cand("blue", "2026-10-10", img="red", text_conf=0.9, img_conf=0.35))
    assert d.action == Action.UPDATE


def test_image_only_change_is_flagged_not_applied(engine):
    engine.process(cand("red", "2026-10-01"))
    d = engine.process(cand("blue", "2026-10-10", text=False, img="blue"))
    assert d.action == Action.CONTRADICTORY
    assert engine.store.current("car_001", "color").value == "red"


def test_image_only_confirmation_merges(engine):
    engine.process(cand("red", "2026-10-01"))
    d = engine.process(cand("red", "2026-10-05", text=False, img="red"))
    assert d.action == Action.MERGE


# ------------------------------------------------------------------------ IGNORE
def test_irrelevant_entity_is_ignored(engine):
    d = engine.process(cand("green", "2026-10-01", entity="pizza"))
    assert d.action == Action.IGNORE
    assert engine.store.stats()["TOTAL"] == 0


def test_low_confidence_claim_is_ignored(engine):
    d = engine.process(cand("red", "2026-10-01", text_conf=0.1))
    assert d.action == Action.IGNORE


def test_empty_candidate_is_ignored(engine):
    d = engine.process(Candidate(session_id="S", timestamp="2026-10-01"))
    assert d.action == Action.IGNORE


# --------------------------------------------------------------- out-of-order
def test_out_of_order_old_evidence_becomes_historical(engine):
    engine.process(cand("red", "2026-10-01"))
    engine.process(cand("black", "2026-10-20"))
    d = engine.process(cand("blue", "2026-10-10"))  # arrives late
    assert d.action == Action.HISTORICAL

    chain = timeline(engine.store, "car_001", "color")
    assert [r.value for r in chain] == ["red", "blue", "black"]
    assert engine.store.current("car_001", "color").value == "black"
    assert chain[1].previous_memory_id == chain[0].memory_id
    assert chain[2].previous_memory_id == chain[1].memory_id


def test_late_duplicate_of_newer_state_merges(engine):
    engine.process(cand("red", "2026-10-01"))
    d_blue = engine.process(cand("blue", "2026-10-20"))
    d = engine.process(cand("blue", "2026-10-10", img="blue"))
    assert d.action == Action.MERGE and d.memory_id == d_blue.memory_id
    assert len(timeline(engine.store, "car_001", "color")) == 2


# ------------------------------------------------------------ other behaviours
def test_value_synonyms_merge(engine):
    engine.process(cand("gray", "2026-10-01"))
    d = engine.process(cand("grey", "2026-10-02"))
    assert d.action == Action.MERGE


def test_entities_are_tracked_separately(engine):
    engine.process(cand("red", "2026-10-01", entity="car"))
    d = engine.process(cand("black", "2026-10-02", entity="laptop"))
    assert d.action == Action.ADD
    assert engine.store.current("car_001", "color").value == "red"
    assert engine.store.current("laptop_001", "color").value == "black"


def test_laptop_scenario_black_blue_black(engine):
    """Brief section 48: state returns to an earlier value; original must stay original."""
    engine.process(cand("black", "2026-10-01", entity="laptop"))
    engine.process(cand("blue", "2026-10-05", entity="laptop", event="apply_skin"))
    d = engine.process(cand("black", "2026-10-09", entity="laptop", event="remove_skin"))
    assert d.action == Action.UPDATE  # not MERGE: black is not the state in effect at t3
    chain = timeline(engine.store, "laptop_001", "color")
    assert [r.value for r in chain] == ["black", "blue", "black"]
    assert chain[-1].status == Status.CURRENT


def test_decision_is_inspectable(engine):
    engine.process(cand("red", "2026-10-01"))
    d = engine.process(cand("blue", "2026-10-10", img="blue"))
    info = d.to_dict()
    assert info["action"] == "UPDATE"
    assert info["entity_match"] == 1.0 and info["attribute_match"] == 1.0
    assert info["temporal_relation"] == "later"
    assert info["visual_agreement"] == 1.0
