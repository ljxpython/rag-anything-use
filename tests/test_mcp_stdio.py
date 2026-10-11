from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = PROJECT_ROOT / "src/mcp_server.py"


def test_mcp_stdio_server_lists_tools_and_handles_admin_calls(
    published_config, monkeypatch
) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.setenv("KNOWLEDGE_STDIO_TOKEN", "1" * 32)

    async def _run() -> None:
        async with Client(
            StdioTransport(
                command=sys.executable,
                args=[str(SERVER_SCRIPT)],
                env=dict(os.environ),
                keep_alive=False,
            )
        ) as client:
            tools = await client.list_tools()
            tool_names = sorted(tool.name for tool in tools)
            assert tool_names == [
                "get_project_knowledge_document_status",
                "list_project_knowledge_documents",
                "mcp_query_project_knowledge",
            ]

            list_result = await client.call_tool(
                "list_project_knowledge_documents",
                {},
            )
            assert list_result.data["count"] == 1
            assert "PRIVATE" not in str(list_result.data)
            assert "SECRET" not in str(list_result.data)

            status_result = await client.call_tool(
                "get_project_knowledge_document_status",
                {
                    "document_id": "kd_" + "f" * 32,
                },
            )
            assert status_result.data["overall_status"] == "not_found"

    asyncio.run(_run())
