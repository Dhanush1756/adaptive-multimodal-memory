"""Claim / relation extraction: sentence -> structured Claim (brief section 13, stages 4 and 6).

    "I got my car repainted blue last week."
 -> Claim(entity="car", attribute="color", value="blue", event="repaint",
          temporal_expression="last week", resolved_time=<ref - 1 week>)

Rule-based baseline (deterministic, testable, no model download). A learned extractor
(e.g. fine-tuned token classification) can replace `extract_claims` behind the same
interface; see docs/training.md.

Deliberate behaviours
  * questions are not facts            -> no claim
  * negations ("not red", "no longer") -> no claim (negative evidence is not representable)
  * past-state statements without a resolvable time ("it was red") -> no claim,
    because the engine cannot place them on the timeline
  * value-less change events ("I removed the skin") -> Claim with value="" ; the fusion
    layer fills the value from the image if (and only if) an image supports it
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..memory.conflict import normalize_value
from ..memory.schema import Claim
from .ner import Entity, tracked_entities
from .preprocessing import normalize, split_sentences
from .temporal_extraction import extract_time_expressions

COLOR_WORDS = [
    "red", "blue", "black", "white", "green", "yellow", "silver", "gray", "grey", "orange",
    "brown", "purple", "pink", "navy", "maroon", "crimson", "scarlet", "violet", "gold", "golden",
]
_COLOR_RX = re.compile(r"\b(" + "|".join(COLOR_WORDS) + r")\b", re.I)

# Ordered: first match wins. Object nouns decide apply_skin / remove_skin.
_SKIN_NOUNS = r"(?:skin|wrap|cover|case|sticker|decal|film|cap)"
_EVENT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("revert", re.compile(r"\b(reverted|revert|restored|restore|undid|undo|went back to|back to (?:its |the )?original)\b", re.I)),
    ("remove_skin", re.compile(rf"\b(?:removed?|took off|taken off|peeled(?: off)?|stripped)\b.*\b{_SKIN_NOUNS}\b", re.I)),
    ("remove", re.compile(r"\b(removed?|took off|taken off|peeled(?: off)?|stripped|got rid of)\b", re.I)),
    ("apply_skin", re.compile(rf"\b(?:added|add|put|applied|apply|stuck|stick|attached|installed|fitted)\b.*\b{_SKIN_NOUNS}\b", re.I)),
    ("repaint", re.compile(r"\b(re-?paint\w*|painted|painting|re-?spray\w*|spray[- ]painted)\b", re.I)),
    ("wrap", re.compile(r"\b(wrapped|vinyl)\b", re.I)),
    ("dye", re.compile(r"\b(dyed|dye)\b", re.I)),
    ("buy", re.compile(r"\b(bought|buy|buying|purchas\w*|picked up|got (?:a|an|my) new|brought home)\b", re.I)),
    ("change", re.compile(r"\b(chang\w+|turn(?:ed|s)?|swap\w*|switch\w*|replac\w+|became|become|becomes)\b", re.I)),
]
VALUELESS_EVENTS = {"remove", "remove_skin", "revert"}
_NEG_RX = re.compile(r"(?:\bnot|n't|\bnever|\bno longer|\bnor)\s+(?:\w+\s+){0,2}$", re.I)
_PAST_STATE_RX = re.compile(r"\b(was|were|used to be|used to look|had been|originally|at first|initially)\b", re.I)
_CONTRAST_RX = re.compile(r"\b(but now|now|then|instead|into|turned|became|become|changed to|to)\b", re.I)
_PRESENT_CUE_RX = re.compile(r"\b(but now|now|currently|these days|at the moment|today)\b", re.I)
_COPULA_RX = re.compile(r"\b(is|are|was|were|looks?|looked|became|become|turned|got|gets|appears|seems|now|currently)\b", re.I)


def detect_event(sentence: str) -> Optional[str]:
    for name, rx in _EVENT_PATTERNS:
        if rx.search(sentence):
            return name
    return None


def _find_colors(sentence: str) -> List[re.Match]:
    return list(_COLOR_RX.finditer(sentence))


def _is_negated(sentence: str, color_start: int) -> bool:
    return bool(_NEG_RX.search(sentence[:color_start]))


def _nearest_entity(ents: List[Entity], pos: int) -> Optional[Entity]:
    if not ents:
        return None
    return min(ents, key=lambda e: min(abs(e.start - pos), abs(e.end - pos)))


def _pattern_strength(sentence: str, color: re.Match, ent: Optional[Entity], event: Optional[str]) -> float:
    """0.95 when the colour is syntactically tied to the entity or to a change event, else 0.75."""
    if event in {"repaint", "wrap", "dye", "change", "apply_skin"}:
        return 0.95
    if ent is None:
        return 0.75
    lo, hi = sorted((ent.end, color.start)) if ent.end <= color.start else sorted((color.end, ent.start))
    between = sentence[lo:hi]
    n_words = len(re.findall(r"\w+", between))
    if ent.start > color.start and n_words <= 2:  # "red Tesla", "a shiny red car"
        return 0.95
    if ent.end <= color.start and n_words <= 4 and _COPULA_RX.search(between):  # "car is now red"
        return 0.95
    if event == "buy" and n_words <= 3:
        return 0.95
    return 0.75


def extract_claims(
    text: str,
    reference=None,
    context_entity: Optional[str] = None,
    lexicon: Optional[Dict[str, List[str]]] = None,
    attribute: str = "color",
) -> List[Claim]:
    """Extract at most one claim per sentence, in text order.

    reference      : timestamp used to resolve relative time expressions (session time)
    context_entity : entity to assume when the sentence only says "it" / names no entity
    """
    claims: List[Claim] = []
    for sent in split_sentences(normalize(text), use_spacy=False):
        if sent.rstrip().endswith("?"):
            continue  # a question is not a fact

        ents = tracked_entities(sent, lexicon)
        event = detect_event(sent)
        times = extract_time_expressions(sent, reference)
        resolved = next((t for t in times if t.resolved is not None), None)
        tx = resolved or (times[0] if times else None)

        colors = [c for c in _find_colors(sent) if not _is_negated(sent, c.start())]
        if _find_colors(sent) and not colors:
            continue  # every colour mention was negated

        ent_name = None
        ent_obj: Optional[Entity] = None
        conf_penalty = 0.0
        if colors:
            ent_obj = _nearest_entity(ents, colors[0].start())
        elif ents:
            ent_obj = ents[0]
        if ent_obj is not None:
            ent_name = ent_obj.canonical
        elif context_entity:
            ent_name = context_entity.lower()
            conf_penalty += 0.05  # resolved by context, slightly less certain
        else:
            continue

        # past-state statement with no resolvable time cannot be placed on the timeline
        # (a "but now ..." contrast makes the sentence a statement about the present state)
        if (
            colors
            and event is None
            and _PAST_STATE_RX.search(sent)
            and resolved is None
            and not _PRESENT_CUE_RX.search(sent)
        ):
            continue

        if colors:
            if len(colors) > 1:
                cue = _CONTRAST_RX.search(sent)
                chosen = colors[-1] if cue else colors[0]
                conf_penalty += 0.0 if cue else 0.15
            else:
                chosen = colors[0]
            strength = _pattern_strength(sent, chosen, ent_obj, event)
            value = normalize_value(chosen.group(1))
            conf = max(0.0, strength - conf_penalty)
        elif event in VALUELESS_EVENTS:
            value, conf = "", max(0.0, 0.60 - conf_penalty)
        else:
            continue

        claims.append(
            Claim(
                entity=ent_name,
                attribute=attribute,
                value=value,
                event=event,
                temporal_expression=tx.text if tx else None,
                resolved_time=tx.iso() if (tx and tx.resolved is not None) else None,
                confidence=round(conf, 3),
                source_text=sent,
            )
        )
    return claims
