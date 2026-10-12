"""Actual Platform API HTTP and RAG worker/MCP with isolated IAM/Run data."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import socket
import sys
import tempfile
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from scripts.verify_incremental_snapshot import TEXTS
from src.demo_support import load_settings
from src.knowledge.artifacts import checksum, processing_signature
from src.knowledge.auth import KnowledgeScope
from src.knowledge.config import build_knowledge_service_config
from src.knowledge.generations import KnowledgeGenerationService, storage_dir
from src.knowledge.jobs import KnowledgeJobStore
from src.knowledge.operation_auth import (
    KnowledgeOperationAuthorizer,
    canonical,
    operation_identity,
    signed,
)
from src.mcp_server import create_server

# This imports the platform's existing SQL/IAM fixture; no live platform settings change.
PLATFORM_FIXTURE = r"""
import json, os, socket, sys, threading
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID
import uvicorn
sys.path.insert(0, str(Path.cwd()))
import platform_api.main
from tests.test_knowledge_authorization import KnowledgeAuthorizationTest
from tests import test_knowledge_member_upload as fixtures
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import ThreadAccessRecord

directory = Path(sys.argv[1])
fixtures.TemporaryDirectory = lambda: TemporaryDirectory(dir=directory, prefix="iam-")
case = KnowledgeAuthorizationTest()
case.setUp()
case.settings.knowledge_secret = os.urandom(32).hex()

def controls():
    for line in sys.stdin:
        command = json.loads(line)["command"]
        with case.factory.begin() as db:
            if command == "delete_thread":
                db.delete(db.get(ThreadAccessRecord, case.thread))
            elif command == "restore_thread":
                db.add(ThreadAccessRecord(thread_id=case.thread, project_id=case.project,
                    owner_user_id=case.users["executor"], visibility="private"))
            elif command == "revoke":
                db.query(ProjectMemberRecord).filter_by(project_id=UUID(case.project),
                    user_id=UUID(case.users["executor"])).delete()
            elif command == "restore_member":
                db.add(ProjectMemberRecord(project_id=UUID(case.project),
                    user_id=UUID(case.users["executor"]), role="executor"))
            else:
                raise ValueError("unknown fixture command")
        print(json.dumps({"command": command, "done": True}), flush=True)

async def observed(scope, receive, send):
    body = bytearray()
    async def receiving():
        message = await receive()
        if scope.get("path") == "/api/runtime/internal/knowledge/authorize":
            body.extend(message.get("body", b""))
        return message
    async def sending(message):
        if message["type"] == "http.response.start" and body:
            values = json.loads(body)["values"]
            event = {"operation": values.get("operation"), "status": message["status"],
                "issuer": values.get("issuer"), "fields": sorted(values),
                "job_id": values.get("job_id")}
            with (directory / "authorization-events.jsonl").open("a") as log:
                log.write(json.dumps(event) + "\n")
        await send(message)
    await case.app(scope, receiving, sending)

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(128)
info = {"url": f"http://127.0.0.1:{listener.getsockname()[1]}",
    "key_id": case.settings.knowledge_key_id, "secret": case.settings.knowledge_secret,
    "upload_values": case.values(), "kb": case.settings.knowledge_connections["knowledge"].knowledge_base_id}
with os.fdopen(os.open(directory / "platform-private.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
    json.dump(info, handle)
threading.Thread(target=controls, daemon=True).start()
try:
    uvicorn.Server(uvicorn.Config(observed, lifespan="off", log_level="warning")).run(sockets=[listener])
finally:
    listener.close()
    case.doCleanups()
"""


def request_values(info, key, data):
    clock = int(time.time())
    values = {
        **info["upload_values"],
        "tool_call_id": "contract-" + key,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "file_name": "fixture-" + key + ".md",
        "mime_type": "text/markdown",
        "iat": clock,
        "exp": clock + 30,
        "nonce": uuid4().hex,
    }
    origin = [
        values[k]
        for k in ("tenant_id", "project_id", "thread_id", "run_id", "tool_call_id")
    ]
    values["request_id"] = (
        "kr_" + hashlib.sha256(canonical(origin).encode()).hexdigest()[:32]
    )
    return values


async def verify(info, directory, process, report, authorization_only=False):
    config = replace(
        build_knowledge_service_config(),
        root_dir=directory / "corpus",
        online_enabled=True,
        authorize_url=info["url"] + "/api/runtime/internal/knowledge/authorize",
        authorization_key_id=info["key_id"],
        authorization_secret=info["secret"],
    )
    store = KnowledgeJobStore(config)
    signature = processing_signature(config)
    project = store.register(
        info["upload_values"]["tenant_id"],
        info["upload_values"]["project_id"],
        signature,
        enabled=True,
    )
    # Only the empty verification DB adopts the fixture's configured KB identifier.
    with store.connect(write=True) as db:
        db.execute("UPDATE projects SET id=? WHERE id=?", (info["kb"], project["id"]))
    scope = KnowledgeScope(
        tenant_id=project["tenant_id"],
        project_id=project["project_id"],
        knowledge_base_id=info["kb"],
    )
    authorizer = KnowledgeOperationAuthorizer(config)
    token = os.urandom(32).hex()
    previous = os.environ.get("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON")
    os.environ["KNOWLEDGE_MCP_TOKEN_SCOPES_JSON"] = json.dumps(
        {token: scope.model_dump(exclude_none=True)}
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(create_server(config).http_app(), log_level="warning")
    )
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    receipts, namespaces, counts = [], [], {}
    report.update(
        {
            "platform": "actual Platform API HTTP, isolated SQL/IAM/Run fixture",
            "rag": "actual HTTP/MCP/supervisor and real model providers",
            "models": {
                "llm": load_settings().llm_model,
                "embedding": load_settings().embedding_model,
                "dimensions": load_settings().embedding_dim,
            },
            "checks": {},
        }
    )

    async def control(command):
        process.stdin.write((json.dumps({"command": command}) + "\n").encode())
        await process.stdin.drain()
        response = json.loads(await asyncio.wait_for(process.stdout.readline(), 10))
        assert response == {"command": command, "done": True}

    async def upload_grant(http, values):
        clock = int(time.time())
        values = {**values, "iat": clock, "exp": clock + 30, "nonce": uuid4().hex}
        response = await http.post(config.authorize_url, json=signed(values, config))
        assert response.status_code == 200, "Platform upload grant rejected"
        return response.json()

    async def submit(http, key):
        data = TEXTS[key].encode()
        values = request_values(info, key, data)
        grant = await upload_grant(http, values)
        ref = {
            "version": 1,
            "path": f"/workspace/uploads/{values['sha256']}.md",
            **{
                k: values[k] for k in ("sha256", "size_bytes", "file_name", "mime_type")
            },
        }
        path = origin + "/internal/knowledge/uploads/" + values["request_id"]
        headers = {
            "Authorization": "Bearer " + token,
            "X-Knowledge-Operation-Grant": canonical(grant),
        }
        before = await http.get(path, headers=headers)
        assert before.status_code == 200 and before.json()["receipt"] is None
        response = await http.put(
            path,
            headers={
                **headers,
                "X-Knowledge-File-Ref": canonical(ref),
                "Content-Type": ref["mime_type"],
            },
            content=data,
        )
        assert response.status_code == 200, "Original-byte PUT rejected"
        assert (await http.get(path, headers=headers)).json()["receipt"] is None
        grant = await upload_grant(http, values)
        async with Client(
            StreamableHttpTransport(
                origin + "/mcp",
                auth=token,
                headers={
                    "X-Knowledge-Upload-ID": response.json()["upload_id"],
                    "X-Knowledge-Operation-Grant": canonical(grant),
                },
            )
        ) as client:
            result = await client.call_tool(
                "mcp_submit_project_knowledge_document", {"file_ref": ref}
            )
            receipt = result.structured_content
            assert receipt == json.loads(result.content[0].text)
            assert receipt["status"] == "queued" and not receipt["reused"]
        await lookup(http, values, receipt)
        return values, receipt

    async def lookup(http, values, receipt):
        grant = await upload_grant(http, values)
        headers = {
            "Authorization": "Bearer " + token,
            "X-Knowledge-Operation-Grant": canonical(grant),
        }
        before = usage_count()
        job_before = store.get_job(receipt["job_id"])
        response = await http.get(
            origin + "/internal/knowledge/uploads/" + values["request_id"],
            headers=headers,
        )
        assert response.status_code == 200, "Lost-ACK GET rejected"
        payload = response.json()
        assert payload["request_id"] == values["request_id"]
        assert (
            payload["receipt"]["job_id"] == receipt["job_id"]
            and payload["receipt"]["reused"]
        )
        assert set(payload["receipt"]) == set(receipt) | {"reused"}
        assert "upload_id" not in response.text and "subject" not in response.text
        assert usage_count() == before
        assert store.get_job(receipt["job_id"])["attempt"] == job_before["attempt"]
        for field in ("subject", "sha256", "file_name"):
            changed = {**grant["values"], field: "changed"}
            denied = await http.get(
                origin + "/internal/knowledge/uploads/" + values["request_id"],
                headers={
                    "Authorization": "Bearer " + token,
                    "X-Knowledge-Operation-Grant": canonical(
                        signed(changed, config, grant=True)
                    ),
                },
            )
            assert (
                denied.status_code in (401, 403)
                and receipt["job_id"] not in denied.text
            )

    def usage_count():
        with store.connect() as db:
            return db.execute("SELECT count(*) FROM usage").fetchone()[0]

    async def wait_job(receipt, status):
        async with asyncio.timeout(240):
            while True:
                current = store.receipt(scope.knowledge_base_id, receipt["job_id"])
                if current["status"] == status:
                    return current
                assert current["status"] != "failed", "Real builder failed"
                await asyncio.sleep(0.2)

    async def query(ids):
        async with Client(
            StreamableHttpTransport(origin + "/mcp", auth=token)
        ) as client:
            result = await client.call_tool(
                "mcp_query_project_knowledge", {"query": TEXTS["A"]}
            )
            assert result.structured_content == json.loads(result.content[0].text)
            assert ids.issubset(
                {
                    source["document_id"]
                    for source in result.structured_content["sources"]
                }
            )

    try:
        async with asyncio.timeout(30):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("RAG HTTP startup failed")
                await asyncio.sleep(0.1)
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as http:
            async with asyncio.timeout(30):
                while True:
                    try:
                        await http.get(info["url"] + "/health")
                        break
                    except httpx.ConnectError:
                        await asyncio.sleep(0.1)
            baseline = request_values(info, "baseline", b"baseline")
            grant = await upload_grant(http, baseline)
            identity = operation_identity(grant["values"])
            for operation in ("start", "activate"):
                expected = {"job_id": "kj_" + "1" * 32}
                if operation == "activate":
                    expected.update(target_revision="kg_" + "1" * 32, base_revision=0)
                await authorizer.authorize(scope, operation, identity, expected)
                clock = int(time.time())
                backend = {
                    **identity,
                    **expected,
                    "issuer": "rag-anything-use",
                    "audience": "platform-api",
                    "operation": operation,
                    "tenant_id": scope.tenant_id,
                    "project_id": scope.project_id,
                    "knowledge_base_id": scope.knowledge_base_id,
                    "iat": clock,
                    "exp": clock + 30,
                    "nonce": uuid4().hex,
                }
                tampered = signed(dict(backend), config)
                tampered["values"]["file_name"] = "tampered.md"
                assert (
                    await http.post(config.authorize_url, json=tampered)
                ).status_code == 403
                expired = {**backend, "iat": clock - 60, "exp": clock - 30}
                assert (
                    await http.post(config.authorize_url, json=signed(expired, config))
                ).status_code == 403
                wrong_owner = {**backend, "subject": str(uuid4())}
                assert (
                    await http.post(
                        config.authorize_url, json=signed(wrong_owner, config)
                    )
                ).status_code in (403, 404)
            tampered = signed(baseline, config)
            tampered["values"]["file_name"] = "tampered.md"
            assert (
                await http.post(config.authorize_url, json=tampered)
            ).status_code == 403
            expired = {
                **baseline,
                "iat": int(time.time()) - 60,
                "exp": int(time.time()) - 30,
            }
            assert (
                await http.post(config.authorize_url, json=signed(expired, config))
            ).status_code == 403
            report["checks"]["actual_platform_start_activate_and_invalid_requests"] = (
                True
            )
            if authorization_only:
                report["rag"] = "actual RAG authorizer; no parser/model calls"
                report["authorization_events"] = [
                    json.loads(line)
                    for line in (directory / "authorization-events.jsonl")
                    .read_text()
                    .splitlines()
                ]
                return report

            with (store.path.parent / ".builder.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                values_a, accepted = await submit(http, "A")
            ready = await wait_job(accepted, "ready")
            receipts.append(ready)
            namespaces.append(
                store.project(scope.knowledge_base_id)["active_namespace"]
            )
            paths = KnowledgeGenerationService(store).engine.get_project_paths(
                namespaces[0]
            )
            frozen = {
                file.name: checksum(file) for file in storage_dir(paths).iterdir()
            }
            await query({ready["document_id"]})

            with (store.path.parent / ".builder.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                values_b, accepted = await submit(http, "B")
                await control("delete_thread")
            ready = await wait_job(accepted, "ready")
            receipts.append(ready)
            namespaces.append(
                store.project(scope.knowledge_base_id)["active_namespace"]
            )
            await control("restore_thread")
            report["checks"]["accepted_job_survives_thread_deletion"] = True
            await query({receipt["document_id"] for receipt in receipts})
            assert frozen == {
                file.name: checksum(file) for file in storage_dir(paths).iterdir()
            }

            store.enable(scope.knowledge_base_id, False)
            await lookup(http, values_a, receipts[0])
            await lookup(http, values_b, receipts[1])
            report["checks"]["lost_ack_read_only_after_write_pause"] = True
            store.enable(scope.knowledge_base_id, True)

            with (store.path.parent / ".builder.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                _, accepted = await submit(http, "C")
                await control("revoke")
            failed = await wait_job(accepted, "failed")
            assert failed["error_code"] == "knowledge_authorization_denied"
            for operation in ("start", "activate"):
                expected = {"job_id": receipts[1]["job_id"]}
                if operation == "activate":
                    expected.update(target_revision=namespaces[1], base_revision=1)
                try:
                    await authorizer.authorize(scope, operation, identity, expected)
                except ValueError as error:
                    assert str(error) == "knowledge_authorization_denied"
                else:
                    raise AssertionError("Revoked member authorized")
            await control("restore_member")
            await query({receipt["document_id"] for receipt in receipts})
            with store.connect() as db:
                assert (
                    db.execute(
                        "SELECT count(*) FROM usage WHERE job_id=?", (failed["job_id"],)
                    ).fetchone()[0]
                    == 0
                )
                for receipt in receipts:
                    rows = [
                        dict(row)
                        for row in db.execute(
                            "SELECT kind,stage,status,input_count FROM usage WHERE job_id=?",
                            (receipt["job_id"],),
                        )
                    ]
                    counts[receipt["job_id"]] = dict(
                        Counter(row["kind"] for row in rows)
                    )
            events = [
                json.loads(line)
                for line in (directory / "authorization-events.jsonl")
                .read_text()
                .splitlines()
            ]
            for receipt in receipts:
                for operation in ("start", "activate"):
                    assert any(
                        event["operation"] == operation
                        and event["job_id"] == receipt["job_id"]
                        and event["status"] == 200
                        for event in events
                    )
            report["checks"].update(
                real_worker_ready_and_old_new_mcp_sources=True,
                revoked_job_no_model_calls=True,
                revoked_start_activate_denied=True,
                published_snapshot_unchanged=True,
            )
            report.update(
                receipts=receipts,
                revoked_receipt=failed,
                usage=counts,
                authorization_events=events,
            )
            report["limitations"] = [
                "synthetic isolated SQL/IAM/Run fixture; no production IAM or Runtime Agent/browser E2E",
                "MD/TXT only; no Linux, PDF/Office, or representative load acceptance",
                "external model fees have no exactly-once guarantee",
            ]
            return report
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 20)
        listener.close()
        if previous is None:
            os.environ.pop("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON", None)
        else:
            os.environ["KNOWLEDGE_MCP_TOKEN_SCOPES_JSON"] = previous


async def run(platform_root, report, authorization_only=False):
    evidence = platform_root / ".local-stack" / "evidence"
    assert evidence.is_dir(), "Initialize the target platform worktree first"
    with tempfile.TemporaryDirectory(dir=evidence, prefix="rag-contract-") as temporary:
        directory = Path(temporary)
        with (directory / "platform-fixture.log").open("w") as log:
            fixture = (
                "import json, sys, traceback\nfrom pathlib import Path\ntry:\n"
                + "    exec("
                + repr(PLATFORM_FIXTURE)
                + ")\n"
                + "except BaseException as error:\n"
                + "    Path(sys.argv[1], 'platform-error.json').write_text(json.dumps({"
                + "'type': type(error).__name__, 'frames': [{"
                + "'file': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno"
                + "} for frame in traceback.extract_tb(error.__traceback__)]}))\n"
                + "    raise\n"
            )
            process = await asyncio.create_subprocess_exec(
                str(platform_root / "apps/platform-api/.venv/bin/python"),
                "-c",
                fixture,
                str(directory),
                cwd=platform_root / "apps/platform-api",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=log,
            )
            try:
                info_path = directory / "platform-private.json"
                async with asyncio.timeout(30):
                    while not info_path.exists():
                        if process.returncode is not None:
                            diagnostic = directory / "platform-error.json"
                            if diagnostic.exists():
                                print(diagnostic.read_text())
                            raise RuntimeError("Platform fixture exited")
                        await asyncio.sleep(0.1)
                return await verify(
                    json.loads(info_path.read_text()),
                    directory,
                    process,
                    report,
                    authorization_only,
                )
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), 15)
                    except TimeoutError:
                        process.kill()
                        await process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization-only", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    result = {}
    try:
        result = asyncio.run(
            run(args.platform_root.resolve(), result, args.authorization_only)
        )
    except BaseException as error:
        result.update(passed=False, exception_type=type(error).__name__)
        args.output.with_suffix(".failure.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
        raise
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"checks": result["checks"], "duration_seconds": result["duration_seconds"]}
        )
    )
