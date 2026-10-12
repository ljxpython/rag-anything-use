---
name: implement-feature
description: 接口/架构改动实现过程中调用，每完成一个 Task 输出 Task Completion Card，更新 tasks.md 状态。
---

# Implement Feature

## 每个 Task 完成时

1. 在 `tasks.md` 把该 Task 状态改为 `[x] 完成`
2. 在 `verification.md` 的「Phase 验证」区块追加一条记录
3. 在对话中输出 **Task Completion Card**

## Task Completion Card 格式

```markdown
### Task {编号}: {任务名} ✅ {日期}
- **改动内容：** {做了什么}
- **代码位置：** `{文件}` → `{函数/类}`
- **验证项：** {执行了什么} → {结果}
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（非伪造）
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 需要更新（改了公开接口/功能状态时）
```

**没有 Completion Card = 任务未完成。**

## 注意

- Phase 验证只跑这个 Task 直接相关的最小测试，不跑全量
- 验证结果必须是真实执行的，不得编造
