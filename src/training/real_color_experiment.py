"""Real-photo experiment with explicit features and object-group split manifests.

Input CSV: path,label,object_id,source,license. Paths are relative to the CSV.
Object IDs must group all views/augmentations/near-duplicates of one object.
Only user-supplied, permission-reviewed images are accepted. No downloads.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from ..config import load_config
from ..cv.attributes import hsv_color
from ..cv.embeddings import color_histogram_embedding, ClipBackend


def prepare(csv_path, seed=13):
    """Allocate entire object groups, fail closed on duplicate pixels across groups.

    A global group assignment also prevents one multicoloured physical object
    leaking across label-specific splits. Near-duplicate grouping needs human review.
    """
    csv_path = Path(csv_path).resolve()
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("No real photographs are declared in the manifest.")
    labels = set(load_config()["cv"]["colors"])
    seen = {}
    reviewed = []
    for row in rows:
        if not all(row.get(k, "").strip() for k in ("path", "label", "object_id", "source", "license")):
            raise ValueError("Every image needs path, label, object_id, source and license.")
        if row["label"] not in labels:
            raise ValueError("Unknown colour label: " + row["label"])
        path = (csv_path.parent / row["path"]).resolve()
        path.relative_to(csv_path.parent)
        with Image.open(path) as image:
            image = image.convert("RGB")
            pixel_hash = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
            gray = np.asarray(image.convert("L").resize((9, 8)), dtype=np.int16)
            bits = (gray[:, 1:] > gray[:, :-1]).ravel()
            dhash = sum(int(bit) << i for i, bit in enumerate(bits))
        if pixel_hash in seen:
            raise ValueError("Duplicate decoded image; remove duplicate rows before splitting.")
        seen[pixel_hash] = row["object_id"]
        for previous_hash, group in reviewed:
            if group != row["object_id"] and (previous_hash ^ dhash).bit_count() <= 2:
                raise ValueError("Potential near-duplicate across object groups; review grouping before training.")
        reviewed.append((dhash, row["object_id"]))
        row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        row["pixel_sha256"] = pixel_hash
        row["dhash"] = f"{dhash:016x}"
        row["absolute_path"] = str(path)
    groups = sorted({r["object_id"] for r in rows})
    if len(groups) < 5:
        raise ValueError("At least five independent object groups are required.")
    rng = np.random.default_rng(seed)
    rng.shuffle(groups)
    n_test = max(1, round(len(groups) * .2))
    n_dev = max(1, round(len(groups) * .2))
    assignment = {g: ("test" if i < n_test else "dev" if i < n_test + n_dev else "train") for i, g in enumerate(groups)}
    for row in rows:
        row["split"] = assignment[row["object_id"]]
    for label in {r["label"] for r in rows}:
        present = {r["split"] for r in rows if r["label"] == label}
        if present != {"train", "dev", "test"}:
            raise ValueError(f"Class {label} lacks independent groups in every split; collect more data before training.")
    return rows


def train(csv_path, output, features="hist", seed=13, C=2.0):
    out = Path(output)
    if out.exists():
        raise FileExistsError("Experiment output exists; use a new versioned directory.")
    rows = prepare(csv_path, seed)
    clip = None
    if features == "clip":
        config = load_config()
        config["cv"]["local_files_only"] = True
        clip = ClipBackend(config)
        if not clip.available:
            raise RuntimeError("Requested CLIP unavailable; no histogram substitution or model saved.")
    elif features != "hist":
        raise ValueError("features must be clip or hist")
    def feature(image):
        return clip.image_features([image])[0] if clip else color_histogram_embedding(image)
    X, y, hsv = [], [], []
    for row in rows:
        with Image.open(row["absolute_path"]) as image:
            # Real inputs must already be reviewed object crops. A background
            # colour must not be presented as verified object detection.
            image = image.convert("RGB")
            X.append(feature(image))
            y.append(row["label"])
            hsv.append(hsv_color(image, subtract_background=True).color)
    X, y, hsv = np.asarray(X), np.asarray(y), np.asarray(hsv)
    train_idx = [i for i, r in enumerate(rows) if r["split"] == "train"]
    model = LogisticRegression(C=C, max_iter=3000, class_weight="balanced", random_state=seed)
    model.fit(X[train_idx], y[train_idx])
    labels = sorted(set(y.tolist()))
    metrics = {}
    for split in ("dev", "test"):
        idx = [i for i, r in enumerate(rows) if r["split"] == split]
        started = time.perf_counter()
        pred = model.predict(X[idx])
        elapsed = time.perf_counter() - started
        end_to_end = time.perf_counter()
        for i in idx:
            with Image.open(rows[i]["absolute_path"]) as image:
                model.predict([feature(image.convert("RGB"))])
        end_to_end = (time.perf_counter() - end_to_end) * 1000 / len(idx)
        metrics[split] = {"n": len(idx), "classifier_accuracy": accuracy_score(y[idx], pred),
                          "hsv_accuracy": accuracy_score(y[idx], hsv[idx]),
                          "per_class": classification_report(y[idx], pred, labels=labels, output_dict=True, zero_division=0),
                          "hsv_per_class": classification_report(y[idx], hsv[idx], labels=labels, output_dict=True, zero_division=0),
                          "confusion_matrix": confusion_matrix(y[idx], pred, labels=labels).tolist(),
                          "hsv_confusion_labels": sorted(set(labels) | set(hsv[idx].tolist())),
                          "hsv_confusion_matrix": confusion_matrix(y[idx], hsv[idx], labels=sorted(set(labels) | set(hsv[idx].tolist()))).tolist(),
                          "decode_feature_head_ms_per_image": end_to_end,
                          "head_predict_ms_per_image": elapsed * 1000 / len(idx)}
    public_rows = [{k: v for k, v in r.items() if k != "absolute_path"} for r in rows]
    manifest_hash = hashlib.sha256(json.dumps(public_rows, sort_keys=True).encode()).hexdigest()
    meta = {"features": features, "seed": seed, "C": C, "classes": labels,
            "n_train": len(train_idx), "n_real": len(train_idx), "python": platform.python_version(),
            "manifest_sha256": manifest_hash,
            "input_scope": "declared object crops; annotation quality is recorded, not assumed human-verified",
            "annotation_status": sorted({r.get("annotation_status", "not recorded") for r in rows}),
            "group_scope": sorted({r.get("group_scope", "externally declared object groups") for r in rows}),
            "detector": "none", "calibrated": False,
            "encoder_model": clip.name if clip else "rgb-histogram-64"}
    out.mkdir(parents=True)
    joblib.dump({"model": model, "features": features, "classes": labels, "meta": meta}, out / "color_head.joblib")
    (out / "manifest.json").write_text(json.dumps(public_rows, indent=2), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps({"configuration": meta, "metrics": metrics}, indent=2), encoding="utf-8")
    return metrics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--features", required=True, choices=("clip", "hist"))
    p.add_argument("--seed", type=int, default=13)
    a = p.parse_args()
    print(json.dumps(train(a.manifest, a.out, a.features, a.seed), indent=2))


if __name__ == "__main__":
    main()
