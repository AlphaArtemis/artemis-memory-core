"""Immutable local acquisitions and FTS5 retrieval, extracted from the local core.

The operator controls the state directory. Hashes detect inconsistencies, not a
malicious operator replacing both originals and registry. No source text runs.
"""
import contextlib
import datetime as dt
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
import unicodedata

from .safeio import (MemoryError, canonical, fail, open_readonly, parse, read_bytes,
                     secure_directory, sha, signature, write_immutable)

SCHEMA = 'artemis-memory-community/1'
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DOCUMENT_CHARS = 100000
ID = re.compile(r'v1:[a-f0-9]{64}\Z')
STATES = {'possibility', 'intention', 'decision', 'reported_result',
          'attested_action', 'correction', 'unspecified'}
REPRESENTATIONS = {'original_document', 'capsule_summary', 'synthetic_test'}
SECRET_PATTERNS = [
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    re.compile(r'\bsk-(?:proj-|admin-)?[A-Za-z0-9_-]{20,}'),
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
    re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    re.compile(r'''(?im)\b(?:api[_ -]?key|password|passwd|secret|access[_ -]?token|bearer)\s*[:=]\s*["']?[^\s"',;]{8,}'''),
]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def bounded_text(value, field, limit):
    if type(value) is not str or not value.strip() or '\x00' in value or len(value) > limit:
        fail('invalid_' + field)
    return value


def iso_date(value):
    if value is None:
        return None
    bounded_text(value, 'event_at', 50)
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            fail('timezone_required_event_at')
        return parsed.astimezone(dt.timezone.utc).isoformat()
    except ValueError as error:
        if isinstance(error, MemoryError):
            raise
        fail('invalid_event_at')


def secret_guard(value):
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        fail('credential_review_required')


def _schema_sql():
    return '''
    PRAGMA foreign_keys=ON;
    CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE acquisitions(source_sha256 TEXT PRIMARY KEY,source_relpath TEXT NOT NULL,
      imported_at TEXT NOT NULL,format TEXT NOT NULL,approval_sha256 TEXT NOT NULL,
      transformations_json TEXT NOT NULL);
    CREATE TABLE documents(id TEXT PRIMARY KEY,logical_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,
      derived_relpath TEXT NOT NULL,derived_sha256 TEXT NOT NULL,title TEXT NOT NULL,
      project TEXT NOT NULL,author TEXT NOT NULL,event_at TEXT,imported_at TEXT NOT NULL,
      representation TEXT NOT NULL,assertion_status TEXT NOT NULL,supersedes TEXT,
      FOREIGN KEY(source_sha256) REFERENCES acquisitions(source_sha256),
      FOREIGN KEY(supersedes) REFERENCES documents(id));
    CREATE INDEX document_logical ON documents(logical_id);
    CREATE INDEX document_supersedes ON documents(supersedes);
    CREATE VIRTUAL TABLE local_fts USING fts5(id UNINDEXED,text,
      tokenize='unicode61 remove_diacritics 2');
    CREATE TABLE denials(id TEXT PRIMARY KEY,reason TEXT NOT NULL,
      FOREIGN KEY(id) REFERENCES documents(id));
    CREATE TRIGGER acquisitions_no_update BEFORE UPDATE ON acquisitions BEGIN SELECT RAISE(ABORT,'immutable'); END;
    CREATE TRIGGER acquisitions_no_delete BEFORE DELETE ON acquisitions BEGIN SELECT RAISE(ABORT,'immutable'); END;
    CREATE TRIGGER documents_no_update BEFORE UPDATE ON documents BEGIN SELECT RAISE(ABORT,'immutable'); END;
    CREATE TRIGGER documents_no_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT,'immutable'); END;
    '''


class Engine:
    """Explicit, local-only store. Call initialize before staging inbox files."""
    def __init__(self, state):
        if state is None:
            fail('state_directory_required')
        self.state_dir = Path(state)
        if not self.state_dir.is_absolute() or '..' in self.state_dir.parts:
            fail('unsafe_directory')
        self.db_path = self.state_dir / 'registry.sqlite'
        self.inbox = self.state_dir / 'inbox'

    def initialize(self):
        root_fd = secure_directory(self.state_dir, create=True)
        try:
            info = os.fstat(root_fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022:
                fail('state_directory_permissions')
        finally:
            os.close(root_fd)
        for folder in (self.inbox, self.state_dir / 'originals', self.state_dir / 'derived'):
            os.close(secure_directory(folder, create=True))
        if os.path.lexists(self.db_path):
            with self._database():
                pass
            return {'status': 'ALREADY_INITIALIZED', 'source_writes': 0}
        staging = self.state_dir / ('.registry-' + secrets.token_hex(8) + '.pending')
        write_immutable(staging, b'')
        db = sqlite3.connect(staging)
        try:
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('PRAGMA synchronous=FULL')
            db.executescript(_schema_sql())
            db.executemany('INSERT INTO meta VALUES(?,?)',
                           [('schema', SCHEMA), ('created_at', now()), ('revision', '0'),
                            ('instance_id', secrets.token_hex(16))])
            db.commit()
        finally:
            db.close()
        try:
            write_immutable(self.db_path, read_bytes(staging, 32 * 1024 * 1024))
        finally:
            staging.unlink(missing_ok=True)
        return {'status': 'INITIALIZED', 'source_writes': 0}

    @contextlib.contextmanager
    def _database(self, write=False):
        fd = None
        folder = None
        db = None
        try:
            folder = secure_directory(self.state_dir)
            directory_info = os.fstat(folder)
            if directory_info.st_uid != os.getuid() or stat.S_IMODE(directory_info.st_mode) & 0o022:
                fail('state_directory_permissions')
            fd = open_readonly(self.db_path)
            identity = (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
            def check_identity():
                current = open_readonly(self.db_path)
                try:
                    info = os.fstat(current)
                    if (info.st_dev, info.st_ino) != identity:
                        fail('registry_replaced')
                finally:
                    os.close(current)
            if write:
                db = sqlite3.connect(self.db_path, timeout=5)
                check_identity()
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('PRAGMA synchronous=FULL')
            else:
                db = sqlite3.connect(f'file:/dev/fd/{fd}?mode=ro', uri=True, timeout=5)
                db.execute('PRAGMA query_only=ON')
            db.row_factory = sqlite3.Row
            deadline = time.monotonic() + 5
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
            values = dict(db.execute('SELECT key,value FROM meta'))
            if values.get('schema') != SCHEMA:
                fail('registry_schema_mismatch')
            if not values.get('revision', '').isdigit():
                fail('invalid_registry_revision')
            if not re.fullmatch(r'[a-f0-9]{32}', values.get('instance_id', '')):
                fail('invalid_registry_instance')
            yield db
            check_identity()
        except (OSError, sqlite3.Error):
            fail('registry_unavailable')
        finally:
            if db is not None:
                db.close()
            if fd is not None:
                os.close(fd)
            if folder is not None:
                os.close(folder)

    def _revision(self, db):
        return db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]

    def _instance(self, db):
        return db.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]

    def _advance(self, db):
        db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")

    def _guard(self, revision, source_id=None):
        with self._database() as db:
            if source_id is not None:
                denied = db.execute('SELECT reason FROM denials WHERE id=?', (source_id,)).fetchone()
                if denied:
                    fail('source_' + denied[0])
            if (self._instance(db), self._revision(db)) != revision:
                fail('scope_changed_retry')

    def status(self):
        with self._database() as db:
            count = db.execute('SELECT count(*) FROM documents').fetchone()[0]
            denied = db.execute('SELECT count(*) FROM denials').fetchone()[0]
            acquired = db.execute('SELECT count(*) FROM acquisitions').fetchone()[0]
            check = db.execute('PRAGMA quick_check').fetchone()[0]
            revision = self._revision(db)
        return {'status': 'PASS' if check == 'ok' else 'BLOCKED', 'document_versions': count,
                'accessible_versions': count - denied, 'denied_versions': denied,
                'acquisitions': acquired, 'scope_revision': revision, 'sqlite_quick_check': check,
                'method': 'local_acquisition_FTS5', 'source_writes': 0, 'remote_access': False,
                'source_bodies_checked': False, 'historical_claim_verified': False}

    def _inbox_bytes(self, filename):
        if type(filename) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.json', filename):
            fail('invalid_inbox_filename')
        return read_bytes(self.inbox / filename, MAX_FILE_BYTES)

    def _capsule(self, data):
        required = {'schema', 'document_id', 'title', 'project', 'author', 'event_at',
                    'representation', 'assertion_status', 'text', 'provenance'}
        allowed = required | {'evidence_refs', 'supersedes', 'corrects', 'parent_source_id',
                              'branch_id', 'attachments', 'excluded'}
        if type(data) is not dict or set(data) - allowed or required - set(data):
            fail('invalid_capsule_fields')
        if data['schema'] != 'artemis-memory-capsule/1':
            fail('unsupported_schema')
        if type(data['document_id']) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', data['document_id']):
            fail('invalid_document_id')
        if (type(data['representation']) is not str or data['representation'] not in REPRESENTATIONS
                or type(data['assertion_status']) is not str or data['assertion_status'] not in STATES):
            fail('invalid_document_classification')
        provenance = data['provenance']
        if type(provenance) is not dict or set(provenance) != {'origin', 'approved_by'}:
            fail('invalid_provenance')
        for key, value in provenance.items():
            bounded_text(value, 'provenance_' + key, 1000)
        evidence = data.get('evidence_refs', [])
        if type(evidence) is not list or len(evidence) > 20:
            fail('invalid_evidence_refs')
        for value in evidence:
            bounded_text(value, 'evidence_ref', 240)
        if data['assertion_status'] == 'attested_action' and not evidence:
            fail('attested_action_requires_evidence')
        for field in ('supersedes', 'parent_source_id'):
            value = data.get(field)
            if value is not None and (type(value) is not str or not ID.fullmatch(value)):
                fail('invalid_' + field)
        corrects = data.get('corrects', [])
        if (type(corrects) is not list or len(corrects) > 20
                or any(type(v) is not str or not ID.fullmatch(v) for v in corrects)
                or len(set(corrects)) != len(corrects)):
            fail('invalid_corrects')
        branch = data.get('branch_id')
        if branch is not None:
            bounded_text(branch, 'branch_id', 100)
        attachments = data.get('attachments', [])
        if type(attachments) is not list or len(attachments) > 20:
            fail('invalid_attachments')
        for attachment in attachments:
            if (type(attachment) is not dict or set(attachment) != {'name', 'status'}
                    or attachment['status'] != 'unavailable'):
                fail('invalid_attachment')
            bounded_text(attachment['name'], 'attachment_name', 200)
        excluded = data.get('excluded', False)
        if type(excluded) is not bool:
            fail('invalid_excluded')
        return {'logical_id': 'capsule:' + data['document_id'],
                'title': bounded_text(data['title'], 'title', 300),
                'project': bounded_text(data['project'], 'project', 200),
                'author': bounded_text(data['author'], 'author', 200),
                'event_at': iso_date(data['event_at']), 'representation': data['representation'],
                'assertion_status': data['assertion_status'],
                'text': bounded_text(data['text'], 'text', MAX_DOCUMENT_CHARS),
                'provenance': provenance, 'evidence_refs': evidence,
                'supersedes': data.get('supersedes'), 'corrects': corrects,
                'parent_source_id': data.get('parent_source_id'), 'branch_id': branch,
                'attachments': attachments, 'excluded': excluded, 'source_locator': '/text',
                'transformations': []}

    def _document(self, raw):
        secret_guard(raw.decode('utf-8', 'replace'))
        doc = self._capsule(parse(raw))
        # JSON escapes must not hide a recognizable credential in decoded text
        # or metadata. This screen is conservative, not guaranteed anonymization.
        secret_guard(canonical(doc).decode('utf-8'))
        doc['text_sha256'] = sha(doc['text'].encode())
        doc['id'] = 'v1:' + sha(canonical(doc))
        return doc

    def _relations(self, db, doc):
        refs = doc['corrects'] + [x for x in (doc['supersedes'], doc['parent_source_id']) if x]
        for source_id in refs:
            row = db.execute('SELECT logical_id FROM documents WHERE id=?', (source_id,)).fetchone()
            if row is None:
                fail('relation_source_missing')
            if source_id == doc['supersedes'] and row[0] != doc['logical_id']:
                fail('supersedes_different_document')

    def _plan(self, filename):
        raw = self._inbox_bytes(filename)
        doc = self._document(raw)
        with self._database() as db:
            self._relations(db, doc)
            revision = self._revision(db)
            instance = self._instance(db)
            exists = db.execute('SELECT 1 FROM documents WHERE id=?', (doc['id'],)).fetchone() is not None
        approval = sha(canonical({'source_sha256': sha(raw), 'document_ids': [doc['id']],
                                  'scope_revision': revision, 'instance_id': instance, 'schema': SCHEMA}))
        return {'raw': raw, 'document': doc, 'source_sha256': sha(raw),
                'approval_sha256': approval, 'revision': revision, 'instance': instance,
                'exists': exists}

    def prepare_import(self, filename):
        plan = self._plan(filename)
        doc = plan['document']
        return {'status': 'PREVIEW', 'approval_sha256': plan['approval_sha256'],
                'source_sha256': plan['source_sha256'], 'document_count': 1,
                'new_documents': int(not plan['exists']),
                'documents': [{k: doc[k] for k in ('id', 'title', 'representation', 'supersedes', 'corrects', 'excluded')}],
                'writes_performed': 0, 'remote_access': False}

    def apply_import(self, filename, approval_sha256):
        plan = self._plan(filename)
        if type(approval_sha256) is not str or approval_sha256 != plan['approval_sha256']:
            fail('approval_mismatch')
        doc = plan['document']
        stamp = now()
        with self._database(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            if self._revision(db) != plan['revision'] or self._instance(db) != plan['instance']:
                fail('scope_changed_retry')
            self._relations(db, doc)
            if db.execute('SELECT 1 FROM documents WHERE id=?', (doc['id'],)).fetchone():
                return {'status': 'ALREADY_IMPORTED', 'document_ids': [doc['id']], 'new_document_count': 0, 'source_writes': 0}
            source_rel = 'originals/' + plan['source_sha256'] + '.json'
            write_immutable(self.state_dir / source_rel, plan['raw'])
            db.execute('INSERT OR IGNORE INTO acquisitions VALUES(?,?,?,?,?,?)',
                       (plan['source_sha256'], source_rel, stamp, 'capsule', approval_sha256, '[]'))
            derived_rel = 'derived/' + doc['id'][3:] + '.json'
            body = canonical(doc)
            write_immutable(self.state_dir / derived_rel, body)
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (doc['id'], doc['logical_id'], plan['source_sha256'], derived_rel, sha(body),
                        doc['title'], doc['project'], doc['author'], doc['event_at'], stamp,
                        doc['representation'], doc['assertion_status'], doc['supersedes']))
            db.execute('INSERT INTO local_fts(id,text) VALUES(?,?)', (doc['id'], doc['text']))
            if doc['excluded']:
                db.execute('INSERT INTO denials VALUES(?,?)', (doc['id'], 'excluded'))
            self._advance(db)
            db.commit()
        return {'status': 'IMPORTED', 'document_ids': [doc['id']], 'new_document_count': 1,
                'source_sha256': plan['source_sha256'], 'source_writes': 0,
                'new_custody_copies': 1, 'remote_access': False, 'truth_verified': False}

    def revoke(self, source_id):
        self._source_id(source_id)
        with self._database(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM documents WHERE id=?', (source_id,)).fetchone():
                fail('unknown_source_id')
            exists = db.execute('SELECT 1 FROM denials WHERE id=?', (source_id,)).fetchone()
            if not exists:
                db.execute('INSERT INTO denials VALUES(?,?)', (source_id, 'revoked'))
                self._advance(db)
            db.commit()
        return {'status': 'DENIED', 'source_id': source_id, 'source_writes': 0,
                'custody_copies_deleted': False}

    @staticmethod
    def _source_id(source_id):
        if type(source_id) is not str or not ID.fullmatch(source_id):
            fail('invalid_source_id')

    def _local(self, source_id):
        self._source_id(source_id)
        with self._database() as db:
            revision = (self._instance(db), self._revision(db))
            denied = db.execute('SELECT reason FROM denials WHERE id=?', (source_id,)).fetchone()
            if denied:
                fail('source_' + denied[0])
            row = db.execute('SELECT d.*,a.source_relpath FROM documents d JOIN acquisitions a USING(source_sha256) WHERE d.id=?', (source_id,)).fetchone()
            if row is None:
                fail('unknown_source_id')
            newer = [r[0] for r in db.execute('''SELECT id FROM documents WHERE supersedes=?
                AND id NOT IN (SELECT id FROM denials) ORDER BY id''', (source_id,))]
        row = dict(row)
        for field, prefix in [('derived_relpath', 'derived/'), ('source_relpath', 'originals/')]:
            if not re.fullmatch(re.escape(prefix) + r'[a-f0-9]{64}\.json', row[field]):
                fail('invalid_registry_path')
        original = read_bytes(self.state_dir / row['source_relpath'], MAX_FILE_BYTES, row['source_sha256'])
        raw = read_bytes(self.state_dir / row['derived_relpath'], MAX_FILE_BYTES, row['derived_sha256'])
        doc = parse(raw)
        if doc != self._document(original) or doc.get('id') != source_id:
            fail('derived_integrity_mismatch')
        for key in ('logical_id', 'title', 'project', 'author', 'event_at', 'representation', 'assertion_status', 'supersedes'):
            if row[key] != doc[key]:
                fail('registry_metadata_mismatch')
        if doc['excluded']:
            fail('source_excluded')
        self._guard(revision, source_id)
        return row, doc, newer, revision

    def fetch(self, source_id, start=0, limit=6000):
        if type(start) is not int or start < 0 or type(limit) is not int or not 1 <= limit <= 6000:
            fail('invalid_excerpt_window')
        row, doc, newer, revision = self._local(source_id)
        text = doc['text']
        if start >= len(text):
            fail('excerpt_start_outside_source')
        end = min(len(text), start + limit)
        excerpt = text[start:end]
        meta = {k: v for k, v in doc.items() if k not in ('text', 'id', 'text_sha256', 'excluded')}
        result = {'status': 'PASS', **meta, 'source_id': source_id, 'text': excerpt,
                  'imported_at': row['imported_at'], 'original_sha256': row['source_sha256'],
                  'derived_sha256': row['derived_sha256'], 'superseded_by': newer,
                  'version_state': 'has_later_edition' if newer else 'no_later_edition_registered',
                  'citation': {'start': start, 'end': end, 'text_sha256': doc['text_sha256'],
                               'excerpt_sha256': sha(excerpt.encode()), 'basis': 'original_json_text_string'},
                  'source_integrity_verified': True, 'historical_claim_verified': False,
                  'assertion_status_is_declared_not_fact_verification': True,
                  'total_characters': len(text), 'next_start': end if end < len(text) else None,
                  'truncated': start != 0 or end != len(text), 'untrusted_content': True,
                  'source_writes': 0, 'remote_access': False}
        read_bytes(self.state_dir / row['source_relpath'], MAX_FILE_BYTES, row['source_sha256'])
        read_bytes(self.state_dir / row['derived_relpath'], MAX_FILE_BYTES, row['derived_sha256'])
        self._guard(revision, source_id)
        return result

    def search(self, query, limit=5, project=None, cursor=None, filters=None):
        bounded_text(query, 'query', 500)
        if type(limit) is not int or not 1 <= limit <= 5:
            fail('invalid_result_limit')
        if filters is not None and type(filters) is not dict:
            fail('invalid_filters')
        filters = dict(filters or {})
        if set(filters) - {'project', 'author', 'representation', 'branch_id', 'from', 'to'}:
            fail('unsupported_filters')
        if project is not None:
            bounded_text(project, 'project', 200)
            if 'project' in filters and filters['project'] != project:
                fail('conflicting_project_filter')
            filters['project'] = project
        for key, value in filters.items():
            bounded_text(value, 'filter_' + key, 200)
            if key in ('from', 'to'):
                try:
                    if dt.date.fromisoformat(value).isoformat() != value:
                        fail('invalid_date_filter')
                except ValueError:
                    fail('invalid_date_filter')
        if filters.get('from') and filters.get('to') and filters['from'] > filters['to']:
            fail('invalid_date_range')
        if filters.get('representation') and filters['representation'] not in REPRESENTATIONS:
            fail('invalid_representation_filter')
        folded = ''.join(c for c in unicodedata.normalize('NFKD', query.casefold()) if not unicodedata.combining(c))
        tokens = list(dict.fromkeys(re.findall(r'\w+', folded)))[:16]
        if not tokens:
            fail('empty_query')
        match = ' AND '.join('"' + token.replace('"', '""') + '"' for token in tokens)
        with self._database() as db:
            revision = self._revision(db)
            instance = self._instance(db)
            key = sha(canonical([instance, revision, query, filters, limit]))
            offset = 0
            if cursor is not None:
                if type(cursor) is not str or len(cursor) > 100:
                    fail('invalid_cursor')
                parts = cursor.split(':')
                if len(parts) != 2 or parts[0] != key:
                    fail('cursor_query_or_scope_mismatch')
                if not parts[1].isdigit() or str(int(parts[1])) != parts[1] or int(parts[1]) > 10000000:
                    fail('invalid_cursor')
                offset = int(parts[1])
            rows = db.execute('''SELECT f.id,bm25(local_fts) AS score FROM local_fts f
                JOIN documents d ON d.id=f.id WHERE local_fts MATCH ?
                ORDER BY score,f.id LIMIT ? OFFSET ?''', (match, limit + 1, offset)).fetchall()
        next_cursor = key + ':' + str(offset + limit) if len(rows) > limit else None
        results = []
        for row in rows[:limit]:
            try:
                page = self.fetch(row['id'], 0, 240)
            except MemoryError as error:
                if error.code in ('source_revoked', 'source_excluded'):
                    continue
                raise
            if any(page.get(k) != v for k, v in filters.items() if k not in ('from', 'to')):
                continue
            day = (page.get('event_at') or '')[:10]
            if filters.get('from') and (not day or day < filters['from']):
                continue
            if filters.get('to') and (not day or day > filters['to']):
                continue
            item = {k: v for k, v in page.items() if k not in ('text', 'next_start', 'truncated', 'total_characters')}
            item.update(snippet=page['text'], candidate_only=True,
                        fetch={'source_id': page['source_id'], 'start': 0, 'limit': 240})
            results.append(item)
        # Revalidate every emitted source after all candidates, then policy once.
        for item in results:
            if self.fetch(item['source_id'], 0, 240)['citation'] != item['citation']:
                fail('source_changed_during_search')
        self._guard((instance, revision))
        return {'status': 'CANDIDATES' if results else 'NO_MATCH_ON_THIS_PAGE', 'results': results,
                'next_cursor': next_cursor, 'scope_revision': revision,
                'method': 'local_acquisition_FTS5', 'candidate_limit_reached': next_cursor is not None,
                'pagination': 'Reuse query, filters and limit; an empty page with a cursor is not exhaustion.',
                'answer_generated': False, 'historical_claim_verified': False,
                'source_writes': 0, 'remote_access': False}
