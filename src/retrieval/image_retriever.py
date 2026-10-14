"""Visual similarity search over stored image evidence (brief section 22, "Image retrieval")."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..cv.similarity import top_k
from ..memory.store import MemoryStore


class ImageRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def search(self, embedding: Sequence[float], k: int = 5) -> List[Dict[str, Any]]:
        items = []
        for rec in self.store.all():
            for ev in rec.visual_evidence:
                if ev.embedding:
                    items.append((rec, ev))
        if not items:
            return []
        # group by embedding length so a backend switch cannot produce garbage comparisons
        items = [it for it in items if len(it[1].embedding) == len(embedding)]
        hits = top_k(embedding, [ev.embedding for _, ev in items], k)
        return [{"record": items[i][0], "evidence": items[i][1], "score": s} for i, s in hits]

    def for_records(self, records: Sequence[Any]) -> List[Dict[str, Any]]:
        """Retrieve visual evidence structurally tied to already selected states.

        A text question has no image embedding to compare.  State selection is
        therefore the reliable first-stage retrieval: only evidence stored on an
        answer-supporting state can be returned.  Ambiguous/unmatched detections
        never become hits.
        """
        hits: List[Dict[str, Any]] = []
        for rec in records:
            for ev in rec.visual_evidence:
                if ev.association_status in {"verified", "contextual"}:
                    hits.append({"record": rec, "evidence": ev, "score": 1.0})
        return hits
