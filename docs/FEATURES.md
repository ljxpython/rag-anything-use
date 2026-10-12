# 功能现状总览

最后更新：2026-10-12

## MCP 查询服务（`src/mcp_server.py`）

| 功能 | 状态 |
|---|---|
| `mcp_query_project_knowledge(query, top_k=8)` | ✅ 生产可用 |
| `list_project_knowledge_documents(limit=20)` | ✅ 生产可用 |
| `get_project_knowledge_document_status(document_id)` | ✅ 生产可用 |
| Streamable HTTP `/mcp` + Bearer 鉴权 | ✅ 生产可用 |
| stdio 模式（管理员专用） | ✅ 可用 |

## CLI 管理工具（`src/cli.py`）

| 命令 | 状态 |
|---|---|
| `ingest --project-id --file` | ✅ 可用（UTF-8 文本） |
| `publish --project-id` | ✅ 可用 |
| `list-docs --project-id` | ✅ 可用 |
| `query --project-id` | ✅ 管理员诊断用 |
| `debug-retrieve --project-id` | ✅ 管理员诊断用 |
| PDF/Office 入库（`--extra documents`） | ⚠️ 需 ARM Mac 或兼容 Linux |
