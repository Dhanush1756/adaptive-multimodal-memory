"""Export reproducibility metadata and image attribution without image pixels."""
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import statistics

import joblib


def wilson(success, total):
    z = 1.96
    p = success / total
    d = 1 + z*z/total
    mid = (p+z*z/(2*total))/d
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [mid-half,mid+half]


def main():
    root = Path("data/raw/openimages_colour_v1")
    output = Path("reports/openimages_colour_v1")
    report_path = output / "provenance.json"
    if report_path.exists():
        raise FileExistsError("Provenance report exists; preserve the completed run.")
    acquisition = json.loads((root/"acquisition.json").read_text())
    decisions = json.loads((root/"review/decisions.json").read_text())
    validation = json.loads((output/"pipeline_validation.json").read_text())
    manifest = json.loads((output/"split_manifest.json").read_text())
    model = joblib.load("models/openimages_car_colour_v1/color_head.joblib")
    credits = [{"image_id":r["image_id"], "crop":r["path"], "author":r["image_info"]["Author"],
                "author_profile":r["image_info"]["AuthorProfileURL"], "title":r["image_info"]["Title"],
                "original_landing_url":r["image_info"]["OriginalLandingURL"], "license":r["image_info"]["License"],
                "bbox":r["bbox"], "caption":r["caption"], "caption_annotator_id":r["caption_annotator_id"],
                "image_sha256":r["image_sha256"], "label":r["label"]} for r in acquisition["downloaded"]]
    packages = ["numpy","Pillow","PyYAML","scikit-learn","joblib","streamlit","pytest"]
    n = validation["test_n"]
    predictions = validation["predictions"]
    latency = [p["latency_ms"] for p in predictions]
    report = {"study": "Open Images V7 four-colour car baseline v1", "python":platform.python_version(),
              "packages":{p:importlib.metadata.version(p) for p in packages},
              "downloads":len(credits), "excluded":sum(r["decision"]=="exclude" for r in decisions),
              "retained":len(manifest), "source_metadata":acquisition["metadata"],
              "model_path":"models/openimages_car_colour_v1/color_head.joblib",
              "model_sha256":validation["model_artifact_sha256"], "model_parameters":model["model"].get_params(),
              "model_feature_dimension":int(model["model"].n_features_in_),
              "split_image_counts":dict(Counter(r["split"] for r in manifest)),
              "split_group_counts":{s:len({r["object_id"] for r in manifest if r["split"]==s}) for s in ("train","dev","test")},
              "pipeline_accuracy_wilson95_image_level":wilson(sum(p["correct"] for p in predictions),n),
              "hsv_accuracy_wilson95_image_level":wilson(sum(p["hsv_prediction"]==p["expected"] for p in predictions),n),
              "pipeline_median_ms":statistics.median(latency), "pipeline_max_ms":max(latency),
              "ci_scope":"Descriptive image-level Wilson intervals; not group-bootstrap or a significance test.",
              "label_quality":"Human-caption-derived, assistant visually reviewed before split; independent human validation pending.",
              "group_quality":"Photographer + near-duplicate proxy. Physical-object isolation across photographers not proven.",
              "licensing":"Provider-listed CC BY 2.0 image metadata retained with attribution; independent contemporary legal verification not performed. Annotation sources CC BY 4.0.",
              "pretrained_encoder_used":False,"pretrained_detector_used":False,"model_environment_installed":False}
    for name, value in (("provenance.json",report),("attribution.json",credits),("review_decisions.json",decisions)):
        with (output/name).open("x",encoding="utf-8") as f:
            json.dump(value,f,indent=2)
    print(json.dumps({k:report[k] for k in ("split_image_counts","split_group_counts","pipeline_accuracy_wilson95_image_level","pipeline_median_ms","model_sha256")},indent=2))


if __name__ == "__main__":
    main()
