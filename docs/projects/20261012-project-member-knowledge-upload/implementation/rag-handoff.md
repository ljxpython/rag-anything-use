# RAG 实施交接

2026-10-12。G01、K01–K08 的 UTF-8 MD/TXT 范围及 RAG 配置已实现并验证。平台负责当前成员/凭据权限、可信 Thread 附件核验、传输与官方 MCP interceptor；前端继续按 [既定交接](../frontend-handoff.md) 实施。本文补充内部接线细节，六字段 FileRef、任务回执、OffsetPage、查询 sources 均保持原约定。

## 接口与调用顺序

1. 管理员注册逻辑库，按需迁移旧库；服务端 Bearer scope 用 `knowledge_base_id` 代替 `namespace`，两者互斥。tenant/project 必须与注册归属一致，未知库不能自动建成空库。
2. Runtime 从当前 Thread 的可信附件记录核对六字段及实际 hash，取得平台 `upload` grant，再传原字节。
3. `PUT /internal/knowledge/uploads/{request_id}`：`Authorization: Bearer <project-token>`、`Content-Type` 等于 FileRef 的 MIME，`X-Knowledge-File-Ref` 为该六字段 JSON，`X-Knowledge-Operation-Grant` 为 grant JSON。正文是原字节，不能用 URL/base64 或宿主路径。成功仅返回 `{"upload_id":"ku_…"}`，此时尚无 job。
4. 官方 MCP interceptor 向 `mcp_submit_project_knowledge_document(file_ref)` 注入 `X-Knowledge-Upload-ID`、`X-Knowledge-Operation-Grant`；模型参数只有 `file_ref`。票据5分钟，grant最长30秒；传输超过窗口时，提交前按**同一 identity/request/hash/size**重新取 grant。响应为单 JSON 文本块和同值 structuredContent，最多4KiB；queued 持久后返回，不等模型。
5. RAG supervisor 在 start、activate 调平台当前授权；子进程只构建。授权不可用或被撤销时不激活新增资料，旧视图可查。30秒窗口不是跨服务数据库的即时原子撤权。
6. API 用项目 Bearer 转发内部 GET：`/internal/knowledge/capabilities`、`/documents?limit=20&offset=0`、`/jobs?limit=20&offset=0`、`/jobs/{job_id}`。无 scope query 参数，列表为 `{"items":[],"total":0}`；失败为既定 `ErrorResponse`。MCP 状态工具为 `mcp_get_project_knowledge_ingest_job(job_id)`。

`request_id` 只允许1–128字符 `[A-Za-z0-9_-]`，平台应从可信工具调用派生稳定值；结果未知时沿同 key 回查/重放，不能换 key 自动重试。相同原件的正在处理/ready回执复用已有任务，保留原主体和原名。failed 的旧 key 只返回原失败；明确新提交才新 attempt，最多3次。迁移旧资料可 `job_id=null,status=ready,searchable=true,reused=true`；GET 不返回 reused，不轮询 null ID。回退后 ready 可以 searchable=false。

FileRef `path=/workspace/uploads/{sha256}.{md|txt}` 仅作可信附件身份，RAG 不打开该路径。受管原件按项目/hash唯一保存，MD/TXT改名或扩展名变化不会留下第二份原件。票据和 grant 不进入模型、历史、浏览器、审计正文或工具回执。

## 平台授权签名

专用 `KNOWLEDGE_AUTHORIZATION_KEY_ID/SECRET`，secret至少32字符；与 JWT、MCP Bearer、其他回调密钥分开。RAG 的 `KNOWLEDGE_AUTHORIZE_URL` 指向平台约定的 `POST /api/runtime/internal/knowledge/authorize`，不跟随重定向，10秒网络超时。

请求及响应 envelope：`{"version":1,"key_id":"<id>","values":{…},"signature":"<lowercase-hex-sha256>"}`。签名为 HMAC-SHA256：UTF-8 `domain + "\n" + canonical(values)`。canonical 等价 Python `json.dumps(values,sort_keys=True,separators=(",",":"),ensure_ascii=True)`；跨语言必须保持键排序、JSON布尔/null、数字与 Unicode 转义一致。

| 方向 | domain | values |
|---|---|---|
| RAG→平台复核 | `knowledge-operation-request` | 下表的 scope/identity 与 operation 专属字段 |
| 平台→Runtime/RAG grant | `knowledge-operation-grant` | 原值逐字段一致，加 issuer/audience/iat/exp/nonce |

| 字段组 | 内容 |
|---|---|
| scope | `tenant_id,project_id,knowledge_base_id` |
| identity | `subject,principal_type,credential_id,resource_id,request_id,thread_id,run_id,tool_call_id`；credential_id可null，其他身份来自可信平台/Runtime |
| upload | `operation="upload",sha256,size_bytes`；必须当前Thread ACL/六字段附件核验及当前项目upload权限 |
| start | `operation="start",job_id`；原提交者当前成员/凭据权限与项目生命周期复核，不因Thread删除取消已受理任务 |
| activate | `operation="activate",job_id,target_revision,base_revision`；target_revision为候选 namespace字符串，base_revision为SQLite整数 |
| grant固定值 | `issuer="platform-api",audience="rag-knowledge"`；iat/exp为Unix秒数，iat≤当前时刻、exp>当前时刻且exp≤iat+30；nonce长16–128 |

平台先验请求签名，再回查当前 actor/credential/resource/project，不能因为 values 有 subject 就信任客户端。相同 upload grant 允许同请求受理重放，票据/事务保证幂等；不以 nonce 单次消费破坏 ACK 丢失恢复。不同操作、scope、主体、hash、大小或候选/base 的 grant 都拒绝。

## 配置与管理员命令

默认 `KNOWLEDGE_ONLINE_ENABLED=false`。全局开关、项目 enabled、授权URL/key/secret及处理签名全部满足才 `upload_enabled=true`；legacy只读不需要新secret。online范围仅 MD/TXT，capabilities如实报告。文件20MiB，项目100份/100MiB原件，项目10/全局100未完成任务，deadline1800秒。磁盘默认项目2GiB/全局10GiB，含暂存、原件、成果、候选、历史版本和读副本，部署前按实际容量调整两个disk env。

下面命令是管理员操作示例，未对现役库执行：

```sh
uv run --frozen --env-file ".env" python "main.py" init-project-knowledge --tenant-id __default --project-id 11111111-1111-4111-8111-111111111111
uv run --frozen --env-file ".env" python "main.py" migrate-project-knowledge --knowledge-base-id <kb_id> --namespace <legacy_namespace> --processing-signature <confirmed_signature>
uv run --frozen --env-file ".env" python "main.py" activate-knowledge-generation --knowledge-base-id <kb_id> --uploads on
uv run --frozen --env-file ".env" python "main.py" activate-knowledge-generation --knowledge-base-id <kb_id> --uploads off
uv run --frozen --env-file ".env" python "main.py" activate-knowledge-generation --knowledge-base-id <kb_id> --namespace <retained_namespace>
```

注册返回完整 processing_signature。旧 publication 仅记录LLM/Embedding模型与维度，无法证明所有历史参数；管理员必须核对 provider/endpoint、parser、prompt、chunk/graph 参数后传确认签名。无法确认时保持legacy查询并拒绝迁移，不能把当前签名强贴旧向量。迁移先让**旧 MCP 服务释放 namespace 读锁**，以独占锁冻结旧库，完整复制12项存储到新 workspace；旧索引内容不改，不重新外调模型。缺原件、多个旧ID同hash、原chunks来源不一致、unsupported格式或签名不兼容均失败，不激活不完整库。

回退先关上传，并等所属在途job终态；queued保留。`--namespace`只允许同库完整已发布generation，原子改指针；新版本/原件不删除。恢复包含全部已发布资料的累计版本后才可 `--uploads on`。退旧代码使用原legacy scope和匹配模型配置，保留新SQLite/原件备份。

## 实现限制与证据

服务按POSIX单机、本地SQLite/文件系统、单个服务进程运行；supervisor/builder跨进程flock只用于防重复writer，不作为多副本HTTP集群支持。重启 recovery 在取得builder锁后将中断job记failed、queued留存；残留builder锁等最多30秒，仍不释放则启动失败，不抢锁。残留upload reservation只有在所属旧HTTP进程已停止后才清。保留版本达到配额会拒绝新增，首版没有自动删索引。读副本是可抛弃缓存，SIGKILL留下的目录由管理员停服后按所属资源清理，不跟随symlink。快照校验/复制及图/向量构造已搬到后台IO，取消等IO结束才清目录；上游JSON存储初始化的大库延迟及峰值内存仍需代表性负载验收。

LightRAG1.4.12有两个版本适配点：新在线chunk ID包含document ID，避免不同原件的相同正文覆盖来源；reader无lease后清理LightRAG全局workspace KV/锁，避免每次发布常驻一份内存。旧ID保留；升级必须重跑快照与连续发布测试。原生LLM响应缓存随完整快照复用，未新增第二套Embedding缓存/全库重组。

[G01恢复/计数/失败隔离证据](g01-evidence.md)、[RAG实施验收](rag-evidence.md)、[真实worker/HTTP/MCP结果](rag-real-chain.json)。平台IAM、两主图/审批/Stop语义、前端、Linux进程/格式与代表性性能仍待各团队联合验收；当前上传默认关闭。
