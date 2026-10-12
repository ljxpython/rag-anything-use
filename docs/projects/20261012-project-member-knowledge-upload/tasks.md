# 项目成员通过 Agent MCP 异步入库：任务拆分

> 2026-10-12 用户授权 G01、K01–K08 和 RAG 配置实施；平台权限、可信附件传输及 Runtime MCP 接线、前端由对应团队负责。先验证完整快照恢复增量路线，再定稿候选构建。进度以本文件为准，旧专项测试不充当在线上传证据。

代码根目录：K = `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use`；P = `/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform`。“新增”表示本专项新增；K文件已落地，P文件由平台团队实施。

## 规划交付

- [x] P01 核对已发布 namespace 锁、入库冻结、MCP 只读和平台受管附件/权限代码。
- [x] P02 确认平台成员入口、免管理员内容审核、Agent MCP 异步入库、新旧资料累计共享。
- [x] P03 完成 [方案](plan.md)、本清单、[验证计划](verification.md)、[前端交接](frontend-handoff.md)，同步 RAG 文档导航和规划状态。
- [x] P04 用户方向确认：2026-10-12回复“我同意你的上述规划和方案，将它们写回到文档中，进行细化”。覆盖原件去重、异步任务、成本目标及职责；随后明确授权G01、K01–K08和RAG配置实施，未授权部署。
- [x] P05 细化源码依据、SHA-256并发去重、处理签名/成果复用、增量技术门禁、真实费用验收与前端状态边界，移除“每次无缓存全量重建”的默认推荐。

P01–P05只表示规划和方向确认完成，不表示功能done。新增权限/发布方式若在实施中与现行规范冲突，需要就具体差异补充评审；不要求用户重复批准已确认方向。

## Phase 0：增量发布与成本技术验证

### G01 验证原生增量和成果缓存，确定最小可发布路线

- [x] **状态：完成；mock/真实DeepSeek＋百炼隔离试验通过，固定完整快照候选＋新文档原生增量。** [恢复、计数、失败隔离与回退证据](implementation/g01-evidence.md)。
- **调查/试验入口：** K `rag_engine.py:ProjectRAGEngine`、`publication.py:namespace_lock()/validate_publication()`、`demo_support.py:build_lightrag()/build_embedding_func()`；锁定LightRAG `apipeline_enqueue_documents()/apipeline_process_enqueue_documents()`、四种默认存储的initialize/finalize/index_done_callback和缓存能力，RAGAnything parser cache。使用隔离fixture和namespace，不动用户现役资料。
- **执行：** A/B建基线→重复A→新C→解析/索引/激活故障→重启→连续D；先spy/mock精确计数，再以真实DeepSeek＋已批准Embedding小语料验证。依次评估原生增量＋候选发布、成果/精确模型缓存＋候选重组；base＋delta只在前两者不满足时给出比较与补充评审，不默认建设。
- **必须交付：** 在plan第8.1节记实测路线和拒绝路线的证据；准确存储/锁/刷新/工作目录语义、调用次数/usage、受影响图合并费用、失败可见性与回退步骤。确定后只保留所需实现入口和测试，不能并行实现三套策略。
- **完成条件：** 重复原件新增解析/入库模型调用0；C不批量重做A/B，未变输入不重复外调；处理中A/B可查，失败不暴露C/破坏A/B，成功后A/B/C都可查；现行published不可变/签名/来源限制成立。
- **不能通过时：** 上传继续关闭，完成不依赖该路线的协议/权限工作；记录具体失败与最小可评审替代。无缓存全量重建不作为自动降级。
- **验证/产物：** `scripts/verify_incremental_snapshot.py`、`implementation/g01-{mock,real}.json`；后续K04/K06回归覆盖事务/lease/故障，所有存储复制先校验再恢复。

## Phase 1：RAG 持久任务与受管上传

### K01 逻辑项目库、原件与任务事务

- [x] **状态：完成；SQLite WAL/FULL、schema1、事务去重/幂等、稳定ID和可检索投影通过。**
- **开发：** `K/src/knowledge/jobs.py:KnowledgeJobStore` **新增**，`schemas.py/config.py` 新DTO/限制/开关；sqlite3 WAL、schema版本、scope唯一、稳定document_id、项目内原件hash唯一、同文档/处理签名非终态job唯一、request幂等、当前视图/可检索性。原件身份与处理签名分离。
- **完成条件：** queued之前原件已完整持久化；不同request并发相同文件最多一个处理job；相同hash/size矛盾409；改名复用，同名不同hash追加；ready且当前可查/处理中复用，failed旧key不重试，新明确提交才新attempt；跨项目同hash仍隔离。迁移旧文档无job可返回nullable job_id的ready复用回执。
- **验证：** `K/tests/test_knowledge_jobs.py` **新增**；数据库唯一约束/竞争回查、角色与原任务主体不换、同key冲突/ACK丢失、失败attempt上限、事务回滚/DB忙、当前视图回退/签名失配。

### K02 内部原字节上传与安全票据

- [x] **状态：完成；原字节流式核验、原件持久/唯一、5分钟票据、配额与显式HTTP鉴权通过。**
- **开发：** `K/src/knowledge/upload_service.py:KnowledgeUploadService.stage_upload()/submit_document()` **新增**，`K/src/knowledge/http_routes.py:register_knowledge_routes()` **新增**；流式写原字节同时计算SHA-256/长度，核验MIME/授权hash和20 MiB上限；fsync/原子归档/5分钟票据，原件与暂存/缓存/索引计入配额。
- **完成条件：** 普通HTTP显式鉴权；只有平台精确grant可产生上传/入库；部分文件不建job，票据不可跨scope/主体；同原件只一份长期文件，重复临时副本安全回收。首版不提供仅hash秒传/分片协议；超大文件明确413，不静默截断。
- **验证：** `K/tests/test_knowledge_upload.py` **新增**；20 MiB边界/超限、空/乱码、MIME伪造、symlink/穿越、实际hash不符、断流/归档或事务失败、并发相同原件、票据重放/到期/跨项目、队列/磁盘配额。未支持格式415。

### K03 MCP 提交和任务状态、内部状态查询

- [x] **状态：完成；两个约定MCP工具及内部GET已实现，旧三工具/sources和六字段/回执保持。**
- **开发：** `K/src/mcp_server.py:create_server()` 新增 `mcp_submit_project_knowledge_document(file_ref)` 和 `mcp_get_project_knowledge_ingest_job(job_id)`；共享上传服务；内部 capabilities/documents/jobs GET。补 auth.py 逻辑库 scope，保留显式 legacy 模式。
- **完成条件：** 返回bounded JSON文本＋同值structuredContent；新job持久queued后快速响应，任务不在call_tool中等解析；ready/处理中复用按真实状态返回；迁移复用可job_id=null；GET查询不触发解析/模型请求。旧三工具和sources契约保留；旧Bearer单独不能写。
- **验证：** 扩展 K 的 `tests/test_mcp_http.py`、`tests/test_knowledge_security.py`、`tests/test_mcp_stdio.py`；逐字段/annotations验证，直接 MCP 无 grant 拒绝、私有 header不外泄、内外返回一致、空注册库/未知库区分、legacy只读不需要新密钥。

## Phase 2：成果复用、增量发布与恢复

### K04 稳定文档ID、处理成果与增量构建

- [x] **状态：完成（MD/TXT）；完整12存储恢复到新workspace，仅新原件解析/入库，累计来源及失败隔离通过。**
- **开发：** `generations.py:KnowledgeGenerationService.build()` 与既有 `rag_engine.py:ingest_text()`，MD/TXT UTF-8解析成果复用；原CLI ingest不改签名。在线chunk ID包含document ID避免同正文来源覆盖，旧快照ID保留；累计资料不驱动旧文件重新入库。
- **完成条件：** A/B＋C→A/B/C再＋D→A/B/C/D，ID/来源稳定；旧原件不重新parse，旧未变模型输入不重复外调；受影响graph merge费用单列；半成品/失败文档不发布，不改published或生硬copy workspace。
- **验证：** 新 `test_knowledge_generations.py` 及G01计数回归；原件/解析缓存签名、候选失败/清单缺失、processed检查、重复模型输入计数、同名来源、模型配置变化拒绝；旧lifecycle/smoke回归。

### K08 项目内解析成果、必要精确缓存与基本用量

- [x] **状态：完成（文本成果/必要原生缓存）；完整处理签名/checksum/原子成果、实际HTTP计数、图更新费用与unknown/null通过。**
- **开发：** `src/knowledge/artifacts.py` 保存完整文本成果与处理签名/checksum，复用快照内LightRAG LLM缓存；G01无需新增Embedding缓存/全库重组。`demo_support.py`、`rag_engine.py`注入job用量，旧CLI/examples默认兼容。多模态资产跟随Linux格式后置，本版不接收该格式。
- **完成条件：** key隔离project且覆盖实际输入、provider/受管endpoint、model版本、dimensions与参数；部分/失败/坏维度/不明结果不缓存；配置变化不得误命中。图抽取/合并、Embedding、解析、cache hit/miss分别计数；provider usage缺失null/unknown，估算explicit estimated，金额有usage/费率才算。
- **验证：** 拟新增 `K/tests/test_knowledge_artifacts.py`；跨路径原件复用、损坏/missing资产、并发成果写、跨项目/配置/hash失配、精确cache命中与miss、坏向量/失败不缓存、零模型调用重复提交。管理员读脱敏计数，模型输入/key不入日志、工具或前端。

### K05 单 worker、超时、进程归属和重启恢复

- [x] **状态：完成；单supervisor/builder flock、真实进程组deadline/取消/父SIGKILL、重启failed/queued与锁回收通过（本机POSIX）。** Linux部署OS复验仍待V02。
- **开发：** `K/src/knowledge/job_worker.py:KnowledgeJobSupervisor` **新增**；主进程持久消费、构建子进程隔离解析/索引，阶段写回、安全错误、job deadline、有限重试；锁跨进程保持，停止时完整回收所属进程组。子进程不自行激活。
- **完成条件：** CPU解析在子进程，MCP/旧查询可用；30分钟deadline自领取计时；queued保留，失败不堵后续；Stop不取消已受理任务，重启不复用半写索引/缓存；完整兼容成果可复用。外部请求已发送但结果未落盘的费用不承诺exactly-once，记录unknown与有限重试。
- **验证：** 故障注入 queued/parsing/indexing/publishing 进程退出、SIGTERM/SIGKILL和ACK丢失；两个服务实例争锁、队列满、磁盘不足、超时/取消；实际在部署 OS 检查进程与锁的回收证据。

### K06 原子激活、在途查询和缓存回收

- [x] **状态：RAG完成；候选校验、start/activate签名协议、SQL原子激活、旧lease与10次mock发布缓存回收通过。** A02生产当前授权由平台团队联验。
- **开发：** `K/src/knowledge/generations.py:activate()/acquire()` **新增**，复用读副本 `ProjectRAGEngine.close()` 与publication校验；候选flush/finalize→主进程校验/读初始化→发布前授权→active/job/document同SQLite事务；读请求固定版本/lease。
- **完成条件：** 旧查询不中断；失败/未授权/候选未完整时新内容和半写图关系不污染旧查询；成功后旧＋新可查，单请求固定视图/清单/来源；base/签名/grant变化不激活，旧缓存无在途才回收；历史来源保持。
- **验证：** 并发查旧/新与持续上传；切换前/后崩溃、初始化失败/权限拒绝；active与job状态一致；多次发布内存/锁不线性增长，目录和原件保持可回退。

### K07 注册、旧库迁移、显式回退与格式能力

- [x] **状态：完成（MD/TXT）；注册/冻结旧库迁移/显式回退、旧ID和nullable job回执通过。** PDF/Office及Linux逐格式验收后置，能力列表继续仅MD/TXT。
- **开发：** `K/src/cli.py` 三个管理员命令和对应项目库服务；迁移原件/归属/模型检查并保留 document_id；回退指针、searchable准确投影；Linux格式探针与支持表；更新 env/文档规范。
- **完成条件：** 迁移原件hash去重，保留ID并报告多个旧ID同hash的冲突；没有旧job时复用回执job_id=null。初始化成果缓存若需一次模型费用要单列，不隐藏在第一次普通上传。缺原件/不兼容签名时关闭上传但旧查询保持；回退searchable真实，所有资料恢复才重启上传。PDF/Office各自Linux证据通过才开启。
- **验证：** 完整/缺原件/不兼容格式/错scope迁移；签名匹配与不匹配回退；旧只读程序恢复演练；Linux逐格式原件→解析→索引→MCP检索，不能用md替代PDF证据。

## Phase 3：Platform API 与 Runtime 接线

### A01 成员知识权限、项目状态接口与审计

- [ ] **状态：待开始；依赖 P04/K03。**
- **开发：** `P/apps/platform-api/src/platform_api/modules/iam/application/policies.py` 增加精确权限；新 `modules/knowledge/{router,service,schemas}.py`、`adapters/knowledge/client.py`，注册 `entrypoints/http/router.py/bootstrap/lifespan.py/config.py`。文档/任务列表复用 OffsetPage、统一错误和当前actor；补 `modules/audit/http_resolution.py`。
- **完成条件：** executor也可read/upload；非成员、撤权、错误项目403/404；内网资源不能由客户端指定；项目面板只看安全共享信息；运行时write权限矩阵不变，无平台新入库表。
- **验证：** `P/apps/platform-api/tests/test_knowledge_member_upload.py` **新增**，扩展审计/binding测试；三角色、非成员、服务账号现有有效grant/撤销、返回污染、HTTP失败、读超时、SQL不阻塞事件循环/Session不跨线程。

### A02 精确短时授权与 start/activate 当前复核

- [ ] **状态：待开始；依赖 A01。**
- **开发：** 新知识service `authorize_knowledge_operation()`、内部 authorize路由；复用已验证主体重建当前actor和HMAC模式，专用knowledge key；upload时Thread ACL＋项目权限，后台start/activate时项目当前成员/凭据/项目生命周期。
- **完成条件：** 静态RAG Bearer或伪user_id不能上传；过期/错aud/错scope/错操作/改正文被拒；发布候选与base绑定；权限服务不可用不发布；密钥不进入浏览器/模型/审计正文。
- **验证：** 签名/重放/时钟/正文篡改、撤权、禁用主体、撤销服务凭据、项目归档；审批前后/排队后/激活前撤权；记录并确认30秒授权窗口的边界。

### R01 受管附件到 MCP 的官方 interceptor

- [ ] **状态：待开始；依赖 K03/A02。**
- **开发：** `P/apps/runtime-service/src/runtime_service/tools/knowledge_upload.py:knowledge_upload_interceptor()` **新增**，`tools/mcp.py:load_mcp_tools()`、`tools/knowledge.py`、`runtime/mcp_config.py`；从当前Thread可信附件记录核对六字段/FileRef内容hash，受管原字节传输、私有 headers、同key回查、任务输出脱敏。
- **完成条件：** 非当前Thread/模型伪造ref不能读；模型无scope/hostpath/url/base64/token参数；业务任务属于RAG，Runtime不阻塞等解析、不建第二队列；已受理ACK丢失不重复建任务。
- **验证：** `P/apps/runtime-service/tests/tools/test_knowledge_upload.py` **新增**，扩展同目录 `test_knowledge_http_contract.py`、`test_knowledge_result.py`；FileRef六字段/名称/hash/所有权、上游恶意DTO、禁secret/history泄漏、网络未知提交、Stop/CancelledError和有界结果。

### R02 两主图、工具审批与 Plan/deny 边界

- [ ] **状态：待开始；依赖 R01。**
- **开发：** `P/apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` 与 `services/demo/showcase_demo/agent.py`、`runtime/capabilities.py`；共同精确写工具白名单/批准配置、提示词，保留 `runtime/access_policy.py:interrupts_for_access_policy()` 语义，不把共享上传归为workspace写。
- **完成条件：** 两主图普通执行按能力/权限装配；review/workspace_write用原审批，full_access沿原策略；Plan/schema-only/offload/子图/unbound/deny不提权；批准后再次查当前权限。
- **验证：** 现有 `P/apps/runtime-service/tests/services/test_knowledge_composition.py`、DearFlow MCP、Plan/HITL测试扩展；陌生mutation拒绝、catalog/tool refresh一致、改变审批参数重验、denied工具不在提示/执行链。

### O01 配置、所属启停和跨仓活文档

- [ ] **状态：RAG配置/活文档已完成；平台配置/local-stack及联合启停由平台团队接续，O01整体未完成。** [RAG接线交接](implementation/rag-handoff.md)。
- **开发：** K `env.example`、`README.md`、`AGENTS.md`及现有运行/接入指南；P两服务 `.env.example`、`P/apps/runtime-service/docs/standards/project-knowledge-mcp.md`、API权限/审计活规范，`P/scripts/local-stack.sh` 及实际负责知识资源配置的脚本；两仓 FEATURES/CONTEXT，功能实施后加用户可见CHANGELOG。
- **完成条件：** 默认关闭在线上传；legacy查询不依赖新secret；每个服务配置scope一致、Bearer安全；local-stack回收supervisor子进程，不共享其他worktree依赖/服务；不开Docker、不自动生产发布。
- **验证：** 干净配置冷启动、缺失配置能力降级、旧CLI/MCP回归；本worktree测试资源注册/start/status/stop/restart检查；三服务最终配置示例无真实secret。

## Phase 4：独立前端接续和真实验收

### F01–F03 前端同事实施

- [ ] F01 复用聊天附件上传进度/20 MiB限额、明确项目共享入口、现有审批；普通附件不自动入库。
- [ ] F02 queued与耗时处理分离、reused按已入库/处理中显示、nullable job_id不轮询、安全错误和项目列表；不在前端判定hash重复。
- [ ] F03 切项目/撤权/迟到响应、离开返回、failed明确重提、ready/searchable、重复改名/同名不同内容和新旧资料浏览器验收；前端不展示模型费用/数据库拓扑。

依赖A01/R02及真实fixtures；准确文件/组件、话术和前端验收见 [frontend-handoff.md](frontend-handoff.md)。非前端开发者提供协议样例和真实工具结果，不能用“前端已交接”代替F01–F03完成。

### V01 非前端完整链路与故障验证

- [ ] **状态：待开始；依赖G01/K01–K08/A01–A02/R01–R02/O01。**
- **开发/执行：** `P/apps/runtime-service/tests/e2e/test_knowledge_member_upload.py` **新增**，复用既有知识真实平台fixture；隔离native服务、DeepSeek真实模型、两个项目/两个主图/多个成员。填 [verification.md](verification.md) 的Phase证据。
- **完成条件：** 验证计划E01–E16、C01–C06及安全/恢复/回退/性能门禁有证据；重复零新增入库调用，新增不批量重做旧资料，真实usage与未知计费边界明确。前端未实施时只记非前端Phase，不宣称全项目done。

### V02 前端联合 Final 与部署演练

- [ ] **状态：待开始；依赖 V01/F01–F03/兼容Linux及代表性资料。**
- **执行：** 用户同事前端浏览器链路；Linux文本及逐格式真实解析；部署/回退演练。先核对sshmy2当前源码、namespace、原件和进程，部署仅在对应实施/环境授权内进行。
- **完成条件：** 全部范围完成、关键链路/权限/故障/回退测试通过；Phase与Final记录分离，如实说明PDF等未通过项；关联规范需要时同步，不将原专项未完成草案整体“毕业”。

## 进度与外部条件

| 范围 | 当前状态 |
|---|---|
| 方案和交接 | 方向及RAG实施已授权；前端契约保持，RAG内部接线补充完毕 |
| G01增量/缓存与发布技术路线 | done；mock/真实计数、失败隔离与回退证据已提交到implementation |
| G01、K01–K08、RAG配置 | done（UTF-8 MD/TXT）；真实RAG worker/HTTP/MCP通过，默认online关闭 |
| API/Runtime/平台运维代码 | 平台团队实施；本轮未改该工作区 |
| 前端业务代码 | 由同事接续，待开始 |
| 新功能测试/联调/部署 | RAG78项回归、[provider两项修复/实际平台HTTP](../20261012-rag-provider-contract-alignment/README.md)通过；Runtime Agent/可信附件、前端、Linux格式/负载及部署待执行 |

整专项partial。增量底层及RAG文本实现已验证；剩余是平台IAM/可信附件/Runtime、前端、Linux documents与实际负载/部署条件。请求金额缺可确认费率为null；已发送但未知结果不承诺exactly-once计费。只保留完整快照增量单一路线，published不可变；无自动全量重建降级或生产发布。

依赖主线：G01→K08/K04→K05→K06（另依赖A02）→K07/O01→V01→F01–F03/V02。K01–K03/A01–A02可在技术试验并行准备，但不在G01通过前开放在线上传。
