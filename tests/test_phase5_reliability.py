from datetime import datetime

from PIL import Image

from src.agent.reasoning import MemoryAgent
from src.memory.schema import Action


def test_contextual_laptop_image_cannot_contradict_car_text(tmp_path):
    agent = MemoryAgent(db_path=":memory:", light=True, image_dir=str(tmp_path / "images"))
    result = agent.remember("My car is blue.", Image.new("RGB", (80, 60), "red"),
                            "2026-10-01", "mixed")
    assert result.decisions[0].action == Action.ADD
    state = agent.timeline_for("car")[0]
    assert state.value == "blue"
    assert state.visual_evidence[0].association_status == "contextual"
    assert state.visual_evidence[0].supports_state is False
    assert agent.ask("What color is my car now?").value == "blue"


def test_multiple_contextual_images_never_establish_or_change_state(tmp_path):
    agent = MemoryAgent(db_path=":memory:", light=True, image_dir=str(tmp_path / "images"))
    for i, colour in enumerate(("red", "green", "black")):
        result = agent.remember("", Image.new("RGB", (50, 50), colour),
                                f"2026-10-0{i + 1}", f"image-{i}")
        assert result.decisions[0].action == Action.IGNORE
    assert agent.store.all() == []


def test_two_explicit_car_identities_remain_separate():
    agent = MemoryAgent(db_path=":memory:", light=True)
    agent.remember("My first car is red.", timestamp="2026-10-01", session_id="first")
    agent.remember("My second car is blue.", timestamp="2026-10-02", session_id="second")
    assert agent.ask("What colour is my first car?").value == "red"
    assert agent.ask("What colour is my second car?").value == "blue"
    ambiguous = agent.ask("What colour is my car?")
    assert not ambiguous.found and ambiguous.status == "abstained"
    assert "multiple" in ambiguous.note.lower()


def test_answer_contract_has_status_and_supporting_references():
    agent = MemoryAgent(db_path=":memory:", light=True)
    agent.remember("My car is red.", timestamp=datetime(2026, 10, 1), session_id="s1")
    answer = agent.ask("Which evidence supports the established car colour?")
    payload = answer.to_dict()
    assert payload["status"] == "answered"
    assert payload["supporting_state_ids"] and payload["supporting_evidence_ids"]
    assert answer.value == "red"


def test_deictic_past_observation_uses_supplied_event_time():
    agent = MemoryAgent(db_path=":memory:", light=True)
    result = agent.remember("On this date the car was blue.", timestamp="2026-10-10", session_id="dated")
    assert result.decisions[0].action == Action.ADD
    assert agent.timeline_for("car")[0].timestamp == "2026-10-10T00:00:00"


def test_optional_llm_cannot_replace_grounded_value_with_an_unsupported_one():
    agent = MemoryAgent(db_path=":memory:", light=True,
                        answer_llm=lambda prompt: "Your car was red, but it is green.")
    agent.remember("My car is red.", timestamp="2026-10-01", session_id="s1")
    answer = agent.ask("What colour is my car now?")
    assert answer.value == "red" and "red" in answer.text.lower()
    assert "green" not in answer.text.lower()
