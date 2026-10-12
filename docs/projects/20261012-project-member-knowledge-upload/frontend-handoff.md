# 前端交接：项目成员通过 Agent MCP 异步入库

> 2026-10-12。用户已确认去重、异步入库、成本优先与各层职责，现细化前端交接。接口和增量发布尚未实现/验证；后端实施后提供最终DTO和真实fixture，再由同事接续前端。本文不是已上线接口说明。

## 可以直接转发的话术

“这次支持普通项目成员把文件加入当前项目知识库。请复用聊天附件上传，显示传输进度，保留首版20 MiB限额；用户必须明确选择/表达‘加入项目知识库’，普通附件不会自动共享。Agent通过MCP提交，原件保存和任务受理后返回编号，聊天继续，不等后台解析。处理时旧资料照常查，新资料发布后项目成员共享、新旧都可查。相同文件已有则提示‘资料已在知识库’，正在处理则提示‘已复用正在处理的任务’，不要制造第二份解析任务；去重由后端判断。页面显示文件名、真实阶段、可检索性和安全错误，失败由用户明确重提。关闭页面/停止聊天不停止已受理的任务。请按这份交接接API和任务卡；后端提供最终接口/真实结果，前端由你接续实现。”

## 1. 前端范围

### 必须做

1. 在当前项目聊天附件流中增加明确动作，例如“加入项目知识库”；发送普通附件时不自动入库。
2. 使用既有 PUT /api/langgraph/threads/{thread_id}/files/uploads/{sha256}，继续显示附件传输进度/失败/取消；20 MiB限额来自现有上传能力和知识capabilities的交集。上传完成只表示聊天附件可用，不直接显示“入库已受理”。不要新增浏览器直传RAG。
3. 显示Agent MCP ToolResult任务卡：文件名、queued/parsing/indexing/publishing/ready/failed、searchable、reused和安全错误；失败明确重提。queued不能显示可搜索；reused可能直接ready，也可能仍processing。提交回执job_id允许null仅限迁移旧资料已ready的复用，不能拼null任务URL。
4. 在项目范围增加轻量资料/任务列表（可先放项目知识面板或聊天上下文抽屉），分页消费 Platform API；项目切换时取消旧轮询、清空旧项目状态。
5. 使用现有权限探针：project.knowledge.read 控制查看，project.knowledge.upload 控制“加入知识库”入口；后端能力仍是最终裁决。
6. 复用现有审批卡/Run 状态：review/workspace_write 需要审批时让用户处理既有 HITL；full_access 不额外造一套确认弹窗。审批通过后仍可能因撤权/过期失败，错误要可理解。

### 不做

- 不在浏览器保存或发送 RAG Bearer、namespace、knowledge_base_id、服务地址、内部 upload_id/grant。
- 不把附件正文/base64塞入模型消息或前端轮询参数；不让模型填写宿主路径或任意 URL。
- 不把聊天附件默认标为项目共享；不展示“管理员审核”状态（本需求无内容审核）。
- 不在浏览器自行判定相同文件是否已入库、不实现解析/索引百分比或ETA、重建队列、MCP client和第二套上传API。现有字节传输进度可以继续显示。
- 不承诺提交后立即可检索；当前是否可查以 searchable 为准，首次发布成功为 ready/true。

## 2. 接口和 DTO

### 2.1 能力

GET /api/projects/{project_id}/knowledge/capabilities

~~~json
{
  "version": 1,
  "read": true,
  "upload_enabled": true,
  "supported_mime_types": ["text/plain", "text/markdown"],
  "max_file_bytes": 20971520,
  "disabled_reason": null
}
~~~

后端会按部署环境返回格式；不要把平台聊天支持列表直接当作知识解析支持列表。upload_enabled=false 时隐藏/禁用入库动作，但聊天普通附件仍可用。

### 2.2 项目资料

GET /api/projects/{project_id}/knowledge/documents?limit=20&offset=0

返回统一 OffsetPage：

~~~json
{
  "items": [{
    "document_id": "kd_22222222222222222222222222222222",
    "file_name": "项目规范.md",
    "mime_type": "text/markdown",
    "size_bytes": 1234,
    "status": "ready",
    "searchable": true,
    "published_at": "2026-10-12T04:05:00Z"
  }],
  "total": 1
}
~~~

这里只列项目已发布文档。没有下载 URL；如未来需要下载，单独走现有受管工作区/附件权限，不从知识服务暴露路径。

同一原件换名称再上传可能返回第一次入库时的原文件名；这是复用既有文档，不是上传附件名称丢失。当前聊天附件仍显示用户本次选择名称，知识库卡片/列表显示后端提供的原文档名称，不擅自覆盖它。

### 2.3 入库任务

GET /api/projects/{project_id}/knowledge/jobs?limit=20&offset=0

GET /api/projects/{project_id}/knowledge/jobs/{job_id}

提交ToolResult（服务端严格限制字段）示例；首次受理job_id为非空字符串，迁移旧资料复用才允许null：

~~~json
{
  "version": 1,
  "job_id": "kj_11111111111111111111111111111111",
  "document_id": "kd_22222222222222222222222222222222",
  "file_name": "项目规范.md",
  "status": "queued",
  "searchable": false,
  "reused": false,
  "error_code": null,
  "created_at": "2026-10-12T04:00:00Z",
  "updated_at": "2026-10-12T04:00:00Z"
}
~~~

状态展示建议：

| 状态 | 用户文案 | 可检索 |
|---|---|---|
| queued | 已受理，等待解析 | 否 |
| parsing | 正在解析资料 | 否 |
| indexing | 正在建立知识索引 | 否 |
| publishing | 正在发布到项目知识库 | 否 |
| ready | 已完成入库 | 根据 searchable |
| failed | 本次入库失败，可重新提交 | 根据 searchable |

error_code 只映射后端白名单到人话，例如 unsupported_format、document_too_large、knowledge_storage_full、knowledge_permission_revoked、knowledge_parser_failed、knowledge_index_failed、knowledge_service_unavailable。未知 code 显示通用失败，不显示原始异常。

status是该次任务结果，searchable是当前可检索性，分别显示。管理员回退后ready/false显示“已完成入库，当前版本暂不可检索”；旧failed任务的同文档后来入库可failed/true，显示“此任务失败，资料已通过后续任务入库”。文档列表只列当前已发布视图，不能把进行中资料混进去。

复用回执示例（迁移旧文档没有历史job）：

~~~json
{
  "version": 1,
  "job_id": null,
  "document_id": "kd_22222222222222222222222222222222",
  "file_name": "项目规范.md",
  "status": "ready",
  "searchable": true,
  "reused": true,
  "error_code": null,
  "created_at": "2026-10-12T04:00:00Z",
  "updated_at": "2026-10-12T04:00:00Z"
}
~~~

时间字段在迁移复用场景来自文档登记/更新时间，不伪造本次任务时间。常规ready复用仍返回原成功job_id，正在处理复用返回原job_id/阶段；复用不代表新建任务。reused只在提交回执，GET任务状态不返回该字段。API的jobs列表/GET所列真实任务，其job_id始终非空。

| 回执 | 页面行为 |
|---|---|
| reused=false、queued | “已受理，后台处理中”，开始job轮询 |
| reused=true、非终态、非空job_id | “相同资料正在处理，已复用任务”，轮询原job |
| reused=true、ready、searchable=true | “资料已在项目知识库，无需重复处理”，刷新资料列表，无需再等待 |
| ready、searchable=false | “已完成入库，当前版本暂不可检索”，不要报“已可查” |
| failed | 显示安全原因，用户明确选择重新提交；后端决定是否复用已有成果 |

错误白名单补：knowledge_queue_full（处理任务已满，稍后再试）、knowledge_processing_timeout（本次处理超时）、knowledge_content_conflict（文件校验冲突，请重新选择上传）、knowledge_processing_config_changed（知识库配置更新中，暂不能入库）。前端只展示可行动的信息，不展示索引/缓存结构和模型账单。

### 2.4 普通附件

现有聊天上传接口和返回 FileRef 继续使用；FileRef 六字段为 Runtime 内部可信引用。前端只保留当前项目/Thread 上下文，不能自行拼接 path、修改 sha256 或把引用交给其他项目。

## 3. ToolResult 卡片行为

1. 卡片从当前 Run 的 MCP ToolMessage 读取，不从模型自然语言猜任务 ID。
2. 回执有非空job_id且状态非终态才开始轮询Platform API；建议退避2s/4s/8s，上限15s，切项目/页面离开立即取消。reused正在处理也轮询原job；ready或job_id=null直接展示并刷新列表。后台可能很快完成，前端不要求见到每个阶段。轮询失败下次进入可恢复。
3. ready 停止轮询并刷新文档列表；searchable=true 时提示“新资料已可检索，旧资料仍保留”，false 时显示当前不可检索。不要自动重新发送原问题或自动唤醒已 Stop 的 Agent Run。
4. failed停止轮询并提供“重新提交”；新明确意图/工具调用产生新key，未知提交按后端回查，不换key盲发。重提需要当前Thread可用的真实附件引用，原附件不可用时让用户重新选择文件；不能从历史模型文字拼FileRef。reused文案按上表区分ready/进行中。
5. ToolResult/error 和 API 403/404/409/5xx 走现有错误投影；项目切换后迟到的响应必须丢弃，不得覆盖新项目状态。
6. 普通聊天消息仍可继续；入库卡片不锁住输入框。任务与聊天 Stop 生命周期独立，页面文案不要说“停止聊天会取消知识入库”。

### 3.1 传输状态与处理状态分开

| 阶段 | 前端展示 | 可取消/等待边界 |
|---|---|---|
| 现有附件uploading | 真实已传字节进度、名称、取消/上传失败 | 用户需等待附件完整上传才能正常提交；这时没有RAG job |
| 附件已上传，Agent尚未受理入库 | 原聊天附件状态和Run/工具状态 | 不提前画queued或“已入库”；Runtime向RAG原件传输属于工具执行 |
| MCP回执queued/processing | 独立入库任务卡/轮询 | 聊天可继续，页面离开不停止后台任务 |
| ready且searchable=true | 已可检索，刷新项目资料 | 不自动重发原问题/恢复已Stop Run |

首版超过20 MiB明确提示限额；不允许自动截断/压缩改变内容后偷偷入库。本期没有分片或断点续传，也不要求前端造这些协议。容量/格式变化以后以capabilities和后端实际附件上限同步扩展。

## 4. 页面/组件建议

组件名可按现有目录调整，职责保持单一：

- KnowledgeCapabilityBadge：权限/开关/格式提示。
- KnowledgeIngestTaskCard：ToolResult 单任务状态、失败/重提、时间。
- KnowledgeDocumentPanel：项目已发布资料列表，复用 DataTable、PaginationBar、PageHeader。
- useProjectKnowledge(projectId)：能力、列表、任务轮询；维护 epoch/project guard 防迟到响应。
- services/project-knowledge.service.ts：只封装上述 Platform API，不放权限判断和 RAG 凭据。

入口建议放 Chat 附件区域的“加入项目知识库”明确动作；资料面板可放项目级设置/侧栏。无需新增 RAG 登录或独立运维页面。

## 4.1 现有代码与拟修改位置

平台根为 `/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform`，下列路径相对 `apps/platform-web/`；标“新增”的位置为建议，同事可按现有目录调整。

| 文件 | 需要做什么 |
|---|---|
| `src/modules/chat/composables/useChatAttachments.ts:useChatAttachments()` | 复用选择/粘贴/去重/限额和取消；知识上传支持列表来自capabilities，不缩窄普通聊天附件能力 |
| `src/modules/chat/components/ChatComposer.vue`、`ChatSession.vue` | 加明确入库意图入口，复用当前Thread发送；发送内容包含“把所选附件加入当前项目知识库”，不自动共享所有附件 |
| `src/services/runtime-gateway/workspace.service.ts` | 复用现有Thread文件上传，不向模型传正文/base64 |
| `src/modules/chat/components/ToolResult.vue`、`src/modules/chat/transcript.ts` | 保留既有ToolMessage对齐，精确工具名分派任务卡；不重写来源渲染，不从自然语言猜ID |
| `src/modules/chat/components/KnowledgeIngestTaskCard.vue` **新增** | 显示安全任务DTO、状态和当前searchable；留存历史回执，最新状态由API消费 |
| `src/modules/chat/composables/useProjectKnowledge.ts` **新增** | 当前project权限/能力、资料任务分页、AbortController/epoch/有界轮询；不在组件中拼接网络调用 |
| `src/services/project-knowledge.service.ts` **新增** | 四个安全HTTP入口；使用 `platformHttpClient`、现有统一错误处理及认证 |
| `src/modules/chat/components/ChatContextDrawer.vue` | 首版推荐容纳小型项目资料/任务面板；如同事选择独立项目页面再调整 `src/router/routes.ts`，不同时建设两套入口 |
| `src/composables/useAuthorization.ts` | 消费后端新增权限，不硬编码只有admin；项目切换刷新权限 |
| `src/components/platform/DataTable.vue`、`PaginationBar.vue`、`src/components/layout/PageHeader.vue` | 复用平台表格/分页/布局；不新增一套样式/交互规范 |

开发前阅读 `apps/platform-web/docs/frontend-development-playbook.md`、`control-plane-page-standard.md`、`frontend-visual-baseline-standard.md`。按钮提示“资料将与当前项目成员共享”，不在页面暴露SQLite/namespace等实现细节。

## 5. 前端测试与人工验收

- [ ] 能力关闭/无 project.knowledge.upload 时动作隐藏；executor/editor/admin 的预期权限矩阵符合后端返回。
- [ ] ToolResult严格校验字段；任务可直接ready/跳过很快的阶段；job_id=null仅合法迁移ready复用且不轮询；reused正在处理/已存在文案不同，searchable准确。
- [ ] 失败 code 映射、重提使用新 key、未知提交不重复发送；轮询取消/重启/网络5xx恢复。
- [ ] 项目切换、Thread切换、离开页面、权限撤销后的迟到响应不会污染当前项目。
- [ ] 现有附件发送不受影响；普通上传不会自动出现在项目资料列表。
- [ ] 真实传输进度与queued分开，超20 MiB/格式不支持/上传断流无虚假任务；轮询等待不锁聊天输入，不伪造解析百分比。
- [ ] 同原件改名再次提交只显示已有资料；同名不同内容两份均可溯源；失败明确重提，未知提交不造第二任务。后端费用零调用验收由后端计数证明，前端不显示猜测“省了多少元”。
- [ ] 真实浏览器：成员A上传MD→看到queued→ready；成员B另一Thread查到新资料和旧资料；跨项目查不到；撤权后不能再入库；Stop/离开后任务仍完成。
- [ ] 若后端仅开放MD/TXT，PDF/DOCX/PPTX显示不支持；只有收到独立Linux解析证据才扩展选择器。

## 6. 交接时需要后端提供

1. 稳定 API base、OpenAPI/DTO 实际版本、能力响应和错误白名单。
2. 真实ToolResult与API fixture：queued、ready、failed、reused-processing、reused-ready、迁移ready/null job；补413/415/队列满/超时/配置变化的错误投影。不能包含token/原文/host路径；接口未实现时只能提供标明草案的示例。
3. 测试项目/成员账号矩阵、撤权步骤、两项目和两主图的可用环境。
4. 实际支持格式、单文件/项目容量、轮询建议、任务保留时间与回退提示。
5. Frontend E2E 所需的 Linux PDF/Office fixture（若本阶段承诺这些格式）和预期 source/document ID。

## 7. 交接完成标志

前端提交组件、service/composable、单测、类型检查、Lint、生产构建和真实浏览器截图/操作记录；后端在 verification.md 的 F01–F03/E01/E03/E04/E06/E08 栏登记对应 commit、环境和结果。双方都通过后，才能把专项从 partial/blocked 改为 done。
