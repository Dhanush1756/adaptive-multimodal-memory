"""Image embeddings and CLIP access (brief section 14, stages 5-6).

CLIP (transformers) when available. Fallback: a 64-d colour-histogram embedding. The fallback
captures colour only - it is fine for the colour-tracking prototype but is NOT a semantic
image embedding, so report results made with it as "histogram baseline".
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from PIL import Image

from ..config import load_config


def color_histogram_embedding(img: Image.Image, bins: int = 4) -> np.ndarray:
    """L2-normalised sqrt of a bins^3 RGB histogram (Hellinger-style)."""
    a = np.asarray(img.convert("RGB").resize((64, 64)), dtype=np.int32) // (256 // bins)
    idx = a[..., 0] * bins * bins + a[..., 1] * bins + a[..., 2]
    h = np.bincount(idx.ravel(), minlength=bins ** 3).astype(np.float32)
    h /= max(float(h.sum()), 1.0)
    h = np.sqrt(h)
    return h / (np.linalg.norm(h) + 1e-9)


class ClipBackend:
    def __init__(self, cfg: Optional[Dict[str, Any]] = None, force_fallback: bool = False):
        cv = (cfg or load_config()).get("cv", {})
        self.name = cv.get("clip_model", "openai/clip-vit-base-patch32")
        self.available = False
        self._model = None
        self._proc = None
        self._torch = None
        self._text_cache: Dict[Any, np.ndarray] = {}
        if force_fallback:
            return
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            self._torch = torch
            self._model = CLIPModel.from_pretrained(self.name, local_files_only=bool(cv.get("local_files_only", False))).eval()
            self._proc = CLIPProcessor.from_pretrained(self.name, local_files_only=bool(cv.get("local_files_only", False)))
            self.available = True
        except Exception as exc:
            print(f"[clip] unavailable ({exc.__class__.__name__}); using colour-histogram fallback")

    @staticmethod
    def _norm(x: np.ndarray) -> np.ndarray:
        return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9)

    def image_features(self, imgs: Sequence[Image.Image]) -> np.ndarray:
        inputs = self._proc(images=list(imgs), return_tensors="pt")
        with self._torch.no_grad():
            f = self._model.get_image_features(**inputs)
        return self._norm(f.detach().cpu().numpy().astype(np.float32))

    def text_features(self, texts: Sequence[str]) -> np.ndarray:
        key = tuple(texts)
        if key not in self._text_cache:
            inputs = self._proc(text=list(texts), return_tensors="pt", padding=True)
            with self._torch.no_grad():
                f = self._model.get_text_features(**inputs)
            self._text_cache[key] = self._norm(f.detach().cpu().numpy().astype(np.float32))
        return self._text_cache[key]

    def zero_shot(
        self, img: Image.Image, labels: Sequence[str], template: str = "a photo of a {} object",
        scale: float = 100.0,
    ) -> Dict[str, float]:
        tf = self.text_features([template.format(lab) for lab in labels])
        imf = self.image_features([img])[0]
        logits = scale * (tf @ imf)
        e = np.exp(logits - logits.max())
        p = e / e.sum()
        return {lab: float(v) for lab, v in zip(labels, p)}

    def similarity(self, img: Image.Image, text: str) -> float:
        """Cosine similarity between an image and a sentence in CLIP space."""
        return float(self.image_features([img])[0] @ self.text_features([text])[0])


_CACHE: Dict[Any, ClipBackend] = {}


def get_clip(cfg: Optional[Dict[str, Any]] = None, force_fallback: bool = False) -> ClipBackend:
    cv=(cfg or load_config()).get('cv',{})
    key = ("fallback",) if force_fallback else (cv.get('clip_model'),bool(cv.get('local_files_only',False)))
    if key not in _CACHE:
        _CACHE[key] = ClipBackend(cfg, force_fallback)
    return _CACHE[key]


class ImageEmbedder:
    def __init__(self, clip: Optional[ClipBackend] = None):
        self.clip = clip

    @property
    def name(self) -> str:
        return "clip" if (self.clip is not None and self.clip.available) else "color-histogram"

    def embed(self, img: Image.Image) -> np.ndarray:
        if self.clip is not None and self.clip.available:
            return self.clip.image_features([img])[0]
        return color_histogram_embedding(img)
