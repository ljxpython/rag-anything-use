from __future__ import annotations

import json
from pathlib import Path

from src.knowledge.project_paths import KnowledgeProjectPaths
from src.knowledge.schemas import KnowledgeDocumentRecord


class KnowledgeDocumentRegistry:
    def __init__(self, paths: KnowledgeProjectPaths) -> None:
        self.paths = paths
        self.registry_path = self.paths.manifest_dir / "documents.json"

    def _load(self) -> dict[str, dict]:
        if not self.registry_path.exists():
            return {}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _save(self, payload: dict[str, dict]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def register_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocumentRecord:
        payload = self._load()
        payload[record.document_id] = record.model_dump()
        self._save(payload)
        return record

    def update_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocumentRecord:
        return self.register_document(record)

    def list_documents(self, *, status: str | None = None, limit: int = 20) -> list[KnowledgeDocumentRecord]:
        payload = self._load()
        records = [KnowledgeDocumentRecord(**item) for item in payload.values()]
        if status:
            records = [record for record in records if record.overall_status == status]
        return records[:limit]

    def get_document(self, document_id: str) -> KnowledgeDocumentRecord | None:
        payload = self._load()
        item = payload.get(document_id)
        if item is None:
            return None
        return KnowledgeDocumentRecord(**item)
