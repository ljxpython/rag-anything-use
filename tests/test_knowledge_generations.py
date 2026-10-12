import asyncio
import json

import pytest

from src.knowledge.artifacts import checksum
from src.knowledge.generations import storage_dir, validate_snapshot
import hashlib


async def upload(services, text, request_id):
    data = text.encode()
    digest = hashlib.sha256(data).hexdigest()
    ref = dict(
        version=1,
        path=f"/workspace/uploads/{digest}.md",
        file_name="同名.md",
        mime_type="text/markdown",
        size_bytes=len(data),
        sha256=digest,
    )
    grant = services.authorizer.grant(
        services.scope,
        "upload",
        {
            **services.identity,
            "request_id": request_id,
            "sha256": digest,
            "size_bytes": len(data),
            "file_name": ref["file_name"],
            "mime_type": ref["mime_type"],
        },
    )

    async def stream():
        yield data

    ticket = await services.uploads.stage_upload(
        services.scope, request_id, ref, grant, stream()
    )
    return services.uploads.submit_document(
        services.scope, ticket["upload_id"], ref, grant
    )


def test_snapshots_increment_only_new_document_and_lease_rollback(online_services):
    from scripts.verify_incremental_snapshot import TEXTS

    s = online_services

    async def run():
        try:
            first = await upload(s, TEXTS["A"], "a")
            s.calls.phase = "A"
            ns_a = await s.generations.build(first["job_id"])
            await s.generations.activate(first["job_id"])
            first_paths = s.generations.engine.get_project_paths(ns_a)
            frozen = {p.name: checksum(p) for p in storage_dir(first_paths).iterdir()}
            before = len(s.calls.rows)
            duplicate = await upload(s, TEXTS["A"], "rename")
            assert duplicate["reused"] and duplicate["job_id"] == first["job_id"]
            assert before == len(s.calls.rows)
            held = s.generations.acquire(s.scope.knowledge_base_id)
            reader, view = await held.__aenter__()
            assert view == ns_a
            second = await upload(s, TEXTS["B"], "b")
            s.calls.phase = "B"
            ns_b = await s.generations.build(second["job_id"])
            assert (
                s.store.receipt(s.scope.knowledge_base_id, second["job_id"])[
                    "searchable"
                ]
                is False
            )
            await s.generations.activate(second["job_id"])
            assert len(s.generations._readers) == 2
            assert (
                len(
                    validate_snapshot(
                        s.generations.engine.get_project_paths(ns_b), s.signature
                    )
                )
                == 2
            )
            assert frozen == {
                p.name: checksum(p) for p in storage_dir(first_paths).iterdir()
            }
            # The held old view keeps its manifest even after activation.
            assert (
                len(
                    KnowledgeDocumentRegistry(
                        reader.get_project_paths(view)
                    ).list_documents()
                )
                == 1
            )
            await held.__aexit__(None, None, None)
            assert set(s.generations._readers) == {ns_b}
            with pytest.raises(ValueError, match="knowledge_rollback_upload_disabled"):
                await s.generations.rollback(s.scope.knowledge_base_id, ns_a)
            s.store.enable(s.scope.knowledge_base_id, False)
            await s.generations.rollback(s.scope.knowledge_base_id, ns_a)
            assert (
                s.store.receipt(s.scope.knowledge_base_id, second["job_id"])["status"]
                == "ready"
            )
            assert not s.store.receipt(s.scope.knowledge_base_id, second["job_id"])[
                "searchable"
            ]
            with pytest.raises(ValueError, match="knowledge_rollback_upload_disabled"):
                s.store.enable(s.scope.knowledge_base_id, True)
            await s.generations.rollback(s.scope.knowledge_base_id, ns_b)
            s.store.enable(s.scope.knowledge_base_id, True)
            assert s.store.list_documents(s.scope.knowledge_base_id)["total"] == 2
        finally:
            await s.generations.close()

    from src.knowledge.document_registry import KnowledgeDocumentRegistry

    asyncio.run(run())
    assert s.calls.report()["B"]["unchanged_prior_inputs"] == 0


def test_failure_revocation_base_change_and_corruption_keep_active(online_services):
    from scripts.verify_incremental_snapshot import TEXTS

    s = online_services

    async def run():
        try:
            first = await upload(s, TEXTS["A"], "a")
            ns_a = await s.generations.build(first["job_id"])
            await s.generations.activate(first["job_id"])
            second = await upload(s, TEXTS["B"], "b")
            ns_b = await s.generations.build(second["job_id"])
            s.authorizer.denied = True
            with pytest.raises(ValueError, match="knowledge_authorization_denied"):
                await s.generations.activate(second["job_id"])
            assert (
                s.store.project(s.scope.knowledge_base_id)["active_namespace"] == ns_a
            )
            assert not s.store.receipt(s.scope.knowledge_base_id, second["job_id"])[
                "searchable"
            ]
            s.authorizer.denied = False
            with s.store.connect(write=True) as db:
                db.execute(
                    "UPDATE projects SET revision=revision+1 WHERE id=?",
                    (s.scope.knowledge_base_id,),
                )
            with pytest.raises(ValueError, match="knowledge_base_changed"):
                await s.generations.activate(second["job_id"])
            paths = s.generations.engine.get_project_paths(ns_b)
            (storage_dir(paths) / "vdb_chunks.json").write_text("corrupt")
            with pytest.raises(ValueError, match="knowledge_snapshot_invalid"):
                validate_snapshot(paths, s.signature)
            assert s.store.list_documents(s.scope.knowledge_base_id)["total"] == 1
        finally:
            await s.generations.close()

    asyncio.run(run())


@pytest.mark.parametrize("cancel_restore", [False, True])
def test_restoring_candidate_does_not_block_existing_reader(
    online_services, monkeypatch, cancel_restore
):
    import threading
    from src.knowledge import generations as module

    s = online_services
    copying, release = threading.Event(), threading.Event()
    original = module.copy_storage

    def paused_copy(source, target):
        copying.set()
        assert release.wait(5)
        return original(source, target)

    async def run():
        preparing = None
        try:
            first = await upload(s, "First Orion document", "a")
            old = await s.generations.build(first["job_id"])
            await s.generations.activate(first["job_id"])
            second = await upload(s, "Second Orion document", "b")
            candidate = await s.generations.build(second["job_id"])
            monkeypatch.setattr(module, "copy_storage", paused_copy)
            preparing = asyncio.create_task(
                s.generations.prepare(candidate, s.signature)
            )
            assert await asyncio.to_thread(copying.wait, 5)
            async with asyncio.timeout(0.5):
                async with s.generations.acquire(s.scope.knowledge_base_id) as (
                    _,
                    view,
                ):
                    assert view == old
            if cancel_restore:
                preparing.cancel()
                await asyncio.sleep(0.05)
                assert not preparing.done()
            release.set()
            if cancel_restore:
                with pytest.raises(asyncio.CancelledError):
                    await preparing
            else:
                await preparing
        finally:
            release.set()
            if preparing:
                await asyncio.gather(preparing, return_exceptions=True)
            await s.generations.close()

    asyncio.run(run())


def test_continuous_generations_release_global_data_and_source_ids(online_services):
    from lightrag.kg import shared_storage
    from src.knowledge.rag_engine import storage_workspace
    from scripts.verify_incremental_snapshot import TEXTS

    s = online_services

    async def run():
        workspaces = []
        try:
            for index in range(10):
                text = TEXTS["ABCD"[index % 4]] + f"\nRevision fixture {index}."
                receipt = await upload(s, text, str(index))
                namespace = await s.generations.build(receipt["job_id"])
                assert not any(
                    name.startswith(
                        storage_workspace(
                            s.generations.engine.get_project_paths(namespace)
                        )
                        + ":"
                    )
                    for name in shared_storage._shared_dicts
                )
                await s.generations.activate(receipt["job_id"])
                async with s.generations.acquire(s.scope.knowledge_base_id) as (
                    reader,
                    view,
                ):
                    workspaces.append(storage_workspace(reader.get_project_paths(view)))
                    assert len(
                        KnowledgeDocumentRegistry(
                            reader.get_project_paths(view)
                        ).list_documents()
                    ) == len(workspaces)
                assert len(s.generations._readers) == 1
                for previous in workspaces[:-1]:
                    assert not any(
                        name.startswith(previous + ":")
                        for name in shared_storage._shared_dicts
                    )
                    assert not any(
                        name.startswith(previous + ":")
                        for name in shared_storage._storage_keyed_lock._async_lock
                    )
        finally:
            await s.generations.close()
        for workspace in workspaces:
            assert not any(
                name.startswith(workspace + ":")
                for name in shared_storage._shared_dicts
            )

    from src.knowledge.document_registry import KnowledgeDocumentRegistry

    asyncio.run(run())


def test_different_bytes_with_identical_normalized_text_keep_both_sources(
    online_services,
):
    s = online_services

    async def run():
        try:
            for i, text in enumerate(("Orion 服务说明。", "  Orion 服务说明。\n")):
                receipt = await upload(s, text, str(i))
                namespace = await s.generations.build(receipt["job_id"])
                await s.generations.activate(receipt["job_id"])
            records = validate_snapshot(
                s.generations.engine.get_project_paths(namespace), s.signature
            )
            assert len(records) == 2
            chunks = json.loads(
                (
                    storage_dir(s.generations.engine.get_project_paths(namespace))
                    / "kv_store_text_chunks.json"
                ).read_text()
            )
            assert {chunk["file_path"] for chunk in chunks.values()} == {
                r.document_id for r in records
            }
        finally:
            await s.generations.close()

    asyncio.run(run())
