"""Temporal expression extraction and normalisation (brief section 13, stage 5).

Rule-based on purpose: relative expressions ("last week", "3 days ago") are resolved against
a reference timestamp (the session time), which a generic NER model cannot do.
Dates like 05/10/2026 are read DAY-FIRST (dd/mm/yyyy).
Approximate expressions ("a few days ago") are flagged approximate=True.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from ..utils import parse_ts

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MONTHS["sept"] = 9
_WEEKDAYS = {d.lower(): i for i, d in enumerate(calendar.day_name)}
_NUMWORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "couple": 2, "few": 3, "several": 4,
}
_APPROX_WORDS = {"couple", "few", "several"}
_UNIT = r"(day|week|month|year)s?"
_MON_RX = "|".join(sorted(_MONTHS, key=len, reverse=True))


@dataclass
class TimeExpr:
    text: str
    kind: str                       # "absolute" | "relative" | "vague"
    resolved: Optional[datetime]
    granularity: str = "day"        # day | week | month | year
    approximate: bool = False
    start: int = 0
    end: int = 0

    def iso(self) -> Optional[str]:
        return self.resolved.isoformat(timespec="seconds") if self.resolved else None


def _add_months(dt: datetime, n: int) -> datetime:
    m = dt.month - 1 + n
    y, m = dt.year + m // 12, m % 12 + 1
    return dt.replace(year=y, month=m, day=min(dt.day, calendar.monthrange(y, m)[1]))


def _shift(ref: datetime, n: int, unit: str) -> datetime:
    if unit == "day":
        return ref - timedelta(days=n)
    if unit == "week":
        return ref - timedelta(weeks=n)
    if unit == "month":
        return _add_months(ref, -n)
    return _add_months(ref, -12 * n)


def _safe_date(y: int, m: int, d: int, ref: datetime) -> Optional[datetime]:
    try:
        return datetime(y, m, d, ref.hour, ref.minute, ref.second, tzinfo=ref.tzinfo)
    except ValueError:
        return None


def extract_time_expressions(text: str, reference=None) -> List[TimeExpr]:
    ref = parse_ts(reference)
    out: List[TimeExpr] = []
    spans: List[Tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return all(e <= a or s >= b for a, b in spans)

    def add(m: re.Match, kind: str, resolved, gran="day", approx=False):
        if not free(m.start(), m.end()):
            return
        spans.append((m.start(), m.end()))
        out.append(TimeExpr(m.group(0), kind, resolved, gran, approx, m.start(), m.end()))

    t = text
    # --- absolute -----------------------------------------------------------------
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", t):
        add(m, "absolute", _safe_date(int(m[1]), int(m[2]), int(m[3]), ref))
    for m in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", t):
        add(m, "absolute", _safe_date(int(m[3]), int(m[2]), int(m[1]), ref))  # dd/mm/yyyy
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON_RX})\.?(?:,?\s+(\d{{4}}))?\b", t, re.I):
        y = int(m[3]) if m[3] else ref.year
        add(m, "absolute", _safe_date(y, _MONTHS[m[2].lower()], int(m[1]), ref))
    for m in re.finditer(rf"\b({_MON_RX})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", t, re.I):
        y = int(m[3]) if m[3] else ref.year
        add(m, "absolute", _safe_date(y, _MONTHS[m[1].lower()], int(m[2]), ref))

    # --- relative: N units ago -----------------------------------------------------
    for m in re.finditer(rf"\b(?:(a couple of|a few|several)|(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve))\s+{_UNIT}\s+ago\b", t, re.I):
        if m[1]:
            word = m[1].lower().replace("a ", "").replace(" of", "").strip()
            n, approx = _NUMWORDS.get(word, 3), True
        else:
            raw = m[2].lower()
            n, approx = (int(raw) if raw.isdigit() else _NUMWORDS[raw]), False
        unit = m[3].lower()
        add(m, "relative", _shift(ref, n, unit), unit, approx)

    # --- relative: named days ------------------------------------------------------
    named = [
        (r"\bday before yesterday\b", 2),
        (r"\byesterday\b", 1),
        (r"\blast night\b", 1),
        (r"\b(?:today|tonight|this (?:morning|afternoon|evening)|just now|right now)\b", 0),
    ]
    for rx, back in named:
        for m in re.finditer(rx, t, re.I):
            add(m, "relative", ref - timedelta(days=back), "day")

    # --- relative: last week/month/year, last <weekday>, last/in <month> ------------
    for m in re.finditer(r"\b(last|this|previous)\s+(day|week|month|year)\b", t, re.I):
        unit = m[2].lower()
        back = 0 if m[1].lower() == "this" else 1
        add(m, "relative", _shift(ref, back, unit), unit)
    for m in re.finditer(rf"\blast\s+({'|'.join(_WEEKDAYS)})\b", t, re.I):
        target = _WEEKDAYS[m[1].lower()]
        delta = (ref.weekday() - target) % 7 or 7
        add(m, "relative", ref - timedelta(days=delta), "day")
    for m in re.finditer(rf"\b(?:(last)|in)\s+({_MON_RX})\b(?!\s+\d)", t, re.I):
        mon = _MONTHS[m[2].lower()]
        year = ref.year if mon <= ref.month and not (m[1] and mon == ref.month) else ref.year - 1
        add(m, "relative", _safe_date(year, mon, 1, ref), "month")

    # --- vague (no resolution) -----------------------------------------------------
    for m in re.finditer(r"\b(recently|earlier|a while ago|some time ago|long ago|lately)\b", t, re.I):
        add(m, "vague", None, "day", True)

    return sorted(out, key=lambda e: e.start)


def resolve_event_time(text: str, reference=None) -> Optional[TimeExpr]:
    """First *resolvable* time expression, or None (caller then falls back to session time)."""
    for e in extract_time_expressions(text, reference):
        if e.resolved is not None:
            return e
    return None
