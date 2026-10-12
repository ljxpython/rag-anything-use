# RAG 平台契约对齐

- **时间：** 2026-10-12
- **目标：** 修复后台授权请求字段与失 ACK 只读回查，使已受理任务可由真实平台授权并安全查询。
- **影响模块：** `operation_auth.py`、`upload_service.py`、`jobs.py`、`http_routes.py`，相关测试、验证脚本及交接文档。
- **状态：** done（本轮两项 RAG 契约修复与真实平台 HTTP 验证完成；整成员上传专项的 Runtime Agent/前端/Linux/部署验收独立）

## 方案概述

依据用户指定的平台 Worktree `docs/projects/20261012-project-member-knowledge-upload/provider-contract.md`，只对齐两项实施缺口。沿用既有 identity JSON 保存原 graph、来源和四文件字段；每次 start/activate 生成新的 RAG→platform 请求时间与 nonce，平台 grant 单独校验。新增同 request_id GET，验证固定项目 scope、新 upload grant 与持久原请求后读取安全回执；不受新写开关限制，不创建任务或调用模型。

保留既定 FileRef、MCP 参数、回执、完整快照增量与发布协议。平台源码和现役知识库不在修改范围；真实联调使用隔离资源。旧 identity 缺少 graph 等可信字段时不伪造来源，不绕过平台校验。

原专项及交接见 [项目成员异步入库](../20261012-project-member-knowledge-upload/README.md)。

## 验证与升级

完整回归 **78 项通过**；实际 Platform API HTTP＋隔离 SQL/IAM/Run＋真实 DeepSeek/百炼＋RAG 子进程/MCP 七项检查通过。start/activate 200，篡改/过期/撤权403；Thread删除后任务仍完成；GET同任务/reused=true、暂停项目新写仍回查；撤权任务零模型调用。详见 [验证记录](verification.md)、[实际链路](platform-real.json)、[后台授权拒绝场景](platform-authorization.json)。

旧版本任务 identity 缺可信 graph/文件绑定时不自动补造，保留原件/记录并拒绝后台授权，重新明确提交合法新请求；已有已发布索引不改。GET 关闭新写仍要求当前有效 upload grant；如果平台自身也停止签发 upload grant，Runtime 无法取得新租约。默认关闭与目标环境启用仍由平台部署流程控制，本轮未改现役开关或知识库。
