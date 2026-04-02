from __future__ import annotations

from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.project_paths import build_knowledge_project_paths
from src.knowledge.rag_engine import ProjectRAGEngine


class KnowledgeAdminService:
    def __init__(self, *, rag_engine: ProjectRAGEngine) -> None:
        self.rag_engine = rag_engine

    def list_project_documents(
        self, *, project_id: str, status: str | None = None, limit: int = 20
    ) -> dict[str, object]:
        paths = build_knowledge_project_paths(project_id, self.rag_engine.config)
        registry = KnowledgeDocumentRegistry(paths)
        records = registry.list_documents(status=status, limit=limit)
        return {
            "project_id": project_id,
            "count": len(records),
            "documents": [record.model_dump() for record in records],
        }

    def get_document_status(self, *, project_id: str, document_id: str) -> dict[str, object]:
        paths = build_knowledge_project_paths(project_id, self.rag_engine.config)
        registry = KnowledgeDocumentRegistry(paths)
        record = registry.get_document(document_id)
        if record is None:
            return {
                "project_id": project_id,
                "document_id": document_id,
                "overall_status": "not_found",
                "parse_status": "not_found",
                "index_status": "not_found",
                "last_error": None,
            }
        return record.model_dump()
