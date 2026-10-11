import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.knowledge.auth import KnowledgeTokenVerifier
from src.knowledge.citations import build_retrieval_sources
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.ingest_service import KnowledgeIngestService
from src.knowledge.project_paths import build_knowledge_project_paths
from src.knowledge.publication import namespace_lock, validate_publication
from src.knowledge.rag_engine import ProjectRAGEngine
from src.knowledge.schemas import (
    KnowledgeRetrievalRequest,
    ProjectKnowledgeQueryRequest,
)


def test_paths_and_symlink_escape(published_config, tmp_path):
    for name in (
        "..",
        "../escape",
        "/tmp/escape",
        "a/b",
        "a\\b",
        "a%2fb",
        " a",
        "a" * 97,
    ):
        with pytest.raises(ValueError):
            build_knowledge_project_paths(name, published_config)
    outside = tmp_path.parent / "outside"
    (tmp_path / "escape").symlink_to(outside)
    with pytest.raises(ValueError):
        build_knowledge_project_paths("escape", published_config)


def test_scope_credentials_and_publication_are_fail_closed(
    published_config, monkeypatch
):
    verifier = KnowledgeTokenVerifier(published_config)

    async def check():
        assert await verifier.verify_token("unknown") is None
        token = await verifier.verify_token("1" * 32)
        assert token.claims["namespace"] == "alpha"
        assert token.claims["project_id"].endswith("1")

    asyncio.run(check())
    paths = build_knowledge_project_paths("alpha", published_config)
    with namespace_lock(paths), pytest.raises(ValueError, match="in_use"), namespace_lock(paths, write=True):
        pass
    monkeypatch.setenv("EMBEDDING_MODEL", "other-model")
    with pytest.raises(ValueError, match="signature"):
        validate_publication(paths)


def test_retrieval_parameters():
    assert KnowledgeRetrievalRequest(query=" abc ").query == "abc"
    for kwargs in (
        {"query": " "},
        {"query": "a" * 2001},
        {"query": "q", "top_k": 9},
        {"query": "q", "top_k": True},
    ):
        with pytest.raises(ValidationError):
            KnowledgeRetrievalRequest(**kwargs)
    with pytest.raises(ValidationError):
        ProjectKnowledgeQueryRequest(project_id="x", query="x", document_ids=["d"])


def test_single_retrieval_opaque_sources_and_errors(published_config):
    engine = ProjectRAGEngine(published_config)
    records = KnowledgeDocumentRegistry(
        engine.get_project_paths("alpha")
    ).list_documents()
    data = {
        "status": "success",
        "data": {
            "chunks": [
                {
                    "file_path": records[0].document_id,
                    "chunk_id": "chunk-1",
                    "content": "中文资料" * 400,
                }
            ]
        },
        "raw_data": "SECRET",
    }
    rag = SimpleNamespace(aquery_data=AsyncMock(return_value=data), aquery=AsyncMock())
    engine.get_lightrag = AsyncMock(return_value=rag)
    result = asyncio.run(engine.retrieve("alpha", KnowledgeRetrievalRequest(query="q")))
    assert rag.aquery_data.await_count == 1
    assert rag.aquery.await_count == 0
    assert result["sources"][0]["truncated"]
    assert len(result["sources"][0]["preview"]) == 800
    assert "SECRET" not in json.dumps(result)
    assert "PRIVATE" not in json.dumps(result)
    assert build_retrieval_sources(
        {
            "status": "failure",
            "message": "Query returned no results",
            "metadata": {"failure_reason": "no_results"},
        },
        records,
        8,
    ) == {"status": "no_hit", "sources": []}
    for value in (
        {"status": "failure", "message": "upstream failed"},
        {
            "status": "success",
            "data": {
                "chunks": [{"file_path": "UNKNOWN", "chunk_id": "x", "content": "x"}]
            },
        },
    ):
        with pytest.raises(ValueError):
            build_retrieval_sources(value, records, 8)


def test_published_namespace_cannot_be_modified(published_config):
    engine = ProjectRAGEngine(published_config)
    with pytest.raises(ValueError, match="immutable"):
        asyncio.run(
            KnowledgeIngestService(rag_engine=engine).ingest_document(
                project_id="alpha", file_path="missing.md"
            )
        )


def test_cancelled_retrieval_is_control_flow(published_config):
    engine = ProjectRAGEngine(published_config)
    rag = SimpleNamespace(aquery_data=AsyncMock(side_effect=asyncio.CancelledError))
    engine.get_lightrag = AsyncMock(return_value=rag)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(engine.retrieve("alpha", KnowledgeRetrievalRequest(query="q")))
