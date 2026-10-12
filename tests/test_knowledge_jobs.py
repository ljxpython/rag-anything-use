import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from src.knowledge.jobs import KnowledgeJobStore, now


def ref(text="hello", name="规范.md"):
    data = text.encode()
    digest = hashlib.sha256(data).hexdigest()
    return dict(
        version=1,
        path=f"/workspace/uploads/{digest}.md",
        file_name=name,
        mime_type="text/markdown",
        size_bytes=len(data),
        sha256=digest,
    )


def test_concurrent_dedup_replay_attempts_and_scopes(published_config):
    store = KnowledgeJobStore(published_config)
    kb = store.register("__default", "p1", "signature", enabled=True)["id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(
            pool.map(
                lambda i: store.submit(
                    kb,
                    f"r{i}",
                    {"subject": str(i)},
                    ref(),
                    "/managed/original",
                    "signature",
                ),
                range(8),
            )
        )
    assert len({r["job_id"] for r in receipts}) == 1
    assert len({r["document_id"] for r in receipts}) == 1
    assert sum(not r["reused"] for r in receipts) == 1
    first = next(i for i, r in enumerate(receipts) if not r["reused"])
    job_id = receipts[0]["job_id"]
    original = store.get_job(job_id)
    store.update_job(job_id, "failed", "knowledge_processing_failed")
    replay = store.submit(
        kb,
        f"r{first}",
        {"subject": str(first)},
        ref(),
        "/managed/original",
        "signature",
    )
    assert replay["status"] == "failed" and replay["reused"]
    retry = store.submit(
        kb,
        "retry",
        {"subject": "new-member"},
        ref(name="改名.md"),
        "/managed/original",
        "signature",
    )
    assert (
        retry["document_id"] == receipts[0]["document_id"] and retry["job_id"] != job_id
    )
    assert (
        retry["file_name"] == "规范.md"
        and store.get_job(job_id)["identity"] == original["identity"]
    )
    with pytest.raises(ValueError, match="knowledge_content_conflict"):
        store.submit(kb, f"r{first}", {"subject": "forged"}, ref(), "x", "signature")
    with pytest.raises(ValueError, match="knowledge_processing_config_changed"):
        store.submit(kb, "config", {}, ref(), "x", "changed")
    with pytest.raises(ValueError, match="knowledge_content_conflict"):
        store.submit(kb, "size", {}, {**ref(), "size_bytes": 100}, "x", "signature")
    second = store.register("__default", "p2", "signature", enabled=True)["id"]
    independent = store.submit(second, "r0", {}, ref(), "x", "signature")
    assert independent["document_id"] != retry["document_id"]
    with pytest.raises(ValueError, match="knowledge_not_found"):
        store.receipt(second, retry["job_id"])


def test_migrated_ready_null_and_rollback_projection(published_config):
    store = KnowledgeJobStore(published_config)
    kb = store.register("t", "p", "sig", enabled=True)["id"]
    with store.connect(write=True) as db:
        db.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "kd_" + "a" * 32,
                kb,
                ref()["sha256"],
                ref()["size_bytes"],
                "旧规范.md",
                "text/markdown",
                "x",
                "sig",
                now(),
            ),
        )
        db.execute(
            "INSERT INTO generations VALUES(?,?,?,?,?,?)",
            ("old", kb, "sig", 0, json.dumps(["kd_" + "a" * 32]), now()),
        )
        db.execute(
            "UPDATE projects SET active_namespace='old',revision=1 WHERE id=?", (kb,)
        )
    result = store.submit(kb, "repeat", {}, ref(), "x", "sig")
    assert (
        result["job_id"] is None
        and result["status"] == "ready"
        and result["searchable"]
        and result["reused"]
    )
    assert store.list_documents(kb)["total"] == 1 and store.list_jobs(kb)["total"] == 0
    with store.connect(write=True) as db:
        db.execute(
            "UPDATE projects SET active_namespace=NULL,enabled=0 WHERE id=?", (kb,)
        )
    assert not store.receipt(kb, document_id=result["document_id"])["searchable"]
    with pytest.raises(ValueError, match="knowledge_rollback_upload_disabled"):
        store.enable(kb, True)


def test_limits_transaction_rollback_and_restart(published_config):
    config = replace(published_config, max_jobs=1)
    store = KnowledgeJobStore(config)
    kb = store.register("t", "p", "sig", enabled=True)["id"]
    queued = store.submit(kb, "a", {}, ref(), "x", "sig")
    with pytest.raises(ValueError, match="knowledge_queue_full"):
        store.submit(kb, "b", {}, ref("different"), "x", "sig")
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 1
    assert store.submit(kb, "dup", {}, ref(), "x", "sig")["reused"]
    store.recover()
    assert store.get_job(queued["job_id"])["status"] == "queued"
    for attempt in (1, 2, 3):
        job = (
            queued
            if attempt == 1
            else store.submit(kb, f"retry{attempt}", {}, ref(), "x", "sig")
        )
        store.update_job(job["job_id"], "parsing")
        store = KnowledgeJobStore(config)
        store.recover()
        assert (
            store.get_job(job["job_id"])["error_code"]
            == "knowledge_processing_interrupted"
        )
    with pytest.raises(ValueError, match="knowledge_retry_limit"):
        store.submit(kb, "retry4", {}, ref(), "x", "sig")
