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


@pytest.fixture
def online_services(published_config, monkeypatch):
    import time
    from dataclasses import replace
    from types import SimpleNamespace
    from lightrag import LightRAG
    from lightrag.utils import EmbeddingFunc
    from scripts.verify_incremental_snapshot import Calls
    from src.knowledge import rag_engine as engine_module
    from src.knowledge.artifacts import processing_signature
    from src.knowledge.auth import KnowledgeScope
    from src.knowledge.jobs import KnowledgeJobStore
    from src.knowledge.generations import KnowledgeGenerationService
    from src.knowledge.upload_service import KnowledgeUploadService
    from src.knowledge.operation_auth import KnowledgeOperationAuthorizer, signed

    monkeypatch.setenv("EMBEDDING_DIM", "8")
    config = replace(
        published_config,
        online_enabled=True,
        authorize_url="http://127.0.0.1:1/authorize",
        authorization_key_id="test-key",
        authorization_secret="s" * 32,
    )
    calls = Calls()

    def build(workdir, **kwargs):
        return LightRAG(
            working_dir=workdir,
            workspace=kwargs["workspace"],
            llm_model_func=calls.llm,
            embedding_func=EmbeddingFunc(embedding_dim=8, func=calls.embed),
        )

    monkeypatch.setattr(engine_module, "build_lightrag", build)
    store = KnowledgeJobStore(config)
    signature = processing_signature(config)
    project = store.register(
        "__default", "00000000-0000-0000-0000-000000000001", signature, enabled=True
    )
    scope = KnowledgeScope(
        tenant_id=project["tenant_id"],
        project_id=project["project_id"],
        knowledge_base_id=project["id"],
    )

    class Platform(KnowledgeOperationAuthorizer):
        denied = False

        async def authorize(self, scope, operation, identity, expected):
            if self.denied:
                raise ValueError("knowledge_authorization_denied")
            return self.grant(scope, operation, {**identity, **expected})

        def grant(self, scope, operation, expected):
            clock = time.time()
            return signed(
                {
                    "issuer": "platform-api",
                    "audience": "rag-knowledge",
                    "iat": clock,
                    "exp": clock + 30,
                    "nonce": "n" * 32,
                    "operation": operation,
                    "tenant_id": scope.tenant_id,
                    "project_id": scope.project_id,
                    "knowledge_base_id": scope.knowledge_base_id,
                    **expected,
                },
                config,
                grant=True,
            )

    platform = Platform(config)
    identity = dict(
        subject="user1",
        principal_type="user",
        credential_id="credential1",
        resource_id="resource1",
        thread_id="thread1",
        run_id="run1",
        tool_call_id="call1",
    )
    return SimpleNamespace(
        config=config,
        store=store,
        signature=signature,
        scope=scope,
        identity=identity,
        authorizer=platform,
        calls=calls,
        uploads=KnowledgeUploadService(store, platform),
        generations=KnowledgeGenerationService(store, authorizer=platform),
    )
