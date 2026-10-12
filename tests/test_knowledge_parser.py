import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.knowledge import rag_engine as module
from src.knowledge.content_normalizer import normalize_content_list
from src.knowledge.ingest_service import KnowledgeIngestService
from src.knowledge.parser_adapter import DoclingParserAdapter
from src.knowledge.rag_engine import CHUNK_DOCUMENT, ProjectRAGEngine


def test_main_failed_ingest_exits_nonzero(published_config, tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "main.py"),
            "ingest",
            "--project-id",
            "missing_file",
            "--file",
            str(tmp_path / "missing.md"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout)["accepted"] is False
    assert result.returncode == 1


def test_parser_preserves_upstream_id_without_inventing_page_count(tmp_path):
    blocks = [{"type": "text", "text": "page three", "page_idx": 2}]
    rag = SimpleNamespace(
        parse_document=AsyncMock(return_value=(blocks, "doc-upstream"))
    )
    parsed = asyncio.run(DoclingParserAdapter(rag=rag).parse_file(tmp_path / "a.pdf"))
    assert parsed.source_document_id == "doc-upstream"
    assert parsed.content_list == blocks
    assert parsed.metadata.get("page_count") is None


@pytest.mark.parametrize("result", [("bad", "doc-id"), ([],), (["bad"], "id"), 42])
def test_parser_rejects_malformed_results(tmp_path, result):
    rag = SimpleNamespace(parse_document=AsyncMock(return_value=result))
    with pytest.raises(TypeError):
        asyncio.run(DoclingParserAdapter(rag=rag).parse_file(tmp_path / "a.pdf"))


@pytest.mark.parametrize(
    "failure", [RuntimeError("parser failed"), asyncio.CancelledError()]
)
def test_parser_preserves_failure_and_cancellation(tmp_path, failure):
    rag = SimpleNamespace(parse_document=AsyncMock(side_effect=failure))
    with pytest.raises(type(failure)) as error:
        asyncio.run(DoclingParserAdapter(rag=rag).parse_file(tmp_path / "a.pdf"))
    assert error.value is failure


def test_normalizer_owns_source_identity_and_keeps_only_valid_pages():
    blocks = normalize_content_list(
        [
            {
                "type": "text",
                "text": "a",
                "page_idx": 2,
                "metadata": {
                    "document_id": "other",
                    "filename": "secret",
                    "page_index": 9,
                },
            },
            {"type": "text", "text": "b", "page_idx": True},
            {"type": "text", "text": "c", "page_idx": -1},
            {"type": "text", "text": "d"},
        ],
        document_id="kd-test",
        filename="a.pdf",
    )
    assert blocks[0]["metadata"]["document_id"] == "kd-test"
    assert blocks[0]["metadata"]["filename"] == "a.pdf"
    assert blocks[0]["metadata"]["page_index"] == 2
    assert all("page_index" not in block["metadata"] for block in blocks[1:])


def test_rag_cache_and_effective_parser_config(published_config, monkeypatch):
    from dataclasses import replace

    config = replace(published_config, parser_name="mineru", parse_method="ocr")
    engine = ProjectRAGEngine(config)
    native = SimpleNamespace(finalize_storages=AsyncMock())

    async def get_native(*args):
        await asyncio.sleep(0)
        return native

    engine.get_lightrag = get_native
    factory = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(module, "build_raganything", factory)

    async def run():
        first, second = await asyncio.gather(
            engine.get_rag("new"), engine.get_rag("new")
        )
        assert first is second

    asyncio.run(run())
    factory.assert_called_once()
    assert factory.call_args.kwargs["parser_name"] == "mineru"
    assert factory.call_args.kwargs["parse_method"] == "ocr"
    assert factory.call_args.kwargs["parser_output_dir"] == str(
        engine.get_project_paths("new").parser_dir
    )


def test_offline_same_text_keeps_two_document_sources(online_services, tmp_path):
    from src.knowledge.document_registry import KnowledgeDocumentRegistry

    engine = online_services.generations.engine
    service = KnowledgeIngestService(rag_engine=engine)
    files = [tmp_path / "one" / "same.md", tmp_path / "two" / "same.md"]
    for file in files:
        file.parent.mkdir()
        file.write_text("Orion 服务审计编号 A-731。", encoding="utf-8")

    async def run():
        try:
            results = [
                await service.ingest_document(project_id="offline", file_path=str(file))
                for file in files
            ]
            assert all(result.accepted for result in results)
            native = await engine.get_lightrag("offline")
            ids = {result.document_id for result in results}
            statuses = [await native.doc_status.get_by_id(doc_id) for doc_id in ids]
            chunk_ids = {
                chunk_id for record in statuses for chunk_id in record["chunks_list"]
            }
            chunks = dict(
                zip(
                    chunk_ids,
                    await native.text_chunks.get_by_ids(list(chunk_ids)),
                    strict=True,
                )
            )
            assert {chunk["full_doc_id"] for chunk in chunks.values()} == ids
            assert {chunk["file_path"] for chunk in chunks.values()} == ids
            assert len(chunks) == 2
            records = KnowledgeDocumentRegistry(
                engine.get_project_paths("offline")
            ).list_documents()
            assert all(record.page_count is None for record in records)
            assert all(record.chunk_count == 1 for record in records)
            from src.cli import _execute
            from argparse import Namespace
            from fastmcp import Client
            from src.mcp_server import create_server
            import json
            import os

            await _execute(Namespace(command="publish", project_id="offline"), engine)
            with patch.dict(
                os.environ,
                {
                    "KNOWLEDGE_MCP_TOKEN_SCOPES_JSON": json.dumps(
                        {
                            "a" * 32: {
                                "tenant_id": "__default",
                                "project_id": "11111111-1111-4111-8111-111111111111",
                                "namespace": "offline",
                            }
                        }
                    ),
                    "KNOWLEDGE_STDIO_TOKEN": "a" * 32,
                    "MCP_TRANSPORT": "stdio",
                },
            ):
                async with Client(create_server(engine.config, engine)) as client:
                    result = await client.call_tool(
                        "mcp_query_project_knowledge", {"query": "Orion A-731"}
                    )
                    assert {
                        source["document_id"]
                        for source in result.structured_content["sources"]
                    } == ids
        finally:
            await engine.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure", [RuntimeError("index failed"), asyncio.CancelledError()]
)
def test_content_list_document_context_is_reset(published_config, failure):
    engine = ProjectRAGEngine(published_config)

    async def insert(**kwargs):
        assert CHUNK_DOCUMENT.get() == "kd-test"
        assert kwargs["doc_id"] == kwargs["file_path"] == "kd-test"
        raise failure

    engine.get_rag = AsyncMock(return_value=SimpleNamespace(insert_content_list=insert))
    # The fake RAG object has no optional parser modules in the text-only test environment.
    from unittest.mock import patch

    with (
        patch.object(module, "install_document_chunk_ids"),
        pytest.raises(type(failure)),
    ):
        asyncio.run(
            engine.ingest_content_list(
                project_id="new", document_id="kd-test", content_list=[]
            )
        )
    assert CHUNK_DOCUMENT.get() is None
