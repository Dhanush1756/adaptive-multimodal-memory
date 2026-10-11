"""SQLite-backed structured memory store (brief sections 25 and 60).

States live in one table; evidence lists and embeddings are JSON columns. This is
deliberately simple: easy to inspect with any SQLite browser and easy to explain in a viva.
Use db_path=":memory:" for tests.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Dict, List, Optional

from .schema import MemoryRecord, Status, TextEvidence, VisualEvidence

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
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_entity_attr ON memory(entity_id, attribute);
CREATE INDEX IF NOT EXISTS idx_status ON memory(status);
"""


class MemoryStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.RLock()
        # check_same_thread=False so Streamlit reruns on other threads can reuse the connection.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

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
        with self._lock:
            self.conn.execute(
                """INSERT INTO memory (memory_id, seq, session_id, entity, entity_id, attribute, value,
                   timestamp, confidence, status, previous_memory_id, event, conflicting_value,
                   text_evidence, visual_evidence, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rec.memory_id, self._next_seq(), rec.session_id, rec.entity, rec.entity_id,
                    rec.attribute, rec.value, rec.timestamp, rec.confidence, rec.status.value,
                    rec.previous_memory_id, rec.event, rec.conflicting_value,
                    json.dumps([e.to_dict() for e in rec.text_evidence]),
                    json.dumps([e.to_dict() for e in rec.visual_evidence]),
                    rec.source,
                ),
            )
            self.conn.commit()
        return rec

    def set_status(self, memory_id: str, status: Status) -> None:
        with self._lock:
            self.conn.execute("UPDATE memory SET status=? WHERE memory_id=?", (status.value, memory_id))
            self.conn.commit()

    def set_previous(self, memory_id: str, previous_id: Optional[str]) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE memory SET previous_memory_id=? WHERE memory_id=?", (previous_id, memory_id)
            )
            self.conn.commit()

    def set_confidence(self, memory_id: str, confidence: float) -> None:
        with self._lock:
            self.conn.execute("UPDATE memory SET confidence=? WHERE memory_id=?", (confidence, memory_id))
            self.conn.commit()

    def add_evidence(
        self,
        memory_id: str,
        text: Optional[TextEvidence] = None,
        visual: Optional[VisualEvidence] = None,
    ) -> None:
        """Append evidence to an existing state (used by MERGE)."""
        rec = self.get(memory_id)
        if rec is None:
            raise KeyError(memory_id)
        texts = [e.to_dict() for e in rec.text_evidence]
        visuals = [e.to_dict() for e in rec.visual_evidence]
        if text is not None:
            texts.append(text.to_dict())
        if visual is not None:
            visuals.append(visual.to_dict())
        with self._lock:
            self.conn.execute(
                "UPDATE memory SET text_evidence=?, visual_evidence=? WHERE memory_id=?",
                (json.dumps(texts), json.dumps(visuals), memory_id),
            )
            self.conn.commit()

    def reset(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM memory")
            self.conn.commit()

    def delete_memory(self, memory_id: str) -> None:
        """Explicit user-requested deletion (privacy, brief section 50)."""
        with self._lock:
            self.conn.execute("DELETE FROM memory WHERE memory_id=?", (memory_id,))
            self.conn.commit()

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

    def current(self, entity_id: str, attribute: str) -> Optional[MemoryRecord]:
        recs = self.query(entity_id, attribute, Status.CURRENT)
        return recs[-1] if recs else None

    def entities(self) -> List[Dict[str, str]]:
        with self._lock:
            rows = self.conn.execute("SELECT DISTINCT entity_id, entity FROM memory ORDER BY entity_id").fetchall()
        return [{"entity_id": r["entity_id"], "entity": r["entity"]} for r in rows]

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
