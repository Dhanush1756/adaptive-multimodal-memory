"""Recovery-code behavior uses only temporary isolated SQLite databases."""
from pathlib import Path

import pytest

from src.agent.reasoning import MemoryAgent
from src.config import load_config
from src.session_recovery import (
    new_recovery_code, recoverable_session_exists, session_paths, validate_recovery_code,
)


def _config(tmp_path):
    cfg = load_config()
    cfg["paths"]["db_path"] = str(tmp_path / "memory" / "memory.db")
    cfg["paths"]["image_dir"] = str(tmp_path / "images")
    return cfg


def test_recovery_code_validation_rejects_missing_and_path_inputs():
    assert len(new_recovery_code()) == 32
    for invalid in ("", "short", "../memory", "g" * 32, "a" * 31, "a" * 33):
        with pytest.raises(ValueError, match="invalid recovery code"):
            validate_recovery_code(invalid)


def test_missing_recovery_session_is_not_created(tmp_path):
    cfg = _config(tmp_path)
    code = new_recovery_code()
    db, images = session_paths(cfg, code)
    assert not recoverable_session_exists(cfg, code)
    assert not db.exists() and not images.exists()


def test_existing_session_can_be_recovered_without_cross_session_access(tmp_path):
    cfg = _config(tmp_path)
    first_code, second_code = new_recovery_code(), new_recovery_code()
    first_db, first_images = session_paths(cfg, first_code)
    second_db, second_images = session_paths(cfg, second_code)

    first = MemoryAgent(cfg, db_path=str(first_db), image_dir=str(first_images),
                        light=True, use_intent_model=False)
    second = MemoryAgent(cfg, db_path=str(second_db), image_dir=str(second_images),
                         light=True, use_intent_model=False)
    try:
        first.remember("My car is red.", timestamp="2026-10-01", session_id="first")
        second.remember("My car is blue.", timestamp="2026-10-02", session_id="second")
    finally:
        first.store.close()
        second.store.close()

    assert recoverable_session_exists(cfg, first_code)
    assert recoverable_session_exists(cfg, second_code)
    reopened = MemoryAgent(cfg, db_path=str(session_paths(cfg, first_code)[0]),
                           image_dir=str(first_images), light=True, use_intent_model=False)
    try:
        assert reopened.ask("What color is my car now?").value == "red"
        assert Path(reopened.store.db_path) != second_db
    finally:
        reopened.store.close()
