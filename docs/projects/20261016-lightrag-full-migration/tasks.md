# 任务列表

## 进度追踪

| Task | 状态 | 负责环境 |
|---|---|---|
| Task 1.1: 生产级 FastMCP 网关与 TenantWorkspaceManager 模块化打包 | [x] 已完成 | 本地 / sshmy2 |
| Task 1.2: 读租约（Reader Lease）计数与平滑退役调度器实现 | [x] 已完成 | 本地 / sshmy2 |
| Task 2.1: Docling 多模态 Sidecar 解析管道与 Locator 提取器集成 | [ ] 待开始 | sshmy2 |
| Task 2.2: 受管附件异步入库接口与平台 HMAC 鉴权链路迁移 | [ ] 待开始 | sshmy2 |
| Task 3.1: 存量知识数据提取与 1.5.8 候选工作区重建迁移工具开发 | [ ] 待开始 | 本地 / sshmy2 |
| Task 3.2: 迁移快照一致性、SHA256 签名与版本回退机制实测 | [ ] 待开始 | sshmy2 |
| Task 4.1: 120 项全量自动化测试迁移与回归适配（消除旧版锁依赖） | [ ] 待开始 | 本地 / sshmy2 |
| Task 4.2: 现役 rag-service 优雅停服与新网关 systemd 割接上线 | [ ] 待开始 | sshmy2 |

---

## 任务详情

### Phase 1: 生产级外挂网关与多租户隔离层标准化

#### Task 1.1: 生产级 FastMCP 网关与 TenantWorkspaceManager 模块化打包
- **改动内容：** 将沙箱验证成熟的 `gateway_mcp_server.py` 逻辑解耦重构为标准的生产级模块，规范化 Token 鉴权与租户项目工作区映射。
- **代码位置：** `src/mcp_server.py` → `create_server` / `TenantWorkspaceManager`
- **预期结果：** 网关支持通过环境变量配置启动，完全兼容 Streamable HTTP 协议与平台 token scope。
- **验证项：** 本地与远端分别启动并通过 `test_contract_client.py` 严格校验。
- **状态：** `[x]` 已完成（2026-10-16 实测通过 `tests/test_fastmcp_gateway.py`，双端通过）

#### Task 1.2: 读租约（Reader Lease）计数与平滑退役调度器实现
- **改动内容：** 实现基于引用计数的 `ReaderLease` 管理器，记录每个租户/项目正在执行的只读请求，并在 CAS 版本激活后，安全卸载旧版轻量存储实例。
- **代码位置：** `src/knowledge/lease_manager.py` → `ReaderLeaseManager`
- **预期结果：** 新版本发布时，存量并发查询 0 报错，旧版本实例在查询归零后平滑释放。
- **验证项：** 编写多协程并发查询压测与版本发布并发单测。
- **状态：** `[x]` 已完成（2026-10-16 实测通过 `tests/test_lease_manager.py`，并发排空全过）

---

### Phase 2: 异步入库写链路与 Docling 多模态管道集成

#### Task 2.1: Docling 多模态 Sidecar 解析管道与 Locator 提取器集成
- **改动内容：** 正式接入 `locator_resolver.py`，支持多格式（PDF/DOCX/PPTX/PNG/JPEG）解析中间态的持久化与缓存，根据召回 chunk 文本动态精准反查真实页码与幻灯片编号。
- **代码位置：** `src/knowledge/locator_resolver.py` → `LocatorResolver`
- **预期结果：** `sources_version=2` 请求下 100% 吐出合法、精确的 `locator` 对象，严禁伪造。
- **验证项：** 覆盖单页、跨页、幻灯片多格式测试用例。
- **状态：** `[ ]` 待开始

#### Task 2.2: 受管附件异步入库接口与平台 HMAC 鉴权链路迁移
- **改动内容：** 迁移 `mcp_submit_project_knowledge_document` 与 `mcp_get_project_knowledge_ingest_job` 工具，对接平台确定性 request_id 派生与 HMAC 票据校验，任务投递至后台 Candidate 目录。
- **代码位置：** `src/knowledge/ingest_service.py` → `KnowledgeIngestService`
- **预期结果：** 普通成员上传经平台授权后可安全异步入库，防失 ACK 重复回查无副作用。
- **验证项：** 运行原平台授权与失 ACK 场景单测。
- **状态：** `[ ]` 待开始

---

### Phase 3: 存量知识数据平滑迁移与自愈工具链

#### Task 3.1: 存量知识数据提取与 1.5.8 候选工作区重建迁移工具开发
- **改动内容：** 开发管理员迁移 CLI 命令 `rag migrate-v1-to-v2`，自动扫描现役旧版 1.4.12 的项目原始语料与受管原件，在 1.5.8 沙箱中批量重新索引构建。
- **代码位置：** `src/cli.py` → `cmd_migrate_v2`
- **预期结果：** 存量项目的所有文档原件无损迁移并生成全新的 1.5.8 图谱与向量数据。
- **验证项：** 对现役存量项目执行迁移并对比文档数量与事实召回。
- **状态：** `[ ]` 待开始

#### Task 3.2: 迁移快照一致性、SHA256 签名与版本回退机制实测
- **改动内容：** 迁移完成后生成 `snapshot.json` 快照校验清单，验证物理文件完整性，并实现 `rag rollback` 命令支持秒级切回历史版本。
- **代码位置：** `src/knowledge/snapshot.py` → `seal_snapshot` / `rollback_version`
- **预期结果：** 具备完整的冻结签名校验与秒级原子回退能力。
- **验证项：** 注入文件篡改测试防破坏，演练版本一键回退。
- **状态：** `[ ]` 待开始

---

### Phase 4: 平台端联合联调、120项全量回归与正式割接

#### Task 4.1: 120 项全量自动化测试迁移与回归适配（消除旧版锁依赖）
- **改动内容：** 清理 `tests/` 套件中强行断言 `lightrag.kg.shared_storage` 内部字典的陈旧测试，对齐新版无侵入目录规范。
- **代码位置：** `tests/`
- **预期结果：** `uv run pytest tests/ -q` 全部通过，无任何 monkey patch 告警。
- **验证项：** 在 Ubuntu `sshmy2` 上跑通全部测试套件。
- **状态：** `[ ]` 待开始

#### Task 4.2: 现役 rag-service 优雅停服与新网关 systemd 割接上线
- **改动内容：** 停止现役 `rag-service.service`（端口 8000），将新网关配置为 systemd 自启服务，更新平台连接配置，完成线上平滑割接。
- **代码位置：** `sshmy2:/etc/systemd/system/rag-service.service`
- **预期结果：** 新服务在后台稳定自启，平台无缝切换，端到端聊天检索正常。
- **验证项：** 生产环境双向联调验收。
- **状态：** `[ ]` 待开始
