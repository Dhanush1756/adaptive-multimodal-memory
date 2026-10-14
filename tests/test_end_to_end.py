"""End-to-end tests in light mode (hashing embeddings, HSV colour, no downloads).

They follow the brief's first implementation target (section 78) and the laptop scenario (48).
"""
import random

import pytest

from src.agent.reasoning import MemoryAgent
from src.config import load_config
from src.data.synthetic import render_object
from src.cv.detection import Detection
from src.memory.schema import Action, Status
from src.memory.state_tracker import transitions


@pytest.fixture()
def agent():
    agent = MemoryAgent(load_config(), db_path=":memory:", light=True, use_intent_model=False)
    yield agent
    agent.store.close()


def img(entity, color, seed=0):
    return render_object(entity, color, random.Random(seed))


def test_red_then_blue_car(agent):
    r1 = agent.remember("I bought a red car.", img("car", "red"), "2026-10-01T10:00:00")
    assert r1.decision.action == Action.ADD
    r2 = agent.remember("I repainted my car blue.", img("car", "blue", 1), "2026-10-10T10:00:00")
    assert r2.decision.action == Action.UPDATE

    now = agent.ask("What color is my car now?")
    assert now.found and now.value == "blue"
    orig = agent.ask("What color was my car originally?")
    assert orig.value == "red"
    prev = agent.ask("What color was my car before?")
    assert prev.value == "red"
    assert agent.ask("When did my car's color change?").value == "2026-10-10"
    red, blue = agent.timeline_for("car")
    assert (red.value, red.status) == ("red", Status.HISTORICAL)
    assert (blue.value, blue.status) == ("blue", Status.CURRENT)
    assert blue.previous_memory_id == red.memory_id


def test_evidence_is_cited_from_both_modalities(agent):
    agent.remember("I bought a red car.", img("car", "red"), "2026-10-01T10:00:00")
    agent.remember("I repainted my car blue.", img("car", "blue", 1), "2026-10-10T10:00:00")
    ans = agent.ask("How do you know my car is blue?")
    mods = {e["modality"] for e in ans.evidence}
    assert mods == {"text", "image"}
    assert all(e["value"] == "blue" for e in ans.evidence)


def test_three_states_and_before_anchor(agent):
    for text, color, ts in [("My car is red.", "red", "2026-10-01T10:00:00"),
                            ("I repainted my car blue.", "blue", "2026-10-10T10:00:00"),
                            ("I repainted my car black.", "black", "2026-10-20T10:00:00")]:
        agent.remember(text, img("car", color), ts)
    assert agent.ask("What color is my car now?").value == "black"
    assert agent.ask("What color was my car before it became black?").value == "blue"
    assert agent.ask("What color was my car originally?").value == "red"
    assert agent.ask("Show me the history of my car's color.").value == ["red", "blue", "black"]
    assert agent.ask("What color was my car before?").value == "blue"
    chain = agent.timeline_for("car")
    assert [r.timestamp for r in chain] == [
        "2026-10-01T10:00:00", "2026-10-10T10:00:00", "2026-10-20T10:00:00"]
    assert [r.previous_memory_id for r in chain] == [None, chain[0].memory_id, chain[1].memory_id]
    assert [r.status for r in chain] == [Status.HISTORICAL, Status.HISTORICAL, Status.CURRENT]
    changes = transitions(agent.store, "car_001", "color")
    assert [t["changed_at"] for t in changes] == [r.timestamp for r in chain[1:]]
    assert [(t["from_memory_id"], t["to_memory_id"]) for t in changes] == [
        (chain[0].memory_id, chain[1].memory_id), (chain[1].memory_id, chain[2].memory_id)]


def test_text_image_conflict_is_flagged_not_applied(agent, monkeypatch):
    monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
        Detection("car", "car", [40, 78, 280, 207], .95)])
    agent.remember("My car is red.", img("car", "red"), "2026-10-01T10:00:00")
    r = agent.remember("My car is blue.", img("car", "red", 3), "2026-10-05T10:00:00")
    assert r.decision.action == Action.CONTRADICTORY
    ans = agent.ask("What color is my car now?")
    assert ans.value == "red" and "conflicting" in ans.text.lower()


def test_laptop_roundtrip_uses_image_for_valueless_text(agent, monkeypatch):
    monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
        Detection("laptop", "laptop", [40, 40, 280, 190], .95)])
    agent.remember("My laptop is black.", img("laptop", "black"), "2026-10-01T10:00:00")
    agent.remember("I put a blue skin on my laptop.", img("laptop", "blue", 1), "2026-10-05T10:00:00")
    r = agent.remember("I removed the skin from my laptop.", img("laptop", "black", 2), "2026-10-09T10:00:00")
    assert r.decision.action == Action.UPDATE
    assert agent.ask("What color is my laptop now?").value == "black"
    assert agent.ask("What color was my laptop originally?").value == "black"
    assert agent.ask("Was my laptop originally blue?").value == "no"


def test_irrelevant_text_is_ignored_and_empty_memory_is_honest(agent):
    r = agent.remember("I like pizza.", None, "2026-10-01T10:00:00")
    assert r.decision.action == Action.IGNORE
    ans = agent.ask("What color is my car now?")
    assert not ans.found and "don't have enough" in ans.text.lower()


def test_text_only_and_image_only_inputs_do_not_crash(agent, monkeypatch):
    monkeypatch.setattr(agent.comp.visual.detector, "detect", lambda image: [
        Detection("car", "car", [40, 78, 280, 207], .95)])
    assert agent.remember("My car is green.", None, "2026-10-01T10:00:00").decision.action == Action.ADD
    r = agent.remember("", img("car", "green", 4), "2026-10-02T10:00:00")
    assert r.decision.action == Action.MERGE
