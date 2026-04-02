from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP

from src.knowledge import (
    KnowledgeAdminService,
    KnowledgeQueryService,
    ProjectRAGEngine,
    build_knowledge_service_config,
)
from src.knowledge.schemas import ProjectKnowledgeQueryRequest

mcp = FastMCP("RAGAnythingKnowledgeServer")
SUPPORTED_TRANSPORTS = {"stdio", "http", "sse", "streamable-http"}


def _build_services() -> tuple[KnowledgeQueryService, KnowledgeAdminService]:
    config = build_knowledge_service_config()
    rag_engine = ProjectRAGEngine(config)
    return (
        KnowledgeQueryService(rag_engine=rag_engine),
        KnowledgeAdminService(rag_engine=rag_engine),
    )


@mcp.tool()
def query_project_knowledge(
    project_id: str,
    query: str,
    top_k: int = 8,
    mode: str = "hybrid",
) -> dict:
    """查询指定项目的知识库。"""

    query_service, _ = _build_services()
    result = asyncio.run(
        query_service.query_project_knowledge(
            ProjectKnowledgeQueryRequest(
                project_id=project_id,
                query=query,
                top_k=top_k,
                mode=mode,
                include_citations=True,
            )
        )
    )
    return result.model_dump()


@mcp.tool()
def list_project_knowledge_documents(
    project_id: str,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    """列出项目知识文档。"""

    _, admin_service = _build_services()
    return admin_service.list_project_documents(
        project_id=project_id,
        status=status,
        limit=limit,
    )


@mcp.tool()
def get_project_knowledge_document_status(
    project_id: str,
    document_id: str,
) -> dict:
    """查看单个知识文档状态。"""

    _, admin_service = _build_services()
    return admin_service.get_document_status(
        project_id=project_id,
        document_id=document_id,
    )


def build_server_run_settings() -> dict[str, Any]:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower() or "stdio"
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"unsupported_mcp_transport:{transport}")

    run_settings: dict[str, Any] = {
        "transport": transport,
        "show_banner": _parse_bool_env("MCP_SHOW_BANNER", False),
    }
    if transport == "stdio":
        return run_settings

    run_settings["host"] = os.getenv("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    run_settings["port"] = _parse_int_env("MCP_PORT", 8000)

    path = os.getenv("MCP_PATH", "").strip()
    if path:
        run_settings["path"] = path

    log_level = os.getenv("MCP_LOG_LEVEL", "").strip().upper()
    if log_level:
        run_settings["log_level"] = log_level

    message_path = os.getenv("MCP_MESSAGE_PATH", "").strip()
    if message_path:
        os.environ["FASTMCP_MESSAGE_PATH"] = message_path

    return run_settings


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    try:
        mcp.run(**build_server_run_settings())
    except KeyboardInterrupt:
        pass
