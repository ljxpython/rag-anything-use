from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.knowledge.content_normalizer import normalize_content_list
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.parser_adapter import DoclingParserAdapter
from src.knowledge.project_paths import build_knowledge_project_paths
from src.knowledge.rag_engine import ProjectRAGEngine
from src.knowledge.schemas import KnowledgeDocumentRecord, KnowledgeOperationResult


class KnowledgeIngestService:
    def __init__(self, *, rag_engine: ProjectRAGEngine) -> None:
        self.rag_engine = rag_engine

    async def ingest_document(
        self,
        *,
        project_id: str,
        file_path: str,
        source_type: str = "local_file",
    ) -> KnowledgeOperationResult:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return KnowledgeOperationResult(
                accepted=False,
                project_id=project_id,
                operation="ingest_document",
                status="failed",
                message=f"file_not_found:{path}",
            )
        document_id = f"kd_{uuid4().hex}"
        record = KnowledgeDocumentRecord(
            document_id=document_id,
            project_id=project_id,
            filename=path.name,
            source_type=source_type,
            source_uri=str(path),
            parser_name=self.rag_engine.config.parser_name,
        )
        paths = build_knowledge_project_paths(project_id, self.rag_engine.config)
        registry = KnowledgeDocumentRegistry(paths)
        registry.register_document(record)
        rag = await self.rag_engine.get_rag(project_id)
        parser = DoclingParserAdapter(rag=rag, parser_name=record.parser_name)
        try:
            parsed = await parser.parse_file(path)
            normalized_content = normalize_content_list(
                parsed.content_list,
                document_id=document_id,
                filename=record.filename,
            )
            await self.rag_engine.ingest_content_list(
                project_id=project_id,
                document_id=document_id,
                content_list=normalized_content,
                file_path=str(path),
            )
            updated = record.model_copy(
                update={
                    "parse_status": "parsed",
                    "index_status": "ready",
                    "overall_status": "ready",
                    "page_count": parsed.metadata.get("page_count"),
                    "chunk_count": len(normalized_content),
                }
            )
            registry.update_document(updated)
            return KnowledgeOperationResult(
                accepted=True,
                project_id=project_id,
                document_id=document_id,
                operation="ingest_document",
                status="ingested",
                message="document_ingested",
            )
        except Exception as exc:
            failed = record.model_copy(
                update={
                    "parse_status": "failed",
                    "index_status": "failed",
                    "overall_status": "failed",
                    "last_error": str(exc),
                }
            )
            registry.update_document(failed)
            return KnowledgeOperationResult(
                accepted=False,
                project_id=project_id,
                document_id=document_id,
                operation="ingest_document",
                status="failed",
                message=str(exc),
            )
