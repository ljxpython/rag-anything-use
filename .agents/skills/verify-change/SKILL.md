---
name: verify-change
description: 所有 Task 完成后调用，执行 Final 验证，输出四态判定，做状态一致性检查。
---

# Verify Change

## 触发时机

所有 tasks.md 中的 Task 标为 `[x]` 后。

## Final 验证步骤

1. **测试套件**
   ```
   uv run --frozen --env-file ".env" pytest tests/ -q
   ```

2. **链路验证**（接口/发布流程有改动时必做）
   ```
   # 入库
   uv run --frozen --env-file ".env" python main.py ingest --project-id {test-ns} --file {test-file}
   # 发布
   uv run --frozen --env-file ".env" python main.py publish --project-id {test-ns}
   # MCP 查询（用 fastmcp client 或 curl）
   ```

3. **状态一致性检查**（任何不一致先对齐再收尾）
   - `tasks.md` 的完成状态
   - `verification.md` 的 Phase 验证记录条数 == 已完成 Task 数
   - `README.md` 的「状态」字段
   - `docs/CONTEXT.md` 是否需要更新

## 四态判定

在 `verification.md` 的「最终结论」里写：

| 状态 | 含义 |
|---|---|
| `done` | 全部完成并验证 |
| `partial` | 部分完成，说明哪部分未完成及原因 |
| `blocked` | 被外部依赖卡住，说明所缺条件 |
| `deferred` | 明确推迟，说明推迟理由 |

`partial` 不能作为停止工作的理由——能继续的必须继续。

## 项目收尾

Final 验证通过后：
1. 把 `README.md` 的「状态」改为最终四态值
2. 更新 `docs/CONTEXT.md`
3. 更新 `docs/FEATURES.md`（如果有功能变化）
4. **主动回顾**：本次改动是否有值得沉淀的教训？有则提议写入 `docs/lessons/`，等用户确认后写入
