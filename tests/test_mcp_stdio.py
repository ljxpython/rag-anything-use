from __future__ import annotations

import asyncio
from pathlib import Path

from fastmcp import Client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = PROJECT_ROOT / "src/mcp_server.py"


def test_mcp_stdio_server_lists_tools_and_handles_admin_calls() -> None:
    async def _run() -> None:
        async with Client(SERVER_SCRIPT) as client:
            tools = await client.list_tools()
            tool_names = sorted(tool.name for tool in tools)
            assert tool_names == [
                "get_project_knowledge_document_status",
                "list_project_knowledge_documents",
                "query_project_knowledge",
            ]

            list_result = await client.call_tool(
                "list_project_knowledge_documents",
                {"project_id": "pytest-mcp-empty"},
            )
            assert list_result.data == {
                "project_id": "pytest-mcp-empty",
                "count": 0,
                "documents": [],
            }

            status_result = await client.call_tool(
                "get_project_knowledge_document_status",
                {
                    "project_id": "pytest-mcp-empty",
                    "document_id": "missing-doc",
                },
            )
            assert status_result.data["overall_status"] == "not_found"
            assert status_result.data["project_id"] == "pytest-mcp-empty"

    asyncio.run(_run())
