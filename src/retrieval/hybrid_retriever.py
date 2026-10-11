"""Hybrid ranking: semantic + entity + attribute + temporal + confidence (brief sections 18, 22).

    score = w_sem*semantic + w_ent*entity_match + w_attr*attribute_match
            + w_time*temporal_relevance + w_conf*confidence

Weights come from config `retrieval:` and are initial values, not tuned. The structured
TemporalRetriever answers questions deterministically; this ranker is used for entity
resolution when the question names no entity and several are stored, and as the scoring
function you can ablate (semantic-only vs hybrid).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..agent.query_parser import Intent, ParsedQuery
from ..config import load_config
from ..memory import state_tracker
from ..memory.schema import MemoryRecord
from ..memory.store import MemoryStore


def temporal_relevance(pos: int, n: int, intent: Intent) -> float:
    """How well a state at chain position `pos` (of n) fits the temporal intent."""
    if intent == Intent.CURRENT:
        return 1.0 if pos == n - 1 else 0.2
    if intent == Intent.ORIGINAL:
        return 1.0 if pos == 0 else 0.2
    if intent == Intent.PREVIOUS:
        return 1.0 if pos == n - 2 else 0.4
    return 0.6  # CHANGE / HISTORY / WHEN / EVIDENCE / AFTER / AS_OF: every state is relevant


class HybridRetriever:
    def __init__(self, store: MemoryStore, embedder=None, cfg: Optional[Dict[str, Any]] = None):
        r = (cfg or load_config()).get("retrieval", {})
        self.store = store
        self.embedder = embedder
        self.w_sem = float(r.get("w_semantic", 0.30))
        self.w_ent = float(r.get("w_entity", 0.20))
        self.w_attr = float(r.get("w_attribute", 0.20))
        self.w_time = float(r.get("w_temporal", 0.20))
        self.w_conf = float(r.get("w_confidence", 0.10))

    def _semantic(self, rec: MemoryRecord, q: Optional[np.ndarray]) -> float:
        if q is None:
            return 0.0
        best = 0.0
        for ev in rec.text_evidence:
            if ev.embedding and len(ev.embedding) == len(q):
                e = np.asarray(ev.embedding, dtype=np.float32)
                best = max(best, float(e @ q / max(np.linalg.norm(e) * np.linalg.norm(q), 1e-9)))
        return max(best, 0.0)

    def rank(self, parsed: ParsedQuery, k: int = 10) -> List[Dict[str, Any]]:
        q = self.embedder.embed([parsed.raw])[0] if self.embedder is not None else None
        out: List[Dict[str, Any]] = []
        for ent in self.store.entities():
            chain = state_tracker.timeline(self.store, ent["entity_id"], parsed.attribute)
            for pos, rec in enumerate(chain):
                comp = {
                    "semantic": self._semantic(rec, q),
                    "entity": 1.0 if parsed.entity == rec.entity else (0.5 if parsed.entity is None else 0.0),
                    "attribute": 1.0 if parsed.attribute == rec.attribute else 0.0,
                    "temporal": temporal_relevance(pos, len(chain), parsed.intent),
                    "confidence": rec.confidence,
                }
                score = (self.w_sem * comp["semantic"] + self.w_ent * comp["entity"]
                         + self.w_attr * comp["attribute"] + self.w_time * comp["temporal"]
                         + self.w_conf * comp["confidence"])
                out.append({"record": rec, "score": score, "components": comp})
        out.sort(key=lambda d: d["score"], reverse=True)
        return out[:k]

    def resolve_entity(self, parsed: ParsedQuery) -> Optional[Tuple[str, str]]:
        """(entity_id, entity) the question is about, or None if memory has nothing for it."""
        ents = self.store.entities()
        if parsed.entity:
            for e in ents:
                if e["entity"] == parsed.entity:
                    return e["entity_id"], e["entity"]
            return None
        if not ents:
            return None
        if len(ents) == 1:
            return ents[0]["entity_id"], ents[0]["entity"]
        ranked = self.rank(parsed, k=1)
        if ranked:
            r = ranked[0]["record"]
            return r.entity_id, r.entity
        return ents[-1]["entity_id"], ents[-1]["entity"]
