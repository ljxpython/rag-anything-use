# LightRAG 官方原生版本迁移与平台服务架构适配

- **时间：** 2026-10-15
- **目标：** 调研与验证将底层知识库引擎平滑迁移至官方最新 LightRAG (1.5+，已合并 RagAnything 多模态)，消除侵入式私有锁与 Monkey Patch，向 `ai-agent-platform` 及 `runtime-service` 提供零破坏性的工业级知识服务。
- **影响模块：** 
  - 本项目：`src/knowledge/` (rag_engine, generations, parser_adapter, artifacts), `src/mcp_server.py`, `pyproject.toml`
  - 远程环境：`sshmy2` 独立沙箱目录 `/home/ubuntu/lightrag-v2-exploration`
  - 平台联动分析：`ai-agent-platform` 的 `platform-api` 与 `runtime-service`
- **状态：** 规划与方案讨论中

## 方案概述

### 1. 核心定调：下游专有复刻（Downstream Fork）+ 严格分层架构
- **为什么要复刻（Fork）：** 
  - 战略上，HKUDS 官方已正式将 `RagAnything` 合并并废弃独立维护，`LightRAG` 成为多模态核心主干；复刻官方仓库能直接继承最新的解析路由、分块策略与算法红利。
  - 业务上，开源团队只关注算法与单机原型，绝不会内置多租户隔离、权限管控、原子快照切换等业务逻辑。复刻后由我们自主二次开发网关与平台适配层。
- **避免冲突的架构铁律（分层开发）：**
  - **上游内核目录 `lightrag/`**：保持 Vanilla（纯净），通过 `upstream` 远程分支无缝同步官方 bug 修复和算法更新，严禁在核心算法逻辑中硬编码业务参数。
  - **平台网关目录 `gateway/`（我们的核心二次开发资产）**：
    - `gateway/multitenancy/`：基于独立目录的物理租户/项目实例池（Tenant & Project Workspace Router）。
    - `gateway/lifecycle/`：CAS 灰度候选构建、原子软链切换（Symlink Swap）、读租约锁（POSIX flock）。
    - `gateway/mcp/`：向平台暴露标准的 Streamable HTTP MCP 服务（`mcp_query_project_knowledge`、`sources_version=2`、可信 locator 生成）。
    - `gateway/auth/`：对接 `platform-api` 的 HMAC JWT 票据与操作鉴权。
    - `gateway/ingest/`：受管附件异步任务状态机与失 ACK 幂等回查。

### 2. 平台层与 runtime-service 改造评估结论

| 模块 | 原生接口硬接（否定） | 复刻改造 + 网关适配（采纳） |
|---|---|---|
| **runtime-service** | **灾难级破坏**：推翻 MCP Client、重写 Tool 定义、丢失页码定位 | **零改动 (0 行代码)**：完全保留现有 `mcp_query_project_knowledge` 与 `_SourceV2` 结构契约 |
| **platform-api** | **重度破坏**：平台需自行管理各项目独立进程端口与生命周期 | **零改动 (0 行代码)**：保留现有 `/api/projects/{id}/knowledge/...` 与 JWT 鉴权流程 |
| **复刻工程 (LightRAG-Enterprise)** | 仅有单机单库能力 | **承载全部平台适配**：内置多租户路由、原子发布、格式定位与 MCP 协议 |

### 3. 演进路线图
1. **阶段一（sshmy2 沙箱部署与原生摸底）：** 复刻/克隆官方最新代码到 `sshmy2:/home/ubuntu/lightrag-v2-exploration`，验证 Python 3.13 与 Docling/MinerU 环境，摸清官方解析产物 `.blocks.jsonl` 与元数据。
2. **阶段二（多租户与生命周期控制面实现）：** 在二次开发目录构建 `gateway/`，验证基于物理目录隔离与原子软链（Symlink Swap）的免侵入租户切换。
3. **阶段三（平台契约适配与定位对齐）：** 实现 MCP Server 适配器，将新版 LightRAG 召回数据转换为平台 `_ResultV2`（含 `locator`）。
4. **阶段四（13 事实回归与质量压测）：** 运行 119 项测试与 19 题公开基线，确保召回率 100%、P50/P95 响应时间不劣化。
5. **阶段五（平台联合联调与灰度切换）：** 与 `ai-agent-platform` 完成端到端联调，平滑替换旧服务。
