"""CV tests that need no model downloads (HSV colour, fallback detection, embeddings)."""
import random

import numpy as np
import pytest
from PIL import Image

from src.cv.attributes import hsv_color
from src.cv.embeddings import color_histogram_embedding
from src.cv.detection import crop_to_bbox, full_image_detection
from src.data.synthetic import COLOR_RGB, ENTITIES, render_object
from src.multimodal.visual_pipeline import VisualPipeline
from src.config import load_config


@pytest.mark.parametrize("name", ["red", "blue", "green", "yellow", "black", "white", "orange", "purple"])
def test_hsv_on_flat_colours(name):
    img = Image.new("RGB", (64, 64), COLOR_RGB[name])
    assert hsv_color(img).color == name


@pytest.mark.parametrize("entity", ENTITIES)
@pytest.mark.parametrize("color", ["red", "blue", "black", "white", "green"])
def test_synthetic_objects_are_read_correctly(entity, color):
    img = render_object(entity, color, random.Random(1))
    assert hsv_color(img, subtract_background=True).color == color


def test_light_pipeline_reports_colour_and_entity_hint():
    vp = VisualPipeline(load_config(), light=True)
    an = vp.analyze(render_object("car", "blue", random.Random(2)), preferred_entity="car")
    assert an.color == "blue" and an.detection.source == "fallback"
    assert 0.0 < an.confidence <= 0.99
    assert len(an.embedding) > 0


def test_histogram_embedding_is_normalised_and_colour_sensitive():
    a = color_histogram_embedding(Image.new("RGB", (32, 32), (200, 30, 30)))
    b = color_histogram_embedding(Image.new("RGB", (32, 32), (30, 30, 200)))
    assert abs(np.linalg.norm(a) - 1.0) < 1e-5
    assert float(a @ a) > float(a @ b)


def test_crop_and_fallback_detection():
    img = Image.new("RGB", (100, 80))
    det = full_image_detection(img, "car")
    assert det.bbox == [0.0, 0.0, 100.0, 80.0] and det.entity == "car"
    assert crop_to_bbox(img, [10, 10, 50, 40]).size[0] >= 40
