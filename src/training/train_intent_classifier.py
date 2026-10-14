"""Train the optional query-intent classifier (CPU, seconds).

    python -m src.training.train_intent_classifier \
        --data data/synthetic --paraphrases data/annotations/intent_paraphrases.csv

Data  : synthetic questions (train split) + hand-written paraphrases (CSV: question,intent).
        Every 4th paraphrase row is held out as a dev set that the model never sees.
Model : TF-IDF (word 1-2 grams over slot-masked text) + logistic regression.
Output: models/intent_clf.joblib  (loaded by src/agent/intent_model.py; it only overrides the
        rules when the rule parser is unsure, so it can only help on questions the rules miss).

Report the rule-only vs rules+model numbers on the HELD-OUT paraphrases, never on training rows.
Synthetic questions are template-generated, so accuracy there says little: add your own
paraphrases (ideally written by people who have not seen the rules) to the CSV.
"""
from __future__ import annotations

import argparse
import csv
import os
from typing import Dict, List

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline

from ..agent.query_parser import parse_query
from ..config import resolve_path
from ..data.synthetic import load_dataset
from ..evaluation.benchmarks import split_dataset
from .text_prep import mask_slots


def _rules_acc(rows: List[Dict[str, str]]) -> float:
    ok = sum(parse_query(r["question"], "2026-10-20T10:00:00", context_entity="car").intent.value == r["intent"]
             for r in rows)
    return ok / max(len(rows), 1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--paraphrases", default="data/annotations/intent_paraphrases.csv")
    ap.add_argument("--seed", type=int, default=0, help="must match the seed used for the dataset split")
    ap.add_argument("--out", default=resolve_path("models/intent_clf.joblib"))
    a = ap.parse_args()

    data = split_dataset(load_dataset(a.data), a.seed)
    to_rows = lambda scs: [{"question": q["question"], "intent": q["intent"]} for sc in scs for q in sc["queries"]]
    syn_train, syn_dev = to_rows(data["train"]), to_rows(data["dev"])

    with open(a.paraphrases, newline="", encoding="utf-8") as f:
        para = [r for r in csv.DictReader(f) if r.get("question") and r.get("intent")]
    para_dev = [r for i, r in enumerate(para) if i % 4 == 0]
    para_train = [r for i, r in enumerate(para) if i % 4 != 0]

    train = syn_train + para_train * 3          # upweight the (scarcer) human-written rows
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=mask_slots, ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(C=5.0, max_iter=3000, class_weight="balanced")),
    ])
    pipe.fit([r["question"] for r in train], [r["intent"] for r in train])

    for name, rows in (("synthetic dev", syn_dev), ("held-out paraphrases", para_dev)):
        if not rows:
            continue
        pred = pipe.predict([r["question"] for r in rows])
        gold = [r["intent"] for r in rows]
        print(f"\n== {name} (n={len(rows)})")
        print(f"rules only : {_rules_acc(rows):.3f}")
        print(f"model only : {accuracy_score(gold, pred):.3f}")
        print(classification_report(gold, pred, zero_division=0))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    joblib.dump(pipe, a.out)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
