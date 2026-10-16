# 港大官方最新 LightRAG 1.5.8 工业级全面迁移与平台无侵入接入规划

- **时间：** 2026-10-16
- **目标：** 彻底废除旧版 1.4.12 侵入式架构与脆弱私有锁，基于官方最新 LightRAG 1.5.8 算法与多模态底座，构建工业级外挂网关、多租户 CAS 原子发布体系与 Docling 可信定位解析器，向上对平台 (`ai-agent-platform`) 保持 0 代码改动无缝平滑割接。
- **影响模块：**
  - `src/mcp_server.py`（FastMCP 4.1.0 网关协议迁移）
  - `src/knowledge/`（废除旧版 `generations.py` 私有锁破解，接入 `TenantWorkspaceManager` 目录级隔离）
  - `src/cli.py`（管理员迁移与校验工具重构）
  - `tests/`（120 项现役单测升级对标）
- **状态：** 规划中

---

## 1. 方案概述与架构边界

### 1.1 核心设计理念
1. **上游原生不魔改（Zero Hack to Upstream）**：坚决不修改 LightRAG 官方内部算法库源码，确保随时能够快进跟踪上游安全补丁与新特性。
2. **平台端 0 代码改动（Zero Code Change on Platform）**：`ai-agent-platform` 的 `platform-api` 与 `runtime-service` 保持现有 FastMCP 协议接口契约（`sources_version=1|2`、`_ResultV2`、`_Locator`），仅需更新网关环境变量配置。
3. **彻底抛弃私有锁，拥抱 POSIX 内核原子性（Atomic Swap & Reader Lease）**：消除旧版 `release_workspace` 中强删内部字典的危险行为，基于文件系统软链完成零锁原子热切与读租约平滑下线。
4. **多模态真实溯源（Precision Locator via Docling）**：结合 Docling 2.139 产生的 `.blocks.jsonl` Sidecar 中间态，精准动态解析页码（1-based 正整数）与幻灯片（Slide），严禁伪造页码。

---

## 2. 迁移四个大阶段 (Four Phases Roadmap)

```text
┌────────────────────────────────────────────────────────┐
│ Phase 1: 生产级外挂网关与多租户隔离层标准化 (Gateway & Tenants)  │
│  - 将沙箱验证成熟的 FastMCP 4.1.0 网关转为正式服务规范   │
│  - 固化 TenantWorkspaceManager 软链 CAS 发布与读租约     │
├────────────────────────────────────────────────────────┤
│ Phase 2: 异步入库写链路与 Docling 多模态管道集成 (Ingest) │
│  - 串联 mcp_submit_project_knowledge_document          │
│  - HMAC 票据鉴权、受管附件防失 ACK 回查与 Candidate 构建  │
├────────────────────────────────────────────────────────┤
│ Phase 3: 存量知识数据平滑迁移与自愈工具链 (Data Migration)│
│  - 编写旧版 1.4.12 存量语料向 1.5.8 的无损迁移脚本       │
│  - 验证多租户历史快照密封、SHA256 签名与回退演练       │
├────────────────────────────────────────────────────────┤
│ Phase 4: 平台端联合联调、120项全量回归与正式割接 (Cutover)│
│  - 平台 DearFlow / Showcase 端到端真实验收              │
│  - 现役 rag-service 停服与新服务 systemd 无缝接管        │
└────────────────────────────────────────────────────────┘
```
