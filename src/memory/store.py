"""SQLite-backed structured memory store (brief sections 25 and 60).

States live in one table; evidence lists and embeddings are JSON columns. This is
deliberately simple: easy to inspect with any SQLite browser and easy to explain in a viva.
Use db_path=":memory:" for tests.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .schema import ConflictResolution, MemoryRecord, Status, TextEvidence, VisualEvidence

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    memory_id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL,
    session_id TEXT,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    confidence REAL,
    status TEXT NOT NULL,
    previous_memory_id TEXT,
    event TEXT,
    conflicting_value TEXT,
    text_evidence TEXT,
    visual_evidence TEXT,
    source TEXT,
    ingested_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_entity_attr ON memory(entity_id, attribute);
CREATE INDEX IF NOT EXISTS idx_status ON memory(status);
CREATE TABLE IF NOT EXISTS conflict_resolutions (
    resolution_id TEXT PRIMARY KEY,
    original_conflict_id TEXT NOT NULL UNIQUE,
    source_memory_id TEXT NOT NULL,
    resulting_memory_id TEXT NOT NULL,
    selected_value TEXT NOT NULL,
    selected_source TEXT NOT NULL,
    text_value TEXT NOT NULL,
    image_value TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    decision_source TEXT NOT NULL,
    actor TEXT NOT NULL,
    rationale TEXT DEFAULT '',
    source_session_id TEXT DEFAULT '',
    original_text_evidence TEXT DEFAULT '[]',
    original_visual_evidence TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_resolution_result ON conflict_resolutions(resulting_memory_id);
"""


class MemoryStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            # mkdir never replaces an existing file/directory or database.
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._transaction_depth = 0
        # check_same_thread=False so Streamlit reruns on other threads can reuse the connection.
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(_SCHEMA)
            columns = {r[1] for r in self.conn.execute("PRAGMA table_info(memory)")}
            if "entity_ref" not in columns:
                self.conn.execute("ALTER TABLE memory ADD COLUMN entity_ref TEXT DEFAULT ''")
            if "ingested_at" not in columns:
                self.conn.execute("ALTER TABLE memory ADD COLUMN ingested_at TEXT DEFAULT ''")
            resolution_columns = {
                r[1] for r in self.conn.execute("PRAGMA table_info(conflict_resolutions)")
            }
            if "original_text_evidence" not in resolution_columns:
                self.conn.execute(
                    "ALTER TABLE conflict_resolutions ADD COLUMN original_text_evidence TEXT DEFAULT '[]'"
                )
            if "original_visual_evidence" not in resolution_columns:
                self.conn.execute(
                    "ALTER TABLE conflict_resolutions ADD COLUMN original_visual_evidence TEXT DEFAULT '[]'"
                )
            self.conn.commit()

    @contextmanager
    def transaction(self, write: bool = True) -> Iterator[None]:
        """One atomic operation, including its reads, across threads/connections.

        BEGIN IMMEDIATE reserves the writer before IDs or state decisions are read.
        Nested calls use savepoints, so helpers never commit an outer operation.
        A read transaction gives answering a consistent snapshot without reserving a writer.
        """
        with self._lock:
            depth = self._transaction_depth
            savepoint = f"memory_sp_{depth}"
            self.conn.execute(f"SAVEPOINT {savepoint}" if depth else
                              ("BEGIN IMMEDIATE" if write else "BEGIN"))
            self._transaction_depth += 1
            try:
                yield
                if depth:
                    self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                else:
                    self.conn.commit()
            except BaseException:
                if depth:
                    self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                else:
                    self.conn.rollback()
                raise
            finally:
                self._transaction_depth -= 1

    # ------------------------------------------------------------------ ids
    def next_memory_id(self) -> str:
        with self._lock:
            row = self.conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM memory").fetchone()
            return f"M{int(row['n']):03d}"

    def _next_seq(self) -> int:
        row = self.conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM memory").fetchone()
        return int(row["n"])

    # ---------------------------------------------------------------- write
    def insert(self, rec: MemoryRecord) -> MemoryRecord:
        with self.transaction():
            self.conn.execute(
                """INSERT INTO memory (memory_id, seq, session_id, entity, entity_id, attribute, value,
                   timestamp, confidence, status, previous_memory_id, event, conflicting_value,
                   text_evidence, visual_evidence, source, entity_ref, ingested_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rec.memory_id, self._next_seq(), rec.session_id, rec.entity, rec.entity_id,
                    rec.attribute, rec.value, rec.timestamp, rec.confidence, rec.status.value,
                    rec.previous_memory_id, rec.event, rec.conflicting_value,
                    json.dumps([e.to_dict() for e in rec.text_evidence]),
                    json.dumps([e.to_dict() for e in rec.visual_evidence]),
                    rec.source, rec.entity_ref, rec.ingested_at,
                ),
            )
        return rec

    def set_status(self, memory_id: str, status: Status) -> None:
        with self.transaction():
            self.conn.execute("UPDATE memory SET status=? WHERE memory_id=?", (status.value, memory_id))

    def set_previous(self, memory_id: str, previous_id: Optional[str]) -> None:
        with self.transaction():
            self.conn.execute(
                "UPDATE memory SET previous_memory_id=? WHERE memory_id=?", (previous_id, memory_id)
            )

    def set_confidence(self, memory_id: str, confidence: float) -> None:
        with self.transaction():
            self.conn.execute("UPDATE memory SET confidence=? WHERE memory_id=?", (confidence, memory_id))

    def set_state_start(self, memory_id: str, timestamp: str, event: Optional[str]) -> None:
        """Extend a state to earlier compatible event time, retaining source dates.

        Older databases lack per-image dates. Freeze their existing fallback date before
        changing the state timestamp; no SQL schema migration is needed for JSON evidence.
        """
        with self.transaction():
            rec = self.get(memory_id)
            if rec is None:
                raise KeyError(memory_id)
            for ev in rec.visual_evidence:
                if not ev.timestamp:
                    ev.timestamp = rec.timestamp
            self.conn.execute(
                "UPDATE memory SET timestamp=?, event=?, visual_evidence=? WHERE memory_id=?",
                (timestamp, event, json.dumps([e.to_dict() for e in rec.visual_evidence]), memory_id),
            )

    def add_evidence(
        self,
        memory_id: str,
        text: Optional[TextEvidence] = None,
        visual: Optional[VisualEvidence] = None,
    ) -> bool:
        """Append novel evidence to an existing state (used by MERGE).

        Returns whether anything was appended.  A retry of the same source must
        not inflate confidence or create duplicate provenance entries.
        """
        with self.transaction():
            rec = self.get(memory_id)
            if rec is None:
                raise KeyError(memory_id)
            texts = [e.to_dict() for e in rec.text_evidence]
            visuals = [e.to_dict() for e in rec.visual_evidence]
            changed = False
            if text is not None and text.to_dict() not in texts:
                texts.append(text.to_dict())
                changed = True
            if visual is not None and visual.to_dict() not in visuals:
                visuals.append(visual.to_dict())
                changed = True
            if changed:
                self.conn.execute(
                    "UPDATE memory SET text_evidence=?, visual_evidence=? WHERE memory_id=?",
                    (json.dumps(texts), json.dumps(visuals), memory_id),
                )
            return changed

    def insert_resolution(self, resolution: ConflictResolution) -> ConflictResolution:
        """Persist one immutable resolution; a conflict can be resolved only once."""
        with self.transaction():
            self.conn.execute(
                """INSERT INTO conflict_resolutions (
                   resolution_id, original_conflict_id, source_memory_id, resulting_memory_id,
                   selected_value, selected_source, text_value, image_value, resolved_at,
                   decision_source, actor, rationale, source_session_id,
                   original_text_evidence, original_visual_evidence)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    resolution.resolution_id, resolution.original_conflict_id,
                    resolution.source_memory_id, resolution.resulting_memory_id,
                    resolution.selected_value, resolution.selected_source,
                    resolution.text_value, resolution.image_value, resolution.resolved_at,
                    resolution.decision_source, resolution.actor, resolution.rationale,
                    resolution.source_session_id,
                    json.dumps(resolution.original_text_evidence),
                    json.dumps(resolution.original_visual_evidence),
                ),
            )
        return resolution

    def reset(self) -> None:
        with self.transaction():
            self.conn.execute("DELETE FROM conflict_resolutions")
            self.conn.execute("DELETE FROM memory")

    def delete_memory(self, memory_id: str) -> None:
        """Explicit user-requested deletion (privacy, brief section 50)."""
        with self.transaction():
            self.conn.execute("DELETE FROM memory WHERE memory_id=?", (memory_id,))

    # ----------------------------------------------------------------- read
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            session_id=row["session_id"] or "",
            entity=row["entity"],
            entity_id=row["entity_id"],
            attribute=row["attribute"],
            value=row["value"],
            timestamp=row["timestamp"],
            confidence=row["confidence"] or 0.0,
            status=Status(row["status"]),
            previous_memory_id=row["previous_memory_id"],
            event=row["event"],
            conflicting_value=row["conflicting_value"],
            text_evidence=[TextEvidence.from_dict(d) for d in json.loads(row["text_evidence"] or "[]")],
            visual_evidence=[VisualEvidence.from_dict(d) for d in json.loads(row["visual_evidence"] or "[]")],
            source=row["source"] or "",
            entity_ref=row["entity_ref"] or "",
            ingested_at=row["ingested_at"] or "",
        )

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM memory WHERE memory_id=?", (memory_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def query(
        self,
        entity_id: Optional[str] = None,
        attribute: Optional[str] = None,
        status: Optional[Status] = None,
    ) -> List[MemoryRecord]:
        """Return matching states ordered by (timestamp, insertion order)."""
        sql, args = "SELECT * FROM memory WHERE 1=1", []
        if entity_id is not None:
            sql += " AND entity_id=?"
            args.append(entity_id)
        if attribute is not None:
            sql += " AND attribute=?"
            args.append(attribute)
        if status is not None:
            sql += " AND status=?"
            args.append(status.value)
        sql += " ORDER BY timestamp ASC, seq ASC"
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [self._row_to_record(r) for r in rows]

    def all(self) -> List[MemoryRecord]:
        return self.query()

    @staticmethod
    def _row_to_resolution(row: sqlite3.Row) -> ConflictResolution:
        values = dict(row)
        values["original_text_evidence"] = json.loads(values.get("original_text_evidence") or "[]")
        values["original_visual_evidence"] = json.loads(values.get("original_visual_evidence") or "[]")
        return ConflictResolution(**values)

    def get_resolution(self, original_conflict_id: str) -> Optional[ConflictResolution]:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM conflict_resolutions WHERE original_conflict_id=?",
                (original_conflict_id,),
            ).fetchone()
        return self._row_to_resolution(row) if row else None

    def resolutions(self) -> List[ConflictResolution]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM conflict_resolutions ORDER BY resolved_at, resolution_id"
            ).fetchall()
        return [self._row_to_resolution(row) for row in rows]

    def current(self, entity_id: str, attribute: str) -> Optional[MemoryRecord]:
        recs = self.query(entity_id, attribute, Status.CURRENT)
        return recs[-1] if recs else None

    def entities(self) -> List[Dict[str, str]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT DISTINCT entity_id, entity, entity_ref FROM memory ORDER BY entity_id"
            ).fetchall()
        return [{"entity_id": r["entity_id"], "entity": r["entity"],
                 "entity_ref": r["entity_ref"] or ""} for r in rows]

    def stats(self) -> Dict[str, int]:
        out = {s.value: 0 for s in Status}
        with self._lock:
            for r in self.conn.execute("SELECT status, COUNT(*) AS n FROM memory GROUP BY status"):
                out[r["status"]] = r["n"]
        out["TOTAL"] = sum(out.values())
        return out

    def close(self) -> None:
        with self._lock:
            self.conn.close()
