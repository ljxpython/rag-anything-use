"""Checksummed complete parse results and safe per-attempt model usage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import MISSING, fields
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from lightrag import LightRAG
from lightrag.prompt import PROMPTS

from src.demo_support import load_settings
from src.knowledge.operation_auth import canonical


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        try:
            json.dump(value, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(handle.name, path)
            fsync_directory(path.parent)
        finally:
            if Path(handle.name).exists():
                Path(handle.name).unlink()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def processing_signature(config):
    settings = load_settings()
    defaults = {}
    # Capture effective defaults, including environment-derived graph/chunk parameters.
    for field in fields(LightRAG):
        if field.name in {
            "chunk_token_size",
            "chunk_overlap_token_size",
            "tiktoken_model_name",
            "entity_extract_max_gleaning",
            "force_llm_summary_on_merge",
            "summary_max_tokens",
            "summary_context_size",
            "summary_length_recommended",
            "addon_params",
            "max_source_ids_per_entity",
            "max_source_ids_per_relation",
            "source_ids_limit_method",
            "max_file_paths",
            "file_path_more_placeholder",
        }:
            defaults[field.name] = (
                field.default
                if field.default is not MISSING
                else field.default_factory()
            )
    packages = {}
    for package in ("lightrag-hku", "raganything", "docling"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    values = {
        "version": 1,
        "packages": packages,
        "normalizer": 1,
        "chunk_identity": "document-v1",
        "parser": config.parser_name,
        "parse_method": config.parse_method,
        "multimodal": [
            config.enable_image_processing,
            config.enable_table_processing,
            config.enable_equation_processing,
        ],
        "llm": [
            settings.llm_model,
            hashlib.sha256(settings.llm_base_url.encode()).hexdigest(),
            settings.llm_max_tokens,
            json.loads(os.getenv("LLM_EXTRA_BODY_JSON", "{}")),
        ],
        "embedding": [
            settings.embedding_provider,
            settings.embedding_model,
            settings.embedding_dim,
            settings.embedding_max_tokens,
            hashlib.sha256(settings.embedding_base_url.encode()).hexdigest(),
        ],
        "vision": [
            settings.vision_model,
            hashlib.sha256(settings.vision_base_url.encode()).hexdigest(),
            settings.vision_max_tokens,
        ],
        "lightrag": defaults,
        "prompts": hashlib.sha256(canonical(PROMPTS).encode()).hexdigest(),
    }
    return hashlib.sha256(canonical(values).encode()).hexdigest()


class KnowledgeArtifactStore:
    def __init__(self, store):
        self.store = store

    def directory(self, kb):
        self.store.project(kb)
        root = self.store.config.root_dir.expanduser().resolve()
        target = root / "managed" / kb / "artifacts"
        if not target.resolve().is_relative_to(root) or any(
            p.is_symlink() for p in (root / "managed", target.parent, target)
        ):
            raise ValueError("knowledge_path_escape")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def load(self, doc, signature):
        path = self.directory(doc["kb"]) / f"{doc['id']}-{signature}.json"
        try:
            payload = json.loads(path.read_text())
            content = payload["content"]
            if (
                payload["sha256"]
                != hashlib.sha256(canonical(content).encode()).hexdigest()
                or content["original_sha256"] != doc["sha256"]
                or content["signature"] != signature
                or content["kb"] != doc["kb"]
                or content["document_id"] != doc["id"]
            ):
                return None
            if (
                content["kind"] != "text"
                or not isinstance(content["text"], str)
                or not content["text"].strip()
            ):
                return None
            return content
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save_text(self, doc, signature, text):
        content = {
            "kind": "text",
            "text": text,
            "kb": doc["kb"],
            "document_id": doc["id"],
            "original_sha256": doc["sha256"],
            "signature": signature,
        }
        if not text.strip():
            raise ValueError("empty_knowledge_document")
        atomic_json(
            self.directory(doc["kb"]) / f"{doc['id']}-{signature}.json",
            {
                "content": content,
                "sha256": hashlib.sha256(canonical(content).encode()).hexdigest(),
            },
        )
        return content


class KnowledgeUsageRecorder:
    def __init__(self, store, job_id):
        self.store, self.job_id = store, job_id
        self.stage = "indexing"
        self._embedding_stages = {}

    def begin(self, kind, input_count=0, *, stage=None):
        with self.store.connect(write=True) as db:
            return db.execute(
                "INSERT INTO usage(job_id,stage,kind,input_count,status) VALUES(?,?,?,?,'started')",
                (self.job_id, stage or self.stage, kind, input_count),
            ).lastrowid

    def finish(self, row_id, usage=None, *, status="complete"):
        with self.store.connect(write=True) as db:
            db.execute(
                "UPDATE usage SET status=?,provider_usage=?,usage_source=? WHERE id=?",
                (
                    status,
                    json.dumps(usage) if usage is not None else None,
                    "provider" if usage is not None else "unknown",
                    row_id,
                ),
            )

    def event(self, kind):
        self.finish(self.begin(kind))

    def embedding_stage(self, texts):
        stages = set()
        for text in texts:
            digest = hashlib.sha256(text.encode()).hexdigest()
            stages.update(self._embedding_stages.get(digest, {"unknown_embedding"}))
        return stages.pop() if len(stages) == 1 else "mixed_embedding"

    def instrument(self, rag):
        cache = rag.llm_response_cache
        original_get = cache.get_by_id

        async def measured_get(key):
            result = await original_get(key)
            if key.startswith(("default:extract:", "default:summary:")):
                self.event("llm_cache_hit" if result else "llm_cache_miss")
            return result

        cache.get_by_id = measured_get
        for name, stage in (
            ("chunks_vdb", "new_chunks"),
            ("entities_vdb", "graph_embedding"),
            ("relationships_vdb", "graph_embedding"),
        ):
            storage = getattr(rag, name)
            original = storage.upsert

            async def measured(
                data, _original=original, _storage=storage, _stage=stage
            ):
                previous = (
                    await _storage.get_by_ids(list(data))
                    if _stage == "graph_embedding"
                    else [None] * len(data)
                )
                # The shared embedding queue retains its first task's ContextVars.
                for value, old in zip(data.values(), previous, strict=True):
                    digest = hashlib.sha256(value["content"].encode()).hexdigest()
                    self._embedding_stages.setdefault(digest, set()).add(
                        "affected_graph_merge" if old is not None else _stage
                    )
                return await _original(data)

            storage.upsert = measured
