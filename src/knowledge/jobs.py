"""One durable control database; no parser/model work inside transactions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from src.knowledge.config import KnowledgeServiceConfig

ACTIVE_STATES = ("queued", "parsing", "indexing", "publishing")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class KnowledgeJobStore:
    def __init__(self, config: KnowledgeServiceConfig):
        self.config = config
        control = config.root_dir.expanduser().resolve() / "control"
        if control.is_symlink():
            raise ValueError("knowledge_path_escape")
        control.mkdir(parents=True, exist_ok=True)
        self.path = control / "knowledge.sqlite3"
        if self.path.is_symlink():
            raise ValueError("knowledge_path_escape")
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            schema_version = db.execute("PRAGMA user_version").fetchone()[0]
            if schema_version not in (0, 1):
                raise ValueError("knowledge_schema_version_mismatch")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT NOT NULL,
                    signature TEXT NOT NULL, active_namespace TEXT, revision INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 0, UNIQUE(tenant_id, project_id));
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, kb TEXT NOT NULL REFERENCES projects(id),
                    sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, file_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL, original TEXT NOT NULL, signature TEXT NOT NULL,
                    published_at TEXT, UNIQUE(kb, sha256));
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kb TEXT NOT NULL REFERENCES projects(id),
                    document_id TEXT NOT NULL REFERENCES documents(id), signature TEXT NOT NULL,
                    identity TEXT NOT NULL, status TEXT NOT NULL, error_code TEXT,
                    attempt INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    started_at TEXT, target TEXT, base_revision INTEGER);
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_document ON jobs(kb, document_id, signature)
                    WHERE status IN ('queued','parsing','indexing','publishing');
                CREATE TABLE IF NOT EXISTS requests (
                    kb TEXT NOT NULL, request_id TEXT NOT NULL, identity TEXT NOT NULL,
                    sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, job_id TEXT,
                    document_id TEXT NOT NULL, PRIMARY KEY(kb, request_id));
                CREATE TABLE IF NOT EXISTS uploads (
                    id TEXT PRIMARY KEY, kb TEXT NOT NULL, request_id TEXT NOT NULL,
                    identity TEXT NOT NULL, file_ref TEXT NOT NULL, original TEXT NOT NULL,
                    expires_at REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(kb, request_id));
                CREATE TABLE IF NOT EXISTS upload_reservations (
                    kb TEXT NOT NULL, request_id TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL, PRIMARY KEY(kb,request_id));
                CREATE TABLE IF NOT EXISTS generations (
                    namespace TEXT PRIMARY KEY, kb TEXT NOT NULL, signature TEXT NOT NULL,
                    base_revision INTEGER NOT NULL, documents TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, stage TEXT NOT NULL,
                    kind TEXT NOT NULL, input_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL, provider_usage TEXT, usage_source TEXT NOT NULL DEFAULT 'unknown');
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def register(self, tenant_id, project_id, signature, *, enabled=False):
        with self.connect(write=True) as db:
            existing = db.execute(
                "SELECT * FROM projects WHERE tenant_id=? AND project_id=?",
                (tenant_id, project_id),
            ).fetchone()
            if existing:
                if existing["signature"] != signature:
                    raise ValueError("knowledge_processing_config_changed")
                return dict(existing)
            kb = "kb_" + uuid4().hex
            db.execute(
                "INSERT INTO projects(id,tenant_id,project_id,signature,enabled) VALUES(?,?,?,?,?)",
                (kb, tenant_id, project_id, signature, int(enabled)),
            )
        return self.project(kb)

    def project(self, kb):
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (kb,)).fetchone()
        if row is None:
            raise ValueError("knowledge_not_found")
        return dict(row)

    def enable(self, kb, enabled):
        with self.connect(write=True) as db:
            if enabled:
                project = db.execute(
                    "SELECT * FROM projects WHERE id=?", (kb,)
                ).fetchone()
                if not project:
                    raise ValueError("knowledge_not_found")
                searchable = self._visible(db, project)
                published = {
                    r[0]
                    for r in db.execute(
                        "SELECT id FROM documents WHERE kb=? AND published_at IS NOT NULL",
                        (kb,),
                    )
                }
                if not published.issubset(searchable):
                    raise ValueError("knowledge_rollback_upload_disabled")
            if (
                db.execute(
                    "UPDATE projects SET enabled=? WHERE id=?", (int(enabled), kb)
                ).rowcount
                != 1
            ):
                raise ValueError("knowledge_not_found")

    @staticmethod
    def _visible(db, project):
        row = db.execute(
            "SELECT documents,signature FROM generations WHERE namespace=? AND kb=?",
            (project["active_namespace"], project["id"]),
        ).fetchone()
        return (
            set(json.loads(row["documents"]))
            if row and row["signature"] == project["signature"]
            else set()
        )

    def receipt(self, kb, job_id=None, document_id=None, *, reused=None):
        with self.connect() as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (kb,)).fetchone()
            job = (
                db.execute(
                    "SELECT * FROM jobs WHERE id=? AND kb=?", (job_id, kb)
                ).fetchone()
                if job_id
                else None
            )
            if job_id and not job:
                raise ValueError("knowledge_not_found")
            document_id = job["document_id"] if job else document_id
            doc = db.execute(
                "SELECT * FROM documents WHERE id=? AND kb=?", (document_id, kb)
            ).fetchone()
            if not doc or not project:
                raise ValueError("knowledge_not_found")
            result = dict(
                version=1,
                job_id=job_id,
                document_id=document_id,
                file_name=doc["file_name"],
                status=job["status"] if job else "ready",
                searchable=document_id in self._visible(db, project),
                error_code=job["error_code"] if job else None,
                created_at=job["created_at"] if job else doc["published_at"],
                updated_at=job["updated_at"] if job else doc["published_at"],
            )
            if reused is not None:
                result["reused"] = reused
            return result

    def submit(self, kb, request_id, identity, file_ref, original, signature):
        stamp = now()
        identity_json = json.dumps(identity, sort_keys=True)
        with self.connect(write=True) as db:
            project = db.execute("SELECT * FROM projects WHERE id=?", (kb,)).fetchone()
            if not project:
                raise ValueError("knowledge_not_found")
            if project["signature"] != signature:
                raise ValueError("knowledge_processing_config_changed")
            request = db.execute(
                "SELECT * FROM requests WHERE kb=? AND request_id=?", (kb, request_id)
            ).fetchone()
            if request:
                if (request["identity"], request["sha256"], request["size_bytes"]) != (
                    identity_json,
                    file_ref["sha256"],
                    file_ref["size_bytes"],
                ):
                    raise ValueError("knowledge_content_conflict")
                job_id, doc_id, reused = request["job_id"], request["document_id"], True
            else:
                if not project["enabled"]:
                    raise ValueError("knowledge_upload_disabled")
                doc = db.execute(
                    "SELECT * FROM documents WHERE kb=? AND sha256=?",
                    (kb, file_ref["sha256"]),
                ).fetchone()
                if doc and doc["size_bytes"] != file_ref["size_bytes"]:
                    raise ValueError("knowledge_content_conflict")
                if doc and doc["signature"] != signature:
                    raise ValueError("knowledge_processing_config_changed")
                if not doc:
                    count, size = db.execute(
                        "SELECT count(*),coalesce(sum(size_bytes),0) FROM documents WHERE kb=?",
                        (kb,),
                    ).fetchone()
                    if (
                        count >= self.config.max_project_documents
                        or size + file_ref["size_bytes"]
                        > self.config.max_project_original_bytes
                    ):
                        raise ValueError("knowledge_quota_exceeded")
                    doc_id = "kd_" + uuid4().hex
                    db.execute(
                        "INSERT INTO documents(id,kb,sha256,size_bytes,file_name,mime_type,original,signature) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            doc_id,
                            kb,
                            file_ref["sha256"],
                            file_ref["size_bytes"],
                            file_ref["file_name"],
                            file_ref["mime_type"],
                            original,
                            signature,
                        ),
                    )
                else:
                    doc_id = doc["id"]
                pending = db.execute(
                    "SELECT id FROM jobs WHERE kb=? AND document_id=? AND signature=? AND status IN ('queued','parsing','indexing','publishing')",
                    (kb, doc_id, signature),
                ).fetchone()
                visible = doc_id in self._visible(db, project)
                if visible or pending:
                    successful = db.execute(
                        "SELECT id FROM jobs WHERE kb=? AND document_id=? AND status='ready' ORDER BY created_at DESC LIMIT 1",
                        (kb, doc_id),
                    ).fetchone()
                    job_id = (
                        pending["id"]
                        if pending
                        else successful["id"]
                        if successful
                        else None
                    )
                    reused = True
                else:
                    global_pending = db.execute(
                        "SELECT count(*) FROM jobs WHERE status IN ('queued','parsing','indexing','publishing')"
                    ).fetchone()[0]
                    project_pending = db.execute(
                        "SELECT count(*) FROM jobs WHERE kb=? AND status IN ('queued','parsing','indexing','publishing')",
                        (kb,),
                    ).fetchone()[0]
                    if (
                        global_pending >= self.config.max_jobs
                        or project_pending >= self.config.max_project_jobs
                    ):
                        raise ValueError("knowledge_queue_full")
                    attempt = db.execute(
                        "SELECT coalesce(max(attempt),0)+1 FROM jobs WHERE kb=? AND document_id=? AND signature=?",
                        (kb, doc_id, signature),
                    ).fetchone()[0]
                    if attempt > 3:
                        raise ValueError("knowledge_retry_limit")
                    job_id = "kj_" + uuid4().hex
                    db.execute(
                        "INSERT INTO jobs(id,kb,document_id,signature,identity,status,attempt,created_at,updated_at) VALUES(?,?,?,?,?,'queued',?,?,?)",
                        (
                            job_id,
                            kb,
                            doc_id,
                            signature,
                            identity_json,
                            attempt,
                            stamp,
                            stamp,
                        ),
                    )
                    reused = False
                db.execute(
                    "INSERT INTO requests VALUES(?,?,?,?,?,?,?)",
                    (
                        kb,
                        request_id,
                        identity_json,
                        file_ref["sha256"],
                        file_ref["size_bytes"],
                        job_id,
                        doc_id,
                    ),
                )
        return self.receipt(kb, job_id, doc_id, reused=reused)

    def request_receipt(self, kb, request_id, identity):
        with self.connect() as db:
            request = db.execute(
                "SELECT * FROM requests WHERE kb=? AND request_id=?", (kb, request_id)
            ).fetchone()
            upload = db.execute(
                "SELECT identity,file_ref FROM uploads WHERE kb=? AND request_id=?",
                (kb, request_id),
            ).fetchone()
        for saved in (request, upload):
            if saved is None:
                continue
            file = json.loads(saved["file_ref"]) if saved is upload else saved
            if (
                json.loads(saved["identity"]) != identity
                or file["sha256"] != identity["sha256"]
                or file["size_bytes"] != identity["size_bytes"]
                or (
                    saved is upload
                    and any(
                        file[key] != identity[key] for key in ("file_name", "mime_type")
                    )
                )
            ):
                raise ValueError("knowledge_authorization_denied")
        return (
            self.receipt(kb, request["job_id"], request["document_id"], reused=True)
            if request
            else None
        )

    def get_job(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError("knowledge_not_found")
        return dict(row)

    def document(self, document_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM documents WHERE id=?", (document_id,)
            ).fetchone()
        if not row:
            raise ValueError("knowledge_not_found")
        return dict(row)

    def update_job(
        self, job_id, status, error_code=None, *, target=None, base_revision=None
    ):
        if status not in (*ACTIVE_STATES, "ready", "failed"):
            raise ValueError("invalid_knowledge_job_status")
        with self.connect(write=True) as db:
            db.execute(
                "UPDATE jobs SET status=?,error_code=?,updated_at=?,target=coalesce(?,target),base_revision=coalesce(?,base_revision),started_at=CASE WHEN ?='parsing' THEN coalesce(started_at,?) ELSE started_at END WHERE id=? AND status NOT IN ('ready','failed')",
                (
                    status,
                    error_code,
                    now(),
                    target,
                    base_revision,
                    status,
                    now(),
                    job_id,
                ),
            )

    def next_job(self):
        with self.connect() as db:
            row = db.execute(
                "SELECT jobs.id FROM jobs JOIN projects ON jobs.kb=projects.id WHERE jobs.status='queued' AND projects.enabled=1 ORDER BY jobs.created_at,jobs.id LIMIT 1"
            ).fetchone()
        return row[0] if row else None

    def recover(self):
        with self.connect(write=True) as db:
            db.execute(
                "UPDATE jobs SET status='failed',error_code='knowledge_processing_interrupted',updated_at=? WHERE status IN ('parsing','indexing','publishing')",
                (now(),),
            )
            db.execute("UPDATE usage SET status='unknown' WHERE status='started'")
            db.execute("DELETE FROM upload_reservations")

    def list_jobs(self, kb, limit=20, offset=0):
        self.project(kb)
        with self.connect() as db:
            total = db.execute(
                "SELECT count(*) FROM jobs WHERE kb=?", (kb,)
            ).fetchone()[0]
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM jobs WHERE kb=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                    (kb, limit, offset),
                )
            ]
        return {"items": [self.receipt(kb, job_id) for job_id in ids], "total": total}

    def list_documents(self, kb, limit=20, offset=0):
        with self.connect() as db:
            project = self.project(kb)
            visible = self._visible(db, project)
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM documents WHERE kb=? ORDER BY published_at,id", (kb,)
                )
                if r["id"] in visible
            ]
        return {
            "items": [
                dict(
                    document_id=r["id"],
                    file_name=r["file_name"],
                    mime_type=r["mime_type"],
                    size_bytes=r["size_bytes"],
                    status="ready",
                    searchable=True,
                    published_at=r["published_at"],
                )
                for r in rows[offset : offset + limit]
            ],
            "total": len(rows),
        }
