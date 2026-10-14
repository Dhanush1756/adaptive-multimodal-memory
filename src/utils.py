"""Small shared helpers."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np


def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def parse_ts(ts) -> datetime:
    """Accept None / datetime / date / ISO string and return a datetime."""
    if ts is None:
        return datetime.now()
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, date):
        return datetime(ts.year, ts.month, ts.day)
    return datetime.fromisoformat(str(ts))


def iso(ts) -> str:
    return parse_ts(ts).isoformat(timespec="seconds")
