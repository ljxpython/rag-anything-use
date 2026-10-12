import json
import asyncio
from types import SimpleNamespace

import httpx

from src.knowledge.artifacts import (
    KnowledgeArtifactStore,
    KnowledgeUsageRecorder,
    processing_signature,
)


def test_artifacts_checksums_scope_signature_and_usage_unknown(
    online_services, monkeypatch
):
    s = online_services
    from test_knowledge_generations import upload
    import asyncio

    receipt = asyncio.run(upload(s, "# text", "a"))
    doc = s.store.document(receipt["document_id"])
    artifacts = KnowledgeArtifactStore(s.store)
    saved = artifacts.save_text(doc, s.signature, "# text")
    assert artifacts.load(doc, s.signature) == saved
    assert artifacts.load(doc, "changed") is None
    assert artifacts.load({**doc, "sha256": "b" * 64}, s.signature) is None
    path = next(artifacts.directory(doc["kb"]).iterdir())
    payload = json.loads(path.read_text())
    payload["content"]["text"] = "tampered"
    path.write_text(json.dumps(payload))
    assert artifacts.load(doc, s.signature) is None
    original = processing_signature(s.config)
    monkeypatch.setenv("EMBEDDING_MODEL", "new-model")
    assert processing_signature(s.config) != original
    recorder = KnowledgeUsageRecorder(s.store, receipt["job_id"])
    row = recorder.begin("embedding", 2)
    recorder.finish(row)
    recorder.begin("graph_extraction")
    s.store.recover()
    with s.store.connect() as db:
        rows = list(db.execute("SELECT * FROM usage ORDER BY id"))
    assert rows[0]["provider_usage"] is None and rows[0]["usage_source"] == "unknown"
    assert rows[1]["status"] == "unknown"


def test_embedding_usage_tracks_actual_queued_inputs_and_existing_graph(
    online_services,
):
    from src.demo_support import UsageTransport
    from test_knowledge_generations import upload

    s = online_services

    async def run():
        receipt = await upload(s, "usage classification", "a")
        recorder = KnowledgeUsageRecorder(s.store, receipt["job_id"])
        queued = []

        class Storage:
            async def get_by_ids(self, ids):
                return [{"id": key} if key == "old" else None for key in ids]

            async def upsert(self, data):
                queued.append([value["content"] for value in data.values()])

        rag = SimpleNamespace(
            llm_response_cache=SimpleNamespace(get_by_id=lambda key: None),
            chunks_vdb=Storage(),
            entities_vdb=Storage(),
            relationships_vdb=Storage(),
        )
        recorder.instrument(rag)
        await rag.chunks_vdb.upsert({"chunk": {"content": "new chunk"}})
        await rag.entities_vdb.upsert({"entity": {"content": "new entity"}})
        await rag.relationships_vdb.upsert({"old": {"content": "merged relation"}})
        # Process later through a common transport, as LightRAG's shared queue does.
        transport = UsageTransport(recorder, "embedding")
        await transport.inner.aclose()
        transport.inner = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"usage": {"total_tokens": 1}})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            for batch in queued:
                await client.post("http://provider/embeddings", json={"input": batch})
        with s.store.connect() as db:
            rows = list(
                db.execute(
                    "SELECT * FROM usage WHERE job_id=? ORDER BY id",
                    (receipt["job_id"],),
                )
            )
        assert [row["stage"] for row in rows] == [
            "new_chunks",
            "graph_embedding",
            "affected_graph_merge",
        ]
        assert all(
            row["input_count"] == 1 and row["usage_source"] == "provider"
            for row in rows
        )
        assert (
            recorder.embedding_stage(["new chunk", "new entity"]) == "mixed_embedding"
        )
        assert recorder.embedding_stage(["unregistered"]) == "unknown_embedding"

    asyncio.run(run())
