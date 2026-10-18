import csv
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
import pytest

from src.training.real_color_experiment import prepare, train
from src.multimodal.visual_pipeline import VisualPipeline
from src.config import load_config
from src.agent.reasoning import MemoryAgent


def fixture_manifest(tmp_path, n=80):
    # Generated image fixture verifies mechanics only; never real-photo metrics.
    rows = []
    rng = np.random.default_rng(4)
    for i in range(n):
        label = "red" if i % 2 else "blue"
        pixels = rng.integers(0, 70, (16, 16, 3), dtype=np.uint8)
        pixels[:, :, 0 if label == "red" else 2] += 160
        Image.fromarray(pixels).save(tmp_path / f"{i}.png")
        rows.append(dict(path=f"{i}.png", label=label, object_id=f"object-{i}", source="synthetic-test-fixture", license="generated-test-only"))
    path = tmp_path / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_group_split_repeatable_and_disjoint(tmp_path):
    csv = fixture_manifest(tmp_path)
    a, b = prepare(csv), prepare(csv)
    assert a == b
    groups = {}
    for row in a:
        groups.setdefault(row["object_id"], set()).add(row["split"])
    assert all(len(s) == 1 for s in groups.values())
    assert {r["split"] for r in a} == {"train", "dev", "test"}


def test_duplicate_image_rejected(tmp_path):
    path = fixture_manifest(tmp_path)
    (tmp_path / "1.png").write_bytes((tmp_path / "0.png").read_bytes())
    with pytest.raises(ValueError, match="Duplicate"):
        prepare(path)


def test_real_pipeline_loads_saved_hist_head_and_preserves_fallback(tmp_path):
    csv = fixture_manifest(tmp_path)
    metrics = train(csv, tmp_path / "experiment", features="hist")
    assert metrics["test"]["n"] > 0
    saved = joblib.load(tmp_path / "experiment" / "color_head.joblib")
    assert saved["features"] == "hist"
    config = load_config()
    config["cv"]["color_head_path"] = str(tmp_path / "experiment" / "color_head.joblib")
    config["cv"]["color_head_entities"] = ["car"]
    visual = VisualPipeline(config, light=True)
    assert visual.status()["classifier"] == "logistic-regression"
    assert visual.status()["classifier_features"] == "hist"
    analysis = visual.analyze(Image.open(tmp_path / "1.png"), preferred_entity="car")
    assert analysis.method == "hsv+head"
    assert analysis.association_status == "contextual"
    unrelated = visual.analyze(Image.open(tmp_path / "1.png"), preferred_entity="laptop")
    assert unrelated.method == "hsv"
    assert unrelated.classifier["applied"] is False
    agent = MemoryAgent(config, db_path=":memory:", light=True)
    observation = agent.remember("My car is red.", Image.open(tmp_path / "0.png"), "2026-10-01")
    assert observation.image["method"] == "hsv+head"
    assert observation.image["classifier"]["classifier_artifact_sha256"]
    assert observation.candidate.visual.classifier["classifier_features"] == "hist"
    assert agent.ask("What color is my car now?").value == "red"
    assert agent.verification_request(observation) is not None
    agent.store.close()
    with pytest.raises(FileExistsError):
        train(csv, tmp_path / "experiment", features="hist")


def test_requested_clip_fails_without_silent_histogram_substitution(tmp_path, monkeypatch):
    manifest = fixture_manifest(tmp_path)
    class MissingClip:
        available = False
        def __init__(self, cfg):
            assert cfg["cv"]["local_files_only"] is True
    monkeypatch.setattr("src.training.real_color_experiment.ClipBackend", MissingClip)
    with pytest.raises(RuntimeError, match="CLIP unavailable"):
        train(manifest, tmp_path / "clip-experiment", features="clip")
    assert not (tmp_path / "clip-experiment").exists()


def test_legacy_filename_split_is_disabled():
    from src.training.train_color_head import real_items
    with pytest.raises(ValueError, match="Filename-only real-photo splits are disabled"):
        real_items("not-opened", False)
