# 验证记录

## Phase 验证（每个 Task 完成后）

### Task 1.1

`uv run --frozen --env-file ".env" pytest "tests/test_knowledge_operation_auth.py" "tests/test_knowledge_upload.py" "tests/test_knowledge_generations.py" -q` → **30 passed in 20.48s**。新测试核对完整持久来源/文件、重开 SQLite 后的 identity、start/activate 新请求签名/整数租约/不同 nonce、精确 job/候选绑定，以及篡改/过期/不完整旧 identity 拒绝。此 Phase 使用 HTTP mock，不写作真实平台通过；实际端点计入 Task 1.3。

### Task 1.2

`uv run --frozen --env-file ".env" pytest "tests/test_knowledge_online_http.py" "tests/test_knowledge_upload.py" "tests/test_knowledge_jobs.py" -q` → **22 passed in 12.02s**。实际 ASGI HTTP/MCP 验证 PUT 后未 submit 回查为 null、submit 后同 job/reused=true，关闭全局及项目新写后仍可读取。跨主体/凭据/来源/项目、文件字段变更和过期 grant 拒绝；无受理请求返回 null；数据库各表、attempt 与模型调用记录不变。

### Task 1.3

使用用户指定 Worktree 的**实际 Platform API 源码和HTTP授权路由**，复用其隔离 SQL/IAM/Run fixture；数据和临时进程位于该 Worktree `.local-stack/evidence/`，OS分配端口，不重启已登记栈、不读写生产库，不修改平台源码。知识模型使用本RAG `.env` DeepSeek `deepseek-v4.1-flash`、百炼 `text-embedding-v4` /1024维。所有临时进程/目录已回收。

```sh
uv run --frozen --env-file ".env" python "scripts/verify_provider_contract.py" --platform-root "/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform" --output "docs/projects/20261012-rag-provider-contract-alignment/platform-real.json"
uv run --frozen --env-file ".env" python "scripts/verify_provider_contract.py" --platform-root "/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform" --authorization-only --output "docs/projects/20261012-rag-provider-contract-alignment/platform-authorization.json"
```

第一命令最终通过：**7项checks全true，269.536s**，[实际结果](platform-real.json)。两个已受理 job 的实际 start/activate 均200；B受理后删除原Thread，仍ready/searchable；第三job受理后撤成员，start403/failed，usage0，旧视图仍查到A/B。GET原request返回同任务/reused=true；暂停项目上传后仍200，attempt/usage不变；原快照checksum不变。

第二命令通过：**6.258s**，[后台授权证据](platform-authorization.json)。真实start/activate各200；分别签名篡改、过期租约、错误原主体均403；无解析/模型请求。本fixture是实际授权逻辑/SQL，但主体/资料合成，不代替真实Runtime Agent、浏览器或生产IAM验收。

源码基线与关键文件SHA-256记录在 [source-versions.json](source-versions.json)；平台包含其当前未提交接线实现，不能只凭平台HEAD识别测试源码。两个结果只保存安全回执、字段名及HTTP状态，无Bearer/HMAC/grant正文。临时资源回收后已核对原local-stack全部服务仍running/ready。

验收脚本失败事实：首次 fixture 导入顺序触发 ImportError，按平台原runner先加载 `platform_api.main` 后恢复；随后一轮已完成A/B发布、Thread删除及新旧检索，但将状态回执字段集与提交回执（多reused）比较导致AssertionError；修正验收断言后才获得上述7项完整通过结果。失败轮不算Final通过，未更改RAG业务逻辑绕过断言。脚本现在将后续失败类型/已完成checks写入单独脱敏failure.json，不打印秘密或原始异常内容。

## Final 验证

### 测试套件
- [x] `uv run --frozen --env-file ".env" pytest "tests" -q` → **78 passed in 52.28s**；前一轮真实模型联调并行时为78 passed in 67.81s
- [x] `uvx ruff check "src" "tests" "scripts" --select F,E9` → 通过
- [x] `git diff --check` → 通过

### 链路验证（接口改动必须）
- [x] 真实 Platform API HTTP start/activate 200；篡改/过期/撤权拒绝
- [x] 隔离入库 → 发布 → MCP 新旧查询
- [x] 同 key 失 ACK 回查及关闭新写后查询；无新增任务/attempt/usage

### 最终结论
**done**：用户指定的两项RAG协议缺口均已实现并有单测、HTTP/MCP及实际平台授权/真实模型证据，MCP参数/回执和完整快照发布路线保持。3个已完成Task对应3条Phase记录，README、CONTEXT、FEATURES与交接同步。

边界：首版MD/TXT；实际平台授权但隔离合成SQL主体，Runtime两主图/浏览器/生产IAM、Linux进程和格式、代表性负载及部署由原专项继续验收。旧不完整identity不能安全补造；RAG写开关关闭的GET仍需平台新upload grant，平台自身停签后不能通过该路径获取新租约。外部模型费用不承诺exactly-once。
