"""Load config.yaml. Missing file or missing keys fall back to safe defaults."""
from __future__ import annotations

import copy
import os
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS: Dict[str, Any] = {
    "paths": {
        "db_path": "data/processed/memory.db",
        "image_dir": "data/synthetic/images",
        "synthetic_dir": "data/synthetic",
        "results_dir": "reports/results",
    },
    "nlp": {
        "spacy_model": "en_core_web_sm",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "fallback_embedding_dim": 256,
        "tracked_entities": ["car", "laptop", "bike", "phone", "shirt", "room", "plant"],
        "tracked_attributes": ["color"],
    },
    "cv": {
        "yolo_weights": "yolov8n.pt",
        "yolo_conf": 0.25,
        "clip_model": "openai/clip-vit-base-patch32",
        "colors": ["red", "blue", "black", "white", "green", "yellow", "silver", "gray", "orange", "brown", "purple", "pink"],
        "clip_weight": 0.6,
        "hsv_weight": 0.4,
    },
    "memory": {
        "min_claim_confidence": 0.30,
        "conflict_text_conf": 0.60,
        "conflict_visual_conf": 0.60,
        "agreement_threshold": 0.50,
    },
    "confidence": {"w_text": 0.30, "w_visual": 0.30, "w_agreement": 0.25, "w_temporal": 0.15},
    "retrieval": {
        "w_semantic": 0.30, "w_entity": 0.20, "w_attribute": 0.20,
        "w_temporal": 0.20, "w_confidence": 0.10, "top_k": 5,
    },
    "llm": {"provider": "none", "model": ""},
}


def _merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    environment_path = os.environ.get("AEGM_CONFIG_PATH")
    if path is None and environment_path and not os.path.isfile(environment_path):
        raise FileNotFoundError("AEGM_CONFIG_PATH does not identify an existing configuration file")
    path = path or environment_path or os.path.join(ROOT, "config.yaml")
    user: Dict[str, Any] = {}
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[config] could not parse {path}: {exc}; using defaults")
    return _merge(DEFAULTS, user)


def resolve_path(rel: str) -> str:
    return rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
