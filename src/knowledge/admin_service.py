from __future__ import annotations

from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.project_paths import build_knowledge_project_paths
from src.knowledge.rag_engine import ProjectRAGEngine


class KnowledgeAdminService:
    def __init__(self, *, rag_engine: ProjectRAGEngine) -> None:
        self.rag_engine = rag_engine

    def list_project_documents(
        self,
        *,
        project_id: str,
        status: str | None = None,
        limit: int = 20,
        public: bool = False,
    ) -> dict[str, object]:
        paths = build_knowledge_project_paths(project_id, self.rag_engine.config)
        registry = KnowledgeDocumentRegistry(paths)
        records = registry.list_documents(status=status, limit=limit)
        if public:
            return {
                "count": len(records),
                "documents": [self.public_record(r.model_dump()) for r in records],
            }
        return {
            "project_id": project_id,
            "count": len(records),
            "documents": [
                self.public_record(record.model_dump())
                if public
                else record.model_dump()
                for record in records
            ],
        }

    def get_document_status(
        self, *, project_id: str, document_id: str, public: bool = False
    ) -> dict[str, object]:
        paths = build_knowledge_project_paths(project_id, self.rag_engine.config)
        registry = KnowledgeDocumentRegistry(paths)
        record = registry.get_document(document_id)
        if record is None:
            if public:
                return {"document_id": document_id, "overall_status": "not_found"}
            return {
                "project_id": project_id,
                "document_id": document_id,
                "overall_status": "not_found",
                "parse_status": "not_found",
                "index_status": "not_found",
                "last_error": None,
            }
        return (
            self.public_record(record.model_dump()) if public else record.model_dump()
        )

    @staticmethod
    def public_record(record: dict) -> dict:
        return {
            key: record[key]
            for key in (
                "document_id",
                "filename",
                "overall_status",
                "parse_status",
                "index_status",
            )
        }
