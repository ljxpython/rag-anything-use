import asyncio
import json

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from src.mcp_server import create_server


def test_http_explicit_auth_and_mcp_receipt_contract(online_services, monkeypatch):
    from test_knowledge_upload import fixture
    from src.knowledge.job_worker import KnowledgeJobSupervisor

    s = online_services
    token = "a" * 32
    monkeypatch.setenv(
        "KNOWLEDGE_MCP_TOKEN_SCOPES_JSON",
        json.dumps({token: s.scope.model_dump(exclude_none=True)}),
    )

    async def no_worker(self):
        return False

    monkeypatch.setattr(KnowledgeJobSupervisor, "start", no_worker)
    server = create_server(s.config)
    app = server.http_app()
    ref, grant = fixture(s)
    headers = {
        "authorization": "Bearer " + token,
        "x-knowledge-file-ref": json.dumps(ref),
        "x-knowledge-operation-grant": json.dumps(grant),
        "content-type": ref["mime_type"],
    }

    async def run():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as http:
                response = await http.get("/internal/knowledge/capabilities")
                assert response.status_code == 401
                response = await http.get(
                    "/internal/knowledge/capabilities",
                    headers={"authorization": "Bearer " + token},
                )
                assert response.json()["upload_enabled"]
                forged = {**headers, "x-knowledge-operation-grant": "{}"}
                assert (
                    await http.put(
                        "/internal/knowledge/uploads/request",
                        headers=forged,
                        content=b"# content",
                    )
                ).status_code == 401
                response = await http.put(
                    "/internal/knowledge/uploads/request",
                    headers=headers,
                    content=b"# content",
                )
                assert response.status_code == 200
                upload_id = response.json()["upload_id"]

                # Use an ASGI-backed HTTP transport; private headers stay outside tool args.
                def client_factory(**kwargs):
                    return httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), **kwargs
                    )

                tool_headers = {
                    "x-knowledge-upload-id": upload_id,
                    "x-knowledge-operation-grant": json.dumps(grant),
                }
                async with Client(
                    StreamableHttpTransport(
                        "http://test/mcp",
                        headers=tool_headers,
                        auth=token,
                        httpx_client_factory=client_factory,
                    )
                ) as client:
                    tools = await client.list_tools()
                    submit = next(
                        t
                        for t in tools
                        if t.name == "mcp_submit_project_knowledge_document"
                    )
                    assert set(submit.inputSchema["properties"]) == {"file_ref"}
                    assert (
                        not submit.annotations.readOnlyHint
                        and submit.annotations.idempotentHint
                        and not submit.annotations.destructiveHint
                    )
                    result = await client.call_tool(submit.name, {"file_ref": ref})
                    receipt = result.structured_content
                    assert json.loads(result.content[0].text) == receipt
                    assert receipt["status"] == "queued" and not receipt["reused"]
                    assert set(receipt) == {
                        "version",
                        "job_id",
                        "document_id",
                        "file_name",
                        "status",
                        "searchable",
                        "reused",
                        "error_code",
                        "created_at",
                        "updated_at",
                    }
                    fetched = await client.call_tool(
                        "mcp_get_project_knowledge_ingest_job",
                        {"job_id": receipt["job_id"]},
                    )
                    assert "reused" not in fetched.structured_content
                    assert fetched.structured_content["job_id"] == receipt["job_id"]
                    for args in (
                        {"file_ref": ref, "project_id": "forged"},
                        {"file_ref": {**ref, "path": "/PRIVATE/secret"}},
                    ):
                        assert (
                            await client.call_tool(
                                submit.name, args, raise_on_error=False
                            )
                        ).is_error
                    assert (
                        await client.call_tool(
                            "mcp_query_project_knowledge", {"query": "empty"}
                        )
                    ).structured_content == {"status": "no_hit", "sources": []}
                async with Client(
                    StreamableHttpTransport(
                        "http://test/mcp",
                        auth=token,
                        httpx_client_factory=client_factory,
                    )
                ) as client:
                    result = await client.call_tool(
                        "mcp_submit_project_knowledge_document",
                        {"file_ref": ref},
                        raise_on_error=False,
                    )
                    assert result.is_error and "PRIVATE" not in str(result.content)
                response = await http.get("/internal/knowledge/jobs", headers=headers)
                assert response.json()["total"] == 1
                assert (
                    "thread1" not in response.text and "upload_id" not in response.text
                )
                assert (
                    await http.get("/internal/knowledge/documents", headers=headers)
                ).json() == {"items": [], "total": 0}

    asyncio.run(run())


def test_activated_mcp_sources_keep_stable_ids(online_services, monkeypatch):
    from test_knowledge_generations import upload
    from scripts.verify_incremental_snapshot import TEXTS

    s = online_services
    monkeypatch.setenv(
        "KNOWLEDGE_MCP_TOKEN_SCOPES_JSON",
        json.dumps({"a" * 32: s.scope.model_dump(exclude_none=True)}),
    )

    async def run():
        ids = []
        for key in "AB":
            receipt = await upload(s, TEXTS[key], key)
            ids.append(receipt["document_id"])
            await s.generations.build(receipt["job_id"])
            await s.generations.activate(receipt["job_id"])
        # Exercise the unchanged MCP source contract through the actual server/client.
        async with Client(create_server(s.config)) as client:
            import src.mcp_server as module

            monkeypatch.setattr(module, "resolve_knowledge_scope", lambda _: s.scope)
            result = await client.call_tool(
                "mcp_query_project_knowledge", {"query": "Orion 服务"}
            )
            assert result.structured_content["status"] == "ok"
            assert {
                r["document_id"] for r in result.structured_content["sources"]
            } == set(ids)
            for source in result.structured_content["sources"]:
                assert set(source) == {
                    "source_id",
                    "document_id",
                    "chunk_id",
                    "title",
                    "kind",
                    "preview",
                    "truncated",
                }
                assert "PRIVATE" not in json.dumps(
                    source
                ) and "/managed/" not in json.dumps(source)
        await s.generations.close()

    asyncio.run(run())
