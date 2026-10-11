"""Temporal selection semantics (pure function select_states) and query parsing."""
from dataclasses import dataclass
from typing import Optional

import pytest

from src.agent.query_parser import Intent, parse_query
from src.retrieval.temporal_retriever import select_states


@dataclass
class S:
    value: str
    timestamp: str
    event: Optional[str] = None


CHAIN = [S("red", "2026-10-01T10:00:00"), S("blue", "2026-10-10T10:00:00", "repaint"),
         S("black", "2026-10-20T10:00:00", "repaint")]


def sel(question):
    return select_states(parse_query(question, "2026-10-30T10:00:00", context_entity="car"), CHAIN)


@pytest.mark.parametrize("q,expected", [
    ("What color is my car now?", "black"),
    ("What color was my car originally?", "red"),
    ("What color was my car before?", "blue"),
    ("What color was my car before it became black?", "blue"),
    ("What color was my car before it became blue?", "red"),
    ("What color did my car become after red?", "blue"),
    ("Was my car red before it became blue?", "yes"),
    ("Was my car black before it became blue?", "no"),
    ("Is my car blue now?", "no"),
])
def test_value_questions(q, expected):
    s = sel(q)
    assert s.found and s.value == expected


def test_never_just_newest_for_historical_queries():
    assert sel("What color was my car before it became black?").value != "black"


def test_when_change_history_and_as_of():
    assert sel("When did my car become blue?").value == "2026-10-10"
    assert sel("When did my car's color change?").value == "2026-10-20"
    assert sel("What changed about my car?").value == "blue->black"
    assert sel("Show me the history of my car's color.").value == ["red", "blue", "black"]
    assert sel("What color was my car on 2026-10-12?").value == "blue"


def test_missing_history_is_not_invented():
    one = [S("red", "2026-10-01T10:00:00")]
    p = parse_query("What color was my car before?", "2026-10-30T10:00:00", context_entity="car")
    assert not select_states(p, one).found
    assert not select_states(p, []).found


def test_intent_detection():
    assert parse_query("How do you know my car is blue?").intent == Intent.EVIDENCE
    assert parse_query("Show the evidence.", context_entity="car").intent == Intent.EVIDENCE
    assert parse_query("What color is it?", context_entity="car").entity == "car"
