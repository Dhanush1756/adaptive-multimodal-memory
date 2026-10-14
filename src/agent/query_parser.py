"""Query understanding and temporal-intent detection (brief sections 20-21 and 31).

    "What color was it before it became black?"
 -> ParsedQuery(entity=None->context, attribute="color", intent=PREVIOUS, reference_value="black")

Rule-based baseline. Intent labels double as the target of an optional learned classifier
(see docs/training.md); `parse_query` is the interface to keep stable.

Priority order (first match wins):
  EVIDENCE > WHEN > CHANGE > HISTORY > ORIGINAL > AFTER > AS_OF > PREVIOUS > CURRENT(default)
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..memory.conflict import normalize_value
from ..nlp.ner import entity_reference, tracked_entities
from ..nlp.preprocessing import normalize
from ..nlp.relation_extraction import COLOR_WORDS, detect_event
from ..nlp.temporal_extraction import extract_time_expressions
from ..utils import parse_ts


class Intent(str, Enum):
    CURRENT = "CURRENT"
    PREVIOUS = "PREVIOUS"
    ORIGINAL = "ORIGINAL"
    AFTER = "AFTER"
    CHANGE = "CHANGE"
    WHEN = "WHEN"
    EVIDENCE = "EVIDENCE"
    HISTORY = "HISTORY"
    AS_OF = "AS_OF"


@dataclass
class ParsedQuery:
    raw: str
    entity: Optional[str]
    attribute: str
    intent: Intent
    reference_value: Optional[str] = None     # "before BLUE", "after BLUE"
    reference_event: Optional[str] = None     # "after I added the SKIN" -> apply_skin
    target_value: Optional[str] = None        # value the question is about ("was it RED ...")
    time: Optional[str] = None                # ISO time for AS_OF queries
    time_text: Optional[str] = None
    asks_boolean: bool = False
    evidence_scope: Optional[str] = None      # CURRENT | PREVIOUS | ORIGINAL | VALUE | ALL
    rule_confidence: float = 0.6
    entity_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["intent"] = self.intent.value
        return d


_COLOR_RX = re.compile(r"\b(" + "|".join(COLOR_WORDS) + r")\b", re.I)

_EVIDENCE = re.compile(
    r"\b(evidence|proof|prove|how do you know|how can you tell|how did you (?:know|conclude)|"
    r"why do you (?:think|say|believe)|based on what|what.s your source|show me (?:the )?(?:image|photo|picture|text))\b"
)
_WHEN = re.compile(r"(?:^|\b)when\s+(?:did|was|were|does|is)\b|^when\b|\bwhat (?:date|time|day)\b|\bhow long ago\b")
_CHANGE = re.compile(
    r"\bwhat (?:has |have )?(?:changed|changes)\b|\bany changes?\b|\bwhat happened\b|\bwhat.s (?:new|different)\b|"
    r"\bhow (?:has|have|did|does) .{0,30}change|\bdifference\b|\bwhat is different\b"
)
_HISTORY = re.compile(
    r"\bhistory\b|\btimeline\b|\ball (?:the )?(?:colou?rs|states|values)\b|\bevery colou?r\b|\bover time\b|"
    r"\bsequence\b|\beach state\b|\bevery state\b"
)
_ORIGINAL = re.compile(
    r"\boriginal(?:ly)?\b|\bat first\b|\binitial(?:ly)?\b|\bin the beginning\b|\bat the start\b|"
    r"\bto begin with\b|\bfrom the start\b|\bvery first\b|\bfirst (?:colou?r|state|value|time|appearance)\b|"
    r"\bstart(?:ed)? (?:out )?with\b|\bearliest recorded\b|\binitial condition\b"
)
_AFTER_KW = re.compile(r"\b(after|following|since)\b")
_BEFORE_KW = re.compile(r"\b(before|prior to|preceding|until|earlier than)\b")
_PREVIOUS = re.compile(
    r"\bbefore\b|\bprevious(?:ly)?\b|\bprior\b|\bused to\b|\bformerly\b|\bearlier\b|\blast time\b|"
    r"\bpreceding\b|\bold colou?r\b|\bformer\b|\bone before\b"
)
_PAST_TENSE = re.compile(r"\b(was|were|had|did)\b")
_CURRENT_CUE = re.compile(r"\b(now|currently|current|today|at the moment|these days|latest|right now|nowadays)\b")
_BOOL_START = re.compile(r"^(is|was|were|did|does|do|has|had|are|will|can|could)\b")


def _colors_with_pos(low: str) -> List[Tuple[str, int]]:
    return [(normalize_value(m.group(1)), m.start()) for m in _COLOR_RX.finditer(low)]


def _first_after(colors: List[Tuple[str, int]], pos: int) -> Optional[Tuple[str, int]]:
    return next(((c, p) for c, p in colors if p > pos), None)


def parse_query(text: str, reference_time=None, context_entity: Optional[str] = None,
                context_entity_ref: Optional[str] = None) -> ParsedQuery:
    """Parse a user question.

    reference_time : "now" for resolving relative expressions (defaults to datetime.now())
    context_entity : entity assumed when the question says only "it"
    """
    raw = normalize(text)
    low = raw.lower()
    ref = parse_ts(reference_time)

    ents = tracked_entities(raw)
    entity = ents[0].canonical if ents else (context_entity.lower() if context_entity else None)
    entity_ref = entity_reference(raw, ents[0]) if ents else context_entity_ref
    attribute = "color"

    colors = _colors_with_pos(low)

    # ---- reference clause: "before X" / "after X" --------------------------------
    reference_value: Optional[str] = None
    reference_event: Optional[str] = None
    ref_pos = -1
    kw = _BEFORE_KW.search(low) or _AFTER_KW.search(low)
    if kw:
        hit = _first_after(colors, kw.end() - 1)
        if hit:
            reference_value, ref_pos = hit
        else:
            reference_event = detect_event(low[kw.end():])

    others = [(c, p) for c, p in colors if p != ref_pos]
    target_value = others[0][0] if others else None
    if reference_value is None and reference_event is None and target_value is None and colors:
        target_value = colors[0][0]

    asks_boolean = bool(_BOOL_START.match(low)) and target_value is not None

    # ---- temporal expression (AS_OF) ---------------------------------------------
    time_text, time_iso = None, None
    for t in extract_time_expressions(raw, ref):
        if t.resolved is None:
            continue
        if t.kind == "relative" and abs((t.resolved - ref).total_seconds()) < 86400 and t.granularity == "day":
            continue  # "today"/"now" is just CURRENT
        time_text, time_iso = t.text, t.iso()
        break

    # ---- cue-based intent (everything except EVIDENCE/WHEN/CHANGE) -----------------
    cue: Optional[Intent] = None
    if _HISTORY.search(low):
        cue = Intent.HISTORY
    elif _ORIGINAL.search(low):
        cue = Intent.ORIGINAL
    elif _AFTER_KW.search(low) and (reference_value or reference_event):
        cue = Intent.AFTER
    elif time_iso:
        cue = Intent.AS_OF
    elif _PREVIOUS.search(low):
        cue = Intent.PREVIOUS
    elif _PAST_TENSE.search(low) and not _CURRENT_CUE.search(low):
        cue = Intent.PREVIOUS

    # ---- final intent ---------------------------------------------------------------
    rule_conf = 0.9
    if _EVIDENCE.search(low):
        intent = Intent.EVIDENCE
        if cue in (Intent.ORIGINAL, Intent.PREVIOUS):
            scope = cue.value
        elif target_value and cue is None:
            scope = "VALUE"
        elif _CURRENT_CUE.search(low):
            scope = "CURRENT"
        else:
            scope = "CURRENT"
        return ParsedQuery(raw, entity, attribute, intent, reference_value, reference_event,
                           target_value, time_iso, time_text, asks_boolean, scope, rule_conf, entity_ref)

    if _WHEN.search(low):
        intent = Intent.WHEN
    elif _CHANGE.search(low):
        intent = Intent.CHANGE
    elif cue is not None:
        intent = cue
    else:
        intent = Intent.CURRENT
        rule_conf = 0.9 if _CURRENT_CUE.search(low) or "color" in low or "colour" in low else 0.6

    return ParsedQuery(raw, entity, attribute, intent, reference_value, reference_event,
                       target_value, time_iso, time_text, asks_boolean, None, rule_conf, entity_ref)
