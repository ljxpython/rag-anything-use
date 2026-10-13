# 功能现状总览

最后更新：2026-10-13；Ubuntu在线文档与多模态、来源v2及临时平台文档联验完成；旧供应商使用已清理，文本／视觉统一DeepSeek。剩余开发与验收、Ubuntu用途见[剩余事项](remaining-work.md)。

## MCP 查询服务（`src/mcp_server.py`）

| 功能 | 状态 |
|---|---|
| `mcp_query_project_knowledge(query, top_k=8, sources_version=1)` | ✅ 默认v1兼容，显式v2可信page／slide／unknown；平台v2展示待接入 |
| `list_project_knowledge_documents(limit=20)` | ✅ 生产可用 |
| `get_project_knowledge_document_status(document_id)` | ✅ 生产可用 |
| Streamable HTTP `/mcp` + Bearer 鉴权 | ✅ 生产可用 |
| stdio 模式（管理员专用） | ✅ 可用 |

## 在线入库（RAG文档／图片实现完成，默认关闭）

| 功能 | 状态 | 方案 |
|---|---|---|
| `mcp_submit_project_knowledge_document(file_ref)` / `mcp_get_project_knowledge_ingest_job(job_id)`、内部安全GET/原字节PUT | ✅ RAG及临时union实际Agent／Worker／浏览器文档链和撤权／Stop／重启／Fork通过；正式平台未合入部署，图片ImageRef收据待协同 | [接线交接](projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md) |
| 后台精确授权字段/新租约、同request_id失ACK只读GET | ✅ 78项回归及实际平台HTTP/真实模型通过，Thread删除继续/撤权拒绝/新写暂停后回查；旧缺来源任务不自动补造 | [契约修复](projects/20261012-rag-provider-contract-alignment/README.md) |
| SHA-256原件唯一、持久任务幂等/复用、成果签名、完整快照候选原生增量 | ✅ 恢复/重复0新入库调用；失败隔离/回退/lease及10次mock回收通过 | [G01证据](projects/20261012-project-member-knowledge-upload/implementation/g01-evidence.md) · [实施验收](projects/20261012-project-member-knowledge-upload/implementation/rag-evidence.md) |
| 格式能力 | UTF-8 MD/TXT；完整documents配置支持PDF／DOCX／PPTX／PNG／JPEG，受管资产hash校验／恢复；能力按依赖及开关声明 | [在线文档专项](projects/20261013-online-documents/README.md) |

## CLI 管理工具（`src/cli.py`）

| 命令 | 状态 |
|---|---|
| `ingest --project-id --file` | ✅ 可用（UTF-8 文本） |
| `publish --project-id` | ✅ 可用 |
| `list-docs --project-id` | ✅ 可用 |
| `query --project-id` | ✅ 管理员诊断用 |
| `debug-retrieve --project-id` | ✅ 管理员诊断用 |
| `init-project-knowledge` / `migrate-project-knowledge` / `activate-knowledge-generation` | ✅ 管理员注册/完整旧库迁移/显式上传启停与回退；本机隔离验证通过 |
| PDF/Office 入库（`--extra documents`） | ✅ Ubuntu五格式完整链与13事实通过；PNG／JPEG真实模型入库／恢复通过；Intel Mac仍缺锁定Torch wheel |
