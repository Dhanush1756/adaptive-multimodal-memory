"""Baselines for the ablation study (brief sections 38, 39, 53).

All expose the same interface as MemoryAgent:  reset() / remember(...) / ask(...) -> Answer

  A  NaiveTextMemory         text -> embedding -> top-1 retrieval -> read a colour from the hit
  B  NaiveMultimodalMemory   text + image(caption) -> embedding -> top-1 retrieval -> read a colour
  C  AppendOnlyTemporalMemory every session appended as an observation in time order; the SAME
                             temporal selection logic as the proposed system is applied, but there
                             is no MERGE (duplicates stay), no CONTRADICTORY handling (text wins,
                             images that differ become new states) and no evidence linking

The proposed system is MemoryAgent (link_evidence=True); "no evidence linking" is
MemoryAgent(link_evidence=False). A and B use the same extractors and pretrained models as the
proposed system, so differences come from the memory mechanism, not from stronger components.

Fairness notes (state these in the report):
  * A/B retrieval ignores temporal wording ("now" vs "originally"): ties are broken by similarity
    only (then by newest). That is how a plain RAG memory behaves.
  * A/B cannot answer HISTORY / CHANGE / WHEN questions; those count as wrong (found=False).
  * A/B only consider stored items from which a colour could be read (generous to the baseline).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..agent.answer_generator import Answer
from ..agent.query_parser import Intent, ParsedQuery, parse_query
from ..agent.reasoning import Components, build_components
from ..config import load_config
from ..memory.conflict import normalize_value, values_equal
from ..nlp.ner import tracked_entities
from ..nlp.preprocessing import normalize
from ..nlp.relation_extraction import extract_claims
from ..retrieval.temporal_retriever import select_states
from ..utils import cosine, iso, parse_ts

UNSUPPORTED = {Intent.HISTORY, Intent.CHANGE, Intent.WHEN}


def _no_answer(parsed: ParsedQuery, note: str) -> Answer:
    return Answer(text="I cannot answer that with this memory.", value=None, confidence=0.0,
                  found=False, intent=parsed.intent.value, note=note)


def _ev(modality: str, session_id: str, timestamp: str, value: Optional[str], text: str = "") -> Dict[str, Any]:
    return {"modality": modality, "session_id": session_id, "timestamp": timestamp,
            "value": value, "text": text, "role": "supporting"}


class _Base:
    name = "base"

    def __init__(self, cfg: Optional[Dict[str, Any]] = None, light: bool = False,
                 components: Optional[Components] = None):
        self.cfg = cfg or load_config()
        self.comp = components or build_components(self.cfg, light)
        self._n = 0
        self.items: List[Dict[str, Any]] = []

    def reset(self) -> None:
        self._n = 0
        self.items = []

    def _sid(self, session_id: Optional[str]) -> str:
        self._n += 1
        return session_id or f"S{self._n:02d}"

    # -------- shared reader: top-1 retrieval by similarity, tie -> newest ---------------
    def ask(self, question: str, reference_time: Any = None) -> Answer:
        parsed = parse_query(question, reference_time)
        if parsed.intent in UNSUPPORTED:
            return _no_answer(parsed, "baseline cannot answer this question type")
        cands = [it for it in self.items if it["value"]]
        if not cands:
            return _no_answer(parsed, "nothing readable is stored")
        q = self.comp.embedder.embed([parsed.raw])[0]
        best = max(cands, key=lambda it: (cosine(q, it["emb"]), it["ts"]))
        value = best["value"]
        yes_no = None
        if parsed.asks_boolean and parsed.target_value:
            yes_no = values_equal(value, parsed.target_value)
            value = "yes" if yes_no else "no"
        return Answer(text=str(value), value=value, confidence=round(float(cosine(q, best["emb"])), 3),
                      found=True, intent=parsed.intent.value,
                      evidence=[_ev("text", best["sid"], best["ts"], best["value"], best["doc"])],
                      yes_no=yes_no)


class NaiveTextMemory(_Base):
    name = "A_naive_text"

    def remember(self, text: str = "", image: Any = None, timestamp: Any = None,
                 session_id: Optional[str] = None):
        sid, ts = self._sid(session_id), iso(timestamp)
        text = normalize(text or "")
        if not text:                     # images are ignored by this baseline
            return None
        claims = extract_claims(text, parse_ts(ts))
        value = next((normalize_value(c.value) for c in claims if c.value), None)
        self.items.append({"doc": text, "emb": self.comp.embedder.embed([text])[0], "ts": ts,
                           "sid": sid, "value": value})
        return None


class NaiveMultimodalMemory(_Base):
    name = "B_naive_multimodal"

    def remember(self, text: str = "", image: Any = None, timestamp: Any = None,
                 session_id: Optional[str] = None):
        sid, ts = self._sid(session_id), iso(timestamp)
        text = normalize(text or "")
        claims = extract_claims(text, parse_ts(ts)) if text else []
        claim_val = next((normalize_value(c.value) for c in claims if c.value), None)
        ents = tracked_entities(text) if text else []
        entity = claims[0].entity if claims else (ents[0].canonical if ents else None)
        img_val, caption = None, ""
        if image is not None:
            an = self.comp.visual.analyze(image, preferred_entity=entity)
            img_val = normalize_value(an.color) if an.color else None
            entity = entity or an.entity
            caption = f"a photo of a {img_val} {entity or 'object'}" if img_val else ""
        doc = text or caption
        if not doc:
            return None
        self.items.append({"doc": doc, "emb": self.comp.embedder.embed([doc])[0], "ts": ts,
                           "sid": sid, "value": claim_val or img_val})
        return None


@dataclass
class _Obs:
    value: str
    timestamp: str
    event: Optional[str]
    sessions: List[str]


class AppendOnlyTemporalMemory(_Base):
    name = "C_append_only_temporal"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.chains: Dict[str, List[_Obs]] = {}
        self.last_entity: Optional[str] = None

    def reset(self) -> None:
        super().reset()
        self.chains = {}
        self.last_entity = None

    def remember(self, text: str = "", image: Any = None, timestamp: Any = None,
                 session_id: Optional[str] = None):
        sid, ts = self._sid(session_id), iso(timestamp)
        text = normalize(text or "")
        ctx = self.last_entity
        claims = extract_claims(text, parse_ts(ts), context_entity=ctx) if text else []
        claim = claims[0] if claims else None
        ents = tracked_entities(text) if text else []
        entity = (claim.entity if claim else None) or (ents[0].canonical if ents else None)
        an = self.comp.visual.analyze(image, preferred_entity=entity or ctx) if image is not None else None
        entity = entity or (an.entity if an is not None else None) or ctx
        if entity is None:
            return None
        if claim is not None and claim.value:
            value = normalize_value(claim.value)      # text wins; a conflicting image is never noticed
        elif an is not None and an.color:
            value = normalize_value(an.color)
        else:
            return None
        when = claim.resolved_time if (claim is not None and claim.resolved_time) else ts
        chain = self.chains.setdefault(entity, [])
        chain.append(_Obs(value, iso(when), claim.event if claim else None, [sid]))
        chain.sort(key=lambda o: o.timestamp)         # stable: insertion order breaks ties
        self.last_entity = entity
        return None

    def ask(self, question: str, reference_time: Any = None) -> Answer:
        parsed = parse_query(question, reference_time, context_entity=self.last_entity)
        ent = parsed.entity if parsed.entity in self.chains else self.last_entity
        chain = self.chains.get(ent or "", [])
        sel = select_states(parsed, chain)
        if not sel.found:
            return _no_answer(parsed, sel.note)
        ev = [_ev("observation", s, chain[i].timestamp, chain[i].value)
              for i in sel.indices for s in chain[i].sessions]
        return Answer(text=str(sel.value), value=sel.value, confidence=0.5, found=True,
                      intent=parsed.intent.value, evidence=ev, yes_no=sel.yes_no, note=sel.note)
