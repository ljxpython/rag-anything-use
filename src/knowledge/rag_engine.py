from __future__ import annotations

import asyncio
import hashlib
import logging
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from lightrag import LightRAG, QueryParam

if TYPE_CHECKING:
    from raganything import RAGAnything
from lightrag.kg.shared_storage import initialize_pipeline_status

from src.demo_support import build_lightrag, build_raganything
from src.knowledge.citations import (
    build_query_result_artifacts,
    build_retrieval_sources,
)
from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.project_paths import (
    KnowledgeProjectPaths,
    build_knowledge_project_paths,
)
from src.knowledge.publication import validate_publication
from src.knowledge.schemas import (
    CitationRecord,
    KnowledgeRetrievalRequest,
    ProjectKnowledgeQueryRequest,
    ProjectKnowledgeQueryResponse,
)

logger = logging.getLogger(__name__)
CHUNK_DOCUMENT = ContextVar("knowledge_chunk_document", default=None)


def install_document_chunk_ids():
    from lightrag import lightrag as native

    if getattr(native.compute_mdhash_id, "_knowledge_document_scoped", False):
        return
    original = native.compute_mdhash_id

    def scoped(content, prefix=""):
        document = CHUNK_DOCUMENT.get()
        return original(
            document + "\n" + content if prefix == "chunk-" and document else content,
            prefix=prefix,
        )

    scoped._knowledge_document_scoped = True
    native.compute_mdhash_id = scoped


def storage_workspace(paths: KnowledgeProjectPaths) -> str:
    return "kb_" + hashlib.sha256(str(paths.project_dir).encode()).hexdigest()[:24]


async def storage_io(function, *args, **kwargs):
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # A cancelled to_thread keeps writing; join it before deleting its reader directory.
        await asyncio.gather(task, return_exceptions=True)
        raise


class ProjectRAGEngine:
    def __init__(self, config: KnowledgeServiceConfig, *, usage=None) -> None:
        self.config = config
        self.usage = usage
        self._rag_cache: dict[str, RAGAnything] = {}
        self._lightrag_cache: dict[str, LightRAG] = {}
        self._init_lock = asyncio.Lock()

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
        paths = self.get_project_paths(project_id)
        lightrag = await self.get_lightrag(project_id)
        rag = build_raganything(
            working_dir=str(paths.rag_workdir),
            lightrag=lightrag,
            enable_image_processing=self.config.enable_image_processing,
            enable_table_processing=self.config.enable_table_processing,
            enable_equation_processing=self.config.enable_equation_processing,
        )
        self._rag_cache[project_id] = rag
        return rag

    async def get_lightrag(self, project_id: str) -> LightRAG:
        async with self._init_lock:
            if project_id in self._lightrag_cache:
                return self._lightrag_cache[project_id]
            paths = await self.ensure_project_dirs(project_id)
            workspace = storage_workspace(paths)
            kwargs = {"workspace": workspace}
            if self.usage is not None:
                kwargs["usage"] = self.usage
            rag = await storage_io(build_lightrag, str(paths.rag_workdir), **kwargs)
            try:
                async with asyncio.timeout(60):
                    await rag.initialize_storages()
                    await initialize_pipeline_status(workspace=workspace)
            except BaseException:
                try:
                    await self._close_lightrag(rag)
                except Exception as cleanup_error:  # noqa: BLE001 - preserve the initialization failure
                    logger.warning(
                        "knowledge_engine_cleanup_failed: %s",
                        type(cleanup_error).__name__,
                    )
                raise
            self._lightrag_cache[project_id] = rag
            return rag

    async def close(self) -> None:
        results = await asyncio.gather(
            *(self._close_lightrag(rag) for rag in self._lightrag_cache.values()),
            return_exceptions=True,
        )
        self._lightrag_cache.clear()
        self._rag_cache.clear()
        for result in results:
            if isinstance(result, BaseException):
                raise result

    @staticmethod
    async def _close_lightrag(rag: LightRAG) -> None:
        async with asyncio.timeout(30):
            await rag.finalize_storages()

    async def retrieve(
        self, namespace: str, request: KnowledgeRetrievalRequest
    ) -> dict:
        documents = validate_publication(self.get_project_paths(namespace))
        rag = await self.get_lightrag(namespace)
        async with asyncio.timeout(60):
            data = await rag.aquery_data(
                request.query,
                param=QueryParam(
                    mode="hybrid",
                    top_k=request.top_k,
                    chunk_top_k=request.top_k,
                    include_references=True,
                    enable_rerank=False,
                ),
            )
        return build_retrieval_sources(data, documents, request.top_k)

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
            file_path=document_id,
            doc_id=document_id,
        )
        await self.assert_document_ready(project_id, document_id)
        return {
            "project_id": project_id,
            "document_id": document_id,
            "content_count": len(content_list),
            "working_dir": str(paths.rag_workdir),
            "status": "ingested",
        }

    async def ingest_text(
        self, project_id: str, document_id: str, text: str, *, document_chunks=False
    ) -> None:
        rag = await self.get_lightrag(project_id)
        # Native content-only chunk IDs overwrite sources across distinct originals.
        if document_chunks:
            install_document_chunk_ids()
        token = CHUNK_DOCUMENT.set(document_id if document_chunks else None)
        try:
            await rag.ainsert(text, ids=document_id, file_paths=document_id)
        finally:
            CHUNK_DOCUMENT.reset(token)
        await self.assert_document_ready(project_id, document_id)

    async def assert_document_ready(self, project_id: str, document_id: str) -> None:
        rag = await self.get_lightrag(project_id)
        record = await rag.doc_status.get_by_id(document_id)
        if not isinstance(record, dict) or record.get("status") != "processed":
            raise ValueError("knowledge_document_index_failed")

    async def query(
        self, request: ProjectKnowledgeQueryRequest
    ) -> ProjectKnowledgeQueryResponse:
        rag = await self.get_lightrag(request.project_id)
        query_mode = request.mode or self.config.query_default_mode
        query_top_k = request.top_k or self.config.query_default_top_k
        query_param = QueryParam(
            mode=query_mode,
            top_k=query_top_k,
            chunk_top_k=query_top_k,
            include_references=request.include_citations
            or request.include_debug_chunks,
            enable_rerank=False,
        )
        retrieval_data = await rag.aquery_data(
            request.query,
            param=query_param,
        )
        answer = await rag.aquery(
            request.query,
            param=query_param,
        )
        citations: list[CitationRecord] = []
        matched_document_ids: list[str] = []
        debug_chunks: list[dict[str, object]] = []
        if request.include_citations or request.include_debug_chunks:
            registry = KnowledgeDocumentRegistry(
                build_knowledge_project_paths(request.project_id, self.config)
            )
            documents = registry.list_documents(limit=10_000)
            citations, matched_document_ids, debug_chunks = (
                build_query_result_artifacts(
                    retrieval_data,
                    documents=documents,
                )
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
        rag = await self.get_lightrag(request.project_id)
        query_mode = request.mode or self.config.query_default_mode
        query_top_k = request.top_k or self.config.query_default_top_k
        query_data = await rag.aquery_data(
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
