# 面向 test_case_service 的 RAG 系统设计草案

## 1. 文档目的

这份文档用于收敛当前这一轮方案讨论，明确后续要做的 RAG 系统边界、职责拆分和对外暴露方式。

当前约束已经明确：

1. 底层知识库能力以 `RAGAnything` 为主，不再把系统设计成“解析器优先”的模式
2. `docling` 只作为辅助解析组件使用，不作为系统主抽象
3. 文档嵌入、建库、索引管理不直接暴露给 agent
4. 对 agent / 外部系统 暴露能力时，优先通过 `MCP`，并使用 `FastMCP`
5. 第一阶段主要服务于 `test_case_service`，不是先做一个泛化大平台

一句话总结：

我们要做的不是“一个文件上传站点”，而是“一个面向测试用例智能体的项目级知识底座”。

## 2. 核心定位

### 2.1 为什么以 RAGAnything 为主

结合当前已经跑通的示例，`RAGAnything` 对我们真正有价值的不是“它自带 parser”，而是下面这套主链路：

1. 接收文档或标准化内容
2. 完成文本和多模态内容分流
3. 调用嵌入与图谱/向量存储能力完成建库
4. 提供统一查询接口
5. 支持后续的多模态增强检索

这意味着系统主抽象应该是：

`文档知识接入 -> RAGAnything 建库 -> 项目级查询`

而不是：

`先围绕 docling 设计一套系统 -> 再想办法塞给 RAGAnything`

### 2.2 Docling 的正确定位

`docling` 仍然重要，但它的角色应该下沉为“可替换的解析适配器”，而不是系统中心。

更准确地说：

1. 如果输入是 PDF / Office / 复杂版式文档，优先用 `docling` 解析
2. 如果后续接别的解析器，也应该统一转换为 `content_list`
3. 一旦进入 `content_list`，后面的链路都由 `RAGAnything` 接管

所以后续系统设计里，真正稳定的接口不是“某个 parser 的原始输出”，而是：

- 原始文件
- 标准化后的 `content_list`
- 项目级查询请求

## 3. 总体设计原则

### 3.1 边界清晰

系统只做三件核心事：

1. 文档接入
2. 项目知识建库
3. 项目内检索与问答

不在第一版里做这些东西：

1. 对 agent 开放底层 embedding 参数
2. 对 agent 开放任意 parser 选择
3. 做成跨业务线通用知识平台
4. 做复杂权限中心和多级租户模型

### 3.2 项目作用域优先

所有知识库能力必须严格绑定 `project_id`。

原因很简单：

1. `test_case_service` 本身已经是项目级服务
2. 现有运行时上下文里已经有 `project_id` 解析逻辑
3. 如果不强制项目隔离，后面测试用例生成一定会串文档、串上下文、串结果

### 3.3 对 agent 暴露高层能力，不暴露底层实现

Agent 不需要知道：

1. 用的是什么嵌入模型
2. chunk 是怎么切的
3. `RAGAnything` 具体初始化细节是什么
4. 索引目录放在哪里

Agent 只需要知道：

1. 这个项目有哪些知识文档
2. 现在知识库是否可查
3. 按问题去检索
4. 返回引用证据

这才是干净的工具边界。

## 4. 功能范围

### 4.1 第一阶段 MVP

我建议第一阶段先做下面 6 个能力。

#### 4.1.1 文档接入

职责：

1. 接收本地文件路径、附件资产、或后续扩展的远程文件引用
2. 完成文档注册
3. 生成文档记录和处理任务

返回重点：

- `document_id`
- `project_id`
- `status`
- `filename`

#### 4.1.2 文档解析

职责：

1. 对原始文档执行解析
2. 默认优先走 `docling`
3. 产出标准化 `content_list`
4. 保留原始解析元数据用于调试

这里要注意，解析是内部能力，不对 agent 暴露。

#### 4.1.3 项目知识建库

职责：

1. 把标准化 `content_list` 送进 `RAGAnything`
2. 完成文本和多模态内容入库
3. 按 `project_id` 建立独立 working dir / index dir
4. 记录索引状态和最后更新时间

#### 4.1.4 项目知识查询

职责：

1. 根据 `project_id` 检索
2. 按查询模式返回答案
3. 返回引用证据
4. 支持基础过滤条件

这是第一阶段对 agent 最核心的能力。

#### 4.1.5 文档状态与列表查询

职责：

1. 查看某个项目下有哪些知识文档
2. 查看某份文档的解析/索引状态
3. 查看最近失败原因

这东西看起来土，但没有它，联调和排障会把人整疯。

#### 4.1.6 重建索引

职责：

1. 对单文档重建
2. 对项目全量重建
3. 在解析成功但索引异常时做恢复

第一版不强求精细删除，但必须有重建。

### 4.2 第二阶段增强项

后面可以继续补，但不建议第一版就上：

1. 文档标签、模块、类型过滤
2. 多查询模式切换，如 `naive / local / global / hybrid`
3. 查询调试接口，返回 raw retrieval 结果
4. 知识库健康检查和召回质量评估
5. 文档逻辑删除与增量清理
6. 更细粒度的 chunk / top_k / rerank 控制

## 5. 系统分层

建议拆成下面 5 层。

```text
+---------------------------------------------------+
| CLI / FastMCP / test_case_service 私有工具层      |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
| 应用服务层                                        |
| - document_ingest_service                         |
| - rag_index_service                               |
| - rag_query_service                               |
| - knowledge_admin_service                         |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
| RAG 引擎适配层                                    |
| - RAGAnything facade                              |
| - parser adapter (docling 为默认实现)              |
| - content_list normalizer                         |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
| 持久化层                                          |
| - 文档元数据                                      |
| - 解析结果元数据                                  |
| - 项目级 working_dir / 索引目录                    |
+-------------------------+-------------------------+
                          |
                          v
+---------------------------------------------------+
| 模型与外部依赖                                    |
| - LLM / Vision Model / Embedding                  |
| - Docling                                         |
+---------------------------------------------------+
```

## 6. 推荐的数据流

### 6.1 入库链路

```text
文件/附件输入
  -> 文档注册
  -> 解析任务
  -> docling 解析
  -> 规范化 content_list
  -> RAGAnything.insert_content_list / process_document_complete
  -> 项目知识库索引完成
  -> 状态更新为 ready
```

这里有两个实现入口：

1. 原始文件直接给 `RAGAnything.process_document_complete()`
2. 先由 `docling` 解析，再走 `RAGAnything.insert_content_list()`

从系统可控性来说，我更建议后者作为主实现。

原因：

1. 解析和索引边界更清楚
2. 以后如果 parser 替换，不会影响后面的建库流程
3. 更方便做失败重试和离线重放

但注意，这并不意味着系统以 `docling` 为主。主干仍然是 `RAGAnything`，只是选择了更稳的接入姿势。

### 6.2 查询链路

```text
agent / CLI / MCP 请求
  -> 解析 project_id 与 query
  -> rag_query_service
  -> RAGAnything.aquery(...)
  -> 组织回答与引用证据
  -> 返回 structured result
```

如果后面确认 `RAGAnything` 的多模态查询接口在你们业务文档上稳定，也可以在二期补：

- `aquery_with_multimodal`
- `aquery_vlm_enhanced`

但第一版没必要一口吃成胖子。

## 7. 对外能力边界

### 7.1 不对 agent 暴露的能力

下面这些能力不应该直接给 agent：

1. `set_embedding_model`
2. `set_parser`
3. `set_chunk_size`
4. `insert_raw_content_list`
5. `delete_storage_dir`
6. 任意 working dir 管理能力

这些是系统内部实现细节，不是 agent 工具。

### 7.2 对 agent 暴露的能力

第一阶段建议只暴露 3 到 5 个高层工具：

1. `query_project_knowledge`
2. `list_project_knowledge_documents`
3. `get_project_knowledge_document_status`
4. `rebuild_project_knowledge_index`
5. `debug_project_knowledge_retrieval`

其中真正默认给 agent 用的，我建议只有前 3 个。

`rebuild` 和 `debug_retrieval` 更偏运维或调试，是否默认暴露给智能体，要看后面你们 agent 的权限策略。

## 8. FastMCP 设计建议

### 8.1 为什么适合用 FastMCP

根据 FastMCP 当前官方文档：

1. 工具可以直接通过 `@mcp.tool` 暴露
2. 工具入参会自动生成 schema
3. 返回 `dict`、Pydantic 模型、dataclass 时，会自动生成结构化输出
4. 可以为工具设置超时
5. 可以通过依赖注入隐藏不想暴露给 LLM 的参数
6. 工具内部可以拿到 `Context` 记录日志、汇报进度

这几条正好适合我们这种“只暴露高层检索能力、不暴露底层参数”的需求。

### 8.2 MCP 服务职责

MCP 这一层建议做得很薄，只负责：

1. 参数校验
2. 调用应用服务
3. 输出结构化结果
4. 做统一错误封装

不要在 MCP 这一层里直接堆：

1. 文档解析逻辑
2. RAGAnything 初始化细节
3. embedding / parser 具体配置
4. 项目目录拼接逻辑

否则后面 CLI、服务内调用、MCP 三边会复制逻辑，代码会越来越臭。

### 8.3 FastMCP 工具建议清单

建议定义如下工具。

#### 8.3.1 `query_project_knowledge`

用途：

对项目知识库发起自然语言查询，并返回答案与引用。

建议入参：

- `project_id`
- `query`
- `top_k`
- `mode`
- `document_ids` 可选

建议返回：

- `answer`
- `citations`
- `matched_documents`
- `timing_ms`
- `query_mode`

#### 8.3.2 `list_project_knowledge_documents`

用途：

查看项目下当前已注册的知识文档。

建议入参：

- `project_id`
- `status` 可选
- `limit`

建议返回：

- `documents`
- `count`

#### 8.3.3 `get_project_knowledge_document_status`

用途：

查看指定文档的解析和索引状态。

建议入参：

- `project_id`
- `document_id`

建议返回：

- `document_id`
- `status`
- `parse_status`
- `index_status`
- `last_error`
- `updated_at`

#### 8.3.4 `rebuild_project_knowledge_index`

用途：

手动触发项目或文档重建。

建议入参：

- `project_id`
- `document_id` 可选

建议返回：

- `accepted`
- `scope`
- `task_id`

#### 8.3.5 `debug_project_knowledge_retrieval`

用途：

直接看召回结果，不走最后答案生成。

建议入参：

- `project_id`
- `query`
- `top_k`

建议返回：

- `chunks`
- `scores`
- `document_ids`

### 8.4 运行方式建议

`FastMCP` 官方当前支持通过 `FastMCP(...)` 定义 server，通过 `@mcp.tool` 注册工具，也支持直接 `mcp.run()` 或 `fastmcp run module.py:mcp` 启动；工具返回字典或模型时会提供结构化结果，还支持通过 `Depends()` 隐藏不想暴露给 LLM 的参数，以及通过 `Context` 做日志和进度上报。

这对我们意味着：

1. 本地开发时可以先走 `stdio`
2. 服务化部署时可以切到 HTTP transport
3. 内部注入的运行时参数可以考虑用依赖注入，不直接暴露给 LLM

## 9. 和 test_case_service 的关系

### 9.1 为什么不建议先做成独立平行产品

当前 `test_case_service` 已经具备这些基础：

1. 已有项目级上下文约束
2. 已有多模态附件处理链路
3. 已有服务私有工具机制
4. 已经是 agent 驱动工作流

所以第一阶段最合理的方式是：

把 RAG 系统设计成 `test_case_service` 的一个知识能力子系统。

### 9.2 在 test_case_service 中的推荐使用姿势

推荐有两条使用路径：

#### 路径 A：显式工具调用

当 agent 需要补充上下文时，主动调用：

- `query_project_knowledge`
- `list_project_knowledge_documents`

#### 路径 B：工作流内隐式调用

在生成测试策略或测试用例之前，由服务内部逻辑先做一次知识检索，把结果拼进上下文。

我更偏向：

1. 先实现显式工具调用
2. 跑通后，再决定哪些节点适合做隐式检索

因为隐式检索一旦做早了，调试时你根本不知道是 prompt 写坏了，还是召回坏了，还是模型乱编。

## 10. 状态模型建议

建议至少维护以下状态：

### 10.1 文档级状态

- `registered`
- `parsing`
- `parsed`
- `indexing`
- `ready`
- `failed`
- `disabled`

### 10.2 项目知识库状态

- `empty`
- `building`
- `ready`
- `degraded`
- `rebuilding`

其中：

1. 文档 ready 不代表整个项目知识库一定 ready
2. 项目级状态应由文档状态汇总得出

## 11. 第一版技术决策建议

### 11.1 建议立即确定的事情

1. 按 `project_id` 组织知识库存储目录
2. 以 `RAGAnything + insert_content_list` 为主链路
3. `docling` 作为默认 parser adapter
4. MCP 只暴露高层检索和状态工具
5. 返回结果必须带引用证据

### 11.2 暂时不要过度设计的事情

1. 多租户权限体系
2. 文档精细物理删除
3. embedding 模型动态切换
4. parser 动态切换
5. 复杂 rerank 编排

## 12. 推荐的落地顺序

### 阶段 1：跑通知识接入闭环

1. 单文档注册
2. `docling` 解析
3. 标准化 `content_list`
4. `RAGAnything` 建库
5. 按项目查询

### 阶段 2：补管理能力

1. 文档列表
2. 状态查询
3. 失败信息
4. 重建索引

### 阶段 3：补 MCP 暴露

1. 用 `FastMCP` 定义只读查询工具
2. 再补调试与重建工具
3. 最后再考虑是否开放 ingest 类能力

## 13. 当前结论

当前讨论后的结论如下：

1. 系统主体以 `RAGAnything` 为主，不以 `docling` 为主
2. `docling` 是默认解析适配器，不是系统中心
3. Agent 不接触 embedding、parser、storage 等底层实现参数
4. MCP 只暴露必要查询、文档列表、状态、重建、调试能力
5. 第一版优先服务 `test_case_service`，以项目级知识底座方式接入

如果继续往下推进，下一份文档应该进入“接口定义级别”，也就是：

1. 目录结构
2. 模块命名
3. 核心 schema
4. CLI 命令清单
5. FastMCP tool 入参与返回模型

对应文档已补充：

- `docs/rag_system_interface_spec.md`

## 14. 参考资料

- FastMCP Quickstart: https://gofastmcp.com/getting-started/quickstart
- FastMCP Tools: https://gofastmcp.com/servers/tools
- FastMCP GitHub: https://github.com/PrefectHQ/fastmcp
