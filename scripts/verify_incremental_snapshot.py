"""G01: isolated, reproducible native-storage snapshot experiment (no live data)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import shutil
import sys
import tempfile
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import httpx
import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.demo_support import build_lightrag, load_settings

STORES = (
    "full_docs",
    "text_chunks",
    "full_entities",
    "full_relations",
    "entity_chunks",
    "relation_chunks",
    "entities_vdb",
    "relationships_vdb",
    "chunks_vdb",
    "chunk_entity_relation_graph",
    "llm_response_cache",
    "doc_status",
)
TEXTS = {
    "A": "Orion 项目的登录服务由 Alice 维护，登录接口使用 POST，审计编号 A-731。",
    "B": "Orion 项目的备份服务由 Bob 维护，每天凌晨两点执行，审计编号 B-842。",
    "C": "Orion 项目的付款服务由 Carol 维护，付款币种为人民币，审计编号 C-953。",
    "D": "Orion 项目的通知服务由 David 维护，通知通道为短信，审计编号 D-164。",
}
IDS = {key: "kd_" + f"{i:032x}" for i, key in enumerate(TEXTS, 1)}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Calls:
    def __init__(self):
        self.phase = "baseline"
        self.rows = []

    def add(self, kind, inputs, usage=None, ok=True):
        self.rows.append(
            {
                "phase": self.phase,
                "kind": kind,
                "ok": ok,
                "inputs": [hashlib.sha256(x.encode()).hexdigest() for x in inputs],
                "usage": usage,
                "usage_source": "provider" if usage else "unknown",
            }
        )

    async def llm(self, prompt, system_prompt=None, history_messages=None, **kwargs):
        self.add("llm", [json.dumps([system_prompt, history_messages, prompt])])
        if history_messages:
            return "<|COMPLETE|>"
        key = next((key for key in TEXTS if f"{key}-" in prompt), "A")
        return (
            "entity<|#|>Orion<|#|>organization<|#|>Orion 是项目。\n"
            f"entity<|#|>Service{key}<|#|>concept<|#|>Service{key} 是服务。\n"
            f"relation<|#|>Orion<|#|>Service{key}<|#|>维护<|#|>Orion 维护 Service{key}。\n"
            "<|COMPLETE|>"
        )

    async def embed(self, texts):
        self.add("embedding", texts)
        return (
            np.array(
                [
                    np.frombuffer(hashlib.sha256(x.encode()).digest(), dtype=np.uint8)[
                        :8
                    ]
                    for x in texts
                ],
                dtype=np.float32,
            )
            + 1
        )

    def report(self):
        result = {}
        previous = set()
        for phase in dict.fromkeys(row["phase"] for row in self.rows):
            rows = [row for row in self.rows if row["phase"] == phase]
            inputs = [(row["kind"], x) for row in rows for x in row["inputs"]]
            result[phase] = {
                "requests": dict(Counter(row["kind"] for row in rows)),
                "inputs": len(inputs),
                "unchanged_prior_inputs": sum(x in previous for x in inputs),
                "provider_usage": [row["usage"] for row in rows if row["usage"]],
            }
            if not phase.startswith("query"):
                previous.update(inputs)
        return result


async def run(real: bool):
    calls = Calls()
    original_send = httpx.AsyncClient.send

    async def send(client, request, **kwargs):
        is_model = request.url.path.endswith(("/embeddings", "/chat/completions"))
        if not is_model:
            return await original_send(client, request, **kwargs)
        body = json.loads(request.content)
        kind = "embedding" if "input" in body else "llm"
        inputs = (
            body.get("input")
            if kind == "embedding"
            else [json.dumps(body, sort_keys=True, ensure_ascii=False)]
        )
        inputs = inputs if isinstance(inputs, list) else [inputs]
        row_index = len(calls.rows)
        calls.add(kind, inputs, ok=False)
        response = await original_send(client, request, **kwargs)
        await response.aread()
        payload = response.json()
        calls.rows[row_index].update(
            ok=response.is_success,
            usage=payload.get("usage"),
            usage_source="provider" if payload.get("usage") else "unknown",
        )
        return response

    async def open_rag(root, name):
        workdir = root / name
        if real:
            rag = build_lightrag(str(workdir), workspace=name)
        else:
            rag = LightRAG(
                working_dir=str(workdir),
                workspace=name,
                llm_model_func=calls.llm,
                embedding_func=EmbeddingFunc(embedding_dim=8, func=calls.embed),
            )
        await rag.initialize_storages()
        return rag

    async def flush(rag):
        await asyncio.gather(
            *[getattr(rag, name).index_done_callback() for name in STORES]
        )

    async def insert(rag, key):
        await rag.ainsert(TEXTS[key], ids=IDS[key], file_paths=IDS[key])
        assert (await rag.doc_status.get_by_id(IDS[key]))["status"] == "processed"

    async def check(rag, keys):
        for key in keys:
            assert (await rag.full_docs.get_by_id(IDS[key]))["content"] == TEXTS[key]
            assert (await rag.doc_status.get_by_id(IDS[key]))["status"] == "processed"
        calls.phase = "query_" + "".join(keys)
        for key in keys:
            result = await rag.aquery_data(
                TEXTS[key],
                param=QueryParam(mode="naive", top_k=8, chunk_top_k=8),
            )
            chunks = result.get("data", {}).get("chunks", [])
            assert any(chunk.get("file_path") == IDS[key] for chunk in chunks), result

    with tempfile.TemporaryDirectory(prefix="rag-g01-") as temp:
        root = Path(temp)
        with (
            patch.object(httpx.AsyncClient, "send", send)
            if real
            else patch.dict({}, {})
        ):
            baseline = await open_rag(root, "base")
            await insert(baseline, "A")
            await insert(baseline, "B")
            await flush(baseline)
            await baseline.finalize_storages()
            files = {p.name: digest(p) for p in (root / "base" / "base").iterdir()}
            assert len(files) == 12, files

            # Restore files before constructing the candidate: constructors load graph/vector files.
            def restore(name, source="base"):
                target = root / name / name
                target.mkdir(parents=True)
                for path in (root / source / source).iterdir():
                    shutil.copyfile(path, target / path.name)
                assert all(
                    digest(target / file) == checksum
                    for file, checksum in files.items()
                )

            restore("candidate")
            calls.phase = "restore"
            candidate = await open_rag(root, "candidate")
            assert not any(row["phase"] == "restore" for row in calls.rows)
            calls.phase = "duplicate_A"
            await insert(candidate, "A")
            assert not any(row["phase"] == "duplicate_A" for row in calls.rows)
            calls.phase = "increment_C"
            await insert(candidate, "C")
            await flush(candidate)
            await candidate.finalize_storages()
            assert files == {
                p.name: digest(p) for p in (root / "base" / "base").iterdir()
            }
            restored = root / "restarted" / "restarted"
            restored.mkdir(parents=True)
            for path in (root / "candidate" / "candidate").iterdir():
                shutil.copyfile(path, restored / path.name)
            candidate = await open_rag(root, "restarted")
            await check(candidate, "ABC")
            calls.phase = "increment_D"
            await insert(candidate, "D")
            await flush(candidate)
            await check(candidate, "ABCD")
            await candidate.finalize_storages()

            restore("failure")
            failed = await open_rag(root, "failure")
            calls.phase = "failed_C"

            async def broken_embed(texts, **kwargs):
                raise RuntimeError("injected_embedding_failure")

            with patch.object(failed.chunks_vdb, "embedding_func", broken_embed):
                await failed.ainsert(TEXTS["C"], ids=IDS["C"], file_paths=IDS["C"])
            assert (await failed.doc_status.get_by_id(IDS["C"]))[
                "status"
            ] != "processed"
            await failed.finalize_storages()
            assert files == {
                p.name: digest(p) for p in (root / "base" / "base").iterdir()
            }
            restore("rollback")
            rollback = await open_rag(root, "rollback")
            await check(rollback, "AB")
            assert await rollback.full_docs.get_by_id(IDS["C"]) is None
            await rollback.finalize_storages()
        settings = load_settings() if real else None
        return {
            "mode": "real" if real else "mock",
            "lightrag": version("lightrag-hku"),
            "storage_files": sorted(files),
            "storage_checksums": files,
            "models": {
                "llm": settings.llm_model,
                "embedding": settings.embedding_model,
                "dimensions": settings.embedding_dim,
            }
            if real
            else {"dimensions": 8},
            "checks": {
                "restore_without_models": True,
                "duplicate_without_models": True,
                "base_unchanged": True,
                "restart_ABCD": True,
                "failure_isolated": True,
                "rollback_AB": True,
            },
            "calls": calls.report(),
            "amount": None,
            "amount_reason": "No approved rate table; usage is reported separately.",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.getLogger("lightrag").setLevel(logging.ERROR)
    result = asyncio.run(run(args.real))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
