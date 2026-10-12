"""Original bytes are durable before a ticket or queued receipt is returned."""

from __future__ import annotations

import hashlib
import asyncio
import json
import os
import re
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from src.knowledge.artifacts import checksum, fsync_directory, processing_signature
from src.knowledge.operation_auth import (
    KnowledgeOperationAuthorizer,
    operation_identity,
)

MIME_EXT = {"text/plain": "txt", "text/markdown": "md"}
SAFE_ERRORS = {
    "knowledge_not_found",
    "knowledge_upload_disabled",
    "knowledge_authorization_denied",
    "knowledge_authorization_unavailable",
    "knowledge_content_conflict",
    "knowledge_processing_config_changed",
    "knowledge_queue_full",
    "knowledge_retry_limit",
    "knowledge_quota_exceeded",
    "knowledge_file_too_large",
    "knowledge_unsupported_format",
    "invalid_file_ref",
    "knowledge_upload_expired",
    "knowledge_invalid_content",
    "knowledge_processing_timeout",
    "knowledge_processing_interrupted",
    "knowledge_processing_failed",
    "knowledge_base_changed",
    "knowledge_snapshot_invalid",
    "knowledge_path_escape",
    "knowledge_rollback_upload_disabled",
    "knowledge_migration_original_missing",
    "knowledge_migration_duplicate_original",
    "knowledge_upload_in_progress",
}


def safe_error(exc):
    return str(exc) if str(exc) in SAFE_ERRORS else "knowledge_processing_failed"


def validate_file_ref(value, max_bytes=20 * 1024**2):
    if not isinstance(value, dict) or set(value) != {
        "version",
        "path",
        "file_name",
        "mime_type",
        "size_bytes",
        "sha256",
    }:
        raise ValueError("invalid_file_ref")
    name, mime, digest = value["file_name"], value["mime_type"], value["sha256"]
    if (
        type(value["version"]) is not int
        or value["version"] != 1
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] <= 0
        or not isinstance(name, str)
        or not 0 < len(name) <= 200
        or any(ord(ch) < 32 or ch in "/\\\x7f" for ch in name)
        or not isinstance(digest, str)
        or not re.fullmatch("[a-f0-9]{64}", digest)
    ):
        raise ValueError("invalid_file_ref")
    if value["size_bytes"] > max_bytes:
        raise ValueError("knowledge_file_too_large")
    if mime not in MIME_EXT:
        raise ValueError("knowledge_unsupported_format")
    ext = MIME_EXT[mime]
    if (
        value["path"] != f"/workspace/uploads/{digest}.{ext}"
        or Path(name).suffix.lower() != "." + ext
    ):
        raise ValueError("invalid_file_ref")
    return value


class KnowledgeUploadService:
    def __init__(self, store, authorizer=None):
        self.store, self.config = store, store.config
        self.authorizer = authorizer or KnowledgeOperationAuthorizer(self.config)

    def scope_project(self, scope):
        if scope.knowledge_base_id is None:
            raise ValueError("knowledge_upload_disabled")
        project = self.store.project(scope.knowledge_base_id)
        if (project["tenant_id"], project["project_id"]) != (
            scope.tenant_id,
            scope.project_id,
        ):
            raise ValueError("knowledge_not_found")
        return project

    def capabilities(self, scope):
        project = self.scope_project(scope)
        signature_ok = project["signature"] == processing_signature(self.config)
        enabled = bool(
            self.config.online_enabled
            and self.authorizer.configured
            and project["enabled"]
            and signature_ok
        )
        reason = (
            None
            if enabled
            else "knowledge_processing_config_changed"
            if not signature_ok
            else "knowledge_upload_disabled"
        )
        return dict(
            version=1,
            read=True,
            upload_enabled=enabled,
            supported_mime_types=list(MIME_EXT),
            max_file_bytes=self.config.max_file_bytes,
            disabled_reason=reason,
        )

    def directory(self, kb, name):
        if name not in {"originals", "tmp"}:
            raise ValueError("knowledge_path_escape")
        root = self.config.root_dir.expanduser().resolve()
        target = root / "managed" / kb / name
        if not target.resolve().is_relative_to(root) or any(
            p.is_symlink() for p in (root / "managed", target.parent, target)
        ):
            raise ValueError("knowledge_path_escape")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def disk_usage(self, path):
        total = 0
        if path.exists():
            for file in path.rglob("*"):
                if file.is_symlink():
                    raise ValueError("knowledge_path_escape")
                if file.is_file():
                    total += file.stat().st_size
        return total

    def check_disk(self, kb, reserve=0):
        root = self.config.root_dir.expanduser().resolve()
        with self.store.connect() as db:
            namespaces = {
                r[0]
                for r in db.execute(
                    "SELECT namespace FROM generations WHERE kb=? UNION SELECT target FROM jobs WHERE kb=? AND target IS NOT NULL",
                    (kb, kb),
                )
            }
            global_reserved = db.execute(
                "SELECT coalesce(sum(size_bytes),0) FROM upload_reservations"
            ).fetchone()[0]
            project_reserved = db.execute(
                "SELECT coalesce(sum(size_bytes),0) FROM upload_reservations WHERE kb=?",
                (kb,),
            ).fetchone()[0]
        project_bytes = self.disk_usage(root / "managed" / kb) + sum(
            self.disk_usage(root / namespace) for namespace in namespaces
        )
        project_bytes += self.disk_usage(root / "control" / "readers" / kb)
        if (
            self.disk_usage(root) + global_reserved + reserve
            > self.config.max_disk_bytes
            or project_bytes + project_reserved + reserve
            > self.config.max_project_disk_bytes
        ):
            raise ValueError("knowledge_quota_exceeded")

    def reserve_upload(self, kb, request_id, ref):
        with self.store.connect(write=True) as db:
            if db.execute(
                "SELECT 1 FROM upload_reservations WHERE kb=? AND request_id=?",
                (kb, request_id),
            ).fetchone():
                raise ValueError("knowledge_upload_in_progress")
            rows = list(
                db.execute("SELECT sha256,size_bytes FROM documents WHERE kb=?", (kb,))
            )
            originals = {r[0]: r[1] for r in rows}
            for row in db.execute("SELECT file_ref FROM uploads WHERE kb=?", (kb,)):
                old = json.loads(row[0])
                originals[old["sha256"]] = old["size_bytes"]
            reserved_count, reserved_size = db.execute(
                "SELECT count(*),coalesce(sum(size_bytes),0) FROM upload_reservations WHERE kb=?",
                (kb,),
            ).fetchone()
            if ref["sha256"] not in originals and (
                len(originals) + reserved_count >= self.config.max_project_documents
                or sum(originals.values()) + reserved_size + ref["size_bytes"]
                > self.config.max_project_original_bytes
            ):
                raise ValueError("knowledge_quota_exceeded")
            db.execute(
                "INSERT INTO upload_reservations VALUES(?,?,?,?)",
                (kb, request_id, ref["size_bytes"], time.time()),
            )
            self.check_disk(kb, ref["size_bytes"] * 2)

    def cleanup_uploads(self):
        cutoff = time.time() - 86400
        with self.store.connect(write=True) as db:
            db.execute(
                "DELETE FROM uploads WHERE consumed=0 AND expires_at<?", (cutoff,)
            )
            projects = [r[0] for r in db.execute("SELECT id FROM projects")]
            used = {
                r[0]
                for r in db.execute(
                    "SELECT original FROM documents UNION SELECT original FROM uploads"
                )
            }
        for kb in projects:
            for file in self.directory(kb, "tmp").glob("upload-*"):
                if (
                    not file.is_symlink()
                    and file.is_file()
                    and file.stat().st_mtime < cutoff
                ):
                    file.unlink()
            for file in self.directory(kb, "originals").iterdir():
                if (
                    re.fullmatch(r"[a-f0-9]{64}", file.name)
                    and str(file) not in used
                    and not file.is_symlink()
                    and file.is_file()
                    and file.stat().st_mtime < cutoff
                ):
                    file.unlink()

    async def stage_upload(self, scope, request_id, file_ref, grant, chunks):
        ref = validate_file_ref(file_ref, self.config.max_file_bytes)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id):
            raise ValueError("invalid_file_ref")
        project = self.scope_project(scope)
        if not self.capabilities(scope)["upload_enabled"]:
            raise ValueError("knowledge_upload_disabled")
        values = self.authorizer.verify(
            grant,
            scope,
            "upload",
            {
                "request_id": request_id,
                "sha256": ref["sha256"],
                "size_bytes": ref["size_bytes"],
                "file_name": ref["file_name"],
                "mime_type": ref["mime_type"],
            },
        )
        identity = operation_identity(values)
        kb = project["id"]
        with self.store.connect() as db:
            old = db.execute(
                "SELECT * FROM uploads WHERE kb=? AND request_id=?", (kb, request_id)
            ).fetchone()
        if old:
            if (
                json.loads(old["identity"]) != identity
                or json.loads(old["file_ref"]) != ref
            ):
                raise ValueError("knowledge_content_conflict")
            if old["expires_at"] <= time.time() and not old["consumed"]:
                raise ValueError("knowledge_upload_expired")
            return {"upload_id": old["id"]}
        temp_dir = self.directory(kb, "tmp")
        original = self.directory(kb, "originals") / ref["sha256"]
        digest, size = hashlib.sha256(), 0
        with tempfile.NamedTemporaryFile(
            dir=temp_dir, prefix="upload-", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            reserved = False
            try:
                await asyncio.to_thread(self.reserve_upload, kb, request_id, ref)
                reserved = True
                async for chunk in chunks:
                    size += len(chunk)
                    if size > self.config.max_file_bytes:
                        raise ValueError("knowledge_file_too_large")
                    if size > ref["size_bytes"]:
                        raise ValueError("knowledge_content_conflict")
                    digest.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
                if size != ref["size_bytes"] or digest.hexdigest() != ref["sha256"]:
                    raise ValueError("knowledge_content_conflict")
                handle.flush()
                await asyncio.to_thread(os.fsync, handle.fileno())
                try:
                    text = await asyncio.to_thread(
                        temp_path.read_text, encoding="utf-8"
                    )
                    if not text.strip() or "\x00" in text:
                        raise ValueError
                except (ValueError, UnicodeError):
                    raise ValueError("knowledge_invalid_content") from None
                with self.store.connect(write=True) as db:
                    if original.is_symlink():
                        raise ValueError("knowledge_path_escape")
                    if original.exists():
                        if (
                            original.stat().st_size != size
                            or checksum(original) != ref["sha256"]
                        ):
                            raise ValueError("knowledge_content_conflict")
                    else:
                        os.replace(temp_path, original)
                        fsync_directory(original.parent)
                    ticket = db.execute(
                        "SELECT * FROM uploads WHERE kb=? AND request_id=?",
                        (kb, request_id),
                    ).fetchone()
                    if ticket:
                        if (
                            json.loads(ticket["identity"]) != identity
                            or json.loads(ticket["file_ref"]) != ref
                        ):
                            raise ValueError("knowledge_content_conflict")
                        upload_id = ticket["id"]
                    else:
                        upload_id = "ku_" + uuid4().hex
                        db.execute(
                            "INSERT INTO uploads(id,kb,request_id,identity,file_ref,original,expires_at) VALUES(?,?,?,?,?,?,?)",
                            (
                                upload_id,
                                kb,
                                request_id,
                                json.dumps(identity, sort_keys=True),
                                json.dumps(ref),
                                str(original),
                                time.time() + 300,
                            ),
                        )
                return {"upload_id": upload_id}
            finally:
                if temp_path.exists():
                    temp_path.unlink()
                if reserved:
                    with self.store.connect(write=True) as db:
                        db.execute(
                            "DELETE FROM upload_reservations WHERE kb=? AND request_id=?",
                            (kb, request_id),
                        )

    def submit_document(self, scope, upload_id, file_ref, grant):
        ref = validate_file_ref(file_ref, self.config.max_file_bytes)
        self.scope_project(scope)
        if not self.config.online_enabled:
            raise ValueError("knowledge_upload_disabled")
        with self.store.connect() as db:
            ticket = db.execute(
                "SELECT * FROM uploads WHERE id=? AND kb=?",
                (upload_id, scope.knowledge_base_id),
            ).fetchone()
            accepted = db.execute(
                "SELECT 1 FROM requests WHERE kb=? AND request_id=(SELECT request_id FROM uploads WHERE id=?)",
                (scope.knowledge_base_id, upload_id),
            ).fetchone()
        if not ticket:
            raise ValueError("knowledge_not_found")
        identity = json.loads(ticket["identity"])
        self.authorizer.verify(
            grant,
            scope,
            "upload",
            {
                **identity,
                "sha256": ref["sha256"],
                "size_bytes": ref["size_bytes"],
                "file_name": ref["file_name"],
                "mime_type": ref["mime_type"],
            },
        )
        if json.loads(ticket["file_ref"]) != ref:
            raise ValueError("knowledge_content_conflict")
        if (
            ticket["expires_at"] <= time.time()
            and not ticket["consumed"]
            and not accepted
        ):
            raise ValueError("knowledge_upload_expired")
        original = Path(ticket["original"])
        if (
            original.is_symlink()
            or not original.resolve().is_relative_to(
                self.directory(scope.knowledge_base_id, "originals")
            )
            or original.stat().st_size != ref["size_bytes"]
            or checksum(original) != ref["sha256"]
        ):
            raise ValueError("knowledge_content_conflict")
        receipt = self.store.submit(
            scope.knowledge_base_id,
            ticket["request_id"],
            identity,
            ref,
            str(original),
            processing_signature(self.config),
        )
        with self.store.connect(write=True) as db:
            db.execute("UPDATE uploads SET consumed=1 WHERE id=?", (upload_id,))
        return receipt

    def lookup_request(self, scope, request_id, grant):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id):
            raise ValueError("invalid_file_ref")
        self.scope_project(scope)
        values = self.authorizer.verify(
            grant, scope, "upload", {"request_id": request_id}
        )
        return {
            "request_id": request_id,
            "receipt": self.store.request_receipt(
                scope.knowledge_base_id, request_id, operation_identity(values)
            ),
        }
