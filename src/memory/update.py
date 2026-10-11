"""Adaptive memory engine: ADD / UPDATE / MERGE / HISTORICAL / CONTRADICTORY / IGNORE.

Deliberately rule-based and independent of any LLM (brief sections 30 and 56).
Input : a fused Candidate (NLP claim + CV evidence).
Output: a Decision that explains what happened and why (brief section 55).

Decision procedure for a candidate with value v at time t
  0. no usable claim / outside tracked domain / too low confidence      -> IGNORE
  1. text and image confidently disagree                                 -> CONTRADICTORY
     (stored with both values; the existing chain is NOT touched)
  2. image-only claim that differs from the state in effect               -> CONTRADICTORY
     (an unconfirmed photo must not silently rewrite memory)
  3. no state exists for (entity, attribute)                              -> ADD
  4. state in effect at t (or the next later state) has value v           -> MERGE evidence
  5. otherwise insert a new state; the chain is recomputed from time:
       t >= newest state time -> UPDATE (old current becomes HISTORICAL)
       t <  newest state time -> HISTORICAL (late/out-of-order evidence)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..utils import iso, parse_ts
from .conflict import detect_cross_modal_conflict, normalize_value, values_equal
from .schema import (
    Action,
    Candidate,
    Claim,
    Decision,
    MemoryRecord,
    Status,
    TextEvidence,
)
from .state_tracker import _chain_members, rebuild_chain, resolve_entity_id
from .store import MemoryStore


class MemoryEngine:
    def __init__(self, store: MemoryStore, cfg: Optional[Dict[str, Any]] = None):
        cfg = cfg or {}
        mem = cfg.get("memory", {})
        nlp = cfg.get("nlp", {})
        self.store = store
        self.min_claim_conf = mem.get("min_claim_confidence", 0.30)
        self.conflict_text_conf = mem.get("conflict_text_conf", 0.60)
        self.conflict_visual_conf = mem.get("conflict_visual_conf", 0.60)
        ents = nlp.get("tracked_entities") or []
        attrs = nlp.get("tracked_attributes") or []
        self.tracked_entities = {e.lower() for e in ents} or None
        self.tracked_attributes = {a.lower() for a in attrs} or None

    # ------------------------------------------------------------------ helpers
    def _effective_claim(self, cand: Candidate) -> Optional[Claim]:
        """Text claim if present, else a claim derived from the image alone."""
        if cand.claim is not None:
            return cand.claim
        v = cand.visual
        if v is not None and v.value and v.label:
            return Claim(
                entity=v.label,
                attribute="color",
                value=v.value,
                confidence=v.confidence,
                source_text="",
            )
        return None

    def _build_record(
        self,
        cand: Candidate,
        claim: Claim,
        entity_id: str,
        ts: str,
        status: Status,
        conflicting_value: Optional[str] = None,
    ) -> MemoryRecord:
        text_ev = cand.text_evidence
        if text_ev is None and claim.source_text:
            text_ev = TextEvidence(
                text=claim.source_text,
                session_id=cand.session_id,
                timestamp=ts,
                confidence=claim.confidence,
            )
        return MemoryRecord(
            memory_id=self.store.next_memory_id(),
            session_id=cand.session_id,
            entity=claim.entity.lower(),
            entity_id=entity_id,
            attribute=claim.attribute.lower(),
            value=normalize_value(claim.value),
            timestamp=ts,
            confidence=cand.confidence if cand.confidence > 0 else claim.confidence,
            status=status,
            event=claim.event,
            conflicting_value=conflicting_value,
            text_evidence=[text_ev] if text_ev else [],
            visual_evidence=[cand.visual] if cand.visual else [],
            source=cand.source,
        )

    # --------------------------------------------------------------- main entry
    def process(self, cand: Candidate) -> Decision:
        claim = self._effective_claim(cand)
        if claim is None:
            return Decision(Action.IGNORE, None, "no extractable claim in text or image")

        entity = claim.entity.strip().lower()
        attribute = claim.attribute.strip().lower()

        if self.tracked_entities is not None and entity not in self.tracked_entities:
            return Decision(Action.IGNORE, None, f"entity '{entity}' is outside the tracked domain")
        if self.tracked_attributes is not None and attribute not in self.tracked_attributes:
            return Decision(Action.IGNORE, None, f"attribute '{attribute}' is outside the tracked domain")
        if claim.confidence < self.min_claim_conf:
            return Decision(
                Action.IGNORE, None, f"claim confidence {claim.confidence:.2f} below {self.min_claim_conf:.2f}"
            )

        ts = iso(cand.timestamp)
        entity_id = resolve_entity_id(self.store, entity)
        members = _chain_members(self.store, entity_id, attribute)
        entity_match = 1.0 if members or self.store.query(entity_id=entity_id) else 0.0
        attribute_match = 1.0 if members else 0.0
        new_value = normalize_value(claim.value)

        base = dict(
            entity_match=entity_match,
            attribute_match=attribute_match,
            semantic_similarity=cand.semantic_similarity,
            visual_agreement=cand.agreement,
            new_value=new_value,
        )

        # --- 1. text vs image conflict inside the same candidate -----------------
        visual_value = detect_cross_modal_conflict(cand, self.conflict_text_conf, self.conflict_visual_conf)
        if visual_value is not None:
            rec = self._build_record(cand, claim, entity_id, ts, Status.CONTRADICTORY, normalize_value(visual_value))
            self.store.insert(rec)
            return Decision(
                Action.CONTRADICTORY,
                rec.memory_id,
                f"text says '{new_value}' but image indicates '{normalize_value(visual_value)}'",
                temporal_relation="n/a",
                previous_value=members[-1].value if members else None,
                **base,
            )

        # --- 3. nothing known yet -> ADD ------------------------------------------
        if not members:
            if cand.claim is None:  # image-only first observation is allowed but flagged in reason
                reason = "first observation, from image only"
            else:
                reason = "no existing memory for this entity/attribute"
            rec = self._build_record(cand, claim, entity_id, ts, Status.CURRENT)
            self.store.insert(rec)
            rebuild_chain(self.store, entity_id, attribute)
            return Decision(Action.ADD, rec.memory_id, reason, temporal_relation="n/a", **base)

        t = parse_ts(ts)
        newest = members[-1]
        in_effect = None
        next_after = None
        for m in members:
            if parse_ts(m.timestamp) <= t:
                in_effect = m
            elif next_after is None:
                next_after = m

        if t > parse_ts(newest.timestamp):
            relation = "later"
        elif t < parse_ts(newest.timestamp):
            relation = "earlier"
        else:
            relation = "same"

        # --- 2. image-only claim that contradicts what we know ---------------------
        reference = in_effect or newest
        if cand.claim is None and not values_equal(reference.value, new_value):
            rec = self._build_record(cand, claim, entity_id, ts, Status.CONTRADICTORY, reference.value)
            self.store.insert(rec)
            return Decision(
                Action.CONTRADICTORY,
                rec.memory_id,
                f"image-only evidence shows '{new_value}' but memory has '{reference.value}'; "
                "needs a confirming statement",
                temporal_relation=relation,
                previous_value=reference.value,
                **base,
            )

        # --- 4. same value already represented -> MERGE ------------------------------
        for target in (in_effect, next_after):
            if target is not None and values_equal(target.value, new_value):
                text_ev = cand.text_evidence
                if text_ev is None and claim.source_text:
                    text_ev = TextEvidence(claim.source_text, cand.session_id, ts, claim.confidence)
                self.store.add_evidence(target.memory_id, text=text_ev, visual=cand.visual)
                new_conf = min(0.99, 1.0 - (1.0 - target.confidence) * (1.0 - max(cand.confidence, 0.0)))
                self.store.set_confidence(target.memory_id, new_conf)
                return Decision(
                    Action.MERGE,
                    target.memory_id,
                    "new evidence supports an existing state; evidence attached, confidence raised",
                    temporal_relation=relation,
                    previous_value=target.value,
                    **base,
                )

        # --- 5. genuinely new state -> UPDATE or HISTORICAL --------------------------
        rec = self._build_record(cand, claim, entity_id, ts, Status.CURRENT)
        previous_current = newest
        self.store.insert(rec)
        rebuild_chain(self.store, entity_id, attribute)

        if relation in ("later", "same"):
            return Decision(
                Action.UPDATE,
                rec.memory_id,
                f"value changed '{previous_current.value}' -> '{new_value}'; old state kept as HISTORICAL",
                temporal_relation=relation,
                previous_value=previous_current.value,
                superseded_memory_id=previous_current.memory_id,
                **base,
            )
        return Decision(
            Action.HISTORICAL,
            rec.memory_id,
            f"evidence is older than the current state; stored as HISTORICAL ('{new_value}')",
            temporal_relation=relation,
            previous_value=previous_current.value,
            **base,
        )
