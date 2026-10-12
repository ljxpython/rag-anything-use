---
name: plan-project
description: 判断为接口/架构改动时调用，在 docs/projects/{YYYYMMDD}-{slug}/ 下创建项目文档（README + tasks + verification）。内部改动跳过。
---

# Plan Project

## 触发条件

- 改 CLI 命令/MCP tool 签名
- 改跨模块数据契约（schemas、publication 协议、锁机制）
- 升级核心依赖（LightRAG、FastMCP）
- 改 env 配置项定义

## 跳过条件

- 内部改动（单模块、不影响公开接口）
- 纯讨论/方案探索——直接对话，确定要做了再调本 Skill

## 工作流

1. 从对话上下文确认：slug（kebab-case）、目标（一句话）、影响的模块
2. 创建 `docs/projects/{YYYYMMDD}-{slug}/`，生成下面三个文件

## 文档模板

### README.md

```markdown
# {项目标题}

- **时间：** {开始日期}
- **目标：** {一句话}
- **影响模块：** {列表}
- **状态：** 规划中

## 方案概述

{简要描述方案，重点说清楚接口变更和兼容性影响}
```

### tasks.md

```markdown
# 任务列表

## 进度追踪

| Task | 状态 |
|---|---|
| 1.1 xxx | [ ] 待开始 |

## 任务详情

### Task 1.1: {任务名}
- **改动内容：** {具体改什么}
- **代码位置：** `{文件路径}` → `{函数/类名}`
- **预期结果：** {改完是什么状态}
- **验证项：** `{具体命令或测试}`
- **状态：** `[ ]` 待开始
```

### verification.md

```markdown
# 验证记录

## Phase 验证（每个 Task 完成后）

<!-- 每个 Task 完成时在这里追加一条 -->

## Final 验证

<!-- 所有 Task 完成后执行 -->

### 测试套件
- [ ] `uv run pytest tests/ -q` → 全部通过

### 链路验证（接口改动必须）
- [ ] 入库 → 发布 → MCP 查询完整链路通过

### 最终结论
<!-- done / partial / blocked / deferred，说明原因 -->
```
