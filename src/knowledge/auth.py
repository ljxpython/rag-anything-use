"""Project credentials are server configuration, never tool arguments."""

from __future__ import annotations

import hmac
import json
import os
from uuid import UUID

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
)

from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.project_paths import build_knowledge_project_paths


class KnowledgeScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str
    project_id: str
    namespace: str | None = None
    knowledge_base_id: str | None = None

    @model_validator(mode="after")
    def select_mode(self):
        if (self.namespace is None) == (self.knowledge_base_id is None):
            raise ValueError("knowledge_scope_mode_required")
        if self.knowledge_base_id is not None:
            import re

            if not re.fullmatch(r"kb_[a-f0-9]{32}", self.knowledge_base_id):
                raise ValueError("invalid_knowledge_base_id")
        return self

    @field_validator("tenant_id", "project_id")
    @classmethod
    def canonical_uuid(cls, value: str, info: ValidationInfo) -> str:
        if info.field_name == "tenant_id" and value == "__default":
            return value
        if str(UUID(value)) != value:
            raise ValueError("canonical_uuid_required")
        return value


import jwt

class KnowledgeTokenVerifier(TokenVerifier):
    def __init__(self, config: KnowledgeServiceConfig):
        super().__init__(required_scopes=["knowledge:read"])
        self.config = config
        self.dynamic_secret = os.getenv("KNOWLEDGE_AUTHORIZATION_SECRET", "").strip()
        raw = json.loads(os.getenv("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON", "{}"))
        if not isinstance(raw, dict):
            raise ValueError("knowledge_token_scopes_required")
        if not raw and not self.dynamic_secret:
            raise ValueError("knowledge_token_scopes_required")
        self.token_scopes: dict[str, KnowledgeScope] = {}
        owners: dict[str, tuple[str, str]] = {}
        for token, value in raw.items():
            if not isinstance(token, str) or len(token) < 32 or token != token.strip():
                raise ValueError("invalid_knowledge_token")
            scope = KnowledgeScope.model_validate(value)
            if scope.namespace is not None:
                build_knowledge_project_paths(scope.namespace, config)
            else:
                from src.knowledge.jobs import KnowledgeJobStore

                project = KnowledgeJobStore(config).project(scope.knowledge_base_id)
                if (project["tenant_id"], project["project_id"]) != (
                    scope.tenant_id,
                    scope.project_id,
                ):
                    raise ValueError("knowledge_scope_denied")
            owner = (scope.tenant_id, scope.project_id)
            resource = scope.namespace or scope.knowledge_base_id
            if resource in owners and owners[resource] != owner:
                raise ValueError("knowledge_namespace_scope_conflict")
            owners[resource] = owner
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
        if self.dynamic_secret:
            try:
                payload = jwt.decode(
                    token,
                    self.dynamic_secret,
                    algorithms=["HS256"],
                    audience="rag-service",
                    options={"require": ["tenant_id", "project_id", "knowledge_base_id", "exp"]},
                )
                scope = KnowledgeScope(
                    tenant_id=payload["tenant_id"],
                    project_id=payload["project_id"],
                    knowledge_base_id=payload["knowledge_base_id"],
                )
                from src.knowledge.jobs import KnowledgeJobStore

                KnowledgeJobStore(self.config).ensure_project(
                    scope.knowledge_base_id, scope.tenant_id, scope.project_id
                )
                self.token_scopes[token] = scope
                return AccessToken(
                    token=token,
                    client_id=scope.project_id,
                    scopes=["knowledge:read"],
                    claims=scope.model_dump(),
                )
            except (jwt.PyJWTError, ValueError, KeyError):
                pass
        return None


def resolve_knowledge_scope(verifier: KnowledgeTokenVerifier) -> KnowledgeScope:
    token = get_access_token()
    # Stdio is an explicitly scoped administrator client, not an unauthenticated fallback.
    if token is None and os.getenv("MCP_TRANSPORT", "http") == "stdio":
        scope = verifier.token_scopes.get(os.getenv("KNOWLEDGE_STDIO_TOKEN", ""))
    elif token is not None:
        scope = verifier.token_scopes.get(token.token)
        if scope is None and token.claims:
            try:
                scope = KnowledgeScope.model_validate(token.claims)
            except Exception:
                scope = None
    else:
        scope = None
    if scope is None:
        raise ToolError("knowledge_scope_denied")
    return scope
