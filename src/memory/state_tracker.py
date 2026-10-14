"""Entity resolution, state chaining and timelines.

The chain is always *recomputed from timestamps* after every insert. This keeps the
store correct even when sessions arrive out of order (a late-uploaded old photo must
become HISTORICAL, not overwrite the real current state).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..utils import parse_ts
from .schema import MemoryRecord, Status
from .store import MemoryStore


def resolve_entity_id(store: MemoryStore, entity: str, entity_ref: Optional[str] = None) -> str:
    """Map an entity name to a stable id.

    Baseline policy: one instance per entity name ("car" -> car_001). Multiple instances
    (two cars) are a stretch goal; this function is the single place to extend it,
    e.g. by comparing image embeddings of the object across sessions.
    """
    entity = entity.strip().lower()
    ref = (entity_ref or "").strip().lower()
    rows = [row for row in store.entities() if row["entity"] == entity]
    for row in rows:
        if ref and row.get("entity_ref", "") == ref:
            return row["entity_id"]
    if not ref and len(rows) == 1:
        return rows[0]["entity_id"]
    n = len(rows) + 1
    return f"{entity}_{n:03d}"


def _chain_members(store: MemoryStore, entity_id: str, attribute: str) -> List[MemoryRecord]:
    recs = [r for r in store.query(entity_id, attribute) if r.status != Status.CONTRADICTORY]
    # Stable sort by actual time; ties keep insertion order (store.query already ordered by seq).
    return sorted(recs, key=lambda r: parse_ts(r.timestamp))


def rebuild_chain(store: MemoryStore, entity_id: str, attribute: str) -> Optional[MemoryRecord]:
    """Latest state -> CURRENT, everything earlier -> HISTORICAL, relink previous ids.

    Returns the current record (or None if the chain is empty).
    """
    members = _chain_members(store, entity_id, attribute)
    prev: Optional[MemoryRecord] = None
    for rec in members:
        store.set_previous(rec.memory_id, prev.memory_id if prev else None)
        prev = rec
    for rec in members[:-1]:
        if rec.status != Status.HISTORICAL:
            store.set_status(rec.memory_id, Status.HISTORICAL)
    if members:
        if members[-1].status != Status.CURRENT:
            store.set_status(members[-1].memory_id, Status.CURRENT)
        return store.get(members[-1].memory_id)
    return None


def timeline(store: MemoryStore, entity_id: str, attribute: str) -> List[MemoryRecord]:
    """Ordered states, oldest first. Contradictory records are excluded (see conflicts())."""
    return _chain_members(store, entity_id, attribute)


def conflicts(store: MemoryStore, entity_id: str, attribute: str) -> List[MemoryRecord]:
    return [r for r in store.query(entity_id, attribute) if r.status == Status.CONTRADICTORY]


def transitions(store: MemoryStore, entity_id: str, attribute: str) -> List[Dict[str, str]]:
    """Consecutive (old -> new) pairs with the time of the change and its trigger event."""
    chain = timeline(store, entity_id, attribute)
    out = []
    for old, new in zip(chain, chain[1:]):
        out.append(
            {
                "from_value": old.value,
                "to_value": new.value,
                "from_memory_id": old.memory_id,
                "to_memory_id": new.memory_id,
                "changed_at": new.timestamp,
                "event": new.event or "",
            }
        )
    return out
