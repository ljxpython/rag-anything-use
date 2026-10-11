"""Offline single-writer publication; serving holds shared namespace locks."""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager

from src.demo_support import load_settings
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.project_paths import KnowledgeProjectPaths


def model_signature() -> dict:
    settings = load_settings()
    return {
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "embedding_dim": settings.embedding_dim,
    }


@contextmanager
def namespace_lock(paths: KnowledgeProjectPaths, *, write: bool = False):
    if write:
        paths.project_dir.mkdir(parents=True, exist_ok=True)
    elif not paths.project_dir.is_dir():
        raise ValueError("knowledge_namespace_not_published")
    with (paths.project_dir / ".index.lock").open("a") as handle:
        try:
            fcntl.flock(
                handle, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB
            )
        except BlockingIOError as exc:
            raise ValueError("knowledge_namespace_in_use") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate_publication(paths: KnowledgeProjectPaths) -> list:
    marker = paths.manifest_dir / "publication.json"
    if not marker.is_file() or not paths.rag_workdir.is_dir():
        raise ValueError("knowledge_namespace_not_published")
    if json.loads(marker.read_text()) != model_signature():
        raise ValueError("knowledge_model_signature_mismatch")
    registry = KnowledgeDocumentRegistry(paths)
    if not registry.registry_path.is_file():
        raise ValueError("knowledge_manifest_missing")
    records = registry.list_documents(limit=10000)
    if not records or any(
        r.overall_status != "ready" or r.index_status != "ready" for r in records
    ):
        raise ValueError("knowledge_index_not_ready")
    return records
