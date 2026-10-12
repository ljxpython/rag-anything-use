# RAG-Anything Use 开发规范

单服务知识库 MCP 系统。离线入库（CLI）+ 只读查询（MCP）。

## 会话初始化

**开始任何需求前，读 `docs/CONTEXT.md` 同步项目状态。**

改动完成后，更新 CONTEXT.md 的「最后更新」和受影响的状态行。

## 改动分级

### 内部改动

**范围：** 单模块内部，不改变 CLI 命令签名、MCP tool 签名、跨模块数据契约、发布/锁机制。

**流程：** 直接实现 → 单元测试 → Commit

**示例：** 修复 bug、优化内部逻辑、加日志、调整 LightRAG 参数

### 接口/架构改动

**范围：** 改变 CLI 命令、MCP tool 签名、跨模块数据契约、入库/发布流程、依赖版本升级、env 配置项。

**流程：** 调用 `plan-project` → 实现（调用 `implement-feature`）→ 验证（调用 `verify-change`）→ Commit

**示例：** 新增 MCP tool、改变 ingest 流程、修改 namespace 发布协议、升级 LightRAG/FastMCP 版本

判断有歧义时，偏「接口/架构改动」而不是往轻处理，先问用户确认。

## 模块边界

| 模块 | 职责 |
|---|---|
| `src/mcp_server.py` | MCP 服务入口；只对外暴露 3 个只读 tool |
| `src/cli.py` | 管理员 CLI（ingest / publish / list-docs / query / debug-retrieve）；不经 MCP 暴露 |
| `src/knowledge/` | 核心引擎；CLI 和 MCP 共用 |
| `tests/` | 测试套件；目前 24 项覆盖协议、安全、生命周期 |

## 验证

```
uv run --frozen --env-file ".env" pytest tests/ -q
```

接口/架构改动还需要用测试 namespace 完整跑一遍：入库 → 发布 → MCP 查询链路。

## Skills（按场景自动调用）

- `plan-project`：判断为接口/架构改动时，在 `docs/projects/{YYYYMMDD}-{slug}/` 下建项目文档
- `implement-feature`：实现过程中记录改动，输出 Task Completion Card
- `verify-change`：所有任务完成后执行两阶段验证，输出四态判定

## 经验库读取

改动前，查看 `docs/lessons/index.md`，按需读对应经验文件。

## 严禁行为

- ❌ 不得编造测试结果或入库验证记录
- ❌ 不得通过 MCP tool 暴露管理员接口或宿主机路径
- ❌ 不得修改已发布（published）namespace 的内容
- ❌ 不得在模型/Embedding 配置变更后复用旧索引（必须新建 namespace）
- ❌ 不得在接口/架构改动未建项目文档的情况下开始写代码
