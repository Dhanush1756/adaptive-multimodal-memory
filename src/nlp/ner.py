"""Entity extraction (brief section 13, stage 3).

Two layers:
  1. A domain lexicon (canonical entity -> surface forms/brands). This is precise and needs
     no model; it is what the memory engine relies on.
  2. Optional spaCy NER, used only to *report* extra named entities (ORG/PRODUCT/DATE...)
     for the analysis panel. It never overrides the lexicon.

To add a tracked entity, extend DEFAULT_LEXICON (or pass your own lexicon).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .preprocessing import get_spacy, normalize

DEFAULT_LEXICON: Dict[str, List[str]] = {
    "car": [
        "car", "cars", "vehicle", "sedan", "suv", "hatchback", "coupe", "automobile", "ride",
        "tesla", "honda", "toyota", "bmw", "audi", "ford", "hyundai", "kia", "mercedes",
        "maruti", "tata", "mahindra", "volkswagen", "nissan", "model 3", "model s", "model y",
    ],
    "laptop": ["laptop", "notebook", "macbook", "thinkpad", "chromebook", "dell xps", "ultrabook"],
    "bike": ["bike", "bicycle", "motorcycle", "motorbike", "scooter"],
    "phone": ["phone", "smartphone", "iphone", "pixel", "android phone", "mobile"],
    "shirt": ["shirt", "t-shirt", "tshirt", "jacket", "hoodie", "sweater"],
    "room": ["room", "bedroom", "wall", "walls", "living room"],
    "plant": ["plant", "flower", "leaf", "leaves", "tree"],
}
PRONOUNS = {"it", "its", "this", "that", "he", "she"}


@dataclass
class Entity:
    text: str                 # surface form as written
    canonical: str            # lexicon key, e.g. "car"
    label: str                # "TRACKED" or a spaCy label
    start: int
    end: int
    confidence: float


def _compile(lexicon: Dict[str, List[str]]):
    pairs = []
    for canon, forms in lexicon.items():
        for f in sorted(set(forms), key=len, reverse=True):
            pairs.append((canon, f, re.compile(r"\b" + re.escape(f) + r"\b", re.I)))
    return pairs


_COMPILED = _compile(DEFAULT_LEXICON)


def extract_entities(
    text: str,
    lexicon: Optional[Dict[str, List[str]]] = None,
    use_spacy: bool = True,
) -> List[Entity]:
    """Tracked-domain entities first (confidence 0.95 canonical noun, 0.85 brand/model alias)."""
    text = normalize(text)
    pairs = _COMPILED if lexicon is None else _compile(lexicon)
    found: List[Entity] = []
    taken = []
    for canon, form, rx in pairs:
        for m in rx.finditer(text):
            if any(not (m.end() <= s or m.start() >= e) for s, e in taken):
                continue  # overlaps a longer, already-matched span
            taken.append((m.start(), m.end()))
            conf = 0.95 if form.lower() == canon else 0.85
            found.append(Entity(m.group(0), canon, "TRACKED", m.start(), m.end(), conf))
    found.sort(key=lambda e: e.start)

    if use_spacy:
        nlp = get_spacy()
        if nlp is not None and nlp.has_pipe("ner"):
            for ent in nlp(text).ents:
                if any(not (ent.end_char <= s or ent.start_char >= e) for s, e in taken):
                    continue
                found.append(Entity(ent.text, ent.text.lower(), ent.label_, ent.start_char, ent.end_char, 0.6))
            found.sort(key=lambda e: e.start)
    return found


def tracked_entities(text: str, lexicon: Optional[Dict[str, List[str]]] = None) -> List[Entity]:
    return [e for e in extract_entities(text, lexicon, use_spacy=False) if e.label == "TRACKED"]


def has_pronoun_reference(text: str) -> bool:
    """True if the sentence refers back to an entity ("it", "this one", "the vehicle")."""
    toks = set(re.findall(r"[a-z']+", normalize(text).lower()))
    return bool(toks & PRONOUNS)
