"""Text embeddings (brief section 13, stage 7).

Primary  : sentence-transformers (default all-MiniLM-L6-v2, 384-d, CPU friendly).
Fallback : HashingEmbedder - deterministic character/word n-gram hashing. It has NO semantic
           knowledge beyond lexical overlap, so results obtained with it must be reported as
           "hashing baseline", never as sentence-transformer results.

The returned object always exposes: .name, .dim, .embed(list[str]) -> np.ndarray (n, dim),
rows L2-normalised, so dot product == cosine similarity.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

import numpy as np


class HashingEmbedder:
    def __init__(self, dim: int = 256):
        self.dim = dim
        self.name = f"hashing-{dim}"

    @staticmethod
    def _features(text: str) -> List[str]:
        t = re.sub(r"\s+", " ", text.lower()).strip()
        words = re.findall(r"[a-z0-9']+", t)
        feats = list(words) + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        for w in words:
            padded = f"#{w}#"
            feats += [padded[i : i + 3] for i in range(max(1, len(padded) - 2))]
        return feats

    def embed(self, texts: List[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for f in self._features(text):
                h = int(hashlib.md5(f.encode("utf-8")).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 64) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, local_files_only=False):
        from sentence_transformers import SentenceTransformer  # heavy import kept local

        self.model = SentenceTransformer(model_name, local_files_only=local_files_only)
        self.name = model_name
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def embed(self, texts: List[str]) -> np.ndarray:
        arr = self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(arr, dtype=np.float32)


_CACHE: Dict[str, Any] = {}


def get_embedder(cfg: Optional[Dict[str, Any]] = None, force_fallback: bool = False):
    """Load the configured embedder once; fall back to hashing if it cannot be loaded."""
    nlp_cfg = (cfg or {}).get("nlp", {})
    model = nlp_cfg.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
    dim = nlp_cfg.get("fallback_embedding_dim", 256)
    local_only = bool(nlp_cfg.get('local_files_only',False))
    key = f'hash:{dim}' if force_fallback else (model,local_only,dim)
    if key in _CACHE:
        return _CACHE[key]
    emb = None
    if not force_fallback:
        try:
            emb = SentenceTransformerEmbedder(model, local_files_only=local_only)
        except Exception as exc:  # offline, missing package, bad name ...
            print(f"[embeddings] could not load '{model}' ({exc.__class__.__name__}); using hashing fallback")
    if emb is None:
        emb = HashingEmbedder(dim)
    _CACHE[key] = emb
    return emb


def embed_one(embedder, text: str) -> List[float]:
    return embedder.embed([text])[0].tolist()
