# 项目当前状态

## 最后更新

2026-10-12 | Harness 初始化

## 系统状态

| 组件 | 状态 | 关键约束 |
|---|---|---|
| `src/mcp_server.py` | 稳定 | 只读 3 个 tool，不暴露管理员接口 |
| `src/cli.py` | 稳定 | 管理员专用（ingest/publish/list-docs/query/debug-retrieve） |
| `src/knowledge/` | 稳定 | 核心引擎，POSIX flock 保护 namespace |
| 测试套件 | ✅ 24 项全通过 | 覆盖协议、安全、生命周期 |

## 环境说明

- Python ≥ 3.13，uv
- LightRAG 1.4.12 / FastMCP 3.2.0（锁定版本）
- 验证配置：miaomiaoai `deepseek-v4.1-flash` + Ollama `nomic-embed-text` 768 维
- Intel macOS：PDF/Office extra 暂不可用（需 ARM Mac 或兼容 Linux）

## 活跃项目

_（无）_

## 近期关键决策

- 2026-10-11：DeepSeek 抽取需 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}` + `LLM_MAX_TOKENS=8192`，确保有正文可解析
- 2026-10-11：CLI `query`/`debug-retrieve` 为管理员诊断工具，不作为平台来源契约
