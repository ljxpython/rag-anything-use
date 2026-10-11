from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.knowledge.schemas import CitationRecord, KnowledgeDocumentRecord


def build_citations(chunks: Iterable[dict[str, Any]]) -> list[CitationRecord]:
    citations: list[CitationRecord] = []
    for chunk in chunks:
        metadata = chunk.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        document_id = str(metadata.get("document_id") or "")
        if not document_id:
            continue
        citations.append(
            CitationRecord(
                document_id=document_id,
                filename=metadata.get("filename"),
                chunk_id=metadata.get("chunk_id"),
                page_index=metadata.get("page_index"),
                block_type=chunk.get("type"),
                score=chunk.get("score"),
                snippet=chunk.get("text") or chunk.get("snippet"),
                metadata=metadata,
            )
        )
    return citations


def build_query_result_artifacts(
    query_data: dict[str, Any],
    *,
    documents: Iterable[KnowledgeDocumentRecord],
) -> tuple[list[CitationRecord], list[str], list[dict[str, Any]]]:
    data = query_data.get("data")
    data = data if isinstance(data, dict) else {}
    chunks = data.get("chunks")
    chunks = chunks if isinstance(chunks, list) else []

    documents = list(documents)
    document_map = {r.document_id: r for r in documents}
    source_uri_map: dict[str, KnowledgeDocumentRecord] = {}
    filename_map: dict[str, KnowledgeDocumentRecord] = {}
    for record in documents:
        if record.source_uri:
            source_uri_map[str(record.source_uri)] = record
            source_uri_map[Path(record.source_uri).name] = record
        filename_map[record.filename] = record

    citations: list[CitationRecord] = []
    matched_document_ids: list[str] = []
    debug_chunks: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str | None]] = set()

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        file_path = str(chunk.get("file_path") or "").strip()
        chunk_id = chunk.get("chunk_id")
        record = (
            document_map.get(file_path)
            or source_uri_map.get(file_path)
            or filename_map.get(Path(file_path).name)
        )
        document_id = record.document_id if record else ""
        if not document_id:
            continue
        dedupe_key = (document_id, str(chunk_id) if chunk_id else None)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        snippet = _truncate_text(str(chunk.get("content") or "").strip())
        citation = CitationRecord(
            document_id=document_id,
            filename=record.filename if record else Path(file_path).name or None,
            chunk_id=str(chunk_id) if chunk_id else None,
            block_type="text",
            snippet=snippet or None,
            metadata={
                "reference_id": chunk.get("reference_id"),
                "file_path": file_path,
            },
        )
        citations.append(citation)
        if document_id not in matched_document_ids:
            matched_document_ids.append(document_id)
        debug_chunks.append(
            {
                "document_id": document_id,
                "filename": citation.filename,
                "chunk_id": citation.chunk_id,
                "reference_id": chunk.get("reference_id"),
                "file_path": file_path,
                "content": str(chunk.get("content") or ""),
            }
        )

    return citations, matched_document_ids, debug_chunks


def _truncate_text(text: str, limit: int = 280) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_retrieval_sources(
    query_data: dict, documents: Iterable[KnowledgeDocumentRecord], top_k: int
) -> dict:
    """Use the opaque locator written during ingest; never guess from filenames."""
    if query_data.get("status") != "success":
        if query_data.get("metadata", {}).get("failure_reason") == "no_results":
            return {"status": "no_hit", "sources": []}
        raise ValueError("knowledge_retrieval_failed")
    chunks = query_data.get("data", {}).get("chunks", [])
    if not isinstance(chunks, list):
        raise TypeError("invalid_knowledge_chunks")
    records = {r.document_id: r for r in documents if r.overall_status == "ready"}
    sources = []
    seen = set()
    retrieval_id = uuid4().hex
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise TypeError("invalid_knowledge_chunk")
        record = records.get(chunk.get("file_path"))
        chunk_id = chunk.get("chunk_id")
        text = chunk.get("content")
        if (
            record is None
            or not isinstance(chunk_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", chunk_id)
        ):
            raise ValueError("unknown_knowledge_locator")
        if not isinstance(text, str) or not text.strip():
            continue
        key = (record.document_id, chunk_id)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "source_id": f"{retrieval_id}-{len(sources) + 1}",
                "document_id": record.document_id,
                "chunk_id": chunk_id,
                "title": f"[{len(sources) + 1}] {Path(record.filename).name[:160]}",
                "kind": "knowledge",
                "preview": text.strip()[:800],
                "truncated": len(text.strip()) > 800,
            }
        )
        if len(sources) >= top_k:
            break
    result = {"status": "ok" if sources else "no_hit", "sources": sources}
    while len(json.dumps(result, ensure_ascii=False).encode()) > 12 * 1024:
        largest = max(sources, key=lambda s: len(s["preview"].encode()))
        largest["preview"] = largest["preview"][: max(1, len(largest["preview"]) // 2)]
        largest["truncated"] = True
    return result
