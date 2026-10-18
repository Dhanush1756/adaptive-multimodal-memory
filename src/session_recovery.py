"""Opaque, local recovery codes for isolated Streamlit memory namespaces.

Codes are bearer secrets: the application never lists them and only opens an
already-existing database for an exact, validated code. This is suitable for
the local prototype; multi-user deployment still requires real authentication.
"""
from __future__ import annotations

from pathlib import Path
import re
import secrets
from typing import Any, Dict, Tuple

from .config import resolve_path


_RECOVERY_CODE = re.compile(r"^[0-9a-f]{32}$")


def new_recovery_code() -> str:
    return secrets.token_hex(16)


def validate_recovery_code(code: str) -> str:
    normalized = (code or "").strip().lower()
    if not _RECOVERY_CODE.fullmatch(normalized):
        raise ValueError("invalid recovery code")
    return normalized


def session_paths(cfg: Dict[str, Any], code: str) -> Tuple[Path, Path]:
    token = validate_recovery_code(code)
    configured_db = cfg["paths"]["db_path"]
    if configured_db == ":memory:":
        raise ValueError("in-memory sessions cannot be recovered after restart")
    base = Path(resolve_path(configured_db))
    db_root = (base.parent / f"{base.stem}_sessions").resolve()
    image_root = (Path(resolve_path(cfg["paths"]["image_dir"])) / "sessions").resolve()
    db_path = (db_root / token / base.name).resolve()
    image_path = (image_root / token).resolve()
    # Strict token validation already prevents traversal; retain an explicit
    # containment check in case path construction changes later.
    db_path.relative_to(db_root)
    image_path.relative_to(image_root)
    return db_path, image_path


def recoverable_session_exists(cfg: Dict[str, Any], code: str) -> bool:
    try:
        db_path, _ = session_paths(cfg, code)
    except ValueError:
        return False
    return db_path.is_file()
