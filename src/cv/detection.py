"""Object detection (brief section 14, stage 3).

YOLO (ultralytics) when available; otherwise no detections are returned and the pipeline
falls back to analysing the whole image. COCO has no 'laptop skin' or 'shirt' classes etc.,
so detection only *localises* objects; the attribute (colour) is computed separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from ..config import load_config, resolve_path

# COCO label -> tracked entity name used by the memory
COCO_TO_ENTITY: Dict[str, str] = {
    "car": "car", "truck": "car", "bus": "car",
    "motorcycle": "bike", "bicycle": "bike",
    "laptop": "laptop",
    "cell phone": "phone",
    "potted plant": "plant",
}


@dataclass
class Detection:
    label: str
    entity: Optional[str]            # tracked entity name, or None for unmapped/fallback
    bbox: List[float]                # [x1, y1, x2, y2] in pixels
    confidence: float
    source: str = "yolo"             # "yolo" | "fallback"

    @property
    def area(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0]) * max(0.0, self.bbox[3] - self.bbox[1])

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "entity": self.entity, "bbox": self.bbox,
                "confidence": round(self.confidence, 3), "source": self.source}


class ObjectDetector:
    def __init__(self, cfg: Optional[Dict[str, Any]] = None, force_fallback: bool = False):
        cv = (cfg or load_config()).get("cv", {})
        self.conf = float(cv.get("yolo_conf", 0.25))
        self.weights = cv.get("yolo_weights", "yolov8n.pt")
        self.model = None
        self.kind = cv.get('detector_backend','yolo')
        self.general_categories = bool(cv.get('general_categories',False))
        self.model_identity = ''
        if self.kind == 'ssdlite':
            self.weights = cv.get('detector_weights_path','models/local/ssdlite320.pt')
            local_weights = Path(resolve_path(self.weights))
            if force_fallback or not local_weights.is_file():return
            try:
                import torch
                from torchvision.models.detection import ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights
                self.labels = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1.meta['categories']
                self.model = ssdlite320_mobilenet_v3_large(weights=None,weights_backbone=None).eval()
                self.model.load_state_dict(torch.load(str(local_weights),map_location='cpu',weights_only=True))
                import hashlib
                self.model_identity = 'ssdlite320-coco:'+hashlib.sha256(local_weights.read_bytes()).hexdigest()
            except Exception:self.model=None
            return
        if cv.get('local_files_only'):
            local_weights = Path(resolve_path(self.weights))
            if not local_weights.is_file():
                return
            self.weights = str(local_weights)
        if not force_fallback:
            try:
                from ultralytics import YOLO  # heavy import kept local

                self.model = YOLO(self.weights)
            except Exception as exc:
                print(f"[detection] YOLO unavailable ({exc.__class__.__name__}); using whole-image fallback")

    @property
    def backend(self) -> str:
        return self.kind if self.model is not None else "none (whole-image fallback)"

    def detect(self, img: Image.Image) -> List[Detection]:
        if self.model is None:
            return []
        out: List[Detection] = []
        try:
            if self.kind == 'ssdlite':
                import torch
                from torchvision.transforms.functional import to_tensor
                with torch.inference_mode():res=self.model([to_tensor(img)])[0]
                for box,score,label in zip(res['boxes'],res['scores'],res['labels']):
                    name=self.labels[int(label)]
                    if float(score) >= self.conf and name not in {'N/A','__background__'}:
                        entity=(name if self.general_categories and name in {'bus','truck'} else
                                COCO_TO_ENTITY.get(name,name if self.general_categories else None))
                        out.append(Detection(name,entity,[float(x) for x in box],float(score),'ssdlite'))
                return sorted(out,key=lambda d:d.confidence,reverse=True)[:20]
            res = self.model.predict(img, conf=self.conf, verbose=False)[0]
            names = res.names
            for b in res.boxes:
                label = names[int(b.cls[0])]
                out.append(
                    Detection(
                        label=label,
                        entity=COCO_TO_ENTITY.get(label,label if self.general_categories else None),
                        bbox=[float(v) for v in b.xyxy[0].tolist()],
                        confidence=float(b.conf[0]),
                    )
                )
        except Exception as exc:
            print(f"[detection] inference failed ({exc.__class__.__name__}); using whole-image fallback")
            return []
        return sorted(out, key=lambda d: d.confidence, reverse=True)


def full_image_detection(img: Image.Image, entity: Optional[str] = None) -> Detection:
    w, h = img.size
    return Detection("object", entity, [0.0, 0.0, float(w), float(h)], 0.30, "fallback")


def select_primary(
    dets: List[Detection], img: Image.Image, preferred_entity: Optional[str] = None
) -> Detection:
    """Pick the detection the text is (most likely) talking about.

    preferred_entity given  -> the largest-confident detection of that entity, else the whole
                               image (never a *different* object: we trust the text on identity)
    no preferred entity     -> the most confident tracked-entity detection, else whole image
    """
    mapped = [d for d in dets if d.entity]
    if preferred_entity:
        match = [d for d in mapped if d.entity == preferred_entity]
        if match:
            return max(match, key=lambda d: d.confidence * max(d.area, 1.0))
        return full_image_detection(img, preferred_entity)
    if mapped:
        return max(mapped, key=lambda d: d.confidence)
    return full_image_detection(img, None)


def crop_to_bbox(img: Image.Image, bbox: List[float], pad: float = 0.02) -> Image.Image:
    w, h = img.size
    x1, y1, x2, y2 = bbox
    px, py = (x2 - x1) * pad, (y2 - y1) * pad
    box = (max(0, int(x1 - px)), max(0, int(y1 - py)), min(w, int(x2 + px)), min(h, int(y2 + py)))
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        return img
    return img.crop(box)
