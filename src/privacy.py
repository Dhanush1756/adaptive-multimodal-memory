"""Local privacy gates. Classification is conservative pattern matching, not DLP."""
import re


def sensitivity(text):
    if re.search(r'\b(?:password|api[ _-]?key|access[ _-]?token|private key|credit[ _-]?card)\b|gsk_[\w]+|-----BEGIN .*PRIVATE KEY', text, re.I):
        return 'credential'
    if re.search(r'\b(?:allergy|allergic|diagnosed|diagnosis|medical record|passport|aadhaar|social security|sexual orientation|religious belief)\b', text, re.I):
        return 'highly_sensitive'
    return 'ordinary'


class PrivacyControls:
    def read_evidence(self, path):
        self._authorize()
        from pathlib import Path
        file = Path(path).resolve()
        if not self.agent.image_dir or not file.is_relative_to(self.agent.image_dir.resolve()):
            from .accounts import AuthenticationError
            raise AuthenticationError('Evidence is unavailable.')
        data = file.read_bytes()
        if file.name.endswith('.fernet'):
            if not self.agent.protection:
                from .accounts import AuthenticationError
                raise AuthenticationError('Evidence is unavailable.')
            data = self.agent.protection.decrypt(data)
        return data

    def _init_privacy(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS privacy_preferences (
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), external_processing INTEGER NOT NULL DEFAULT 0,
          automatic_memory INTEGER NOT NULL DEFAULT 1, retention_days INTEGER NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO privacy_preferences VALUES (1,0,1,0);
        CREATE TABLE IF NOT EXISTS privacy_audit (
          event_id TEXT PRIMARY KEY, action TEXT NOT NULL, created_at TEXT NOT NULL,
          actor TEXT NOT NULL, affected_records INTEGER NOT NULL);
        ''')

    def privacy_settings(self):
        self._authorize()
        return dict(self.db.execute('SELECT * FROM privacy_preferences WHERE singleton=1').fetchone())

    def set_privacy(self, *, external_processing=False, automatic_memory=True, retention_days=0):
        self._authorize()
        if isinstance(retention_days, bool) or not isinstance(retention_days, int) or not 0 <= retention_days <= 3650:
            raise ValueError('Retention must be 0–3650 days; zero disables automatic expiry.')
        with self.agent.store.transaction():
            self.db.execute('UPDATE privacy_preferences SET external_processing=?,automatic_memory=?,retention_days=? WHERE singleton=1',
                            (int(bool(external_processing)), int(bool(automatic_memory)), retention_days))
        self._clear_private_caches()

    def _clear_private_caches(self):
        self.local.extraction_cache.clear()
        self.local.last_extraction = {'method':'deterministic','notes':[]}
        self.local.last_response = {'method':'deterministic'}
        self.local.last_retrieval = {'method':'lexical'}

    def export_workspace(self):
        """An intentional plaintext export; no secrets, filesystem paths or model vectors."""
        self._authorize()
        def public(value):
            if isinstance(value, dict):
                return {k:public(v) for k,v in value.items() if k not in {'image_path','embedding','vector_json'}}
            if isinstance(value, list): return [public(v) for v in value]
            return value
        return public({'format':'aegm-account-export-v1', 'created_at':self._clock(),
            'conversations':[{'conversation':c,'messages':self.transcript(c['conversation_id'])} for c in self.list()],
            'memories':self.memories(), 'resolutions':self.audit(),
            'visual_observations':[r for c in self.list() for r in self.visual_observations(c['conversation_id'])],
            'privacy':self.privacy_settings()})

    def erase_workspace(self, confirmation):
        """Explicit full-workspace erasure; no selective deletion that leaves copies."""
        self._authorize()
        if confirmation != 'DELETE MY STORED DATA':
            raise ValueError('Type DELETE MY STORED DATA to confirm permanent workspace erasure.')
        from pathlib import Path
        from uuid import uuid4
        # Fixed account-local allowlist, never caller-supplied paths or SQL identifiers.
        tables = ('memory','conflict_resolutions','conversations','messages','memory_events',
                  'conversation_summaries','pending_observations','memory_selection_audit',
                  'memory_visibility_events','memory_priority_events','local_memory_embeddings',
                  'local_embedding_generations','visual_observations')
        with self.agent._lock, self.agent.store.transaction():
            count = self.db.execute('SELECT COUNT(*) FROM memory').fetchone()[0]
            present = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in tables:
                if table in present:self.db.execute('DELETE FROM '+table)
            self.db.execute('INSERT INTO privacy_audit VALUES (?,?,?,?,?)',
                (uuid4().hex,'workspace_erased',self._clock(),'authenticated_user',count))
        self._clear_private_caches()
        self.agent._sessions.clear()
        self.agent._counter = 0
        # DB references disappear first. Orphan removal can be retried idempotently.
        failures = 0
        directory = self.agent.image_dir
        if directory and directory.is_dir():
            boundary = directory.resolve()
            for path in directory.iterdir():
                if not re.fullmatch(r'IMG_[0-9a-f]{32}\.png(?:\.fernet)?', path.name):continue
                try:
                    path.resolve().relative_to(boundary)
                    path.unlink(missing_ok=True)
                except (OSError,ValueError):failures += 1
        # secure_delete removes deleted content from SQLite's logical pages;
        # it is not a guarantee about SSD wear-leveling, snapshots or backups.
        with self.agent._lock:
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            self.db.execute('VACUUM')
        return {'memories_erased':count,'evidence_cleanup_pending':failures,
                'backups_and_provider_copies':'not controlled by this application'}

    def apply_retention(self):
        """Opt-in complete-workspace inactivity expiry, never a selective source purge."""
        self._authorize()
        from datetime import timedelta
        from .utils import parse_ts
        days = self.privacy_settings()['retention_days']
        last = self.db.execute('SELECT MAX(created_at) FROM messages').fetchone()[0]
        if days and last and parse_ts(last) < parse_ts(self._clock()) - timedelta(days=days):
            return self.erase_workspace('DELETE MY STORED DATA')
        return None
