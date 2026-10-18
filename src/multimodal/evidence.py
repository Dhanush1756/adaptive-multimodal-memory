"""Intermediate evidence objects produced before the memory engine (brief section 15)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from ..cv.detection import Detection


@dataclass
class ImageAnalysis:
    """Everything the CV pipeline learned about one image."""
    image: Image.Image
    detection: Detection
    color: str
    color_confidence: float
    confidence: float                       # visual confidence after detection/quality adjustment
    method: str
    embedding: np.ndarray
    quality: Dict[str, Any] = field(default_factory=dict)
    distribution: Dict[str, float] = field(default_factory=dict)
    association_status: str = "contextual"
    association_reason: str = ""
    detector_model: str = ""
    embedding_model: str = ""
    classifier: Dict[str, Any] = field(default_factory=dict)

    @property
    def entity(self) -> Optional[str]:
        return self.detection.entity

    def summary(self) -> Dict[str, Any]:
        return {
            "detection": self.detection.to_dict(),
            "color": self.color,
            "color_confidence": self.color_confidence,
            "visual_confidence": self.confidence,
            "method": self.method,
            "quality": self.quality,
            "association_status": self.association_status,
            "association_reason": self.association_reason,
            "detector_model": self.detector_model,
            "attribute_model": self.method,
            "embedding_model": self.embedding_model,
            "classifier": self.classifier,
        }
