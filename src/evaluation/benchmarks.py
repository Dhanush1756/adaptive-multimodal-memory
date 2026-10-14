"""Benchmark runner: replay synthetic scenarios through any memory system and score them.

A "system" is anything with reset(), remember(text, image, timestamp, session_id) and
ask(question, reference_time) -> Answer (MemoryAgent and the baselines all qualify).
"""
from __future__ import annotations

import random
import time
from collections import defaultdict
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from ..data.synthetic import render_session_image
from ..cv.detection import Detection
from .metrics import action_metrics, score_query, summarize_queries


def split_dataset(data: List[Dict[str, Any]], seed: int = 0,
                  fractions: Tuple[float, float, float] = (0.7, 0.15, 0.15)) -> Dict[str, List[Dict[str, Any]]]:
    """Deterministic scenario-level split (never split inside a scenario: that would leak)."""
    idx = list(range(len(data)))
    random.Random(seed).shuffle(idx)
    n_tr = int(fractions[0] * len(data))
    n_dev = int(fractions[1] * len(data))
    parts = {"train": idx[:n_tr], "dev": idx[n_tr:n_tr + n_dev], "test": idx[n_tr + n_dev:]}
    return {k: [data[i] for i in sorted(v)] for k, v in parts.items()}


def session_action(result: Any) -> Optional[str]:
    """Memory action of a session. Unlinked agents emit two decisions: use the first non-IGNORE."""
    decisions = getattr(result, "decisions", None)
    if not decisions:
        return None
    for d in decisions:
        if d.action.value != "IGNORE":
            return d.action.value
    return "IGNORE"


def session_visual_association(result: Any) -> Optional[str]:
    candidates = getattr(result, "candidates", None) or []
    visuals = [c.visual for c in candidates if getattr(c, "visual", None) is not None]
    if not visuals:
        return None
    return "verified" if any(v.supports_state for v in visuals) else "contextual"


def _detector(system: Any):
    """Find the shared detector through an optional evaluation wrapper."""
    obj = system
    for _ in range(3):
        comp = getattr(obj, "comp", None)
        if comp is not None:
            return getattr(getattr(comp, "visual", None), "detector", None)
        obj = getattr(obj, "inner", None)
        if obj is None:
            break
    return None


def _controlled_detections(specs: List[Dict[str, Any]]):
    return [Detection(s.get("label", s.get("entity", "object")), s.get("entity"),
                      s["bbox"], float(s.get("confidence", .95)), source="phase6_controlled")
            for s in specs]


def _quantiles(values: List[float]):
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    return [round(values[int(.025 * n)], 4), round(values[int(.975 * n) - 1], 4)]


def _action_intervals(sessions: List[Dict[str, Any]], seed: int = 20261013, iters: int = 500):
    by = defaultdict(list)
    for s in sessions:
        if s["predicted"] not in (None, "ERROR", "SKIPPED"):
            by[s["scenario_id"]].append((s["gold"], s["predicted"]))
    groups = list(by.values())
    if len(groups) < 5:
        return None, None
    rng = random.Random(seed)
    accuracies, conflict_f1s = [], []
    for _ in range(iters):
        pairs = [p for _ in groups for p in rng.choice(groups)]
        metrics = action_metrics(pairs)
        accuracies.append(metrics["state_update_accuracy"])
        f1 = metrics["conflict_detection"]["f1"]
        if f1 is not None:
            conflict_f1s.append(f1)
    return _quantiles(accuracies), _quantiles(conflict_f1s)


def _visual_intervals(sessions: List[Dict[str, Any]], seed: int = 20261013, iters: int = 500):
    labelled = [s for s in sessions if s.get("visual_gold") in {"verified", "rejected"}]
    by = defaultdict(list)
    for s in labelled:
        by[s["scenario_id"]].append(s)
    groups = list(by.values())
    if len(groups) < 5:
        return None, None
    rng = random.Random(seed)
    precisions, fars = [], []
    for _ in range(iters):
        sample = [s for _ in groups for s in rng.choice(groups)]
        tp = sum(s["visual_gold"] == "verified" and s["visual_predicted"] == "verified" for s in sample)
        fp = sum(s["visual_gold"] == "rejected" and s["visual_predicted"] == "verified" for s in sample)
        rejected = sum(s["visual_gold"] == "rejected" for s in sample)
        if tp + fp:
            precisions.append(tp / (tp + fp))
        if rejected:
            fars.append(fp / rejected)
    return _quantiles(precisions), _quantiles(fars)


def run_system(system: Any, scenarios: List[Dict[str, Any]], verbose: bool = False) -> Dict[str, Any]:
    queries: List[Dict[str, Any]] = []
    sessions: List[Dict[str, Any]] = []
    t0 = time.time()
    for n, sc in enumerate(scenarios, 1):
        system.reset()
        dated = [s["timestamp"] for s in sc["sessions"] if s.get("timestamp")]
        ref = max(dated) if dated else None
        for s in sc["sessions"]:
            if s.get("skip_reason"):
                sessions.append({"scenario_id": sc["scenario_id"], "family": sc.get("family"), "session_id": s["session_id"],
                                 "kind": s["gt"]["kind"], "gold": s["gt"]["action"],
                                 "predicted": "SKIPPED", "error": None,
                                 "skip_reason": s["skip_reason"],
                                 "visual_gold": s["gt"].get("visual_association"),
                                 "visual_predicted": None})
                continue
            image = b"not-an-image" if s.get("image_case") == "decode_failure" else render_session_image(s)
            error = None
            detector = _detector(system)
            original_detect = getattr(detector, "detect", None)
            if detector is not None and "detections" in s:
                controlled = _controlled_detections(s["detections"])
                detector.detect = lambda image, values=controlled: values
            try:
                res = system.remember(text=s["text"] or "", image=image,
                                      timestamp=s.get("timestamp"), session_id=s["session_id"])
                predicted = session_action(res)
                visual_predicted = session_visual_association(res)
            except Exception as exc:
                predicted, visual_predicted, error = "ERROR", None, exc.__class__.__name__
            finally:
                if detector is not None and original_detect is not None:
                    detector.detect = original_detect
            sessions.append({"scenario_id": sc["scenario_id"], "family": sc.get("family"), "session_id": s["session_id"],
                             "kind": s["gt"]["kind"], "gold": s["gt"]["action"],
                             "predicted": predicted, "error": error,
                             "skip_reason": None,
                             "visual_gold": s["gt"].get("visual_association"),
                             "visual_predicted": visual_predicted})
        for q in sc["queries"]:
            error = None
            try:
                ans = system.ask(q["question"], reference_time=ref)
            except Exception as exc:
                error = exc.__class__.__name__
                ans = SimpleNamespace(found=False, value=None, evidence=[], states=[],
                                      supporting_state_ids=[], supporting_evidence_ids=[],
                                      status="abstained", text="", intent=None, note="runtime error")
            queries.append({"scenario_id": sc["scenario_id"], "family": sc.get("family"),
                            **score_query(q, ans), "error": error})
        if verbose and n % 25 == 0:
            print(f"  {n}/{len(scenarios)} scenarios")
    out: Dict[str, Any] = {
        "system": getattr(system, "name", system.__class__.__name__),
        "n_scenarios": len(scenarios),
        "seconds": round(time.time() - t0, 1),
        "queries": summarize_queries(queries),
        "raw_queries": queries,
        "raw_sessions": sessions,
        "n_session_errors": sum(1 for s in sessions if s.get("error")),
        "n_query_errors": sum(1 for q in queries if q.get("error")),
        "n_skipped_sessions": sum(1 for s in sessions if s.get("skip_reason")),
    }
    # A runtime ERROR is reported separately; it is not a lifecycle decision.
    scored = [(s["gold"], s["predicted"]) for s in sessions
              if s["predicted"] not in (None, "ERROR", "SKIPPED")]
    out["actions"] = action_metrics(scored) if scored else None
    if out["actions"] is not None:
        action_ci, conflict_ci = _action_intervals(sessions)
        out["actions"]["state_update_accuracy_ci95"] = action_ci
        out["actions"]["conflict_detection"]["f1_ci95"] = conflict_ci
    labelled_visual = [s for s in sessions if s.get("visual_gold") in {"verified", "rejected"}]
    tp = sum(s["visual_gold"] == "verified" and s["visual_predicted"] == "verified" for s in labelled_visual)
    fp = sum(s["visual_gold"] == "rejected" and s["visual_predicted"] == "verified" for s in labelled_visual)
    fn = sum(s["visual_gold"] == "verified" and s["visual_predicted"] != "verified" for s in labelled_visual)
    tn = sum(s["visual_gold"] == "rejected" and s["visual_predicted"] != "verified" for s in labelled_visual)
    rejected = sum(s["visual_gold"] == "rejected" for s in labelled_visual)
    visual_precision_ci, visual_far_ci = _visual_intervals(sessions)
    out["visual_association"] = {
        "precision": tp / (tp + fp) if tp + fp else None,
        "false_association_rate": fp / rejected if rejected else None,
        "accepted": tp + fp, "labelled": len(labelled_visual), "rejected": rejected,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision_ci95": visual_precision_ci,
        "false_association_rate_ci95": visual_far_ci,
    }
    return out
