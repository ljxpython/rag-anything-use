# 面向 test_case_service 的 RAG 实现拆解与验收计划

## 1. 文档目的

前两份文档已经把方向和接口定下来了，这一份只解决一个问题：

后面真正开始写代码时，应该按什么顺序推进，才能少返工、少踩坑、少写废代码。

本文不再重复“为什么用 RAGAnything”这类原则讨论，只关注：

1. 实现阶段划分
2. 每阶段产出
3. 每阶段验收标准
4. 与 `runtime-service` 现有结构的具体接入点

建议配套阅读：

- `docs/rag_system_design_for_test_case_service.md`
- `docs/rag_system_interface_spec.md`

## 2. 总体策略

### 2.1 先做内部闭环，再做对外暴露

正确顺序应该是：

1. 先把项目级知识接入和查询跑通
2. 再让 `test_case_service` 内部 agent 能调用
3. 最后再暴露 MCP

不要反过来。

如果先做 MCP，再补底层服务，后面你会得到一堆：

1. 名字看起来漂亮但内部全是透传的工具
2. 外层契约早早锁死，底层却还在改
3. CLI、私有工具、MCP 三套逻辑一起漂移

这套玩法很蠢，第一版一定要避开。

### 2.2 先做查询闭环，再做 ingest 外露

即使最终系统要支持文档导入，第一阶段也不应该优先把 ingest 暴露给 agent 或 MCP。

更合理的顺序是：

1. 先由 CLI 或内部脚本完成 ingest
2. 验证查询质量、引用质量、项目隔离
3. 查询稳定后，再考虑是否暴露导入类能力

原因：

1. ingest 链路更重
2. ingest 涉及幂等、失败恢复、文件源、权限
3. 你如果连查询都没稳，就急着开放导入，那纯属给自己添堵

## 3. 推荐实施阶段

建议拆成 6 个阶段。

## 4. 阶段 0：代码骨架与配置层

### 4.1 目标

把最小结构搭起来，但先不接完整业务逻辑。

### 4.2 任务

1. 创建 `knowledge/` 子目录骨架
2. 创建 `config.py`
3. 创建 `schemas.py`
4. 创建 `project_paths.py`
5. 创建空的 `rag_engine.py`、`ingest_service.py`、`query_service.py`、`admin_service.py`
6. 创建 `tools_knowledge.py`
7. 创建 CLI 和 MCP server 骨架文件

### 4.3 验收标准

1. 模块可 import
2. 不产生循环依赖
3. 默认配置能正常解析
4. `project_id -> knowledge path` 计算稳定

### 4.4 这一阶段不要做的事

1. 不要接真实 parser
2. 不要接真实 RAGAnything
3. 不要急着写复杂 prompt

## 5. 阶段 1：项目级 RAG 引擎门面层

### 5.1 目标

把 `RAGAnything` 的初始化、目录组织和项目级实例加载统一收口。

### 5.2 任务

1. 在 `rag_engine.py` 中封装项目级 `RAGAnything` 初始化
2. 支持按 `project_id` 加载 `working_dir`
3. 注入统一的 LLM、Vision、Embedding 配置
4. 暴露最小方法：
   - `ingest_content_list`
   - `query`
   - `debug_retrieve`

### 5.3 验收标准

1. 同一个 `project_id` 重复加载时走同一套工作目录
2. 不同 `project_id` 的工作目录彼此隔离
3. 单元测试可验证路径与配置解析
4. 用最小手工 `content_list` 能完成一次入库和查询

### 5.4 风险点

1. `RAGAnything` 初始化可能较重，后面可能需要做实例缓存
2. `working_dir` 持久化目录必须明确，不能偷懒放会话临时目录

## 6. 阶段 2：解析与 ingest 编排

### 6.1 目标

打通：

`原始文档 -> docling -> content_list -> RAGAnything`

### 6.2 任务

1. 实现 `parser_adapter.py`
2. 实现 `content_normalizer.py`
3. 实现 `document_registry.py`
4. 实现 `ingest_service.py`
5. 支持单文档 ingest
6. 支持已注册文档重试 ingest

### 6.3 最小数据流

```text
register_document
  -> update status: registered
  -> parse_document
  -> update status: parsing -> parsed
  -> normalize_content_list
  -> rag_engine.ingest_content_list
  -> update status: indexing -> ready
```

### 6.4 验收标准

1. 用真实 PDF 能完成解析与入库
2. 文档状态正确流转
3. 失败时 `last_error` 会落下来
4. 重复 ingest 同一文档不会把状态搞乱

### 6.5 这一阶段的联调入口

优先用 CLI 或 devtools 脚本验证，不要先接 agent。

## 7. 阶段 3：查询与引用输出

### 7.1 目标

把“能查到”升级成“能可信地查到”。

### 7.2 任务

1. 实现 `query_service.py`
2. 实现 `citations.py`
3. 定义查询请求与响应 schema
4. 增加 `debug_retrieve` 返回 raw chunks
5. 支持基础过滤：
   - `project_id`
   - `document_ids`
   - `top_k`
   - `mode`

### 7.3 验收标准

1. 查询结果稳定返回 `answer`
2. 返回 `citations`
3. `citations` 至少包含：
   - `document_id`
   - `chunk_id` 或等效块标识
   - `page_index`
   - `snippet`
4. 不同项目同问法返回的结果不会串库

### 7.4 失败判定

下面任意一种都算这阶段没过：

1. 答案能出，但没有来源引用
2. 引用字段有，但追不到具体文档/块
3. 换项目查询还能查到别的项目内容

## 8. 阶段 4：接入 test_case_service 私有工具

### 8.1 目标

让 `test_case_service` 内部 agent 真正能用上项目知识。

### 8.2 任务

1. 在 `tools_knowledge.py` 实现服务私有工具
2. 从 `ToolRuntime` 中自动注入 `project_id`
3. 把工具挂进 `build_test_case_service_tools(...)`
4. 明确工具文案，让 agent 知道什么场景该调用

### 8.3 推荐先接的工具

1. `query_project_knowledge_for_current_project`
2. `list_current_project_knowledge_documents`
3. `get_current_project_knowledge_document_status`

### 8.4 验收标准

1. 在 `test_case_service` 对话里，无需 agent 显式传 `project_id` 也能查询
2. 缺失项目上下文时，工具显式报错
3. 生成测试用例前，agent 可以主动补检索上下文

### 8.5 关键取舍

这一阶段不要让服务内部 agent 通过 MCP 再绕回自己。

直接走内部 service 调用，路径更短，也更干净。

## 9. 阶段 5：CLI 联调与回归能力

### 9.1 目标

把开发和运维入口补齐。

### 9.2 任务

实现以下命令：

1. `ingest`
2. `query`
3. `list-docs`
4. `doc-status`
5. `project-status`
6. `rebuild`
7. `debug-retrieve`

### 9.3 验收标准

1. 本地可以用 CLI 完成完整 ingest 和 query
2. CLI 输出结构清晰
3. CLI 能用于复现线上问题

### 9.4 推荐用途

CLI 不是花架子，它主要用于：

1. 联调验证
2. 批量重建
3. 回归脚本
4. 排查引用异常

## 10. 阶段 6：FastMCP 暴露

### 10.1 目标

把稳定下来的高层能力暴露成 MCP server。

### 10.2 任务

1. 创建 `runtime_service/mcp/test_case_knowledge_server.py`
2. 用 FastMCP 注册工具
3. 默认只暴露：
   - `query_project_knowledge`
   - `list_project_knowledge_documents`
   - `get_project_knowledge_document_status`
4. 视需要再补：
   - `debug_project_knowledge_retrieval`
   - `rebuild_project_knowledge_index`

### 10.3 外部接入约束

本仓库当前阶段只负责：

1. 产出一个独立可运行的 MCP server
2. 保证 tool 名称、参数、返回结构稳定
3. 保证它可以被其他系统以自己的方式挂载

至于其他系统最终如何把它接入自身工具池，不属于本仓库实现计划的强约束。

### 10.4 验收标准

1. MCP server 能单独启动
2. MCP tool schema 正常暴露
3. 外部系统可按其自身规范接入
4. 通过 MCP 客户端可以拿到工具清单

## 11. 推荐测试矩阵

### 11.1 单元测试

优先覆盖：

1. schema 序列化
2. 配置解析
3. 路径计算
4. 状态流转
5. 引用格式化

### 11.2 冒烟测试

至少覆盖：

1. 手工 `content_list` ingest
2. 单项目 query
3. 双项目隔离 query

### 11.3 真实联调测试

至少覆盖：

1. 真实 PDF ingest
2. 真实项目查询
3. `test_case_service` 内部工具调用
4. MCP server 对外查询

## 12. 第一版完成定义

下面这些条件全部满足，才算第一版真的能用了：

1. 可以按 `project_id` 建立独立知识库
2. 可以 ingest 至少一种真实文档类型
3. 可以返回带引用的查询结果
4. `test_case_service` 内部 agent 可以直接调用项目知识查询工具
5. MCP 可以对外暴露查询、列表、状态工具
6. CLI 可以完成基本联调和排障

## 13. 明确暂缓事项

第一版先别碰这些：

1. 文档物理删除
2. 复杂权限体系
3. parser 动态切换界面化
4. embedding 模型在线切换
5. 自动 rerank 编排
6. 多模态查询花活

这些都不是现在最短闭环必需品。

## 14. 推荐开工顺序

如果下一步开始写代码，我建议严格按这个顺序：

1. 阶段 0：骨架与 schema
2. 阶段 1：`rag_engine`
3. 阶段 2：`ingest_service`
4. 阶段 3：`query_service + citations`
5. 阶段 5：CLI
6. 阶段 4：`test_case_service` 私有工具
7. 阶段 6：FastMCP

注意这里我把 CLI 放在私有工具前面。

理由很实际：

1. CLI 更适合先验证底层服务
2. CLI 比 agent 调用更容易排错
3. 私有工具和 MCP 都应该建立在 CLI 已经能跑通的基础上

## 15. 当前结论

现在文档层面已经基本够了。

再继续纯讨论，收益会迅速下降。

最合理的下一步就是：

开始搭最小代码骨架，并优先把 `rag_engine`、`ingest_service`、`query_service` 三件事跑起来。
