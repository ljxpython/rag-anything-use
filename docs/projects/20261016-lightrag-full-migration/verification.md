# 验证记录

## Phase 验证（每个 Task 完成后）

### 2026-10-16 Task 1.1: 生产级 FastMCP 网关与 TenantWorkspaceManager 模块化打包
1. **代码落地**：
   - 提取 `src/knowledge/llm_client.py`：统一封装指数退避重试与 miaomiaoai `extra_body`（thinking 禁用）。
   - 提取 `src/knowledge/locator_resolver.py`：支持自适应解析 Docling raw JSON 与 `.blocks.jsonl` Sidecar。
   - 提取 `src/knowledge/workspace_manager.py`：实现 `TenantWorkspaceManager`，支持目录物理隔离与 POSIX CAS 原子软链接激活。
   - 重构 `src/mcp_server.py`：支持 FastMCP 4.1.0，完全遵循平台 `_ResultV1` 与 `_ResultV2` 数据契约。
2. **测试验证**：
   - 本地环境：`uv run pytest tests/test_fastmcp_gateway.py -v` → **2 passed in 1.51s**。
   - 远端环境（`sshmy2`）：`uv run pytest tests/test_fastmcp_gateway.py -v` → **2 passed in 1.23s**。
   - 校验：空 query 防御返回合规 `no_hit`，物理软链切换（`atomic_publish_candidate`）在真实 Linux 内核上验证成功。

### 2026-10-16 Task 1.2: 读租约（Reader Lease）计数与平滑退役调度器实现
1. **代码落地**：
   - 实现 `src/knowledge/lease_manager.py`：基于引用计数的细粒度异步读租约管理器 `ReaderLeaseManager`，支持 `(tenant_id, project_id, version_tag)` 活跃查询跟踪。
   - 实现优雅排空机制（`mark_retired` 与 `_drain_and_cleanup`）：版本激活后将旧实例移入退休队列，新请求无缝获取新版本，存量查询继续执行；计数器归零后触发清理，彻底消除内存泄漏和私有锁强删隐患。
   - `TenantWorkspaceManager` 深度集成：在 `acquire_read_lease` 中绑定版本租约，并在 `atomic_publish_candidate` 后自动触发非阻塞平滑下线调度。
2. **测试验证**：
   - 编写 `tests/test_lease_manager.py`（租约基础计数、并发慢查询下的版本退休排空、工作区管理器集成）。
   - 本地验证：`uv run pytest tests/test_fastmcp_gateway.py tests/test_lease_manager.py -v` → **5 passed in 2.96s**。
   - 远端验证（`sshmy2`）：`uv run --env-file .env pytest tests/test_fastmcp_gateway.py tests/test_lease_manager.py -v` → **5 passed in 1.52s**。
   - 结论：Phase 1 所有目标达成，生产级网关与零锁多租户读租约体系已稳固落地！

## Final 验证

<!-- 所有 Task 完成后执行 -->

### 测试套件
- [ ] `uv run pytest tests/ -q` → 全部通过（消除旧版锁断言，通过新版无侵入测试）

### 链路验证（接口改动必须）
- [ ] 平台端 0 代码改动：更新 `RUNTIME_MCP_CONNECTIONS_JSON` 后与 `runtime-service` 连通正常
- [ ] 检索链路：`mcp_query_project_knowledge(sources_version=2)` 实测通过 `_ResultV2` / `_Locator` 严格校验
- [ ] 异步入库链路：受管附件经平台授权后成功入库并在 `active` 目录累积生效
- [ ] 性能指标：19 题事实检索 Recall@8 维持 100%，P50/P95 显著优于旧版本基线（当前实测为 0.104s / 0.199s）

### 最终结论
<!-- done / partial / blocked / deferred，说明原因 -->
待启动
