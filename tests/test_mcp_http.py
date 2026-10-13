import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastmcp import Client


def test_http_auth_scopes_inputs_and_safe_results(published_config, tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "server.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, __file__, str(port)], stdout=log, stderr=log
        )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail((tmp_path / "server.log").read_text())
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("knowledge HTTP server startup timeout")
        url = f"http://127.0.0.1:{port}/mcp"

        async def run():
            async with httpx.AsyncClient(trust_env=False) as http:
                for token in (None, "invalid"):
                    response = await http.post(
                        url,
                        headers={"authorization": f"Bearer {token}"} if token else {},
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {},
                        },
                    )
                    assert response.status_code == 401
            for i in (1, 2):
                async with Client(url, auth=str(i) * 32) as client:
                    tools = await client.list_tools()
                    query = next(
                        t for t in tools if t.name == "mcp_query_project_knowledge"
                    )
                    assert query.annotations.readOnlyHint is True
                    assert set(query.inputSchema["properties"]) == {
                        "query",
                        "top_k",
                        "sources_version",
                    }
                    docs = (
                        await client.call_tool("list_project_knowledge_documents", {})
                    ).data
                    assert docs["documents"][0]["document_id"] == f"kd_{i:032x}"
                    assert "PRIVATE" not in str(docs) and "SECRET" not in str(docs)
                    found = await client.call_tool(query.name, {"query": "scope"})
                    assert (
                        found.structured_content["sources"][0]["document_id"]
                        == f"kd_{i:032x}"
                    )
                    for args in (
                        {"query": "scope", "project_id": "other"},
                        {"query": "scope", "top_k": 9},
                        {"query": "scope", "sources_version": 3},
                        {"query": " "},
                    ):
                        failure = await client.call_tool(
                            query.name, args, raise_on_error=False
                        )
                        assert failure.is_error
                    error = await client.call_tool(
                        query.name, {"query": "error"}, raise_on_error=False
                    )
                    assert error.is_error and "SECRET" not in str(error.content)

        asyncio.run(run())
    finally:
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.knowledge import ProjectRAGEngine, build_knowledge_service_config
    from src.knowledge.document_registry import KnowledgeDocumentRegistry
    from src.mcp_server import create_server

    class Engine(ProjectRAGEngine):
        async def get_lightrag(self, namespace):
            return None

        async def retrieve(self, namespace, request):
            if request.query == "error":
                raise RuntimeError("SECRET /PRIVATE")
            record = KnowledgeDocumentRegistry(
                self.get_project_paths(namespace)
            ).list_documents()[0]
            return {"status": "ok", "sources": [{"document_id": record.document_id}]}

    config = build_knowledge_service_config()
    create_server(config, Engine(config)).run(
        transport="http", host="127.0.0.1", port=int(sys.argv[1]), show_banner=False
    )
