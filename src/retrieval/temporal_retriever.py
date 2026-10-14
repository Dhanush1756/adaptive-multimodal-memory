"""Temporal-intent-aware retrieval (brief sections 20, 22, 31, 32, 57).

`select_states` is a pure function over an ordered chain of states (anything with
.value / .timestamp / .event), so the memory-backed retriever and the baselines share the
exact same temporal semantics.

Semantics per intent (chain is oldest -> newest, contradictory states excluded):
  CURRENT   newest state
  ORIGINAL  oldest state
  PREVIOUS  state before the newest one; "before X" -> state before the latest X
            (never "just take the newest": see brief section 57); "before <event>" likewise
  AFTER     "after X" -> state following the latest X; "after <event>" -> state that event created
  CHANGE    all transitions; value = "old->new" of the latest one
  WHEN      time of the state named in the question (or of the latest change)
  EVIDENCE  the state selected by evidence_scope (CURRENT/PREVIOUS/ORIGINAL/VALUE/ALL)
  HISTORY   the whole chain
  AS_OF     the state in effect at the resolved time
Boolean questions ("Was it red before it became blue?") compare the selected state with
target_value and answer "yes"/"no".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..agent.query_parser import Intent, ParsedQuery
from ..memory import state_tracker
from ..memory.conflict import values_equal
from ..memory.schema import MemoryRecord
from ..memory.store import MemoryStore
from ..utils import parse_ts
from .hybrid_retriever import HybridRetriever
from .image_retriever import ImageRetriever


@dataclass
class Selection:
    found: bool
    indices: List[int] = field(default_factory=list)   # chain positions that support the answer
    value: Any = None                                    # what the answer is (str | list | "yes"/"no")
    actual: Any = None                                   # underlying state value(s) before yes/no
    yes_no: Optional[bool] = None
    time: Optional[str] = None
    note: str = ""


def _latest(chain: Sequence[Any], pred: Callable[[int, Any], bool]) -> Optional[int]:
    hits = [i for i, s in enumerate(chain) if pred(i, s)]
    return hits[-1] if hits else None


def _finish(parsed: ParsedQuery, chain: Sequence[Any], indices: List[int], value_idx: int, note: str = "") -> Selection:
    actual = chain[value_idx].value
    sel = Selection(True, indices, actual, actual, note=note)
    if parsed.asks_boolean and parsed.target_value:
        sel.yes_no = values_equal(actual, parsed.target_value)
        sel.value = "yes" if sel.yes_no else "no"
    return sel


def select_states(parsed: ParsedQuery, chain: Sequence[Any]) -> Selection:
    n = len(chain)
    if n == 0:
        return Selection(False, note="nothing is stored for that entity/attribute")
    I = parsed.intent
    ref_v, ref_e = parsed.reference_value, parsed.reference_event

    if I == Intent.ORIGINAL:
        return _finish(parsed, chain, [0], 0)

    if I == Intent.PREVIOUS:
        if ref_v:
            i = _latest(chain, lambda i, s: i > 0 and values_equal(s.value, ref_v))
            why = f"no state before '{ref_v}' is recorded"
        elif ref_e:
            i = _latest(chain, lambda i, s: i > 0 and s.event == ref_e)
            why = f"no state before the '{ref_e}' event is recorded"
        else:
            i = n - 1 if n >= 2 else None
            why = "no earlier state is recorded"
        if i is None:
            return Selection(False, note=why)
        return _finish(parsed, chain, [i - 1, i], i - 1)

    if I == Intent.AFTER:
        tgt: Optional[int] = None
        if ref_v:
            i = _latest(chain, lambda i, s: i < n - 1 and values_equal(s.value, ref_v))
            tgt = i + 1 if i is not None else None
            why = f"no state after '{ref_v}' is recorded"
        elif ref_e:
            tgt = _latest(chain, lambda i, s: s.event == ref_e)
            why = f"no '{ref_e}' event is recorded"
        else:
            why = "the question names nothing to come after"
        if tgt is None:
            return Selection(False, note=why)
        return _finish(parsed, chain, [tgt - 1, tgt] if tgt > 0 else [tgt], tgt)

    if I == Intent.CHANGE:
        if n < 2:
            return Selection(False, note="no change has been recorded")
        v = f"{chain[-2].value}->{chain[-1].value}"
        return Selection(True, list(range(n)), v, v, time=chain[-1].timestamp)

    if I == Intent.WHEN:
        note = ""
        if ref_e:
            i = _latest(chain, lambda i, s: s.event == ref_e)
        else:
            v = parsed.target_value or ref_v
            if v:
                i = _latest(chain, lambda i, s: i > 0 and values_equal(s.value, v))
                if i is None and values_equal(chain[0].value, v):
                    i, note = 0, "this is the first recorded state, not a change"
            else:
                i = n - 1
                if n == 1:
                    note = "no change has been recorded; this is when the first state was recorded"
        if i is None:
            return Selection(False, note="no matching state is recorded")
        t = chain[i].timestamp
        return Selection(True, [i], t[:10], chain[i].value, time=t, note=note)

    if I == Intent.EVIDENCE:
        scope = parsed.evidence_scope or ("VALUE" if parsed.target_value else "CURRENT")
        if scope == "ALL":
            return Selection(True, list(range(n)), [s.value for s in chain], [s.value for s in chain])
        if scope == "ORIGINAL":
            i: Optional[int] = 0
        elif scope == "PREVIOUS":
            i = n - 2 if n >= 2 else None
        elif scope == "VALUE":
            i = _latest(chain, lambda i, s: values_equal(s.value, parsed.target_value))
        else:
            i = n - 1
        if i is None:
            return Selection(False, note="no stored state matches that")
        return Selection(True, [i], chain[i].value, chain[i].value, time=chain[i].timestamp)

    if I == Intent.HISTORY:
        vals = [s.value for s in chain]
        return Selection(True, list(range(n)), vals, vals)

    if I == Intent.AS_OF and parsed.time:
        t = parse_ts(parsed.time)
        i = _latest(chain, lambda i, s: parse_ts(s.timestamp) <= t)
        if i is None:
            return Selection(False, note="no state was recorded on or before that time")
        sel = _finish(parsed, chain, [i], i)
        sel.time = parsed.time
        return sel

    return _finish(parsed, chain, [n - 1], n - 1)  # CURRENT and fallback


@dataclass
class RetrievalResult:
    parsed: ParsedQuery
    found: bool = False
    entity: Optional[str] = None
    entity_id: Optional[str] = None
    value: Any = None
    actual: Any = None
    yes_no: Optional[bool] = None
    time: Optional[str] = None
    note: str = ""
    records: List[MemoryRecord] = field(default_factory=list)      # states supporting the answer
    chain: List[MemoryRecord] = field(default_factory=list)        # full ordered timeline
    conflicts: List[MemoryRecord] = field(default_factory=list)    # CONTRADICTORY states
    transitions: List[Dict[str, str]] = field(default_factory=list)
    image_hits: List[Dict[str, Any]] = field(default_factory=list)


class TemporalRetriever:
    def __init__(self, store: MemoryStore, hybrid: HybridRetriever):
        self.store = store
        self.hybrid = hybrid
        self.image_retriever = ImageRetriever(store)

    def retrieve(self, parsed: ParsedQuery) -> RetrievalResult:
        res = RetrievalResult(parsed=parsed)
        ent = self.hybrid.resolve_entity(parsed)
        if ent is None:
            matches = [e for e in self.store.entities() if e["entity"] == parsed.entity]
            if parsed.entity and len(matches) > 1 and not parsed.entity_ref:
                res.note = f"Multiple {parsed.entity} identities are stored; name which one you mean."
            elif parsed.entity_ref and matches:
                res.note = f"No stored identity matches '{parsed.entity_ref}'."
            else:
                res.note = (f"I have no memories about a {parsed.entity}." if parsed.entity
                            else "No memories are stored yet.")
            return res
        res.entity_id, res.entity = ent
        res.chain = state_tracker.timeline(self.store, res.entity_id, parsed.attribute)
        res.conflicts = state_tracker.conflicts(self.store, res.entity_id, parsed.attribute)
        res.transitions = state_tracker.transitions(self.store, res.entity_id, parsed.attribute)
        if not res.chain:
            res.note = ("Only conflicting evidence is stored (no confirmed state)." if res.conflicts
                        else "Nothing is stored for that attribute.")
            return res
        sel = select_states(parsed, res.chain)
        res.found, res.value, res.actual = sel.found, sel.value, sel.actual
        res.yes_no, res.time, res.note = sel.yes_no, sel.time, sel.note
        res.records = [res.chain[i] for i in sel.indices]
        # This is the actual visual QA retrieval step.  It is scoped to selected
        # state IDs, not to all images in the session/entity.
        res.image_hits = self.image_retriever.for_records(res.records)
        return res
