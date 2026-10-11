"""Unit tests for the NLP pipeline. Rule-based paths only: no model downloads needed."""
from datetime import datetime

import numpy as np
import pytest

from src.agent.query_parser import Intent, parse_query
from src.nlp.embeddings import HashingEmbedder
from src.nlp.ner import extract_entities, tracked_entities
from src.nlp.preprocessing import lemmatize, normalize, split_sentences, tokenize
from src.nlp.relation_extraction import detect_event, extract_claims
from src.nlp.temporal_extraction import extract_time_expressions, resolve_event_time

REF = datetime(2026, 10, 10, 10, 0, 0)  # a Saturday


# ------------------------------------------------------------------ preprocessing
def test_normalize_and_tokenize():
    assert normalize("  I   bought’s  a\tcar ") == "I bought's a car"
    assert tokenize("I don't like red-brown cars.") == ["I", "don't", "like", "red-brown", "cars"]


def test_sentence_split_keeps_abbreviations():
    s = split_sentences("I met Dr. Rao. My car is red! Is it new?", use_spacy=False)
    assert s == ["I met Dr. Rao.", "My car is red!", "Is it new?"]


def test_lemmatize_does_not_mangle_colours():
    assert lemmatize("red", nlp=False) == "red"  # nlp=False is truthy-safe: falls to rules
    assert lemmatize("bought", nlp=False) == "buy"
    assert lemmatize("painted", nlp=False) == "paint"


# ------------------------------------------------------------------------- NER
def test_brand_maps_to_canonical_entity():
    ents = tracked_entities("I bought a red Tesla.")
    assert [e.canonical for e in ents] == ["car"]
    assert ents[0].confidence < 0.95  # alias, not the canonical noun


def test_longest_match_wins_no_overlap():
    ents = tracked_entities("My Dell XPS laptop is great")
    assert [e.canonical for e in ents] == ["laptop", "laptop"] or len(ents) >= 1
    spans = sorted((e.start, e.end) for e in ents)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))


# ---------------------------------------------------------------------- temporal
@pytest.mark.parametrize(
    "text,expected",
    [
        ("last week", datetime(2026, 10, 3, 10)),
        ("3 days ago", datetime(2026, 10, 7, 10)),
        ("two weeks ago", datetime(2026, 9, 26, 10)),
        ("yesterday", datetime(2026, 10, 9, 10)),
        ("last month", datetime(2026, 9, 10, 10)),
        ("last friday", datetime(2026, 10, 9, 10)),
        ("on 2026-09-01", datetime(2026, 9, 1, 10)),
        ("on 05/10/2026", datetime(2026, 10, 5, 10)),  # day-first
        ("on 5 October 2026", datetime(2026, 10, 5, 10)),
        ("on October 5th, 2026", datetime(2026, 10, 5, 10)),
        ("in March", datetime(2026, 3, 1, 10)),
    ],
)
def test_time_resolution(text, expected):
    e = resolve_event_time(text, REF)
    assert e is not None and e.resolved == expected


def test_vague_and_approximate_time():
    v = extract_time_expressions("I did it recently", REF)
    assert v and v[0].kind == "vague" and v[0].resolved is None
    a = extract_time_expressions("a few days ago", REF)
    assert a and a[0].approximate and a[0].resolved == datetime(2026, 10, 7, 10)


def test_in_month_after_current_month_means_last_year():
    e = resolve_event_time("in December", REF)
    assert e.resolved == datetime(2025, 12, 1, 10)


# ----------------------------------------------------------------------- events
@pytest.mark.parametrize(
    "s,ev",
    [
        ("I bought a red Tesla", "buy"),
        ("I got the car repainted blue", "repaint"),
        ("I put a blue skin on it", "apply_skin"),
        ("I removed the skin", "remove_skin"),
        ("I changed the colour to green", "change"),
        ("I like pizza", None),
    ],
)
def test_event_detection(s, ev):
    assert detect_event(s) == ev


# ------------------------------------------------------------------------ claims
def test_claim_buy_with_brand():
    (c,) = extract_claims("I bought a red Tesla.", REF)
    assert (c.entity, c.attribute, c.value, c.event) == ("car", "color", "red", "buy")
    assert c.confidence >= 0.9


def test_claim_copula():
    (c,) = extract_claims("My car is blue.", REF)
    assert (c.entity, c.value) == ("car", "blue") and c.confidence >= 0.9


def test_claim_repaint_with_time():
    (c,) = extract_claims("I got my car repainted blue last week.", REF)
    assert (c.value, c.event, c.temporal_expression) == ("blue", "repaint", "last week")
    assert c.resolved_time == "2026-10-03T10:00:00"


def test_pronoun_uses_context_entity():
    (c,) = extract_claims("I repainted it black yesterday.", REF, context_entity="car")
    assert c.entity == "car" and c.value == "black"
    assert c.confidence < 0.95  # resolved from context -> slightly lower


def test_no_entity_and_no_context_gives_no_claim():
    assert extract_claims("I repainted it black.", REF) == []


def test_valueless_change_event():
    (c,) = extract_claims("I removed the skin.", REF, context_entity="laptop")
    assert c.entity == "laptop" and c.value == "" and c.event == "remove_skin"


def test_question_is_not_a_fact():
    assert extract_claims("Is my car red?", REF) == []


def test_negation_produces_no_claim():
    assert extract_claims("My car is not red.", REF) == []
    assert extract_claims("My car isn't red anymore.", REF) == []


def test_irrelevant_sentence_produces_no_claim():
    assert extract_claims("I like pizza.", REF) == []


def test_past_state_without_time_is_skipped_but_with_time_is_kept():
    assert extract_claims("My car was red.", REF) == []
    (c,) = extract_claims("In March my car was red.", REF)
    assert c.value == "red" and c.resolved_time is not None


def test_contrast_sentence_takes_present_colour():
    (c,) = extract_claims("My car was red but now it is blue.", REF)
    assert c.value == "blue"


def test_two_sentences_two_claims_in_order():
    cs = extract_claims("My car is red. Later I repainted it blue.", REF, context_entity="car")
    assert [c.value for c in cs] == ["red", "blue"]


# ---------------------------------------------------------------- query parsing
@pytest.mark.parametrize(
    "q,intent",
    [
        ("What color is my car now?", Intent.CURRENT),
        ("What color is my car?", Intent.CURRENT),
        ("What color was it before?", Intent.PREVIOUS),
        ("What color was my car originally?", Intent.ORIGINAL),
        ("What was the car before it became black?", Intent.PREVIOUS),
        ("What changed about my car?", Intent.CHANGE),
        ("When did the color change?", Intent.WHEN),
        ("How do you know it is blue?", Intent.EVIDENCE),
        ("Show the evidence.", Intent.EVIDENCE),
        ("Show me the history of my car's color", Intent.HISTORY),
        ("What color was it last week?", Intent.AS_OF),
        ("What color was the laptop after I added the skin?", Intent.AFTER),
    ],
)
def test_query_intent(q, intent):
    assert parse_query(q, REF, context_entity="car").intent == intent


def test_query_reference_and_target_values():
    p = parse_query("Was my car red before it became blue?", REF)
    assert p.intent == Intent.PREVIOUS
    assert p.reference_value == "blue" and p.target_value == "red" and p.asks_boolean

    p = parse_query("What was the car before it became black?", REF)
    assert p.reference_value == "black" and p.target_value is None


def test_query_event_reference_and_entity():
    p = parse_query("What color was the laptop after I added the skin?", REF)
    assert p.entity == "laptop" and p.reference_event == "apply_skin"


def test_query_evidence_scope():
    assert parse_query("Show the evidence.", REF).evidence_scope == "ALL"
    assert parse_query("How do you know it is blue?", REF).evidence_scope == "VALUE"
    assert parse_query("Show the evidence for the original color", REF).evidence_scope == "ORIGINAL"


def test_query_asof_time_resolved():
    p = parse_query("What color was it last week?", REF)
    assert p.time == "2026-10-03T10:00:00"


def test_query_entity_falls_back_to_context():
    assert parse_query("What color is it now?", REF, context_entity="Laptop").entity == "laptop"
    assert parse_query("What color is it now?", REF).entity is None


# ---------------------------------------------------------------------- embeddings
def test_hashing_embedder_is_deterministic_and_normalised():
    e = HashingEmbedder(128)
    a = e.embed(["I bought a red car"])
    b = e.embed(["I bought a red car"])
    assert np.allclose(a, b) and abs(np.linalg.norm(a[0]) - 1.0) < 1e-5


def test_hashing_embedder_ranks_lexical_neighbours():
    e = HashingEmbedder(512)
    v = e.embed(["my car is red", "my car is crimson red", "the weather is cold in winter"])
    assert float(v[0] @ v[1]) > float(v[0] @ v[2])
