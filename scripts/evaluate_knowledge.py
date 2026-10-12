"""Reproducible retrieval baseline through the actual MCP source contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import tempfile
import time
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from src.knowledge.config import build_knowledge_service_config
from src.knowledge.ingest_service import KnowledgeIngestService
from src.knowledge.rag_engine import ProjectRAGEngine
from src.cli import _execute
from src.mcp_server import create_server
from src.demo_support import load_settings


def score_sources(required, sources, document_ids):
    unknown = set(required) - set(document_ids)
    if unknown:
        raise ValueError("evaluation_expected_document_missing")
    found = {source["document_id"] for source in sources}
    required_ids = {document_ids[name] for name in required}
    checks = [
        all(
            fact.casefold()
            in "\n".join(
                s["preview"] for s in sources if s["document_id"] == document_ids[name]
            ).casefold()
            for fact in facts
        )
        for name, facts in required.items()
    ]
    return {
        "required_documents": sorted(required_ids),
        "matched_documents": sorted(found),
        "document_recall": len(required_ids & found) / len(required_ids)
        if required_ids
        else None,
        "evidence_complete": all(checks) if checks else None,
        "first_relevant_rank": next(
            (i for i, s in enumerate(sources, 1) if s["document_id"] in required_ids),
            None,
        ),
        "cross_project_sources": len(found - set(document_ids.values())),
    }


async def run(output: Path, corpus: Path, questions: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    question_rows = json.loads(questions.read_text(encoding="utf-8"))
    docs = sorted(p for p in corpus.glob("*.md") if p.name != "README.md")
    if not docs or not question_rows:
        raise ValueError("evaluation_corpus_or_questions_empty")
    settings = load_settings()
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "packages": {"lightrag-hku": version("lightrag-hku")},
        "models": {
            "llm": settings.llm_model,
            "embedding": settings.embedding_model,
            "dimensions": settings.embedding_dim,
        },
        "corpus": [p.name for p in docs],
        "questions": len(question_rows),
        "queries": [],
        "recall_at_8": None,
        "evidence_completeness": None,
        "no_answer": {},
        "cross_project_sources": 0,
        "amount": None,
        "status": "running",
        "model_calls": [],
        "ingest_seconds": {},
    }
    with tempfile.TemporaryDirectory(prefix="rag-eval-") as temporary:
        root = Path(temporary)
        config = replace(build_knowledge_service_config(), root_dir=root / "knowledge")
        namespace = "evaluation_baseline"
        engine = ProjectRAGEngine(config)
        ingest = KnowledgeIngestService(rag_engine=engine)
        original_send = httpx.AsyncClient.send
        call_stage = "ingest"

        async def measured_send(client, request, **kwargs):
            response = await original_send(client, request, **kwargs)
            if request.url.path.endswith(("/embeddings", "/chat/completions")):
                await response.aread()
                payload = response.json()
                report["model_calls"].append(
                    {
                        "stage": call_stage,
                        "kind": "embedding"
                        if request.url.path.endswith("/embeddings")
                        else "llm",
                        "usage": payload.get("usage"),
                        "status_code": response.status_code,
                    }
                )
            return response

        try:
            document_ids = {}
            for doc in docs:
                start = time.monotonic()
                with patch.object(httpx.AsyncClient, "send", measured_send):
                    receipt = await ingest.ingest_document(
                        project_id=namespace,
                        file_path=str(doc),
                        source_type="evaluation",
                    )
                report["ingest_seconds"][doc.name] = round(time.monotonic() - start, 3)
                if not receipt.accepted:
                    raise RuntimeError(
                        f"evaluation_ingest_failed:{doc.name}:{receipt.message}"
                    )
                document_ids[doc.name] = receipt.document_id
            paths = engine.get_project_paths(namespace)
            with redirect_stdout(StringIO()):
                await _execute(
                    Namespace(command="publish", project_id=namespace), engine
                )
            report["indexed_bytes"] = sum(
                p.stat().st_size for p in paths.project_dir.rglob("*") if p.is_file()
            )
            decoy = root / "other-project.md"
            decoy.write_text(
                "另一个项目的客户合同价格为 999 元，保密标记 DECOY-9281。",
                encoding="utf-8",
            )
            with patch.object(httpx.AsyncClient, "send", measured_send):
                other = await ingest.ingest_document(
                    project_id="evaluation_other", file_path=str(decoy)
                )
            assert other.accepted
            report["isolated_project_document"] = other.document_id
            with redirect_stdout(StringIO()):
                await _execute(
                    Namespace(command="publish", project_id="evaluation_other"), engine
                )
            token = "evaluation-" + ("x" * 32)
            call_stage = "query"
            scopes = {
                token: {
                    "tenant_id": "__default",
                    "project_id": "11111111-1111-4111-1111-111111111111",
                    "namespace": namespace,
                }
            }
            with (
                patch.dict(
                    os.environ, {"KNOWLEDGE_MCP_TOKEN_SCOPES_JSON": json.dumps(scopes)}
                ),
                patch.object(httpx.AsyncClient, "send", measured_send),
            ):
                app = create_server(config, engine).http_app()

                def factory(**kwargs):
                    return httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), **kwargs
                    )

                async with (
                    app.router.lifespan_context(app),
                    Client(
                        StreamableHttpTransport(
                            "http://rag/mcp", auth=token, httpx_client_factory=factory
                        )
                    ) as client,
                ):
                    for row in question_rows:
                        start = time.monotonic()
                        result = await client.call_tool(
                            "mcp_query_project_knowledge",
                            {"query": row["query"], "top_k": 8},
                        )
                        payload = result.structured_content
                        elapsed = time.monotonic() - start
                        required = row.get("required", {})
                        scores = score_sources(
                            required, payload.get("sources", []), document_ids
                        )
                        report["queries"].append(
                            {
                                "id": row["id"],
                                "query": row["query"],
                                "status": payload.get("status"),
                                **scores,
                                "seconds": round(elapsed, 3),
                                "sources": payload.get("sources", []),
                            }
                        )
                        report["cross_project_sources"] += scores[
                            "cross_project_sources"
                        ]
                        assert json.loads(result.content[0].text) == payload
                        assert len(payload["sources"]) <= 8
                        assert (
                            len(json.dumps(payload, ensure_ascii=False).encode())
                            <= 12 * 1024
                        )
                        assert all(len(s["preview"]) <= 800 for s in payload["sources"])
                        assert (
                            str(root) not in str(payload)
                            and not scores["cross_project_sources"]
                        )
            answered = [q for q in report["queries"] if q["required_documents"]]
            report["recall_at_8"] = (
                round(sum(q["document_recall"] for q in answered) / len(answered), 4)
                if answered
                else None
            )
            report["evidence_completeness"] = (
                round(sum(q["evidence_complete"] for q in answered) / len(answered), 4)
                if answered
                else None
            )
            no_answer = [q for q in report["queries"] if not q["required_documents"]]
            report["no_answer"] = {
                "count": len(no_answer),
                "no_hit": sum(q["status"] == "no_hit" for q in no_answer),
                "returned_sources": sum(bool(q["sources"]) for q in no_answer),
            }
            import numpy as np

            report["latency_seconds"] = {
                "p50": float(
                    np.percentile([q["seconds"] for q in report["queries"]], 50)
                ),
                "p95": float(
                    np.percentile([q["seconds"] for q in report["queries"]], 95)
                ),
            }
            report["status"] = "done"
        except BaseException as error:
            report["status"] = "failed"
            report["error_type"] = type(error).__name__
            raise
        finally:
            try:
                await engine.close()
            finally:
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("test_data/evaluation"))
    parser.add_argument(
        "--questions", type=Path, default=Path("test_data/evaluation/questions.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(run(args.output, args.corpus, args.questions))
    print(
        json.dumps(
            {
                "recall_at_8": report["recall_at_8"],
                "evidence_completeness": report["evidence_completeness"],
                "no_answer": report["no_answer"],
            },
            ensure_ascii=False,
        )
    )
