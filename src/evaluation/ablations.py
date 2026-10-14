"""Ablation study (brief sections 38-39).

    python -m src.evaluation.ablations --data data/synthetic --split test --out reports/results
    python -m src.evaluation.ablations --light --n 40          # quick smoke run, no model downloads

Systems compared (same extractors, same pretrained models; only the memory mechanism differs):
  A  naive text memory                          text only, top-1 retrieval
  B  naive multimodal memory                    text + image, top-1 retrieval
  C  append-only temporal memory                time-ordered observations, no MERGE / conflicts / linking
  D  proposed, no evidence linking              adaptive states, but text and image as independent streams
  E  proposed                                   adaptive states + evidence linking + conflict handling
  E-text / E-image                              proposed system fed only one modality (what is lost)

The table is generated from measured results only. Nothing is hard-coded.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List

from ..agent.reasoning import MemoryAgent, build_components
from ..config import load_config
from ..data.synthetic import load_dataset
from .baselines import (AppendOnlyTemporalMemory, LatestValueMemory, NaiveMultimodalMemory,
                        NaiveTextMemory, NoPersistentMemory)
from .benchmarks import run_system, split_dataset
from .metrics import fmt
from .research_reporting import comparisons, error_analysis, error_markdown, manifest, research_summary


class ModalityView:
    """Feeds only one modality of every session to an inner system."""

    def __init__(self, inner: Any, text: bool, image: bool, name: str):
        self.inner, self.use_text, self.use_image, self.name = inner, text, image, name

    def reset(self) -> None:
        self.inner.reset()

    def remember(self, text: str = "", image: Any = None, timestamp: Any = None, session_id=None):
        return self.inner.remember(text if self.use_text else "", image if self.use_image else None,
                                   timestamp, session_id)

    def ask(self, question: str, reference_time: Any = None):
        return self.inner.ask(question, reference_time)


class NoProvenanceView:
    """Keep the answer while removing state-specific citations."""
    name = "E_no_provenance"

    def __init__(self, inner: Any):
        self.inner = inner

    def reset(self):
        return self.inner.reset()

    def remember(self, *args, **kwargs):
        return self.inner.remember(*args, **kwargs)

    def ask(self, *args, **kwargs):
        answer = self.inner.ask(*args, **kwargs)
        answer.evidence = []
        return answer


def build_systems(comp: Any, cfg: Dict[str, Any]) -> Dict[str, Callable[[], Any]]:
    def agent(link: bool, name: str):
        # Benchmarks reset between scenarios and must never open the configured user database.
        a = MemoryAgent(cfg, db_path=":memory:", components=comp, link_evidence=link, use_intent_model=False)
        a.name = name
        return a

    def named(obj, name):
        obj.name = name
        return obj

    no_conflict_cfg = deepcopy(cfg)
    no_conflict_cfg.setdefault("memory", {})["conflict_text_conf"] = 1.1
    no_conflict_cfg.setdefault("memory", {})["conflict_visual_conf"] = 1.1

    def no_conflict_agent():
        a = MemoryAgent(no_conflict_cfg, db_path=":memory:", components=comp,
                        link_evidence=True, use_intent_model=False)
        a.name = "E_no_text_image_conflict"
        return a

    return {
        "N_no_memory": lambda: named(NoPersistentMemory(cfg, components=comp), "N_no_memory"),
        "L_latest_value": lambda: named(LatestValueMemory(cfg, components=comp), "L_latest_value"),
        "A_naive_text": lambda: named(NaiveTextMemory(cfg, components=comp), "A_naive_text"),
        "B_naive_multimodal": lambda: named(NaiveMultimodalMemory(cfg, components=comp), "B_naive_multimodal"),
        "C_append_only_temporal": lambda: named(AppendOnlyTemporalMemory(cfg, components=comp), "C_append_only_temporal"),
        "D_proposed_no_linking": lambda: agent(False, "D_proposed_no_linking"),
        "E_proposed": lambda: agent(True, "E_proposed"),
        "E_no_provenance": lambda: NoProvenanceView(agent(True, "E_no_provenance_inner")),
        "E_no_visual_linking": lambda: agent(False, "E_no_visual_linking"),
        "E_no_text_image_conflict": no_conflict_agent,
        "E_text_input_only": lambda: ModalityView(agent(True, "x"), True, False, "E_text_input_only"),
        "E_image_input_only": lambda: ModalityView(agent(True, "x"), False, True, "E_image_input_only"),
    }


FLAGS = {  # (text, image, temporal memory, evidence linking) per the brief's table
    "N_no_memory": ("-", "-", "-", "-"),
    "L_latest_value": ("yes", "yes", "latest only", "limited"),
    "E_no_provenance": ("yes", "yes", "adaptive", "citations removed"),
    "E_no_visual_linking": ("yes", "yes", "adaptive", "no cross-modal link"),
    "E_no_text_image_conflict": ("yes", "yes", "adaptive", "conflict gate removed"),
    "A_naive_text": ("✓", "✗", "✗", "✗"),
    "B_naive_multimodal": ("✓", "✓", "✗", "✗"),
    "C_append_only_temporal": ("✓", "✓", "✓ (append-only)", "✗"),
    "D_proposed_no_linking": ("✓", "✓", "✓ (adaptive)", "✗"),
    "E_proposed": ("✓", "✓", "✓ (adaptive)", "✓"),
    "E_text_input_only": ("✓", "✗", "✓ (adaptive)", "–"),
    "E_image_input_only": ("✗", "✓", "✓ (adaptive)", "–"),
}

# Console- and Markdown-safe labels for every system. This also replaces legacy
# checkmark glyphs that fail on the default Windows cp1252 console encoding.
FLAGS.update({
    "A_naive_text": ("yes", "no", "no", "no"),
    "B_naive_multimodal": ("yes", "yes", "no", "no"),
    "C_append_only_temporal": ("yes", "yes", "append-only", "no"),
    "D_proposed_no_linking": ("yes", "yes", "adaptive", "no"),
    "E_proposed": ("yes", "yes", "adaptive", "yes"),
    "E_text_input_only": ("yes", "no", "adaptive", "n/a"),
    "E_image_input_only": ("no", "yes", "adaptive", "n/a"),
})


def _cell(m: Dict[str, Any], key: str) -> str:
    v = m["queries"][key]
    s = fmt(v["value"])
    if v.get("ci95"):
        s += f" [{v['ci95'][0]:.2f}, {v['ci95'][1]:.2f}]"
    return s


def markdown_table(results: List[Dict[str, Any]]) -> str:
    head = ("| System | Text | Image | Temporal memory | Evidence linking | Current QA (CSA) | Historical QA (HSA) "
            "| Initial | Identity | Evidence P/R | Unsupported | Schema | Visual P/FAR | Update acc. | Conflict F1 |\n"
            "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    rows = []
    for r in results:
        f = FLAGS.get(r["system"], ("?",) * 4)
        act = r.get("actions") or {}
        conflict = (act.get("conflict_detection") or {}).get("f1")
        vis = r.get("visual_association") or {}
        rows.append(
            f"| {r['system']} | {f[0]} | {f[1]} | {f[2]} | {f[3]} | {_cell(r, 'current_state_accuracy')} "
            f"| {_cell(r, 'historical_state_accuracy')} | {_cell(r, 'initial_state_accuracy')} "
            f"| {_cell(r, 'entity_identity_accuracy')} | {fmt(r['queries']['evidence_precision']['value'])}/"
            f"{fmt(r['queries']['evidence_recall']['value'])} | {fmt(r['queries']['unsupported_answer_rate']['value'])} "
            f"| {fmt(r['queries']['answer_schema_validity']['value'])} "
            f"| {fmt(vis.get('precision'))}/{fmt(vis.get('false_association_rate'))} "
            f"| {fmt(act.get('state_update_accuracy'))} | {fmt(conflict)} |")
    note = ("\n_Values are accuracies on the chosen split with 95% cluster-bootstrap CIs over scenarios in "
            "brackets. Update acc. and Conflict F1 are n/a for systems without an update engine._\n")
    return head + "\n".join(rows) + "\n" + note


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=0, help="use only the first n scenarios of the split (0 = all)")
    ap.add_argument("--light", action="store_true", help="hashing embeddings + HSV only; no downloads")
    ap.add_argument("--systems", nargs="*", default=None, help="subset of system names")
    ap.add_argument("--out", default="reports/results")
    a = ap.parse_args()

    cfg = load_config()
    data = load_dataset(a.data)
    scen = data if a.split == "all" else split_dataset(data, a.seed)[a.split]
    if a.n:
        scen = scen[: a.n]
    comp = build_components(cfg, light=a.light)
    print("components:", {"text_embedding": getattr(comp.embedder, "name", "?"), **comp.visual.status()})

    factories = build_systems(comp, cfg)
    names = a.systems or list(factories)
    results = []
    for name in names:
        print(f"== {name}")
        res = run_system(factories[name](), scen, verbose=True)
        res["system"] = name
        results.append(res)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    component_status = {"text_embedding": getattr(comp.embedder, "name", "?"), **comp.visual.status()}
    meta = manifest(a.data, cfg, a, component_status, scen)
    meta["systems"] = names
    paired = comparisons(results)
    errors = error_analysis(results)
    with open(out / "ablation_results.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "paired_comparisons": paired, "results": results}, f, indent=2, default=str)
    (out / "run_manifest.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    (out / "paired_comparisons.json").write_text(json.dumps(paired, indent=2), encoding="utf-8")
    (out / "error_analysis.json").write_text(json.dumps(errors, indent=2, default=str), encoding="utf-8")
    (out / "error_analysis.md").write_text(error_markdown(errors), encoding="utf-8")
    (out / "research_summary.md").write_text(research_summary(results, paired), encoding="utf-8")
    table = markdown_table(results)
    (out / "ablation_table.md").write_text(table, encoding="utf-8")
    encoding = sys.stdout.encoding or "utf-8"
    print("\n" + table.encode(encoding, errors="replace").decode(encoding))
    print(f"saved to {out}/ablation_results.json and ablation_table.md")


if __name__ == "__main__":
    main()
