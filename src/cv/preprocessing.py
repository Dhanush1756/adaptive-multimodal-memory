"""Image loading and quality checks (brief section 14, stages 1-2)."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image


def load_image(src: Any, max_side: int = 640) -> Image.Image:
    """Accept a path, bytes, file-like object (e.g. Streamlit upload) or PIL image -> RGB image.

    Large images are downscaled so the longest side is <= max_side (speed; colour statistics
    are unaffected).
    """
    if isinstance(src, Image.Image):
        img = src
    elif isinstance(src, (str, Path)):
        img = Image.open(src)
    elif isinstance(src, (bytes, bytearray)):
        img = Image.open(io.BytesIO(bytes(src)))
    elif hasattr(src, "read"):
        data = src.read()
        try:
            src.seek(0)
        except Exception:
            pass
        img = Image.open(io.BytesIO(data))
    else:
        raise TypeError(f"unsupported image source: {type(src)!r}")
    img = img.convert("RGB")
    w, h = img.size
    scale = max_side / float(max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return img


def quality_report(img: Image.Image) -> Dict[str, Any]:
    """Cheap quality signals used to down-weight visual confidence.

    sharpness = variance of a 4-neighbour Laplacian on the grey image (low -> blurry).
    Thresholds are rough defaults; calibrate on your own photos.
    """
    g = np.asarray(img.convert("L"), dtype=np.float32)
    brightness = float(g.mean())
    if g.shape[0] > 2 and g.shape[1] > 2:
        lap = (-4.0 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
        sharpness = float(lap.var())
    else:
        sharpness = 0.0
    flags: List[str] = []
    if brightness < 40:
        flags.append("dark")
    if brightness > 225:
        flags.append("overexposed")
    if sharpness < 15:
        flags.append("blurry")
    if min(img.size) < 64:
        flags.append("small")
    return {
        "width": img.size[0], "height": img.size[1],
        "brightness": round(brightness, 1), "sharpness": round(sharpness, 1), "flags": flags,
    }
