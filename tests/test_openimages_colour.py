"""Offline acquisition/label integrity checks; never download the dataset in tests."""
import csv
import json

import pytest

from src.config import load_config
from src.data.openimages_colour import caption_colour, candidates, acquire


@pytest.mark.parametrize("text,expected", [
    ("A red car is parked.", "red"),
    ("A grey coloured car.", "gray"),
    ("The car is blue.", "blue"),
    ("A red carpet.", None),
    ("A red car and a blue car.", None),
    ("A white laptop.", None),
])
def test_explicit_colour_phrase_only(text, expected):
    assert caption_colour(text) == expected


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_multiple_cars_and_depictions_are_excluded(tmp_path):
    meta = tmp_path / "metadata"
    meta.mkdir()
    (meta / "classes.csv").write_text("/m/car,Car\n")
    captions = [{"image_id": name,"caption":"A red car is parked.","annotator_id":1} for name in ("one","many","drawing")]
    (meta / "captions.jsonl").write_text("\n".join(json.dumps(r) for r in captions))
    def box(name, depiction="0"):
        return {"ImageID":name,"LabelName":"/m/car","XMin":"0","XMax":"1","YMin":"0","YMax":"1",
                "IsGroupOf":"0","IsDepiction":depiction,"IsInside":"0","IsTruncated":"0","IsOccluded":"0"}
    write_csv(meta / "boxes.csv", [box("one"),box("many"),box("many"),box("drawing","1")])
    write_csv(meta / "images.csv", [{"ImageID":r["image_id"],"License":"https://creativecommons.org/licenses/by/2.0/",
                                    "AuthorProfileURL":"https://example.org/author"} for r in captions])
    rows = candidates(tmp_path)
    assert len(rows) == 1 and rows[0]["image_id"] == "one"
    assert "physical-object ground truth" in rows[0]["group_scope"]


def test_acquisition_record_prevents_overwrite_or_network(tmp_path, monkeypatch):
    (tmp_path / "acquisition.json").write_text("{}")
    def no_network(*args, **kwargs):
        raise AssertionError("must not access network")
    monkeypatch.setattr("urllib.request.urlopen", no_network)
    with pytest.raises(FileExistsError):
        acquire(tmp_path)


def test_configuration_profile_is_explicit_and_missing_profile_fails(tmp_path, monkeypatch):
    profile = tmp_path / "profile.yaml"
    profile.write_text("cv:\n  color_head_path: models/experimental.joblib\n  color_head_entities: [car]\n")
    monkeypatch.setenv("AEGM_CONFIG_PATH", str(profile))
    assert load_config()["cv"]["color_head_entities"] == ["car"]
    monkeypatch.setenv("AEGM_CONFIG_PATH", str(tmp_path / "absent.yaml"))
    with pytest.raises(FileNotFoundError):
        load_config()
