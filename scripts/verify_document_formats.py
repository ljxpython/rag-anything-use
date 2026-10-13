"""Isolated real CLI ingest/publish and authenticated HTTP MCP format evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from scripts.create_evaluation_documents import create
from src.demo_support import load_settings
from src.knowledge.artifacts import checksum
from src.knowledge.config import build_knowledge_service_config
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.rag_engine import ProjectRAGEngine
from src.mcp_server import create_server

CASES = {
    "text.pdf": [
        ("How long is Orion backup retention?", "35 days"),
        ("How often are Orion restoration drills held?", "14 days"),
    ],
    "scan.pdf": [("What is the Orion emergency recovery code?", "DR-4826")],
    "mixed.pdf": [
        ("What is the Orion capacity reserve?", "27"),
        ("How many daily requests does Atlas support?", "840"),
        ("What is the capacity formula?", "42"),
    ],
    "handbook.docx": [
        ("How quickly must an Orion production incident be acknowledged?", "7 minutes"),
        ("What is the P1 response time in the severity table?", "7 minutes"),
        ("What is the capacity equation in the Orion handbook?", "42"),
        ("What emergency recovery code appears in the handbook image?", "DR-4826"),
    ],
    "release.pptx": [
        ("When do Orion production releases happen?", "Tuesday"),
        ("How long is the Orion rollback window?", "18 minutes"),
        ("What recovery code appears in the release slide image?", "DR-4826"),
    ],
}
MODAL_EVIDENCE = {
    "How many daily requests does Atlas support?": "Table Analysis:",
    "What is the P1 response time in the severity table?": "Table Analysis:",
    "What is the capacity equation in the Orion handbook?": "Mathematical Equation Analysis:",
    "What emergency recovery code appears in the handbook image?": "Image Content Analysis:",
    "What recovery code appears in the release slide image?": "Image Content Analysis:",
}


def evidence_found(question, fact, sources):
    return any(
        fact.casefold() in source["preview"].casefold()
        and MODAL_EVIDENCE.get(question, "") in source["preview"]
        for source in sources
    )


async def run(output, selected_files=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "packages": {
            p: version(p) for p in ("raganything", "lightrag-hku", "docling", "mineru")
        },
        "models": {
            "llm": settings.llm_model,
            "embedding": settings.embedding_model,
            "dimensions": settings.embedding_dim,
            "vision": settings.vision_model,
        },
        "corpus": "generated public format fixtures, no business data",
        "formats": [],
        "amount": None,
    }
    with tempfile.TemporaryDirectory(prefix="rag-formats-") as temporary:
        directory = Path(temporary)
        files = create(directory / "fixtures")
        if selected_files:
            files = [file for file in files if file.name in selected_files]
        config = replace(
            build_knowledge_service_config(),
            root_dir=directory / "knowledge",
            online_enabled=False,
        )
        env = {
            **os.environ,
            "KNOWLEDGE_ROOT_DIR": str(config.root_dir),
            "PARSER": "docling",
            "KNOWLEDGE_ONLINE_ENABLED": "false",
            "KNOWLEDGE_ENABLE_IMAGE_PROCESSING": "true",
            "KNOWLEDGE_ENABLE_TABLE_PROCESSING": "true",
            "KNOWLEDGE_ENABLE_EQUATION_PROCESSING": "true",
        }
        for number, file in enumerate(files):
            namespace = f"format_{number}"
            row = {"file": file.name, "sha256": checksum(file), "queries": []}
            report["formats"].append(row)
            start = time.monotonic()
            command = [
                sys.executable,
                "main.py",
                "ingest",
                "--project-id",
                namespace,
                "--file",
                str(file),
            ]
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    command,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except subprocess.TimeoutExpired as error:
                row.update(
                    status="failed",
                    error_type="TimeoutExpired",
                    ingest_seconds=round(time.monotonic() - start, 3),
                )
                captured = (error.stdout or b"") + (error.stderr or b"")
                (output.parent / (file.name + ".log")).write_text(
                    captured.decode(errors="replace")
                    if isinstance(captured, bytes)
                    else captured
                )
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                continue
            row["ingest_seconds"] = round(time.monotonic() - start, 3)
            row["ingest_exit"] = result.returncode
            (output.parent / (file.name + ".log")).write_text(
                result.stdout + result.stderr
            )
            row["analysis_failures"] = sum(
                line.startswith("ERROR:")
                and any(
                    marker in line
                    for marker in (
                        "Error generating",
                        "Error processing",
                        "Received empty",
                        "Error in multimodal",
                        "Error parsing",
                    )
                )
                for line in result.stderr.splitlines()
            )
            row["individual_fallbacks"] = result.stderr.count(
                "Falling back to individual multimodal processing"
            )
            if result.returncode:
                row["status"] = "failed"
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                continue
            paths = ProjectRAGEngine(config).get_project_paths(namespace)
            records = KnowledgeDocumentRegistry(paths).list_documents()
            row["page_count"] = records[0].page_count
            row["chunk_count"] = records[0].chunk_count
            row["document_id"] = records[0].document_id
            if records[0].overall_status != "ready":
                row.update(status="failed", error_type="knowledge_index_not_ready")
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                continue
            chunks_path = next(
                paths.rag_workdir.glob("*/kv_store_text_chunks.json"), None
            )
            if chunks_path is None:
                row.update(status="failed", error_type="knowledge_chunks_missing")
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                continue
            chunks = json.loads(chunks_path.read_text())
            cache_path = chunks_path.with_name("kv_store_parse_cache.json")
            cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
            blocks = [
                block
                for parsed in cache.values()
                for block in parsed.get("content_list", [])
            ]
            row["parsed_blocks"] = dict(Counter(block.get("type") for block in blocks))
            row["parse_cache_present"] = bool(cache)
            row["local_asset_paths_hidden"] = all(
                str(directory) not in chunk["content"] for chunk in chunks.values()
            )
            row["pages"] = sorted(
                {
                    r["page_idx"]
                    for r in chunks.values()
                    if type(r.get("page_idx")) is int
                }
            )
            row["page_ranges"] = [
                {
                    key: chunk.get(key)
                    for key in ("page_idx", "page_idx_end", "original_type")
                }
                for chunk in chunks.values()
            ]
            row["chunk_sources_valid"] = all(
                r["full_doc_id"] == r["file_path"] == records[0].document_id
                for r in chunks.values()
            )
            status = json.loads(
                chunks_path.with_name("kv_store_doc_status.json").read_text()
            )
            row["all_chunks_registered"] = set(chunks) == set(
                status[records[0].document_id].get("chunks_list") or []
            )
            publish = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "main.py", "publish", "--project-id", namespace],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            row["publish_exit"] = publish.returncode
            if publish.returncode:
                row["status"] = "failed"
                continue
            token = os.urandom(32).hex()
            scopes = {
                token: {
                    "tenant_id": "__default",
                    "project_id": "11111111-1111-4111-8111-111111111111",
                    "namespace": namespace,
                }
            }
            with patch.dict(
                os.environ, {"KNOWLEDGE_MCP_TOKEN_SCOPES_JSON": json.dumps(scopes)}
            ):
                app = create_server(config).http_app()

                def factory(*, app=app, **kwargs):
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
                    for question, fact in CASES[file.name]:
                        start = time.monotonic()
                        response = await client.call_tool(
                            "mcp_query_project_knowledge", {"query": question}
                        )
                        payload = response.structured_content
                        sources = payload["sources"]
                        row["queries"].append(
                            {
                                "question": question,
                                "expected": fact,
                                "found": evidence_found(question, fact, sources),
                                "required_evidence": MODAL_EVIDENCE.get(question),
                                "seconds": round(time.monotonic() - start, 3),
                                "payload": payload,
                            }
                        )
                        assert json.loads(response.content[0].text) == payload
                        assert all(
                            s["document_id"] == records[0].document_id for s in sources
                        )
                        assert str(directory) not in str(payload)
            row["status"] = (
                "done"
                if all(q["found"] for q in row["queries"])
                and row["chunk_sources_valid"]
                and row["local_asset_paths_hidden"]
                and row["all_chunks_registered"]
                and not row["analysis_failures"]
                else "partial"
            )
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--files", nargs="+", choices=list(CASES))
    args = parser.parse_args()
    report = asyncio.run(run(args.output, args.files))
    print(json.dumps({r["file"]: r["status"] for r in report["formats"]}))
    raise SystemExit(0 if all(r["status"] == "done" for r in report["formats"]) else 1)
