"""Evidence-grounded answer generation (brief sections 23, 24, 58, 61).

Default: deterministic templates built *only* from retrieved states and their evidence, so an
answer can never contain a value that is not in memory. An optional `llm_fn(prompt) -> str`
can rephrase using the grounded prompt; any failure falls back to the template.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Callable, Dict, List, Optional

from ..memory.schema import MemoryRecord
from ..retrieval.temporal_retriever import RetrievalResult
from .query_parser import Intent, ParsedQuery


def _llm_output_is_grounded(text: str, value: Any) -> bool:
    """Conservative guard for optional free-form rephrasing.

    The deterministic template remains authoritative. A rephrase must mention every
    selected scalar value and may not introduce another known colour value.
    """
    from ..nlp.relation_extraction import COLOR_WORDS
    from ..memory.conflict import normalize_value

    expected = value if isinstance(value, list) else [value]
    expected = {normalize_value(str(v)) for v in expected if v is not None}
    low = text.lower()
    if any(v not in low for v in expected if v not in {"yes", "no"}):
        return False
    tokens = set(re.findall(r"[a-z]+", low))
    mentioned = {normalize_value(c) for c in COLOR_WORDS if c in tokens}
    return not mentioned or mentioned <= expected


@dataclass
class Answer:
    text: str
    value: Any
    confidence: float
    found: bool
    intent: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    states: List[Dict[str, Any]] = field(default_factory=list)
    yes_no: Optional[bool] = None
    note: str = ""
    prompt: str = ""
    status: str = "answered"
    supporting_state_ids: List[str] = field(default_factory=list)
    supporting_evidence_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in {"answered", "uncertain", "abstained"}:
            raise ValueError(f"invalid answer status: {self.status}")
        if not self.found and self.status == "answered":
            self.status = "abstained"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _d(ts: Optional[str]) -> str:
    return (ts or "")[:10]


def _ev(e: Optional[str]) -> str:
    return (e or "").replace("_", " ")


def _roles(res: RetrievalResult) -> Dict[str, str]:
    roles: Dict[str, str] = {}
    n = len(res.chain)
    for i, rec in enumerate(res.chain):
        roles[rec.memory_id] = "current" if i == n - 1 else ("original" if i == 0 else "historical")
    for rec in res.conflicts:
        roles[rec.memory_id] = "conflicting"
    return roles


def evidence_items(res: RetrievalResult, include_conflicts: bool) -> List[Dict[str, Any]]:
    roles = _roles(res)
    recs: List[MemoryRecord] = []
    for r in list(res.records) + (list(res.conflicts) if include_conflicts else []):
        if all(r.memory_id != x.memory_id for x in recs):
            recs.append(r)
    items: List[Dict[str, Any]] = []
    hits_by_record: Dict[str, List[Any]] = {}
    for hit in res.image_hits:
        hits_by_record.setdefault(hit["record"].memory_id, []).append(hit["evidence"])
    for rec in recs:
        base = {"memory_id": rec.memory_id, "role": roles.get(rec.memory_id, "supporting"), "value": rec.value}
        for index, te in enumerate(rec.text_evidence):
            items.append({**base, "modality": "text", "text": te.text, "session_id": te.session_id,
                          "timestamp": te.timestamp, "confidence": te.confidence,
                          "evidence_id": f"{rec.memory_id}:text:{index}", "supports_state": True})
        for ve in hits_by_record.get(rec.memory_id, []):
            items.append({**base, "modality": "image", "image_id": ve.image_id, "image_path": ve.image_path,
                          "visual_value": ve.value, "timestamp": ve.timestamp or rec.timestamp,
                          "confidence": ve.confidence,
                          "association_status": ve.association_status,
                          "association_reason": ve.association_reason,
                          "supports_state": ve.supports_state,
                          "evidence_id": ve.image_id or f"{rec.memory_id}:image",
                          "session_id": ve.session_id or (
                              ve.image_id[4:] if ve.image_id.startswith("IMG_") else "")})
    return sorted(items, key=lambda x: (x.get("timestamp") or "", x["modality"]))


def build_grounded_prompt(parsed: ParsedQuery, res: RetrievalResult, items: List[Dict[str, Any]]) -> str:
    """Prompt from the brief (section 61): the model may only use what is listed here."""
    states = "\n".join(
        f"- {r.memory_id}: {r.entity}.{r.attribute} = {r.value} ({r.status.value}, since {r.timestamp}, "
        f"confidence {r.confidence:.2f})" for r in res.chain
    ) or "(none)"
    evid = "\n".join(
        f"- [{i['role']}] {i['modality']}: " + (f"\"{i['text']}\"" if i["modality"] == "text" else i["image_id"])
        + f" @ {i.get('timestamp', '')}" for i in items
    ) or "(none)"
    return (
        "You are an evidence-grounded assistant.\n\n"
        f"User question:\n{parsed.raw}\n\n"
        f"Memory timeline (oldest first):\n{states}\n\n"
        f"Selected evidence:\n{evid}\n\n"
        "Instructions:\n1. Answer only using the provided evidence.\n"
        "2. Distinguish current and historical information.\n3. Do not invent missing facts.\n"
        "4. If evidence conflicts, state the conflict.\n5. Mention uncertainty when confidence is low.\n"
        "6. Identify the evidence supporting the answer.\n"
    )


class AnswerGenerator:
    def __init__(self, llm_fn: Optional[Callable[[str], str]] = None):
        self.llm_fn = llm_fn

    # ------------------------------------------------------------------ templates
    def _template(self, parsed: ParsedQuery, res: RetrievalResult, items: List[Dict[str, Any]]) -> str:
        e = res.entity or "item"
        v, I = res.actual, parsed.intent
        cur = res.chain[-1].value if res.chain else None
        if I == Intent.ORIGINAL:
            base = f"Your {e} was originally {v}."
        elif I == Intent.PREVIOUS:
            if parsed.reference_value:
                base = f"Before it became {parsed.reference_value}, your {e} was {v}."
            elif parsed.reference_event:
                base = f"Before the '{_ev(parsed.reference_event)}' event, your {e} was {v}."
            else:
                base = f"Before it became {cur}, your {e} was {v}."
        elif I == Intent.AFTER:
            if parsed.reference_value:
                base = f"After it was {parsed.reference_value}, your {e} became {v}."
            else:
                base = f"After the '{_ev(parsed.reference_event)}' event, your {e} was {v}."
        elif I == Intent.CHANGE:
            parts = [f"{t['from_value']} to {t['to_value']} on {_d(t['changed_at'])}" for t in res.transitions]
            base = f"Your {e} changed from " + "; then from ".join(parts) + "."
        elif I == Intent.WHEN:
            base = f"Your {e} became {v} on {_d(res.time)}." + (f" ({res.note})" if res.note else "")
        elif I == Intent.EVIDENCE:
            if isinstance(v, list):
                head = f"Here is everything I have stored about your {e}:"
            else:
                head = f"I believe your {e} is {v} because of:" if res.records and res.records[0] is res.chain[-1] \
                    else f"I have your {e} recorded as {v} because of:"
            lines = []
            for it in items:
                if it["role"] == "conflicting":
                    continue
                if it["modality"] == "text":
                    lines.append(f"- text ({it['session_id']}, {_d(it['timestamp'])}): \"{it['text']}\"")
                else:
                    qualifier = "" if it.get("association_status") == "verified" else " (contextually associated; detector did not verify entity)"
                    lines.append(f"- image {it['image_id']} ({_d(it['timestamp'])}), looks {it['visual_value']}{qualifier}")
            base = head + "\n" + "\n".join(lines)
        elif I == Intent.HISTORY:
            base = "Timeline: " + " → ".join(f"{r.value} ({_d(r.timestamp)})" for r in res.chain)
        elif I == Intent.AS_OF:
            base = f"On {_d(parsed.time)}, your {e} was {v}."
        else:
            base = f"Your {e} is currently {v}."
        if res.yes_no is not None:
            base = ("Yes. " if res.yes_no else "No. ") + base
        if res.conflicts and I in (Intent.CURRENT, Intent.EVIDENCE):
            c = res.conflicts[-1]
            base += (f" Note: conflicting evidence was also recorded ('{c.value}' vs "
                     f"'{c.conflicting_value}'); it was not applied.")
        return base

    # ----------------------------------------------------------------- main entry
    def generate(self, parsed: ParsedQuery, res: RetrievalResult) -> Answer:
        if not res.found:
            note = res.note or "I could not find a matching memory."
            extra = ""
            if res.conflicts:
                c = res.conflicts[-1]
                extra = f" Conflicting evidence exists ('{c.value}' vs '{c.conflicting_value}')."
            return Answer(f"I don't have enough stored information to answer that. {note}.{extra}".replace("..", "."),
                          None, 0.0, False, parsed.intent.value, note=note,
                          evidence=evidence_items(res, True) if res.conflicts else [], status="abstained")

        include_conf = parsed.intent in (Intent.CURRENT, Intent.EVIDENCE)
        items = evidence_items(res, include_conf)
        text = self._template(parsed, res, items)
        prompt = build_grounded_prompt(parsed, res, items)
        if self.llm_fn is not None:
            try:
                out = self.llm_fn(prompt)
                if out and out.strip() and _llm_output_is_grounded(out, res.actual):
                    text = out.strip()
            except Exception as exc:
                print(f"[answer] LLM failed ({exc.__class__.__name__}); using template answer")
        conf = min((r.confidence for r in res.records), default=0.5)
        if res.conflicts and include_conf:
            conf *= 0.8
        supporting = [i for i in items if i.get("supports_state", True) and i.get("role") != "conflicting"]
        status = "uncertain" if (res.conflicts and include_conf) else "answered"
        return Answer(
            text=text, value=res.value, confidence=round(conf, 3), found=True, intent=parsed.intent.value,
            evidence=items, states=[r.to_dict() for r in res.records], yes_no=res.yes_no,
            note=res.note, prompt=prompt, status=status,
            supporting_state_ids=[r.memory_id for r in res.records],
            supporting_evidence_ids=[i["evidence_id"] for i in supporting],
        )
