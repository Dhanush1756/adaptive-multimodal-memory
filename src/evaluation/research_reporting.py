"""Reproducibility metadata, paired comparisons, and deterministic error reports."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List

from .metrics import paired_comparison


def sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], check=True, capture_output=True,
                              text=True).stdout.strip() or "clean"
    except Exception:
        return "unavailable"


def manifest(data_path: str, cfg: Dict[str, Any], args: Any, components: Dict[str, Any],
             scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    encoded = json.dumps(cfg, sort_keys=True, default=str).encode("utf-8")
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "-m", "src.evaluation.ablations", *sys.argv[1:]],
        "python": sys.version, "platform": platform.platform(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_status": _git("status", "--short"),
        "dataset_path": str(Path(data_path).as_posix()), "dataset_sha256": sha256(data_path),
        "configuration_sha256": hashlib.sha256(encoded).hexdigest(), "configuration": cfg,
        "split": args.split, "seed": args.seed, "light": bool(args.light),
        "components": components, "systems": args.systems,
        "n_scenarios": len(scenarios),
        "n_sessions": sum(len(s["sessions"]) for s in scenarios),
        "n_queries": sum(len(s["queries"]) for s in scenarios),
        "families": dict(Counter(s.get("family", "unspecified") for s in scenarios)),
    }


def comparisons(results: List[Dict[str, Any]], proposed_name: str = "E_proposed") -> List[Dict[str, Any]]:
    proposed = next((r for r in results if r["system"] == proposed_name), None)
    if proposed is None:
        return []
    return [paired_comparison(r, proposed) for r in results if r is not proposed]


def _query_category(q: Dict[str, Any]) -> str:
    if q.get("error"):
        return "evaluation_runtime"
    if q.get("predicted_intent") and q.get("predicted_intent") != q.get("intent"):
        return "temporal_interpretation"
    if q.get("kind") == "entity_identity":
        return "entity_identity_resolution"
    if q.get("family") == "long_sequence" and not q.get("correct"):
        return "nlp_extraction"
    if q.get("kind") == "evidence" or q.get("evidence_precision") not in (None, 1.0):
        return "evidence_retrieval"
    if q.get("intent") in {"ORIGINAL", "PREVIOUS", "AS_OF", "HISTORY", "AFTER", "WHEN", "CHANGE"}:
        return "temporal_interpretation"
    if not q.get("found") and q.get("answerable"):
        return "nlp_extraction_or_memory"
    return "answer_generation"


def _session_category(s: Dict[str, Any]) -> str:
    if s.get("error"):
        return "evaluation_runtime"
    kind = s.get("kind", "")
    if "conflict" in kind:
        return "conflict_resolution"
    if "visual" in kind or "image" in kind or "cv" in kind:
        return "visual_evidence_association"
    if kind in {"late_arrival", "historical"}:
        return "temporal_interpretation"
    if "identity" in kind or "instance" in kind:
        return "entity_identity_resolution"
    return "nlp_extraction_or_lifecycle"


def error_analysis(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for result in results:
        query_issues = []
        for q in result["raw_queries"]:
            citation_issue = q.get("evidence_precision") not in (None, 1.0) or q.get("evidence_recall") not in (None, 1.0)
            intent_issue = q.get("predicted_intent") and q.get("predicted_intent") != q.get("intent")
            if not q["correct"] or citation_issue or intent_issue or q.get("error") or not q.get("answer_schema_valid"):
                query_issues.append({"category": _query_category(q), **q})
        session_issues = [{"category": _session_category(s), **s} for s in result["raw_sessions"]
                          if s.get("predicted") != s.get("gold") or s.get("error") or s.get("skip_reason")]
        counts = Counter(x["category"] for x in query_issues + session_issues)
        out[result["system"]] = {
            "query_issues": query_issues, "session_issues": session_issues,
            "category_counts": dict(sorted(counts.items())),
        }
    return out


def error_markdown(analysis: Dict[str, Any]) -> str:
    lines = ["# Phase 6 error analysis", "",
             "Every incorrect output, runtime failure, invalid schema, and incomplete citation is listed in the JSON artifact.", "",
             "| System | Query issues | Session issues | Categories |", "|---|---:|---:|---|"]
    for name, item in analysis.items():
        cats = ", ".join(f"{k}: {v}" for k, v in item["category_counts"].items()) or "none"
        lines.append(f"| {name} | {len(item['query_issues'])} | {len(item['session_issues'])} | {cats} |")
    lines.extend(["", "Categories are deterministic first-pass labels for review; they do not replace individual inspection."])
    return "\n".join(lines) + "\n"


def research_summary(results: List[Dict[str, Any]], paired: List[Dict[str, Any]]) -> str:
    lines = ["# Phase 6 comparison summary", "",
             "Counts are shown as correct/denominator. Coverage is answered/all questions.", "",
             "| System | Overall | Current | Historical | Initial | Identity | Evidence P/R | Coverage | Abstention correct | Unsupported | Lifecycle | Conflict F1 | Visual P/FAR | Schema | Errors (session/query) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        q, a, v = r["queries"], r.get("actions") or {}, r.get("visual_association") or {}
        def count(name):
            m = q[name]
            return f"{m.get('correct', 0)}/{m.get('n', 0)}"
        def number(value):
            return "n/a" if value is None else f"{value:.3f}"
        evp, evr = q["evidence_precision"], q["evidence_recall"]
        cov, abst = q["answered_rate"], q["abstention_correctness"]
        uns = q["unsupported_answer_rate"]
        conflict = (a.get("conflict_detection") or {}).get("f1")
        lines.append(
            f"| {r['system']} | {count('overall_accuracy')} | {count('current_state_accuracy')} | "
            f"{count('historical_state_accuracy')} | {count('initial_state_accuracy')} | "
            f"{count('entity_identity_accuracy')} | {number(evp['value'])}/"
            f"{number(evr['value'])} | {cov.get('correct', 0)}/{cov.get('n', 0)} | "
            f"{abst.get('correct', 0)}/{abst.get('n', 0)} | {uns.get('unsupported', 0)}/{uns.get('n', 0)} | "
            f"{a.get('state_update_accuracy', 'n/a')} | {conflict if conflict is not None else 'n/a'} | "
            f"{v.get('precision') if v.get('precision') is not None else 'n/a'}/{v.get('false_association_rate') if v.get('false_association_rate') is not None else 'n/a'} | "
            f"{count('answer_schema_validity')} | {r.get('n_session_errors', 0)}/{r.get('n_query_errors', 0)} |")
    lines.extend(["", "## Paired overall-accuracy comparisons against E_proposed", "",
                  "| Candidate | n | Candidate | Proposed | Difference | Discordant (candidate/proposed only) | McNemar exact p | Cluster-bootstrap CI |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for p in paired:
        lines.append(f"| {p['candidate']} | {p['n']} | {p['candidate_accuracy']:.3f} | "
                     f"{p['proposed_accuracy']:.3f} | {p['difference_proposed_minus_candidate']:.3f} | "
                     f"{p['candidate_only_correct']}/{p['proposed_only_correct']} | "
                     f"{p['mcnemar_exact_two_sided_p']:.6f} | {p['scenario_bootstrap_difference_ci95']} |")
    lines.extend(["", "McNemar p-values are descriptive paired tests. Multiple systems and correlated metrics are compared; no multiplicity-adjusted significance claim is made."])
    return "\n".join(lines) + "\n"
