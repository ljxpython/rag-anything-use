import asyncio
import json
import time
from dataclasses import replace

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from src.mcp_server import create_server


def test_lost_ack_lookup_is_private_read_only_and_survives_write_pause(
    online_services, monkeypatch
):
    from test_knowledge_upload import fixture, stream
    from src.knowledge.auth import KnowledgeScope
    from src.knowledge.operation_auth import signed

    s = online_services
    token, other_token = "a" * 32, "b" * 32
    other = s.store.register(
        s.scope.tenant_id,
        "00000000-0000-0000-0000-000000000002",
        s.signature,
    )
    other_scope = KnowledgeScope(
        tenant_id=other["tenant_id"],
        project_id=other["project_id"],
        knowledge_base_id=other["id"],
    )
    monkeypatch.setenv(
        "KNOWLEDGE_MCP_TOKEN_SCOPES_JSON",
        json.dumps(
            {
                token: s.scope.model_dump(exclude_none=True),
                other_token: other_scope.model_dump(exclude_none=True),
            }
        ),
    )
    ref, grant = fixture(s)

    def headers(grant, bearer=token):
        return {
            "authorization": "Bearer " + bearer,
            "x-knowledge-operation-grant": json.dumps(grant),
        }

    def snapshot():
        with s.store.connect() as db:
            return {
                table: [tuple(row) for row in db.execute("SELECT * FROM " + table)]
                for table in (
                    "projects",
                    "documents",
                    "jobs",
                    "requests",
                    "uploads",
                    "usage",
                )
            }

    async def run():
        ticket = await s.uploads.stage_upload(
            s.scope, "request", ref, grant, stream(b"# content")
        )
        accepted = s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)
        s.store.enable(s.scope.knowledge_base_id, False)
        config = replace(s.config, online_enabled=False)
        app = create_server(config).http_app()
        before = snapshot()
        calls = list(s.calls.rows)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                path = "/internal/knowledge/uploads/request"
                for _ in range(2):
                    response = await client.get(path, headers=headers(grant))
                    assert response.status_code == 200
                    assert response.json() == {
                        "request_id": "request",
                        "receipt": {**accepted, "reused": True},
                    }
                    assert len(response.content) < 4096
                assert (await client.get(path)).status_code == 401
                assert (
                    await client.get(path, headers=headers(grant, other_token))
                ).status_code == 401
                for field in (
                    "subject",
                    "credential_id",
                    "graph_id",
                    "thread_id",
                    "run_id",
                    "tool_call_id",
                    "request_id",
                    "sha256",
                    "size_bytes",
                    "file_name",
                    "mime_type",
                ):
                    changed = {**grant["values"], field: "changed"}
                    if field == "size_bytes":
                        changed[field] = ref[field] + 1
                    response = await client.get(
                        path, headers=headers(signed(changed, s.config, grant=True))
                    )
                    assert response.status_code == 401, (field, response.text)
                    assert accepted["job_id"] not in response.text
                expired = {
                    **grant["values"],
                    "iat": int(time.time()) - 60,
                    "exp": int(time.time()) - 30,
                }
                assert (
                    await client.get(
                        path, headers=headers(signed(expired, s.config, grant=True))
                    )
                ).status_code == 401
                assert (
                    await client.get(
                        path + "?project_id=forged", headers=headers(grant)
                    )
                ).status_code == 400
                _, pending_grant = fixture(s, request_id="not-accepted")
                unknown = await client.get(
                    "/internal/knowledge/uploads/not-accepted",
                    headers=headers(pending_grant),
                )
                assert unknown.status_code == 200
                assert unknown.json() == {"request_id": "not-accepted", "receipt": None}
                other_grant = s.authorizer.grant(
                    other_scope,
                    "upload",
                    {
                        key: value
                        for key, value in grant["values"].items()
                        if key
                        not in {
                            "tenant_id",
                            "project_id",
                            "knowledge_base_id",
                            "issuer",
                            "audience",
                            "iat",
                            "exp",
                            "nonce",
                            "operation",
                        }
                    },
                )
                separate = await client.get(
                    path, headers=headers(other_grant, other_token)
                )
                assert (
                    separate.status_code == 200 and separate.json()["receipt"] is None
                )
        assert snapshot() == before
        assert s.calls.rows == calls

    asyncio.run(run())


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
                lookup = await http.get(
                    "/internal/knowledge/uploads/request",
                    headers=headers,
                )
                assert lookup.status_code == 200
                assert lookup.json()["receipt"] is None

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
                    lookup = await http.get(
                        "/internal/knowledge/uploads/request",
                        headers=headers,
                    )
                    assert lookup.status_code == 200
                    assert lookup.json()["receipt"]["job_id"] == receipt["job_id"]
                    assert lookup.json()["receipt"]["reused"] is True
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
