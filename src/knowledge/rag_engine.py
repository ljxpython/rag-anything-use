from __future__ import annotations

import asyncio
from pathlib import Path

from lightrag import QueryParam
from raganything import RAGAnything
from lightrag.kg.shared_storage import initialize_pipeline_status

from src.demo_support import build_lightrag, build_raganything
from src.knowledge.citations import build_query_result_artifacts
from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.project_paths import (
    KnowledgeProjectPaths,
    build_knowledge_project_paths,
)
from src.knowledge.schemas import (
    CitationRecord,
    ProjectKnowledgeQueryRequest,
    ProjectKnowledgeQueryResponse,
)


class ProjectRAGEngine:
    def __init__(self, config: KnowledgeServiceConfig) -> None:
        self.config = config
        self._rag_cache: dict[str, RAGAnything] = {}

    def get_project_paths(self, project_id: str) -> KnowledgeProjectPaths:
        return build_knowledge_project_paths(project_id, self.config)

    async def ensure_project_dirs(self, project_id: str) -> KnowledgeProjectPaths:
        paths = self.get_project_paths(project_id)
        await asyncio.gather(
            *[
                asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
                for path in paths.as_path_list()
            ]
        )
        return paths

    async def get_rag(self, project_id: str) -> RAGAnything:
        cached = self._rag_cache.get(project_id)
        if cached is not None:
            return cached
        paths = await self.ensure_project_dirs(project_id)
        lightrag = build_lightrag(str(paths.rag_workdir))
        await lightrag.initialize_storages()
        await initialize_pipeline_status()
        rag = build_raganything(
            working_dir=str(paths.rag_workdir),
            lightrag=lightrag,
            enable_image_processing=self.config.enable_image_processing,
            enable_table_processing=self.config.enable_table_processing,
            enable_equation_processing=self.config.enable_equation_processing,
        )
        self._rag_cache[project_id] = rag
        return rag

    async def ingest_content_list(
        self,
        *,
        project_id: str,
        document_id: str,
        content_list: list[dict],
        file_path: str | None = None,
    ) -> dict[str, object]:
        paths = await self.ensure_project_dirs(project_id)
        rag = await self.get_rag(project_id)
        await rag.insert_content_list(
            content_list=content_list,
            file_path=file_path or document_id,
            doc_id=document_id,
        )
        return {
            "project_id": project_id,
            "document_id": document_id,
            "content_count": len(content_list),
            "working_dir": str(paths.rag_workdir),
            "status": "ingested",
        }

    async def query(
        self, request: ProjectKnowledgeQueryRequest
    ) -> ProjectKnowledgeQueryResponse:
        rag = await self.get_rag(request.project_id)
        query_mode = request.mode or self.config.query_default_mode
        query_top_k = request.top_k or self.config.query_default_top_k
        query_param = QueryParam(
            mode=query_mode,
            top_k=query_top_k,
            chunk_top_k=query_top_k,
            include_references=request.include_citations or request.include_debug_chunks,
            enable_rerank=False,
        )
        retrieval_data = await rag.lightrag.aquery_data(
            request.query,
            param=query_param,
        )
        answer = await rag.aquery(
            request.query,
            mode=query_mode,
            top_k=query_top_k,
            chunk_top_k=query_top_k,
            include_references=request.include_citations,
            enable_rerank=False,
            vlm_enhanced=False,
        )
        citations: list[CitationRecord] = []
        matched_document_ids: list[str] = []
        debug_chunks: list[dict[str, object]] = []
        if request.include_citations or request.include_debug_chunks:
            registry = KnowledgeDocumentRegistry(
                build_knowledge_project_paths(request.project_id, self.config)
            )
            documents = registry.list_documents(limit=10_000)
            citations, matched_document_ids, debug_chunks = build_query_result_artifacts(
                retrieval_data,
                documents=documents,
            )
        return ProjectKnowledgeQueryResponse(
            project_id=request.project_id,
            query=request.query,
            answer=str(answer),
            mode=query_mode,
            citations=citations if request.include_citations else [],
            matched_document_ids=matched_document_ids,
            debug_chunks=debug_chunks if request.include_debug_chunks else [],
        )

    async def debug_retrieve(
        self, request: ProjectKnowledgeQueryRequest
    ) -> dict[str, object]:
        paths = await self.ensure_project_dirs(request.project_id)
        rag = await self.get_rag(request.project_id)
        query_mode = request.mode or self.config.query_default_mode
        query_top_k = request.top_k or self.config.query_default_top_k
        query_data = await rag.lightrag.aquery_data(
            request.query,
            param=QueryParam(
                mode=query_mode,
                top_k=query_top_k,
                chunk_top_k=query_top_k,
                include_references=True,
                enable_rerank=False,
            ),
        )
        registry = KnowledgeDocumentRegistry(
            build_knowledge_project_paths(request.project_id, self.config)
        )
        citations, matched_document_ids, debug_chunks = build_query_result_artifacts(
            query_data,
            documents=registry.list_documents(limit=10_000),
        )
        return {
            "project_id": request.project_id,
            "query": request.query,
            "mode": query_mode,
            "top_k": query_top_k,
            "working_dir": str(paths.rag_workdir),
            "matched_document_ids": matched_document_ids,
            "citations": [citation.model_dump() for citation in citations],
            "chunks": debug_chunks,
            "raw_data": query_data,
            "status": query_data.get("status", "unknown"),
        }

    @staticmethod
    def resolve_path(path: str | Path) -> str:
        return str(Path(path).expanduser().resolve())
