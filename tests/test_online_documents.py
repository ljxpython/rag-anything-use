"""Online containers, managed assets, and strict multimodal completion."""

import asyncio
import hashlib
import json
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.knowledge.artifacts import KnowledgeArtifactStore, processing_signature
from src.knowledge.document_formats import (
    MIME_EXT,
    supported_mime_types,
    validate_original,
)
from src.knowledge.generations import KnowledgeGenerationService, validate_snapshot
from src.knowledge.upload_service import KnowledgeUploadService


async def upload_bytes(s, data, mime="image/png", name="chart.png", request="image"):
    digest = hashlib.sha256(data).hexdigest()
    ref = {
        "version": 1,
        "path": f"/workspace/uploads/{digest}.{MIME_EXT[mime]}",
        "file_name": name,
        "mime_type": mime,
        "size_bytes": len(data),
        "sha256": digest,
    }
    grant = s.authorizer.grant(
        s.scope,
        "upload",
        {
            **s.identity,
            "request_id": request,
            **{k: ref[k] for k in ("sha256", "size_bytes", "file_name", "mime_type")},
        },
    )

    async def chunks():
        yield data

    ticket = await s.uploads.stage_upload(s.scope, request, ref, grant, chunks())
    return s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)


def configure_documents(s, monkeypatch):
    from src import demo_support

    s.config = replace(
        s.config,
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )
    s.store.config = s.config
    s.uploads = KnowledgeUploadService(s.store, s.authorizer)
    s.generations = KnowledgeGenerationService(s.store, authorizer=s.authorizer)
    s.signature = processing_signature(s.config)
    with s.store.connect(write=True) as db:
        db.execute(
            "UPDATE projects SET signature=? WHERE id=?",
            (s.signature, s.scope.knowledge_base_id),
        )
    for key in ("VISION_BASE_URL", "VISION_MODEL", "VISION_API_KEY"):
        monkeypatch.setenv(key, "test-vision")
    # VISION values are part of the signature: bind the final effective configuration.
    s.signature = processing_signature(s.config)
    with s.store.connect(write=True) as db:
        db.execute(
            "UPDATE projects SET signature=? WHERE id=?",
            (s.signature, s.scope.knowledge_base_id),
        )

    async def vision(*args, **kwargs):
        return json.dumps(
            {
                "detailed_description": "Orion image states capacity 73 units.",
                "entity_info": {
                    "entity_name": "Orion capacity",
                    "entity_type": "image",
                    "summary": "Capacity 73 units.",
                },
            }
        )

    monkeypatch.setattr(
        demo_support, "build_vision_model_func", lambda *a, **kw: vision
    )


def png_bytes():
    from PIL import Image

    out = BytesIO()
    Image.new("RGB", (32, 32), "white").save(out, format="PNG")
    return out.getvalue()


def test_actual_containers_reject_disguised_documents(tmp_path, published_config):
    pytest.importorskip("raganything")
    from scripts.create_evaluation_documents import create

    files = create(tmp_path / "fixtures")
    for file in files:
        mime = next(k for k, ext in MIME_EXT.items() if file.suffix == "." + ext)
        validate_original(file, mime, 20 * 1024**2)
    bad = tmp_path / "bad"
    bad.write_bytes(b"plain text disguised as a binary document")
    for mime in (
        "application/pdf",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        with pytest.raises(ValueError, match="knowledge_invalid_content"):
            validate_original(bad, mime, 20 * 1024**2)
    assert supported_mime_types(published_config) == ["text/plain", "text/markdown"]


def test_managed_assets_survive_parser_cleanup_and_reject_loss(
    online_services, monkeypatch, tmp_path
):
    pytest.importorskip("raganything")
    s = online_services
    configure_documents(s, monkeypatch)

    async def run():
        receipt = await upload_bytes(s, png_bytes())
        doc = s.store.document(receipt["document_id"])
        parsed_dir = tmp_path / "parser"
        parsed_dir.mkdir()
        image = parsed_dir / "figure.png"
        image.write_bytes(png_bytes())
        artifacts = KnowledgeArtifactStore(s.store)
        saved = artifacts.save_document(
            doc,
            s.signature,
            [
                {
                    "type": "image",
                    "img_path": str(image),
                    "page_idx": 2,
                    "page_idx_end": 3,
                }
            ],
            parser_name="docling",
            trusted_dir=parsed_dir,
        )
        image.unlink()
        loaded = artifacts.load(doc, s.signature)
        assert loaded == saved
        assert Path(loaded["content_list"][0]["img_path"]).is_file()
        manifest = next(artifacts.directory(doc["kb"]).glob("*.json"))
        assert str(parsed_dir) not in manifest.read_text()
        with pytest.raises(ValueError, match="knowledge_artifact_invalid"):
            artifacts.load({**doc, "sha256": "a" * 64}, s.signature)
        asset = Path(loaded["content_list"][0]["img_path"])
        asset.write_bytes(b"damaged")
        with pytest.raises(ValueError, match="knowledge_artifact_invalid"):
            artifacts.load(doc, s.signature)

    asyncio.run(run())


def test_multimodal_only_snapshot_increment_restore_and_missing_asset(
    online_services, monkeypatch
):
    pytest.importorskip("raganything")
    from test_knowledge_generations import upload

    from src.knowledge.document_registry import KnowledgeDocumentRegistry

    s = online_services
    configure_documents(s, monkeypatch)

    async def run():
        try:
            first = await upload_bytes(s, png_bytes())
            ns = await s.generations.build(first["job_id"])
            await s.generations.activate(first["job_id"])
            paths = s.generations.engine.get_project_paths(ns)
            assert len(validate_snapshot(paths, s.signature)) == 1
            before = len(s.calls.rows)
            duplicate = await upload_bytes(s, png_bytes(), request="duplicate")
            assert duplicate["reused"]
            await s.generations.close()
            s.generations = KnowledgeGenerationService(s.store, authorizer=s.authorizer)
            async with s.generations.acquire(s.scope.knowledge_base_id) as (
                reader,
                namespace,
            ):
                assert namespace == ns
                assert (
                    len(
                        KnowledgeDocumentRegistry(
                            reader.get_project_paths(namespace)
                        ).list_documents()
                    )
                    == 1
                )
            assert len(s.calls.rows) == before
            second = await upload(s, "New Orion capacity is 74 units.", "text")
            ns2 = await s.generations.build(second["job_id"])
            await s.generations.activate(second["job_id"])
            assert (
                len(
                    validate_snapshot(
                        s.generations.engine.get_project_paths(ns2), s.signature
                    )
                )
                == 2
            )
            assert len(validate_snapshot(paths, s.signature)) == 1
            doc = s.store.document(first["document_id"])
            artifacts = KnowledgeArtifactStore(s.store)
            asset = Path(
                artifacts.load(doc, s.signature)["content_list"][0]["img_path"]
            )
            asset.unlink()
            # A retry cannot repair a corrupt artifact by silently re-parsing the original.
            with pytest.raises(ValueError, match="knowledge_artifact_invalid"):
                await s.generations.build(first["job_id"])
            assert s.store.project(s.scope.knowledge_base_id)["active_namespace"] == ns2
            await s.generations.close()
            s.generations = KnowledgeGenerationService(s.store, authorizer=s.authorizer)
            with pytest.raises(ValueError, match="knowledge_artifact_invalid"):
                async with s.generations.acquire(s.scope.knowledge_base_id):
                    pytest.fail("reader restored missing assets")
            third = await upload(s, "Additional Orion capacity is 75 units.", "third")
            before = len(s.calls.rows)
            with pytest.raises(ValueError, match="knowledge_artifact_invalid"):
                await s.generations.build(third["job_id"])
            assert len(s.calls.rows) == before
            assert s.store.project(s.scope.knowledge_base_id)["active_namespace"] == ns2
        finally:
            await s.generations.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "response", ["", "not json", '{"detailed_description":"", "entity_info":{}}']
)
def test_invalid_modal_response_cannot_mark_processed(
    online_services, monkeypatch, response
):
    pytest.importorskip("raganything")
    from src import demo_support

    s = online_services
    configure_documents(s, monkeypatch)
    monkeypatch.setattr(
        demo_support,
        "build_vision_model_func",
        lambda *a, **kw: AsyncMock(return_value=response),
    )

    async def run():
        try:
            receipt = await upload_bytes(s, png_bytes())
            with pytest.raises(ValueError, match="knowledge_multimodal_failed"):
                await s.generations.build(receipt["job_id"])
            assert (
                s.store.project(s.scope.knowledge_base_id)["active_namespace"] is None
            )
            assert not s.store.receipt(s.scope.knowledge_base_id, receipt["job_id"])[
                "searchable"
            ]
        finally:
            await s.generations.close()

    asyncio.run(run())


@pytest.mark.parametrize("image_path", [None, "missing.png"])
def test_image_failure_before_caption_is_not_a_fallback_success(
    online_services, monkeypatch, image_path
):
    pytest.importorskip("raganything")
    s = online_services
    configure_documents(s, monkeypatch)

    async def run():
        try:
            engine = s.generations.engine
            with pytest.raises(ValueError, match="knowledge_multimodal_failed"):
                await engine.ingest_content_list(
                    project_id="missing_asset",
                    document_id="kd_" + "9" * 32,
                    content_list=[{"type": "image", "img_path": image_path}],
                )
            rag = await engine.get_lightrag("missing_asset")
            assert (await rag.doc_status.get_by_id("kd_" + "9" * 32))[
                "status"
            ] == "failed"
            assert await rag.text_chunks.is_empty()
        finally:
            await s.generations.engine.close()

    asyncio.run(run())


def test_single_text_block_page_range_survives_native_chunking(
    online_services, monkeypatch
):
    pytest.importorskip("raganything")
    s = online_services
    configure_documents(s, monkeypatch)

    async def run():
        try:
            engine = s.generations.engine
            doc_id = "kd_" + "8" * 32
            await engine.ingest_content_list(
                project_id="ranged_text",
                document_id=doc_id,
                content_list=[
                    {
                        "type": "text",
                        "text": "Orion backup retention is 35 days.",
                        "page_idx": 2,
                        "page_idx_end": 4,
                    }
                ],
            )
            rag = await engine.get_lightrag("ranged_text")
            status = await rag.doc_status.get_by_id(doc_id)
            chunks = await rag.text_chunks.get_by_ids(status["chunks_list"])
            assert [(c["page_idx"], c["page_idx_end"]) for c in chunks] == [(2, 4)]
        finally:
            await s.generations.engine.close()

    asyncio.run(run())


def test_internal_modal_failures_keep_existing_public_error_codes():
    from src.knowledge.upload_service import safe_error

    for code in ("knowledge_artifact_invalid", "knowledge_multimodal_failed"):
        assert safe_error(ValueError(code)) == "knowledge_processing_failed"
    assert (
        safe_error(ValueError("knowledge_invalid_content"))
        == "knowledge_invalid_content"
    )
