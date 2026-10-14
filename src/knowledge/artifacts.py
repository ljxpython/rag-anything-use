"""Checksummed complete parse results and safe per-attempt model usage."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
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


def _processing_values(config):
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
    values = {
        "version": 1,
        "packages": {
            package: _package_version(package)
            for package in ("lightrag-hku", "raganything", "docling")
        },
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
    return values


def _package_version(package):
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def processing_signature(config):
    values = _processing_values(config)
    values["version"] = 2
    if any(values["multimodal"]):
        values.update(version=3, normalizer=2, artifact_format=2)
    else:
        # Preserve the reviewed text-only signature and its existing snapshots.
        values["packages"] = {"lightrag-hku": values["packages"]["lightrag-hku"]}
    return hashlib.sha256(canonical(values).encode()).hexdigest()


def compatible_processing_signature(config, expected):
    """Retain a reviewed v1 text signature without rewriting immutable snapshots."""
    if expected in (None, "dynamic_managed_v1") or expected == processing_signature(config):
        return processing_signature(config)
    values = _processing_values(config)
    packages = values["packages"]
    if (
        packages["lightrag-hku"] == "1.4.12"
        and packages["raganything"] in (None, "1.2.10", "1.4.2")
        and packages["docling"] in (None, "2.84.0")
        and not any(values["multimodal"])
    ):
        for rag_version in (None, "1.2.10", "1.4.2"):
            for docling_version in (None, "2.84.0"):
                values["packages"] = {
                    "lightrag-hku": "1.4.12",
                    "raganything": rag_version,
                    "docling": docling_version,
                }
                if expected == hashlib.sha256(canonical(values).encode()).hexdigest():
                    return expected
    raise ValueError("knowledge_processing_config_changed")


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
            if path.is_symlink():
                raise ValueError("knowledge_path_escape")
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
                raise ValueError("knowledge_artifact_invalid")
            if content["kind"] == "content_list":
                return self._load_document(doc, content)
            from src.knowledge.document_formats import DOCUMENT_MIME

            if doc.get("mime_type") in DOCUMENT_MIME:
                raise ValueError("knowledge_artifact_invalid")
            if (
                content["kind"] != "text"
                or not isinstance(content["text"], str)
                or not content["text"].strip()
            ):
                return None
            return content
        except (OSError, ValueError, KeyError, TypeError):
            from src.knowledge.document_formats import DOCUMENT_MIME

            if (path.exists() or path.is_symlink()) and doc.get(
                "mime_type"
            ) in DOCUMENT_MIME:
                raise ValueError("knowledge_artifact_invalid") from None
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

    def _asset_directory(self, doc, signature):
        if not re.fullmatch(r"kd_[a-f0-9]{32}", doc["id"]) or not re.fullmatch(
            r"[a-f0-9]{64}", signature
        ):
            raise ValueError("knowledge_artifact_invalid")
        root = self.directory(doc["kb"])
        target = root / "assets" / (doc["id"] + "-" + signature)
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError("knowledge_path_escape")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _load_document(self, doc, content):
        from src.knowledge.document_formats import validate_original

        if content["version"] != 2:
            raise ValueError("knowledge_artifact_invalid")
        blocks = copy.deepcopy(content["content_list"])
        if (
            not isinstance(blocks, list)
            or not blocks
            or any(not isinstance(item, dict) for item in blocks)
        ):
            raise ValueError("knowledge_artifact_invalid")
        assets = content["assets"]
        if not isinstance(assets, dict):
            raise ValueError("knowledge_artifact_invalid")  # noqa: TRY004 - Corrupt artifacts keep one domain error.
        directory = self._asset_directory(doc, content["signature"])
        referenced = set()
        for block in blocks:
            if block.get("type") == "image" and not block.get("img_path"):
                raise ValueError("knowledge_artifact_invalid")
            for key in ("img_path", "image_path", "table_img_path"):
                value = block.get(key)
                if not value:
                    continue
                if not isinstance(value, str) or not value.startswith("asset:"):
                    raise ValueError("knowledge_artifact_invalid")
                name = value.removeprefix("asset:")
                asset = assets[name]
                if not isinstance(asset, dict) or asset.get("mime_type") not in {
                    "image/png",
                    "image/jpeg",
                }:
                    raise ValueError("knowledge_artifact_invalid")
                if not re.fullmatch(r"[a-f0-9]{64}\.(png|jpg)", name):
                    raise ValueError("knowledge_artifact_invalid")
                path = directory / name
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or path.stat().st_size != asset["size_bytes"]
                    or checksum(path) != asset["sha256"]
                    or name.split(".")[0] != asset["sha256"]
                ):
                    raise ValueError("knowledge_artifact_invalid")
                validate_original(
                    path, asset["mime_type"], self.store.config.max_file_bytes
                )
                referenced.add(name)
                block[key] = str(path)
        if referenced != set(assets):
            raise ValueError("knowledge_artifact_invalid")
        return {**content, "content_list": blocks}

    def save_document(
        self, doc, signature, blocks, *, parser_name, trusted_dir, metadata=None
    ):
        from PIL import Image

        from src.knowledge.document_formats import validate_original

        directory = self._asset_directory(doc, signature)
        trusted_dir = Path(trusted_dir).resolve()
        blocks = copy.deepcopy(blocks)
        assets = {}
        for block in blocks:
            if block.get("type") == "image" and not block.get("img_path"):
                raise ValueError("knowledge_artifact_invalid")
            for key in ("img_path", "image_path", "table_img_path"):
                value = block.get(key)
                if not value:
                    continue
                path = Path(value)
                if (
                    path.is_symlink()
                    or not path.resolve().is_relative_to(trusted_dir)
                    or not path.is_file()
                ):
                    raise ValueError("knowledge_path_escape")
                if path.stat().st_size > self.store.config.max_file_bytes:
                    raise ValueError("knowledge_quota_exceeded")
                with Image.open(path) as image:
                    mime = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(image.format)
                if mime is None:
                    raise ValueError("knowledge_invalid_content")
                validate_original(path, mime, self.store.config.max_file_bytes)
                digest = checksum(path)
                name = digest + (".png" if mime == "image/png" else ".jpg")
                target = directory / name
                if target.is_symlink():
                    raise ValueError("knowledge_path_escape")
                if target.exists():
                    if checksum(target) != digest:
                        raise ValueError("knowledge_artifact_invalid")
                else:
                    with tempfile.NamedTemporaryFile(
                        dir=directory, delete=False
                    ) as handle:
                        temporary = Path(handle.name)
                    try:
                        shutil.copyfile(path, temporary)
                        with temporary.open("rb") as handle:
                            os.fsync(handle.fileno())
                        if checksum(temporary) != digest:
                            raise ValueError("knowledge_artifact_invalid")
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
                assets[name] = {
                    "sha256": digest,
                    "size_bytes": target.stat().st_size,
                    "mime_type": mime,
                }
                block[key] = "asset:" + name
        fsync_directory(directory)
        content = {
            "kind": "content_list",
            "version": 2,
            "content_list": blocks,
            "assets": assets,
            "parser_name": parser_name,
            "metadata": metadata or {},
            "kb": doc["kb"],
            "document_id": doc["id"],
            "original_sha256": doc["sha256"],
            "signature": signature,
        }
        # Validate and materialize assets before committing the parse result.
        result = self._load_document(doc, content)
        atomic_json(
            self.directory(doc["kb"]) / f"{doc['id']}-{signature}.json",
            {
                "content": content,
                "sha256": hashlib.sha256(canonical(content).encode()).hexdigest(),
            },
        )
        return result


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
