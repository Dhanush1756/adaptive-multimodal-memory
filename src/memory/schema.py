"""Unified memory schema (brief sections 16 and 60).

Design notes
- One MemoryRecord == one *state* of (entity, attribute). Old states are never deleted;
  they change status to HISTORICAL and are chained with previous_memory_id.
- A record can carry several text and visual evidence items (MERGE adds evidence).
- Everything is plain dataclasses so the memory engine has no ML dependency.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Status(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    CONTRADICTORY = "CONTRADICTORY"
    RESOLVED = "RESOLVED"


class Action(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    MERGE = "MERGE"
    HISTORICAL = "HISTORICAL"
    CONTRADICTORY = "CONTRADICTORY"
    IGNORE = "IGNORE"


@dataclass
class TextEvidence:
    text: str
    session_id: str = ""
    timestamp: str = ""
    confidence: float = 0.0
    embedding: Optional[List[float]] = None
    evidence_id: str = ""
    ingested_at: str = ""
    extractor: str = "rules-v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TextEvidence":
        return TextEvidence(**d)


@dataclass
class VisualEvidence:
    image_id: str
    image_path: str = ""
    label: str = ""                       # detected object label, e.g. "car"
    bbox: Optional[List[float]] = None    # [x1, y1, x2, y2]
    value: Optional[str] = None           # visually derived attribute value, e.g. "blue"
    confidence: float = 0.0               # confidence of the visual attribute
    detection_confidence: float = 0.0     # confidence of the object detector
    embedding: Optional[List[float]] = None
    # Source observation metadata; independent of a state's earliest known event time.
    # Defaults keep JSON evidence from existing databases readable.
    timestamp: str = ""
    session_id: str = ""
    # `verified` means one detector result matched the claim entity.  `contextual`
    # is retained for detector-free observations and older JSON evidence; it is
    # explicitly surfaced to callers rather than claimed as detector verification.
    association_status: str = "contextual"
    association_reason: str = ""
    # Only detector-grounded associations may establish, support, or contradict a state.
    supports_state: bool = False
    ingested_at: str = ""
    detector_model: str = ""
    attribute_model: str = ""
    embedding_model: str = ""

    def __post_init__(self) -> None:
        if self.association_status == "verified":
            self.supports_state = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "VisualEvidence":
        compatible = dict(d)
        compatible.setdefault("association_status", "contextual")
        compatible.setdefault("association_reason", "legacy evidence has no detector association metadata")
        compatible.setdefault("supports_state", compatible.get("association_status") == "verified")
        compatible.setdefault("ingested_at", "")
        compatible.setdefault("detector_model", "")
        compatible.setdefault("attribute_model", "")
        compatible.setdefault("embedding_model", "")
        return VisualEvidence(**compatible)


@dataclass
class Claim:
    """Structured fact extracted from text (brief section 13, stage 6)."""
    entity: str
    attribute: str
    value: str
    event: Optional[str] = None               # e.g. "repaint", "buy"
    temporal_expression: Optional[str] = None  # e.g. "last week"
    resolved_time: Optional[str] = None        # ISO timestamp if the expression was normalised
    confidence: float = 0.0
    source_text: str = ""
    entity_ref: Optional[str] = None            # explicit identity, e.g. "second car"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    """What the memory engine receives: NLP claim + CV evidence, already fused.

    Either side may be missing (text-only or image-only input).
    """
    session_id: str
    timestamp: str                              # ISO string
    claim: Optional[Claim] = None
    text_evidence: Optional[TextEvidence] = None
    visual: Optional[VisualEvidence] = None
    agreement: Optional[float] = None           # cross-modal agreement in [0, 1]
    confidence: float = 0.0                     # fused confidence C_total
    semantic_similarity: Optional[float] = None  # optional, for explainability only
    source: str = "user_interaction"
    ingested_at: str = ""


@dataclass
class MemoryRecord:
    memory_id: str
    session_id: str
    entity: str
    entity_id: str
    attribute: str
    value: str
    timestamp: str
    confidence: float
    status: Status = Status.CURRENT
    previous_memory_id: Optional[str] = None
    event: Optional[str] = None
    conflicting_value: Optional[str] = None     # set when status == CONTRADICTORY
    text_evidence: List[TextEvidence] = field(default_factory=list)
    visual_evidence: List[VisualEvidence] = field(default_factory=list)
    source: str = "user_interaction"
    entity_ref: str = ""
    ingested_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ConflictResolution:
    """Immutable audit record for one human-resolved multimodal disagreement."""
    resolution_id: str
    original_conflict_id: str
    source_memory_id: str
    resulting_memory_id: str
    selected_value: str
    selected_source: str
    text_value: str
    image_value: str
    resolved_at: str
    decision_source: str = "human_verification"
    actor: str = "user"
    rationale: str = ""
    source_session_id: str = ""
    original_text_evidence: List[Dict[str, Any]] = field(default_factory=list)
    original_visual_evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Decision:
    """Inspectable result of one memory update (brief section 55)."""
    action: Action
    memory_id: Optional[str]
    reason: str
    entity_match: float = 0.0
    attribute_match: float = 0.0
    semantic_similarity: Optional[float] = None
    visual_agreement: Optional[float] = None
    temporal_relation: str = "n/a"              # "later" | "earlier" | "same" | "n/a"
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    superseded_memory_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value
        return d
