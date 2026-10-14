"""Freeze complete native storage; build and read through independent workspaces."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from src.knowledge.artifacts import (
    KnowledgeArtifactStore,
    KnowledgeUsageRecorder,
    atomic_json,
    checksum,
    compatible_processing_signature,
    fsync_directory,
)
from src.knowledge.auth import KnowledgeScope
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.jobs import now
from src.knowledge.operation_auth import KnowledgeOperationAuthorizer
from src.knowledge.publication import (
    model_signature,
    namespace_lock,
    validate_publication,
)
from src.knowledge.rag_engine import ProjectRAGEngine, storage_io, storage_workspace
from src.knowledge.schemas import KnowledgeDocumentRecord

STORES = (
    "full_docs",
    "text_chunks",
    "full_entities",
    "full_relations",
    "entity_chunks",
    "relation_chunks",
    "entities_vdb",
    "relationships_vdb",
    "chunks_vdb",
    "chunk_entity_relation_graph",
    "llm_response_cache",
    "doc_status",
)
STORAGE_FILES = frozenset(
    [
        *(
            f"kv_store_{name}.json"
            for name in (
                "full_docs",
                "text_chunks",
                "full_entities",
                "full_relations",
                "entity_chunks",
                "relation_chunks",
                "llm_response_cache",
                "doc_status",
            )
        ),
        "vdb_entities.json",
        "vdb_relationships.json",
        "vdb_chunks.json",
        "graph_chunk_entity_relation.graphml",
    ]
)


def release_workspace(workspace):
    # LightRAG 1.4.12 finalize leaves global KV/locks alive; only release our unleased workspace.
    from lightrag.kg import shared_storage as shared

    if version("lightrag-hku") != "1.4.12" or shared._is_multiprocess:
        raise ValueError("knowledge_storage_version_unsupported")
    prefix = workspace + ":"
    keyed = shared._storage_keyed_lock
    if keyed:
        for key, count in keyed._async_lock_count.items():
            if key.startswith(prefix) and count:
                raise ValueError("knowledge_namespace_in_use")
        for mapping in (
            keyed._async_lock,
            keyed._async_lock_count,
            keyed._async_lock_cleanup_data,
        ):
            for key in list(mapping):
                if key.startswith(prefix):
                    del mapping[key]
    for mapping in (shared._shared_dicts, shared._init_flags, shared._update_flags):
        if mapping is not None:
            for key in list(mapping):
                if key.startswith(prefix):
                    del mapping[key]
    if shared._default_workspace == workspace:
        shared.set_default_workspace(None)


def storage_dir(paths):
    return paths.rag_workdir / storage_workspace(paths)


def validate_snapshot(paths, signature):
    records = validate_publication(paths)
    marker = paths.manifest_dir / "snapshot.json"
    try:
        data = json.loads(marker.read_text())
        files = data["files"]
        if (
            data["version"] != 1
            or data["signature"] != signature
            or set(files) != STORAGE_FILES
            or set(data["documents"]) != {r.document_id for r in records}
        ):
            raise ValueError
        directory = storage_dir(paths)
        for name, digest in files.items():
            file = directory / name
            if file.is_symlink() or not file.is_file() or checksum(file) != digest:
                raise ValueError
        status = json.loads((directory / "kv_store_doc_status.json").read_text())
        docs = json.loads((directory / "kv_store_full_docs.json").read_text())
        if (
            set(status) != set(data["documents"])
            or set(docs) != set(status)
            or any(r.get("status") != "processed" for r in status.values())
        ):
            raise ValueError
        chunks = json.loads((directory / "kv_store_text_chunks.json").read_text())
        for doc_id, record in status.items():
            chunk_ids = record.get("chunks_list", [])
            if not chunk_ids or any(
                key not in chunks
                or chunks[key].get("full_doc_id") != doc_id
                or chunks[key].get("file_path") != doc_id
                for key in chunk_ids
            ):
                raise ValueError
        import networkx as nx
        import numpy as np
        from nano_vectordb.dbs import load_storage

        from src.demo_support import load_settings

        for name in ("vdb_chunks.json", "vdb_entities.json", "vdb_relationships.json"):
            vectors = load_storage(directory / name)
            if (
                vectors["embedding_dim"] != load_settings().embedding_dim
                or len(vectors["data"]) != len(vectors["matrix"])
                or not np.isfinite(vectors["matrix"]).all()
            ):
                raise ValueError
            if name == "vdb_chunks.json" and {
                r["__id__"] for r in vectors["data"]
            } != set(chunks):
                raise ValueError
        nx.read_graphml(directory / "graph_chunk_entity_relation.graphml")
        return records
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("knowledge_snapshot_invalid") from None


def copy_storage(source, target):
    if target.exists():
        raise ValueError("knowledge_snapshot_invalid")
    target.mkdir(parents=True)
    for name in STORAGE_FILES:
        file = source / name
        if file.is_symlink() or not file.is_file():
            raise ValueError("knowledge_snapshot_invalid")
        shutil.copyfile(file, target / name)
        with (target / name).open("rb") as handle:
            os.fsync(handle.fileno())
        if checksum(file) != checksum(target / name):
            raise ValueError("knowledge_snapshot_invalid")
    fsync_directory(target)


async def flush_storages(rag):
    await asyncio.gather(*(getattr(rag, name).index_done_callback() for name in STORES))
    # Empty optional graph KV stores may never be written by LightRAG.
    for name in (
        "full_entities",
        "full_relations",
        "entity_chunks",
        "relation_chunks",
        "llm_response_cache",
    ):
        storage = getattr(rag, name)
        path = Path(storage._file_name)
        if not path.exists() and await storage.is_empty():
            atomic_json(path, {})


def seal_snapshot(paths, signature):
    records = KnowledgeDocumentRegistry(paths).list_documents(limit=10000)
    directory = storage_dir(paths)
    files = {}
    for name in STORAGE_FILES:
        file = directory / name
        if file.is_symlink() or not file.is_file():
            raise ValueError("knowledge_snapshot_invalid")
        with file.open("rb") as handle:
            os.fsync(handle.fileno())
        files[name] = checksum(file)
    fsync_directory(directory)
    atomic_json(paths.manifest_dir / "publication.json", model_signature())
    atomic_json(
        paths.manifest_dir / "snapshot.json",
        {
            "version": 1,
            "signature": signature,
            "files": files,
            "documents": [r.document_id for r in records],
        },
    )
    validate_snapshot(paths, signature)


class KnowledgeGenerationService:
    def __init__(self, store, engine=None, authorizer=None):
        self.store, self.config = store, store.config
        self.engine = engine or ProjectRAGEngine(self.config)
        self.authorizer = authorizer or KnowledgeOperationAuthorizer(self.config)
        self._readers = {}
        self._lock = asyncio.Lock()
        self._prepare_lock = asyncio.Lock()

    def scope(self, kb):
        project = self.store.project(kb)
        return KnowledgeScope(
            tenant_id=project["tenant_id"],
            project_id=project["project_id"],
            knowledge_base_id=kb,
        )

    async def build(self, job_id):
        job = self.store.get_job(job_id)
        project = self.store.project(job["kb"])
        signature = compatible_processing_signature(self.config, project["signature"])
        if signature != job["signature"] or signature != project["signature"]:
            raise ValueError("knowledge_processing_config_changed")
        if not project["enabled"]:
            raise ValueError("knowledge_upload_disabled")
        namespace = "kg_" + uuid4().hex
        paths = self.engine.get_project_paths(namespace)
        doc = self.store.document(job["document_id"])
        self.store.update_job(
            job_id, "parsing", target=namespace, base_revision=project["revision"]
        )
        usage = KnowledgeUsageRecorder(self.store, job_id)
        builder = ProjectRAGEngine(self.config, usage=usage)
        from src.knowledge.upload_service import KnowledgeUploadService

        uploads = KnowledgeUploadService(self.store)
        with namespace_lock(paths, write=True):
            old_records = []
            if project["active_namespace"]:
                source = self.engine.get_project_paths(project["active_namespace"])
                with namespace_lock(source):
                    old_records = validate_snapshot(source, signature)
                    self.validate_document_artifacts(old_records, signature)
                    uploads.check_disk(
                        job["kb"],
                        uploads.disk_usage(source.project_dir) * 2 + doc["size_bytes"],
                    )
                    copy_storage(storage_dir(source), storage_dir(paths))
            else:
                uploads.check_disk(job["kb"], doc["size_bytes"] * 2)
            registry = KnowledgeDocumentRegistry(paths)
            for record in old_records:
                if record.source_type == "managed_upload":
                    try:
                        self.store.document(record.document_id)
                    except ValueError as e:
                        if str(e) == "knowledge_not_found":
                            continue
                        raise
                registry.register_document(
                    record.model_copy(update={"project_id": namespace})
                )
            original = Path(doc["original"])
            managed = (
                self.config.root_dir.expanduser().resolve()
                / "managed"
                / job["kb"]
                / "originals"
            )
            if (
                original.is_symlink()
                or not original.resolve().is_relative_to(managed)
                or original.stat().st_size != doc["size_bytes"]
                or checksum(original) != doc["sha256"]
            ):
                raise ValueError("knowledge_content_conflict")
            artifacts = KnowledgeArtifactStore(self.store)
            try:
                rag = await builder.get_lightrag(namespace)
                usage.instrument(rag)
                parsed = artifacts.load(doc, signature)
                if parsed is None:
                    usage.stage = "parsing"
                    usage.event("parse")
                    from src.knowledge.document_formats import (
                        MIME_EXT,
                        TEXT_MIME,
                        supported_mime_types,
                        validate_original,
                    )

                    if doc["mime_type"] not in supported_mime_types(self.config):
                        raise ValueError("knowledge_unsupported_format")
                    validate_original(
                        original, doc["mime_type"], self.config.max_file_bytes
                    )
                    if doc["mime_type"] in TEXT_MIME:
                        parsed = artifacts.save_text(
                            doc, signature, original.read_text(encoding="utf-8").strip()
                        )
                    else:
                        from src.knowledge.content_normalizer import (
                            normalize_content_list,
                        )
                        from src.knowledge.parser_adapter import DoclingParserAdapter

                        # Originals retain content-addressed names; parser dispatch needs a trusted suffix.
                        with tempfile.TemporaryDirectory(
                            prefix="document-", dir=paths.parser_dir
                        ) as temporary:
                            input_path = Path(temporary) / (
                                "original." + MIME_EXT[doc["mime_type"]]
                            )
                            shutil.copyfile(original, input_path)
                            if doc["mime_type"].startswith("image/"):
                                blocks = [
                                    {"type": "image", "img_path": str(input_path)}
                                ]
                                metadata = {}
                                parser_name = "image"
                                trusted = Path(temporary)
                            else:
                                multimodal = await builder.get_rag(namespace)
                                result = await DoclingParserAdapter(
                                    rag=multimodal,
                                    parser_name=self.config.parser_name,
                                ).parse_file(input_path)
                                blocks, metadata = result.content_list, result.metadata
                                parser_name = self.config.parser_name
                                trusted = paths.parser_dir
                            blocks = normalize_content_list(
                                blocks,
                                document_id=doc["id"],
                                filename=doc["file_name"],
                            )
                            parsed = artifacts.save_document(
                                doc,
                                signature,
                                blocks,
                                parser_name=parser_name,
                                trusted_dir=trusted,
                                metadata=metadata,
                            )
                else:
                    usage.event("parse_cache_hit")
                self.store.update_job(job_id, "indexing")
                usage.stage = "indexing"
                if parsed["kind"] == "text":
                    await builder.ingest_text(
                        namespace, doc["id"], parsed["text"], document_chunks=True
                    )
                    parser_name = "utf8"
                else:
                    await builder.ingest_content_list(
                        project_id=namespace,
                        document_id=doc["id"],
                        content_list=parsed["content_list"],
                    )
                    parser_name = parsed["parser_name"]
                indexed = await rag.doc_status.get_by_id(doc["id"])
                registry.register_document(
                    KnowledgeDocumentRecord(
                        document_id=doc["id"],
                        project_id=namespace,
                        filename=doc["file_name"],
                        source_type="managed_upload",
                        source_uri=str(original),
                        parser_name=parser_name,
                        parse_status="parsed",
                        index_status="ready",
                        overall_status="ready",
                        chunk_count=len(set(indexed.get("chunks_list") or [])),
                    )
                )
                for record in registry.list_documents(limit=10000):
                    await builder.assert_document_ready(namespace, record.document_id)
                await flush_storages(rag)
                uploads.check_disk(job["kb"], uploads.disk_usage(paths.project_dir))
            finally:
                await builder.close()
                release_workspace(storage_workspace(paths))
            seal_snapshot(paths, signature)
        self.store.update_job(job_id, "publishing")
        return namespace

    def validate_document_artifacts(self, records, signature):
        from src.knowledge.document_formats import DOCUMENT_MIME

        artifacts = KnowledgeArtifactStore(self.store)
        for record in records:
            if record.source_type != "managed_upload":
                continue
            try:
                doc = self.store.document(record.document_id)
            except ValueError as e:
                if str(e) == "knowledge_not_found":
                    continue
                raise
            if (
                doc["mime_type"] in DOCUMENT_MIME
                and artifacts.load(doc, signature) is None
            ):
                raise ValueError("knowledge_artifact_invalid")

    async def prepare(self, namespace, signature, *, pin=False):
        async with self._lock:
            if namespace in self._readers:
                if pin:
                    self._readers[namespace]["leases"] += 1
                return self._readers[namespace]
        async with self._prepare_lock:
            async with self._lock:
                if namespace in self._readers:
                    if pin:
                        self._readers[namespace]["leases"] += 1
                    return self._readers[namespace]
            source = self.engine.get_project_paths(namespace)
            with self.store.connect() as db:
                generation = db.execute(
                    "SELECT kb FROM generations WHERE namespace=?", (namespace,)
                ).fetchone()
                if generation is None:
                    generation = db.execute(
                        "SELECT kb FROM jobs WHERE target=?", (namespace,)
                    ).fetchone()
            kb = generation[0] if generation else "migration"
            reader_root = (
                self.config.root_dir.expanduser().resolve() / "control" / "readers" / kb
            )
            reader_root.mkdir(parents=True, exist_ok=True)
            temp = tempfile.TemporaryDirectory(prefix="reader-", dir=reader_root)
            reader = ProjectRAGEngine(replace(self.config, root_dir=Path(temp.name)))
            paths = reader.get_project_paths(namespace)

            def restore_reader():
                with namespace_lock(source):
                    records = validate_snapshot(source, signature)
                    self.validate_document_artifacts(records, signature)
                    copy_storage(storage_dir(source), storage_dir(paths))
                    paths.manifest_dir.mkdir(parents=True)
                    for name in ("documents.json", "publication.json", "snapshot.json"):
                        shutil.copyfile(
                            source.manifest_dir / name, paths.manifest_dir / name
                        )
                validate_snapshot(paths, signature)

            try:
                await storage_io(restore_reader)
                lock = namespace_lock(paths)
                lock.__enter__()
                try:
                    await reader.get_lightrag(namespace)
                except BaseException:
                    lock.__exit__(None, None, None)
                    raise
                entry = {
                    "engine": reader,
                    "temp": temp,
                    "lock": lock,
                    "leases": int(pin),
                }
                async with self._lock:
                    self._readers[namespace] = entry
                return entry
            except BaseException:
                await reader.close()
                release_workspace(storage_workspace(paths))
                temp.cleanup()
                raise

    async def activate(self, job_id):
        job = self.store.get_job(job_id)
        project = self.store.project(job["kb"])
        signature = compatible_processing_signature(self.config, project["signature"])
        namespace = job["target"]
        if (
            job["status"] != "publishing"
            or not namespace
            or not project["enabled"]
            or signature != job["signature"]
            or signature != project["signature"]
        ):
            raise ValueError("knowledge_processing_config_changed")
        prepared = await self.prepare(namespace, signature, pin=True)
        try:
            records = await asyncio.to_thread(
                validate_snapshot, self.engine.get_project_paths(namespace), signature
            )
            self.validate_document_artifacts(records, signature)
            grant = await self.authorizer.authorize(
                self.scope(job["kb"]),
                "activate",
                json.loads(job["identity"]),
                {
                    "job_id": job_id,
                    "target_revision": namespace,
                    "base_revision": job["base_revision"],
                },
            )
            with self.store.connect(write=True) as db:
                self.authorizer.verify(
                    grant,
                    self.scope(job["kb"]),
                    "activate",
                    {
                        **json.loads(job["identity"]),
                        "job_id": job_id,
                        "target_revision": namespace,
                        "base_revision": job["base_revision"],
                    },
                )
                current = db.execute(
                    "SELECT * FROM projects WHERE id=?", (job["kb"],)
                ).fetchone()
                current_job = db.execute(
                    "SELECT * FROM jobs WHERE id=?", (job_id,)
                ).fetchone()
                if (
                    not current["enabled"]
                    or current["revision"] != job["base_revision"]
                    or current["signature"] != signature
                    or current_job["status"] != "publishing"
                ):
                    raise ValueError("knowledge_base_changed")
                ids = {r.document_id for r in records}
                if ids != self.store._visible(db, current) | {job["document_id"]}:
                    raise ValueError("knowledge_snapshot_invalid")
                stamp = now()
                db.execute(
                    "INSERT INTO generations VALUES(?,?,?,?,?,?)",
                    (
                        namespace,
                        job["kb"],
                        signature,
                        job["base_revision"],
                        json.dumps(sorted(ids)),
                        stamp,
                    ),
                )
                db.execute(
                    "UPDATE projects SET active_namespace=?,revision=revision+1 WHERE id=?",
                    (namespace, job["kb"]),
                )
                db.execute(
                    "UPDATE jobs SET status='ready',updated_at=? WHERE id=?",
                    (stamp, job_id),
                )
                db.execute(
                    "UPDATE documents SET published_at=coalesce(published_at,?) WHERE id=?",
                    (stamp, job["document_id"]),
                )
        finally:
            async with self._lock:
                prepared["leases"] -= 1
            await self.reap()
        return self.store.receipt(job["kb"], job_id)

    @asynccontextmanager
    async def acquire(self, kb):
        project = self.store.project(kb)
        namespace = project["active_namespace"]
        if namespace is None:
            yield None, None
            return
        compatible_processing_signature(self.config, project["signature"])
        entry = await self.prepare(namespace, project["signature"], pin=True)
        try:
            yield entry["engine"], namespace
        finally:
            async with self._lock:
                entry["leases"] -= 1
            await self.reap()

    async def reap(self, *, all_readers=False):
        async with self._lock:
            with self.store.connect() as db:
                active = {
                    r[0]
                    for r in db.execute(
                        "SELECT active_namespace FROM projects WHERE active_namespace IS NOT NULL"
                    )
                }
            for namespace, entry in list(self._readers.items()):
                if not entry["leases"] and (all_readers or namespace not in active):
                    try:
                        await entry["engine"].close()
                    finally:
                        release_workspace(
                            storage_workspace(
                                entry["engine"].get_project_paths(namespace)
                            )
                        )
                        entry["lock"].__exit__(None, None, None)
                        entry["temp"].cleanup()
                        del self._readers[namespace]

    async def rollback(self, kb, namespace):
        project = self.store.project(kb)
        signature = compatible_processing_signature(self.config, project["signature"])
        if signature != project["signature"]:
            raise ValueError("knowledge_processing_config_changed")
        with self.store.connect() as db:
            generation = db.execute(
                "SELECT * FROM generations WHERE namespace=? AND kb=?", (namespace, kb)
            ).fetchone()
            running = db.execute(
                "SELECT 1 FROM jobs WHERE kb=? AND status IN ('parsing','indexing','publishing')",
                (kb,),
            ).fetchone()
        if project["enabled"] or running:
            raise ValueError("knowledge_rollback_upload_disabled")
        if generation is None or generation["signature"] != signature:
            raise ValueError("knowledge_not_found")
        records = validate_snapshot(self.engine.get_project_paths(namespace), signature)
        self.validate_document_artifacts(records, signature)
        prepared = await self.prepare(namespace, signature, pin=True)
        try:
            with self.store.connect(write=True) as db:
                if db.execute(
                    "SELECT enabled FROM projects WHERE id=?", (kb,)
                ).fetchone()[0]:
                    raise ValueError("knowledge_rollback_upload_disabled")
                db.execute(
                    "UPDATE projects SET active_namespace=?,revision=revision+1 WHERE id=?",
                    (namespace, kb),
                )
        finally:
            async with self._lock:
                prepared["leases"] -= 1
            await self.reap()

    async def close(self):
        await self.reap(all_readers=True)
