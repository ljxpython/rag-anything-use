from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocumentRecord(BaseModel):
    document_id: str
    project_id: str
    filename: str
    source_type: str
    source_uri: str | None = None
    parser_name: str = "docling"
    parse_status: str = "registered"
    index_status: str = "pending"
    overall_status: str = "registered"
    page_count: int | None = None
    chunk_count: int | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationRecord(BaseModel):
    document_id: str
    filename: str | None = None
    chunk_id: str | None = None
    page_index: int | None = None
    block_type: str | None = None
    score: float | None = None
    snippet: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectKnowledgeQueryRequest(BaseModel):
    project_id: str
    query: str = Field(min_length=1)
    mode: str = "hybrid"
    top_k: int = Field(default=8, ge=1, le=50)
    document_ids: list[str] = Field(default_factory=list)
    include_citations: bool = True
    include_debug_chunks: bool = False


class ProjectKnowledgeQueryResponse(BaseModel):
    project_id: str
    query: str
    answer: str
    mode: str
    citations: list[CitationRecord] = Field(default_factory=list)
    matched_document_ids: list[str] = Field(default_factory=list)
    debug_chunks: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeOperationResult(BaseModel):
    accepted: bool
    project_id: str
    document_id: str | None = None
    operation: str
    status: str
    message: str = ""
