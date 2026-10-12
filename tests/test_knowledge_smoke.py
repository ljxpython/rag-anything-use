from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli import build_parser
from src.knowledge import ProjectRAGEngine, build_knowledge_service_config
from src.knowledge.citations import build_citations, build_query_result_artifacts
from src.knowledge.content_normalizer import normalize_content_list
from src.knowledge.schemas import KnowledgeDocumentRecord
from src.mcp_server import build_server_run_settings, create_server


def test_build_knowledge_service_config_defaults() -> None:
    config = build_knowledge_service_config()
    assert config.parser_name == "docling"
    assert config.query_default_mode == "hybrid"
    assert config.query_default_top_k == 8
    assert config.root_dir.name == "knowledge_data"


def test_build_parser_has_expected_commands() -> None:
    parser = build_parser()
    subcommands = parser._subparsers._group_actions[0].choices
    assert sorted(subcommands.keys()) == [
        "activate-knowledge-generation",
        "debug-retrieve",
        "doc-status",
        "ingest",
        "init-project-knowledge",
        "list-docs",
        "migrate-project-knowledge",
        "publish",
        "query",
    ]


def test_mcp_server_created(monkeypatch) -> None:
    import json

    monkeypatch.setenv(
        "KNOWLEDGE_MCP_TOKEN_SCOPES_JSON",
        json.dumps(
            {
                "a" * 32: {
                    "tenant_id": "__default",
                    "project_id": "00000000-0000-0000-0000-000000000001",
                    "namespace": "test",
                }
            }
        ),
    )
    assert type(create_server()).__name__ == "FastMCP"


def test_build_server_run_settings_defaults(monkeypatch) -> None:
    for name in [
        "MCP_TRANSPORT",
        "MCP_SHOW_BANNER",
        "MCP_HOST",
        "MCP_PORT",
        "MCP_PATH",
        "MCP_LOG_LEVEL",
        "MCP_MESSAGE_PATH",
    ]:
        monkeypatch.delenv(name, raising=False)
    settings = build_server_run_settings()
    assert settings == {
        "transport": "http",
        "show_banner": False,
        "host": "127.0.0.1",
        "port": 8000,
        "path": "/mcp",
    }


def test_build_server_run_settings_sse(monkeypatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "sse")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8765")
    monkeypatch.setenv("MCP_PATH", "/rag/sse")
    monkeypatch.setenv("MCP_MESSAGE_PATH", "/rag/messages/")
    monkeypatch.setenv("MCP_LOG_LEVEL", "info")
    monkeypatch.setenv("MCP_SHOW_BANNER", "true")
    settings = build_server_run_settings()
    assert settings == {
        "transport": "sse",
        "show_banner": True,
        "host": "0.0.0.0",
        "port": 8765,
        "path": "/rag/sse",
        "log_level": "INFO",
    }


def test_project_paths_resolve_under_knowledge_root() -> None:
    config = build_knowledge_service_config()
    engine = ProjectRAGEngine(config)
    paths = engine.get_project_paths("demo-project")
    assert paths.project_dir.name == "demo-project"
    assert paths.rag_workdir.parent == paths.project_dir


def test_normalize_content_list_and_build_citations() -> None:
    items = normalize_content_list(
        [{"type": "text", "text": "abc", "page_idx": 0}],
        document_id="d1",
        filename="a.pdf",
    )
    citations = build_citations(items)
    assert items[0]["metadata"]["chunk_id"] == "d1:chunk:1"
    assert citations[0].document_id == "d1"
    assert citations[0].snippet == "abc"


def test_build_query_result_artifacts_maps_document_by_filename() -> None:
    query_data = {
        "data": {
            "chunks": [
                {
                    "reference_id": "1",
                    "content": "customer login api uses post",
                    "file_path": "接口文档.pdf",
                    "chunk_id": "chunk-1",
                }
            ]
        }
    }
    documents = [
        KnowledgeDocumentRecord(
            document_id="doc-1",
            project_id="p1",
            filename="接口文档.pdf",
            source_type="local_file",
            source_uri="/tmp/接口文档.pdf",
        )
    ]
    citations, matched_document_ids, debug_chunks = build_query_result_artifacts(
        query_data,
        documents=documents,
    )
    assert matched_document_ids == ["doc-1"]
    assert citations[0].document_id == "doc-1"
    assert citations[0].chunk_id == "chunk-1"
    assert debug_chunks[0]["document_id"] == "doc-1"
