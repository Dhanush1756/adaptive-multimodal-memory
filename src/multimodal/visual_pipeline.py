"""CV pipeline: image -> ImageAnalysis (brief section 28).

    load -> quality -> YOLO detect -> pick the object the text talks about -> crop
         -> colour (HSV + CLIP/head) -> embedding
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import load_config
from ..cv.attributes import VisualAttributeExtractor
from ..cv.detection import ObjectDetector, crop_to_bbox, full_image_detection, select_primary
from ..cv.embeddings import ImageEmbedder, get_clip
from ..cv.preprocessing import load_image, quality_report
from .evidence import ImageAnalysis


class VisualPipeline:
    def __init__(self, cfg: Optional[Dict[str, Any]] = None, light: bool = False):
        self.cfg = cfg or load_config()
        self.clip = get_clip(self.cfg, force_fallback=light)
        self.detector = ObjectDetector(self.cfg, force_fallback=light)
        self.attributes = VisualAttributeExtractor(self.cfg, clip=self.clip)
        self.embedder = ImageEmbedder(self.clip)

    def status(self) -> Dict[str, str]:
        return {"detector": self.detector.backend, "color": self.attributes.method,
                "image_embedding": self.embedder.name, **self.attributes.provenance()}

    def analyze(self, image: Any, preferred_entity: Optional[str] = None) -> ImageAnalysis:
        img = load_image(image)
        quality = quality_report(img)
        dets = self.detector.detect(img)
        mapped = [d for d in dets if d.entity]
        if preferred_entity:
            matches = [d for d in mapped if d.entity == preferred_entity]
            if len(matches) == 1:
                primary, association_status, association_reason = matches[0], "verified", "one detector result matches the claim entity"
            elif len(matches) > 1:
                primary, association_status, association_reason = select_primary(matches, img), "ambiguous", "multiple detected objects match the claim entity"
            elif not dets:
                primary, association_status, association_reason = full_image_detection(img, preferred_entity), "contextual", "detector unavailable; image was submitted with this claim"
            else:
                primary, association_status, association_reason = full_image_detection(img), "unmatched", "detector found no object matching the claim entity"
        elif mapped:
            primary, association_status, association_reason = select_primary(mapped, img), "verified", "detected object selected without a text entity"
        else:
            primary, association_status, association_reason = full_image_detection(img), "unmatched", "no tracked object was detected"
        crop = crop_to_bbox(img, primary.bbox) if primary.source != "fallback" else img
        attrs = self.attributes.extract(
            crop, entity=primary.entity or preferred_entity,
            subtract_background=(primary.source == "fallback"),
        )
        # visual confidence = colour confidence, mildly scaled by detector confidence and quality
        conf = attrs["confidence"] * (0.8 + 0.2 * primary.confidence)
        if "blurry" in quality["flags"] or "dark" in quality["flags"]:
            conf *= 0.9
        return ImageAnalysis(
            image=img,
            detection=primary,
            color=attrs["color"],
            color_confidence=attrs["confidence"],
            confidence=round(min(conf, 0.99), 3),
            method=attrs["method"],
            embedding=self.embedder.embed(crop),
            quality=quality,
            distribution=attrs.get("distribution", {}),
            association_status=association_status,
            association_reason=association_reason,
            detector_model=self.detector.backend,
            embedding_model=self.embedder.name,
            classifier={**self.attributes.provenance(), "applied": attrs["method"] == "hsv+head"},
        )
