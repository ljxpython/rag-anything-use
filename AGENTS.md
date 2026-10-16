# LightRAG 生产底座开发规范 (Production Constitution)

基于香港大学最新官方 LightRAG 1.5.8 专有分支构建的企业级外挂式知识系统。
双轨生产运行：外挂 FastMCP 4.1.0 生产网关（端口 8001，8 大核心工具矩阵）+ 官方原生 WebUI（端口 9621）。

## 核心环境与物理拓扑

- **代码主仓库**：`git@github.com:ljxpython/LightRAG.git`（分支：`main`）
- **开发与黄金运行宿主机 (Golden Host)**：`sshmy2`（Ubuntu 24.04）
  - 核心工作区：`/home/ubuntu/lightrag-v2-exploration/LightRAG`
  - 环境管理：`/home/ubuntu/.local/bin/uv`
  - 常驻守护：`rag-service.service` (端口 8001) / `rag-webui.service` (端口 9621)
- **本地宿主机 (Local Mirror)**：Mac 本地工作区（作为只读观察或镜像同步源）
- **上层消费平台**：`ai-agent-platform`（通过公网直连 `http://152.136.27.196:8001/mcp`）

## 开发工作流范式：Remote-First (sshmy2 现场闭环)

所有开发、调试与验证全面遵循 **“sshmy2 现场改，现场验，push 固化，本地 pull 同步”** 的极简原则（KISS）：

```
[sshmy2 现场编写/修改]
       │
       ▼
[sshmy2 原地运行验证 (uv run pytest)]
       │
       ▼
[经用户明确确认后，sshmy2 执行 git commit & git push]
       │
       ▼
[本地 Mac 仅需执行 git pull 保持镜像同步]
```

### 1. 会话初始化
- 任何需求开始前，读 `docs/CONTEXT.md` 同步当前系统状态与已投产工具。

### 2. 代码修改与现场验证
- **直接在 `sshmy2` 上修改代码**，彻底杜绝双端 scp/rsync 导致的代码版本不一致或文件覆盖事故。
- 所有单元测试必须在 `sshmy2` 宿主机现场运行并输出真实日志：
  ```bash
  uv run --with pytest --with pytest-asyncio pytest tests/ -v
  ```
- 涉及 MCP 接口或守护进程改动，现场执行重启并做 Live 探针检查：
  ```bash
  sudo systemctl restart rag-service && uv run python verify_8_tools_live.py
  ```

### 3. 代码提交与本地同步
- 严禁未经用户明确授权擅自提交！
- 获得用户明确指令（“确认”、“提交”）后，在 `sshmy2` 上执行 `git commit` 并 `git push origin main`。
- 本地 Mac 终端或 IDE 仅需执行 `git pull origin main`，无缝拉取最新生产代码。

## 改动分级与流程规范

### 1. 内部改动
- **范围：** 单模块内部实现、Bug 修复、内部日志优化、Prompt 微调。
- **流程：** `sshmy2` 直接修改 ➔ 运行对应单测 ➔ 用户确认后 Commit & Push ➔ 本地 Pull。

### 2. 接口 / 架构改动
- **范围：** 改动/新增 MCP Tool 签名、调整租约/CAS 发布机制、修改 Snapshot 签名协议、升级核心依赖。
- **流程：** 
  1. 调用 `plan-project` 在 `docs/projects/{YYYYMMDD}-{slug}/` 创建专项（README, tasks, verification）；
  2. 在 `sshmy2` 上分步实现并记录 Task Completion Card；
  3. 执行 4 级全量验收（静态检查、单测回归、systemd 状态、跨网络 E2E）；
  4. 用户确认后 Commit & Push ➔ 本地 Pull 同步。

## 模块架构与边界职责

| 模块文件 | 架构职责 | 严禁行为 |
|---|---|---|
| `gateway_mcp_server.py` | 外挂式 FastMCP 8 大工具网关；对齐平台 JWT 鉴权与 `readOnlyHint` 等安全注解 | 严禁暴露宿主机绝对路径；严禁改动破坏现有 8 大工具默认签名 |
| `workspace_manager.py` | 多租户物理工作区隔离；POSIX CAS 零锁原子版本切换 (`active -> revisions/rev_N`) | 严禁引入跨进程文件死锁；严禁绕过 CAS 软链直接在 active 目录增量覆写 |
| `lease_manager.py` | 异步读租约引用计数与旧版本平滑优雅排空 | 严禁在有在读查询时强制关闭底层存储 |
| `locator_resolver.py` | Docling 多模态可信定位器 (page/slide/unknown) | 严禁编造或猜测未经解析的页码信息 |
| `snapshot_manager.py` | SHA-256 完整性封印与秒级原子回退 | 严禁将易变 LLM 查询缓存 (`kv_store_llm_response_cache.json`) 纳入静态签名 |
| `graph_explorer.py` | 基于 NetworkX 的实体局部 N 度拓扑抽取 | 严禁无深度限制全图遍历（防止内存爆炸） |
| `ingest_service.py` | 候选沙箱入库与安全修剪 (`adelete_by_doc_id`) | 严禁在生产激活库直接执行破坏性删除 |
| `lightrag/` (核心库) | 港大官方源码，保持纯净上游同步能力 | ❌ **严禁修改任何一行代码（保持 0 侵入）** |

## 严禁行为红线 (Zero Tolerance)

- ❌ **严禁侵入官方核心源码**：执行 `git status --porcelain lightrag/` 必须永远为空，确保随时无冲突 `git merge upstream/main`。
- ❌ **严禁虚假跑测与 Mock 冒充**：禁止编造测试结果，所有测试必须在 `sshmy2` 真实运行并留存输出。
- ❌ **严禁擅自执行 Git 提交**：执行 `git commit` / `git push` 前必须向用户触发危险操作确认，获得明确授权后方可执行。
- ❌ **严禁提交敏感资产与索引**：`.env` 私密配置、`sandbox_storage/` 索引目录严禁入库。
