"""Contact sheets and explicit review records for caption-derived colour labels."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def sheets(root):
    root = Path(root)
    record = json.loads((root / "acquisition.json").read_text())
    rows = sorted(record["downloaded"], key=lambda r: (r["label"], r["image_id"]))
    review = root / "review"
    review.mkdir(exist_ok=True)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for first in range(0, len(rows), 24):
        page = Image.new("RGB", (1200, 1100), "white")
        draw = ImageDraw.Draw(page)
        for j, row in enumerate(rows[first:first+24]):
            x, y = (j % 4) * 300, (j // 4) * 180
            with Image.open(root / row["path"]) as source:
                picture = ImageOps.contain(source.convert("RGB"), (292, 145))
                page.paste(picture, (x + (292-picture.width)//2, y + 24))
            draw.text((x+4, y+3), f"{first+j:03d}  caption: {row['label']}", font=font, fill="black")
        page.save(review / f"sheet_{first//24:02d}.jpg", quality=92)
    with (review / "index.json").open("x", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print("Crops for review:", len(rows), Counter(r["label"] for r in rows))


def freeze(root, excluded, reviewer="assistant-visual-review"):
    """Freeze explicit review outcomes and conservative author/duplicate groups.

    This is AI review of human captions, not independent human annotation.
    All ambiguous or uncertain crops must be excluded with a recorded reason.
    """
    root = Path(root)
    rows = json.loads((root / "review/index.json").read_text())
    parents = {}
    def find(g):
        parents.setdefault(g, g)
        while parents[g] != g:
            g = parents[g]
        return g
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parents[max(a,b)] = min(a,b)
    checked, fingerprints, retained = [], set(), []
    decisions = []
    for index, row in enumerate(rows):
        reason = excluded.get(index)
        if not reason:
            with Image.open(root / row["path"]) as image:
                image = image.convert("RGB")
                pixel_hash = hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
                gray = np.asarray(image.convert("L").resize((9,8)), dtype=np.int16)
                h = sum(int(b)<<i for i,b in enumerate((gray[:,1:] > gray[:,:-1]).ravel()))
            if pixel_hash in fingerprints:
                reason = "duplicate decoded crop"
            else:
                fingerprints.add(pixel_hash)
                group = row["object_id"]
                find(group)
                for old_hash, old_group in checked:
                    if (old_hash ^ h).bit_count() <= 2:
                        union(group, old_group)
                checked.append((h, group))
                retained.append(row)
        decisions.append({"index": index, "image_id": row["image_id"], "caption_label": row["label"],
                          "decision": "exclude" if reason else "retain-caption-label",
                          "reason": reason or "caption agrees with assistant visual review",
                          "reviewer": reviewer})
    manifest = []
    for row in retained:
        manifest.append({"path": row["path"], "label": row["label"],
                         "object_id": find(row["object_id"]),
                         "source": row["image_info"]["OriginalLandingURL"],
                         "license": row["image_info"]["License"],
                         "annotation_status": "human-caption-derived; assistant-reviewed; not independent human gold",
                         "group_scope": "source-author plus perceptual clusters; physical-object identity unverified"})
    # O_EXCL semantics preserve previously frozen datasets/reviews.
    with (root / "manifest.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    with (root / "review/decisions.json").open("x", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)
    print("Frozen", len(manifest), "crops", dict(Counter(r["label"] for r in manifest)),
          "groups", len({r["object_id"] for r in manifest}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/raw/openimages_colour_v1")
    parser.add_argument("--exclusions", help="Frozen review decisions; image-index fingerprint must match")
    args = parser.parse_args()
    if args.exclusions:
        record = json.loads(Path(args.exclusions).read_text())
        rows = json.loads((Path(args.root) / "review/index.json").read_text())
        fingerprint = hashlib.sha256("\n".join(r["image_id"] for r in rows).encode()).hexdigest()
        if fingerprint != record["review_index_sha256"]:
            raise ValueError("Review index changed; do not apply numbered labels to different images.")
        freeze(args.root, {int(k):v for k,v in record["excluded_indices"].items()})
    else:
        sheets(args.root)
