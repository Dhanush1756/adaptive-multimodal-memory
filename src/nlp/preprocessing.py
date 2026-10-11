"""Text preprocessing (brief section 13, stages 1-2).

Principle from the brief: do NOT strip information that matters for temporal or factual
reasoning (negations, "now", "before", "ago" ...), so there is no stop-word removal here.
spaCy is used when available; everything has a plain-Python fallback so tests need no models.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import List, Optional

_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}
_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "e.g.", "i.e.", "vs.", "etc.", "no."}


def normalize(text: str) -> str:
    """Unicode-normalise, unify quotes/dashes and collapse whitespace. Keeps case and digits."""
    text = unicodedata.normalize("NFKC", text or "")
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> List[str]:
    """Word tokens; keeps apostrophes inside words ("don't") and hyphenated words."""
    return re.findall(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*", normalize(text))


@lru_cache(maxsize=1)
def _spacy(model: str = "en_core_web_sm"):
    try:
        import spacy

        return spacy.load(model)
    except Exception:
        return None


def get_spacy(model: str = "en_core_web_sm"):
    """Return a loaded spaCy pipeline or None (callers must handle None)."""
    return _spacy(model)


def split_sentences(text: str, use_spacy: bool = True) -> List[str]:
    text = normalize(text)
    if not text:
        return []
    nlp = get_spacy() if use_spacy else None
    if nlp is not None and nlp.has_pipe("parser"):
        return [s.text.strip() for s in nlp(text).sents if s.text.strip()]
    # Regex fallback: split after . ! ? followed by space + capital/digit, except abbreviations.
    parts, start = [], 0
    for m in re.finditer(r"[.!?]+(?=\s+[A-Z0-9\"'])", text):
        chunk = text[start : m.end()]
        last = chunk.split()[-1].lower() if chunk.split() else ""
        if last in _ABBREV:
            continue
        parts.append(chunk.strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


# --- optional lemmatisation -------------------------------------------------------------
_IRREGULAR = {
    "bought": "buy", "got": "get", "gotten": "get", "took": "take", "taken": "take",
    "went": "go", "was": "be", "were": "be", "is": "be", "are": "be", "been": "be",
    "had": "have", "has": "have", "did": "do", "done": "do", "made": "make",
    "put": "put", "stuck": "stick", "dyed": "dye", "removed": "remove", "changed": "change",
}
_PROTECTED = {"red", "bed", "need", "speed", "feed", "shed", "pink", "this", "his", "its", "was", "has"}


def lemmatize(token: str, nlp: Optional[object] = None) -> str:
    """Lemma of a single token. Uses spaCy if provided/available, else a small rule set."""
    tok = token.lower()
    # nlp=None -> try spaCy; nlp=False -> force the rule-based path (used in tests)
    nlp = get_spacy() if nlp is None else (nlp or None)
    if nlp is not None and nlp.has_pipe("lemmatizer"):
        doc = nlp(tok)
        if len(doc) == 1 and doc[0].lemma_:
            return doc[0].lemma_.lower()
    if tok in _IRREGULAR:
        return _IRREGULAR[tok]
    if tok in _PROTECTED or len(tok) <= 4:
        return tok
    if tok.endswith("ing") and len(tok) > 5:
        stem = tok[:-3]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem
    if tok.endswith("ied"):
        return tok[:-3] + "y"
    if tok.endswith("ed"):
        stem = tok[:-2]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem
    if tok.endswith("ies"):
        return tok[:-3] + "y"
    if tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok
