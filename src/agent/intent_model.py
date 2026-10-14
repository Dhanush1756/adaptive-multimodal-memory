"""Optional learned intent classifier that backs up the rule-based query parser.

The rules are tried first. Only when the parser's own `rule_confidence` is low (it fell
through to the CURRENT default without any cue) does the classifier get a vote. It changes the
intent label only; slots (entity, reference_value, ...) always come from the rules.
Train it with: python -m src.training.train_intent_classifier
"""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Optional

from ..config import resolve_path
from .query_parser import Intent, ParsedQuery

MODEL_PATH = resolve_path("models/intent_clf.joblib")


def load_intent_model(path: Optional[str] = None) -> Optional[Any]:
    path = path or MODEL_PATH
    if not os.path.exists(path):
        return None
    try:
        import joblib

        return joblib.load(path)
    except Exception as exc:
        print(f"[intent] could not load {path} ({exc.__class__.__name__}); using rules only")
        return None


def apply_intent_model(parsed: ParsedQuery, model: Any, min_rule_conf: float = 0.7) -> ParsedQuery:
    if model is None or parsed.rule_confidence >= min_rule_conf:
        return parsed
    try:
        label = str(model.predict([parsed.raw])[0])
        intent = Intent(label)
    except Exception:
        return parsed
    scope = parsed.evidence_scope
    if intent == Intent.EVIDENCE and scope is None:
        scope = "VALUE" if parsed.target_value else "CURRENT"
    return replace(parsed, intent=intent, evidence_scope=scope)
