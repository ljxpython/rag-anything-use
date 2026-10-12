# 任务列表

## 进度追踪

| Task | 状态 |
|---|---|
| 1.1 后台授权请求完整持久绑定及新租约 | [x] 完成 |
| 1.2 同 request_id 失 ACK 只读回查 | [x] 完成 |
| 1.3 真实平台 HTTP 联调与交接证据 | [x] 完成 |

## 任务详情

### Task 1.1: 后台授权请求完整持久绑定及新租约
- **改动内容：** 保存 graph_id 与 sha256/size_bytes/file_name/mime_type；start/activate 使用新 issuer/audience/iat/exp/nonce，不复用 upload grant 租约。
- **代码位置：** `src/knowledge/operation_auth.py` → `operation_identity/authorize`，`upload_service.py` → 上传与提交校验，worker/generations 调用链。
- **预期结果：** 平台可校验完整请求；响应 grant 精确绑定原来源、文件、job 与候选版本；字段篡改、过期或撤权不能执行/激活。
- **验证项：** 授权请求 HTTP 契约测试、持久重启/worker 测试；真实平台结果计入 Task 1.3。
- **状态：** `[x]` 完成

### Task 1.2: 同 request_id 失 ACK 只读回查
- **改动内容：** 注册 GET 上传路径，验证 token scope、当前 upload grant、原主体/文件/原请求；返回 null 或原安全回执，reused=true。
- **代码位置：** `src/knowledge/http_routes.py`、`upload_service.py`、`jobs.py`。
- **预期结果：** 已受理 ACK 丢失后同 key 查询得到同任务；关闭新写仍可回查；跨项目/主体拒绝；不 enqueue、不消费 attempt、无新解析/模型调用。
- **验证项：** HTTP/MCP 失 ACK、上传未受理/null、过期/篡改/跨主体/跨项目、开关关闭、数据库/usage 不变。
- **状态：** `[x]` 完成

### Task 1.3: 真实平台 HTTP 联调与交接证据
- **改动内容：** 使用实际 Platform API 授权端点验证 start/activate，执行隔离上传→MCP→后台→发布→查询与同 key 回查；记录脱敏证据并同步交接。
- **代码位置：** `scripts/verify_provider_contract.py`、当前目录 `verification.md` 与脱敏 JSON，原专项 RAG 交接、`docs/CONTEXT.md`。
- **预期结果：** 明确区分真实平台 HTTP、合成隔离主体/资料和真实模型边界；原两个缺口有可复核结果。
- **验证项：** 真实链路；Final 全量 pytest、ruff F/E9、diff check、文档状态一致性。
- **状态：** `[x]` 完成
