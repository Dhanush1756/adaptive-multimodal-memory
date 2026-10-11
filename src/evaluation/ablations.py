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
import json
from pathlib import Path
from typing import Any, Callable, Dict, List

from ..agent.reasoning import MemoryAgent, build_components
from ..config import load_config
from ..data.synthetic import load_dataset
from .baselines import AppendOnlyTemporalMemory, NaiveMultimodalMemory, NaiveTextMemory
from .benchmarks import run_system, split_dataset
from .metrics import fmt


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


def build_systems(comp: Any, cfg: Dict[str, Any]) -> Dict[str, Callable[[], Any]]:
    def agent(link: bool, name: str):
        a = MemoryAgent(cfg, components=comp, link_evidence=link, use_intent_model=False)
        a.name = name
        return a

    def named(obj, name):
        obj.name = name
        return obj

    return {
        "A_naive_text": lambda: named(NaiveTextMemory(cfg, components=comp), "A_naive_text"),
        "B_naive_multimodal": lambda: named(NaiveMultimodalMemory(cfg, components=comp), "B_naive_multimodal"),
        "C_append_only_temporal": lambda: named(AppendOnlyTemporalMemory(cfg, components=comp), "C_append_only_temporal"),
        "D_proposed_no_linking": lambda: agent(False, "D_proposed_no_linking"),
        "E_proposed": lambda: agent(True, "E_proposed"),
        "E_text_input_only": lambda: ModalityView(agent(True, "x"), True, False, "E_text_input_only"),
        "E_image_input_only": lambda: ModalityView(agent(True, "x"), False, True, "E_image_input_only"),
    }


FLAGS = {  # (text, image, temporal memory, evidence linking) per the brief's table
    "A_naive_text": ("✓", "✗", "✗", "✗"),
    "B_naive_multimodal": ("✓", "✓", "✗", "✗"),
    "C_append_only_temporal": ("✓", "✓", "✓ (append-only)", "✗"),
    "D_proposed_no_linking": ("✓", "✓", "✓ (adaptive)", "✗"),
    "E_proposed": ("✓", "✓", "✓ (adaptive)", "✓"),
    "E_text_input_only": ("✓", "✗", "✓ (adaptive)", "–"),
    "E_image_input_only": ("✗", "✓", "✓ (adaptive)", "–"),
}


def _cell(m: Dict[str, Any], key: str) -> str:
    v = m["queries"][key]
    s = fmt(v["value"])
    if v.get("ci95"):
        s += f" [{v['ci95'][0]:.2f}, {v['ci95'][1]:.2f}]"
    return s


def markdown_table(results: List[Dict[str, Any]]) -> str:
    head = ("| System | Text | Image | Temporal memory | Evidence linking | Current QA (CSA) | Historical QA (HSA) "
            "| Time/Change QA | Timeline QA | Evidence recall | Update acc. | Conflict F1 |\n"
            "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
    rows = []
    for r in results:
        f = FLAGS.get(r["system"], ("?",) * 4)
        act = r.get("actions") or {}
        conflict = (act.get("conflict_detection") or {}).get("f1")
        rows.append(
            f"| {r['system']} | {f[0]} | {f[1]} | {f[2]} | {f[3]} | {_cell(r, 'current_state_accuracy')} "
            f"| {_cell(r, 'historical_state_accuracy')} | {_cell(r, 'temporal_accuracy')} "
            f"| {_cell(r, 'temporal_ordering_accuracy')} | {fmt(r['queries']['evidence_recall']['value'])} "
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
    meta = {"split": a.split, "n_scenarios": len(scen), "light": a.light,
            "components": {"text_embedding": getattr(comp.embedder, "name", "?"), **comp.visual.status()}}
    with open(out / "ablation_results.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, indent=2, default=str)
    table = markdown_table(results)
    (out / "ablation_table.md").write_text(table, encoding="utf-8")
    print("\n" + table)
    print(f"saved to {out}/ablation_results.json and ablation_table.md")


if __name__ == "__main__":
    main()
