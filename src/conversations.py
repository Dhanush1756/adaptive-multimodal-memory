"""Authenticated conversations over the existing adaptive temporal memory engine.

Transcripts, login records and selected memory facts are distinct. All memory
and conversation changes share the user's SQLite transaction. Never accepts a
user ID or recovery code from the caller: identity comes only from Accounts.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace, asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

from .accounts import AuthenticationError
from .automatic_memory import AutomaticMemory
from .agent.answer_generator import Answer, evidence_items
from .agent.query_parser import Intent, ParsedQuery
from .agent.reasoning import MemoryAgent, IngestResult
from .config import load_config
from .memory.schema import Candidate, Claim, TextEvidence, VisualEvidence, Decision, Action
from .memory.state_tracker import timeline
from .nlp.temporal_extraction import resolve_event_time
from .nlp.relation_extraction import extract_claims
from .retrieval.temporal_retriever import RetrievalResult, select_states
from .utils import iso, parse_ts


def now():
    return datetime.now(timezone.utc).isoformat()


def project_claims(text):
    """Constrained explicit statements; transcript-only outside these patterns.

    No inference of unnamed project identity or unsupported general knowledge.
    Each match is a separate Candidate processed by the original MemoryEngine.
    """
    patterns = [
        (r"(?:my|our) project(?: named ([\w-]+))?'?s? model is ([^.;\n]+)", "project", "model"),
        (r"(?:we|i) (?:decided|plan) to train ([^.;\n]+)", "project", "model"),
        (r"(?:my|our) (?:new |previous )?requirement is ([^.;\n]+)", "project", "requirement"),
        (r"i (?:now )?prefer ([^.;\n]+)", "user", "preference"),
    ]
    claims = []
    for sentence in re.split(r"[.;\n]+", text):
        sentence = re.sub(r"^(?:correction|actually|update)\s*[:,]?\s*", "", sentence.strip(), flags=re.I)
        for pattern, entity, attribute in patterns:
            match = re.fullmatch(pattern, sentence, re.I)
            if match is None:
                continue
            ref = ((match.group(1) or "default project") if len(match.groups()) == 2
                   else "default project" if entity == "project" else None)
            value = match.group(match.lastindex).strip()
            claims.append(Claim(entity, attribute, value, confidence=.9,
                                source_text=text, entity_ref=ref))
    return claims


class Conversations(AutomaticMemory):
    def __init__(self, accounts, token, root, cfg=None, light=True):
        self.accounts, self.token = accounts, token
        self.uid = accounts.identity(token)
        base = Path(root).resolve() / self.uid
        config = deepcopy(cfg or load_config())
        config["nlp"]["tracked_entities"] += ["project", "user"]
        config["nlp"]["tracked_attributes"] += ["model", "requirement", "preference"]
        # The account schema is entity/attribute agnostic. The legacy demo and
        # frozen benchmark profiles retain their original configured domain.
        config["nlp"]["tracked_entities"] = []
        config["nlp"]["tracked_attributes"] = []
        # Account processing is local-only, even when optional CV/NLP backends
        # are enabled. Missing cached weights must not trigger downloads.
        config['cv']['local_files_only'] = True
        config['nlp']['local_files_only'] = True
        self.agent = MemoryAgent(config, db_path=str(base / "memory.db"),
                                 image_dir=str(base / "images"), light=light)
        self.db = self.agent.store.conn
        # New tables in account-only storage. Anonymous/legacy DBs aren't opened.
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
          conversation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
          title TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (
          message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('user','assistant')),
          content TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_events (
          event_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          message_id TEXT NOT NULL, memory_id TEXT, action TEXT NOT NULL,
          evidence_ids TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversation_summaries (
          summary_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          content TEXT NOT NULL, source_message_ids TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pending_observations (
          observation_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          payload TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0);
        """)
        self._init_automatic()

    def _authorize(self, conversation_id=None):
        if self.accounts.identity(self.token) != self.uid:
            raise AuthenticationError("Please log in again.")
        if conversation_id is not None and not self.db.execute(
                "SELECT 1 FROM conversations WHERE conversation_id=? AND user_id=?",
                (conversation_id, self.uid)).fetchone():
            raise AuthenticationError("Conversation is unavailable.")

    def create(self, title="New conversation"):
        self._authorize()
        cid = uuid4().hex
        with self.agent.store.transaction():
            self.db.execute("INSERT INTO conversations VALUES (?,?,?,?)", (cid, self.uid, title[:200], now()))
        return cid

    def list(self):
        self._authorize()
        return [dict(r) for r in self.db.execute(
            "SELECT conversation_id,title,created_at FROM conversations WHERE user_id=? ORDER BY created_at", (self.uid,))]

    def transcript(self, cid):
        self._authorize(cid)
        return [dict(r) for r in self.db.execute(
            "SELECT message_id,role,content,created_at FROM messages WHERE conversation_id=? ORDER BY rowid", (cid,))]

    def _message(self, cid, role, text):
        mid = uuid4().hex
        self.db.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (mid, cid, role, text, now()))
        return mid

    def _link(self, cid, mid, decision, source_id=None):
        record = self.agent.store.get(decision.memory_id) if decision.memory_id else None
        ids = ([e.evidence_id for e in record.text_evidence if source_id is None or e.session_id == source_id]
               + [e.image_id for e in record.visual_evidence if source_id is None or e.session_id == source_id]) if record else []
        self.db.execute("INSERT INTO memory_events VALUES (?,?,?,?,?,?,?)",
                        (uuid4().hex, cid, mid, decision.memory_id, decision.action.value, json.dumps(ids), now()))

    def remember(self, cid, text="", image=None, timestamp=None):
        """Roll back newly created evidence files if the enclosing transcript fails."""
        with self.agent._lock:
            created = []
            sessions, counter = self.agent._sessions.copy(), self.agent._counter
            try:
                with self.agent.store.transaction():
                    return self._remember(cid, text, image, timestamp, created)
            except BaseException:
                self.agent._sessions, self.agent._counter = sessions, counter
                for path in created:
                    # Only a UUID path returned by this attempted ingestion is
                    # eligible. Existing user evidence is never enumerated/deleted.
                    file = Path(path)
                    file.resolve().relative_to(self.agent.image_dir.resolve())
                    if re.fullmatch(r"IMG_[0-9a-f]{32}\.png", file.name):
                        file.unlink(missing_ok=True)
                raise

    def _remember(self, cid, text, image, timestamp, created):
        self._authorize(cid)
        source_id = "MSG_" + uuid4().hex
        event_time = parse_ts(timestamp or now())
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        timestamp = event_time.isoformat()
        # Process text+image with existing fusion/conflict gates, then extra
        # explicit project statements with the same lifecycle engine.
        with self.agent._lock, self.agent.store.transaction():
            mid = self._message(cid, "user", text)
            project_facts = project_claims(text)
            if project_facts and not extract_claims(text, timestamp):
                # Project/model values may contain colour words (e.g. Gold).
                # Never resolve them through an unrelated object's colour context.
                result = IngestResult(source_id, timestamp, None, None,
                    decisions=[Decision(Action.IGNORE, None, 'Explicit non-colour facts use their own attribute path.')],
                    notes=['Image is not evidence of a project attribute.'] if image is not None else [])
            else:
                result = self.agent.remember(text, image, timestamp, source_id)
            for candidate in result.candidates:
                if candidate.visual and candidate.visual.image_path:
                    created.append(candidate.visual.image_path)
            for decision in result.decisions:
                self._link(cid, mid, decision, source_id)
            project_candidates, project_decisions = [], []
            for i, claim in enumerate(project_facts):
                event = resolve_event_time(text, reference=timestamp)
                resolved = event.resolved if event and event.resolved else event_time
                if resolved.tzinfo is None:
                    resolved = resolved.replace(tzinfo=timezone.utc)
                ts = iso(resolved)
                claim = replace(claim, resolved_time=ts)
                evidence = TextEvidence(text=text, session_id=source_id, timestamp=ts,
                                        confidence=.9, evidence_id=f"TXT_{source_id}_P{i}",
                                        ingested_at=now(), extractor="explicit-project-rules-v1")
                candidate = Candidate(source_id, ts, claim=claim, text_evidence=evidence,
                                      confidence=.9, ingested_at=evidence.ingested_at)
                decision = self.agent.engine.process(candidate)
                self._link(cid, mid, decision, source_id)
                project_candidates.append(candidate)
                project_decisions.append(decision)
            if project_decisions and all(d.action == Action.IGNORE for d in result.decisions):
                result.candidates = project_candidates
                result.decisions = project_decisions
                result.claim = project_candidates[0].claim.to_dict()
            if self.agent.verification_request(result):
                self.db.execute("INSERT INTO pending_observations VALUES (?,?,?,0)",
                                (result.session_id, cid, json.dumps(asdict(result))))
            self._message(cid, "assistant", result.decision.reason)
        return result

    def ask(self, cid, question, reference_time=None):
        self._authorize(cid)
        low = question.lower()
        with self.agent._lock, self.agent.store.transaction():
            self._message(cid, "user", question)
            attr = "model" if re.search(r"\bmodel\b", low) else "requirement" if "requirement" in low else "preference" if "prefer" in low else None
            project_query = "project" in low or attr in {"model", "requirement"}
            if self._hidden():
                answer = self._automatic_answer(question, reference_time)
            elif project_query or attr == "preference":
                answer = self._project_answer(question, attr, reference_time)
                if not answer.found:
                    answer = self._automatic_answer(question, reference_time)
            else:
                answer = self._automatic_answer(question, reference_time)
            for evidence in answer.evidence:
                eid = evidence.get("evidence_id") or evidence.get("image_id")
                refs = self.db.execute("SELECT DISTINCT conversation_id,message_id FROM memory_events WHERE EXISTS (SELECT 1 FROM json_each(memory_events.evidence_ids) WHERE value=?)", (eid,)).fetchall()
                evidence["conversation_references"] = [dict(r) for r in refs]
            answer = self.local.retrieve(question,reference_time,answer)
            answer = self.local.respond(question,answer,
                [r['content'] for r in self.transcript(cid) if r['role']=='user'][-4:])
            self._message(cid, "assistant", answer.text)
        return answer

    def _project_answer(self, question, attribute, reference_time):
        low = question.lower()
        if attribute is None and not any(cue in low for cue in ("remember", "tell", "history", "so far", "last week")):
            return Answer("Name the stored project attribute (model or requirement); that fact may not have been provided.",
                          None, 0, False, "CURRENT")
        entities = [e for e in self.agent.store.entities() if e["entity"] == ("user" if attribute == "preference" else "project")]
        named = re.search(r"project named ([\w-]+)", low)
        if named:
            entities = [e for e in entities if e.get("entity_ref") == named.group(1)]
        if len(entities) != 1:
            return Answer("Specify the project identity, or provide the missing fact.", None, 0, False, "CURRENT")
        attrs = [attribute] if attribute else ["model", "requirement"]
        records = []
        values = []
        for attr in attrs:
            chain = timeline(self.agent.store, entities[0]["entity_id"], attr)
            parsed = ParsedQuery(question, entities[0]["entity"], attr, Intent.CURRENT)
            if "history" in low or "remember" in low or "last week" in low:
                parsed.intent = Intent.HISTORY
            elif "original" in low or "initial" in low:
                parsed.intent = Intent.ORIGINAL
            elif "previous" in low or "earlier" in low or "before" in low:
                parsed.intent = Intent.PREVIOUS
            date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", low)
            if date:
                parsed.intent, parsed.time = Intent.AS_OF, date.group(0) + "T23:59:59+00:00"
            if "last week" in low:
                end = parse_ts(reference_time or now())
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                # Previous calendar week, Monday inclusive to Monday exclusive.
                end = (end - timedelta(days=end.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                start = end - timedelta(days=7)
                chain = [r for r in chain if start <= parse_ts(r.timestamp) < end]
            selected = select_states(parsed, chain)
            if selected.found:
                records.extend(chain[i] for i in selected.indices)
                values.append(selected.value)
        if not records:
            return Answer("No supporting fact is stored for that question.", None, 0, False, "CURRENT")
        result = RetrievalResult(parsed=parsed, records=records)
        evidence = evidence_items(result, False)
        return Answer("; ".join(f"{r.attribute}: {r.value} ({r.timestamp[:10]})" for r in records),
                      values[0] if len(values) == 1 else values, min(r.confidence for r in records), True,
                      parsed.intent.value, evidence=evidence,
                      supporting_state_ids=[r.memory_id for r in records],
                      supporting_evidence_ids=[e["evidence_id"] for e in evidence if e.get("evidence_id")])

    def resolve(self, cid, result, value, rationale=""):
        self._authorize(cid)
        # Only the pending observation ingested in this account/conversation
        # can be resolved, never an object supplied by another account.
        stored = self.db.execute("SELECT payload FROM pending_observations WHERE conversation_id=? AND observation_id=? AND resolved=0",
                                 (cid, result.session_id)).fetchone()
        if not stored:
            raise AuthenticationError("Observation is unavailable in this conversation.")
        result = self._decode_result(stored["payload"])
        with self.agent._lock, self.agent.store.transaction():
            verified = self.agent.verify(result, value, actor="authenticated_user", rationale=rationale)
            mid = self._message(cid, "assistant", f"Human verification accepted {value}. {rationale}")
            self._link(cid, mid, verified.decision, verified.session_id)
            requested = self.db.execute(
                'SELECT 1 FROM memory_selection_audit WHERE conversation_id=? AND memory_id=? '
                "AND json_extract(candidate_json, '$.memory_request.explicit')=1 LIMIT 1",
                (cid, result.decision.memory_id)).fetchone()
            if requested and verified.decision.memory_id:
                self.set_memory_priority(verified.decision.memory_id, True, mid)
            self.db.execute("UPDATE pending_observations SET resolved=1 WHERE observation_id=?", (result.session_id,))
        return verified

    @staticmethod
    def _decode_result(payload):
        data = json.loads(payload)
        candidates = []
        for row in data["candidates"]:
            row["claim"] = Claim(**row["claim"]) if row["claim"] else None
            row["text_evidence"] = TextEvidence.from_dict(row["text_evidence"]) if row["text_evidence"] else None
            row["visual"] = VisualEvidence.from_dict(row["visual"]) if row["visual"] else None
            candidates.append(Candidate(**row))
        data["candidates"] = candidates
        data["decisions"] = [Decision(**{**row, "action": Action(row["action"])}) for row in data["decisions"]]
        return IngestResult(**data)

    def pending(self, cid):
        self._authorize(cid)
        return [self._decode_result(r["payload"]) for r in self.db.execute(
            "SELECT payload FROM pending_observations WHERE conversation_id=? AND resolved=0 ORDER BY rowid", (cid,))]

    def summarize(self, cid):
        self._authorize(cid)
        rows = self.transcript(cid)
        # Extractive summary, no invented facts and no LLM claim.
        selected = [r for r in rows if r["role"] == "user"][-10:]
        summary = "\n".join(r["content"] for r in selected)
        with self.agent.store.transaction():
            self.db.execute("INSERT INTO conversation_summaries VALUES (?,?,?,?,?)",
                            (uuid4().hex, cid, summary, json.dumps([r["message_id"] for r in selected]), now()))
        return summary

    def summaries(self, cid):
        self._authorize(cid)
        return [dict(r) for r in self.db.execute(
            "SELECT summary_id,content,source_message_ids,created_at FROM conversation_summaries WHERE conversation_id=? ORDER BY rowid", (cid,))]

    def events(self, cid):
        self._authorize(cid)
        return [dict(r) for r in self.db.execute(
            "SELECT message_id,memory_id,action,evidence_ids,created_at FROM memory_events WHERE conversation_id=? ORDER BY rowid", (cid,))]

    def audit(self):
        self._authorize()
        return self.agent.conflict_audit()

    def memories(self):
        self._authorize()
        return [r.to_dict() for r in self.agent.store.all()]

    def close(self):
        self.agent.store.close()
