"""Evaluation metrics (brief sections 36-37). Pure functions, no model dependencies.

Query-level metrics are grouped by the `kind` field of the synthetic benchmark:

  current_state_accuracy      CSA   kinds: current, bool_current
  historical_state_accuracy   HSA   kinds: original, previous, previous_ref, after, as_of,
                                          bool_original, bool_previous_ref
  temporal_accuracy                 kinds: change, when_last, when_value
  temporal_ordering_accuracy        kinds: history (full ordered list of states must match)
  evidence_accuracy                 kinds: evidence (answer value correct)
  evidence_recall                   mean over ALL questions that have gold evidence sessions:
                                    |gold ∩ cited| / |gold|  (recall only; precision is not measured)

Confidence intervals are cluster-bootstrap CIs over *scenarios* (questions of one scenario are
correlated, so resampling single questions would give intervals that are too narrow).
"""
from __future__ import annotations

import random
import re
import math
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..memory.conflict import normalize_value

_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}")

GROUPS: Dict[str, set] = {
    "current_state_accuracy": {"current", "bool_current"},
    "historical_state_accuracy": {
        "original", "previous", "previous_ref", "after", "as_of", "bool_original", "bool_previous_ref"},
    "temporal_accuracy": {"change", "when_last", "when_value"},
    "temporal_ordering_accuracy": {"history"},
    "evidence_accuracy": {"evidence"},
    "initial_state_accuracy": {"initial"},
    "entity_identity_accuracy": {"entity_identity"},
}


# ----------------------------------------------------------------------------- scoring
def canon(v: Any) -> Any:
    """Canonical form so 'Grey', 'gray', ['red','blue'], 'red->blue', '2026-10-10T..' compare sanely."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return tuple(canon(x) for x in v)
    s = str(v).strip().lower()
    if s in ("yes", "no"):
        return s
    if _DATE_RX.match(s):
        return s[:10]
    if "->" in s:
        return tuple(normalize_value(p.strip()) for p in s.split("->"))
    return normalize_value(s)


def cited_sessions(answer: Any) -> set:
    out = set()
    for e in getattr(answer, "evidence", None) or []:
        if e.get("role") == "conflicting":
            continue
        if not e.get("supports_state", True):
            continue
        if e.get("session_id"):
            out.add(e["session_id"])
    return out


def score_query(q: Dict[str, Any], answer: Any) -> Dict[str, Any]:
    found = bool(getattr(answer, "found", False))
    pred = getattr(answer, "value", None) if found else None
    answerable = bool(q.get("answerable", True))
    correct = (found and canon(pred) == canon(q["answer"])) if answerable else not found
    gold_ev = set(q.get("evidence_sessions") or [])
    cited = cited_sessions(answer)
    recall = (len(gold_ev & cited) / len(gold_ev)) if gold_ev else None
    precision = ((len(gold_ev & cited) / len(cited)) if cited else 0.0) if gold_ev else None
    schema_valid = (
        getattr(answer, "status", None) in {"answered", "uncertain", "abstained"}
        and isinstance(getattr(answer, "text", None), str)
        and isinstance(getattr(answer, "evidence", None), list)
        and isinstance(getattr(answer, "states", None), list)
        and isinstance(getattr(answer, "supporting_state_ids", None), list)
        and isinstance(getattr(answer, "supporting_evidence_ids", None), list)
    )
    return {
        "kind": q["kind"], "intent": q["intent"], "question": q["question"], "gold": q["answer"],
        "predicted": pred, "found": found, "answerable": answerable,
        "correct": bool(correct), "evidence_recall": recall,
        "evidence_precision": precision,
        # Operational unsupported-answer measure: a returned value that does not
        # match the labelled answer. This is not a claim about open-ended LLM
        # hallucination, because default answers are deterministic templates.
        "unsupported_answer": bool(found and (not answerable or not correct)),
        "answer_schema_valid": schema_valid,
        "predicted_intent": getattr(answer, "intent", None),
        "answer_status": getattr(answer, "status", None),
        "note": getattr(answer, "note", ""),
    }


# --------------------------------------------------------------------------- aggregation
def _acc(flags: Sequence[float]) -> Optional[float]:
    return (sum(flags) / len(flags)) if flags else None


def _count_metric(flags: Sequence[float], ci95=None) -> Dict[str, Any]:
    correct = int(sum(flags))
    n = len(flags)
    return {"value": _acc(flags), "correct": correct, "incorrect": n - correct,
            "n": n, "denominator": n, "ci95": ci95}


def cluster_ci(results: List[Dict[str, Any]], kinds: Iterable[str], iters: int = 500, seed: int = 0):
    kinds = set(kinds)
    by: Dict[str, List[float]] = defaultdict(list)
    for r in results:
        if r["kind"] in kinds:
            by[r["scenario_id"]].append(1.0 if r["correct"] else 0.0)
    groups = list(by.values())
    if len(groups) < 5:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(iters):
        sample = [rng.choice(groups) for _ in groups]
        n = sum(len(g) for g in sample)
        vals.append(sum(sum(g) for g in sample) / n)
    vals.sort()
    return [round(vals[int(0.025 * iters)], 4), round(vals[int(0.975 * iters) - 1], 4)]


def cluster_mean_ci(results: List[Dict[str, Any]], field: str, iters: int = 500,
                    seed: int = 20261013):
    by: Dict[str, List[float]] = defaultdict(list)
    for r in results:
        value = r.get(field)
        if value is not None:
            by[r["scenario_id"]].append(float(value))
    groups = list(by.values())
    if len(groups) < 5:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(iters):
        sample = [rng.choice(groups) for _ in groups]
        flat = [v for group in sample for v in group]
        vals.append(sum(flat) / len(flat))
    vals.sort()
    return [round(vals[int(.025 * iters)], 4), round(vals[int(.975 * iters) - 1], 4)]


def summarize_queries(results: List[Dict[str, Any]], with_ci: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n_queries": len(results)}
    for name, kinds in GROUPS.items():
        flags = [1.0 if r["correct"] else 0.0 for r in results if r["kind"] in kinds]
        out[name] = _count_metric(flags, cluster_ci(results, kinds) if with_ci else None)
    recalls = [r["evidence_recall"] for r in results if r.get("evidence_recall") is not None]
    out["evidence_recall"] = {"value": _acc(recalls), "n": len(recalls), "denominator": len(recalls),
                              "ci95": cluster_mean_ci(results, "evidence_recall") if with_ci else None}
    precisions = [r["evidence_precision"] for r in results if r.get("evidence_precision") is not None]
    out["evidence_precision"] = {"value": _acc(precisions), "n": len(precisions),
                                 "denominator": len(precisions),
                                 "ci95": cluster_mean_ci(results, "evidence_precision") if with_ci else None}
    out["overall_accuracy"] = _count_metric(
        [1.0 if r["correct"] else 0.0 for r in results],
        cluster_mean_ci([{**r, "_metric": 1.0 if r["correct"] else 0.0} for r in results], "_metric") if with_ci else None)
    answered_flags = [1.0 if r["found"] else 0.0 for r in results]
    out["answered_rate"] = _count_metric(answered_flags, cluster_mean_ci(
        [{**r, "_metric": 1.0 if r["found"] else 0.0} for r in results], "_metric") if with_ci else None)
    out["abstention_rate"] = _count_metric([1.0 if not r["found"] else 0.0 for r in results], cluster_mean_ci(
        [{**r, "_metric": 1.0 if not r["found"] else 0.0} for r in results], "_metric") if with_ci else None)
    abstained = [r for r in results if not r["found"]]
    out["abstention_correctness"] = _count_metric(
        [1.0 if r["correct"] else 0.0 for r in abstained], cluster_mean_ci(
            [{**r, "_metric": 1.0 if r["correct"] else 0.0} for r in abstained], "_metric") if with_ci else None)
    answered = [r for r in results if r["found"]]
    out["unsupported_answer_rate"] = {
        "value": _acc([1.0 if r["unsupported_answer"] else 0.0 for r in answered]),
        "unsupported": sum(1 for r in answered if r["unsupported_answer"]),
        "n": len(answered), "denominator": len(answered), "ci95": cluster_mean_ci(
            [{**r, "_metric": 1.0 if r["unsupported_answer"] else 0.0} for r in answered], "_metric") if with_ci else None
    }
    out["answer_schema_validity"] = _count_metric(
        [1.0 if r.get("answer_schema_valid") else 0.0 for r in results], cluster_mean_ci(
            [{**r, "_metric": 1.0 if r.get("answer_schema_valid") else 0.0} for r in results], "_metric") if with_ci else None)
    by_kind: Dict[str, List[float]] = defaultdict(list)
    for r in results:
        by_kind[r["kind"]].append(1.0 if r["correct"] else 0.0)
    out["by_kind"] = {k: _count_metric(v) for k, v in sorted(by_kind.items())}
    return out


def paired_comparison(candidate: Dict[str, Any], proposed: Dict[str, Any],
                      seed: int = 20261013, iters: int = 2000) -> Dict[str, Any]:
    """Paired accuracy comparison on identical query keys.

    McNemar's exact p-value uses discordant query pairs. The confidence interval
    bootstraps whole scenarios so correlated questions stay together.
    """
    key = lambda r: (r["scenario_id"], r["question"])
    left = {key(r): r for r in candidate["raw_queries"]}
    right = {key(r): r for r in proposed["raw_queries"]}
    keys = sorted(set(left) & set(right))
    pairs = [(bool(left[k]["correct"]), bool(right[k]["correct"])) for k in keys]
    cand_only = sum(a and not b for a, b in pairs)
    proposed_only = sum(b and not a for a, b in pairs)
    discordant = cand_only + proposed_only
    if discordant:
        tail = sum(math.comb(discordant, i) for i in range(0, min(cand_only, proposed_only) + 1)) / (2 ** discordant)
        p_value = min(1.0, 2 * tail)
    else:
        p_value = 1.0
    by_scenario: Dict[str, List[Tuple[bool, bool]]] = defaultdict(list)
    for k, pair in zip(keys, pairs):
        by_scenario[k[0]].append(pair)
    groups = list(by_scenario.values())
    ci = None
    if len(groups) >= 5:
        rng = random.Random(seed)
        diffs = []
        for _ in range(iters):
            sample = [rng.choice(groups) for _ in groups]
            flat = [p for group in sample for p in group]
            diffs.append(sum(b - a for a, b in flat) / len(flat))
        diffs.sort()
        ci = [round(diffs[int(.025 * iters)], 4), round(diffs[int(.975 * iters) - 1], 4)]
    return {
        "candidate": candidate["system"], "proposed": proposed["system"], "n": len(keys),
        "candidate_accuracy": _acc([a for a, _ in pairs]),
        "proposed_accuracy": _acc([b for _, b in pairs]),
        "difference_proposed_minus_candidate": _acc([b - a for a, b in pairs]),
        "candidate_only_correct": cand_only, "proposed_only_correct": proposed_only,
        "discordant": discordant, "mcnemar_exact_two_sided_p": p_value,
        "scenario_bootstrap_difference_ci95": ci,
        "bootstrap_seed": seed, "bootstrap_iterations": iters,
    }


# ------------------------------------------------------------------- memory-action metrics
def prf(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * r / (p + r)) if (p is not None and r is not None and (p + r) > 0) else (0.0 if (p is not None or r is not None) else None)
    return {"precision": p, "recall": r, "f1": f1, "support": tp + fn,
            "tp": tp, "fp": fp, "fn": fn}


def action_metrics(pairs: Sequence[Tuple[str, Optional[str]]]) -> Dict[str, Any]:
    """pairs = [(gold_action, predicted_action_or_None)]. State Update Accuracy + per-class PRF."""
    if not pairs:
        return {"state_update_accuracy": None, "n": 0}
    gold = [g for g, _ in pairs]
    pred = [p if p is not None else "NONE" for _, p in pairs]
    labels = sorted(set(gold) | set(pred))
    per: Dict[str, Any] = {}
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        per[lab] = prf(tp, fp, fn)
    conf: Dict[str, Counter] = defaultdict(Counter)
    for g, p in zip(gold, pred):
        conf[g][p] += 1
    correct = sum(1 for g, p in zip(gold, pred) if g == p)
    return {
        "state_update_accuracy": correct / len(gold), "correct": correct, "incorrect": len(gold) - correct,
        "n": len(gold),
        "per_action": per,
        "conflict_detection": per.get("CONTRADICTORY", prf(0, 0, 0)),
        "confusion": {g: dict(c) for g, c in conf.items()},
    }


def fmt(x: Optional[float], digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"
