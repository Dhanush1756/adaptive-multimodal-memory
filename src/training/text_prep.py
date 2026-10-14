"""Slot masking for the intent classifier.

Kept in its own importable module on purpose: the sklearn pipeline is pickled with a reference
to `mask_slots`, so it must live at a stable module path (not in a script run as __main__).
Masking colours / entities / dates makes the classifier learn the *question shape* instead of
memorising which colour words appeared in the training questions.
"""
from __future__ import annotations

import re

from ..nlp.ner import DEFAULT_LEXICON
from ..nlp.relation_extraction import COLOR_WORDS

_COLOR_RX = re.compile(r"\b(" + "|".join(COLOR_WORDS) + r")\b", re.I)
_ENT_WORDS = sorted({w.lower() for ws in DEFAULT_LEXICON.values() for w in ws} | set(DEFAULT_LEXICON), key=len, reverse=True)
_ENT_RX = re.compile(r"\b(" + "|".join(re.escape(w) for w in _ENT_WORDS) + r")s?\b", re.I)
_DATE_RX = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"
    r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{4})?\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s+\d{4})?\b",
    re.I,
)


def mask_slots(text: str) -> str:
    t = (text or "").lower()
    t = _DATE_RX.sub(" datetoken ", t)
    t = _COLOR_RX.sub(" colorword ", t)
    t = _ENT_RX.sub(" entityword ", t)
    return re.sub(r"\s+", " ", t).strip()
