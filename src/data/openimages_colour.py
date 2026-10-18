"""Bounded Open Images V7 colour study preparation, never pseudo-labels from HSV.

Object boxes and human-written Localized Narratives are joined by image ID.
Caption-derived labels are weak labels until independent review; object groups
are conservative author/duplicate proxies, not verified physical identities.
Images and metadata stay in the ignored data/raw directory.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import urllib.request

from PIL import Image


SOURCES = {
    "classes.csv": "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv",
    "boxes.csv": "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv",
    "images.csv": "https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv",
    "captions.jsonl": "https://storage.googleapis.com/localized-narratives/annotations/open_images_validation_captions.jsonl",
}
COLORS = "red blue black white green yellow silver gray orange brown purple pink".split()


def caption_colour(caption):
    """Only explicit singular-car colour phrases; ambiguous mentions are rejected."""
    colors = "|".join(COLORS + ["grey"])
    matches = re.findall(r"\b(" + colors + r")\s+(?:(?:colou?red|colou?r)\s+)?car\b", caption.lower())
    matches += re.findall(r"\bcar\s+(?:is|in)\s+(?:a\s+)?(" + colors + r")\b", caption.lower())
    values = {"gray" if x == "grey" else x for x in matches}
    return next(iter(values)) if len(values) == 1 else None


def candidates(root):
    root = Path(root)
    meta = root / "metadata"
    captions = defaultdict(list)
    with (meta / "captions.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            color = caption_colour(row["caption"])
            if color:
                captions[row["image_id"]].append((color, row))
    with (meta / "classes.csv").open(encoding="utf-8", newline="") as f:
        car_id = next(row[0] for row in csv.reader(f) if row[1] == "Car")
    boxes = defaultdict(list)
    with (meta / "boxes.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["LabelName"] == car_id and row["ImageID"] in captions:
                boxes[row["ImageID"]].append(row)
    with (meta / "images.csv").open(encoding="utf-8", newline="") as f:
        information = {r["ImageID"]: r for r in csv.DictReader(f) if r["ImageID"] in boxes}
    output = []
    for image_id, items in boxes.items():
        if len(items) != 1 or len({c for c, _ in captions[image_id]}) != 1:
            continue
        box, info = items[0], information.get(image_id)
        if not info or info["License"] != "https://creativecommons.org/licenses/by/2.0/" or not info["AuthorProfileURL"]:
            continue
        if any(box.get(k) != "0" for k in ("IsGroupOf", "IsDepiction", "IsInside", "IsTruncated", "IsOccluded")):
            continue
        xy = [float(box[k]) for k in ("XMin", "YMin", "XMax", "YMax")]
        if (xy[2] - xy[0]) * (xy[3] - xy[1]) < .08:
            continue
        color, narrative = captions[image_id][0]
        output.append({"image_id": image_id, "label": color, "bbox": xy,
                       "caption": narrative["caption"], "caption_annotator_id": narrative["annotator_id"],
                       "label_source": "human-caption-derived; independent verification pending",
                       "object_id": "author-" + hashlib.sha256(info["AuthorProfileURL"].encode()).hexdigest()[:20],
                       "group_scope": "photographer proxy; not physical-object ground truth",
                       "image_info": info})
    return output


def acquire(root, per_class=50, classes=("red", "blue", "black", "white")):
    root = Path(root)
    if (root / "acquisition.json").exists():
        raise FileExistsError("Acquisition record exists. Reuse it or use a new dataset directory.")
    metadata = root / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        file = metadata / name
        if not file.exists():
            with urllib.request.urlopen(url, timeout=60) as stream, file.open("xb") as out:
                out.write(stream.read())
    eligible = candidates(root)
    selected = []
    for label in classes:
        pool = sorted((r for r in eligible if r["label"] == label),
                      key=lambda r: hashlib.sha256(("openimages-colour-v1:" + r["image_id"]).encode()).hexdigest())
        selected += pool[:per_class]
    (root / "images").mkdir(exist_ok=True)
    (root / "crops").mkdir(exist_ok=True)
    def download(row):
        image_id = row["image_id"]
        path = root / "images" / (image_id + ".jpg")
        url = f"https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg"
        try:
            if not path.exists():
                with urllib.request.urlopen(url, timeout=45) as stream:
                    raw = stream.read(12 * 1024 * 1024 + 1)
                if len(raw) > 12 * 1024 * 1024:
                    raise ValueError("image exceeds per-image size bound")
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
                with path.open("xb") as stream:
                    stream.write(raw)
            crop_path = root / "crops" / (image_id + ".png")
            if not crop_path.exists():
                with Image.open(path) as image:
                    image = image.convert("RGB")
                    # Open Images coordinates refer to the released image pixels.
                    x1, y1, x2, y2 = row["bbox"]
                    w, h = image.size
                    crop = image.crop((round(x1*w), round(y1*h), round(x2*w), round(y2*h)))
                    crop.thumbnail((512, 512))
                    with crop_path.open("xb") as stream:
                        crop.save(stream, format="PNG")
            row["download_url"] = url
            row["image_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            row["path"] = "crops/" + crop_path.name
            return row
        except Exception as exc:
            return {"image_id": image_id, "error": type(exc).__name__}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, selected))
    report = {"source": "Open Images V7 official download page; shared V5 boxes and V6 narratives",
              "metadata": {n: {"url": u, "sha256": hashlib.sha256((metadata/n).read_bytes()).hexdigest()} for n, u in SOURCES.items()},
              "candidate_counts": dict(Counter(r["label"] for r in eligible)),
              "downloaded": [r for r in results if "error" not in r],
              "failures": [r for r in results if "error" in r]}
    destination = root / "acquisition.json"
    if destination.exists():
        raise FileExistsError("Acquisition record exists. Reuse it or use a new dataset directory.")
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"eligible": report["candidate_counts"], "downloaded": len(report["downloaded"]), "failures": len(report["failures"])}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/raw/openimages_colour_v1")
    parser.add_argument("--per-class", type=int, default=50)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.per_class <= 100:
        parser.error("per-class must be between 1 and 100")
    if args.audit_only:
        print(dict(Counter(r["label"] for r in candidates(args.root))))
    else:
        acquire(args.root, args.per_class)


if __name__ == "__main__":
    main()
