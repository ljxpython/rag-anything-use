"""Verify platform operation leases; static project Bearer never grants writes."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from uuid import uuid4

import httpx

from src.knowledge.config import KnowledgeServiceConfig


def canonical(values):
    return json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def signed(values, config, *, grant=False):
    domain = "knowledge-operation-grant" if grant else "knowledge-operation-request"
    return {
        "version": 1,
        "key_id": config.authorization_key_id,
        "values": values,
        "signature": hmac.new(
            config.authorization_secret.encode(),
            (domain + "\n" + canonical(values)).encode(),
            hashlib.sha256,
        ).hexdigest(),
    }


class KnowledgeOperationAuthorizer:
    def __init__(self, config: KnowledgeServiceConfig):
        self.config = config

    @property
    def configured(self):
        return bool(
            self.config.authorize_url
            and self.config.authorization_key_id
            and len(self.config.authorization_secret) >= 32
        )

    def verify(self, envelope, scope, operation, expected):
        try:
            if (
                not self.config.authorization_key_id
                or len(self.config.authorization_secret) < 32
            ):
                raise ValueError
            if isinstance(envelope, str):
                if len(envelope.encode()) > 8192:
                    raise ValueError
                envelope = json.loads(envelope)
            values = envelope["values"]
            if (
                set(envelope) != {"version", "key_id", "values", "signature"}
                or type(envelope["version"]) is not int
                or envelope["version"] != 1
                or envelope["key_id"] != self.config.authorization_key_id
                or not isinstance(values, dict)
            ):
                raise ValueError
            signature = envelope["signature"]
            if (
                not isinstance(signature, str)
                or not re.fullmatch("[a-f0-9]{64}", signature)
                or not hmac.compare_digest(
                    signature, signed(values, self.config, grant=True)["signature"]
                )
            ):
                raise ValueError
            clock = time.time()
            if (
                values["issuer"] != "platform-api"
                or values["audience"] != "rag-knowledge"
                or values["operation"] != operation
                or values["tenant_id"] != scope.tenant_id
                or values["project_id"] != scope.project_id
                or values["knowledge_base_id"] != scope.knowledge_base_id
                or type(values["iat"]) is not int
                or type(values["exp"]) is not int
                or not clock - 30 <= values["iat"] <= clock
                or not clock < values["exp"] <= values["iat"] + 30
                or not isinstance(values["nonce"], str)
                or not re.fullmatch("[a-f0-9]{32}", values["nonce"])
                or any(values.get(key) != value for key, value in expected.items())
            ):
                raise ValueError
            required = ("subject", "principal_type", "resource_id", "request_id")
            if any(
                not isinstance(values.get(key), str) or not 0 < len(values[key]) <= 256
                for key in required
            ):
                raise ValueError
            if "credential_id" not in values or (
                values["credential_id"] is not None
                and not isinstance(values["credential_id"], str)
            ):
                raise ValueError
            if any(
                not isinstance(values.get(key), str) or not values[key]
                for key in ("thread_id", "run_id", "tool_call_id")
            ):
                raise ValueError
            if values.get("graph_id") not in {"dearflow_agent", "showcase_demo"}:
                raise ValueError
            operation_identity(values)
            return values
        except (KeyError, TypeError, ValueError):
            raise ValueError("knowledge_authorization_denied") from None

    async def authorize(self, scope, operation, identity, expected):
        if not self.configured:
            raise ValueError("knowledge_authorization_unavailable")
        try:
            binding = {**operation_identity(identity), **expected}
            clock = int(time.time())
            values = {
                **binding,
                "operation": operation,
                "tenant_id": scope.tenant_id,
                "project_id": scope.project_id,
                "knowledge_base_id": scope.knowledge_base_id,
                "issuer": "rag-anything-use",
                "audience": "platform-api",
                "iat": clock,
                "exp": clock + 30,
                "nonce": uuid4().hex,
            }
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.post(
                    self.config.authorize_url, json=signed(values, self.config)
                )
                response.raise_for_status()
                envelope = response.json()
                self.verify(envelope, scope, operation, binding)
                return envelope
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise ValueError("knowledge_authorization_denied") from None


def operation_identity(values):
    return {
        key: values[key]
        for key in (
            "subject",
            "principal_type",
            "credential_id",
            "resource_id",
            "request_id",
            "graph_id",
            "thread_id",
            "run_id",
            "tool_call_id",
            "sha256",
            "size_bytes",
            "file_name",
            "mime_type",
        )
    }
