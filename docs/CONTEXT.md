# 项目当前状态

## 最后更新

2026-10-12 | 平台provider契约两项修复完成：后台完整绑定/新租约与失ACK只读回查；78项回归、实际Platform API HTTP＋隔离IAM/Run＋真实模型七检查通过。整成员上传专项partial，online默认关闭，Runtime Agent/前端/Linux/部署待联合验收

## 系统状态

| 组件 | 状态 | 关键约束 |
|---|---|---|
| `src/mcp_server.py` | 旧3只读工具保留；online精确提交/任务状态及内部HTTP含失ACK GET | FileRef/回执/sources不变；GET按当前grant及持久原主体/文件查同请求，新写关闭仍可查 |
| `src/cli.py` | 稳定；新增注册/迁移/回退3命令 | 管理员专用；迁移需冻结旧服务与确认全部处理签名 |
| `src/knowledge/` | 持久graph/来源/四文件绑定；每次start/activate新RAG→平台租约，实际平台200 | 12存储完整候选增量、published不可变；旧identity缺字段拒绝，不伪造来源；POSIX单服务进程 |
| 测试套件 | ✅ 78 项全通过（52.28s） | 新增授权HTTP/失ACK回查私有边界；原故障/迁移/回退/计数/连续发布回收保留；真实平台/模型另列 |

## 环境说明

- Python ≥ 3.13，uv
- LightRAG 1.4.12 / FastMCP 3.2.0（锁定版本）
- 2026-10-12本轮真实验证：miaomiaoai `deepseek-v4.1-flash` + 百炼 OpenAI兼容 `text-embedding-v4` 1024维；2026-10-11旧只读专项曾使用Ollama768维，两套索引不可混用
- Intel macOS：PDF/Office extra 暂不可用（需 ARM Mac 或兼容 Linux）

## 活跃项目

- [项目成员 Agent MCP 异步入库](projects/20261012-project-member-knowledge-upload/README.md)：RAG文本范围done，整专项partial。恢复/重复0新调用、完整候选增量/回退已验；[provider两项对齐](projects/20261012-rag-provider-contract-alignment/README.md)done，实际平台HTTP/真实模型链七检查通过，Thread删除继续/撤权拒绝/失ACK GET已验。Runtime Agent/可信附件/浏览器、Linux格式/负载与部署待验收；[RAG接线](projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md)。

## 近期关键决策

- 2026-10-12：后台identity持久保留graph_id及sha256/size/name/MIME；每次新issuer/audience/整数iat/exp/uuid nonce。新增同key GET不enqueue/不消费attempt，要求当前upload grant；RAG新写关闭不拒回查，平台停签会阻止获取新租约。旧缺字段任务不猜来源。
- 2026-10-12：实测固定完整快照候选＋新文档原生增量；不全库重组，不base＋delta。原生LLM缓存随快照恢复，不另加Embedding缓存；图更新必要费用单列，未知费率金额null。平台只接入，不持有第二套解析/索引队列。
- 2026-10-12：online默认false；首版能力只报告UTF-8 MD/TXT。迁移冻结legacy服务、保留旧ID/原件并确认处理签名；回退先禁上传、恢复完整累计版本后才重启上传。新chunk ID含document ID与workspace全局KV/锁回收绑定LightRAG1.4.12，升级需重验。
- 2026-10-11：DeepSeek 抽取需 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}` + `LLM_MAX_TOKENS=8192`，确保有正文可解析
- 2026-10-11：CLI `query`/`debug-retrieve` 为管理员诊断工具，不作为平台来源契约
