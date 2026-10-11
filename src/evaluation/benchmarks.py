"""Benchmark runner: replay synthetic scenarios through any memory system and score them.

A "system" is anything with reset(), remember(text, image, timestamp, session_id) and
ask(question, reference_time) -> Answer (MemoryAgent and the baselines all qualify).
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple

from ..data.synthetic import render_session_image
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


def run_system(system: Any, scenarios: List[Dict[str, Any]], verbose: bool = False) -> Dict[str, Any]:
    queries: List[Dict[str, Any]] = []
    sessions: List[Dict[str, Any]] = []
    t0 = time.time()
    for n, sc in enumerate(scenarios, 1):
        system.reset()
        ref = max(s["timestamp"] for s in sc["sessions"])
        for s in sc["sessions"]:
            res = system.remember(text=s["text"] or "", image=render_session_image(s),
                                  timestamp=s["timestamp"], session_id=s["session_id"])
            sessions.append({"scenario_id": sc["scenario_id"], "session_id": s["session_id"],
                             "kind": s["gt"]["kind"], "gold": s["gt"]["action"],
                             "predicted": session_action(res)})
        for q in sc["queries"]:
            ans = system.ask(q["question"], reference_time=ref)
            queries.append({"scenario_id": sc["scenario_id"], **score_query(q, ans)})
        if verbose and n % 25 == 0:
            print(f"  {n}/{len(scenarios)} scenarios")
    out: Dict[str, Any] = {
        "system": getattr(system, "name", system.__class__.__name__),
        "n_scenarios": len(scenarios),
        "seconds": round(time.time() - t0, 1),
        "queries": summarize_queries(queries),
        "raw_queries": queries,
        "raw_sessions": sessions,
    }
    scored = [(s["gold"], s["predicted"]) for s in sessions if s["predicted"] is not None]
    out["actions"] = action_metrics(scored) if scored else None
    return out
