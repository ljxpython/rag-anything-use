# 项目当前状态

## 最后更新

2026-10-12 | G01、K01–K08及RAG配置的MD/TXT范围完成：完整快照候选＋新文档原生增量，67项回归与真实worker/HTTP/MCP通过；整专项partial，online默认关闭，平台/前端/Linux/部署待联合验收

## 系统状态

| 组件 | 状态 | 关键约束 |
|---|---|---|
| `src/mcp_server.py` | 旧3只读工具保留；online逻辑库增加精确提交/任务状态及内部HTTP | FileRef/回执/sources不变；写需平台grant＋票据，不暴露管理员接口 |
| `src/cli.py` | 稳定；新增注册/迁移/回退3命令 | 管理员专用；迁移需冻结旧服务与确认全部处理签名 |
| `src/knowledge/` | SQLite持久任务、原件/成果去重、单构建进程、原子激活/lease/回退已实现 | 12存储完整冻结快照恢复到新workspace，只处理新原件；published不可变，POSIX本地单服务进程 |
| 测试套件 | ✅ 67 项全通过（35.76s） | 协议、安全、故障/父SIGKILL恢复、迁移/回退、计数、10次mock发布回收；真实链路证据另列 |

## 环境说明

- Python ≥ 3.13，uv
- LightRAG 1.4.12 / FastMCP 3.2.0（锁定版本）
- 2026-10-12本轮真实验证：miaomiaoai `deepseek-v4.1-flash` + 百炼 OpenAI兼容 `text-embedding-v4` 1024维；2026-10-11旧只读专项曾使用Ollama768维，两套索引不可混用
- Intel macOS：PDF/Office extra 暂不可用（需 ARM Mac 或兼容 Linux）

## 活跃项目

- [项目成员 Agent MCP 异步入库](projects/20261012-project-member-knowledge-upload/README.md)：RAG文本范围done，整专项partial。恢复/重复0新模型调用；真实C/D未重发旧相同输入，失败不改变旧checksum，回退searchable真实。平台权限/可信附件/Runtime、前端、Linux格式与负载/部署待验收。[RAG接线与管理员命令](projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md)，[证据](projects/20261012-project-member-knowledge-upload/implementation/rag-evidence.md)。

## 近期关键决策

- 2026-10-12：实测固定完整快照候选＋新文档原生增量；不全库重组，不base＋delta。原生LLM缓存随快照恢复，不另加Embedding缓存；图更新必要费用单列，未知费率金额null。平台只接入，不持有第二套解析/索引队列。
- 2026-10-12：online默认false；首版能力只报告UTF-8 MD/TXT。迁移冻结legacy服务、保留旧ID/原件并确认处理签名；回退先禁上传、恢复完整累计版本后才重启上传。新chunk ID含document ID与workspace全局KV/锁回收绑定LightRAG1.4.12，升级需重验。
- 2026-10-11：DeepSeek 抽取需 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}` + `LLM_MAX_TOKENS=8192`，确保有正文可解析
- 2026-10-11：CLI `query`/`debug-retrieve` 为管理员诊断工具，不作为平台来源契约
