"""Project credentials are server configuration, never tool arguments."""

from __future__ import annotations

import hmac
import json
import os
from uuid import UUID

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.project_paths import build_knowledge_project_paths


class KnowledgeScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str
    project_id: str
    namespace: str

    @field_validator("tenant_id", "project_id")
    @classmethod
    def canonical_uuid(cls, value: str, info: ValidationInfo) -> str:
        if info.field_name == "tenant_id" and value == "__default":
            return value
        if str(UUID(value)) != value:
            raise ValueError("canonical_uuid_required")
        return value


class KnowledgeTokenVerifier(TokenVerifier):
    def __init__(self, config: KnowledgeServiceConfig):
        super().__init__(required_scopes=["knowledge:read"])
        raw = json.loads(os.getenv("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON", "{}"))
        if not isinstance(raw, dict) or not raw:
            raise ValueError("knowledge_token_scopes_required")
        self.token_scopes: dict[str, KnowledgeScope] = {}
        owners: dict[str, tuple[str, str]] = {}
        for token, value in raw.items():
            if not isinstance(token, str) or len(token) < 32 or token != token.strip():
                raise ValueError("invalid_knowledge_token")
            scope = KnowledgeScope.model_validate(value)
            build_knowledge_project_paths(scope.namespace, config)
            owner = (scope.tenant_id, scope.project_id)
            if scope.namespace in owners and owners[scope.namespace] != owner:
                raise ValueError("knowledge_namespace_scope_conflict")
            owners[scope.namespace] = owner
            self.token_scopes[token] = scope

    async def verify_token(self, token: str) -> AccessToken | None:
        for configured, scope in self.token_scopes.items():
            if hmac.compare_digest(configured.encode(), token.encode()):
                return AccessToken(
                    token=token,
                    client_id=scope.project_id,
                    scopes=["knowledge:read"],
                    claims=scope.model_dump(),
                )
        return None


def resolve_knowledge_scope(verifier: KnowledgeTokenVerifier) -> KnowledgeScope:
    token = get_access_token()
    # Stdio is an explicitly scoped administrator client, not an unauthenticated fallback.
    if token is None and os.getenv("MCP_TRANSPORT", "http") == "stdio":
        scope = verifier.token_scopes.get(os.getenv("KNOWLEDGE_STDIO_TOKEN", ""))
    else:
        scope = verifier.token_scopes.get(token.token) if token is not None else None
    if scope is None:
        raise ToolError("knowledge_scope_denied")
    return scope
