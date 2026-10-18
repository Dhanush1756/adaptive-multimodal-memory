"""Small account-local SQLite embedding index; no vector database dependency.

Build a complete generation before atomically activating it. Retain old generations
for inspection; never query vectors with a different model digest or dimension.
"""
import hashlib
import json
from uuid import uuid4
import numpy as np

from ..local_runtime import LocalModelUnavailable


def document(record):
    return f'{record.entity} {record.entity_ref} {record.attribute}: {record.value}'[:1000]


def content_hash(record):
    return hashlib.sha256(document(record).encode()).hexdigest()


class LocalEmbeddingIndex:
    schema_version = 'entity-attribute-value-v1'

    def __init__(self, store):
        self.store, self.db = store, store.conn
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS local_embedding_generations (
          generation_id TEXT PRIMARY KEY, model_name TEXT NOT NULL,
          model_digest TEXT NOT NULL, dimensions INTEGER NOT NULL,
          document_schema TEXT NOT NULL, manifest_hash TEXT NOT NULL,
          active INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS local_memory_embeddings (
          generation_id TEXT NOT NULL, memory_id TEXT NOT NULL,
          content_hash TEXT NOT NULL, vector_json TEXT NOT NULL,
          PRIMARY KEY(generation_id,memory_id));
        CREATE UNIQUE INDEX IF NOT EXISTS one_local_embedding_generation
          ON local_embedding_generations(active) WHERE active=1;
        ''')

    def active(self):
        row = self.db.execute('SELECT * FROM local_embedding_generations WHERE active=1').fetchone()
        return dict(row) if row else None

    def sync(self, records, runtime, model, now, force=False, max_documents=512):
        if len(records) > max_documents:
            raise LocalModelUnavailable('Local index exceeds the configured small-prototype limit; lexical fallback active.')
        manifest = hashlib.sha256(json.dumps(sorted((r.memory_id,content_hash(r)) for r in records)).encode()).hexdigest()
        old = self.active()
        same_model = old and old['model_name'] == model['name'] and old['model_digest'] == model['digest'] and old['document_schema'] == self.schema_version
        if same_model and old['manifest_hash'] == manifest and not force:
            return old
        cached = {r['memory_id']:dict(r) for r in self.db.execute(
            'SELECT * FROM local_memory_embeddings WHERE generation_id=?', (old['generation_id'],))} if same_model and not force else {}
        prepared, missing = {}, []
        for record in records:
            item = cached.get(record.memory_id)
            if item and item['content_hash'] == content_hash(record):
                prepared[record.memory_id] = json.loads(item['vector_json'])
            else:
                missing.append(record)
        for start in range(0,len(missing),8):
            batch = missing[start:start+8]
            vectors = runtime.embed(model['name'], [document(r) for r in batch])
            prepared.update((r.memory_id,v) for r,v in zip(batch,vectors))
        dimensions = {len(v) for v in prepared.values()}
        if len(dimensions) != 1:
            raise LocalModelUnavailable('No complete, consistent embedding generation is available.')
        dimension = dimensions.pop()
        gid = uuid4().hex
        # Check the installed tag again before committing vectors; a mutable tag
        # must not silently combine different model versions in one generation.
        if runtime.identify(model['name'])['digest'] != model['digest']:
            raise LocalModelUnavailable('Embedding model changed during indexing; retry explicitly.')
        with self.store.transaction():
            self.db.execute('INSERT INTO local_embedding_generations VALUES (?,?,?,?,?,?,0,?)',
                (gid,model['name'],model['digest'],dimension,self.schema_version,manifest,now))
            self.db.executemany('INSERT INTO local_memory_embeddings VALUES (?,?,?,?)',
                [(gid,r.memory_id,content_hash(r),json.dumps(prepared[r.memory_id])) for r in records])
            self.db.execute('UPDATE local_embedding_generations SET active=0 WHERE active=1')
            self.db.execute('UPDATE local_embedding_generations SET active=1 WHERE generation_id=?',(gid,))
        return self.active()

    def rank(self, question, records, runtime, model):
        active = self.active()
        if not active or active['model_digest'] != model['digest'] or active['model_name'] != model['name']:
            raise LocalModelUnavailable('Embedding index needs a matching model generation.')
        query = np.asarray(runtime.embed(model['name'],[question])[0],dtype=np.float32)
        if len(query) != active['dimensions']:
            raise LocalModelUnavailable('Embedding dimension changed; explicit re-index required.')
        if runtime.identify(model['name'])['digest'] != model['digest']:
            raise LocalModelUnavailable('Embedding model changed during query; lexical fallback active.')
        current = {r.memory_id:r for r in records}
        ranked = []
        for row in self.db.execute('SELECT * FROM local_memory_embeddings WHERE generation_id=?',(active['generation_id'],)):
            record = current.get(row['memory_id'])
            if record is None or row['content_hash'] != content_hash(record):
                continue  # hidden, changed or another scope is never admitted
            vector = np.asarray(json.loads(row['vector_json']),dtype=np.float32)
            if len(vector) != len(query) or not np.isfinite(vector).all():
                raise LocalModelUnavailable('Stored embedding is inconsistent; lexical fallback active.')
            cosine = float(np.dot(vector,query) / max(float(np.linalg.norm(vector)*np.linalg.norm(query)),1e-12))
            ranked.append((record,cosine))
        return sorted(ranked,key=lambda pair:pair[1],reverse=True)
