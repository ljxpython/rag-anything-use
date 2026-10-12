import asyncio
import hashlib
import time
from dataclasses import replace

import pytest

from src.knowledge.operation_auth import signed
from src.knowledge.upload_service import KnowledgeUploadService


def fixture(
    s, data=b"# content", request_id="request", name="规范.md", mime="text/markdown"
):
    digest = hashlib.sha256(data).hexdigest()
    ext = "md" if mime == "text/markdown" else "txt"
    ref = dict(
        version=1,
        path=f"/workspace/uploads/{digest}.{ext}",
        file_name=name,
        mime_type=mime,
        size_bytes=len(data),
        sha256=digest,
    )
    grant = s.authorizer.grant(
        s.scope,
        "upload",
        {
            **s.identity,
            "request_id": request_id,
            "sha256": digest,
            "size_bytes": len(data),
        },
    )
    return ref, grant


async def stream(data):
    for i in range(0, len(data), 1024):
        yield data[i : i + 1024]


def test_upload_durable_ticket_idempotency_private_binding(online_services):
    s = online_services
    ref, grant = fixture(s)

    async def run():
        ticket = await s.uploads.stage_upload(
            s.scope, "request", ref, grant, stream(b"# content")
        )
        assert s.store.next_job() is None
        receipt = s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)
        assert receipt["status"] == "queued" and not receipt["searchable"]
        same = s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)
        assert same["job_id"] == receipt["job_id"] and same["reused"]
        assert "original" not in receipt and "subject" not in receipt
        assert (
            list(s.uploads.directory(s.scope.knowledge_base_id, "tmp").iterdir()) == []
        )
        with pytest.raises(ValueError, match="knowledge_authorization_denied"):
            s.uploads.submit_document(s.scope, ticket["upload_id"], ref, {})
        forged = s.authorizer.grant(
            s.scope,
            "upload",
            {
                **s.identity,
                "subject": "another",
                "request_id": "request",
                "sha256": ref["sha256"],
                "size_bytes": ref["size_bytes"],
            },
        )
        with pytest.raises(ValueError, match="knowledge_authorization_denied"):
            s.uploads.submit_document(s.scope, ticket["upload_id"], ref, forged)
        return ticket

    asyncio.run(run())


@pytest.mark.parametrize("data", [b"", b"\xff\xfe", b"\x00abc", b"   "])
def test_invalid_original_never_queues(online_services, data):
    s = online_services
    ref, grant = fixture(s, data)
    with pytest.raises(ValueError):
        asyncio.run(
            s.uploads.stage_upload(s.scope, "request", ref, grant, stream(data))
        )
    assert s.store.next_job() is None
    with s.store.connect() as db:
        assert db.execute("SELECT count(*) FROM uploads").fetchone()[0] == 0


@pytest.mark.parametrize(
    "mutation", ["hash", "path", "mime", "oversize", "name", "signature", "expired"]
)
def test_validation_and_grants_fail_closed(online_services, mutation):
    s = online_services
    ref, grant = fixture(s)
    if mutation == "hash":
        ref["sha256"] = "a" * 64
    elif mutation == "path":
        ref["path"] = "/PRIVATE/secret.md"
    elif mutation == "mime":
        ref["mime_type"] = "application/pdf"
    elif mutation == "oversize":
        ref["size_bytes"] = 20 * 1024**2 + 1
    elif mutation == "name":
        ref["file_name"] = "../secret.md"
    elif mutation == "signature":
        grant["signature"] = "a" * 64
    else:
        grant["values"]["iat"] = time.time() - 60
        grant["values"]["exp"] = time.time() - 30
        grant = signed(grant["values"], s.config, grant=True)
    with pytest.raises(ValueError):
        asyncio.run(
            s.uploads.stage_upload(s.scope, "request", ref, grant, stream(b"# content"))
        )
    assert s.store.next_job() is None


def test_disconnect_expiration_symlink_and_quota(online_services, tmp_path):
    s = online_services
    ref, grant = fixture(s)

    async def interrupted():
        yield b"# con"
        raise ConnectionError("disconnect")

    with pytest.raises(ConnectionError):
        asyncio.run(
            s.uploads.stage_upload(s.scope, "request", ref, grant, interrupted())
        )
    assert s.store.next_job() is None
    ticket = asyncio.run(
        s.uploads.stage_upload(s.scope, "request", ref, grant, stream(b"# content"))
    )
    with s.store.connect(write=True) as db:
        db.execute("UPDATE uploads SET expires_at=0")
    with pytest.raises(ValueError, match="knowledge_upload_expired"):
        s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)
    tiny = replace(s.config, max_disk_bytes=1)
    uploads = KnowledgeUploadService(type(s.store)(tiny), s.authorizer)
    with pytest.raises(ValueError, match="knowledge_quota_exceeded"):
        asyncio.run(
            uploads.stage_upload(
                s.scope, "quota", *fixture(s, b"quota", "quota"), stream(b"quota")
            )
        )
    other_ref, other_grant = fixture(s, b"other", "other")
    target = (
        s.uploads.directory(s.scope.knowledge_base_id, "originals")
        / other_ref["sha256"]
    )
    target.symlink_to(tmp_path / "outside.md")
    with pytest.raises(ValueError, match="knowledge_path_escape"):
        asyncio.run(
            s.uploads.stage_upload(
                s.scope, "other", other_ref, other_grant, stream(b"other")
            )
        )


def test_size_boundary_and_actual_content_hash(online_services):
    s = online_services
    s.uploads.config = replace(s.config, max_file_bytes=9)
    ref, grant = fixture(s, b"123456789")
    ticket = asyncio.run(
        s.uploads.stage_upload(s.scope, "request", ref, grant, stream(b"123456789"))
    )
    assert ticket["upload_id"].startswith("ku_")
    ref2, grant2 = fixture(s, b"0123456789", "ten")
    with pytest.raises(ValueError, match="knowledge_file_too_large"):
        asyncio.run(
            s.uploads.stage_upload(s.scope, "ten", ref2, grant2, stream(b"0123456789"))
        )
    ref3, grant3 = fixture(s, b"different", "mismatch")
    with pytest.raises(ValueError, match="knowledge_content_conflict"):
        asyncio.run(
            s.uploads.stage_upload(
                s.scope, "mismatch", ref3, grant3, stream(b"DIFFERENT")
            )
        )


def test_same_bytes_different_text_extensions_share_original_and_job(online_services):
    s = online_services

    async def run():
        receipts = []
        for request_id, name, mime in (
            ("md", "doc.md", "text/markdown"),
            ("txt", "doc.txt", "text/plain"),
        ):
            ref, grant = fixture(s, b"same original", request_id, name, mime)
            ticket = await s.uploads.stage_upload(
                s.scope, request_id, ref, grant, stream(b"same original")
            )
            receipts.append(
                s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)
            )
        assert receipts[0]["document_id"] == receipts[1]["document_id"]
        assert receipts[0]["job_id"] == receipts[1]["job_id"] and receipts[1]["reused"]
        assert (
            len(
                list(
                    s.uploads.directory(
                        s.scope.knowledge_base_id, "originals"
                    ).iterdir()
                )
            )
            == 1
        )

    asyncio.run(run())
