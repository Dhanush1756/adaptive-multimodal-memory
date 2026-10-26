"""Account-only automatic turns; reuses the existing temporal memory engine.

All operations require the hosting Conversations authorization boundary. Selection
audit and reversible retrieval exclusions are additive account-local tables.
"""
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from uuid import uuid4

from .accounts import AuthenticationError
from .agent.answer_generator import Answer, evidence_items
from .agent.query_parser import Intent, ParsedQuery, parse_query
from .memory.schema import Candidate, TextEvidence, Status, Claim
from .memory.selection import SelectionPolicy, extract_candidates, EXTRACTOR_VERSION, is_query_text
from .memory.state_tracker import timeline
from .retrieval.temporal_retriever import RetrievalResult, select_states
from .utils import iso, parse_ts
from .local_memory import LocalMemoryServices, key as extraction_key


@dataclass
class ChatTurn:
    answer: Answer
    selections: list = field(default_factory=list)
    observations: list = field(default_factory=list)


class AutomaticMemory:
    def _init_automatic(self):
        self.selection_policy = SelectionPolicy(self.agent.cfg.get('automatic_memory'))
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS visual_observations (
          observation_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          message_id TEXT NOT NULL, event_time TEXT NOT NULL, ingested_at TEXT NOT NULL,
          payload_json TEXT NOT NULL, image_path TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_priority_events (
          event_id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, entity_id TEXT NOT NULL,
          attribute TEXT NOT NULL, enabled INTEGER NOT NULL, priority REAL NOT NULL,
          source_message_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_selection_audit (
          selection_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
          message_id TEXT NOT NULL, candidate_json TEXT NOT NULL,
          outcome TEXT NOT NULL, reason TEXT NOT NULL, usefulness REAL NOT NULL,
          extraction_confidence REAL NOT NULL, policy_version TEXT NOT NULL,
          memory_id TEXT, lifecycle_action TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_visibility_events (
          event_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, attribute TEXT NOT NULL,
          visible INTEGER NOT NULL, actor TEXT NOT NULL, rationale TEXT NOT NULL,
          created_at TEXT NOT NULL);
        ''')
        self.local = LocalMemoryServices(self,self.agent.cfg)

    def visual_observations(self, cid):
        self._authorize(cid)
        return [{**dict(row),'payload':json.loads(row['payload_json'])} for row in self.db.execute(
            'SELECT * FROM visual_observations WHERE conversation_id=? ORDER BY rowid',(cid,))]

    def _observe_image(self, cid, mid, image, timestamp, created):
        """Multi-object context, kept outside accepted same-object memory states."""
        analysis = self.agent.comp.visual.analyze(image)
        image_id = 'IMG_'+uuid4().hex
        path = ''
        if self.agent.image_dir:
            from io import BytesIO
            self.agent.image_dir.mkdir(parents=True,exist_ok=True)
            file=self.agent.image_dir/(image_id+'.png'+('.fernet' if self.agent.protection else ''))
            clean_image=analysis.image.copy();clean_image.info.clear()
            data=BytesIO();clean_image.save(data,format='PNG')
            payload=data.getvalue()
            if self.agent.protection:payload=self.agent.protection.cipher.encrypt(payload)
            try:
                with file.open('xb') as stream:stream.write(payload)
            except BaseException:
                file.unlink(missing_ok=True)
                raise
            path=str(file);created.append(path)
        summary={**analysis.summary(),'image_id':image_id,'event_time':timestamp,
                 'ingested_at':self._clock(),'source_message_id':mid,'supports_memory_state':False}
        self.db.execute('INSERT INTO visual_observations VALUES (?,?,?,?,?,?,?)',
            (image_id,cid,mid,timestamp,summary['ingested_at'],json.dumps(summary),path))
        return summary

    def priority_history(self):
        self._authorize()
        return [dict(r) for r in self.db.execute('SELECT * FROM memory_priority_events ORDER BY rowid')]

    def _important(self):
        latest = {}
        for row in self.db.execute('SELECT * FROM memory_priority_events ORDER BY rowid'):
            latest[(row['entity_id'], row['attribute'])] = bool(row['enabled'])
        return {k for k, enabled in latest.items() if enabled}

    def set_memory_priority(self, memory_id, enabled=True, source_message_id=''):
        """Account-local importance; never changes truth, visibility or event time."""
        self._authorize()
        with self.agent._lock, self.agent.store.transaction():
            record = self.agent.store.get(memory_id)
            if record is None or record.status in {Status.CONTRADICTORY, Status.RESOLVED}:
                raise AuthenticationError('Accepted memory is unavailable.')
            if ((record.entity_id, record.attribute) in self._important()) == bool(enabled):
                return
            self.db.execute('INSERT INTO memory_priority_events VALUES (?,?,?,?,?,?,?,?,?)',
                (uuid4().hex, memory_id, record.entity_id, record.attribute, int(bool(enabled)),
                 1.0 if enabled else 0.0, source_message_id, 'authenticated_user', self._clock()))

    def selection_history(self):
        self._authorize()
        return [dict(r) for r in self.db.execute('SELECT * FROM memory_selection_audit ORDER BY rowid')]

    def _hidden(self):
        state = {}
        for r in self.db.execute('SELECT * FROM memory_visibility_events ORDER BY rowid'):
            state[(r['entity_id'], r['attribute'])] = not r['visible']
        return {key for key, hidden in state.items() if hidden}

    def set_memory_visibility(self, memory_id, visible, rationale=''):
        """Forget from retrieval, preserving historical states and immutable audits."""
        self._authorize()
        with self.agent._lock, self.agent.store.transaction():
            record = self.agent.store.get(memory_id)
            if record is None:
                raise AuthenticationError('Memory is unavailable.')
            self.db.execute('INSERT INTO memory_visibility_events VALUES (?,?,?,?,?,?,?)',
                            (uuid4().hex, record.entity_id, record.attribute, int(bool(visible)),
                             'authenticated_user', rationale, self._clock()))
            # Derived generations may contain hidden values; purge rather than
            # relying only on filtering. Rebuild from eligible records on demand.
            self.db.execute('DELETE FROM local_memory_embeddings')
            self.db.execute('DELETE FROM local_embedding_generations')
        self._clear_private_caches()

    @staticmethod
    def _clock():
        from .conversations import now
        return now()

    def _references(self, answer):
        for evidence in answer.evidence:
            eid = evidence.get('evidence_id') or evidence.get('image_id')
            evidence['conversation_references'] = [dict(r) for r in self.db.execute(
                'SELECT DISTINCT conversation_id,message_id FROM memory_events WHERE EXISTS '
                '(SELECT 1 FROM json_each(memory_events.evidence_ids) WHERE value=?)', (eid,))]
        return answer

    def _automatic_answer(self, question, reference_time=None, _resolved_group=None):
        """Explicit lexical entity/attribute matching, then existing temporal selection.

        No semantic retrieval claim. Unknown or ambiguous requests abstain. Colour
        requests retain the mature image/conflict-aware legacy retriever.
        """
        low = question.lower()
        hidden = self._hidden()
        all_records = self.agent.store.all()
        records = [r for r in all_records if (r.entity_id, r.attribute) not in hidden]
        if re.fullmatch(r'(?:show (?:my )?(?:pinned memories|saved notes)|what did i ask you to remember)[?.!]*', low.strip()):
            chosen = [r for r in records if r.status == Status.CURRENT
                      and (r.entity_id, r.attribute) in self._important()]
            blocked = []
            for r in chosen:
                if r.attribute == 'color':
                    check = self._automatic_answer(f'What color is my {r.entity}?', reference_time,
                        _resolved_group=(r.entity, r.entity_id, r.entity_ref, r.attribute))
                    if check.status == 'uncertain':
                        blocked.append(r)
            chosen = [r for r in chosen if r not in blocked]
            evidence = evidence_items(RetrievalResult(parsed=parse_query(question, reference_time), records=chosen), False)
            text = '\n'.join(f'{r.entity}: {r.attribute} = {r.value}' for r in chosen)
            if blocked:
                text += '\nSome pinned memories have unresolved disagreements; verify them before using their values.'
            return Answer(text
                          or 'You have no visible pinned memories.',
                          [r.value for r in chosen], min((r.confidence for r in chosen), default=0),
                          bool(chosen), 'HISTORY', evidence=evidence,
                          states=[r.to_dict() for r in chosen],
                          supporting_state_ids=[r.memory_id for r in chosen])
        attrs = {r.attribute for r in records if re.search(r'\b'+re.escape(r.attribute)+r'\b', low)}
        if _resolved_group:
            attrs = {_resolved_group[3]}
        if 'prefer' in low:
            attrs.add('preference')
        if re.search(r'\bcolou?r\b', low):
            attrs.add('color')
        if not attrs and not re.search(r'\b(remember|history|tell me about)\b', low):
            return self.agent.ask(question, reference_time) if not hidden and re.search(
                r'\b(conflict|disagree|contradiction|evidence|proof)\b', low) else Answer(
                    'No supporting fact is stored for that question.', None, 0, False, 'CURRENT')
        relevant = [r for r in records if (not attrs or r.attribute in attrs)]
        named = re.search(r'\bnamed ([\w-]+)', low)
        entities = {(r.entity, r.entity_id, r.entity_ref) for r in relevant}
        if named:
            entities = {e for e in entities if e[2] == named[1]}
            explicit = {e for e in entities if re.search(r'\b'+re.escape(e[0])+r'\b', low)}
            if explicit:
                entities = explicit
        else:
            explicit = {e for e in entities if re.search(r'\b'+re.escape(e[0])+r'\b', low)}
            if explicit:
                entities = explicit
            elif not attrs and re.search(r'\btell me about\b', low):
                entities = set()
            subject = re.search(r'\b(?:my|our) (?:(?:previous|original|initial|current) )?(?:first |second |third )?([\w-]+)', low)
            if subject and subject[1] not in attrs and subject[1] not in {'preference','preferences'}:
                entities = {e for e in entities if e[0] == subject[1]}
            ordinal = re.search(r'\b(first|second|third) ([\w-]+)\b', low)
            if ordinal:
                entities = {e for e in entities if e[2] == ordinal[0]}
        if _resolved_group:
            entities = {tuple(_resolved_group[:3])}
            attrs = {_resolved_group[3]}
        if len(entities) != 1:
            return Answer('Specify the entity identity and attribute, or provide the missing fact.', None, 0, False, 'CURRENT')
        entity, eid, ref = next(iter(entities))
        for row in self.db.execute('SELECT payload FROM pending_observations WHERE resolved=0'):
            pending = self._decode_result(row['payload'])
            request = self.agent.verification_request(pending)
            if (request and request['entity'] == entity and
                    (request['entity_ref'] == ref or not request['entity_ref']) and 'color' in attrs):
                source_records = [r for r in relevant if r.entity_id == eid and r.attribute == 'color']
                parsed = ParsedQuery(question, entity, 'color', Intent.CONFLICT, entity_ref=ref)
                evidence = evidence_items(RetrievalResult(parsed=parsed, records=source_records,
                    image_hits=[{'record':r, 'evidence':e} for r in source_records for e in r.visual_evidence]), False)
                return Answer('Unresolved text/image disagreement: ' + request['memory_value'] + ' versus '
                              + request['image_value'] + '. Human verification is required.',
                              None, 0, False, 'CONFLICT', status='uncertain', evidence=evidence)
        # Mature colour path resolves explicit identities and outstanding photo conflicts.
        from .nlp.ner import DEFAULT_LEXICON
        if (attrs == {'color'} and entity in DEFAULT_LEXICON
                and (not ref or parse_query(question, reference_time).entity_ref == ref)
                and not any(k[0] == eid for k in hidden)):
            return self.agent.ask(question, reference_time)
        relevant = [r for r in relevant if r.entity_id == eid]
        selected_records, selected_values = [], []
        parsed = None
        for attr in sorted({r.attribute for r in relevant}):
            parsed = parse_query(question, reference_time)
            parsed.entity, parsed.entity_ref, parsed.attribute = entity, ref, attr
            if (any(cue in attr for cue in ('deadline','date','birthday')) and parsed.intent == Intent.WHEN
                    and not re.search(r'\b(changed?|updated?|recorded|learned)\b',question,re.I)):
                parsed.intent = (Intent.ORIGINAL if re.search(r'\b(original|initial)\b',low) else
                    Intent.PREVIOUS if re.search(r'\b(previous|earlier)\b',low) else Intent.CURRENT)
            chain = [r for r in timeline(self.agent.store, eid, attr) if (eid,attr) not in hidden]
            conflicts = [r for r in relevant if r.attribute == attr and r.status == Status.CONTRADICTORY]
            if conflicts:
                evidence = evidence_items(RetrievalResult(parsed=parsed, records=conflicts), False)
                return Answer('Unresolved conflicting evidence requires verification.', None, 0, False,
                              'CONFLICT', status='uncertain', evidence=evidence)
            chosen = select_states(parsed, chain)
            if chosen.found:
                selected_records.extend(chain[i] for i in chosen.indices)
                selected_values.append(chosen.value)
        if not selected_records:
            return Answer('No supporting fact is stored for that time and attribute.', None, 0, False, 'CURRENT')
        evidence = evidence_items(RetrievalResult(parsed=parsed, records=selected_records,
            image_hits=[{'record': r, 'evidence': e} for r in selected_records for e in r.visual_evidence]), False)
        return Answer('; '.join(f'{r.attribute}: {r.value} ({r.timestamp[:10]})' for r in selected_records),
                      selected_values[0] if len(selected_values) == 1 else selected_values,
                      min(r.confidence for r in selected_records), True, parsed.intent.value,
                      evidence=evidence, states=[r.to_dict() for r in selected_records],
                      supporting_state_ids=[r.memory_id for r in selected_records],
                      supporting_evidence_ids=[e['evidence_id'] for e in evidence if e.get('evidence_id')])

    def chat(self, cid, text='', image=None, timestamp=None, *, remember=False):
        """One normal turn: extract -> select -> validate -> persist -> retrieve -> reply."""
        self._authorize(cid)
        from .privacy import sensitivity
        if sensitivity(text) != 'ordinary':
            return ChatTurn(Answer('Sensitive content was not saved or sent to an external provider. Remove credentials or highly sensitive details before continuing.', None, 0, False, 'CURRENT'))
        event_time = parse_ts(timestamp or self._clock())
        from datetime import timezone
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        ts = iso(event_time)
        explicit = bool(remember or re.match(r'^\s*(?:please\s+)?remember\s+', text, re.I))
        sensitive = bool(re.search(r'password|\bsecret\b|api[ _-]?key|access[ _-]?token|credit[ _-]?card|gsk_[A-Za-z0-9]+', text, re.I))
        created, observations, selections = [], [], []
        with self.agent._lock:
            sessions, counter = self.agent._sessions.copy(), self.agent._counter
            try:
                with self.agent.store.transaction():
                    mid = self._message(cid, 'user', text)
                    claims = extract_candidates(text,ts)
                    model_metadata = {}
                    if not explicit and self.privacy_settings()['automatic_memory']:
                        claims, model_metadata = self.local.extract(text,ts,claims)
                    elif sensitive:
                        claims = []
                    note_only = False
                    if explicit and not sensitive and not claims:
                        content = re.sub(r'^\s*(?:please\s+)?remember\s+(?:that|this|to)\b\s*[:,-]?\s*', '', text, flags=re.I).strip()
                        if content:
                            claims = [Claim('note', 'content', content, entity_ref=mid,
                                            source_text=text, confidence=.9, resolved_time=ts)]
                            note_only = True
                    colours = [c for c in claims if c.attribute == 'color']
                    if not self.privacy_settings()['automatic_memory'] and not explicit:
                        claims, colours = [], []
                    for i, claim in enumerate(claims):
                        existing = self.agent.store.all()
                        selection = self.selection_policy.evaluate(claim, existing, explicit=explicit)
                        extraction = model_metadata.get(extraction_key(claim))
                        selection = self.local.gate_update(claim,selection,existing,extraction)
                        extractor = (extraction.get('provider','ollama')+':'+extraction['model']+'@'+extraction['digest']+':unverified-candidate'
                                     if extraction else 'user-requested-note-v1' if note_only else EXTRACTOR_VERSION)
                        # A duplicate text fact still permits an explicit image cross-check.
                        attach = image is not None and claim.attribute == 'color' and len(colours) == 1
                        process = selection.outcome == 'promote' or (attach and selection.outcome == 'duplicate')
                        decision = None
                        sid = f'MSG_{mid}_{i}'
                        if process:
                            if claim.attribute == 'color':
                                result = self.agent.remember(claim.source_text, image if attach else None, ts, sid,
                                                             explicit_claim=claim,
                                                             extractor=extractor if extraction else 'rules-v1')
                                observations.append(result)
                                if self.agent.cfg.get('cv',{}).get('general_categories') and result.image:
                                    summary={k:v for k,v in result.image.items() if k != 'image_path'}
                                    summary.update(source_message_id=mid,event_time=ts,ingested_at=self._clock(),supports_memory_state=False)
                                    if result.image['image_path']:created.append(result.image['image_path'])
                                    self.db.execute('INSERT INTO visual_observations VALUES (?,?,?,?,?,?,?)',
                                        (summary['image_id'],cid,mid,ts,summary['ingested_at'],json.dumps(summary),result.image['image_path']))
                                for candidate in result.candidates:
                                    if candidate.visual and candidate.visual.image_path:
                                        created.append(candidate.visual.image_path)
                                decision = result.decision
                                self._link(cid, mid, decision, result.session_id)
                                if self.agent.verification_request(result):
                                    self.db.execute('INSERT INTO pending_observations VALUES (?,?,?,0)',
                                                    (result.session_id, cid, json.dumps(asdict(result))))
                            else:
                                evidence = TextEvidence(text=claim.source_text, session_id=sid,
                                    timestamp=claim.resolved_time, confidence=claim.confidence,
                                    evidence_id=f'TXT_{sid}', ingested_at=self._clock(),
                                    extractor=extractor)
                                candidate = Candidate(sid, claim.resolved_time, claim=claim,
                                    text_evidence=evidence, confidence=claim.confidence,
                                    source='automatic_conversation', ingested_at=evidence.ingested_at)
                                decision = self.agent.engine.process(candidate)
                                self._link(cid, mid, decision, sid)
                        record = {**asdict(selection), 'candidate': claim.to_dict(),
                                  'memory_id': decision.memory_id if decision else None,
                                  'lifecycle_action': decision.action.value if decision else None}
                        quote = claim.source_text
                        start = text.find(quote)
                        record['candidate']['provenance'] = {'schema_version':'candidate-memory-v2',
                            'source_message_id':mid, 'assertion':'verbatim_note' if note_only else 'explicit',
                            'source_span':[start,start+len(quote)] if start >= 0 else None,
                            'independently_verified':False}
                        if explicit:
                            record['candidate']['memory_request'] = {'explicit': True, 'priority': 1.0,
                                'retention': 'until_user_forgets', 'verbatim_note': note_only}
                            accepted = self.agent.store.get(record['memory_id']) if record['memory_id'] else None
                            if accepted is None and selection.outcome == 'duplicate':
                                accepted = next((r for r in reversed(sorted(existing, key=lambda r: parse_ts(r.timestamp)))
                                    if r.entity == claim.entity and r.attribute == claim.attribute
                                    and (not claim.entity_ref or r.entity_ref == claim.entity_ref)
                                    and r.value == claim.value.strip().lower()
                                    and parse_ts(r.timestamp) <= parse_ts(claim.resolved_time)
                                    and r.status not in {Status.CONTRADICTORY, Status.RESOLVED}), None)
                            if (accepted and accepted.status not in {Status.CONTRADICTORY, Status.RESOLVED}
                                    and not any(self.agent.verification_request(o) for o in observations)):
                                self.set_memory_priority(accepted.memory_id, True, mid)
                                record['memory_id'] = accepted.memory_id
                                record['pinned'] = True
                        if extraction:
                            record['candidate']['extraction'] = extraction
                        if attach and selection.outcome == 'duplicate':
                            record['outcome'] = 'crosscheck'
                            record['reason'] = 'Duplicate text retained for an explicit visual cross-check.'
                        selections.append(record)
                    if not claims:
                        diagnostics = self.local.last_extraction
                        notes = diagnostics.get('notes',[])
                        selections.append(dict(outcome='history_only', reason=('Sensitive content is not saved as a long-term memory. ' if explicit and sensitive else 'No safe explicit candidate extracted. ')+ ' '.join(notes),
                            usefulness=0., confidence=0., candidate=({'extraction_attempt':diagnostics,'source_text':text}
                            if diagnostics.get('method') == 'local-llm-plus-rules' else {}),
                            memory_id=None, lifecycle_action=None))
                    if image is not None and len(colours) != 1:
                        try:
                            summary=self._observe_image(cid,mid,image,ts,created)
                            reason='Visual observation stored with '+str(len(summary['objects']))+' detected objects; none is automatically associated with an existing identity.'
                        except Exception:
                            reason='Visual processing failed; valid text observations are preserved.'
                        selections.append(dict(outcome='clarify', reason=reason,
                                               usefulness=0., confidence=0., candidate={}, memory_id=None, lifecycle_action=None))
                    for record in selections:
                        self.db.execute('INSERT INTO memory_selection_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                            (uuid4().hex, cid, mid, json.dumps(record['candidate']), record['outcome'], record['reason'],
                             record['usefulness'], record['confidence'], self.selection_policy.version,
                             record['memory_id'], record['lifecycle_action'], self._clock()))
                    is_query = is_query_text(text) and not explicit
                    if is_query:
                        answer = self._references(self._automatic_answer(text, ts))
                        answer = self.local.retrieve(text,ts,answer)
                    else:
                        if any(self.agent.verification_request(o) for o in observations):
                            reply = 'The image and statement disagree. Please review the values below.'
                        elif any(r['lifecycle_action'] in {'ADD','UPDATE','HISTORICAL'} for r in selections):
                            reply = "I've saved this information and preserved any earlier states."
                        elif any(r['lifecycle_action'] == 'MERGE' for r in selections):
                            reply = "I've linked this observation to the existing memory."
                        elif any(r['outcome'] == 'clarify' for r in selections):
                            reply = 'Please clarify the fact and entity, or provide an explicit object context for the image.'
                        elif any(r['outcome'] == 'duplicate' for r in selections):
                            reply = 'That information is already in your memory.'
                        else:
                            reply = "I've kept this message in the conversation without adding a long-term memory."
                        answer = Answer(reply, None, 0, False, 'CURRENT')
                        if any(r.get('pinned') for r in selections):
                            answer.text += ' Pinned as important for long-term memory until you forget it; evidence checks still apply.'
                            if note_only:
                                answer.text += ' Saved as your verbatim note, not an independently verified fact.'
                    context = [r['content'] for r in self.transcript(cid) if r['role'] == 'user'][-4:]
                    # A refusal/clarification or accepted memory update remains
                    # authoritative; the model cannot convert it into another action.
                    if not explicit and (is_query or not claims):
                        answer = self.local.respond(text,answer,context)
                    self._message(cid, 'assistant', answer.text)
                    return ChatTurn(answer, selections, observations)
            except BaseException:
                self.agent._sessions, self.agent._counter = sessions, counter
                for name in created:
                    path = Path(name)
                    path.resolve().relative_to(self.agent.image_dir.resolve())
                    if re.fullmatch(r'IMG_[0-9a-f]{32}\.png(?:\.fernet)?', path.name):
                        path.unlink(missing_ok=True)
                raise
