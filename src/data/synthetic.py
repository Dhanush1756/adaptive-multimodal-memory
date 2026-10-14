"""Controlled synthetic benchmark (brief section 34-B / 35).

Each scenario = one entity whose colour changes over several sessions. A session has text
and/or an image. Ground truth (state chain, per-session memory action, question answers and
supporting sessions) is known by construction, so every metric is exact.

Session kinds produced
  ADD / UPDATE       main state sessions (text+image, text only, or - first session - image only)
  UPDATE (skin)      laptop/phone: "put a <c> skin on my laptop" ... "removed the skin" (value-less
                     text; the colour must come from the image) -> returns to the original colour
  MERGE              same value confirmed again (text+image, image only, or text only)
  CONTRADICTORY      text states one colour while the image shows another, OR an image-only
                     photo that differs from memory (unconfirmed)
  IGNORE             irrelevant text (no entity/colour)

Images are simple synthetic renderings (flat colour objects on a background, lighting jitter,
Gaussian noise). They are an easy domain: use them to test the *memory logic*, then evaluate the
CV module on real photos (docs/training.md). Never present synthetic CV accuracy as real-world.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw

ENTITIES = ["car", "laptop", "phone", "shirt"]
SKINNABLE = {"laptop", "phone"}
SYNTH_COLORS = ["red", "blue", "black", "white", "green", "yellow", "silver", "orange", "purple", "brown", "pink"]
COLOR_RGB = {
    "red": (200, 30, 35), "blue": (30, 70, 200), "black": (25, 25, 28), "white": (240, 240, 240),
    "green": (30, 150, 60), "yellow": (235, 205, 40), "silver": (150, 152, 158),
    "orange": (240, 130, 30), "purple": (130, 50, 160), "brown": (110, 70, 40), "pink": (240, 120, 180),
}
T0 = datetime(2026, 10, 1, 10, 0, 0)

ADD_TPL = {
    "car": ["I bought a {c} car.", "My car is {c}.", "I just got a {c} Tesla.", "I have a {c} car."],
    "laptop": ["I bought a {c} laptop.", "My laptop is {c}.", "I have a {c} laptop."],
    "phone": ["I bought a {c} phone.", "My phone is {c}.", "I have a {c} phone."],
    "shirt": ["I bought a {c} shirt.", "My shirt is {c}.", "I have a {c} shirt."],
}
CHANGE_TPL = {
    "car": ["I repainted my car {c}.", "I got my car repainted {c}.", "I changed my car to {c}.", "My car is now {c}."],
    "laptop": ["I put a {c} skin on my laptop.", "I changed my laptop to {c}.", "My laptop is now {c}."],
    "phone": ["I put a {c} skin on my phone.", "I changed my phone to {c}.", "My phone is now {c}."],
    "shirt": ["I dyed my shirt {c}.", "I changed my shirt to {c}.", "My shirt is now {c}."],
}
IGNORE_TXT = ["I like pizza.", "The weather is nice today.", "Had a great lunch with friends."]


# --------------------------------------------------------------------------- rendering
def _clip(v: float) -> int:
    return max(0, min(255, int(v)))


def _background(color: str, rng: random.Random):
    if color in ("white", "silver"):
        return rng.choice([(45, 55, 65), (60, 50, 45), (35, 45, 40)])
    if color == "black":
        return rng.choice([(225, 225, 215), (205, 215, 225), (215, 205, 200)])
    return rng.choice([(225, 225, 215), (205, 215, 225), (215, 205, 200), (190, 190, 190)])


def _draw_car(d, body, dark, dx, dy):
    d.rounded_rectangle([40 + dx, 120 + dy, 280 + dx, 180 + dy], radius=14, fill=body)
    d.polygon([(90 + dx, 122 + dy), (122 + dx, 78 + dy), (220 + dx, 78 + dy), (252 + dx, 122 + dy)], fill=body)
    glass = (95, 105, 115)
    d.polygon([(100 + dx, 118 + dy), (126 + dx, 86 + dy), (160 + dx, 86 + dy), (160 + dx, 118 + dy)], fill=glass)
    d.polygon([(166 + dx, 118 + dy), (166 + dx, 86 + dy), (216 + dx, 86 + dy), (240 + dx, 118 + dy)], fill=glass)
    for cx in (90, 230):
        d.ellipse([cx - 22 + dx, 163 + dy, cx + 22 + dx, 207 + dy], fill=(20, 20, 22))
        d.ellipse([cx - 8 + dx, 177 + dy, cx + 8 + dx, 193 + dy], fill=(120, 120, 125))


def _draw_laptop(d, body, dark, dx, dy):
    d.rounded_rectangle([70 + dx, 40 + dy, 250 + dx, 150 + dy], radius=8, fill=body)
    light = tuple(_clip(c * 1.15 + 6) for c in body)
    d.ellipse([150 + dx, 88 + dy, 170 + dx, 108 + dy], fill=light)
    d.polygon([(40 + dx, 160 + dy), (280 + dx, 160 + dy), (262 + dx, 188 + dy), (58 + dx, 188 + dy)], fill=dark)


def _draw_phone(d, body, dark, dx, dy):
    d.rounded_rectangle([120 + dx, 20 + dy, 200 + dx, 220 + dy], radius=14, fill=body)
    for i in range(3):
        d.ellipse([130 + dx + i * 14, 30 + dy, 142 + dx + i * 14, 42 + dy], fill=(20, 20, 22))


def _draw_shirt(d, body, dark, dx, dy):
    pts = [(110, 40), (210, 40), (250, 80), (225, 105), (205, 90), (205, 200), (115, 200), (115, 90), (95, 105), (70, 80)]
    d.polygon([(x + dx, y + dy) for x, y in pts], fill=body)


_DRAW = {"car": _draw_car, "laptop": _draw_laptop, "phone": _draw_phone, "shirt": _draw_shirt}


def render_object(entity: str, color: str, rng: Optional[random.Random] = None, size=(320, 240)) -> Image.Image:
    rng = rng or random.Random(0)
    base = COLOR_RGB[color]
    light = rng.uniform(0.9, 1.06)
    body = tuple(_clip(c * light) for c in base)
    dark = tuple(_clip(c * 0.8) for c in body)
    bg = _background(color, rng)
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    sign = 1 if sum(bg) < 400 else -1
    for y in range(size[1]):
        shade = sign * int(10 * y / size[1])
        d.line([(0, y), (size[0], y)], fill=tuple(_clip(c + shade) for c in bg))
    _DRAW[entity](d, body, dark, rng.randint(-12, 12), rng.randint(-8, 8))
    arr = np.asarray(img).astype(np.float32)
    arr += np.random.RandomState(rng.randint(0, 2 ** 31 - 1)).normal(0, 4, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def render_session_image(session: Dict[str, Any]) -> Optional[Image.Image]:
    """Image of a session: the saved PNG if present, else re-rendered from its spec."""
    if session.get("image") and Path(session["image"]).exists():
        return Image.open(session["image"]).convert("RGB")
    spec = session.get("image_spec")
    if spec:
        return render_object(spec["entity"], spec["color"], random.Random(spec["seed"]))
    return None


# --------------------------------------------------------------------------- scenarios
def _other_color(rng: random.Random, *avoid: str) -> str:
    return rng.choice([c for c in SYNTH_COLORS if c not in avoid])


def generate_scenario(idx: int, rng: random.Random) -> Dict[str, Any]:
    entity = rng.choice(ENTITIES)
    roundtrip = entity in SKINNABLE and rng.random() < 0.3
    if roundtrip:
        a = rng.choice(SYNTH_COLORS)
        seq = [a, _other_color(rng, a), a]
    else:
        seq = [rng.choice(SYNTH_COLORS)]
        for _ in range(rng.randint(1, 3)):
            seq.append(_other_color(rng, seq[-1]))

    sessions: List[Dict[str, Any]] = []
    states: List[Dict[str, Any]] = []
    t = T0 + timedelta(days=rng.randint(0, 5))
    sc_id = f"SC{idx:04d}"

    def add_session(ts, text, img_color, action, text_value, kind, event_time=None, state_value=None):
        sid = f"S{len(sessions) + 1:02d}"
        spec = {"entity": entity, "color": img_color, "seed": rng.randint(0, 10 ** 9)} if img_color else None
        sessions.append({
            "session_id": sid, "timestamp": ts.isoformat(), "text": text, "image": None, "image_spec": spec,
            "gt": {"entity": entity, "action": action, "kind": kind, "text_value": text_value,
                   "image_color": img_color, "value": state_value,
                   "event_time": (event_time or ts).isoformat()},
        })
        return sid

    for i, color in enumerate(seq):
        if i > 0:
            t += timedelta(days=rng.randint(4, 15))
        action = "ADD" if i == 0 else "UPDATE"
        unskin = roundtrip and i == 2
        skin = roundtrip and i == 1
        event_time = t
        if unskin:
            text, img, tv, kind = f"I removed the skin from my {entity}.", color, None, "unskin"
        elif i == 0 and rng.random() < 0.15:
            text, img, tv, kind = f"Here is a photo of my {entity}.", color, None, "image_only_first"
        else:
            tpl = "I put a {c} skin on my {e}." if skin else rng.choice(ADD_TPL[entity] if i == 0 else CHANGE_TPL[entity])
            text, tv = tpl.format(c=color, e=entity), color
            if rng.random() < 0.25:
                back, phrase = rng.choice([(1, "yesterday"), (2, "2 days ago")])
                text = text.rstrip(".") + f" {phrase}."
                event_time = t - timedelta(days=back)
            img = color if rng.random() < (0.6 / 0.85 if i > 0 else 0.6 / 0.85) else None
            kind = "text_image" if img else "text_only"
        sid = add_session(t, text, img, action, tv, kind, event_time, color)
        states.append({"value": color, "start": event_time, "sessions": [sid]})

        # --- follow-up sessions inside the same state (all strictly before the next change) ---
        if rng.random() < 0.35:
            v = rng.random()
            if v < 0.4:
                s2 = add_session(t + timedelta(hours=12), f"My {entity} is still {color}.", color, "MERGE", color, "merge_text_image")
            elif v < 0.7:
                s2 = add_session(t + timedelta(hours=12), f"Another photo of my {entity}.", color, "MERGE", None, "merge_image_only")
            else:
                s2 = add_session(t + timedelta(hours=12), f"My {entity} is still {color}.", None, "MERGE", color, "merge_text_only")
            states[-1]["sessions"].append(s2)
        if rng.random() < 0.20:
            add_session(t + timedelta(hours=20), rng.choice(IGNORE_TXT), None, "IGNORE", None, "ignore")
        r = rng.random()
        if r < 0.15:
            wrong = _other_color(rng, color)
            add_session(t + timedelta(hours=30), f"My {entity} is {wrong}.", color, "CONTRADICTORY", wrong, "conflict_text_vs_image")
        elif r < 0.25:
            add_session(t + timedelta(hours=30), f"Here is a photo of my {entity}.", _other_color(rng, color),
                        "CONTRADICTORY", None, "unconfirmed_image")

    return {"scenario_id": sc_id, "entity": entity, "sessions": sessions,
            "states": [{"value": s["value"], "start": s["start"].isoformat(), "sessions": s["sessions"]} for s in states],
            "queries": build_queries(entity, states, rng)}


def _d(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def build_queries(entity: str, states: List[Dict[str, Any]], rng: random.Random) -> List[Dict[str, Any]]:
    n, cur, first = len(states), states[-1], states[0]
    qs: List[Dict[str, Any]] = []

    def add(kind, question, intent, answer, ev=None):
        qs.append({"kind": kind, "question": question, "intent": intent, "answer": answer,
                   "evidence_sessions": list(ev) if ev else []})

    add("current", f"What color is my {entity} now?", "CURRENT", cur["value"], cur["sessions"])
    add("original", f"What color was my {entity} originally?", "ORIGINAL", first["value"], first["sessions"])
    add("evidence", f"How do you know my {entity} is {cur['value']}?", "EVIDENCE", cur["value"], cur["sessions"])
    add("history", f"Show me the history of my {entity}'s color.", "HISTORY", [s["value"] for s in states])
    x = first["value"] if rng.random() < 0.5 else _other_color(rng, first["value"])
    add("bool_original", f"Was my {entity} originally {x}?", "ORIGINAL", "yes" if x == first["value"] else "no")
    y = cur["value"] if rng.random() < 0.5 else _other_color(rng, cur["value"])
    add("bool_current", f"Is my {entity} {y} now?", "CURRENT", "yes" if y == cur["value"] else "no")
    j = rng.randrange(n)
    add("as_of", f"What color was my {entity} on {_d(states[j]['start'])}?", "AS_OF", states[j]["value"], states[j]["sessions"])
    if n >= 2:
        prev = states[-2]
        add("previous", f"What color was my {entity} before?", "PREVIOUS", prev["value"], prev["sessions"])
        add("previous_ref", f"What color was my {entity} before it became {cur['value']}?", "PREVIOUS", prev["value"], prev["sessions"])
        add("change", f"What changed about my {entity}?", "CHANGE", f"{prev['value']}->{cur['value']}")
        add("when_last", f"When did my {entity}'s color change?", "WHEN", _d(cur["start"]))
        add("when_value", f"When did my {entity} become {cur['value']}?", "WHEN", _d(cur["start"]))
        z = prev["value"] if rng.random() < 0.5 else _other_color(rng, prev["value"])
        add("bool_previous_ref", f"Was my {entity} {z} before it became {cur['value']}?", "PREVIOUS",
            "yes" if z == prev["value"] else "no")
    if n >= 3:
        anchor = first["value"]
        i = max(k for k in range(n - 1) if states[k]["value"] == anchor)
        add("after", f"What color did my {entity} become after {anchor}?", "AFTER", states[i + 1]["value"], states[i + 1]["sessions"])
    return qs


def generate_dataset(n: int, seed: int = 0, out_dir: Optional[str] = None, save_images: bool = False) -> List[Dict[str, Any]]:
    """n scenarios. With out_dir: writes scenarios.jsonl (+ PNGs if save_images)."""
    rng = random.Random(seed)
    data = [generate_scenario(i, rng) for i in range(n)]
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if save_images:
            (out / "images").mkdir(exist_ok=True)
            for sc in data:
                for s in sc["sessions"]:
                    img = render_session_image(s)
                    if img is not None:
                        p = out / "images" / f"{sc['scenario_id']}_{s['session_id']}.png"
                        img.save(p)
                        s["image"] = str(p)
        with open(out / "scenarios.jsonl", "w", encoding="utf-8") as f:
            for sc in data:
                f.write(json.dumps(sc) + "\n")
    return data


def load_dataset(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if p.is_dir():
        p = p / "scenarios.jsonl"
    with open(p, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
