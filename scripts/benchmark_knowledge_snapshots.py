"""Measure isolated snapshot growth and stages with deterministic model functions."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from lightrag import LightRAG
from lightrag.kg import shared_storage
from lightrag.utils import EmbeddingFunc

from scripts.verify_incremental_snapshot import Calls
from src.knowledge import generations as module
from src.knowledge import rag_engine
from src.knowledge.artifacts import checksum, processing_signature
from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.generations import KnowledgeGenerationService, storage_dir
from src.knowledge.jobs import KnowledgeJobStore


async def run(count):
    calls, measurements, stages = Calls(), [], {}

    def measured(name, function):
        def invoke(*args, **kwargs):
            start = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                stages.setdefault(name, []).append(time.perf_counter() - start)

        return invoke

    def factory(workdir, **kwargs):
        return LightRAG(
            working_dir=workdir,
            workspace=kwargs["workspace"],
            llm_model_func=calls.llm,
            embedding_func=EmbeddingFunc(embedding_dim=8, func=calls.embed),
        )

    env = {
        "LLM_BASE_URL": "http://127.0.0.1:1",
        "LLM_MODEL": "benchmark-mock",
        "LLM_API_KEY": "mock",
        "EMBEDDING_BASE_URL": "http://127.0.0.1:1",
        "EMBEDDING_MODEL": "benchmark-mock",
        "EMBEDDING_DIM": "8",
    }
    with (
        tempfile.TemporaryDirectory(prefix="rag-capacity-") as temporary,
        patch.dict(os.environ, env),
        patch.object(rag_engine, "build_lightrag", factory),
        patch.object(module, "copy_storage", measured("copy", module.copy_storage)),
        patch.object(
            module, "validate_snapshot", measured("validate", module.validate_snapshot)
        ),
    ):
        config = KnowledgeServiceConfig(root_dir=Path(temporary), online_enabled=True)
        store = KnowledgeJobStore(config)
        signature = processing_signature(config)
        project = store.register(
            "__default", "11111111-1111-4111-8111-111111111111", signature, enabled=True
        )
        service = KnowledgeGenerationService(store)
        frozen = None
        try:
            for number in range(count):
                text = f"Orion audit A-{number:04d}: service capacity is {number + 1} units."
                data = text.encode()
                digest = hashlib.sha256(data).hexdigest()
                original = (
                    config.root_dir / "managed" / project["id"] / "originals" / digest
                )
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(data)
                receipt = store.submit(
                    project["id"],
                    str(number),
                    {},
                    {
                        "sha256": digest,
                        "size_bytes": len(data),
                        "file_name": f"fixture-{number}.md",
                        "mime_type": "text/markdown",
                    },
                    str(original),
                    signature,
                )
                start = time.perf_counter()
                namespace = await service.build(receipt["job_id"])
                elapsed = time.perf_counter() - start
                paths = service.engine.get_project_paths(namespace)
                assert len(module.validate_snapshot(paths, signature)) == number + 1
                with store.connect(write=True) as db:
                    db.execute(
                        "INSERT INTO generations VALUES(?,?,?,?,?,?)",
                        (
                            namespace,
                            project["id"],
                            signature,
                            number,
                            json.dumps(
                                [
                                    r.document_id
                                    for r in module.validate_snapshot(paths, signature)
                                ]
                            ),
                            "benchmark",
                        ),
                    )
                    db.execute(
                        "UPDATE projects SET active_namespace=?,revision=revision+1 WHERE id=?",
                        (namespace, project["id"]),
                    )
                    db.execute(
                        "UPDATE jobs SET status='ready' WHERE id=?",
                        (receipt["job_id"],),
                    )
                before = len(calls.rows)
                start = time.perf_counter()
                async with service.acquire(project["id"]):
                    pass
                prepare_seconds = time.perf_counter() - start
                assert len(calls.rows) == before
                measurements.append(
                    {
                        "documents": number + 1,
                        "build_seconds": elapsed,
                        "reader_seconds": prepare_seconds,
                        "snapshot_bytes": sum(
                            p.stat().st_size for p in storage_dir(paths).iterdir()
                        ),
                        "total_root_bytes": sum(
                            p.stat().st_size
                            for p in config.root_dir.rglob("*")
                            if p.is_file()
                        ),
                    }
                )
                if frozen is None:
                    frozen = (
                        paths,
                        {p.name: checksum(p) for p in storage_dir(paths).iterdir()},
                    )
            assert frozen[1] == {
                p.name: checksum(p) for p in storage_dir(frozen[0]).iterdir()
            }
            remaining = len(
                [key for key in shared_storage._shared_dicts if key.startswith("kb_")]
            )
        finally:
            await service.close()
            remaining_after_close = len(
                [key for key in shared_storage._shared_dicts if key.startswith("kb_")]
            )
            assert remaining_after_close == 0
    return {
        "mode": "deterministic models, no IAM or real-model load",
        "platform": platform.platform(),
        "count": count,
        "measurements": measurements,
        "stage_seconds": {
            k: {
                "p50": float(np.percentile(v, 50)),
                "p95": float(np.percentile(v, 95)),
                "samples": len(v),
            }
            for k, v in stages.items()
        },
        "read_restore_zero_model_calls": True,
        "first_snapshot_unchanged": True,
        "shared_keys_before_final_close": remaining,
        "shared_keys_after_final_close": remaining_after_close,
        "calls": calls.report(),
        "amount": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=20, choices=range(1, 101))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.documents))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"documents": args.documents, "stages": result["stage_seconds"]}))
