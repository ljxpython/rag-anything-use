# 任务列表

## 进度追踪

| Task | 状态 |
|---|---|
| 1.1 清理运行模型配置并验证替代视觉调用 | [x] 完成 |
| 1.2 说明剩余开发、验收与 Ubuntu 用途 | [x] 完成 |

## 任务详情

### Task 1.1: 清理运行模型配置并验证替代视觉调用

- **改动内容：** 核对源码、示例和脚本，无专用供应商调用；本机／Ubuntu `env.example` 删除旧供应商默认／备用配置；本机与 Ubuntu RAG 私有 `.env` 中视觉三项显式复用当前文本模型配置，移除旧视觉凭据。Ubuntu scopes JSON 转义为dotenv单行，授权映射不变。
- **代码位置：** `env.example`；`src/demo_support.py` → `load_settings()` / `build_vision_model_func()`（先核对，确有必要才修改）；项目私有 `.env`。
- **预期结果：** 运行源码及项目 env 无旧供应商引用，现有 DeepSeek 图片适配器可用；凭据不输出、不提交。
- **验证项：** 脱敏配置检查、运行引用扫描、`tests/test_llm_configuration.py` / `tests/test_raganything_compatibility.py`、Ubuntu 合成图片调用。
- **状态：** `[x]` 完成；本机2项通过／6项documents跳过，Ubuntu相关8项通过；更新配置后的现有视觉适配器识别合成图片正确，运行配置／源码引用扫描为零。

### Task 1.2: 说明剩余开发、验收与 Ubuntu 用途

- **改动内容：** 明确 online 多模态／公开来源定位／音视频尚未实现，复杂文档／平台完整闭环／业务质量／负载属于待验收；记录原定后置范围和实际失败，说明 Mac 开发与 Ubuntu 集成验证的分工。
- **代码位置：** `docs/remaining-work.md`、`README.md`、`docs/CONTEXT.md`、`docs/FEATURES.md`、运行及进展文档、原升级专项任务。
- **预期结果：** 不把已完成平台代码重复列为未开发，不把模型图片探针当全文档通过，也不把 Ubuntu 当必须由用户写代码的条件。
- **验证项：** 与 RAG 升级证据及平台最新任务核对、文档链接检查、项目回归和独立测试库链路。
- **状态：** `[x]` 完成；核对平台最新tasks与RAG历史证据，45个本地链接检查通过，文档明确开发／验收／环境／后置原因。
