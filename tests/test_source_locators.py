import asyncio

from src.knowledge.citations import build_retrieval_sources
from src.knowledge.schemas import KnowledgeDocumentRecord, KnowledgeRetrievalRequest


def record(name="public.pdf"):
    return KnowledgeDocumentRecord(
        document_id="kd_" + "1" * 32,
        project_id="a",
        filename=name,
        source_type="managed_upload",
        overall_status="ready",
    )


def test_versioned_sources_keep_v1_and_use_only_bound_stored_pages():
    doc = record()
    chunk = {
        "chunk_id": "chunk-a",
        "file_path": doc.document_id,
        "content": "answer",
        "page_idx": 99,
        "page_idx_end": 100,
    }
    query = {"status": "success", "data": {"chunks": [chunk]}}
    row = {
        "full_doc_id": doc.document_id,
        "file_path": doc.document_id,
        "page_idx": 2,
        "page_idx_end": 4,
        "original_type": "table",
    }
    v1 = build_retrieval_sources(query, [doc], 8)
    assert set(v1) == {"status", "sources"}
    assert set(v1["sources"][0]) == {
        "source_id",
        "document_id",
        "chunk_id",
        "title",
        "kind",
        "preview",
        "truncated",
    }
    v2 = build_retrieval_sources(
        query, [doc], 8, sources_version=2, chunk_rows={"chunk-a": row}
    )
    assert v2["sources_version"] == 2
    assert v2["sources"][0]["locator"] == {
        "unit": "page",
        "start": 3,
        "end": 5,
        "block_type": "table",
    }
    for invalid in (
        None,
        {**row, "full_doc_id": "other"},
        {**row, "page_idx": True},
        {**row, "page_idx_end": 1},
    ):
        locator = build_retrieval_sources(
            query, [doc], 8, sources_version=2, chunk_rows={"chunk-a": invalid}
        )["sources"][0]["locator"]
        assert (
            locator["unit"] == "unknown"
            and locator["start"] is None
            and locator["end"] is None
        )
    for name, unit in (("public.pptx", "slide"), ("public.docx", "unknown")):
        locator = build_retrieval_sources(
            query, [record(name)], 8, sources_version=2, chunk_rows={"chunk-a": row}
        )["sources"][0]["locator"]
        assert locator["unit"] == unit
    assert build_retrieval_sources(
        {"status": "failure", "metadata": {"failure_reason": "no_results"}},
        [],
        8,
        sources_version=2,
    ) == {"status": "no_hit", "sources": [], "sources_version": 2}


def test_engine_v2_reads_native_provenance(published_config, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from src.knowledge import rag_engine

    doc = record()
    monkeypatch.setattr(rag_engine, "validate_publication", lambda *a: [doc])
    native = SimpleNamespace(
        aquery_data=AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "chunks": [
                        {
                            "chunk_id": "chunk-a",
                            "file_path": doc.document_id,
                            "content": "answer",
                            "page_idx": 500,
                        }
                    ]
                },
            }
        ),
        text_chunks=SimpleNamespace(
            get_by_ids=AsyncMock(
                return_value=[
                    {
                        "full_doc_id": doc.document_id,
                        "file_path": doc.document_id,
                        "page_idx": 1,
                        "page_idx_end": 2,
                    }
                ]
            )
        ),
    )
    engine = rag_engine.ProjectRAGEngine(published_config)
    monkeypatch.setattr(engine, "get_lightrag", AsyncMock(return_value=native))
    result = asyncio.run(
        engine.retrieve(
            "alpha", KnowledgeRetrievalRequest(query="test", sources_version=2)
        )
    )
    assert result["sources"][0]["locator"]["start"] == 2
    native.text_chunks.get_by_ids.assert_awaited_once_with(["chunk-a"])
