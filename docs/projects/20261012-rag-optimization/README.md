# 项目优化与 RAG-Anything 升级

- **时间：** 2026-10-12
- **目标：** 在现有知识库服务上安全升级 RAG-Anything，补齐文档入库与来源定位，用业务评测决定检索和运行成本优化。
- **影响模块：** `pyproject.toml` / `uv.lock`、`src/demo_support.py`、`src/knowledge/`、`src/mcp_server.py`、`src/cli.py`、`tests/`、`scripts/`、环境示例与运行文档。
- **改动级别：** 接口/架构改动；涉及依赖、处理签名、解析成果和可能的来源契约扩展。
- **状态：** `done`（本期选定范围）。2026-10-13用户确认验收通过，六项实现/基线/逐格式记录交付完成。技术边界仍保留：文本/扫描PDF通过，混合PDF/Office稳定性与完整多模态未通过；在线多模态、平台资产/页码、音视频和生产负载作为后续项。本次验收不改变格式支持表，未迁移现役数据或部署新版。
- **收尾：** 2026-10-13通过所属平台 `knowledge-stop` 停止知识MCP/Embedding；Ubuntu隔离无残留测试进程。升级分支已推送，主工作区快进到合并提交2fbf89d，e5fb worktree已清理；保留主线后台授权/失ACK功能，最终Ubuntu107项/macOS101项通过。主工作区原有3份百炼专项文档按原内容单独提交，不覆盖历史记录。

## 导航

- [任务列表](tasks.md)：具体代码入口、实施顺序和完成条件。
- [验证计划与记录](verification.md)：升级、格式、检索、负载和回退的证据要求。
- [实施证据与复跑入口](implementation/README.md)：最终测试日志、通用检索/快照基线与逐轮格式结果。
- [剩余开发／验收与Ubuntu用途](../../remaining-work.md)：10-13清理项目旧供应商配置后的最新说明；后置开发不以旧视觉凭据作阻塞理由。
- [既有异步入库专项](../20261012-project-member-knowledge-upload/README.md)：继续负责平台权限、可信附件、Runtime、前端和联合部署验收。

## 方案概述

以独立 RAG-Anything 为文档、多模态处理入口，沿用本项目的 CLI / MCP、持久任务、原件去重、冻结快照候选和原子激活。本轮已选定 RAG-Anything 1.4.2 与既有 LightRAG 1.4.12 的组合，完成来源正确性修复、Ubuntu 文档解析验收和通用检索评测。

版本升级不等于新能力已接入。MD/TXT 当前走原生文本入库；在线候选构建只处理 UTF-8 文本，不能仅安装新版就宣称支持 Markdown 图片、PDF/Office 或音视频。后续按格式证据增加能力。

## 实施结果

| 范围 | 结果 |
|---|---|
| 依赖 | RAG-Anything 1.2.10→1.4.2、MinerU 3.0.7→3.4.5；LightRAG 1.4.12、Docling 2.84.0、FastMCP 3.2.0保留 |
| 正确性 | 文档级chunk来源、解析tuple/参数/可信页码、索引计数、首解析缓存、多模态workspace/资产路径、紧凑表格与CLI失败退出码已修复 |
| 既有在线文本 | 精确兼容已核验v1签名组合，旧checksum不变；不兼容模型/维度仍拒绝；隔离演练通过，现役迁移未执行 |
| 完整回归 | 10-13合并后Ubuntu107 passed / 25.32s；Intel Mac101 passed、6 skipped / 169.36s；10-12升级分支96/90项历史日志保留 |
| 检索 | 3份公开合成资料19题：16道有答案题Recall@8/证据完整率1.0，跨项目来源0；3道无答案题仍返回资料，不能外推业务回答准确率 |
| 快照观测 | 100小文档最终快照3.44 MB、全部历史约182 MB；复制/校验P95约28/7ms，确定性模型恢复零调用 |
| 格式 | 文本/扫描PDF最新done；Office正文初轮通过、最新超时/失败，混合PDF修复后的真实链路未通过。旧iflow凭据无效；10-13补充DeepSeek图片探针/项目适配器通过，完整文档仍partial |

## 实施前基线与证据

以下为2026-10-12规划时的源码和锁文件核对结果，保留用于说明改动原因；不代表当前实现。67项通过来自既有专项，本轮最终结果见上表。

| 项目 | 实施前事实 | 对优化的含义 |
|---|---|---|
| 依赖 | RAG-Anything 1.2.10、LightRAG 1.4.12、Docling 2.84.0、MinerU 3.0.7；documents 为可选依赖 | 升级 RAG-Anything 需要重新解析 documents 依赖，核心引擎无需默认同步跨大版本 |
| 入库 | `KnowledgeIngestService._ingest_document()` 对 MD/TXT 直接读 UTF-8，其他格式经 `parse_document()` / `insert_content_list()` | 新版的 Markdown 图片提取和直接文本解析不会自动进入当前文本路径 |
| 在线构建 | `KnowledgeGenerationService.build()` 只加载或保存文本成果，并调用 `ingest_text()` | 文档块、多模态资产、恢复和计数还需接线；首版 capabilities 仅 MD/TXT |
| 签名 | `processing_signature()` 包含三个包版本、解析参数、模型和向量配置；`acquire()` / `build()` 都校验签名 | 安装或升级 documents 依赖会影响既有逻辑库读写，不能只改依赖号后重启 |
| 工作区回收 | `release_workspace()` 明确要求 LightRAG 1.4.12，访问其私有共享存储与锁 | 若选 1.4.16，必须先适配并重验回收、候选发布和 lease |
| 来源隔离 | 在线文本调用 `document_chunks=True`；离线文本使用默认 False | 两条路径的 chunk 身份规则不同，应复现同正文不同原件的来源冲突风险 |
| 解析结果 | `DoclingParserAdapter.parse_file()` 把 tuple 第二项当 metadata；核对的上游 1.2.10 / 1.4.2 返回 `(content_list, doc_id)` | 现有 `page_count` 无法由这项取得；需明确解析成果、页码与文档 ID 的契约 |
| 检索 | MCP 固定 hybrid、关闭 rerank、最多 8 段，每段 800 字符；sources 不含页码 | 先测召回与截断影响，再选择分块或排序优化；引用页码属于接口扩展 |
| 质量与容量 | 已记录 3 份 Markdown / 30 题合成评测及 10 次 mock 发布回收；PDF/Office、业务语料、Linux负载未验收 | 不能据此推断真实资料质量、最大容量或新版性能收益 |

源码入口：`src/knowledge/{rag_engine,ingest_service,parser_adapter,artifacts,generations,upload_service,citations}.py`；已有实测见 [RAG 证据](../20261012-project-member-knowledge-upload/implementation/rag-evidence.md) 和根 README。

## 优化优先级

P0 表示正确性与升级前置事项，P1 为首期收益，P2 按评测选择，P3 先保留议题。以下保留规划优先级；本轮选择范围与最终状态见[任务列表](tasks.md)。

| 优先级 | 优化方向 | 预期收益 | 本期建议 |
|---|---|---|---|
| P0 | RAG-Anything 1.4.2 兼容验证、处理签名与快照迁移 | 获得入库、缓存、解析修复，同时保留旧库可读与可回退能力 | 先验证，再确定最小升级组合 |
| P0 | 离线/在线来源身份与解析契约 | 避免同正文来源覆盖；页码和状态由真实解析/索引结果产生 | 先复现并补有意义的回归 |
| P1 | Ubuntu PDF / DOCX / PPTX 实际链路 | 从文本服务扩展到日常文档，明确扫描件、表格、公式和图片的效果 | 先 CLI 文档路径验收，再讨论在线开放 |
| P1 | 业务资料检索基线与定向优化 | 明确哪些问题检索不到、排序差或证据被截断 | 比较分块/模式；rerank 只在有证据时接入 |
| P2 | 在线多模态成果、Markdown 图片、来源定位 | 复用已有任务与资产，支持图表资料和可追踪引用 | 按实际资料选择；页码输出需消费方协同 |
| P2 | 容量、耗时和用量可观测 | 找出复制、校验、模型调用或排队的瓶颈，确定运行上限 | 复用现有 usage 和脚本，不先建监控平台 |
| P3 | 音频 / 视频 | 会议和培训资料可检索 | 有真实需求与资源预算后另定范围 |

## 依赖升级路线

截至本轮锁定，RAG-Anything **1.4.2** 要求 `lightrag-hku<1.5`、`mineru[core]>=3.4.1`、Python >=3.10。项目保留现有 Python >=3.13 基线，Ubuntu 隔离环境已确认完整依赖安装；没有为追逐 LightRAG 1.5.x 破坏当前回收/快照契约。

1. **本轮采用：** RAG-Anything 1.4.2 + LightRAG 1.4.12。真实包＋确定性模型的正文/图表接口、workspace与关闭回归通过；真实模型格式能力逐项记录，不能据此宣称全部多模态可用。
2. **备选后置：** 本轮无需改用LightRAG 1.4.16，也未试验该组合。若未来采用，回收代码与存储行为需单独适配，不直接移除版本检查。
3. **Docling / MinerU：** 锁定Docling 2.84.0、MinerU 3.4.5，Ubuntu完整安装与pip check通过；真实格式轮使用Docling，未比较MinerU解析质量。
4. **既有库：** 在线MD/TXT新签名排除未使用解析包版本，并精确兼容已核验旧文本组合；模型/端点/维度/分块仍校验，保留旧签名与checksum。现役清单/切换窗口未确认，不执行生产迁移。离线旧索引的来源/表格修复须从原件导入独立新namespace。
5. **不兼容时：** 保留原运行版本和旧库，拒绝切换；如确需重建，单列原件范围、费用和新 namespace。业务上传不得自动触发全量重建。

上游1.4.0改变解析缓存键和原生TXT/MD内容形状，1.4.2增加等待正文处理完成与失败抛错。本轮已验证当前调用/失败传播和缓存路径；上游并发修复不等于项目当前单worker已发生丢文档。

## 文档与多模态接入

- **解析配置统一：** 让服务配置中的 parser / parse_method 与实际执行一致；明确解析返回的文档 ID、内容块、可信页码、资产清单和失败状态。新建成果遵循既有 checksum / 原子落盘机制。
- **格式顺序：** 在 Ubuntu 先测文本 PDF、扫描 PDF、DOCX、PPTX；表格、图片和公式分别准备已知答案。默认沿用 Docling，遇到质量缺口再比较 MinerU，不同时建设两套入库系统。
- **在线接线：** 复用 `KnowledgeArtifactStore` 和既有 builder；多模态资产以项目、文档归属保存，快照恢复和回退必须带齐资产。检验现有纯文本快照假设是否适用于无正文文档，不能直接照用。
- **Markdown 图片：** 普通 MD 继续可用；多模态模式需要受管图片附件与明确引用关系。仅有一个 MD FileRef 不足以提供其本地图片，不能读取任意宿主文件或替用户抓取外网图片。
- **引用定位：** 先保证内部页码/跨页范围正确；未知页码保留未知。若向 MCP 增加定位信息，评审 sources 版本及消费方兼容；不能将宿主路径和原始 metadata 直接返回。

## 检索与运行优化

先建立含有答案、无答案、相似术语、表格、跨文档和跨项目负例的业务问题集，报告 Recall@8、排序、证据完整性、P50/P95 与外部调用用量。800 字符预览和 12 KiB 总预算可能截掉答案证据，需要用实际 MCP 返回值评测。

随后每次只比较一个变量：分块与重叠、候选范围或检索模式；只有排序问题被证明时才试 rerank。改变索引生成参数需独立测试 namespace 与签名验证。MCP 继续返回来源，由消费方生成最终答案。

完整快照候选会随资料规模增大产生复制与校验成本，读副本也会占空间。测量候选复制、checksum、索引、激活、排队和请求阶段，复用现有 usage 区分新文档与受影响图合并。先输出容量/保留策略建议；历史快照删除和迁移执行不包含在本轮讨论授权中。

## 与已有专项的关系

本专项负责RAG升级、文档与质量优化的实现及验收记录。既有去重、任务、精确授权、lease和原子发布直接复用。平台IAM、Runtime interceptor、前端与部署联合验收仍在原专项跟踪，不以本轮RAG范围结果覆盖其状态。

LightRAG 1.5.x 原生流水线、官方 WebUI、HTTP 解析服务迁移、分布式队列和向量库替换均不作为当前默认方案；发现具体瓶颈后再比较选项。

## 后续条件

1. 用已验证的miaomiaoai DeepSeek过程级VISION配置复验完整文档表格/公式/图片；抽取空正文与超时原因仍需定位，未改变现役配置。
2. 真实业务资料、问题集及召回/延迟/费用门槛；当前按用户选择交付通用公开合成基线。
3. 现役逻辑库清单、规模与切换窗口；Ubuntu本轮仅用sshmy2的隔离目录。
4. 平台可信多模态资产/来源定位与音视频场景、资源预算；未具备时保持deferred。

## 未完成的开发与验收

| 范围 | 待办 |
|---|---|
| 在线多模态开发（Task2.2） | PDF/DOCX/PPTX/图片的受管资产、成果保存与恢复、MIME/配额校验、纯多模态候选与失败/回退；当前online仍仅MD/TXT |
| 来源定位开发（Task2.2） | 将可信页码/跨页范围接入公开sources，需与消费方约定兼容字段；Markdown图片须可信附件引用 |
| 音视频（Task4.1） | 需求、ASR/关键帧/时间戳与资源预算尚未确定，未安装或开放 |
| 模型与格式验收 | DeepSeek图片HTTP/适配器小样已通过；剩余混合PDF/Office稳定抽取、表格/图片/公式真实链路及修正后的完整格式脚本复跑 |
| 业务与运维验收 | 真实业务语料、召回/延迟/费用门槛，20 MiB文件与多项目负载；历史快照保留策略未实现，不自动删除 |
| 跨仓联验 | 只读核对平台工作区最新tasks：A01/A02/R01/R02/O01/V01及前端F01–F03代码已完成；剩余V02真实Agent Worker/另一成员检索、Stop/重启/CAS/回退/大文件及浏览器真实入库闭环。RAG后台授权/失ACK已在主线完成，不重做 |

百炼Embedding调用与真实向量已经实现，本轮真实链路亦已使用；不是剩余开发项。其他工作区的专项草稿由其负责人维护。

跨仓状态依据为2026-10-13只读查看 `/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform/docs/projects/20261012-project-member-knowledge-upload/tasks.md`：前端有组件/自测交付，含模拟响应，未算真实入库验收。本仓成员上传原规划中的平台“待开始”为早期交接记录，应以平台上述最新清单判断代码进度；本轮不修改平台代码或代其关闭V02。

## 官方依据

- [RAG-Anything 1.4.2 PyPI](https://pypi.org/project/raganything/1.4.2/)：依赖范围与可选音视频能力。
- [1.3.0 发布说明](https://github.com/HKUDS/RAG-Anything/releases/tag/v1.3.0)：Docling Python API、超时和 DOCX 公式工具。
- [1.3.1 发布说明](https://github.com/HKUDS/RAG-Anything/releases/tag/v1.3.1)：正文文档重复检测修复。
- [1.4.0 发布说明](https://github.com/HKUDS/RAG-Anything/releases/tag/v1.4.0)：MinerU v2 内容、文本直解析、缓存与迁移说明。
- [1.4.1 发布说明](https://github.com/HKUDS/RAG-Anything/releases/tag/v1.4.1)：Markdown 图片、音频与视频。
- [1.4.2 发布说明](https://github.com/HKUDS/RAG-Anything/releases/tag/v1.4.2)：正文等待/失败、页码、多模态修复与图片校验。

这些说明用于确定候选收益，不替代当前服务、Ubuntu 或业务资料的验收。
