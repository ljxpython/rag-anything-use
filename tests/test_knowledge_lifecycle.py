import asyncio
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.cli import _execute
from src.knowledge import rag_engine as module
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.publication import validate_publication
from src.knowledge.rag_engine import ProjectRAGEngine


@pytest.mark.parametrize(
    "failure", [RuntimeError("init failed"), asyncio.CancelledError()]
)
def test_initialization_failure_closes_partial_engine(
    published_config, monkeypatch, failure
):
    rag = SimpleNamespace(
        initialize_storages=AsyncMock(side_effect=failure),
        finalize_storages=AsyncMock(),
    )
    monkeypatch.setattr(module, "build_lightrag", lambda *a, **k: rag)
    engine = ProjectRAGEngine(published_config)
    with pytest.raises(type(failure)):
        asyncio.run(engine.get_lightrag("alpha"))
    rag.finalize_storages.assert_awaited_once()
    assert engine._lightrag_cache == {}


@pytest.mark.parametrize(
    "failure", [RuntimeError("init failed"), asyncio.CancelledError()]
)
def test_cleanup_failure_preserves_initialization_failure(
    published_config, monkeypatch, failure, caplog
):
    rag = SimpleNamespace(
        initialize_storages=AsyncMock(side_effect=failure),
        finalize_storages=AsyncMock(side_effect=RuntimeError("private cleanup detail")),
    )
    monkeypatch.setattr(module, "build_lightrag", lambda *a, **k: rag)
    engine = ProjectRAGEngine(published_config)
    with pytest.raises(type(failure)) as error:
        asyncio.run(engine.get_lightrag("alpha"))
    assert error.value is failure
    rag.finalize_storages.assert_awaited_once()
    assert engine._lightrag_cache == {}
    assert "knowledge_engine_cleanup_failed" in caplog.text
    assert "private cleanup detail" not in caplog.text


def test_two_namespaces_cache_and_cleanup_even_when_one_close_fails(
    published_config, monkeypatch
):
    engines = []

    def build(*args, **kwargs):
        rag = SimpleNamespace(
            initialize_storages=AsyncMock(), finalize_storages=AsyncMock()
        )
        engines.append((kwargs["workspace"], rag))
        return rag

    monkeypatch.setattr(module, "build_lightrag", build)
    monkeypatch.setattr(module, "initialize_pipeline_status", AsyncMock())

    async def run():
        engine = ProjectRAGEngine(published_config)
        a, b, again = await asyncio.gather(
            engine.get_lightrag("alpha"),
            engine.get_lightrag("beta"),
            engine.get_lightrag("alpha"),
        )
        assert a is again and a is not b
        assert len(engines) == 2 and engines[0][0] != engines[1][0]
        a.finalize_storages.side_effect = RuntimeError("close failed")
        with pytest.raises(RuntimeError, match="close failed"):
            await engine.close()
        a.finalize_storages.assert_awaited_once()
        b.finalize_storages.assert_awaited_once()
        assert engine._lightrag_cache == {}

    asyncio.run(run())


def test_corrupt_manifest_never_passes_publication(published_config):
    paths = ProjectRAGEngine(published_config).get_project_paths("alpha")
    (paths.manifest_dir / "documents.json").write_text("{broken")
    with pytest.raises(ValueError):
        validate_publication(paths)


def test_publish_refuses_partial_index(published_config):
    engine = ProjectRAGEngine(published_config)
    paths = engine.get_project_paths("alpha")
    registry = KnowledgeDocumentRegistry(paths)
    record = registry.list_documents()[0]
    registry.update_document(record.model_copy(update={"index_status": "failed"}))
    with pytest.raises(ValueError, match="knowledge_index_not_ready"):
        asyncio.run(_execute(Namespace(command="publish", project_id="alpha"), engine))
