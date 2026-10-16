import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from lightrag import QueryParam

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

load_dotenv(repo_root / ".env")

from src.knowledge.locator_resolver import LocatorResolver
from src.knowledge.workspace_manager import TenantWorkspaceManager


def build_default_workspace_manager() -> TenantWorkspaceManager:
    storage_root = os.environ.get(
        "KNOWLEDGE_STORAGE_ROOT", str(repo_root / "data" / "storage")
    )
    return TenantWorkspaceManager(Path(storage_root))


def create_mcp_server(
    workspace_mgr: Optional[TenantWorkspaceManager] = None,
    name: str = "knowledge-gateway",
) -> FastMCP:
    """Creates a production FastMCP server instance for platform knowledge integration."""
    mgr = workspace_mgr or build_default_workspace_manager()
    data_root = mgr.storage_root
    locator_resolver = LocatorResolver(data_root)

    server = FastMCP(name=name)

    def _resolve_scope_from_env() -> tuple[str, str]:
        """Resolves target tenant and project from platform token scopes or defaults."""
        token_scopes_json = os.environ.get("KNOWLEDGE_MCP_TOKEN_SCOPES_JSON")
        if token_scopes_json:
            try:
                scopes = json.loads(token_scopes_json)
                if scopes:
                    # Pick the first configured scope if available
                    first_scope = next(iter(scopes.values()))
                    return (
                        first_scope.get("tenant_id", "__default"),
                        first_scope.get(
                            "project_id", "11111111-1111-4111-8111-111111111111"
                        ),
                    )
            except Exception:
                pass
        return ("__default", "11111111-1111-4111-8111-111111111111")

    @server.tool()
    async def mcp_query_project_knowledge(
        query: str,
        top_k: int = 8,
        sources_version: int = 1,
    ) -> Dict[str, Any]:
        """Query project knowledge base with structured sources and locator support.

        Conforms strictly to ai-agent-platform _Result / _ResultV2 schema.
        """
        query = (query or "").strip()
        if not query or len(query) > 2000:
            out = {"status": "no_hit", "sources": []}
            if sources_version == 2:
                out["sources_version"] = 2
            return out

        top_k = max(1, min(int(top_k), 8))
        tenant_id, project_id = _resolve_scope_from_env()

        async with mgr.acquire_read_lease(tenant_id, project_id) as rag:
            res = await rag.aquery_data(
                query, param=QueryParam(mode="hybrid", top_k=top_k)
            )

        chunks = res.get("data", {}).get("chunks", [])
        sources = []
        seen = set()
        retrieval_id = uuid.uuid4().hex[:12]

        for idx, c in enumerate(chunks):
            content = (c.get("content") or "").strip()
            if not content:
                continue
            chunk_id = c.get("chunk_id") or f"chunk-{idx}"
            if chunk_id in seen:
                continue
            seen.add(chunk_id)

            file_path = c.get("file_path") or "document.pdf"
            doc_id = c.get("full_doc_id") or "kd_00000000000000000000000000000000"
            if chunk_id.startswith("kd_"):
                doc_id = chunk_id.split("-")[0]

            filename = Path(file_path).name
            clean_title = f"[{len(sources) + 1}] {filename}".replace("\n", " ").replace("\r", " ")

            src_item: Dict[str, Any] = {
                "source_id": f"{retrieval_id}-{len(sources) + 1}",
                "document_id": doc_id,
                "chunk_id": chunk_id,
                "title": clean_title,
                "kind": "knowledge",
                "preview": content[:800],
                "truncated": len(content) > 800,
            }

            if sources_version == 2:
                src_item["locator"] = locator_resolver.resolve_locator(
                    doc_id, filename, content
                )

            sources.append(src_item)
            if len(sources) >= top_k:
                break

        out: Dict[str, Any] = {
            "status": "ok" if sources else "no_hit",
            "sources": sources,
        }
        if sources_version == 2:
            out["sources_version"] = 2
        return out

    @server.tool()
    async def mcp_list_project_knowledge_documents(
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Lists registered documents in the active project knowledge base."""
        tenant_id, project_id = _resolve_scope_from_env()
        active_dir = mgr.get_active_dir(tenant_id, project_id)
        doc_status_file = active_dir / "kv_store_doc_status.json"

        documents = []
        if doc_status_file.exists():
            try:
                status_data = json.loads(doc_status_file.read_text(encoding="utf-8"))
                for doc_id, info in status_data.items():
                    documents.append(
                        {
                            "document_id": doc_id,
                            "filename": info.get("file_path", "document.pdf"),
                            "status": info.get("status", "ready"),
                        }
                    )
            except Exception:
                pass

        return {"status": "ok", "documents": documents[:limit]}

    @server.tool()
    async def mcp_get_project_knowledge_document_status(
        document_id: str,
    ) -> Dict[str, Any]:
        """Gets processing status of a specific document."""
        tenant_id, project_id = _resolve_scope_from_env()
        active_dir = mgr.get_active_dir(tenant_id, project_id)
        doc_status_file = active_dir / "kv_store_doc_status.json"

        overall_status = "not_found"
        if doc_status_file.exists():
            try:
                status_data = json.loads(doc_status_file.read_text(encoding="utf-8"))
                if document_id in status_data:
                    raw_st = status_data[document_id].get("status", "ready")
                    overall_status = "ready" if raw_st == "processed" else raw_st
            except Exception:
                pass

        return {
            "status": "ok",
            "document_id": document_id,
            "overall_status": overall_status,
        }

    return server


if __name__ == "__main__":
    host = os.environ.get("KNOWLEDGE_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("KNOWLEDGE_MCP_PORT", "8001"))
    path = os.environ.get("KNOWLEDGE_MCP_PATH", "/mcp")

    print(f"Starting production Knowledge FastMCP Server on {host}:{port}{path}...")
    mcp_app = create_mcp_server()
    mcp_app.run(transport="http", host=host, port=port, path=path)
