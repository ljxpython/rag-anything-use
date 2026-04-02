from __future__ import annotations

from src.knowledge.rag_engine import ProjectRAGEngine
from src.knowledge.schemas import (
    ProjectKnowledgeQueryRequest,
    ProjectKnowledgeQueryResponse,
)


class KnowledgeQueryService:
    def __init__(self, *, rag_engine: ProjectRAGEngine) -> None:
        self.rag_engine = rag_engine

    async def query_project_knowledge(
        self, request: ProjectKnowledgeQueryRequest
    ) -> ProjectKnowledgeQueryResponse:
        return await self.rag_engine.query(request)
