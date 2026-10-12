# 项目当前状态

## 最后更新

2026-10-13 | 用户验收RAG-Anything升级与本期优化范围通过，需求done；主线合并2fbf89d保留后台完整绑定/新租约与失ACK回查，升级分支已推送，e5fb worktree已清理；知识MCP/Embedding已停。Ubuntu107项/本机101项通过，DeepSeek图片探针通过，复杂格式限制保留；online默认关闭，现役数据与新版部署未改

## 系统状态

| 组件 | 状态 | 关键约束 |
|---|---|---|
| `src/mcp_server.py` | 旧3只读工具保留；online精确提交/任务状态及内部HTTP含失ACK GET | FileRef/回执/sources不变；GET按当前grant及持久原主体/文件查同请求，新写关闭仍可查 |
| `src/cli.py` | 稳定；注册/迁移/回退3命令；main入口已正确传播失败退出码 | 管理员专用；迁移需冻结旧服务与确认全部处理签名 |
| `src/knowledge/` | 持久graph/来源/四文件绑定与新start/activate租约；来源/解析/缓存修复与旧文本签名兼容保留 | 12存储完整候选增量、published不可变；旧identity缺字段拒绝，不伪造来源；POSIX单服务进程 |
| 测试套件 | ✅ 合并后Ubuntu107项通过（25.32s）；本机101项通过/6项documents跳过（169.36s） | 授权/失ACK、增量/迁移/回退与解析升级均保留；冷启动测试仅准备等待/成功后清理适配高负载，业务worker未改 |

## 环境说明

- Python ≥ 3.13，uv
- RAG-Anything 1.4.2 / MinerU 3.4.5 / Docling 2.84.0；LightRAG 1.4.12 / FastMCP 3.2.0保留（锁定版本）
- 2026-10-12本轮真实验证：miaomiaoai `deepseek-v4.1-flash` + 百炼 OpenAI兼容 `text-embedding-v4` 1024维；2026-10-11旧只读专项曾使用Ollama768维，两套索引不可混用
- Intel macOS：PDF/Office extra 暂不可用（需 ARM Mac 或兼容 Linux）

## 活跃项目

- [项目优化与 RAG-Anything 升级](projects/20261012-rag-optimization/README.md)：done（2026-10-13用户验收本期范围）。P0、19题通用检索基线、100次快照观测与逐格式记录完成；miaomiaoai DeepSeek图片HTTP探针/项目适配器通过，完整复杂PDF/Office多模态仍待复验，online多模态/页码、音视频与生产负载后置，现役迁移/新版部署未执行。
- [项目成员 Agent MCP 异步入库](projects/20261012-project-member-knowledge-upload/README.md)：RAG文本范围done，整专项partial。恢复/重复0新调用、完整候选增量/回退已验；[provider两项对齐](projects/20261012-rag-provider-contract-alignment/README.md)done，实际平台HTTP/真实模型链七检查通过，Thread删除继续/撤权拒绝/失ACK GET已验。10-13只读核对平台tasks：A/R/O/V01与前端F01–F03代码完成，V02真实Agent/生命周期/浏览器入库与部署仍待验收；复杂格式/负载后置。[RAG接线](projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md)。

## 近期关键决策

- 2026-10-13：miaomiaoai `deepseek-v4.1-flash`图片输入和既有vision适配器实测通过，可将私有VISION三项配置为与LLM相同；本次只改探针进程配置，旧iflow434不代表DeepSeek不支持。图片小样不等于完整文档多模态验收。
- 2026-10-12：在线文本新签名排除未使用的解析包版本；精确兼容已核验v1文本组合，保留旧签名/checksum。离线与在线新增chunk均以document ID隔离；多模态显式绑定本workspace，资产路径在batch/fallback索引模板中隐藏。
- 2026-10-12：后台identity持久保留graph_id及sha256/size/name/MIME；每次新issuer/audience/整数iat/exp/uuid nonce。新增同key GET不enqueue/不消费attempt，要求当前upload grant；RAG新写关闭不拒回查，平台停签会阻止获取新租约。旧缺字段任务不猜来源。
- 2026-10-12：实测固定完整快照候选＋新文档原生增量；不全库重组，不base＋delta。原生LLM缓存随快照恢复，不另加Embedding缓存；图更新必要费用单列，未知费率金额null。平台只接入，不持有第二套解析/索引队列。
- 2026-10-12：online默认false；首版能力只报告UTF-8 MD/TXT。迁移冻结legacy服务、保留旧ID/原件并确认处理签名；回退先禁上传、恢复完整累计版本后才重启上传。新chunk ID含document ID与workspace全局KV/锁回收绑定LightRAG1.4.12，升级需重验。
- 2026-10-11：DeepSeek 抽取使用 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}` + `LLM_MAX_TOKENS=8192`；本轮仍有空正文/预算耗尽，供应商稳定性需单独复验
- 2026-10-11：CLI `query`/`debug-retrieve` 为管理员诊断工具，不作为平台来源契约
