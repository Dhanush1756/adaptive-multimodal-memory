"""MemoryAgent: the end-to-end pipeline (brief sections 12, 56).

    remember(text, image, timestamp)
        NLP claims + CV analysis -> fusion -> Candidate -> MemoryEngine (rules, no LLM) -> Decision
    ask(question)
        parse (entity, temporal intent) -> TemporalRetriever -> grounded Answer

`link_evidence=False` is the "no evidence linking" ablation: the text claim and the image are
fed to the engine as two *independent* candidates instead of one fused candidate.
`light=True` loads no pretrained model (hashing embeddings, HSV colour, no YOLO/CLIP): used
by tests and offline demos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..config import load_config, resolve_path
from ..memory.schema import Candidate, Decision, MemoryRecord
from ..memory.state_tracker import resolve_entity_id, timeline
from ..memory.store import MemoryStore
from ..memory.update import MemoryEngine
from ..multimodal.evidence import ImageAnalysis
from ..multimodal.fusion import fuse
from ..multimodal.visual_pipeline import VisualPipeline
from ..nlp.embeddings import get_embedder
from ..nlp.ner import tracked_entities
from ..nlp.preprocessing import normalize
from ..nlp.relation_extraction import extract_claims
from ..retrieval.hybrid_retriever import HybridRetriever
from ..retrieval.temporal_retriever import TemporalRetriever
from ..utils import iso, parse_ts
from .answer_generator import Answer, AnswerGenerator
from .intent_model import apply_intent_model, load_intent_model
from .query_parser import ParsedQuery, parse_query


@dataclass
class Components:
    """Heavy, shareable parts (models). Build once, reuse across agents/baselines."""
    embedder: Any
    visual: VisualPipeline


def build_components(cfg: Optional[Dict[str, Any]] = None, light: bool = False) -> Components:
    cfg = cfg or load_config()
    return Components(get_embedder(cfg, force_fallback=light), VisualPipeline(cfg, light=light))


@dataclass
class IngestResult:
    session_id: str
    timestamp: str
    claim: Optional[Dict[str, Any]]
    image: Optional[Dict[str, Any]]
    candidates: List[Candidate] = field(default_factory=list)
    decisions: List[Decision] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def decision(self) -> Decision:
        return self.decisions[0]

    @property
    def candidate(self) -> Candidate:
        return self.candidates[0]


class MemoryAgent:
    def __init__(
        self,
        cfg: Optional[Dict[str, Any]] = None,
        db_path: Optional[str] = None,
        image_dir: Optional[str] = None,
        light: bool = False,
        components: Optional[Components] = None,
        link_evidence: bool = True,
        use_intent_model: bool = True,
        answer_llm: Optional[Callable[[str], str]] = None,
    ):
        self.cfg = cfg or load_config()
        self.light = light
        self.link_evidence = link_evidence
        paths = self.cfg.get("paths", {})
        db_path = str(db_path if db_path is not None else paths.get("db_path", "data/processed/memory.db"))
        if db_path != ":memory:":
            db_path = resolve_path(db_path)
            if image_dir is None:
                image_dir = paths.get("image_dir", "data/processed/images")
        # Explicit :memory: agents remain disk-free unless image_dir is supplied.
        self.image_dir = Path(resolve_path(image_dir)) if image_dir else None
        self._lock = threading.RLock()
        self.comp = components or build_components(self.cfg, light)
        self.store = MemoryStore(db_path)
        self.engine = MemoryEngine(self.store, self.cfg)
        self.hybrid = HybridRetriever(self.store, self.comp.embedder, self.cfg)
        self.retriever = TemporalRetriever(self.store, self.hybrid)
        self.answerer = AnswerGenerator(answer_llm)
        self.intent_model = load_intent_model() if use_intent_model else None
        self._sessions: set = set()
        self._counter = 0

    # ------------------------------------------------------------------ helpers
    def status(self) -> Dict[str, Any]:
        return {
            "text_embedding": getattr(self.comp.embedder, "name", "?"),
            **self.comp.visual.status(),
            "intent_model": "trained classifier" if self.intent_model is not None else "rules only",
            "evidence_linking": self.link_evidence,
            "memory": self.store.stats(),
        }

    def reset(self) -> None:
        with self._lock:
            self.store.reset()
            self._sessions.clear()
            self._counter = 0

    def _session_taken(self, sid: str) -> bool:
        if sid in self._sessions:
            return True
        for rec in self.store.all():
            if rec.session_id == sid or any(e.session_id == sid for e in rec.text_evidence):
                return True
            if any(e.session_id == sid or (not e.session_id and e.image_id == f"IMG_{sid}")
                   for e in rec.visual_evidence):
                return True
        return False

    def _new_session_id(self, requested: Optional[str]) -> str:
        if requested and not self._session_taken(requested):
            sid = requested
        else:
            base = requested
            while True:
                self._counter += 1
                sid = f"{base}_{self._counter}" if base else f"S{self._counter:02d}"
                if not self._session_taken(sid):
                    break
        self._sessions.add(sid)
        return sid

    def context_entity(self) -> Optional[str]:
        """Entity most recently written to memory (resolves "it")."""
        recs = self.store.all()
        if not recs:
            return None
        return max(recs, key=lambda r: int(r.memory_id[1:])).entity

    def context_entity_ref(self) -> Optional[str]:
        recs = self.store.all()
        if not recs:
            return None
        return max(recs, key=lambda r: int(r.memory_id[1:])).entity_ref or None

    def _temporal_consistency(self, entity: Optional[str], cand_time: str) -> float:
        if not entity:
            return 1.0
        chain = timeline(self.store, resolve_entity_id(self.store, entity), "color")
        if chain and parse_ts(cand_time) < parse_ts(chain[-1].timestamp):
            return 0.6  # out-of-order evidence is less certain to describe the *current* state
        return 1.0

    # ------------------------------------------------------------------ write path
    def remember(
        self,
        text: str = "",
        image: Any = None,
        timestamp: Any = None,
        session_id: Optional[str] = None,
    ) -> IngestResult:
        """Ingest one observation. timestamp is source time, not arrival order.

        An explicit date in the text supplies event time; otherwise timestamp does.
        Source evidence dates remain unchanged when an earlier observation extends a state.
        """
        with self._lock:
            sessions, counter = self._sessions.copy(), self._counter
            try:
                return self._remember(text, image, timestamp, session_id)
            except BaseException:
                self._sessions, self._counter = sessions, counter
                raise

    def _remember(self, text: str, image: Any, timestamp: Any, session_id: Optional[str]) -> IngestResult:
        timestamp_missing = timestamp is None
        ts = parse_ts(timestamp).replace(microsecond=0)
        ts_iso = ts.isoformat()
        sid = self._new_session_id(session_id)
        ctx = self.context_entity()
        text = normalize(text or "")

        claims = extract_claims(text, ts, context_entity=ctx,
                                context_entity_ref=self.context_entity_ref()) if text else []
        claim = claims[0] if claims else None  # one claim per ingest (documented limitation)
        mentions = tracked_entities(text) if text else []
        text_entity = claim.entity if claim else (mentions[0].canonical if mentions else None)
        text_emb = self.comp.embedder.embed([text])[0].tolist() if text else None

        analysis: Optional[ImageAnalysis] = None
        image_id: Optional[str] = None
        image_path = ""
        image_error = ""
        if image is not None:
            try:
                analysis = self.comp.visual.analyze(image, preferred_entity=text_entity or ctx)
            except Exception as exc:
                # A bad upload or unavailable CV backend must not discard a
                # separately usable text observation.
                analysis = None
                image_error = f"image analysis unavailable ({exc.__class__.__name__})"
            else:
                image_error = ""
            # A source session label is metadata, never a filesystem path.
            image_id = f"IMG_{uuid4().hex}"
            if self.image_dir is not None:
                image_path = str(self.image_dir / f"{image_id}.png")

        entity_guess = (claim.entity if claim else None) or text_entity or (analysis.entity if analysis else None) or ctx
        cand_time = claim.resolved_time if (claim and claim.resolved_time) else ts_iso
        tc = self._temporal_consistency(entity_guess, cand_time)

        common = dict(session_id=sid, timestamp=ts_iso, text_entity=text_entity, context_entity=ctx,
                      cfg=self.cfg, temporal_consistency=tc)
        if self.link_evidence or analysis is None or (claim is None and not text):
            cands = [fuse(text=text, claim=claim, image=analysis, image_id=image_id, image_path=image_path,
                          text_embedding=text_emb, **common)]
        else:
            # ablation: independent streams (text first, then image)
            cands = [
                fuse(text=text, claim=claim, image=None, text_embedding=text_emb, **common),
                fuse(text="", claim=None, image=analysis, image_id=image_id, image_path=image_path, **common),
            ]

        created_image = False
        try:
            # Both ablation candidates and the saved evidence succeed or roll back together.
            with self.store.transaction():
                decisions = [self.engine.process(c) for c in cands]
                stored = any(d.memory_id for d in decisions)
                if analysis is not None and stored and self.image_dir is not None:
                    self.image_dir.mkdir(parents=True, exist_ok=True)
                    with open(image_path, "xb") as output:
                        created_image = True
                        analysis.image.save(output, format="PNG")
        except BaseException:
            if created_image:
                # Only remove the new file owned by this failed operation.
                Path(image_path).unlink(missing_ok=True)
            raise

        notes = []
        if timestamp_missing:
            notes.append("source timestamp was missing; using ingestion time as an uncertainty-marked fallback")
        if image is not None and image_error:
            notes.append(image_error)
        if analysis is not None and analysis.quality.get("flags"):
            notes.append("image quality: " + ", ".join(analysis.quality["flags"]))
        if analysis is not None and analysis.association_status in {"ambiguous", "unmatched"}:
            notes.append("image association unavailable: " + analysis.association_reason)
        if claim is not None and claim.confidence < 0.8:
            notes.append("text claim has reduced confidence (hedged or resolved from context)")
        return IngestResult(
            session_id=sid, timestamp=ts_iso,
            claim=claim.to_dict() if claim else None,
            image=analysis.summary() if analysis else None,
            candidates=cands, decisions=decisions, notes=notes,
        )

    # ------------------------------------------------------------------ read path
    def parse(self, question: str, reference_time: Any = None) -> ParsedQuery:
        parsed = parse_query(question, reference_time, context_entity=self.context_entity(),
                             context_entity_ref=self.context_entity_ref())
        return apply_intent_model(parsed, self.intent_model)

    def ask(self, question: str, reference_time: Any = None) -> Answer:
        with self._lock, self.store.transaction(write=False):
            parsed = self.parse(question, reference_time)
            return self.answerer.generate(parsed, self.retriever.retrieve(parsed))

    def timeline_for(self, entity: str, attribute: str = "color",
                     entity_ref: Optional[str] = None) -> List[MemoryRecord]:
        return timeline(self.store, resolve_entity_id(self.store, entity, entity_ref), attribute)
