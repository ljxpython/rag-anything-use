from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.knowledge.schemas import KnowledgeDocumentRecord
from src.knowledge.schemas import CitationRecord


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
        record = source_uri_map.get(file_path) or filename_map.get(Path(file_path).name)
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
