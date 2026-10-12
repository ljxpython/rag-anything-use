"""Real optional-package interfaces with deterministic model functions."""

import asyncio
import atexit
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.knowledge.rag_engine import CHUNK_DOCUMENT, install_document_chunk_ids
from scripts.verify_incremental_snapshot import Calls


def test_docling_provenance_unknown_and_spanning_pages(tmp_path):
    pytest.importorskip("raganything")
    from src.knowledge.parser_adapter import build_docling_parser

    parser = build_docling_parser()
    block = {"label": "text", "orig": "test", "prov": []}
    assert "page_idx" not in parser.read_from_block(block, "texts", tmp_path, 1, "0")
    block["prov"] = [{"page_no": 3}, {"page_no": 4}, {"page_no": True}]
    parsed = parser.read_from_block(block, "texts", tmp_path, 1, "0")
    assert parsed["page_idx"] == 2 and parsed["page_idx_end"] == 3


def test_docling_table_rows_fit_source_preview(tmp_path, published_config):
    pytest.importorskip("raganything")
    from src.demo_support import build_raganything
    from src.knowledge.parser_adapter import build_docling_parser

    cells = [
        {
            "text": value,
            "start_row_offset_idx": row,
            "end_row_offset_idx": row + 1,
            "start_col_offset_idx": col,
            "end_col_offset_idx": col + 1,
            "bbox": None,
            "column_header": row == 0,
        }
        for row, values in enumerate(
            (("Service", "Daily capacity"), ("Atlas", "840 requests"))
        )
        for col, value in enumerate(values)
    ]
    parsed = build_docling_parser().read_from_block(
        {"data": {"num_rows": 2, "num_cols": 2, "table_cells": cells}},
        "tables",
        tmp_path,
        1,
        "0",
    )
    rag = build_raganything(
        working_dir=str(tmp_path),
        enable_image_processing=False,
        enable_table_processing=False,
        enable_equation_processing=False,
    )
    try:
        content = rag._apply_chunk_template(
            "table", parsed, "Atlas supports 840 requests daily."
        )
        assert "Atlas" in content[:800] and "840 requests" in content[:800]
        assert "table_cells" not in content and "bbox" not in content
        assert "| Service | Daily capacity |" in parsed["table_body"]
    finally:
        atexit.unregister(rag.close)


def test_service_modal_template_keeps_local_assets_private(tmp_path, published_config):
    pytest.importorskip("raganything")
    from src.demo_support import build_raganything

    rag = build_raganything(
        working_dir=str(tmp_path),
        enable_image_processing=False,
        enable_table_processing=False,
        enable_equation_processing=False,
    )
    path = str(tmp_path / "PRIVATE" / "figure.png")
    content = rag._apply_chunk_template(
        "image", {"img_path": path}, "Chart from " + path
    )
    assert path not in content and "asset:" in content
    atexit.unregister(rag.close)


def test_first_parse_initializes_cache_and_reuses_result(online_services, tmp_path):
    pytest.importorskip("raganything")
    engine = online_services.generations.engine
    file = tmp_path / "cache.pdf"
    file.write_bytes(b"public parser cache fixture")

    async def run():
        try:
            rag = await engine.get_rag("parse_cache_fixture")
            rag.doc_parser.parse_pdf = Mock(
                return_value=[{"type": "text", "text": "Cached fact."}]
            )
            first = await rag.parse_document(str(file))
            second = await rag.parse_document(str(file))
            assert first == second
            rag.doc_parser.parse_pdf.assert_called_once()
            path = engine.get_project_paths("parse_cache_fixture").rag_workdir
            assert next(path.glob("*/kv_store_parse_cache.json")).is_file()
        finally:
            await engine.close()
            from src.knowledge.generations import release_workspace
            from src.knowledge.rag_engine import storage_workspace

            release_workspace(
                storage_workspace(engine.get_project_paths("parse_cache_fixture"))
            )

    asyncio.run(run())


@pytest.mark.parametrize("fallback", [False, True])
def test_real_content_list_sources_pages_modal_status_and_close(
    tmp_path, published_config, monkeypatch, fallback
):
    pytest.importorskip("raganything")
    from lightrag import LightRAG
    from lightrag.utils import EmbeddingFunc
    from lightrag.kg import shared_storage
    from PIL import Image
    from src import demo_support
    from src.knowledge.generations import release_workspace

    calls = Calls()

    async def vision(prompt, **kwargs):
        kind = "image" if kwargs.get("image_data") else "table"
        return json.dumps(
            {
                "detailed_description": "Orion audit A-731 confirms the capacity is 73 units.",
                "entity_info": {
                    "entity_name": "capacity",
                    "entity_type": kind,
                    "summary": "Orion capacity is 73 units.",
                },
            }
        )

    workspace = "compat_" + tmp_path.name
    native = LightRAG(
        working_dir=str(tmp_path),
        workspace=workspace,
        llm_model_func=calls.llm,
        embedding_func=EmbeddingFunc(embedding_dim=8, func=calls.embed),
    )
    monkeypatch.setenv("VISION_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("VISION_MODEL", "test-vision")
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    with (
        patch.object(demo_support, "build_llm_model_func", return_value=calls.llm),
        patch.object(demo_support, "build_vision_model_func", return_value=vision),
        patch.object(
            demo_support, "build_embedding_func", return_value=native.embedding_func
        ),
    ):
        rag = demo_support.build_raganything(
            working_dir=str(tmp_path),
            lightrag=native,
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=False,
        )
    if fallback:
        rag._process_multimodal_content_batch_type_aware = AsyncMock(
            side_effect=RuntimeError("batch failed")
        )
    image = tmp_path / "chart.png"
    Image.new("RGB", (32, 32), "white").save(image)
    blocks = [
        {"type": "text", "text": "Orion audit A-731.", "page_idx": 2},
        {
            "type": "table",
            "table_body": "<table><tr><td>capacity</td><td>73</td></tr></table>",
            "table_caption": ["Capacity"],
        },
        {
            "type": "image",
            "img_path": str(image),
            "image_caption": ["Capacity 73"],
            "page_idx": 3,
        },
    ]

    async def run():
        other_workspace = "unrelated_" + tmp_path.name
        try:
            await native.initialize_storages()
            await shared_storage.initialize_pipeline_status(workspace=other_workspace)
            shared_storage.set_default_workspace(other_workspace)
            unrelated = dict(
                await shared_storage.get_namespace_data(
                    "pipeline_status", workspace=other_workspace
                )
            )
            install_document_chunk_ids(multimodal=True)
            for document in ("kd-one", "kd-two"):
                token = CHUNK_DOCUMENT.set(document)
                try:
                    await rag.insert_content_list(
                        content_list=blocks, doc_id=document, file_path=document
                    )
                finally:
                    CHUNK_DOCUMENT.reset(token)
                status = await native.doc_status.get_by_id(document)
                assert status["status"] == "processed"
                assert await rag.is_document_fully_processed(document)
                ids = status["chunks_list"]
                rows = await native.text_chunks.get_by_ids(ids)
                assert len(rows) == 3
                assert all(
                    row["full_doc_id"] == row["file_path"] == document for row in rows
                )
                assert all(str(tmp_path) not in row["content"] for row in rows)
                assert any("asset:" in row["content"] for row in rows)
                table = next(row for row in rows if "Table Analysis:" in row["content"])
                assert table.get("page_idx") is None
                text = next(
                    row
                    for row in rows
                    if row["content"].strip() == "Orion audit A-731."
                )
                assert text["page_idx"] == 2
            first = await native.doc_status.get_by_id("kd-one")
            second = await native.doc_status.get_by_id("kd-two")
            assert not set(first["chunks_list"]) & set(second["chunks_list"])
            assert all(
                row["full_doc_id"] == "kd-one"
                for row in await native.text_chunks.get_by_ids(first["chunks_list"])
            )
            assert (
                dict(
                    await shared_storage.get_namespace_data(
                        "pipeline_status", workspace=other_workspace
                    )
                )
                == unrelated
            )
        finally:
            await rag.finalize_storages()
            atexit.unregister(rag.close)
            release_workspace(workspace)
            release_workspace(other_workspace)

    asyncio.run(run())
