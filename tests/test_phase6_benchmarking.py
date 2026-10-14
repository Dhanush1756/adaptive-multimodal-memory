from difflib import SequenceMatcher
from pathlib import Path

from src.agent.reasoning import build_components
from src.config import load_config
from src.data.synthetic import load_dataset
from src.evaluation.ablations import build_systems
from src.evaluation.benchmarks import run_system
from src.evaluation.metrics import paired_comparison


ROOT = Path(__file__).resolve().parents[1]


def _utterances(data):
    return [item[field].strip().lower() for scenario in data
            for group, field in (("sessions", "text"), ("queries", "question"))
            for item in scenario[group]]


def test_phase6_annotations_are_fixed_well_formed_and_split_cleanly():
    dev = load_dataset(str(ROOT / "data" / "annotations" / "phase6_dev.jsonl"))
    test = load_dataset(str(ROOT / "data" / "annotations" / "phase6_test.jsonl"))
    assert len(dev) == 15 and len(test) == 100
    assert len({s["scenario_id"] for s in dev + test}) == 115
    assert all(s.get("family") for s in dev + test)
    assert all(x.get("gt", {}).get("action") for s in dev + test for x in s["sessions"])
    assert all("answer" in q and q.get("intent") for s in dev + test for q in s["queries"])
    dev_text, test_text = _utterances(dev), _utterances(test)
    assert not (set(dev_text) & set(test_text))
    assert max(SequenceMatcher(None, a, b).ratio() for a in dev_text for b in test_text) < .96


def test_phase6_family_counts_and_visual_labels():
    test = load_dataset(str(ROOT / "data" / "annotations" / "phase6_test.jsonl"))
    counts = {}
    for scenario in test:
        counts[scenario["family"]] = counts.get(scenario["family"], 0) + 1
    assert counts == {
        "temporal_sequence": 15, "late_arrival": 10, "duplicate_and_corroboration": 10,
        "unrelated_visual": 10, "verified_visual": 10, "verified_conflict": 10,
        "entity_identity": 10, "abstention_and_irrelevance": 10,
        "corrupt_image": 5, "ambiguous_visual": 5, "long_sequence": 5,
    }
    labels = [s["gt"].get("visual_association") for sc in test for s in sc["sessions"]]
    assert labels.count("verified") == 30 and labels.count("rejected") == 15
    sessions = [s for scenario in test for s in scenario["sessions"]]
    assert sum(s.get("timestamp") is None for s in sessions) == 5
    assert sum(s["gt"]["kind"] == "contradictory_text" for s in sessions) == 5


def test_controlled_detector_annotations_exercise_verified_conflict():
    data = load_dataset(str(ROOT / "data" / "annotations" / "phase6_test.jsonl"))
    scenario = next(s for s in data if s["family"] == "verified_conflict")
    cfg = load_config()
    comp = build_components(cfg, light=True)
    result = run_system(build_systems(comp, cfg)["E_proposed"](), [scenario])
    assert [s["predicted"] for s in result["raw_sessions"]] == ["ADD", "CONTRADICTORY"]
    assert result["actions"]["conflict_detection"]["recall"] == 1.0
    assert result["n_session_errors"] == result["n_query_errors"] == 0


def test_paired_comparison_reports_discordance_and_cluster_interval():
    def result(name, flags):
        return {"system": name, "raw_queries": [
            {"scenario_id": f"S{i // 2}", "question": f"Q{i}", "correct": flag}
            for i, flag in enumerate(flags)]}
    candidate = result("candidate", [False, True] * 6)
    proposed = result("E_proposed", [True, True] * 6)
    compared = paired_comparison(candidate, proposed, seed=7, iters=100)
    assert compared["proposed_only_correct"] == 6
    assert compared["candidate_only_correct"] == 0
    assert compared["difference_proposed_minus_candidate"] == .5
    assert compared["scenario_bootstrap_difference_ci95"] is not None
