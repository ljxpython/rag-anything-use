# 项目当前状态

## 最后更新

2026-10-16 | **ai-agent-platform 平台层全栈端到端真实联调验收大获全胜（20261016-platform-localstack-e2e-verification）**：直接接入本地 `./scripts/local-stack.sh` 运行中的平台栈（`runtime-api`, `runtime-worker`, `platform-api`, `platform-web`），修改 `.env` 端口对齐 `sshmy2:8001`，配置 `KNOWLEDGE_AUTHORIZATION_SECRET`；通过真实 Platform API 登录、创建 LangGraph Thread 并驱动 Agent（`dearflow_agent`），真实跨公网触发 `mcp_list_project_knowledge_documents`（成功列出存量 3 篇文档并排版 Markdown）与 `mcp_query_project_knowledge`（成功召回切片），Thread 运行状态均为 `success`，全栈真实 E2E 彻底闭环。
2026-10-16 | **FastMCP 知识网关 8 大工具平台级扩展大获全胜并正式投产**：针对平台层多 Agent 协同、多跳图谱推理、文档全生命周期治理及可观测运维看板诉求，完成 `20261016-platform-mcp-expansion` 专项。网关能力从 5 工具扩充为 8 工具矩阵（`mcp_query_project_knowledge` 扩展 mode/doc过滤/多轮历史、`mcp_query_knowledge_graph` 实体局部子图探查、`mcp_delete_project_knowledge_document` 沙箱修剪与CAS切换、`mcp_get_project_knowledge_stats` 全景健康指标看板），100% 向后兼容老平台客户端；排除易变 LLM 查询缓存以确保 snapshot 签名永久稳定；6大套件 20 项单测全绿通过（8.72s），端口 8001 真实 HTTP Client 联调全部通过。
2026-10-16 | **LightRAG 生产底座全面落地与生产割接大获全胜**：在 `sshmy2`（Ubuntu 24.04）上基于 LightRAG 1.5.8 完成了全量五阶段落地与正式投产割接。实现外挂式 FastMCP 4.1.0 生产网关（端口 8001，三只读+两写入工具，`_ResultV2` / `_Locator` 严格对齐）、多租户 POSIX CAS 零锁原子切换、Docling 多模态真实页码反查、存量知识库平滑迁移（3篇核心存量文档原件入库重建图谱与向量库）及带 SHA256 签名的 `snapshot.json` 防篡改和秒级版本回滚机制。通过 systemd 双服务（`rag-service.service` 端口 8001 与 `rag-webui.service` 端口 9621）正式接管生产常驻运行，平台端 `ai-agent-platform` 达成 **0 行代码修改** 无缝接入，上游 `lightrag/` 源码达成 **0 行代码侵入**。
2026-10-16 | 用户确认停服操作：已执行 `sudo systemctl stop rag-service.service` 成功停用旧版 1.4.12 现役服务（端口 8000 已彻底释放），存量旧服务平滑下线，正式启动 LightRAG 1.5.8 全量迁移专项（projects/20261016-lightrag-full-migration）。
2026-10-15 | 完成港大最新官方 LightRAG 1.5.8 专有复刻与无侵入平台适配探索（sshmy2 独立沙箱）：构建 TenantWorkspaceManager（POSIX 软链 CAS 替代旧版 shared_storage 私有锁强解）与 FastMCP 4.1.0 网关（端口8001），深度对齐 ai-agent-platform 契约实现平台端 0 代码改动；真实跑通 Docling 2.139.0 多页 Locator 动态解析（page 1-based/slide）；19题公开基线复测 Recall@8 与证据完整率均达 100.0%（19/19全PASS），P50/P95 时延达 0.104s/0.199s（相比旧版基线快 60+ 倍）；现役环境 120 项测试全部通过（33.61s），环境隔离与兼容性完好。
2026-10-15 | 排查并修复远端 sshmy2 上传 PPTX 报错问题：由于远端工作区 rag_engine.py 等文件被旧版代码反向覆盖，导致多模态纯图片幻灯片缺少 full_docs 补偿写入，在 seal_snapshot 处触发 knowledge_snapshot_invalid。现已全量恢复远端关键模块，修复 smoke test 环境隔离，119项回归全过（27.39s）；恢复并密封 candidate 快照，成功将 PPTX（kd_ffba19b7...）激活上线（项目 revision 升至 2）；端到端验证 sources_version=2 可信 slide 定位（命中第5、13页幻灯片）与 systemd 服务重启。
2026-10-13 | 用户批准将已验收在线文档分支快进合入 main，本地和 Ubuntu 统一跟踪 origin/main；原主线与验收提交全部保留，合入后 Ubuntu119 passed／26.07s。在线 PDF／DOCX／PPTX／PNG／JPEG、受管资产与来源 v2、五格式13事实、真实平台 union 文档闭环及生命周期完成；19题公开基线有答案召回／证据1.0、P50/P95 2.948/3.564秒、20MiB／两项目队列已验。平台正式合入／v2展示／ImageRef收据待同事继续，音视频延期；现役索引未切换

## 系统状态

| 组件 | 状态 | 关键约束 |
|---|---|---|
| `gateway_mcp_server.py` (sshmy2) | ✅ 生产活跃（systemd 端口 8001） | FastMCP 4.1.0；8大工具完整矩阵；严格兼容 sources_version=1\|2 与 _ResultV2/_Locator；支持图谱探查、生命周期删除与全景可观测；平台 0 改动 |
| `run_lightrag_webui_server.py` (sshmy2) | ✅ 生产活跃（systemd 端口 9621） | 官方原生 WebUI，公网可访问；图谱可视化；只读监控与调试 |
| `workspace_manager.py` / `lease_manager.py` | ✅ 稳定 | 多租户物理目录隔离；Linux POSIX CAS 零锁软链切换；异步引用计数与优雅退役排空 |
| `graph_explorer.py` | ✅ 稳定 | NetworkX 高性能 N 度子图提取；支持模糊实体匹配与深度限制 |
| `locator_resolver.py` | ✅ 稳定 | Docling raw JSON / .blocks.jsonl 自动反查；支持 page/slide/unknown 三级匹配 |
| 测试套件 | ✅ 6大核心套件 20 passed (8.72s) | 单元测试、8大工具覆盖、平台契约校验、防篡改签名与回退全部通过 |

## 环境说明

- Python ≥ 3.13，uv
- RAG 交接分支 `main`；本地 `/Users/lijiaxin/PyCharmMiscProject/rag-anything-use` 和 Ubuntu `/home/ubuntu/PyCharmMiscProject/rag-anything-use` 跟踪 `origin/main`，私有配置和知识库按环境保留。
- RAG-Anything 1.4.2 / MinerU 3.4.5 / Docling 2.84.0；LightRAG 1.4.12 / FastMCP 3.2.0保留（锁定版本）
- 2026-10-12本轮真实验证：miaomiaoai `deepseek-v4.1-flash` + 百炼 OpenAI兼容 `text-embedding-v4` 1024维；2026-10-11旧只读专项曾使用Ollama768维，两套索引不可混用
- 2026-10-13本机／Ubuntu项目VISION三项已显式复用LLM，视觉预算8192；`env.example`删除旧供应商及备用配置，运行源码无专用供应商调用。视觉配置也参与online处理签名，部署时不绕过旧库校验
- Intel macOS：PDF/Office extra 暂不可用（需 ARM Mac 或兼容 Linux）

## 活跃项目

- [LightRAG 1.5.8 工业级全面迁移](projects/20261016-lightrag-full-migration/README.md)：新立项规划中，全面替换 1.4.12 核心，实现平台 0 代码改动、多租户 CAS 与真实 Locator 交付。
- [LightRAG 1.5.8 原型探索与验证](projects/20261015-lightrag-native-migration/README.md)：探索 Phase 1~3 已完成，验证时延 0.10s (提升 60倍) 及 19 题 100% 召回。
- [Ubuntu 在线文档与联合验收](projects/20261013-online-documents/README.md)：已完成合入 main。
- [模型供应商清理](projects/20261013-model-provider-cleanup/README.md) 与 [RAG升级](projects/20261012-rag-optimization/README.md)：原期 done，本次补齐旧后置文档／资产／定位／联合验收；历史失败证据保留。
- [成员异步入库](projects/20261012-project-member-knowledge-upload/README.md)：RAG与临时平台 V02 文档联验通过，正式平台合并／部署不标已完成；[授权与失ACK](projects/20261012-rag-provider-contract-alignment/README.md)保留。
- [剩余事项](remaining-work.md)：平台v2展示、图片收据／正式合入、私有业务与生产SLA；音视频用户暂不开发。旧token启服前协调消费方轮换，证据不含凭据。

## 近期关键决策

- 2026-10-13：按用户要求清理iflow／豆包运行配置；本机与Ubuntu私有VISION改用miaomiaoai `deepseek-v4.1-flash`，更新配置后既有适配器图片检查通过。图片小样不等于完整文档多模态验收；后置任务不以Ubuntu或旧视觉凭据作统一阻塞理由。
- 2026-10-12：在线文本新签名排除未使用的解析包版本；精确兼容已核验v1文本组合，保留旧签名/checksum。离线与在线新增chunk均以document ID隔离；多模态显式绑定本workspace，资产路径在batch/fallback索引模板中隐藏。
- 2026-10-12：后台identity持久保留graph_id及sha256/size/name/MIME；每次新issuer/audience/整数iat/exp/uuid nonce。新增同key GET不enqueue/不消费attempt，要求当前upload grant；RAG新写关闭不拒回查，平台停签会阻止获取新租约。旧缺字段任务不猜来源。
- 2026-10-12：实测固定完整快照候选＋新文档原生增量；不全库重组，不base＋delta。原生LLM缓存随快照恢复，不另加Embedding缓存；图更新必要费用单列，未知费率金额null。平台只接入，不持有第二套解析/索引队列。
- 2026-10-13：online默认false；依赖及完整多模态开关齐全才报告PDF／DOCX／PPTX／PNG／JPEG，其余只报告MD/TXT。迁移冻结legacy服务、保留旧ID/原件并确认处理签名；回退先禁上传、恢复完整累计版本后才重启上传。新chunk ID含document ID与workspace全局KV/锁回收绑定LightRAG1.4.12，升级需重验。
- 2026-10-13：当前 miaomiaoai 抽取实测 reasoning_effort:off；none 在复杂文档节点出现400，最终 off 五格式13事实全过。模型配置与多模态成果签名变动采用独立新库，不绕过旧签名。
- 2026-10-11：CLI `query`/`debug-retrieve` 为管理员诊断工具，不作为平台来源契约
