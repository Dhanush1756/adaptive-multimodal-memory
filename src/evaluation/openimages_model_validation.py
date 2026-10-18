"""Validate the saved Open Images head through actual pipeline and memory calls.

No refitting, tuning, frozen-benchmark execution or user database access.
Metrics are relative to the recorded weak/assistant-reviewed labels.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from ..agent.reasoning import MemoryAgent
from ..config import load_config
from ..cv.attributes import hsv_color
from ..multimodal.visual_pipeline import VisualPipeline


def validate(dataset_root, experiment, output):
    root, experiment, out = Path(dataset_root), Path(experiment), Path(output)
    if out.exists():
        raise FileExistsError("Use a new report directory; previous evaluations are immutable.")
    manifest = json.loads((experiment / "manifest.json").read_text())
    metrics = json.loads((experiment / "metrics.json").read_text())
    cfg = load_config("config.openimages.yaml")
    cfg["cv"]["color_head_path"] = str((experiment / "color_head.joblib").resolve())
    visual = VisualPipeline(cfg, light=True)
    if visual.status()["color"] != "hsv+head":
        raise RuntimeError("Saved trained classifier was not loaded.")
    predictions = []
    for row in manifest:
        if row["split"] != "test":
            continue
        with Image.open(root / row["path"]) as image:
            start = time.perf_counter()
            analysis = visual.analyze(image, preferred_entity="car")
            elapsed = (time.perf_counter() - start) * 1000
            hsv = hsv_color(image, subtract_background=True).color
        predictions.append({"path": row["path"], "gold_scope": "caption-derived; assistant-reviewed",
                            "expected": row["label"], "pipeline_prediction": analysis.color,
                            "hsv_prediction": hsv, "correct": analysis.color == row["label"],
                            "confidence": analysis.confidence, "method": analysis.method,
                            "association_status": analysis.association_status,
                            "classifier": analysis.classifier, "latency_ms": elapsed})
    whites = sorted((r for r in manifest if r["split"] == "test" and r["label"] == "white"), key=lambda r:r["path"])
    checks = []
    if whites:
        # Choose by path before examining a prediction; never cherry-pick the
        # demonstration image based on correctness.
        chosen = whites[0]
        for source in ("text", "image"):
            agent = MemoryAgent(cfg, db_path=":memory:", light=True, use_intent_model=False)
            agent.remember("My car is red.", timestamp="2026-10-01", session_id="original-red")
            with Image.open(root / chosen["path"]) as image:
                result = agent.remember("My car is red.", image, "2026-10-10", "real-photo-crosscheck")
            request = agent.verification_request(result)
            before = agent.ask("What color is my car now?")
            if request:
                selected = request["memory_value"] if source == "text" else request["image_value"]
                agent.verify(result, selected, actor="automated_integration_check",
                             rationale="Integration check of saved trained head; not a human demonstration")
            checks.append({"source": source, "photo": chosen["path"], "expected_photo_colour": "white",
                           "observed_photo_colour": result.image["color"],
                           "state_before_resolution": before.value, "prompted": request is not None,
                           "current_after": agent.ask("What color is my car now?").value,
                           "original_after": agent.ask("What color was my car originally?").value,
                           "audit_count": len(agent.conflict_audit()),
                           "evidence_methods": [e.get("attribute_model") for e in before.evidence if e["modality"] == "image"]})
            agent.store.close()
    y = [r["expected"] for r in predictions]
    p = [r["pipeline_prediction"] for r in predictions]
    h = [r["hsv_prediction"] for r in predictions]
    hsv_labels = sorted(set(y+h))
    labels = sorted(set(y+p))
    report = {"configuration": metrics["configuration"], "loaded_status": visual.status(),
              "dataset_counts": {s:dict(Counter(r["label"] for r in manifest if r["split"]==s)) for s in ("train","dev","test")},
              "model_artifact_sha256": hashlib.sha256((experiment/"color_head.joblib").read_bytes()).hexdigest(),
              "test_n": len(y), "pipeline_accuracy": accuracy_score(y,p),
              "pipeline_per_class": classification_report(y,p,labels=labels,output_dict=True,zero_division=0),
              "pipeline_confusion_labels": labels, "pipeline_confusion_matrix": confusion_matrix(y,p,labels=labels).tolist(),
              "hsv_confusion_labels": hsv_labels, "hsv_confusion_matrix": confusion_matrix(y,h,labels=hsv_labels).tolist(),
              "memory_checks": checks, "predictions": predictions,
              "interpretation": "Exploratory four-colour real-car study with weak/AI-reviewed labels, author/duplicate groups, no verified physical identity and no pretrained detector or encoder."}
    out.mkdir(parents=True)
    for name, content in (("training_metrics.json",metrics),("split_manifest.json",manifest),("pipeline_validation.json",report)):
        (out/name).write_text(json.dumps(content,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("dataset_counts","loaded_status","test_n","pipeline_accuracy","memory_checks")},indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default="data/raw/openimages_colour_v1")
    p.add_argument("--experiment", default="models/openimages_car_colour_v1")
    p.add_argument("--out", default="reports/openimages_colour_v1")
    a = p.parse_args()
    validate(a.dataset,a.experiment,a.out)


if __name__ == "__main__":
    main()
