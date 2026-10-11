"""Train the optional colour head: logistic regression on CLIP (or histogram) crop features.

    # synthetic only (pipeline check; will NOT transfer to real photos)
    python -m src.training.train_color_head --data data/synthetic

    # recommended: add your own real photos, one folder per colour
    python -m src.training.train_color_head --data data/synthetic --real-dir data/raw/colors
        data/raw/colors/red/*.jpg   data/raw/colors/blue/*.jpg ...

Features: CLIP image features if CLIP loads (config cv.clip_model), else a colour histogram.
The head replaces CLIP zero-shot in src/cv/attributes.py and is blended with the HSV evidence.
Crops are produced by exactly the same detect -> select -> crop path as at inference time.

Evaluation printed: synthetic dev accuracy, held-out real-photo accuracy (20%, chosen by file
name hash so it is stable across runs), and the HSV-only baseline on the same images.
Use only held-out numbers in reports. Photos must be collected legally and without people/faces.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Any, List, Tuple

import joblib
import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression

from ..config import load_config, resolve_path
from ..cv.attributes import hsv_color
from ..cv.detection import crop_to_bbox, select_primary
from ..cv.embeddings import color_histogram_embedding
from ..cv.preprocessing import load_image
from ..data.synthetic import load_dataset, render_session_image
from ..evaluation.benchmarks import split_dataset
from ..memory.conflict import normalize_value
from ..multimodal.visual_pipeline import VisualPipeline

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def crop_for(vp: VisualPipeline, img: Image.Image, entity):
    dets = vp.detector.detect(img)
    primary = select_primary(dets, img, entity)
    return (crop_to_bbox(img, primary.bbox) if primary.source != "fallback" else img), primary.source


def featurize(vp: VisualPipeline, crop: Image.Image, kind: str) -> np.ndarray:
    return vp.clip.image_features([crop])[0] if kind == "clip" else color_histogram_embedding(crop)


def synthetic_items(scenarios) -> List[Tuple[Image.Image, str, str]]:
    out = []
    for sc in scenarios:
        for s in sc["sessions"]:
            img = render_session_image(s)
            if img is not None and s["gt"]["image_color"]:
                out.append((load_image(img), normalize_value(s["gt"]["image_color"]), sc["entity"]))
    return out


def real_items(root: str, holdout: bool) -> List[Tuple[Image.Image, str, None]]:
    out = []
    for d in sorted(Path(root).iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in IMG_EXT:
                continue
            is_hold = int(hashlib.md5(p.name.encode()).hexdigest(), 16) % 5 == 0
            if is_hold == holdout:
                out.append((load_image(str(p)), normalize_value(d.name), None))
    return out


def evaluate(name: str, clf: Any, items, vp: VisualPipeline, kind: str) -> None:
    if not items:
        return
    hsv_ok = head_ok = 0
    for img, gold, ent in items:
        crop, _ = crop_for(vp, img, ent)
        head_ok += int(normalize_value(str(clf.predict([featurize(vp, crop, kind)])[0])) == gold)
        hsv_ok += int(normalize_value(hsv_color(crop, subtract_background=True).color) == gold)
    n = len(items)
    print(f"{name:<22} n={n:<5} head={head_ok / n:.3f}   hsv-only={hsv_ok / n:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--real-dir", default=None)
    ap.add_argument("--seed", type=int, default=0, help="must match the dataset split seed")
    ap.add_argument("--light", action="store_true", help="force histogram features (no CLIP)")
    ap.add_argument("--C", type=float, default=2.0)
    ap.add_argument("--out", default=resolve_path("models/color_head.joblib"))
    a = ap.parse_args()

    vp = VisualPipeline(load_config(), light=a.light)
    kind = "clip" if (vp.clip is not None and vp.clip.available) else "hist"
    print(f"feature type: {kind}")

    splits = split_dataset(load_dataset(a.data), a.seed)
    train = synthetic_items(splits["train"])
    dev = synthetic_items(splits["dev"])
    real_train = real_items(a.real_dir, holdout=False) if a.real_dir else []
    real_hold = real_items(a.real_dir, holdout=True) if a.real_dir else []
    train = train + real_train
    print(f"train images: {len(train)} (real: {len(real_train)})   dev: {len(dev)}   real held-out: {len(real_hold)}")

    X, y = [], []
    for img, label, ent in train:
        crop, _ = crop_for(vp, img, ent)
        X.append(featurize(vp, crop, kind))
        y.append(label)
    clf = LogisticRegression(C=a.C, max_iter=3000, class_weight="balanced").fit(np.stack(X), y)

    evaluate("synthetic dev", clf, dev, vp, kind)
    evaluate("real held-out", clf, real_hold, vp, kind)
    if not real_train:
        print("NOTE: trained on synthetic images only; expect little or no gain on real photos.")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    joblib.dump({"model": clf, "features": kind, "classes": list(clf.classes_),
                 "meta": {"n_train": len(train), "n_real": len(real_train)}}, a.out)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
