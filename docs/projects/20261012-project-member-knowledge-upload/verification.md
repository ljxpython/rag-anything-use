# 项目成员通过 Agent MCP 异步入库：验证计划与记录

> 未勾选矩阵仍是待执行的**跨团队完整验收**，不能据此否认或夸大局部通过结果。G01、K01–K08及RAG配置文本范围已执行，真实命令/结果见第7、8节；第1节保留早先规划历史，不复用旧专项结果充当在线上传证据。整专项partial，平台/前端/Linux/部署未联合验收。

## 1. 本轮规划检查

- [x] 已读取 K `docs/CONTEXT.md`、`AGENTS.md`、`docs/lessons/rag-knowledge.md`，核对CLI、MCP、flock、manifest、引擎缓存和受管附件/平台权限源码。
- [x] 已确认普通成员、现有平台、MCP异步、自动项目共享、新旧资料累计保留。
- [x] 已生成方案、任务、前端交接；本专项不改业务代码。
- [x] 文档引用/路径、格式、diff和改动范围检查；结果见下方规划检查记录。

### 2026-10-12 初版规划检查记录

针对本专项五份Markdown及三个导航/状态文件执行只读文档自检：19个本地链接、48处现有代码路径、4份JSON示例均通过；拟新增文件已标注。`git diff --check`通过，新增文档也单独检查了行尾空白、最终换行和JSON有效性。

改动范围为本专项README/plan/tasks/verification/frontend-handoff、K根README、K的CONTEXT/FEATURES，共8份文档；未修改业务源码、依赖锁、环境配置或数据库，未commit/push，未启停服务或部署。原有未跟踪 `20261012-bailian-embedding` 三份文档保持不动。这些结果仅证明规划文档可读，不证明新功能通过。

### 2026-10-12 本轮细化与检查

- [x] 记录用户对去重、异步、增量成本目标和职责的方向确认；当前授权只细化文档。
- [x] 核对LightRAG1.4.12的ID/content去重、NanoVector upsert的Embedding调用、HTTP后台upload/track_id；核对与uv.lock hash一致的RAGAnything1.2.10 wheel的路径/mtime解析缓存，不假定本机安装了documents extra。
- [x] 增加G01技术验证任务、原件/处理签名分离、精确成果复用与成本断言，取消无缓存全量重建默认推荐；同步前端uploading/queued/reused/job_id为空的边界。
- [x] 本轮文档自检：8份Markdown、23个本地链接（含3处标题锚点）、5份JSON示例、16个独立技术/开发任务标题与38个U/E/C验收ID均通过；无尾空白或缺最终换行。`git diff --check`通过，未跟踪的专项文档另由自检覆盖。
- [x] 修改范围检查：K的8份文档；33份受保护的src/tests、AGENTS、pyproject/uv.lock/env.example和另一专项文件SHA-256与本轮开始时一致。P工作区`git status --short`为空；未写业务代码、配置、数据库，未启停服务/部署/commit/push。

本轮检查是文档验收，不是G01或新功能测试。业务U01–U16、I01–I12、E01–E16、C01–C06、前端和真实模型/故障/回退门禁均仍待执行。

## 2. 执行环境与证据

- 平台在授权的worktree资源内：先读 `P/docs/standards/worktree-development.md`，用 `P/scripts/local-stack.sh` 管理独立native PostgreSQL/Redis，`RUNTIME_BACKEND=local`。知识任务的SQLite/namespace/原件同样专属测试目录，不能使用用户现役语料。
- K独立`.venv`，`uv sync --frozen --group dev`；需要PDF/DOCX/PPTX的兼容Linux另外安装documents extra。不得共享其他worktree的环境，不因Intel macOS依赖不支持擅自引入Docker。
- 模型先沿当前miaomiaoai `deepseek-v4.1-flash`；Embedding使用此次部署已批准provider/模型/维度，一套测试namespace内不能临时更换。网络模型调用真实花费单独统计，不把RAG抽取费用伪装为平台已跟踪Usage。
- 先录baseline、git HEAD、锁包版本和安全配置摘要；不得打印`.env`、Bearer、grant、原文或模型Key。每条E2E记录actor/角色、project/thread/run/tool_call/job/document/版本关联、status转换、source ID、耗时和脱敏结果路径。
- Phase逐任务检查与Final全部回归独立填写；未有真实业务corpus时标注合成样本，不能声称真实业务准确率。

## 3. 单元与契约检查

| ID | 待测范围 | 验收断言 |
|---|---|---|
| U01 | 逻辑库/任务SQLite事务 | scope唯一、同key幂等、冲突409、失败事务不产生半个job/active |
| U02 | 原字节与票据 | MIME/size/hash/UTF-8/名称/路径边界；完整原件先落盘；一次性/过期/重放/跨主体拒绝 |
| U03 | 稳定ID与累计清单 | A/B＋C→A/B/C，继续D→A/B/C/D；同名不同内容ID不同，同内容去重；失败资料不污染后续 |
| U04 | 发布保护 | published namespace仍拒写，候选manifest/ready/签名匹配；不可复制路径hash不同的workspace冒充索引 |
| U05 | 版本切换 | active/document/job同事务；一次检索固定版本；在途读不提前close，旧缓存正确回收 |
| U06 | worker/recovery | 单writer所有权、deadline、queued恢复、半写改新namespace、有限重试、进程回收、状态一致 |
| U07 | 身份和grant | 当前成员/credential/project，签名/aud/operation/hash/TTL，错误scope/伪user_id拒绝，撤权回查 |
| U08 | Runtime附件权限 | 必须当前Thread已登记FileRef逐字段匹配，hash不符/跨Thread/伪ref/任意URL/hostpath拒绝 |
| U09 | 官方MCP+精确写白名单 | 只增加指定submit；metadata/schema/resource校验；其他write不放开，legacy仍可查询 |
| U10 | Plan/HITL/tool deny | 两主图一致；review/workspace_write审批，full_access沿旧策略；Plan/schema/offload/子图不扩权 |
| U11 | 输出和审计 | JSON文本=structuredContent、≤4KiB；来源旧12KiB限制；无key/path/grant/private state/未授权Thread |
| U12 | 平台API边界 | actor当前权限、项目隔离、OffsetPage/统一ErrorResponse、异步DB线程/事务和client生命周期 |
| U13 | 解析前去重/竞争 | 实际原字节流式hash校验；相同project/hash稳定document，同处理签名非终态job唯一；并发不同request只启动1个job，改名复用/同名不同内容追加；failed旧key不重试 |
| U14 | 成果与精确缓存 | 路径/mtime变化不替代hash身份；parser/normalizer/model/维度/输入参数严格匹配；跨项目隔离；坏checksum、缺资产、部分/失败/坏维度向量不当完整成果；重启可读完整缓存 |
| U15 | 复用/回退DTO | 已ready当前可查复用、处理中复用、迁移无job的ready/null回执；配置变化不误报reused，回退searchable真实；GET无模型调用，复用不覆盖原job主体/尝试/时间 |
| U16 | 用量与计费证据 | parse/embedding/extraction/affected_graph_merge分开计数；cache hit不外调；实际usage与estimated/unknown明确，缺费率不输出伪金额；正常Agent/query不计入零新增入库断言 |

- [ ] U01–U16通过，相关旧CLI/HTTP/stdio/lifecycle/knowledge来源/binding/附件/审批/Plan测试回归。
- [ ] 代码按仓库现有 lint/type/check 流程检查。无业务代码时本轮不提前创建镜像实现的空测试。

实施后的常用命令（文档中的命令不带RTK）：

```bash
# 在 K 仓库，mock/契约套件不依赖真实模型
uv run --frozen --group dev python -m pytest "tests" -q

# 在 P/apps/platform-api，实际命令/测试选择按该服务 README 与新增文件更新
uv run --frozen python -m pytest "tests/test_knowledge_member_upload.py" "tests/test_knowledge_mcp_bindings.py" "tests/test_audit_http_resolution.py" -q

# 在 P/apps/runtime-service；新增文件落地后执行
uv run --frozen python -m pytest "tests/tools/test_knowledge_upload.py" "tests/tools/test_knowledge_http_contract.py" "tests/services/test_knowledge_composition.py" -q
```

真实平台E2E沿既有 `P/apps/runtime-service/tests/e2e/test_knowledge_platform.py` 的专用环境配置方式接续，不能仅运行mock工具服务器后标为真实Agent链路。

## 4. 集成与故障验证

- [ ] I01 HTTP文件完整接收→MCP同主体票据受理→SQLite queued，未知提交重放返回同job。
- [ ] I02 按G01选定路线的成果复用→新内容处理→稳定累计清单→flush/finalize/读初始化→权限→active事务；每步失败旧active继续读，未完成图关系不污染旧查询。
- [ ] I03 K→平台start/activate当前授权；模拟禁用账号、成员撤销、服务凭据撤销、项目归档、平台503和过期grant。
- [ ] I04 并发相同原件（不同成员/request）、重复key和不同文件；同原件只1处理任务和原件，不换原主体，只有一个writer；C/D成功后集合完整。跨项目不共享票据、缓存或返回去重信息。
- [ ] I05 queued/parsing/indexing/publishing各点中断、SIGKILL/重启、磁盘满、DB忙、远端模型429/超时/坏响应；不误报ready，不卡住后续队列。
- [ ] I06 已受理后聊天Stop/离开/Thread删除：入库继续，RAG原件可用，历史Run不被自动恢复或迟到工具结果污染。
- [ ] I07 迁移缺原件/错签名/不支持格式：显式失败，旧查询仍可用，无“仅新资料”的不完整版本。
- [ ] I08 运维关闭上传→回退active→新版本再激活；各步searchable/来源清单符合当前版本，无删原件/半写索引。
- [ ] I09 首版格式动态能力一致；Linux未装documents extra时PDF返回unsupported，不能影响MD/TXT和旧查询。
- [ ] I10 安全原件归档但job事务失败、原件未完成上传/断流、队列满/额度已预留；不误报accepted，不留可执行半原件，孤立/重复暂存可安全回收。
- [ ] I11 解析资产、模型结果落盘前/后中断；完整兼容成果重启复用，坏/部分成果不复用；已发外部请求但结果未知按有限恢复策略记录费用不确定，不承诺exactly-once外部计费。
- [ ] I12 迁移原库同hash多个ID冲突、缺缓存、job为空；不静默丢文档/改来源，管理员报告后处置；一次初始化费用单列，旧资料复用不新增queued任务。

## 5. 真实端到端验收

| ID | 操作 | 必须观察到的结果 |
|---|---|---|
| E01 | executor成员上传MD，明确要求入库，真实DeepSeek Agent调用MCP | 普通成员成功；返回kj/kd与queued，解析不阻塞整次Run等待 |
| E02 | 项目B其他成员另一Thread查询新/旧资料 | 在项目B自己的资料范围；A资料不可见，错误ID不能泄露A归属 |
| E03 | 项目A另一成员/另一Thread，在job ready后查询旧问题和新问题 | 旧资料和新资料都命中预期document_id，来源名称正确；不是只剩最新文件 |
| E04 | g2构建期间连续查旧问题，激活后连续查新/旧问题 | 旧资料不中断；active不混用manifest/index，后续包含累计资料 |
| E05 | 原件ready后同key重放、改名再次上传、同名不同内容上传 | 重复返回已有doc/job且reused=true，新解析/入库Embedding/LLM请求0；同名不同内容两文档都可溯源。用RAG侧计数证明，不靠ToolResult成功判断费用 |
| E06 | 排队后/审批后/发布前撤销提交者项目成员资格 | 下一次当前授权拒绝，新增不发布；旧已发布文档仍项目共享 |
| E07 | review/workspace_write/full_access，Plan与deny/unbound分别发起 | 原HITL策略准确；不可写模式无side effect，取消审批无原件入库 |
| E08 | 提交后Stop/离开聊天，再回来看状态 | RAG后台任务继续；可轮询最新状态；不会自动重启已Stop Run |
| E09 | 构建时故障/重启，回查同任务，下一份有效文件再提交 | 状态真实、有限重试，旧知识仍查得到，后续队列可恢复 |
| E10 | 显式回退旧累计版本，再恢复新累计版本 | 回退期间最新资料暂不可查有准确提示，旧资料可查，恢复后新旧齐全 |
| E11 | DearFlow与Showcase分别完成E01/E03关键链路 | 公共MCP能力接线一致，官方Adapter/真实Worker均在链路中 |
| E12 | 兼容Linux分别上传PDF、DOCX、PPTX并在另一成员检索 | 每格式有独立原件/解析/索引/来源证据；不以工具parse或MD结果替代 |
| E13 | 近20 MiB代表性文件、恰好上限与超限，分别正常和断流上传 | 传输期间前端uploading；完整落盘/任务受理后queued，Agent不等解析；超限413/断流无job，解析超时failed，旧资料可查 |
| E14 | 成员A处理资料期间成员B上传相同原件，再撤销A的上传权限 | B复用原job且不启动第二处理；原主体未被替换，发布按A当前权限拒绝；失败后B明确新提交才能新attempt |
| E15 | A/B旧库依次上传C、D，记录每个job的模型输入安全摘要/调用计数并持续查旧资料 | 只解析新增原件，旧未变输入不批量外调；新图合并费用单列；发布后A/B/C/D都可查 |
| E16 | 迁移文档无历史job，再通过Agent明确提交同原件；分别当前可查/回退不可查 | 可查时ready/reused=true/job_id=null并不处理；前端不轮询空ID。回退时searchable准确、上传关闭，无虚假“已可查” |

- [ ] E01–E11、E13–E16在隔离真实平台完成；E13具体语料和解析资源用部署支持范围限定，不把生成20 MiB文本当成全部格式压力证据。
- [ ] E12只有计划开放的格式通过才宣称支持；如仅MD/TXT范围完成，记录格式后置，不宣称PDF/Office已验。
- [ ] F01–F03前端Vitest/types/lint/build及真实浏览器E01/E03/E04/E06/E08完成；后端测试不能替代前端。

## 6. 成本、性能和安全门禁

### 6.1 G01和首版必过的费用断言

测试计数按job/attempt区分，持续进行的原job费用不能归入重复提交者。用provider实际请求spy/安全摘要计数和usage响应交叉核对；正常检索、Agent思考另计。真实小语料baseline和新增文件计数必须留证，mock精确断言用于证明分支，不能替代真实模型路线。

| ID | 场景 | 通过标准 |
|---|---|---|
| C01 | 已ready且可查的相同原件，原名/改名重复提交 | 新job=0，新parse=0，新入库Embedding=0，新图抽取/合并LLM=0；复用原文档；允许网络再次传原件 |
| C02 | 进行中相同原件并发提交/ACK丢失，同key与不同key | 合计只一个处理job；后续提交不新建解析/模型请求。原job已有请求归原attempt，不承诺其总费用0 |
| C03 | 已发布A/B新增C，再新增D；处理配置不变 | 旧A/B/C不再次parse；不批量Embedding/抽取旧未变输入；缓存路线精确旧输入miss导致外调则不通过。新内容/受影响图合并请求单列，不将图变化必要费用当成全库重建 |
| C04 | 改parser/LLM/Embedding provider/model/dimensions或跨项目 | 旧成果不会错命中；线上配置变化拒绝继续普通上传，管理员重建费用单列。兼容独立解析成果可复用，旧向量不作为新模型索引 |
| C05 | 正常关闭后重启，再重复上传/新增；缓存损坏和处理中崩溃另测 | 完整兼容成果持久复用，正常重启不丢去重；损坏/结果未知明确恢复路径和计数，有限重试，不伪造“零收费” |
| C06 | provider返回usage/不返回usage、费率已知/未知 | 实际/estimated/unknown标明；token或费率缺失时金额null。分parse、Embedding、图抽取/合并、query/Agent，模型输入/密钥不输出 |

- [ ] C01–C06通过；G01若不通过C03和一致性，不将无缓存全量重建当成已获批准的自动降级。

建议证据汇总字段：job_id/attempt、基线revision、新document_id、原件/处理签名安全摘要、parse_count、embedding_requests/input_items、extraction_requests、affected_graph_merge_requests、cache_hits/misses、usage_source、input/output_tokens、currency/amount（允许null）、处理时间、RSS、原件/缓存/索引字节。只有统计摘要，不保存业务原文到证据文件。

### 6.2 处理时间、可用性与安全

- [ ] 用3/10/代表性最大语料规模，测baseline后仅新增一份的处理耗时及外部请求增量；若路线重组候选，再记CPU/IO重组开销。费用随新增/受影响图数据变化，不能仅给全库平均值或单文档首次入库结果。
- [ ] 同时持续检索：记录构建期间与切换前后P50/P95/失败率，旧文档不出现因上传导致的namespace锁错误。首版目标：本地受理接口持久落盘后2秒内返回、MCP submit不等待解析；文件传输和Agent模型思考耗时单独统计。
- [ ] 30分钟处理deadline、20 MiB上限、队列和原件/解析资产/缓存/保留索引额度能安全终止/拒绝；连续10次发布未关闭引擎/锁/进程不线性增长。旧版本和缓存磁盘增长需明确维护上限，不用内存检查代替磁盘检查。
- [ ] 检索质量用旧问题、新问题、无答案、跨项目问题；稳定document_id召回验证，记录Recall@8和错误来源，不借合成用例宣称业务质量。
- [ ] 文件格式安全（OOXML压缩展开资源有界/解析deadline、PDF异常文件）、路径/SSRF/引用伪造、payload注入、signed-header重放、审计/ToolResult/历史secret泄漏检查。
- [ ] 回退准备与执行证据齐全；不自动删除namespace、不直接复制正在写或未经存储/workspace一致性核验的索引、不改变Embedding后复用旧向量。G01验证的受支持快照/恢复与粗暴目录copy分开判定。

## 7. Phase 验证记录

本次授权技术任务完成9项，以下Phase记录9条。P01–P05为第1节已验的早先规划交付，单独计数，不当作功能Task。环境：Intel macOS/Python3.13，隔离合成资料，HEAD `790da30df5feabee6b988dd660adb0ac1acddf81`，包版本保持；未commit/push/部署/改现役库。所有命令在RAG仓库执行。

### Phase G01 · 2026-10-12 · done

执行 `uv run --frozen --env-file ".env" python scripts/verify_incremental_snapshot.py --output <g01-mock.json>` 及同命令加 `--real --output <g01-real.json>`。完整12存储恢复/重复A零外部调用，真实C/D各3LLM/10Embedding，旧相同输入重发0；失败候选不processed/旧checksum不变，回退A/B可查。选择完整快照独立候选＋新文档原生增量；[计数与恢复证据](implementation/g01-evidence.md)。小语料不代表规模/平台或格式验收。

### Phase K01 · 2026-10-12 · done

`KnowledgeJobStore` WAL/FULL与唯一约束；`tests/test_knowledge_jobs.py`随本轮Final67项通过。8线程相同hash一文档/job，原主体不换，同key冲突/failed不自动重试，新key最多3attempt；跨项目隔离、事务回滚、迁移ready/null、回退searchable通过。

### Phase K02 · 2026-10-12 · done

执行 `uv run --frozen --env-file ".env" pytest tests/test_knowledge_upload.py tests/test_knowledge_migration.py -q`，18 passed in3.29s。原字节先持久、hash/size/UTF8/MIME/path/票据核验，断流不建job，symlink/过期/配额拒绝，同字节MD/TXT扩展名复用唯一原件。20MiB逻辑按缩小边界测试，代表性上限负载未验。

### Phase K03 · 2026-10-12 · done

新增在线HTTP/MCP协议测试及原HTTP/stdio/security随Final67项通过；真实 `verify_online_knowledge.py`另执行成功。六字段严格FileRef、MCP JSON文本=structuredContent≤4KiB、内部GET/OffsetPage、无grant拒写、legacy独立只读、稳定sources通过。平台实际 IAM/官方 Runtime interceptor仍由平台团队验收。

### Phase K04 · 2026-10-12 · done（MD/TXT）

执行 `uv run --frozen --env-file ".env" pytest tests/test_knowledge_generations.py tests/test_knowledge_worker.py tests/test_knowledge_artifacts.py tests/test_llm_configuration.py -q`，当时14 passed in7.00s；后续10次发布和Final67项通过。完整冻结快照新workspace恢复，只处理新原件，文档ID/累计来源保持；字节不同但相同正文的两资料来源不覆盖。真实HTTP计数和失败/回退见 [G01](implementation/g01-evidence.md)、[RAG链路](implementation/rag-real-chain.json)。

### Phase K08 · 2026-10-12 · done（文本成果）

先执行 `pytest tests/test_knowledge_artifacts.py tests/test_llm_configuration.py -q`，4 passed in2.11s；再上述14项及Final通过。成果原子写/checksum与完整处理签名、配置/hash/scope失配拒用；LLM独立重试client/每次HTTP计数，Embedding共享队列阶段按实际输入/旧vector归类回归通过。真实A：new_chunk1/new_graph11；B：new_chunk1/new_graph8/affected_merge1；各parse1/extraction2。未知usage/金额null；没有第二套Embedding缓存和未支持多模态成果。

### Phase K05 · 2026-10-12 · done（本机POSIX）

执行 `uv run --frozen --env-file ".env" pytest tests/test_knowledge_worker.py -q`，6 passed in9.03s。真实进程组deadline/取消/子SIGKILL与锁释放、两个supervisor争锁、残留builder锁等待、实际父SIGKILL→子stdin watchdog退出→新supervisor恢复failed/queued通过。部署Linux实机与平台Stop/迟到消息仍待联合验收，不借本机证明。

### Phase K06 · 2026-10-12 · done（RAG）

上方14项及Final67项通过，真实RAG链路另通过；候选flush/checksum/读初始化、当前activate grant、base/签名再查与active/job/document同SQL事务；旧查询lease保持、拒授权/base变化不active、checksum损坏拒绝、回退准确、10次mock发布旧workspace KV/锁回收。最后独立执行generations套件6 passed in9.28s：暂停候选复制时500ms内仍可取得旧reader，取消恢复等待后台IO结束才清目录。代表性规模P50/P95和平台A02真实撤权待联验。

### Phase K07 · 2026-10-12 · done（MD/TXT）

上方上传/迁移18项及Final67项通过；完整迁移保持旧document_id、原件hash/归属及新workspace，新增模型请求0、旧资料ready/null回执；缺原件和legacy读锁未释放均拒绝迁移，不改旧索引。注册/上传启停/回退三CLI已落地。capabilities仅MD/TXT；PDF/DOCX/PPTX和Linux实机后置，不宣称支持。[管理员接线与回退](implementation/rag-handoff.md)。

## 8. Final 验证记录

2026-10-12，按verify-change对**本次授权RAG范围**做Final，未勾平台/前端任务不阻止已授权范围收尾，也不假报整专项done。

```sh
uv run --frozen --env-file ".env" pytest "tests" -q
uvx ruff check "src" "tests" "scripts" --select F,E9
git diff --check
uv run --frozen --env-file ".env" python "scripts/verify_online_knowledge.py" --output "docs/projects/20261012-project-member-knowledge-upload/implementation/rag-real-chain.json"
```

测试67 passed in35.76s；ruff F/E9、diff空白通过。真实链路6项checks全true：持久queued、真实worker ready、重复0新增usage、MCP新旧来源、回退searchable、published文件不变。授权端是本地签名平台桩，模型实际HTTP；与平台真实Agent验收分开。锁文件与HEAD逐包比较，未升级任何包，httpx0.28.1/Starlette0.52.1只声明直接依赖。

保留失败事实：前一次全量为1 failed/66 passed in41.15s，父SIGKILL fixture在15秒内未到达ready marker，SQL仅parsing、builder日志为空；没有将该轮标为通过。测试补spawn/ready阶段诊断、所属子PID失败回收，将两个解释器冷启动窗口设30秒，业务1800秒deadline不变。随后worker套件6 passed in18.07s与上述Final67项通过；生产Linux启动/看门狗仍须复验。

文档/状态自检：15份Markdown、54个本地链接、JSON示例和证据有效；9项完成与9条Phase一致，所有锁定包name/version/source与HEAD相同。新增文档另检查行尾空白与最终换行。

状态一致性：本次G01/K01–K08共9项完成与9条Phase记录对应；O01仅RAG部分完成，A/R/F/V及平台运维未勾；项目README/根README/CONTEXT/FEATURES/AGENTS和接入/运行指南已同步。前端交接六字段/回执无变更。完整证据与风险汇总见 [RAG实施验收](implementation/rag-evidence.md)。

**最终结论：`partial`（整专项）；本次授权RAG文本范围 `done`。** 剩余：平台IAM/可信附件/Runtime两主图/审批/Stop、前端浏览器、Linux进程/逐格式解析、代表性20MiB/规模/业务召回及部署回退。online默认关闭，现役资料未动；外部费用不承诺exactly-once，provider没有可确认币种/费率时金额null。
