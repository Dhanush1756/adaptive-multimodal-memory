"""NLP-only and CV-only evaluation (brief section 5: report each modality separately).

    python -m src.evaluation.component_eval --data data/synthetic --split test [--light]
    python -m src.evaluation.component_eval --paraphrases data/annotations/intent_paraphrases.csv

NLP : colour-value extraction P/R/F1, entity accuracy, query-intent accuracy
CV  : colour accuracy (per colour), mean confidence of correct vs wrong predictions
Synthetic CV numbers measure an easy domain; never present them as real-world accuracy.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from typing import Any, Dict, List

from ..agent.query_parser import parse_query
from ..agent.reasoning import build_components
from ..config import load_config
from ..data.synthetic import load_dataset, render_session_image
from ..memory.conflict import normalize_value
from ..nlp.relation_extraction import extract_claims
from ..utils import parse_ts
from .benchmarks import split_dataset
from .metrics import prf


def evaluate_text_extraction(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    tp = fp = fn = ent_ok = ent_n = 0
    for sc in scenarios:
        for s in sc["sessions"]:
            if not s["text"]:
                continue
            gold = s["gt"]["text_value"]
            claims = extract_claims(s["text"], parse_ts(s["timestamp"]), context_entity=sc["entity"])
            pred = next((normalize_value(c.value) for c in claims if c.value), None)
            if gold is not None and pred is not None and normalize_value(gold) == pred:
                tp += 1
            else:
                fp += 1 if pred is not None else 0
                fn += 1 if gold is not None else 0
            if claims and claims[0].entity:
                ent_n += 1
                ent_ok += int(claims[0].entity == s["gt"]["entity"])
    return {**prf(tp, fp, fn), "entity_accuracy": (ent_ok / ent_n) if ent_n else None, "n_entity_claims": ent_n}


def evaluate_visual(scenarios: List[Dict[str, Any]], visual: Any) -> Dict[str, Any]:
    right, wrong = [], []
    per: Dict[str, List[int]] = defaultdict(list)
    confusions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    sources: Dict[str, int] = defaultdict(int)
    for sc in scenarios:
        for s in sc["sessions"]:
            img = render_session_image(s)
            gold = s["gt"]["image_color"]
            if img is None or gold is None:
                continue
            an = visual.analyze(img, preferred_entity=sc["entity"])
            ok = normalize_value(an.color) == normalize_value(gold)
            per[normalize_value(gold)].append(int(ok))
            (right if ok else wrong).append(an.confidence)
            sources[an.detection.source] += 1
            if not ok:
                confusions[normalize_value(gold)][normalize_value(an.color)] += 1
    n = len(right) + len(wrong)
    mean = lambda v: (sum(v) / len(v)) if v else None
    return {
        "color_accuracy": (len(right) / n) if n else None, "n_images": n,
        "per_color": {c: {"accuracy": sum(v) / len(v), "n": len(v)} for c, v in sorted(per.items())},
        "mean_conf_correct": mean(right), "mean_conf_wrong": mean(wrong),
        "detector_source": dict(sources),
        "confusions": {g: dict(p) for g, p in confusions.items()},
    }


def evaluate_intents(pairs: List[Dict[str, str]], intent_model: Any = None) -> Dict[str, Any]:
    from ..agent.intent_model import apply_intent_model

    ok = ok_model = 0
    errors = []
    for p in pairs:
        parsed = parse_query(p["question"], "2026-10-20T10:00:00", context_entity="car")
        ok += int(parsed.intent.value == p["intent"])
        if intent_model is not None:
            ok_model += int(apply_intent_model(parsed, intent_model).intent.value == p["intent"])
        if parsed.intent.value != p["intent"]:
            errors.append({"question": p["question"], "gold": p["intent"], "rules": parsed.intent.value})
    n = len(pairs)
    return {"n": n, "rule_accuracy": ok / n if n else None,
            "rules_plus_model_accuracy": (ok_model / n) if (n and intent_model is not None) else None,
            "errors": errors[:30]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--light", action="store_true", help="hashing embeddings + HSV only; no downloads")
    ap.add_argument("--paraphrases", default=None, help="CSV with columns question,intent")
    ap.add_argument("--out", default=None, help="write JSON here")
    a = ap.parse_args()

    data = load_dataset(a.data)
    scen = data if a.split == "all" else split_dataset(data, a.seed)[a.split]
    comp = build_components(load_config(), light=a.light)
    result: Dict[str, Any] = {"split": a.split, "n_scenarios": len(scen), "visual_status": comp.visual.status()}
    result["nlp_text_extraction"] = evaluate_text_extraction(scen)
    result["cv_color"] = evaluate_visual(scen, comp.visual)
    pairs = [{"question": q["question"], "intent": q["intent"]} for sc in scen for q in sc["queries"]]
    from ..agent.intent_model import load_intent_model
    model = load_intent_model()
    result["intent_synthetic_questions"] = evaluate_intents(pairs, model)
    if a.paraphrases:
        with open(a.paraphrases, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("question") and r.get("intent")]
        result["intent_paraphrases"] = evaluate_intents(rows, model)
    print(json.dumps(result, indent=2))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
