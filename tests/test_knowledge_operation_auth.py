import asyncio
import json
import time
from uuid import uuid4

import httpx
import pytest

from src.knowledge.jobs import KnowledgeJobStore
from src.knowledge.operation_auth import (
    KnowledgeOperationAuthorizer,
    operation_identity,
    signed,
)
from test_knowledge_upload import fixture, stream


def mock_http(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs),
    )


def platform_grant(values, config):
    clock = int(time.time())
    return signed(
        {
            **values,
            "issuer": "platform-api",
            "audience": "rag-knowledge",
            "iat": clock,
            "exp": clock + 30,
            "nonce": uuid4().hex,
        },
        config,
        grant=True,
    )


def test_fresh_backend_requests_keep_persisted_origin_file_and_job_binding(
    online_services, monkeypatch
):
    s = online_services
    ref, grant = fixture(s)

    async def run():
        ticket = await s.uploads.stage_upload(
            s.scope, "request", ref, grant, stream(b"# content")
        )
        receipt = s.uploads.submit_document(s.scope, ticket["upload_id"], ref, grant)
        reopened = KnowledgeJobStore(s.config)
        identity = json.loads(reopened.get_job(receipt["job_id"])["identity"])
        assert identity == operation_identity(grant["values"])
        assert not set(identity) & {"issuer", "audience", "iat", "exp", "nonce"}
        requests = []

        def handler(request):
            envelope = json.loads(request.content)
            values = envelope["values"]
            assert envelope == signed(values, s.config)
            assert values["issuer"] == "rag-anything-use"
            assert values["audience"] == "platform-api"
            assert type(values["iat"]) is int and type(values["exp"]) is int
            assert values["iat"] <= time.time() < values["exp"]
            assert values["exp"] - values["iat"] == 30
            assert operation_identity(values) == identity
            assert values["knowledge_base_id"] == s.scope.knowledge_base_id
            assert values["job_id"] == receipt["job_id"]
            if values["operation"] == "activate":
                assert values["target_revision"] == "kg_" + "1" * 32
                assert type(values["base_revision"]) is int
                assert values["base_revision"] == 0
            requests.append(values)
            return httpx.Response(200, json=platform_grant(values, s.config))

        mock_http(monkeypatch, handler)
        authorizer = KnowledgeOperationAuthorizer(s.config)
        old_lease = {
            **identity,
            "issuer": "platform-api",
            "audience": "rag-knowledge",
            "iat": 1,
            "exp": 31,
            "nonce": "0" * 32,
        }
        await authorizer.authorize(
            s.scope, "start", old_lease, {"job_id": receipt["job_id"]}
        )
        await authorizer.authorize(
            s.scope,
            "activate",
            old_lease,
            {
                "job_id": receipt["job_id"],
                "target_revision": "kg_" + "1" * 32,
                "base_revision": 0,
            },
        )
        assert requests[0]["nonce"] != requests[1]["nonce"] != old_lease["nonce"]

    asyncio.run(run())


@pytest.mark.parametrize(
    "field",
    ["subject", "graph_id", "file_name", "sha256", "job_id", "target_revision", "exp"],
)
def test_backend_authorization_rejects_changed_or_expired_grant(
    online_services, monkeypatch, field
):
    s = online_services
    _, upload = fixture(s)
    identity = operation_identity(upload["values"])

    def handler(request):
        values = json.loads(request.content)["values"]
        grant = platform_grant(values, s.config)
        if field == "exp":
            grant["values"]["iat"] = int(time.time()) - 60
            grant["values"]["exp"] = int(time.time()) - 30
        else:
            grant["values"][field] = "changed"
        return httpx.Response(200, json=signed(grant["values"], s.config, grant=True))

    mock_http(monkeypatch, handler)
    with pytest.raises(ValueError, match="knowledge_authorization_denied"):
        asyncio.run(
            KnowledgeOperationAuthorizer(s.config).authorize(
                s.scope,
                "activate",
                identity,
                {
                    "job_id": "kj_" + "1" * 32,
                    "target_revision": "kg_1",
                    "base_revision": 0,
                },
            )
        )


def test_incomplete_legacy_identity_does_not_guess_origin(online_services, monkeypatch):
    s = online_services

    def unexpected_request(request):
        pytest.fail("Incomplete legacy identity must not be sent to the platform")

    mock_http(monkeypatch, unexpected_request)
    with pytest.raises(ValueError, match="knowledge_authorization_denied"):
        asyncio.run(
            KnowledgeOperationAuthorizer(s.config).authorize(
                s.scope, "start", s.identity, {"job_id": "kj_" + "1" * 32}
            )
        )
