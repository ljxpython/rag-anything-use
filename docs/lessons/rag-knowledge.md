# RAG 知识服务踩坑记录

## [坑] 模型/Embedding 配置变更后不能复用旧索引

- **场景：** 更换 LLM 或 Embedding 模型、调整 embedding 维度
- **错误：** 继续用旧 namespace 的向量索引，查询结果乱或报错
- **正确：** 新建 namespace，完整入库 → 发布后再切换 token 配置；旧 namespace 保留不删
- **日期：** 2026-10-11

## [坑] DeepSeek 抽取不加 thinking 禁用会导致无正文可解析

- **场景：** 用 miaomiaoai DeepSeek 做 LightRAG 实体抽取
- **错误：** 默认配置下 thinking 字段消耗大量 token，正文被截断或为空
- **正确：** `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}` + `LLM_MAX_TOKENS=8192`；此配置只用于支持该参数的供应商
- **日期：** 2026-10-11

## [坑] CLI query/debug-retrieve 不是 MCP 来源，不能当平台契约用

- **场景：** 想用 CLI query 结果作为平台来源验收依据
- **错误：** CLI query 会调用生成式 aquery，生成最终答案；MCP 走 aquery_data，只返回片段
- **正确：** CLI 工具是管理员诊断专用；平台集成和验收必须通过 MCP 接口进行
- **日期：** 2026-10-11

## [坑] MCP 持有读锁期间 CLI 不能写同一 namespace

- **场景：** MCP 服务运行中，尝试 CLI ingest 或 publish 同一 namespace
- **错误：** POSIX flock 冲突，CLI 卡住或报错
- **正确：** 先停 MCP 服务再执行 CLI 写操作；或对新版本用不同 namespace，发布后再重启 MCP
- **日期：** 2026-10-11

## [坑] Intel macOS 无法安装锁定 Torch wheel，documents extra 不可用

- **场景：** 在 Intel Mac / Python 3.13 上 `uv sync --extra documents`
- **错误：** 无兼容 Torch 2.11 wheel，PDF/Office 解析不可用
- **正确：** 文本模式（UTF-8 md/txt）在 Intel Mac 上可用；PDF/Office 需要 ARM Mac 或受支持的 Linux；不修改锁文件来伪造兼容，不引入 Docker
- **日期：** 2026-10-11
