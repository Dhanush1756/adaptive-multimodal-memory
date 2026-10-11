"""Semantic search over stored text evidence (brief section 22, "Text retrieval")."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from ..memory.store import MemoryStore


class TextRetriever:
    """Brute-force cosine search. At prototype scale (hundreds of items) FAISS is unnecessary;
    swap this class for a FAISS index if memory grows."""

    def __init__(self, store: MemoryStore, embedder):
        self.store = store
        self.embedder = embedder

    def search(self, query: str, k: int = 5, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
        q = self.embedder.embed([query])[0]
        hits: List[Dict[str, Any]] = []
        for rec in self.store.query(entity_id=entity_id):
            for ev in rec.text_evidence:
                if not ev.embedding or len(ev.embedding) != len(q):
                    continue
                e = np.asarray(ev.embedding, dtype=np.float32)
                score = float(e @ q / max(np.linalg.norm(e) * np.linalg.norm(q), 1e-9))
                hits.append({"record": rec, "evidence": ev, "score": score})
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:k]
