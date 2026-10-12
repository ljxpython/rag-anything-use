# 任务列表

2026-10-12用户确认实施规划，Ubuntu使用sshmy2隔离测试目录，资料选用公开通用合成样本。实施1.1–1.3、2.1、3.1；3.2收敛为快照/用量观测基线，生产吞吐门槛留待真实负载，2.2、4.1后置。2026-10-13用户验收本期通过，授权停止服务、worktree提交/推送、安全合并主线与清理worktree；现役资料迁移和新版部署仍未执行。

## 进度追踪

| Task | 优先级 | 状态 |
|---|---|---|
| P01 核对源码、锁文件、经验与已有专项 | — | [x] 规划调查完成 |
| P02 建立方案、任务与验证文档 | — | [x] 规划文档完成 |
| 1.1 隔离验证依赖组合与兼容矩阵 | P0 | [x] 完成 |
| 1.2 定稿升级与既有库签名/快照迁移 | P0 | [x] 完成 |
| 1.3 修正来源身份和解析成果契约 | P0 | [x] 完成 |
| 2.1 Ubuntu PDF / Office 逐格式验收 | P1 | [x] 完成验收记录；格式能力partial |
| 2.2 接入选定在线多模态与来源定位 | P2 | deferred，视觉接口与平台资产未验收 |
| 3.1 业务检索基线与定向优化 | P1 | [x] 完成（通用样本；未选 rerank） |
| 3.2 容量、阶段耗时与用量优化 | P2 | [x] 完成（100次确定性快照观测） |
| 4.1 音频 / 视频需求与资源评估 | P3 | deferred，暂无资料与资源预算 |

## 任务详情

### Task 1.1: 隔离验证依赖组合与兼容矩阵

- **改动内容：** 先做隔离试验，核对实际安装的 RAG-Anything 1.4.2 与 LightRAG 1.4.12、Docling、MinerU 组合；需要时试 1.4.16。记录完整版本与平台，选最小依赖变更集合。
- **代码位置：** `pyproject.toml` / `uv.lock`；`src/demo_support.py` → `build_raganything()` / `build_lightrag()`；`src/knowledge/generations.py` → `release_workspace()`；`tests/`。
- **预期结果：** 得到一个可安装、可解析、可入库且通过来源/生命周期检查的候选；包元数据可解、导入成功和完整链路通过分开记录。
- **验证项：** Ubuntu 隔离环境 `uv sync --frozen --extra documents --group dev`（候选锁生成后）；在同一候选环境运行 `uv pip check`；项目测试及真实 content-list 试验。记录上游新方法在 1.4.12 的实际调用结果，不把版本范围当兼容证明。
- **依赖：** 明确 Ubuntu 测试环境；不需要改现役资料。
- **状态：** `[x]` 完成；Phase 证据见 verification.md，现役库未切换。

### Task 1.2: 定稿升级与既有库签名/快照迁移

- **改动内容：** 根据 1.1 选择并锁定版本，限定独立 RAG-Anything 所需的 LightRAG `<1.5` 范围。对比签名变化，设计兼容的旧库读写切换与回退；若需要区分文本/解析依赖，先证明未使用依赖不改变处理语义。LightRAG 升级时适配回收与快照，而非关闭校验。
- **代码位置：** `pyproject.toml` / `uv.lock`；`src/knowledge/artifacts.py` → `processing_signature()`；`generations.py` → `validate_snapshot()` / `acquire()` / `build()` / `release_workspace()`；`project_admin.py` → `KnowledgeProjectAdmin`；`tests/test_knowledge_artifacts.py` / `test_knowledge_generations.py` / `test_knowledge_migration.py`；运行文档。
- **预期结果：** 旧逻辑库在明确的版本/签名方案下保持可用；不兼容时切换被拒绝，原程序和旧库可恢复。不得任意修改 published 内容、伪造新签名或由普通上传自动全量重建。
- **验证项：** `uv run --frozen --env-file ".env" pytest "tests/test_knowledge_artifacts.py" "tests/test_knowledge_generations.py" "tests/test_knowledge_migration.py" "tests/test_knowledge_lifecycle.py" -q`；隔离旧库副本升级/拒绝/回退演练；更换模型或维度仍拒绝旧索引复用。
- **依赖：** 1.1；既有库清单与允许的切换窗口。
- **状态：** `[x]` 完成；Phase 证据见 verification.md，现役库未切换。

### Task 1.3: 修正来源身份和解析成果契约

- **改动内容：** 先复现离线同正文不同原件的 chunk 来源风险，验证可沿用文档级身份的最小修复；核对 PDF/多模态路径是否有同类来源共享。明确上游 `(content_list, doc_id)` 返回值，保持本项目 opaque document_id，不将第二项当 metadata。统一有效 parser / parse_method；可信页码从内容/解析来源提取，未知保持未知。
- **代码位置：** `src/knowledge/ingest_service.py` → `_ingest_document()`；`rag_engine.py` → `ingest_text()` / `ingest_content_list()` / `install_document_chunk_ids()`；`parser_adapter.py` → `ParsedKnowledgeDocument` / `parse_file()`；`content_normalizer.py` → `normalize_content_list()`；`src/demo_support.py` → `build_rag_config()`；`tests/test_knowledge_smoke.py` / `test_knowledge_generations.py`，必要时新增解析适配器回归。
- **预期结果：** 离线和在线新增文档均保持准确来源；重复/同名/同正文资料不覆盖归属；页码与计数不伪造。已有索引不原地改 chunk ID。
- **验证项：** 两个不同 document_id、相同正文以及同名不同内容的入库→发布→MCP 检索；真实 tuple 返回、跨页/无页码、空解析、失败和取消用例；配置传入与实际解析一致。
- **依赖：** 可先在当前版本复现；新版本行为验收依赖 1.1。
- **状态：** `[x]` 完成；Phase 证据见 verification.md，现役库未切换。

### Task 2.1: Ubuntu PDF / Office 逐格式验收

- **改动内容：** 用干净 Ubuntu 环境和候选锁运行现有 CLI 文档路径。准备文本 PDF、扫描 PDF、含表格/图片/公式的 PDF、DOCX、PPTX；记录解析内容、页码、来源、耗时与查询证据。Docling 先行，遇到缺口再比较 MinerU。DOCX 原生公式工具只在现有解析确有遗漏时接入。
- **代码位置：** `src/knowledge/parser_adapter.py` / `ingest_service.py`；`src/demo_support.py`；`main.py`失败退出码；公开fixture生成/格式验收脚本、回归、运行文档与格式支持表。
- **预期结果：** 每种格式分别给出通过、部分支持或失败及原因；解析器依赖安装成功不等于格式支持。在线格式列表暂不因 CLI 试验自动扩大。
- **验证项：** 测试 namespace 执行 CLI ingest→publish→MCP 查询，按已知事实核验正文、表格、图片说明和公式；Linux timeout/cancel/SIGKILL、锁回收与服务重启；记录 OS / Python / 包 / 模型版本。
- **依赖：** 1.1、1.3；Ubuntu 和代表性样本。真实模型调用按后续实施授权与资料范围执行。
- **状态：** `[x]` 完成逐格式验收与问题修复记录，能力判定`partial`。文本/扫描PDF最新链路通过；DOCX/PPTX初轮正文通过、终轮超时/模型空正文失败；混合PDF表格表示修复有确定性证据，真实模型终轮600s超时。视觉端点业务码434提示apiKey无效；不能继续标作图片分析通过。有效凭据/稳定抽取后再用同入口复验，online多模态后置。

### Task 2.2: 接入选定在线多模态与来源定位（deferred）

- **改动内容：** 根据 2.1 和资料需求选定首批格式，扩展既有成果保存/加载和 builder，包含受管资产清单、校验与恢复；同步 MIME/原件验证/capabilities。Markdown 图片要求可信受管附件引用，不接受宿主路径或任意 URL。内部定位先接通，公开页码扩展另核对消费方兼容。
- **代码位置：** `src/knowledge/artifacts.py` → `KnowledgeArtifactStore`；`generations.py` → `build()` / `validate_snapshot()` / `copy_storage()`；`upload_service.py` → `MIME_EXT` / `validate_file_ref()` / `capabilities()`；`demo_support.py` → `build_raganything()` / `build_vision_model_func()`；`citations.py` / `schemas.py` / `src/mcp_server.py`；相关测试、接入指南与 `env.example`。
- **预期结果：** 新格式继续使用同一任务/去重/授权/候选发布链；旧成果复用无新增模型调用，缺资产或不兼容候选拒绝发布；格式能力与实测一致。页面定位缺失时不猜，公开接口无宿主信息泄漏。
- **验证项：** FileRef→原字节→任务→解析/资产→独立候选→激活→MCP；同原件复用、跨项目隔离、资产缺失/损坏/穿越、纯多模态无正文、撤权/失败/重启/回退；旧三工具与新 sources 兼容回归。
- **依赖：** 1.2、1.3、2.1；平台可信附件和 Runtime 接线按原专项协同，若未接通只记录 RAG 范围验证。
- **状态：** `deferred`。现有视觉接口业务码434提示apiKey无效；在线受管图表资产与公开页码须平台协同。首期交付CLI格式证据，online保持MD/TXT。

### Task 3.1: 通用检索基线与定向优化

- **改动内容：** 建立经选择的业务语料与问题集，用实际 MCP sources 评测；记录 Recall@8、排序、证据截断、无命中、跨项目污染与延迟/用量。先比较分块、候选范围与检索模式；发现排序缺口后再试 rerank，不能因关闭 rerank 就断言质量差。
- **代码位置：** `src/knowledge/rag_engine.py` → `retrieve()`；`src/demo_support.py` → `build_lightrag()`；`citations.py` → `build_retrieval_sources()`；`scripts/`（拟新增业务评测入口）；`tests/test_knowledge_security.py` 和接入文档。
- **预期结果：** 提供可复跑的基线、失败问题与对照报告；收益、延迟和费用有证据。选出的参数不破坏单次检索、来源字段、结果预算和取消语义。
- **验证项：** 同一固定语料/问题/模型，分开运行基线与单变量候选；评测用实际 800 字符/12 KiB 输出，分块变化新建 namespace。阈值依业务要求定，不将旧 30 题 100% 作为新语料保证。
- **依赖：** 文本基线可先开展；PDF/Office 评测依赖 2.1；业务样本与预算。
- **状态：** `[x]` 完成。3份通用运维/API/发布样本、19题与跨项目负例已实测；16道有答案题 Recall@8/证据完整率均100%，3道无答案题仍返回资料，详见 Phase。没有证明需要 rerank；PDF/Office 表格表示问题在2.1定向修复，不改变 MCP 输出预算。

### Task 3.2: 容量、阶段耗时与用量优化

- **改动内容：** 复用现有 usage 与脚本记录真实文本入库/查询用量；新增确定性模型的快照复制、checksum、reader准备与空间观测，Ubuntu连续追加100个小文档。固定100文档规模用于成本基线，不等于20 MiB大文件/生产多项目吞吐验收；不改配额或删除历史。
- **代码位置：** `src/knowledge/artifacts.py` → `KnowledgeUsageRecorder`；`generations.py` → `copy_storage()` / `validate_snapshot()` / `prepare()`；`job_worker.py` → `KnowledgeJobSupervisor`；`upload_service.py` → `check_disk()`；`scripts/verify_incremental_snapshot.py` / `verify_online_knowledge.py`；相关测试。
- **预期结果：** 确定容量和 P50/P95 基线，提供阶段耗时与用量分类；重复入库零新增调用、必要图合并单列；供应商缺 usage 保持 unknown，缺费率不编造金额。保留策略先讨论，不自动删除历史或原件。
- **验证项：** 单项目持续追加、多项目排队与查询、最大允许文件、连续发布、服务重启/取消；旧 checksum、reader lease、共享锁/内存回收与配额检查同时验证。Linux 数据独立记录。
- **依赖：** 1.2、测试环境规模和预算；多模态负载依赖 2.2。
- **状态：** `[x]` 完成（观测基线范围）。100个小文档最终快照3.44 MB、保留全部历史约182 MB；复制/校验P95约28/7ms，恢复零模型调用、旧checksum不变、关闭共享键归零。生产吞吐/最大文件与多模态负载 deferred，不能据此确定生产容量上限。

### Task 4.1: 音频 / 视频需求与资源评估（deferred）

- **改动内容：** 明确会议/培训场景、时长、语言、ASR 模型、CPU/GPU 和存储费用；比较新版可选处理器。先做需求与小样验证方案，不默认安装 audio/video extras 或开放格式。
- **代码位置：** 若执行，涉及 `pyproject.toml`、`src/demo_support.py`、`src/knowledge/{config,artifacts,upload_service,generations}.py`；当前只更新本专项讨论记录。
- **预期结果：** 给出是否进入第二期的决定；若需要，单列音轨、时间戳、关键帧、资产与失败恢复的任务。
- **验证项：** 届时用短录音/中文专有词、长录音、静音视频、画面与旁白事实、超时与恢复分别定义验收，不用纯文本试验替代。
- **依赖：** 真实业务需要与资源预算。
- **状态：** `deferred`。尚无会议/视频资料、ASR场景与资源预算；不安装额外音视频栈或开放格式。

## 实施顺序与完成规则

1. 先明确 1.1–1.3 的升级与来源正确性；3.1 文本评测可独立准备。
2. 2.1 输出逐格式结果，再选择是否开展 2.2，不预先开放全部新版功能。
3. 3.1 / 3.2 有基线后，才定参数、rerank 或性能优化的最终改动。
4. 4.1 为后置议题，不影响已选择范围交付。

实施阶段按 `implement-feature` 记录 Task Completion Card 与 Phase 证据；选定范围完成后按 `verify-change` 执行 Final。未选的任务保持 deferred/待讨论，不能为使表格全绿而记为 done。代码提交与部署另遵循用户授权。

2026-10-13本期需求按用户验收标记done；6个已完成Task与6条Phase对应。格式能力partial、外部视觉条件blocked和后置Task2.2/4.1如实保留，不纳入本期通过能力承诺。
