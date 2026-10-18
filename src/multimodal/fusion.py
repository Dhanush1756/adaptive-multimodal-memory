"""Evidence fusion: NLP claim + CV analysis -> engine Candidate (brief sections 15, 19, 29).

Rules
  * entity            : claim entity > entity mentioned in text > detected object > context
  * value-less event  : "I removed the skin" has no colour; the value is taken from the image
                        iff an image exists (otherwise the claim is dropped)
  * text + image      : agreement score; near-synonym colours (gray/silver) are harmonised so
                        they support rather than contradict each other
  * image only        : Candidate.claim = None; the engine applies its image-only rules
  * confidence        : C = (w1*text + w2*visual + w3*agreement + w4*temporal) / sum(w present)
  * time              : the *event* time ("last week") when resolvable, else the session time
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Optional

from ..config import load_config
from ..memory.conflict import normalize_value
from ..memory.schema import Candidate, Claim, TextEvidence, VisualEvidence
from .alignment import cross_modal_agreement
from .evidence import ImageAnalysis


def combine_confidence(
    text_conf: Optional[float],
    visual_conf: Optional[float],
    agreement: Optional[float],
    temporal: float,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    w = (cfg or load_config()).get("confidence", {})
    parts: List[tuple] = []
    if text_conf is not None:
        parts.append((float(w.get("w_text", 0.30)), text_conf))
    if visual_conf is not None:
        parts.append((float(w.get("w_visual", 0.30)), visual_conf))
    if agreement is not None:
        parts.append((float(w.get("w_agreement", 0.25)), agreement))
    parts.append((float(w.get("w_temporal", 0.15)), temporal))
    total = sum(wt for wt, _ in parts)
    return round(sum(wt * v for wt, v in parts) / total, 3)


def fuse(
    *,
    text: str,
    session_id: str,
    timestamp: str,
    claim: Optional[Claim],
    text_entity: Optional[str],
    context_entity: Optional[str],
    image: Optional[ImageAnalysis],
    image_id: Optional[str] = None,
    image_path: str = "",
    text_embedding: Optional[List[float]] = None,
    cfg: Optional[Dict[str, Any]] = None,
    temporal_consistency: float = 1.0,
    semantic_similarity: Optional[float] = None,
    ingested_at: str = "",
    nlp_extractor: str = "rules-v1",
) -> Candidate:
    text = (text or "").strip()
    entity = (claim.entity if claim else None) or text_entity or (image.entity if image else None) or context_entity
    entity = entity.lower() if entity else None

    visual: Optional[VisualEvidence] = None
    colour_attribute = claim is None or claim.attribute.lower() == 'color'
    usable_visual = image is not None and image.association_status in {"verified", "contextual"}
    if usable_visual and entity and image.color:
        visual = VisualEvidence(
            image_id=image_id or "",
            image_path=image_path,
            label=entity,
            bbox=[float(v) for v in image.detection.bbox],
            value=normalize_value(image.color),
            confidence=image.confidence,
            detection_confidence=image.detection.confidence,
            embedding=[float(x) for x in image.embedding],
            timestamp=timestamp,
            session_id=session_id,
            association_status=image.association_status if colour_attribute else 'contextual',
            association_reason=(image.association_reason if colour_attribute else
                image.association_reason + '; colour extraction cannot verify this non-colour attribute'),
            supports_state=image.association_status == "verified" and colour_attribute,
            ingested_at=ingested_at,
            detector_model=image.detector_model,
            attribute_model=image.method,
            embedding_model=image.embedding_model,
            classifier=image.classifier,
        )

    agreement: Optional[float] = None
    if claim is not None and not claim.value:
        # value-less change event: fill from the image if there is one
        if visual is not None and visual.supports_state and colour_attribute:
            claim = replace(claim, value=visual.value, confidence=round(min(claim.confidence, visual.confidence), 3))
        else:
            claim = None
    elif claim is not None and visual is not None and colour_attribute:
        # Cross-check every associated image, including detector-free contextual
        # evidence. Contextual evidence remains non-supporting and cannot change
        # state, but its agreement is still useful to explain a visible mismatch.
        agreement = cross_modal_agreement(claim.value, visual.value)
        if visual.supports_state and agreement is not None and 0.5 <= agreement < 1.0:
            visual.value = normalize_value(claim.value)  # near-synonym: treat as supporting

    text_ev: Optional[TextEvidence] = None
    if text and (claim is not None or visual is not None):
        text_ev = TextEvidence(
            text=claim.source_text if claim else text,
            session_id=session_id,
            timestamp=timestamp,
            confidence=claim.confidence if claim else 0.0,
            embedding=text_embedding,
            evidence_id=f"TXT_{session_id}",
            ingested_at=ingested_at,
            extractor=nlp_extractor,
        )

    cand_time = claim.resolved_time if (claim is not None and claim.resolved_time) else timestamp
    confidence = combine_confidence(
        claim.confidence if claim is not None else None,
        visual.confidence if visual is not None and visual.supports_state else None,
        agreement if visual is not None and visual.supports_state else None,
        temporal_consistency,
        cfg,
    )
    return Candidate(
        session_id=session_id,
        timestamp=cand_time,
        claim=claim,
        text_evidence=text_ev,
        visual=visual,
        agreement=agreement,
        confidence=confidence,
        semantic_similarity=semantic_similarity,
        ingested_at=ingested_at,
    )
