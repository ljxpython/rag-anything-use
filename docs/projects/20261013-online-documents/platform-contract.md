# 平台字段与展示协同方案

状态：RAG v2 已实现；临时 union 的 FileRef 文档上传及真实浏览器／Worker／生命周期联验通过。平台正式合入、v2 展示和 ImageRef 可信收据待按本方案实施，不直接覆盖主工作区。

## 版本与合并基线

指定平台主工作区 `/Users/lijiaxin/PyCharmMiscProject/ai-agent-platform` 的 `feat/langgraph-v3-delta-evaluation`（06d94130）含 Token 看板、用量投影、后台回执；知识专项在 6394 worktree（7fbf1ba3 加未提交代码）。联验使用独立 rag-union-20261013 worktree，三方组合双方实现。保留具名 `VerifiedDelegation` 构造及 `_parse_run_acceptance`、Redis/进程归属检查、usage 与 knowledge 权限审计。平台正式合入需保留现有迁移身份，将并列 Runtime head 做显式 merge；不能删除既有 Token／后台迁移。重复的 API `20261011_0008` 合并迁移只保留主线版本。本期临时修补不自动发布。

## 来源契约

RAG `mcp_query_project_knowledge` 新增可选 `sources_version: 1|2`，默认 1。v1 仍是 `{status,sources}`，每来源保留七字段 source_id/document_id/chunk_id/title/kind/preview/truncated，预算 8 来源、800 字符预览、12 KiB。旧平台默认请求完全兼容。

v2 增加顶层 `sources_version:2` 和每来源 `locator:{unit,start,end,block_type}`。unit 只允许 page、slide、unknown；start/end 为可信存储的 1-based 整数范围或 null，block_type 为 text/image/table/equation/null。PDF 用页；PPTX 仅解析器提供可靠 provenance 时用幻灯片；DOCX／图片／MD／TXT 没固定页码，显示未知，不从模型或正文猜页。单页显示“第 3 页”，跨页“第 3–5 页”，PPTX“第 2 张幻灯片”。现有来源 ID 与预览一致保存，不能把 parser 路径、任意资产 URL 或完整原文加到公开回执。

接线位置：Runtime `src/runtime_service/tools/knowledge.py` 的 `_Source/_Result/project_knowledge_result/fit_knowledge_message` 增加明确 v2 DTO 和范围校验，模型 content、ToolMessage artifact、checkpoint/history/SSE 保持同一投影；Web `ToolResult.vue` 的 EvidenceSourceItem 增加 locator 与文案。Runtime `tools/mcp.py` 当前只强校验 submit/job 参数，query 的可选新参数不会触发该检查。版本选择应由服务配置／interceptor 固定为 v2，模型不能覆盖；先部署兼容 DTO/Web，再切服务配置。回退关 v2 请求，历史 v2 仍可显示，旧历史没有 locator 正常显示标题。

## 上传与能力门禁

Platform API `modules/knowledge/schemas.py` 的 Mime 已允许一般 MIME，capabilities 支持动态列表；正式平台旧知识实现的 Web `ChatComposer.vue:getKnowledgeGate` 硬编码 TXT/MD；临时 union 已修为只对可信 file 附件按 provider `supported_mime_types/max_file_bytes/upload_enabled` 和 Runtime 附件能力共同判定，加载或失败时拒绝，能力被撤销后清掉待提交勾选。PDF/DOCX/PPTX 已有可信 FileRef/DocumentWorkspace/AttachmentReceipts 六字段和真实字节上传链，不要额外复制原件或让模型构造宿主机路径。

实机发现：`createRuntimeFileTextBlock` 原只把 filename/path 放在 text，六字段仅放 extras；OpenAI 模型不看到 extras，无法准确提交 size_bytes/mime_type。最小修复在实际 HTTP 上传返回后，将同一个已校验 FileRef JSON 放入模型可见文本，并保留 extras；Runtime `_file` 继续对六字段与私有 HTTP 回执逐项验证。文件名仅作为数据，不授予权限。联验临时工作区已用该投影核验，正式平台需要相应测试和合入。

图片目前走 ImageRef 和 `/images/uploads`，不是 FileRef；RAG 已支持 image/png/jpeg，但平台不得伪造 FileRef 或仅按 path 接入。方案是在 Runtime 图片原件上传时记录专用 image 原始 name/mime/size/hash 收据；仅在知识提交 interceptor 内将已校验的收据转换为 KnowledgeFileRef，Web 图附件选择共享时带显式指令。scope、原件 hash、root HITL、run-create、非 plan/offload 和项目 IAM 校验全部沿用。该图片可信链改动需要平台治理评审，本期不擅自实施；暂可由管理员 CLI 或合法服务 FileRef 入库，不能宣称平台图片端到端完成。

## 错误回执

现有 Platform API ErrorCode、Runtime `tools/knowledge_jobs.py:ERROR_CODES` 没有 knowledge_artifact_invalid／knowledge_multimodal_failed。为保持现役 v1 DTO，RAG 对公开失败映射为 knowledge_processing_failed，详细内部原因保存受管日志。若平台要细分展示，先把两个值同时纳入 API/Runtime/Web 错误白名单，再启用对应版本；不能直接返回新 code 导致整张任务列表变 502。Web 区分“尚未受理／已受理／处理中／已可检索／失败”，审批 pending 显示“尚未受理”；queued 不显示已入库。本轮临时修复已实测。

## 联合验收与上线顺序

1. 先合并双方平台基线并跑 Token／后台回执回归、冻结依赖和迁移检查，保留已有功能。
2. 先接入 FileRef 文本投影、动态格式门禁和错误映射，以 v1 来源实测普通成员上传→root批准→受理→后台 ready，另一成员查询新旧文档；浏览器资料和回执不 mock。
3. 再部署 v2 DTO＋locator 展示，切 interceptor 请求 v2，校验历史／Fork／Worker 重启、预览预算和 unknown 行为。
4. 图片可信收据单独治理评审后实施，PNG/JPEG 浏览器整链验证通过才开放勾选。音视频延期，不加入能力列表。
5. Ubuntu RAG 部署用新 logical KB/namespace 与当前模型签名；Embedding 1024 和多模态配置不能套进旧 768／文字库。准备完整 Docling 模型缓存后可设 HF_HUB_OFFLINE=1，缺缓存先下载，否则解析显式失败。回滚先停接新上传，再显式回退经验证的冻结 generation，保留原件、资产和读 lease。

## 本轮交接产物与验证

[platform-integration.patch](platform-integration.patch) 只包含临时 union 相对其 index 的 12 个相关文件改动：动态格式勾选与能力撤销清理、FileRef 六字段文本投影、pending 回执、知识面板说明、root tools namespace 身份校验及测试、授权循环导入与测试导入顺序、临时合并产生的 credential_id 重复项修复。它不是原知识专项全量补丁；基线见 [platform-patch-context.json](platform-patch-context.json)。不包含临时迁移替换，正式合入必须核对当前迁移 heads 与原知识 worktree。

union 中的 API 知识／授权／模型策略回归 42 passed + 269 subtests；Runtime 知识／授权／Office 回归 156 passed；API Token／后台回执相关回归 113 passed、1 项未配置真实 PG 测试跳过；Runtime Token／后台回执相关回归 196 passed、35 项需要显式隔离 PG 或容器条件的测试跳过；Web 知识＋Token／后台投影 93 passed，typecheck 0 error。真实知识链路使用本环境 PostgreSQL／Redis／Worker，浏览器 route-list 无 mock。跳过的独立后台测试没有冒充本轮真实生产后台验收。

成员上传 PDF 后返回 queued／searchable=false，后台 ready／true；DOCX、PPTX 和 20MiB PDF 同样 ready，项目面板真实展示 5 份可检索资料。撤权对资料／任务／thread state／run.start 返回 project_role_missing，新增入库模型调用 0；Stop 无迟到结果，Worker 重启与 Fork 保留来源，重复文件新增调用 0。证据见 [浏览器截图](evidence/platform/browser-documents-final.png)、[Agent 结果](evidence/platform/agent-acceptance.json)、[生命周期](evidence/platform/lifecycle.json) 与 [负载](evidence/platform/load.json)。

v2 不在本次平台 union 中启用：现役 DTO 继续请求默认 v1；新 locator 的 RAG 单元、可信存储读取和图片真实检索已验，平台正式 DTO／展示接入后需再验历史、来源卡、Fork、预算与回退。图片需真实 ImageRef 原件收据方案后才能开放浏览器入库。
