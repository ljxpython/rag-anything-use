# 百炼 Embedding 接入

- **时间：** 2026-10-12
- **目标：** 使用百炼 OpenAI 兼容 Embedding API 替换本地 Ollama 调用
- **影响模块：** `src/demo_support.py`、环境变量、Embedding 测试
- **状态：** partial（配置完成，等待知识库资料发布）

## 方案概述

新增 `EMBEDDING_API_KEY` 配置，通过 OpenAI 兼容 `/embeddings` 接口调用百炼 `text-embedding-v4`，保留维度校验并兼容已有 Ollama 配置。
