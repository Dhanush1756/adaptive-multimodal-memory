"""Versioned Track C and controlled Track D checks; never runs frozen benchmarks.

python -m src.evaluation.cross_session --out reports/phase14/run-1.json
Only temporary users, registry databases and uploaded fixtures are used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time

from PIL import Image

from ..accounts import Accounts, AuthenticationError
from ..conversations import Conversations


def ratio(n, d):
    return {"numerator": n, "denominator": d, "value": n / d if d else None}


def run(dataset):
    spec = json.loads(Path(dataset).read_text(encoding="utf-8"))
    results = []
    with tempfile.TemporaryDirectory(prefix="adaptive-track-c-") as tmp:
        root = Path(tmp)
        registry = Accounts(root / "accounts.db")
        registry.register("researcher", "temporary evaluation password")
        token = registry.login("researcher", "temporary evaluation password")
        service = Conversations(registry, token, root / "users")
        names = {}
        for conversation in spec["conversations"]:
            cid = service.create(conversation["name"])
            names[cid] = conversation["name"]
            for observation in conversation["observations"]:
                service.remember(cid, observation["text"], timestamp=observation["date"])
            for i in range(conversation.get("intervening_messages", 0)):
                service.remember(cid, f"Intervening unrelated note {i}.", timestamp="2026-10-02")
        registry.logout(token)
        service.close()
        registry.close()
        # Reconstruct all service objects; no process/session-state memory used.
        registry = Accounts(root / "accounts.db")
        token = registry.login("researcher", "temporary evaluation password")
        service = Conversations(registry, token, root / "users")
        cid = service.create("return visit")
        for query in spec["queries"]:
            start = time.perf_counter()
            answer = service.ask(cid, query["question"])
            latency = (time.perf_counter() - start) * 1000
            retrieved = {names.get(ref["conversation_id"], "return visit")
                         for evidence in answer.evidence for ref in evidence.get("conversation_references", [])}
            expected = set(query["sources"])
            correct = (not answer.found) if query["value"] is None else answer.value == query["value"]
            results.append({"question": query["question"], "family": query["family"],
                            "correct": correct, "found": answer.found, "actual": answer.value,
                            "expected": query["value"], "source_conversations": sorted(retrieved),
                            "expected_sources": sorted(expected), "tp": len(retrieved & expected),
                            "fp": len(retrieved - expected), "fn": len(expected - retrieved), "latency_ms": latency})
        registry.register("other_user", "another temporary password")
        other_token = registry.login("other_user", "another temporary password")
        other = Conversations(registry, other_token, root / "users")
        other_cid = other.create()
        no_leak = not other.ask(other_cid, "Which model did we decide to train?").found
        try:
            other.transcript(cid)
            no_leak = False
        except AuthenticationError:
            pass
        other.close()
        multimodal = []
        for choice in ("red", "white"):
            # Same authenticated account, isolated entity reference per case.
            case = service.create("controlled image decision")
            text = "My first laptop is red." if choice == "red" else "My second laptop is red."
            identity = "first laptop" if choice == "red" else "second laptop"
            result = service.remember(case, text, Image.new("RGB", (128, 128), "white"), "2026-10-20")
            prompted = service.agent.verification_request(result) is not None
            service.resolve(case, result, choice, "Controlled evaluation fixture")
            answer = service.ask(case, f"What color is my {identity} now?")
            original = service.ask(case, f"What color was my {identity} originally?")
            multimodal.append({"selected": choice, "prompted": prompted,
                               "current_correct": answer.value == choice,
                               "historical_correct": original.value == "red"})
        storage_bytes = Path(service.agent.store.db_path).stat().st_size
        service.close()
        registry.close()
    correct = sum(r["correct"] for r in results)
    tp, fp, fn = (sum(r[k] for r in results) for k in ("tp", "fp", "fn"))
    temporal = [r for r in results if r["family"] in {"historical", "initial", "late_arrival"}]
    abstain = [r for r in results if r["family"] == "abstention"]
    identity = [r for r in results if r["family"] == "identity"]
    return {"dataset": spec["version"], "dataset_sha256": hashlib.sha256(Path(dataset).read_bytes()).hexdigest(),
            "profile": "Light mode, controlled authored conversations and generated image fixtures; no real photos or pretrained inference",
            "metrics": {"cross_session_accuracy": ratio(correct, len(results)),
                        "temporal_accuracy": ratio(sum(r["correct"] for r in temporal), len(temporal)),
                        "conversation_evidence_precision": ratio(tp, tp + fp),
                        "conversation_evidence_recall": ratio(tp, tp + fn),
                        "unsupported_answer_rate": ratio(sum(r["found"] and not r["expected_sources"] for r in results), len(results)),
                        "abstention_accuracy": ratio(sum(r["correct"] for r in abstain), len(abstain)),
                        "entity_accuracy": ratio(sum(r["correct"] for r in identity), len(identity)),
                        "service_reopen_success": ratio(int(correct > 0), 1),
                        "cross_user_isolation": ratio(int(no_leak), 1)},
            "storage_bytes_after_run": storage_bytes, "queries": results,
            "track_d_controlled": multimodal,
            "limitations": ["Small controlled suite; no public dialogue benchmark or statistical superiority claim.",
                            "Evidence metrics use source-conversation sets, not token-level citation correctness.",
                            "Service reopen simulates restart; this is not a browser-restart test."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default="data/annotations/phase14_track_c_v1.json")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    output = Path(a.out)
    if output.exists():
        raise FileExistsError("Use a new output file; previous runs are immutable.")
    result = run(a.dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
