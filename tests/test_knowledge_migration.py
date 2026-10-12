import asyncio

import pytest

from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.ingest_service import KnowledgeIngestService
from src.knowledge.generations import flush_storages, seal_snapshot
from src.knowledge.project_admin import KnowledgeProjectAdmin
from src.knowledge.rag_engine import ProjectRAGEngine


def test_migration_preserves_ids_ready_null_receipt_and_no_models(
    online_services, tmp_path
):
    s = online_services
    original = tmp_path / "legacy.md"
    original.write_text("Legacy Orion service uses POST.")

    async def run():
        engine = ProjectRAGEngine(s.config)
        result = await KnowledgeIngestService(rag_engine=engine).ingest_document(
            project_id="legacy", file_path=str(original)
        )
        assert result.accepted
        await flush_storages(await engine.get_lightrag("legacy"))
        await engine.close()
        seal_snapshot(engine.get_project_paths("legacy"), s.signature)
        s.store.enable(s.scope.knowledge_base_id, False)
        admin = KnowledgeProjectAdmin(s.store, s.generations)
        before = len(s.calls.rows)
        migration = await admin.migrate(
            s.scope.knowledge_base_id, "legacy", s.signature
        )
        assert migration["model_requests"] == 0 and before == len(s.calls.rows)
        docs = s.store.list_documents(s.scope.knowledge_base_id)
        assert docs["items"][0]["document_id"] == result.document_id
        s.store.enable(s.scope.knowledge_base_id, True)
        from test_knowledge_generations import upload

        receipt = await upload(s, original.read_text(), "repeat")
        assert (
            receipt["job_id"] is None
            and receipt["status"] == "ready"
            and receipt["searchable"]
            and receipt["reused"]
        )
        assert len(s.calls.rows) == before
        from test_knowledge_upload import fixture

        _, grant = fixture(s, original.read_bytes(), "repeat", "同名.md")
        lookup = s.uploads.lookup_request(s.scope, "repeat", grant)
        assert lookup["receipt"] == receipt and lookup["receipt"]["job_id"] is None
        assert len(s.calls.rows) == before
        await s.generations.close()

    asyncio.run(run())


def test_missing_original_migration_keeps_legacy_and_upload_disabled(online_services):
    s = online_services
    from src.knowledge.publication import model_signature
    import json

    (
        s.generations.engine.get_project_paths("alpha").manifest_dir
        / "publication.json"
    ).write_text(json.dumps(model_signature()))
    s.store.enable(s.scope.knowledge_base_id, False)

    async def run():
        with pytest.raises(ValueError, match="knowledge_migration_original_missing"):
            await KnowledgeProjectAdmin(s.store, s.generations).migrate(
                s.scope.knowledge_base_id, "alpha", s.signature
            )
        assert s.store.project(s.scope.knowledge_base_id)["active_namespace"] is None
        assert not s.store.project(s.scope.knowledge_base_id)["enabled"]
        assert (
            KnowledgeDocumentRegistry(s.generations.engine.get_project_paths("alpha"))
            .list_documents()[0]
            .overall_status
            == "ready"
        )

    asyncio.run(run())


def test_migration_requires_frozen_legacy_service(online_services):
    from src.knowledge.publication import namespace_lock

    s = online_services
    s.store.enable(s.scope.knowledge_base_id, False)

    async def run():
        with namespace_lock(s.generations.engine.get_project_paths("alpha")):
            with pytest.raises(ValueError, match="knowledge_namespace_in_use"):
                await KnowledgeProjectAdmin(s.store, s.generations).migrate(
                    s.scope.knowledge_base_id, "alpha", s.signature
                )
        assert s.store.project(s.scope.knowledge_base_id)["active_namespace"] is None

    asyncio.run(run())
