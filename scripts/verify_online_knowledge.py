"""Real RAG worker/MCP evidence with an explicit local platform authorization stub."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from collections import Counter
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from src.knowledge.artifacts import checksum, processing_signature
from src.knowledge.config import build_knowledge_service_config
from src.knowledge.generations import KnowledgeGenerationService, storage_dir
from src.knowledge.jobs import KnowledgeJobStore
from src.knowledge.operation_auth import signed
from src.mcp_server import create_server
from scripts.verify_incremental_snapshot import TEXTS


async def run():
    with tempfile.TemporaryDirectory(prefix="rag-online-") as temporary:
        root = Path(temporary)
        config = replace(
            build_knowledge_service_config(),
            root_dir=root,
            online_enabled=True,
            authorization_key_id="isolated-test",
            authorization_secret=os.urandom(32).hex(),
        )

        class PlatformStub(BaseHTTPRequestHandler):
            def do_POST(self):
                envelope = json.loads(
                    self.rfile.read(int(self.headers["content-length"]))
                )
                assert envelope == signed(envelope["values"], config)
                clock = int(time.time())
                values = {
                    **envelope["values"],
                    "issuer": "platform-api",
                    "audience": "rag-knowledge",
                    "iat": clock,
                    "exp": clock + 30,
                    "nonce": os.urandom(16).hex(),
                }
                result = json.dumps(signed(values, config, grant=True)).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(result)))
                self.end_headers()
                self.wfile.write(result)

            def log_message(self, *args):
                pass

        platform = ThreadingHTTPServer(("127.0.0.1", 0), PlatformStub)
        thread = threading.Thread(target=platform.serve_forever, daemon=True)
        thread.start()
        config = replace(
            config, authorize_url=f"http://127.0.0.1:{platform.server_port}/authorize"
        )
        store = KnowledgeJobStore(config)
        signature = processing_signature(config)
        project = store.register(
            "__default", "11111111-1111-4111-8111-111111111111", signature, enabled=True
        )
        token = os.urandom(32).hex()
        scope = {
            "tenant_id": project["tenant_id"],
            "project_id": project["project_id"],
            "knowledge_base_id": project["id"],
        }
        previous = os.environ.get("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON")
        os.environ["KNOWLEDGE_MCP_TOKEN_SCOPES_JSON"] = json.dumps({token: scope})
        server = create_server(config)
        app = server.http_app()
        identity = dict(
            subject="fixture-user",
            principal_type="user",
            credential_id=None,
            resource_id="fixture-resource",
            graph_id="showcase_demo",
            thread_id="fixture-thread",
            run_id="fixture-run",
            tool_call_id="fixture-call",
        )
        receipts, counts, namespaces = [], {}, []

        def factory(**kwargs):
            return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)

        async def query(key, ids):
            async with Client(
                StreamableHttpTransport(
                    "http://rag/mcp", auth=token, httpx_client_factory=factory
                )
            ) as client:
                result = await client.call_tool(
                    "mcp_query_project_knowledge", {"query": TEXTS[key]}
                )
                payload = result.structured_content
                assert payload["status"] == "ok" and ids.issubset(
                    {s["document_id"] for s in payload["sources"]}
                ), payload
                assert json.loads(result.content[0].text) == payload
                return [source["document_id"] for source in payload["sources"]]

        async def submit(key, request_id):
            data = TEXTS[key].encode()
            digest = hashlib.sha256(data).hexdigest()
            ref = dict(
                version=1,
                path=f"/workspace/uploads/{digest}.md",
                file_name=f"fixture-{key}.md",
                mime_type="text/markdown",
                size_bytes=len(data),
                sha256=digest,
            )
            clock = int(time.time())
            grant = signed(
                {
                    **scope,
                    **identity,
                    "request_id": request_id,
                    "sha256": digest,
                    "size_bytes": len(data),
                    "file_name": ref["file_name"],
                    "mime_type": ref["mime_type"],
                    "issuer": "platform-api",
                    "audience": "rag-knowledge",
                    "operation": "upload",
                    "iat": clock,
                    "exp": clock + 30,
                    "nonce": os.urandom(16).hex(),
                },
                config,
                grant=True,
            )
            headers = {
                "authorization": "Bearer " + token,
                "x-knowledge-file-ref": json.dumps(ref),
                "x-knowledge-operation-grant": json.dumps(grant),
                "content-type": "text/markdown",
            }
            async with factory(base_url="http://rag") as http:
                response = await http.put(
                    f"/internal/knowledge/uploads/{request_id}",
                    headers=headers,
                    content=data,
                )
                assert response.status_code == 200, response.text
            tool_headers = {
                "x-knowledge-upload-id": response.json()["upload_id"],
                "x-knowledge-operation-grant": json.dumps(grant),
            }
            async with Client(
                StreamableHttpTransport(
                    "http://rag/mcp",
                    auth=token,
                    headers=tool_headers,
                    httpx_client_factory=factory,
                )
            ) as client:
                result = await client.call_tool(
                    "mcp_submit_project_knowledge_document", {"file_ref": ref}
                )
                assert json.loads(result.content[0].text) == result.structured_content
                return result.structured_content

        try:
            async with app.router.lifespan_context(app):
                for key in "AB":
                    accepted = await submit(key, key)
                    assert (
                        accepted["status"] in {"queued", "parsing"}
                        and not accepted["reused"]
                    )
                    deadline = time.monotonic() + 600
                    while time.monotonic() < deadline:
                        receipt = store.receipt(project["id"], accepted["job_id"])
                        if receipt["status"] in {"ready", "failed"}:
                            break
                        await asyncio.sleep(0.5)
                    if receipt["status"] != "ready":
                        with store.connect() as db:
                            failure_usage = [
                                dict(row)
                                for row in db.execute(
                                    "SELECT stage,kind,status,input_count,provider_usage,usage_source FROM usage WHERE job_id=?",
                                    (receipt["job_id"],),
                                )
                            ]
                        failure = {
                            "receipt": receipt,
                            "usage": failure_usage,
                            "builder_errors": re.findall(
                                r"knowledge_builder_failed: (\w+)",
                                (store.path.parent / "builder.log").read_text(),
                            ),
                        }
                        Path(__file__).resolve().parents[1].joinpath(
                            "docs/projects/20261012-project-member-knowledge-upload/implementation/rag-chain-failure.json"
                        ).write_text(json.dumps(failure, ensure_ascii=False, indent=2))
                        raise AssertionError(failure)
                    receipts.append(receipt)
                    namespace = store.project(project["id"])["active_namespace"]
                    namespaces.append(namespace)
                    with store.connect() as db:
                        rows = [
                            dict(row)
                            for row in db.execute(
                                "SELECT stage,kind,status,input_count,provider_usage,usage_source FROM usage WHERE job_id=?",
                                (receipt["job_id"],),
                            )
                        ]
                    counts[key] = {
                        "events": dict(Counter(row["kind"] for row in rows)),
                        "rows": rows,
                    }
                    await query(key, {receipt["document_id"]})
                first_paths = KnowledgeGenerationService(
                    store
                ).engine.get_project_paths(namespaces[0])
                frozen = {
                    p.name: checksum(p) for p in storage_dir(first_paths).iterdir()
                }
                with store.connect() as db:
                    before = db.execute("SELECT count(*) FROM usage").fetchone()[0]
                repeated = await submit("A", "repeat-a")
                assert (
                    repeated["reused"] and repeated["job_id"] == receipts[0]["job_id"]
                )
                with store.connect() as db:
                    assert (
                        before == db.execute("SELECT count(*) FROM usage").fetchone()[0]
                    )
                source_ids = await query(
                    "A", {receipt["document_id"] for receipt in receipts}
                )
                store.enable(project["id"], False)
                generations = KnowledgeGenerationService(store)
                await generations.rollback(project["id"], namespaces[0])
                assert not store.receipt(project["id"], receipts[1]["job_id"])[
                    "searchable"
                ]
                await query("A", {receipts[0]["document_id"]})
                await generations.rollback(project["id"], namespaces[1])
                assert store.receipt(project["id"], receipts[1]["job_id"])["searchable"]
                await generations.close()
                assert frozen == {
                    p.name: checksum(p) for p in storage_dir(first_paths).iterdir()
                }
            return dict(
                platform="local signed authorization stub, not production IAM",
                models="current .env, real HTTP providers",
                processing_signature=signature,
                checks={
                    "http_mcp_queued": True,
                    "real_worker_ready": True,
                    "duplicate_zero_new_usage": True,
                    "mcp_old_and_new_sources": True,
                    "rollback_searchable": True,
                    "published_files_unchanged": True,
                },
                usage=counts,
                receipts=receipts,
                source_ids=source_ids,
                amount=None,
            )
        finally:
            platform.shutdown()
            platform.server_close()
            if previous is None:
                os.environ.pop("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON", None)
            else:
                os.environ["KNOWLEDGE_MCP_TOKEN_SCOPES_JSON"] = previous


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(run())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["checks"], ensure_ascii=False))
