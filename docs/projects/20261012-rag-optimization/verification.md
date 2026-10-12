# 验证计划与记录

## 规划阶段记录

- **日期：** 2026-10-12。
- **工作区：** `/Users/lijiaxin/.codex/worktrees/e5fb/rag-anything-use`。
- **已完成：** 核对 CONTEXT、经验、锁定依赖、CLI/MCP、解析适配器、签名、候选/快照/回收、既有测试和异步入库专项；建立三份规划文档与导航。
- **源码确认：** 回收明确绑定 LightRAG 1.4.12；处理签名包含依赖版本且逻辑库查询/构建都校验；文本与多模态入口不同；离线未启用在线文档级 chunk 身份；适配器未识别上游 tuple 第二项的 doc_id。
- **证据范围：** 来源冲突待复现、候选依赖完整安装待试验、Ubuntu 文档/多模态和业务负载待验收。官方修复说明不当作本项目已复现或通过记录。
- **历史参考：** 根 README / CONTEXT 记载 67 项回归与真实文本链路，见 [旧专项证据](../20261012-project-member-knowledge-upload/implementation/rag-evidence.md)。本轮未重新运行，不能充当新版验收。
- **本轮文档检查：** `git diff --check` 退出 0；标准库脚本检查 5 份改动 Markdown 的末尾换行/尾空白、16 个本地链接、8 项 Task 与验证表映射，全部通过。工作树变更仅为三份新专项文档及 README / CONTEXT 导航和状态。

## Phase 验证（每个 Task 完成后）

2026-10-12 已获实施授权。每项完成后追加：Task、实际命令/操作、版本/环境、退出状态、结果与耗时、证据路径、未验证范围。使用真实模型时记录调用数量和 usage；日志不得保存真实凭据或未授权资料。

| Task | 必须提供的证据 | 当前状态 |
|---|---|---|
| 1.1 | 安装/解析兼容矩阵、pip check、真实 content-list、多模态接口与项目回归 | 已执行，见下方记录 |
| 1.2 | 旧库签名差异、兼容/拒绝、读写切换、回退、快照与回收 | 已执行，见下方记录 |
| 1.3 | 同正文多来源复现及修复、返回契约、parser 参数、页码可信度 | 已执行，见下方记录 |
| 2.1 | Ubuntu 每格式 CLI→发布→MCP 与失败/超时/重启 | 已执行；能力partial |
| 2.2 | 在线新格式、资产保存/恢复、旧成果复用、sources 兼容 | deferred |
| 3.1 | 固定通用评测集、Recall/证据/延迟/用量 | 已执行，见下方记录 |
| 3.2 | 规模/阶段耗时/空间/用量观测基线 | 已执行；生产吞吐后置 |
| 4.1 | 音视频需求、资源与后续小样验证范围 | deferred |

### Task 1.1 — 最小依赖组合（2026-10-12）

- 候选锁：RAG-Anything 1.4.2、LightRAG 1.4.12、Docling 2.84.0、MinerU 3.4.5；FastMCP 3.2.0 保留。仅升级 RAG-Anything / MinerU 必要传递依赖，未采用 LightRAG 1.4.16。
- macOS Intel / Python 3.13.9：`uv lock --check`、基础 `uv sync --frozen --group dev`（113包）、`uv pip check`，退出0。此环境没有安装documents，不能当解析验收。
- sshmy2 独立目录 `/home/ubuntu/rag-opt-20261012-65sx7w4w`，Linux x86_64 / Python 3.13.16：`uv sync --frozen --extra documents --group dev --python 3.13`（224包）及 `uv pip check`，退出0；真实导入与 Docling installation check 通过。
- 真实可选包＋确定性模型测试：正文/表格/图片、相同正文两来源、页码回放、multimodal状态、finalize和workspace回收通过。P0组合回归 **33 passed / 11.72s**（`phase-p0.log`）。这证明调用/存储兼容，真实模型格式证据另列2.1。

### Task 1.2 — 文本签名兼容与回退（2026-10-12）

- 新在线文本签名v2只包含实际使用的核心存储依赖；MD/TXT builder仍不调用RA/Docling。模型、端点、维度、分块、prompt与多模态配置仍计入签名。
- 精确允许旧v1组合：LR1.4.12，RA缺失/1.2.10/1.4.2，Docling缺失/2.84.0，且旧多模态开关全关；逐一重算原hash，保持数据库、原件、成果和冻结快照原签名，不重写published内容。
- macOS Phase：`pytest tests/test_knowledge_upgrade.py tests/test_knowledge_generations.py tests/test_knowledge_migration.py tests/test_knowledge_artifacts.py -q` → **19 passed / 38.52s**。Ubuntu上述P0组合33项亦通过。
- 隔离回归覆盖旧签名读取→新文档追加→激活→重复零新增模型调用→回退；旧checksum不变。模型、Embedding维度/供应商及未知核心版本拒绝。实库清单/停机迁移未执行，当前交付为兼容代码与隔离演练。

### Task 1.3 — 来源与解析契约（2026-10-12）

- 先运行回归得到9失败/3通过，实际native日志确认同正文两个文档共用chunk ID；其中一项测试误用不存在的 `get_all` 已改为状态chunks_list定位，未将测试误差当源码问题。
- 修复离线默认文档级ID，并同步RA正文页码回放/多模态ID；项目opaque ID不采用上游doc_id。解析结果识别 `(content_list, doc_id)`，拒绝坏形状、保留失败/取消，可信页码来自Docling prov，缺失不标0；总页数未知保持null。
- 有效parser、parse_method和项目独立输出目录透传；并发get_rag只创建一次；关闭RA额外cache并注销atexit回调。chunk_count用实际索引状态而非解析块数量。
- macOS直接Phase **27 passed / 2.66s**；补充入库→CLI发布→MCP同正文双来源后 **12 passed / 7.28s**。Ubuntu P0组合33项通过。MCP公开sources字段保持原契约；内部页码未公开。

### Task 3.1 — 通用检索基线（2026-10-12）

- 用户选择通用资料。`test_data/evaluation` 为本项目创建的公开运维/API/发布合成资料，3份Markdown、19题，包含相似时间/数值、表格、跨文档、3题无答案及另一项目的合同诱饵；不是行业标准集或业务准确率证明。
- Ubuntu真实模型＋CLI发布＋Bearer HTTP MCP：`python scripts/evaluate_knowledge.py --output evidence/evaluation-baseline.json`，退出0。16道有答案题文档 Recall@8=1.0、按来源预览核验的证据完整率=1.0；跨项目来源0，800字符/12 KiB预算成立。3道无答案题均返回来源、no_hit=0；调用方必须依据证据判断可否作答。
- 查询P50=6.114s、P95=15.449s；3份入库分别54.789/199.222/118.963s，索引及manifest约1.30 MB。检索评测不生成最终答案；关键词提取仍触发19次LLM＋19次Embedding请求。
- 成功重试轮入库（含另一个项目诱饵）：12次LLM＋142次Embedding，含1个HTTP429；供应商入库usage累计131787 tokens，查询30403 tokens，429无usage，金额null。LLM曾耗尽8192输出预算、为空/截断并重试；不能把重试开销算成升级性能收益。首轮实体抽取失败留在隔离日志 `evaluation.log`，成功轮为 `evaluation-retry.log`。
- 评分回归 `tests/test_knowledge_evaluation.py` 验证跨文档召回与按每个doc的事实完整性。因文本基线未证明排序缺口，未加rerank/新参数；已观测的文档表格预览问题在2.1修复。
- 证据：[evaluation-baseline.json](implementation/evaluation-baseline.json)，模型和包版本均在报告中；原件全文均可公开，不包含私有凭据。

### Task 3.2 — 快照与用量观测（2026-10-12）

- 新入口 `python scripts/benchmark_knowledge_snapshots.py --documents 100 --output evidence/capacity-100-ubuntu.json`，Ubuntu退出0。确定性模型、模拟DB激活，仅测snapshot/reader路径；不是IAM授权、真实模型吞吐或生产负载证明。已有真实worker/授权桩链路另见real-online证据。
- 连续100个小文档追加：最终快照3435821 bytes，保留全部历史及控制文件182040969 bytes；复制P50/P95=0.021225/0.027727s（199次），校验0.004166/0.006695s（599次）。100文档reader准备0.088702s；恢复0模型调用，第一代checksum保持不变，关闭前/后9/0个项目共享键。
- macOS20文档自检亦退出0，最终快照707518 bytes、全部历史8479714 bytes；关闭共享键归零。两系统数据只代表各自缓存/磁盘条件，不外推最大容量或长文件表现。
- 真实模型用量来自Task3.1和 [real-online.json](implementation/real-online.json)：queued/worker、重复零新增usage、新旧来源、回退可查及冻结数据未改写全部为true。
- 当前小样本未证明复制/checksum是瓶颈，保留完整快照语义；优先限制无正文模型重试和规划历史保留策略。自动删除历史、生产多项目排队、20 MiB长文件及多模态负载未执行。
- 证据：[capacity-100-ubuntu.json](implementation/capacity-100-ubuntu.json)。

### Task 2.1 — Ubuntu 文档格式验收（2026-10-12）

- 隔离环境：sshmy2 `/home/ubuntu/rag-opt-20261012-65sx7w4w`，Linux x86_64、Python 3.13.16、RAG-Anything 1.4.2、LightRAG 1.4.12、Docling 2.84.0、MinerU 3.4.5；公开合成 fixture，不含业务资料。每种格式独立 namespace，实际 CLI ingest→publish→Bearer HTTP MCP。
- 首轮结果：文本PDF 90.426s、扫描PDF 123.085s、DOCX 238.641s、PPTX 200.600s 均可入库发布并查到选定正文事实；来源 document_id 校验通过，PPTX 的两页文本页索引为0/1。旧报告中的混合PDF表格题 `Atlas 840` 未在800字符片段找到，状态partial。
- 已修复并回归：Docling表格 `TableData` 转紧凑Markdown行，避免 `table_cells/bbox`结构字典挤占预览；未知页码在存储时保持null，不向上游页面上下文算术传None；首个解析前确保parse cache/锁初始化、重复解析只调用解析器一次；batch/fallback均隐藏资产路径；多模态共享锁按task绑定workspace。Optional包回归6项通过（8.75s），最终Ubuntu96项通过（24.92s）。
- 最新真实链路：文本PDF **done，104.616s**、扫描PDF **done，54.274s**，可信正文页范围与来源/资产路径检查通过；混合PDF **600.185s超时**、DOCX **600.086s超时**；PPTX实体抽取返回空正文，实际CLI回执accepted=false。本轮失败不得被初轮结果覆盖；Office和混合PDF稳定能力仍为partial。
- PPTX失败还复现 `main.py` 忽略CLI返回码：实际failed回执却进程exit0；先用真实子进程回归复现失败，再改一行为 `raise SystemExit(main())`，回归变为exit1。格式脚本也核对manifest ready/索引文件存在，避免将失败当成功；表格/公式/图片题必须在对应类型片段找到事实，不靠正文相同数值冒充。3个直接Phase测试通过（3.38s）。
- 视觉供应商探针HTTP200，但业务`status=434`、`msg=Invalid apiKey`、body=null、choices=0；图片分析受当前VISION凭据失效阻塞。未解包错误响应当模型正文、未擅自替换密钥/模型或改现役配置。
- `formats-final` 运行在旧main入口下于PPTX后读取缺失chunks时中断（exit1）；保存了已完成的4个格式原始报告，PPTX实际失败回执单列。入口与验证器已修正并测试；不靠反复实模型调用掩盖失败。格式用量/视觉usage无法从该轮完整获得，金额null；文本用量在3.1/real-online单独有证据。
- 最终格式判定：PDF正文/OCR小样done；DOCX/PPTX正文曾通过，但最新模型运行不稳定，图表/公式和视觉分析partial；混合PDF表格表示修复已验证，真实模型链路尚未通过。online仍只报告MD/TXT，PDF/Office/受管资产未开放。Linux超时记录、取消/父SIGKILL/重启恢复由完整回归覆盖，不把mock故障当真实PDF故障验收。

证据：[首轮格式](implementation/formats-initial.json)、[终轮格式原始报告](implementation/formats-final.json)、[PPTX真实失败回执](implementation/release-ingest-failure.json)、[视觉凭据错误](implementation/vision-auth-probe.json)。供应商/流程完整日志留在Ubuntu隔离目录，不包含私有凭据的结果已复制到专项。

## 验证矩阵

| 编号 | 场景 | 通过条件 |
|---|---|---|
| U01 | 干净 Ubuntu 安装候选锁与 documents extra | 明确 OS/架构/Python/全包版本；完整依赖可安装且无冲突 |
| U02 | RAG-Anything 1.4.2 + LightRAG 候选组合 | 解析、文本+图表 content-list、初始化/关闭可用；1.4.12 与 1.4.16 结果分别记录 |
| U03 | 旧库升级、签名变化与回退 | 旧读写受方案管理；不兼容拒绝，旧版本可恢复；active/published checksum 不被改写 |
| U04 | 更换模型/Embedding/维度/分块 | 不能绕过签名复用不兼容索引；需要时使用独立 namespace |
| U05 | 正文排队、解析/索引失败、取消 | 不把未索引正文标成 processed；异常和任务状态真实，候选失败不发布 |
| C01 | 两份不同原件正文相同、同名不同内容 | 正确 document_id / chunk_id / 来源映射，不覆盖、不按文件名猜归属 |
| C02 | parse tuple、内容块、页码和配置 | doc_id 与 metadata 分开；实际 parser / parse_method 一致，可信跨页可定位，未知不猜 |
| F01 | 文本 PDF / 扫描 PDF | 已知正文与 OCR 事实在实际 MCP 片段中可找到，独立记录各类限制 |
| F02 | DOCX / PPTX、表格/图片/公式 | 已知事实可检索，公式工具按需要验证；不能以 PDF 通过推断 Office 通过 |
| F03 | 纯图片/表格内容、Markdown 受管图片 | 选定格式的成果/资产可索引、恢复和回退；MD 无附件时不读取宿主路径补全 |
| F04 | 原件重复、成果缺失/损坏、跨项目 | 相同配置复用无新增入库模型调用；损坏拒绝或按明确策略重新处理；资产隔离成立 |
| Q01 | 业务答案、无答案、相似术语、跨文档和跨项目负例 | 使用实际 MCP 结果报告 Recall@8 / 排序 / 证据完整性；跨项目泄漏为 0 |
| Q02 | 800 字符片段、12 KiB 预算、取消与 no_hit | 完整预算仍成立；评测基于截断后的实际证据；服务错误与无命中区分 |
| Q03 | 分块/模式/rerank 单变量对照 | 相同语料与模型，独立记录新索引费用、召回收益和延迟；无证据不承诺改进 |
| O01 | 连续发布、读 lease、重启与回收 | 旧查询在候选构建时可用；无在途旧 reader 才回收；锁/内存不随版本无限增长 |
| O02 | 代表性规模、最大文件、排队、磁盘配额 | P50/P95、复制/校验/索引/激活/查询和空间有数据；超限明确失败，不污染旧库 |
| O03 | 用量与费用 | 区分解析、视觉、新块、图合并、查询；缺 usage/费率为 unknown/null，不编造金额 |
| S01 | 原静态凭据、精确授权、资产与输出边界 | 旧只读契约保持；写需 grant/ticket；路径/URL/凭据不进入公开输出；图片字节验证不替代资产授权 |

## Final 验证

2026-10-12选定范围已实施，以下按实际证据收尾。验收记录完成与格式能力通过分别判定；deferred任务不补成完成。

### 测试套件

- [x] Intel Mac / Python3.13.9最终完整回归：**90 passed、6 skipped / 27.79s**，exit0；未安装documents，6项真实可选包测试跳过。因本地无私有env，用README列出的临时假模型配置运行 `uv run --frozen pytest "tests" -q`，测试替换外部调用。
- [x] Ubuntu / Python3.13.16最终完整回归：**96 passed / 24.92s**，exit0；同一冻结锁＋documents。进程内只读加载服务器私有env后运行pytest，不复制/输出凭据。真实解析/模型格式结果另见Task2.1，不混作单元测试通过。
- [x] 候选环境安装、pip check、真实包导入、冷启动/关闭和workspace回收通过；最终日志：[macOS](implementation/final-tests-macos.log)、[Ubuntu](implementation/final-tests-ubuntu.log)。
- [x] 最终静态检查：`uv lock --check`、`ruff check --select F src scripts tests main.py`、`compileall`、`git diff --check`均exit0；Ubuntu再次pip check的224包兼容。8份JSON的指标/预算/失败状态、两份测试日志和5个锁定版本通过断言；23份专项证据/文档/公开样本/脚本对服务器实际密钥与token扫描，匹配0，不输出凭据。

### 链路验证（接口改动必须）

- [x] 文本独立namespace入库→CLI发布→Bearer HTTP MCP，实际sources与800字符/12 KiB预算验证；真实模型19题基线和同正文双来源回归均有证据。
- [x] 五种选定格式均已尝试并保留成功/失败记录；最新文本PDF/OCR通过，混合PDF/DOCX超时、PPTX空正文失败。旧iflow视觉凭据无效；10-13补充DeepSeek图片HTTP/适配器通过，完整文档与修正后的格式脚本尚未全量复跑。
- [x] 保持online MD/TXT，既有FileRef→queued→真实worker→候选激活→HTTP MCP再次通过，新旧资料、重复零新增用量、回退/冻结数据检查均true。平台授权为签名桩，不作为生产IAM验收；online新格式deferred。
- [x] 旧文本签名兼容/拒绝、模型/维度拒绝、失败隔离、取消/重启/回退与用量回归通过。Linux套件中的故障注入不替代真实PDF进程故障验收；现役停机迁移未执行。
- [x] 交付通用检索及100小文档确定性快照基线；用户未指定业务门槛，仅报告测量值，不外推真实业务准确率、20 MiB文件或生产多项目容量。

### 状态一致性

- [x] tasks的6个已完成实施Task对应6条Phase，2个Task明确deferred；P01/P02为历史规划记录。10份受影响Markdown的末尾换行/尾空白与53个本地链接检查通过；README/CONTEXT/FEATURES已对齐最终测试数和逐轮格式状态。
- [x] 平台IAM/Runtime/前端与部署结果继续在原专项跟踪，本轮只报告RAG范围；本机/桩测试不标为联合完成。
- [x] 2.2在线多模态/平台资产/公开页码、4.1音视频与生产负载明确deferred。
- [x] 快照/原件未删除，旧checksum与回退可核验；没有Git提交、现役迁移或部署。

### 最终结论

**本期需求：`done`（2026-10-13用户验收通过）。** 选定范围的实现、回归和基线/逐格式记录已交付。2026-10-12技术验收的格式能力仍为partial，用户接受该边界；不得将需求关闭改写成所有格式、多模态或生产部署通过。

| 状态 | 范围与证据 |
|---|---|
| `done` | 1.1–1.3依赖/签名/来源契约、3.1通用检索基线、3.2快照观测；2.1逐格式验收记录及缓存/表格/workspace/路径/CLI修复。两系统最终套件通过，真实在线文本链路通过 |
| `partial` | 2.1格式能力：文本/OCR小样通过；DOCX/PPTX初轮正文通过但最新失败，混合PDF表格修复后的真实链路未通过；图片/公式与修正版格式脚本全轮未验收 |
| `blocked` | 10-12旧iflowVISION凭据被434拒绝；10-13验证miaomiaoai DeepSeek图片接口/适配器可用，已提供替代条件。PPTX抽取空正文及混合PDF/DOCX600s超时仍待完整文档复验/定位，不能由图片小样视作修复 |
| `deferred` | 2.2在线多模态与公开页码、4.1音视频、真实业务语料及生产多项目/最大文件验收；现役迁移/新版部署仍不在本轮执行范围 |

已提供同一评测入口与公开样本，后续条件具备后使用独立namespace复验；不能用重复调用刷出成功轮掩盖失败。所有证据入口见[实施导航](implementation/README.md)。

### 用户验收与服务收尾（2026-10-13）

- 用户确认本期验收通过，授权Git提交/远端推送、合并主工作区并清理本worktree，明确不得覆盖既有功能。
- 本地登记的知识MCP/Embedding通过所属平台 `scripts/local-stack.sh knowledge-stop` 正常停止；Ubuntu隔离目录检查未发现遗留解析/MCP/worker进程，不接管其他服务。
- 原格式失败、模型限制和所有技术证据保持原样；需求状态done仅针对本期选择范围。
- 根据用户关于maomaoai DeepSeek的提问，使用既有私有LLM配置测试两张合成图片：当前 `deepseek-v4.1-flash`模型ID两次HTTP200/有效choices，形状/颜色/数量均正确；既有 `build_vision_model_func` JPEG路径亦通过。VISION三项仅在探针进程中复用LLM配置，未写现役env，未扩大online格式或重跑全格式。探针用例首次漏await的脚本错误已纠正，未调用模型，不计产品故障。证据见 [HTTP探针](implementation/deepseek-vision-probe.json)、[适配器](implementation/deepseek-adapter.json)。
