import asyncio
import json
import tempfile
from pathlib import Path
from typing import Literal
import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.mcp_server import create_mcp_server
from src.knowledge.workspace_manager import TenantWorkspaceManager


# Platform contract models (extracted verbatim from runtime_service/tools/knowledge.py)
class _Source(BaseModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    document_id: str = Field(pattern=r"^kd_[a-f0-9]{32}$")
    chunk_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    title: str = Field(pattern=r"^\[\d{1,2}\] [^/\\\r\n]{1,160}$")
    kind: Literal["knowledge"]
    preview: str = Field(min_length=1)
    truncated: bool = Field(strict=True)


class _Locator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Literal["page", "slide", "unknown"]
    start: int | None = Field(strict=True, ge=1)
    end: int | None = Field(strict=True, ge=1)
    block_type: Literal["text", "image", "table", "equation"] | None

    @model_validator(mode="after")
    def valid_range(self):
        if self.unit == "unknown":
            if self.start is not None or self.end is not None:
                raise ValueError("unknown_locator_range")
        elif self.start is None or self.end is None or self.start > self.end:
            raise ValueError("invalid_locator_range")
        return self


class _SourceV2(_Source):
    locator: _Locator


class _ResultV1(BaseModel):
    status: Literal["ok", "no_hit"]
    sources: list[_Source] = Field(max_length=100)


class _ResultV2(BaseModel):
    status: Literal["ok", "no_hit"]
    sources_version: Literal[2]
    sources: list[_SourceV2] = Field(max_length=100)


def extract_payload(res):
    if hasattr(res, "content") and res.content:
        first = res.content[0]
        if hasattr(first, "text"):
            return json.loads(first.text)
    if hasattr(res, "structured_content") and res.structured_content:
        return res.structured_content
    if isinstance(res, dict):
        return res
    if hasattr(res, "data") and res.data is not None:
        return res.data
    return json.loads(str(res))


def test_fastmcp_gateway_contract_empty_query():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = TenantWorkspaceManager(Path(tmpdir))
            server = create_mcp_server(workspace_mgr=mgr)

            # 1. Query with blank string (sources_version=1)
            res1 = await server.call_tool(
                "mcp_query_project_knowledge",
                {"query": "", "sources_version": 1},
            )
            data1 = extract_payload(res1)
            validated_v1 = _ResultV1.model_validate(data1)
            assert validated_v1.status == "no_hit"
            assert len(validated_v1.sources) == 0

            # 2. Query with sources_version=2
            res2 = await server.call_tool(
                "mcp_query_project_knowledge",
                {"query": "   ", "sources_version": 2},
            )
            data2 = extract_payload(res2)
            validated_v2 = _ResultV2.model_validate(data2)
            assert validated_v2.status == "no_hit"
            assert validated_v2.sources_version == 2
            assert len(validated_v2.sources) == 0

            # 3. Document listing tools
            docs_res = await server.call_tool("mcp_list_project_knowledge_documents", {"limit": 10})
            docs_data = extract_payload(docs_res)
            assert docs_data.get("status") == "ok"
            assert isinstance(docs_data.get("documents"), list)

            # 4. Document status tool
            st_res = await server.call_tool("mcp_get_project_knowledge_document_status", {"document_id": "kd_test"})
            st_data = extract_payload(st_res)
            assert st_data.get("status") == "ok"
            assert st_data.get("document_id") == "kd_test"

    asyncio.run(_run())


def test_workspace_manager_lifecycle():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = TenantWorkspaceManager(Path(tmpdir))
            tenant_id = "__test_tenant"
            project_id = "test-project-123"

            # Verify active symlink creation
            active_dir = mgr.get_active_dir(tenant_id, project_id)
            assert active_dir.exists()
            assert active_dir.is_symlink()
            assert "rev_1" in str(active_dir.resolve())

            # Create candidate directory
            cand_dir = (
                mgr.get_project_dir(tenant_id, project_id)
                / "candidates"
                / "cand_test_01"
            )
            cand_dir.mkdir(parents=True, exist_ok=True)
            (cand_dir / "marker.txt").write_text("rev_2_data")

            # Test atomic publish
            next_rev = await mgr.atomic_publish_candidate(
                tenant_id, project_id, cand_dir
            )
            assert next_rev == 2

            # Verify active symlink now resolves to rev_2
            assert active_dir.resolve().name == "rev_2"
            assert (active_dir / "marker.txt").read_text() == "rev_2_data"

    asyncio.run(_run())
