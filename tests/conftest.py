import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.document_registry import KnowledgeDocumentRegistry
from src.knowledge.project_paths import build_knowledge_project_paths
from src.knowledge.publication import model_signature
from src.knowledge.schemas import KnowledgeDocumentRecord


@pytest.fixture
def published_config(tmp_path, monkeypatch):
    for key, value in {
        "LLM_BASE_URL": "http://127.0.0.1:1",
        "LLM_MODEL": "test-llm",
        "LLM_API_KEY": "test-key",
        "EMBEDDING_BASE_URL": "http://127.0.0.1:1",
        "EMBEDDING_MODEL": "test-embed",
    }.items():
        monkeypatch.setenv(key, value)
    config = KnowledgeServiceConfig(root_dir=tmp_path)
    scopes = {}
    for i, namespace in enumerate(("alpha", "beta"), 1):
        paths = build_knowledge_project_paths(namespace, config)
        paths.rag_workdir.mkdir(parents=True)
        registry = KnowledgeDocumentRegistry(paths)
        registry.register_document(
            KnowledgeDocumentRecord(
                document_id=f"kd_{i:032x}",
                project_id=namespace,
                filename="同名说明.md",
                source_type="local_file",
                source_uri="/PRIVATE/secret.md",
                overall_status="ready",
                index_status="ready",
                parse_status="parsed",
                last_error="SECRET",
            )
        )
        (paths.manifest_dir / "publication.json").write_text(
            json.dumps(model_signature())
        )
        scopes[str(i) * 32] = {
            "tenant_id": "__default",
            "project_id": f"00000000-0000-0000-0000-{i:012d}",
            "namespace": namespace,
        }
    monkeypatch.setenv("KNOWLEDGE_ROOT_DIR", str(tmp_path))
    monkeypatch.setenv("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON", json.dumps(scopes))
    return config
