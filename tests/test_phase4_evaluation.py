"""Validation for the fixed, manually annotated Phase 4 evaluation set."""
from pathlib import Path

from src.data.synthetic import load_dataset
from src.evaluation.ablations import build_systems
from src.evaluation.benchmarks import run_system
from src.agent.reasoning import build_components
from src.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def _texts(dataset):
    return {s["text"].strip().lower() for sc in dataset for s in sc["sessions"] if s.get("text")}


def test_phase4_dev_and_test_annotations_are_disjoint_and_well_formed():
    dev = load_dataset(str(ROOT / "data" / "annotations" / "phase4_dev.jsonl"))
    test = load_dataset(str(ROOT / "data" / "annotations" / "phase4_test.jsonl"))
    assert len(dev) == 2 and len(test) == 8
    assert not (_texts(dev) & _texts(test))
    assert len({sc["scenario_id"] for sc in dev + test}) == 10
    assert all("answerable" in q or q.get("answer") is not None for sc in test for q in sc["queries"])


def test_phase4_system_matrix_builds_without_opening_user_storage():
    cfg = load_config()
    comp = build_components(cfg, light=True)
    factories = build_systems(comp, cfg)
    names = {"N_no_memory", "L_latest_value", "B_naive_multimodal", "C_append_only_temporal",
             "E_no_provenance", "E_no_visual_linking", "E_no_text_image_conflict", "E_proposed"}
    assert names <= factories.keys()
    for name in names:
        system = factories[name]()
        agent = getattr(system, "inner", system)
        if hasattr(agent, "store"):
            assert agent.store.db_path == ":memory:"
            agent.store.close()


def test_runtime_errors_are_reported_but_not_scored_as_lifecycle_decisions():
    class Broken:
        def reset(self):
            pass

        def remember(self, **kwargs):
            raise ValueError("bad input")

        def ask(self, question, reference_time=None):
            from types import SimpleNamespace
            return SimpleNamespace(found=False, value=None, evidence=[])

    scenario = [{"scenario_id": "X", "sessions": [{"session_id": "S", "timestamp": None,
                 "text": "", "image_case": "decode_failure", "gt": {"kind": "bad", "action": "IGNORE"}}],
                 "queries": []}]
    result = run_system(Broken(), scenario)
    assert result["n_session_errors"] == 1 and result["actions"] is None
