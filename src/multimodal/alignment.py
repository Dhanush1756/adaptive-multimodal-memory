"""Cross-modal agreement between a text claim and visual evidence (brief section 29)."""
from __future__ import annotations

from typing import Optional

from ..memory.conflict import normalize_value

# Colours the CV side genuinely confuses get partial credit. Initial values, not tuned.
_NEAR = {
    frozenset({"gray", "silver"}): 0.6,
    frozenset({"white", "silver"}): 0.3,
    frozenset({"black", "gray"}): 0.3,
    frozenset({"red", "pink"}): 0.2,
    frozenset({"orange", "brown"}): 0.2,
    frozenset({"orange", "yellow"}): 0.2,
}


def value_agreement(a: Optional[str], b: Optional[str]) -> float:
    a, b = normalize_value(a), normalize_value(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return _NEAR.get(frozenset({a, b}), 0.0)


def cross_modal_agreement(text_value: Optional[str], visual_value: Optional[str]) -> Optional[float]:
    """None when either modality has no value (agreement is undefined, not zero)."""
    if not normalize_value(text_value) or not normalize_value(visual_value):
        return None
    return value_agreement(text_value, visual_value)
