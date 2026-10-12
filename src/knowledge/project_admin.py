"""Administrator-only registration/migration; legacy snapshots stay untouched."""

from __future__ import annotations

import json
import re
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from src.knowledge.artifacts import checksum, processing_signature, fsync_directory
from src.knowledge.auth import KnowledgeScope
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.generations import (
    copy_storage,
    seal_snapshot,
    storage_dir,
)
from src.knowledge.jobs import now
from src.knowledge.publication import namespace_lock, validate_publication
from src.knowledge.upload_service import MIME_EXT, KnowledgeUploadService


class KnowledgeProjectAdmin:
    def __init__(self, store, generations):
        self.store, self.generations = store, generations

    def register(self, tenant_id, project_id):
        # Reuse the credential UUID rules before persisting ownership.
        KnowledgeScope(
            tenant_id=tenant_id, project_id=project_id, namespace="validation"
        )
        signature = processing_signature(self.store.config)
        project = self.store.register(tenant_id, project_id, signature)
        return {
            "knowledge_base_id": project["id"],
            "processing_signature": signature,
            "upload_enabled": bool(project["enabled"]),
        }

    async def migrate(self, kb, namespace, confirmed_signature):
        project = self.store.project(kb)
        signature = processing_signature(self.store.config)
        if confirmed_signature != signature or project["signature"] != signature:
            raise ValueError("knowledge_processing_config_changed")
        if project["active_namespace"] or project["enabled"]:
            raise ValueError("knowledge_base_changed")
        source = self.generations.engine.get_project_paths(namespace)
        target_namespace = "kg_" + uuid4().hex
        target = self.generations.engine.get_project_paths(target_namespace)
        uploads = KnowledgeUploadService(self.store)
        original_rows = []
        hashes = {}
        # Legacy query caches may write; require the old service to release its lease.
        with namespace_lock(source, write=True), namespace_lock(target, write=True):
            records = validate_publication(source)
            if len({record.document_id for record in records}) != len(records):
                raise ValueError("knowledge_content_conflict")
            for record in records:
                if (
                    not re.fullmatch(r"kd_[a-f0-9]{32}", record.document_id)
                    or record.project_id != namespace
                ):
                    raise ValueError("knowledge_content_conflict")
                file = Path(record.source_uri or "")
                if not file.is_file() or file.is_symlink():
                    raise ValueError("knowledge_migration_original_missing")
                extension = file.suffix.lower().lstrip(".")
                mime = next(
                    (m for m, ext in MIME_EXT.items() if ext == extension), None
                )
                if mime is None:
                    raise ValueError("knowledge_unsupported_format")
                data = file.read_bytes()
                if not 0 < len(data) <= self.store.config.max_file_bytes:
                    raise ValueError("knowledge_file_too_large")
                try:
                    if not data.decode("utf-8").strip() or b"\x00" in data:
                        raise ValueError
                except (ValueError, UnicodeError):
                    raise ValueError("knowledge_invalid_content") from None
                digest = checksum(file)
                if digest in hashes:
                    raise ValueError("knowledge_migration_duplicate_original")
                hashes[digest] = record.document_id
                original_rows.append((record, file, digest, len(data), mime))
            if (
                len(records) > self.store.config.max_project_documents
                or sum(row[3] for row in original_rows)
                > self.store.config.max_project_original_bytes
            ):
                raise ValueError("knowledge_quota_exceeded")
            uploads.check_disk(
                kb,
                sum(p.stat().st_size for p in storage_dir(source).iterdir()) * 2
                + sum(row[3] for row in original_rows),
            )
            copy_storage(storage_dir(source), storage_dir(target))
            registry = KnowledgeDocumentRegistry(target)
            originals = []
            for record, file, digest, size, mime in original_rows:
                original = uploads.directory(kb, "originals") / digest
                if original.is_symlink():
                    raise ValueError("knowledge_path_escape")
                if not original.exists():
                    # Atomic file replacement with directory durability, no new model requests.
                    with tempfile.NamedTemporaryFile(
                        dir=original.parent, delete=False
                    ) as handle:
                        temp = Path(handle.name)
                        try:
                            handle.write(file.read_bytes())
                            handle.flush()
                            os.fsync(handle.fileno())
                            os.replace(temp, original)
                            fsync_directory(original.parent)
                        finally:
                            if temp.exists():
                                temp.unlink()
                if checksum(original) != digest or original.stat().st_size != size:
                    raise ValueError("knowledge_content_conflict")
                registry.register_document(
                    record.model_copy(
                        update={
                            "project_id": target_namespace,
                            "source_uri": str(original),
                        }
                    )
                )
                originals.append(
                    (
                        record.document_id,
                        kb,
                        digest,
                        size,
                        record.filename,
                        mime,
                        str(original),
                        signature,
                        now(),
                    )
                )
            seal_snapshot(target, signature)
        prepared = await self.generations.prepare(target_namespace, signature, pin=True)
        try:
            with self.store.connect(write=True) as db:
                current = db.execute(
                    "SELECT * FROM projects WHERE id=?", (kb,)
                ).fetchone()
                if current["active_namespace"] or current["enabled"]:
                    raise ValueError("knowledge_base_changed")
                if db.execute("SELECT 1 FROM documents WHERE kb=?", (kb,)).fetchone():
                    raise ValueError("knowledge_content_conflict")
                db.executemany(
                    "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?)", originals
                )
                db.execute(
                    "INSERT INTO generations VALUES(?,?,?,?,?,?)",
                    (
                        target_namespace,
                        kb,
                        signature,
                        current["revision"],
                        json.dumps([r.document_id for r in records]),
                        now(),
                    ),
                )
                db.execute(
                    "UPDATE projects SET active_namespace=?,revision=revision+1 WHERE id=?",
                    (target_namespace, kb),
                )
        finally:
            async with self.generations._lock:
                prepared["leases"] -= 1
            await self.generations.reap()
        return {
            "status": "migrated",
            "knowledge_base_id": kb,
            "namespace": target_namespace,
            "document_count": len(records),
            "model_requests": 0,
            "upload_enabled": False,
        }
