"""Image similarity helpers (brief section 14; visual retrieval and change detection)."""
from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from ..utils import cosine


def top_k(query: Sequence[float], matrix: Sequence[Sequence[float]], k: int = 5) -> List[Tuple[int, float]]:
    """Indices and cosine scores of the k nearest rows (brute force; fine at prototype scale)."""
    if len(matrix) == 0:
        return []
    m = np.asarray(matrix, dtype=np.float32)
    q = np.asarray(query, dtype=np.float32)
    if m.shape[1] != q.shape[0]:
        return []  # embeddings from a different backend: refuse to compare
    sims = (m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)) @ (q / max(np.linalg.norm(q), 1e-9))
    order = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in order]


def visual_change_score(a: Sequence[float], b: Sequence[float]) -> float:
    """1 - cosine similarity: 0 = identical appearance, larger = more different."""
    return 1.0 - cosine(a, b)
