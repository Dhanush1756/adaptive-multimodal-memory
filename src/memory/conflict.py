"""Value normalisation and cross-modal conflict detection (brief sections 17 and 33)."""
from __future__ import annotations

from typing import Optional

from .schema import Candidate

_SYNONYMS = {
    "grey": "gray",
    "navy": "blue",
    "crimson": "red",
    "scarlet": "red",
    "maroon": "red",
    "violet": "purple",
    "golden": "yellow",
    "gold": "yellow",
    "silvery": "silver",
    "dark": "black",
}


def normalize_value(value: Optional[str]) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    return _SYNONYMS.get(v, v)


def values_equal(a: Optional[str], b: Optional[str]) -> bool:
    return normalize_value(a) == normalize_value(b) and normalize_value(a) != ""


def detect_cross_modal_conflict(
    cand: Candidate, text_conf_min: float = 0.6, visual_conf_min: float = 0.6
) -> Optional[str]:
    """Return the *visual* value if text and image confidently disagree, else None.

    Both modalities must be confident: a weak image prediction alone should not block a
    clear text statement (and vice versa). Weak disagreement is handled by the
    confidence model instead of a conflict flag.
    """
    if (cand.claim is None or cand.visual is None or not cand.visual.value or
            not cand.visual.supports_state):
        return None
    if values_equal(cand.claim.value, cand.visual.value):
        return None
    if cand.claim.confidence >= text_conf_min and cand.visual.confidence >= visual_conf_min:
        return cand.visual.value
    return None
