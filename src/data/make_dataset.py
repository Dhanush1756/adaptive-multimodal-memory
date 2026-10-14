"""Generate the synthetic benchmark.

    python -m src.data.make_dataset --n 300 --seed 0 --out data/synthetic --save-images
"""
from __future__ import annotations

import argparse

from .synthetic import generate_dataset


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=300, help="number of scenarios")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--save-images", action="store_true",
                    help="write PNGs (otherwise images are re-rendered deterministically from specs)")
    a = ap.parse_args()
    data = generate_dataset(a.n, a.seed, a.out, a.save_images)
    n_s = sum(len(d["sessions"]) for d in data)
    n_q = sum(len(d["queries"]) for d in data)
    print(f"wrote {len(data)} scenarios, {n_s} sessions, {n_q} questions to {a.out}/scenarios.jsonl")


if __name__ == "__main__":
    main()
