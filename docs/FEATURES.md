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

## 在线入库（RAG文本范围完成，默认关闭）

| 功能 | 状态 | 方案 |
|---|---|---|
| `mcp_submit_project_knowledge_document(file_ref)` / `mcp_get_project_knowledge_ingest_job(job_id)`、内部安全GET/原字节PUT | ✅ RAG实现及真实worker/HTTP/MCP通过；平台/Runtime/前端接线待联合验收，非线上能力 | [接线交接](projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md) |
| SHA-256原件唯一、持久任务幂等/复用、成果签名、完整快照候选原生增量 | ✅ 恢复/重复0新入库调用；失败隔离/回退/lease及10次mock回收通过 | [G01证据](projects/20261012-project-member-knowledge-upload/implementation/g01-evidence.md) · [实施验收](projects/20261012-project-member-knowledge-upload/implementation/rag-evidence.md) |
| 格式能力 | UTF-8 MD/TXT；PDF/Office未开放，待兼容Linux逐格式验收 | [方案与前端交接](projects/20261012-project-member-knowledge-upload/README.md) |

## CLI 管理工具（`src/cli.py`）

| 命令 | 状态 |
|---|---|
| `ingest --project-id --file` | ✅ 可用（UTF-8 文本） |
| `publish --project-id` | ✅ 可用 |
| `list-docs --project-id` | ✅ 可用 |
| `query --project-id` | ✅ 管理员诊断用 |
| `debug-retrieve --project-id` | ✅ 管理员诊断用 |
| `init-project-knowledge` / `migrate-project-knowledge` / `activate-knowledge-generation` | ✅ 管理员注册/完整旧库迁移/显式上传启停与回退；本机隔离验证通过 |
| PDF/Office 入库（`--extra documents`） | ⚠️ 需 ARM Mac 或兼容 Linux |
