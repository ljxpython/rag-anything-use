import asyncio
import hashlib
from dataclasses import replace
from unittest.mock import patch

import pytest

from src.knowledge import artifacts
from src.knowledge.artifacts import (
    compatible_processing_signature,
    processing_signature,
    checksum,
)
from src.knowledge.generations import storage_dir, validate_snapshot
from src.knowledge.operation_auth import canonical


def old_signature(config):
    values = artifacts._processing_values(config)
    values["packages"] = {
        "lightrag-hku": "1.4.12",
        "raganything": "1.2.10",
        "docling": "2.84.0",
    }
    return hashlib.sha256(canonical(values).encode()).hexdigest()


def test_text_signature_ignores_unused_optional_packages(published_config, monkeypatch):
    before = processing_signature(published_config)
    actual = artifacts.version
    monkeypatch.setattr(
        artifacts,
        "version",
        lambda name: "1.4.2" if name == "raganything" else actual(name),
    )
    assert processing_signature(published_config) == before
    assert compatible_processing_signature(
        published_config, old_signature(published_config)
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("LLM_MODEL", "changed"),
        ("LLM_BASE_URL", "http://other"),
        ("EMBEDDING_MODEL", "changed"),
        ("EMBEDDING_DIM", "16"),
        ("EMBEDDING_PROVIDER", "openai"),
    ],
)
def test_upgrade_compatibility_never_bypasses_model_changes(
    published_config, monkeypatch, key, value
):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
    old = old_signature(published_config)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="knowledge_processing_config_changed"):
        compatible_processing_signature(published_config, old)


def test_unknown_packages_and_multimodal_v1_are_not_approved(
    published_config, monkeypatch
):
    old = old_signature(published_config)
    actual = artifacts.version
    monkeypatch.setattr(
        artifacts,
        "version",
        lambda name: "1.4.16" if name == "lightrag-hku" else actual(name),
    )
    with pytest.raises(ValueError):
        compatible_processing_signature(published_config, old)
    monkeypatch.setattr(artifacts, "version", actual)
    with pytest.raises(ValueError):
        compatible_processing_signature(
            replace(published_config, enable_image_processing=True), old
        )


def test_v1_text_snapshot_retains_signature_increment_and_rollback(
    online_services, monkeypatch
):
    from test_knowledge_generations import upload
    from scripts.verify_incremental_snapshot import TEXTS

    s = online_services
    legacy = old_signature(s.config)
    actual = artifacts.version
    monkeypatch.setattr(
        artifacts,
        "version",
        lambda name: (
            "1.4.2"
            if name == "raganything"
            else "2.84.0"
            if name == "docling"
            else actual(name)
        ),
    )
    with s.store.connect(write=True) as db:
        db.execute(
            "UPDATE projects SET signature=? WHERE id=?",
            (legacy, s.scope.knowledge_base_id),
        )

    async def run():
        try:
            first = await upload(s, TEXTS["A"], "old")
            first_ns = await s.generations.build(first["job_id"])
            await s.generations.activate(first["job_id"])
            paths = s.generations.engine.get_project_paths(first_ns)
            frozen = {p.name: checksum(p) for p in storage_dir(paths).iterdir()}
            before = len(s.calls.rows)
            assert (await upload(s, TEXTS["A"], "duplicate"))["reused"]
            assert len(s.calls.rows) == before
            second = await upload(s, TEXTS["B"], "new")
            second_ns = await s.generations.build(second["job_id"])
            await s.generations.activate(second["job_id"])
            assert (
                len(
                    validate_snapshot(
                        s.generations.engine.get_project_paths(second_ns), legacy
                    )
                )
                == 2
            )
            async with s.generations.acquire(s.scope.knowledge_base_id) as (reader, ns):
                assert ns == second_ns and reader is not None
            assert frozen == {p.name: checksum(p) for p in storage_dir(paths).iterdir()}
            assert s.store.project(s.scope.knowledge_base_id)["signature"] == legacy
            s.store.enable(s.scope.knowledge_base_id, False)
            await s.generations.rollback(s.scope.knowledge_base_id, first_ns)
            async with s.generations.acquire(s.scope.knowledge_base_id) as (reader, ns):
                assert ns == first_ns
            with patch.dict("os.environ", {"EMBEDDING_MODEL": "changed"}):
                with pytest.raises(
                    ValueError, match="knowledge_processing_config_changed"
                ):
                    async with s.generations.acquire(s.scope.knowledge_base_id):
                        pass
        finally:
            await s.generations.close()

    asyncio.run(run())
