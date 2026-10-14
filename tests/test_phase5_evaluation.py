from pathlib import Path

from src.data.synthetic import load_dataset
from src.evaluation.metrics import score_query


ROOT = Path(__file__).resolve().parents[1]


def _texts(data):
    return {s["text"].strip().lower() for sc in data for s in sc["sessions"] if s.get("text")}


def test_phase5_splits_are_fixed_disjoint_and_do_not_overlap_phase4():
    dev = load_dataset(str(ROOT / "data" / "annotations" / "phase5_dev.jsonl"))
    test = load_dataset(str(ROOT / "data" / "annotations" / "phase5_test.jsonl"))
    old = load_dataset(str(ROOT / "data" / "annotations" / "phase4_test.jsonl"))
    assert (len(dev), len(test)) == (3, 6)
    assert not (_texts(dev) & _texts(test))
    assert not (_texts(test) & _texts(old))
    assert len({s["scenario_id"] for s in dev + test}) == 9


def test_answer_schema_metric_rejects_legacy_shape():
    class Legacy:
        found = True
        value = "red"
        evidence = []

    q = {"kind": "current", "intent": "CURRENT", "question": "q", "answer": "red"}
    assert score_query(q, Legacy())["answer_schema_valid"] is False
