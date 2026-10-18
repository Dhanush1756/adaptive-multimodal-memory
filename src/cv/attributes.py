"""Visual attribute extraction: object colour (brief section 14, stage 4).

Three evidence sources, combined (never a single black box):
  1. HSV pixel statistics        - always available, interpretable
  2. CLIP zero-shot              - when CLIP is installed
  3. trained colour head         - optional logistic regression (src/training/train_color_head.py)
     on CLIP (or histogram) features; replaces zero-shot when the model file exists

Combination (weights from config cv.clip_weight / cv.hsv_weight, initial values, untuned):
    p = w_other * p_other + w_hsv * p_hsv ;  colour = argmax p
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from ..config import load_config, resolve_path
from ..memory.conflict import normalize_value
from .embeddings import ClipBackend, color_histogram_embedding

CHROMATIC = ["red", "orange", "yellow", "green", "blue", "purple", "pink", "brown"]
NEUTRAL = ["black", "white", "silver", "gray"]
ALL_COLORS = CHROMATIC + NEUTRAL
HEAD_PATH = resolve_path("models/color_head.joblib")


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """rgb: (N,3) floats in [0,1] -> (N,3) [hue degrees, saturation, value]."""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    d = mx - mn
    nz = d > 1e-6
    safe = np.where(nz, d, 1.0)
    m_r = nz & (mx == r)
    m_g = nz & (mx == g) & ~m_r
    m_b = nz & ~m_r & ~m_g
    h = np.zeros_like(mx)
    h = np.where(m_r, ((g - b) / safe) % 6.0, h)
    h = np.where(m_g, (b - r) / safe + 2.0, h)
    h = np.where(m_b, (r - g) / safe + 4.0, h)
    s = np.where(mx > 1e-6, d / np.where(mx > 1e-6, mx, 1.0), 0.0)
    return np.stack([h * 60.0, s, mx], axis=1)


def name_pixels(hsv: np.ndarray) -> np.ndarray:
    """Map every pixel to an index into ALL_COLORS using simple HSV rules (initial thresholds)."""
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    black = v < 0.22
    white = ~black & (s < 0.12) & (v > 0.78)
    mid = ~black & ~white & (s < 0.18)
    silver = mid & (v >= 0.40)
    gray = mid & (v < 0.40)
    chrom = ~(black | white | mid)
    brown = chrom & (h >= 10) & (h < 45) & (v < 0.60)
    c = chrom & ~brown
    rules = {
        "red": c & ((h < 15) | (h >= 345)),
        "orange": c & (h >= 15) & (h < 40),
        "yellow": c & (h >= 40) & (h < 70),
        "green": c & (h >= 70) & (h < 170),
        "blue": c & (h >= 170) & (h < 260),
        "purple": c & (h >= 260) & (h < 310),
        "pink": c & (h >= 310) & (h < 345),
        "brown": brown, "black": black, "white": white, "silver": silver, "gray": gray,
    }
    out = np.full(h.shape, ALL_COLORS.index("gray"), dtype=np.int64)
    for name, mask in rules.items():
        out[mask] = ALL_COLORS.index(name)
    return out


@dataclass
class ColorResult:
    color: str
    confidence: float
    distribution: Dict[str, float]


def hsv_color(
    img: Image.Image, subtract_background: bool = False, center: float = 0.8, size: int = 96
) -> ColorResult:
    """Dominant colour from HSV statistics.

    subtract_background: estimate the background colour from the image border and ignore
    pixels close to it (used when the whole image, not a tight YOLO box, is analysed).
    Chromatic vs neutral is decided first (>=35% chromatic pixels -> chromatic), so black
    wheels or grey windows on a red car do not win.
    """
    arr = np.asarray(img.convert("RGB").resize((size, size), Image.BILINEAR), dtype=np.float32) / 255.0
    mask = np.ones((size, size), dtype=bool)
    if subtract_background:
        ring = max(3, size // 16)
        border = np.concatenate([
            arr[:ring].reshape(-1, 3), arr[-ring:].reshape(-1, 3),
            arr[:, :ring].reshape(-1, 3), arr[:, -ring:].reshape(-1, 3),
        ])
        bg = np.median(border, axis=0)
        mask = np.linalg.norm(arr - bg, axis=-1) > 0.12
    m = int(size * (1 - center) / 2)
    cm = np.zeros_like(mask)
    cm[m: size - m, m: size - m] = True
    sel = mask & cm
    if sel.sum() < 0.03 * size * size:
        sel = cm
    names = name_pixels(rgb_to_hsv(arr[sel]))
    frac = np.bincount(names, minlength=len(ALL_COLORS)) / max(len(names), 1)
    chrom_frac = float(sum(frac[ALL_COLORS.index(c)] for c in CHROMATIC))
    if chrom_frac >= 0.35:
        pool, group = CHROMATIC, chrom_frac
    else:
        pool, group = NEUTRAL, 1.0 - chrom_frac
    pool_total = max(float(sum(frac[ALL_COLORS.index(c)] for c in pool)), 1e-9)
    top = max(pool, key=lambda c: frac[ALL_COLORS.index(c)])
    conf = float(frac[ALL_COLORS.index(top)] / pool_total) * min(1.0, group / 0.6)
    return ColorResult(top, round(conf, 3), {c: float(frac[i]) for i, c in enumerate(ALL_COLORS)})


class VisualAttributeExtractor:
    def __init__(
        self,
        cfg: Optional[Dict[str, Any]] = None,
        clip: Optional[ClipBackend] = None,
        head_path: Optional[str] = None,
    ):
        cv = (cfg or load_config()).get("cv", {})
        self.w_other = float(cv.get("clip_weight", 0.6))
        self.w_hsv = float(cv.get("hsv_weight", 0.4))
        self.clip = clip
        self.head_entities = cv.get("color_head_entities")
        self.head: Optional[Dict[str, Any]] = None
        self.head_sha256 = ""
        path = resolve_path(head_path or cv.get("color_head_path") or HEAD_PATH)
        if os.path.exists(path):
            try:
                import joblib

                self.head = joblib.load(path)
                if (not isinstance(self.head, dict)
                        or self.head.get("features") not in {"hist", "clip"}
                        or not hasattr(self.head.get("model"), "predict_proba")):
                    self.head = None
                if self.head is not None:
                    encoder = self.head.get("meta", {}).get("encoder_model")
                    if self.head.get("features") == "clip" and encoder and encoder != getattr(clip, "name", None):
                        self.head = None
                    else:
                        self.head_sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            except Exception as exc:
                print(f"[attributes] could not load colour head ({exc.__class__.__name__}); ignoring")

    @property
    def method(self) -> str:
        clip_ok = self.clip is not None and self.clip.available
        if self.head is not None and (clip_ok or self.head.get("features") == "hist"):
            return "hsv+head"
        return "hsv+clip" if clip_ok else "hsv"

    def provenance(self) -> Dict[str, Any]:
        active = self.method == "hsv+head"
        return {"classifier": "logistic-regression" if active else "none",
                "classifier_artifact_sha256": self.head_sha256 if active else None,
                "classifier_features": self.head.get("features") if active else None,
                "classifier_classes": list(self.head.get("classes", [])) if active else [],
                "classifier_entity_scope": self.head_entities,
                "classifier_dataset_sha256": self.head.get("meta", {}).get("manifest_sha256") if active else None,
                "classifier_calibrated": self.head.get("meta", {}).get("calibrated", False) if active else False}

    def _other_probs(self, crop: Image.Image, entity: Optional[str]) -> Optional[Dict[str, float]]:
        if self.head_entities and entity not in self.head_entities:
            return None
        clip_ok = self.clip is not None and self.clip.available
        if self.head is not None:
            feats = None
            if self.head.get("features") == "clip" and clip_ok:
                feats = self.clip.image_features([crop])[0]
            elif self.head.get("features") == "hist":
                feats = color_histogram_embedding(crop)
            if feats is not None:
                probs = self.head["model"].predict_proba([feats])[0]
                return {normalize_value(c): float(p) for c, p in zip(self.head["model"].classes_, probs)}
        if clip_ok:
            noun = entity or "object"
            return self.clip.zero_shot(crop, ALL_COLORS, f"a photo of a {{}} {noun}")
        return None

    def extract(
        self, crop: Image.Image, entity: Optional[str] = None, subtract_background: bool = False
    ) -> Dict[str, Any]:
        hsv = hsv_color(crop, subtract_background=subtract_background)
        other = self._other_probs(crop, entity)
        if other is None:
            return {"color": normalize_value(hsv.color), "confidence": hsv.confidence, "method": "hsv",
                    "hsv_color": hsv.color, "hsv_confidence": hsv.confidence,
                    "distribution": hsv.distribution}
        wo, wh = self.w_other, self.w_hsv
        z = wo + wh
        wo, wh = wo / z, wh / z
        names = {normalize_value(n) for n in list(other) + list(hsv.distribution)}
        hsv_p = {normalize_value(k): v for k, v in hsv.distribution.items()}
        comb = {n: wo * other.get(n, 0.0) + wh * hsv_p.get(n, 0.0) for n in names}
        top = max(comb, key=comb.get)
        hsv_part = hsv.confidence if normalize_value(hsv.color) == top else hsv_p.get(top, 0.0)
        conf = wo * other.get(top, 0.0) + wh * hsv_part
        return {"color": top, "confidence": round(float(conf), 3), "method": self.method,
                "hsv_color": hsv.color, "hsv_confidence": hsv.confidence,
                "other_top": max(other, key=other.get), "distribution": comb}
