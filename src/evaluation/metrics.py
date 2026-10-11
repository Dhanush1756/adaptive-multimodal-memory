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
        if e.get("session_id"):
            out.add(e["session_id"])
    return out


def score_query(q: Dict[str, Any], answer: Any) -> Dict[str, Any]:
    found = bool(getattr(answer, "found", False))
    pred = getattr(answer, "value", None) if found else None
    correct = found and canon(pred) == canon(q["answer"])
    gold_ev = set(q.get("evidence_sessions") or [])
    recall = (len(gold_ev & cited_sessions(answer)) / len(gold_ev)) if gold_ev else None
    return {
        "kind": q["kind"], "intent": q["intent"], "question": q["question"], "gold": q["answer"],
        "predicted": pred, "found": found, "correct": bool(correct), "evidence_recall": recall,
    }


# --------------------------------------------------------------------------- aggregation
def _acc(flags: Sequence[float]) -> Optional[float]:
    return (sum(flags) / len(flags)) if flags else None


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


def summarize_queries(results: List[Dict[str, Any]], with_ci: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n_queries": len(results)}
    for name, kinds in GROUPS.items():
        flags = [1.0 if r["correct"] else 0.0 for r in results if r["kind"] in kinds]
        out[name] = {"value": _acc(flags), "n": len(flags),
                     "ci95": cluster_ci(results, kinds) if with_ci else None}
    recalls = [r["evidence_recall"] for r in results if r.get("evidence_recall") is not None]
    out["evidence_recall"] = {"value": _acc(recalls), "n": len(recalls)}
    out["overall_accuracy"] = {"value": _acc([1.0 if r["correct"] else 0.0 for r in results]), "n": len(results)}
    out["answered_rate"] = {"value": _acc([1.0 if r["found"] else 0.0 for r in results]), "n": len(results)}
    by_kind: Dict[str, List[float]] = defaultdict(list)
    for r in results:
        by_kind[r["kind"]].append(1.0 if r["correct"] else 0.0)
    out["by_kind"] = {k: {"value": _acc(v), "n": len(v)} for k, v in sorted(by_kind.items())}
    return out


# ------------------------------------------------------------------- memory-action metrics
def prf(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * r / (p + r)) if (p is not None and r is not None and (p + r) > 0) else (0.0 if (p is not None or r is not None) else None)
    return {"precision": p, "recall": r, "f1": f1, "support": tp + fn}


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
    return {
        "state_update_accuracy": sum(1 for g, p in zip(gold, pred) if g == p) / len(gold),
        "n": len(gold),
        "per_action": per,
        "conflict_detection": per.get("CONTRADICTORY", prf(0, 0, 0)),
        "confusion": {g: dict(c) for g, c in conf.items()},
    }


def fmt(x: Optional[float], digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"
