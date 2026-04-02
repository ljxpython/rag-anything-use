# 面向 test_case_service 的 RAG 接口与模块设计

## 1. 文档目的

这份文档是上一份方案草案的下一层细化，目标不是再讨论“该不该做”，而是明确：

1. 模块怎么拆
2. 接口怎么定义
3. CLI 怎么组织
4. MCP 暴露哪些工具
5. `test_case_service` 内部如何接这套能力

本文默认延续以下已确认结论：

1. 系统主抽象以 `RAGAnything` 为主
2. `docling` 是默认解析适配器
3. Agent 不直接操作嵌入与索引底层参数
4. MCP 优先只暴露检索与必要状态能力

建议结合上一份文档一起看：

- `docs/rag_system_design_for_test_case_service.md`

## 2. 与现有仓库习惯对齐

当前目标接入仓库里已经有两类现成风格，不要自己另起炉灶：

### 2.1 MCP 风格

`runtime-service` 已经有最小可运行的 FastMCP 示例：

- `runtime_service/mcp/local_math_server.py`
- `runtime_service/mcp/local_text_server.py`

它们当前使用：

```python
from mcp.server.fastmcp import FastMCP
```

需要注意一个现实坑：

1. 你当前机器上的全局 Python 环境里，`fastmcp` 顶层包和 `mcp.server.fastmcp` 两种导入都可用
2. 但 `runtime-service` 这个项目自己的 `uv` 环境里，当前只确认 `mcp.server.fastmcp` 可用
3. 所以后续实现时，必须以项目实际环境为准，不要把新版文档里的导入方式硬抄进去

换句话说，设计上按 FastMCP 思路走，代码实现时按项目环境锁定导入路径。

### 2.2 CLI 风格

`runtime-service` 现有联调脚本基本都用 `argparse`，例如：

- `runtime_service/tests/services_test_case_service_document_live.py`

所以后续 RAG 调试/回归脚本也建议继续用 `argparse`，而不是突然切一套 `click` / `typer`。

原因很简单：

1. 团队现有习惯一致
2. 联调脚本更容易直接复用
3. 少引入一套没必要的新框架

## 3. 推荐目录结构

建议把知识能力收敛到 `test_case_service` 私有子模块中，先别上来就做全局共享库。

```text
runtime_service/
├── services/
│   └── test_case_service/
│       ├── knowledge/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── schemas.py
│       │   ├── project_paths.py
│       │   ├── parser_adapter.py
│       │   ├── content_normalizer.py
│       │   ├── rag_engine.py
│       │   ├── document_registry.py
│       │   ├── ingest_service.py
│       │   ├── query_service.py
│       │   ├── admin_service.py
│       │   └── citations.py
│       ├── tools_knowledge.py
│       └── tests/
│           ├── test_knowledge_smoke.py
│           ├── test_knowledge_query_live.py
│           └── test_knowledge_ingest_live.py
├── mcp/
│   └── test_case_knowledge_server.py
└── devtools/
    └── test_case_knowledge_cli.py
```

## 4. 各模块职责

### 4.1 `knowledge/config.py`

负责：

1. 解析知识库相关配置
2. 管理默认模型、目录、查询模式、top_k 等默认值
3. 统一读取环境变量和 `RunnableConfig.configurable`

不要放：

1. 解析逻辑
2. 查询逻辑
3. 目录创建副作用

### 4.2 `knowledge/project_paths.py`

负责：

1. 按 `project_id` 计算 working dir
2. 计算 parser 输出目录
3. 计算解析缓存、索引缓存、调试输出目录

建议目录组织：

```text
{knowledge_root}/
  {project_id}/
    manifest/
    parser/
    rag_workdir/
    debug/
```

### 4.3 `knowledge/parser_adapter.py`

负责：

1. 封装 `docling` 调用
2. 未来可扩展别的 parser
3. 输出统一的中间结果对象

这里不要直接暴露给 agent 或 MCP。

### 4.4 `knowledge/content_normalizer.py`

负责：

1. 将 parser 输出转换为 `RAGAnything` 可接受的 `content_list`
2. 统一字段名
3. 做必要清洗
4. 补充页码、块 ID、文档引用等元信息

这个模块很关键，因为它决定后面引用链能不能稳定。

### 4.5 `knowledge/rag_engine.py`

负责：

1. 创建或加载项目级 `RAGAnything`
2. 注入 LLM、Vision、Embedding 配置
3. 统一暴露 `ingest_content_list()`、`query()`、`debug_retrieve()` 之类的底层方法

这层是“RAGAnything 门面层”，不是业务服务层。

### 4.6 `knowledge/document_registry.py`

负责：

1. 文档元数据登记
2. 解析状态、索引状态更新
3. 列表、详情、失败原因查询

它解决的是“系统知道自己处理过什么文档”，不是“RAGAnything 是否已经存进去”。

### 4.7 `knowledge/ingest_service.py`

负责：

1. 文档注册
2. 解析
3. `content_list` 规范化
4. 调用 `rag_engine` 完成建库
5. 更新状态

这是文档接入主编排层。

### 4.8 `knowledge/query_service.py`

负责：

1. 接收项目级查询
2. 调用 `rag_engine`
3. 组织回答
4. 抽取和格式化引用
5. 输出结构化结果

这是 MCP 和内部工具最核心依赖的服务层。

### 4.9 `knowledge/admin_service.py`

负责：

1. 文档列表
2. 文档状态
3. 项目状态
4. 重建索引
5. 调试召回

### 4.10 `services/test_case_service/tools_knowledge.py`

负责：

1. 为 `test_case_service` 提供私有工具
2. 从 `ToolRuntime` 注入当前 `project_id`
3. 调用 `query_service` / `admin_service`

这层非常重要。

我的建议是：

`test_case_service` 内部 agent 不直接依赖外部仓库如何挂 MCP，而是优先调用这层私有工具。

理由：

1. 可以自动注入当前项目上下文
2. 不用让 agent 自己猜 `project_id`
3. 避免服务内部走一层 MCP 回环

### 4.11 `runtime_service/mcp/test_case_knowledge_server.py`

负责：

1. 用 FastMCP 对外暴露通用能力
2. 供外部 agent 或平台工具池接入
3. 不承担业务编排，只做薄封装

注意：

MCP server 的“注册方式”和“在哪个仓库里 append 到 tools”不属于本仓库这份设计的核心范围。
本方案只保证：

1. MCP server 本身可独立启动
2. 工具名、入参、返回结构稳定
3. 其他系统可以按自己的规范把这组 tools 接进去

### 4.12 `runtime_service/devtools/test_case_knowledge_cli.py`

负责：

1. 本地联调
2. 真实回归验证
3. 批量导入与重建
4. 开发期 debug

## 5. 核心数据模型

下面不是最终代码，而是接口级定义。

### 5.1 `KnowledgeDocumentRecord`

```python
class KnowledgeDocumentRecord(BaseModel):
    document_id: str
    project_id: str
    filename: str
    source_type: str
    source_uri: str | None = None
    source_document_id: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    checksum: str | None = None
    parser_name: str = "docling"
    parser_version: str | None = None
    parse_status: str
    index_status: str
    overall_status: str
    page_count: int | None = None
    chunk_count: int | None = None
    last_error: str | None = None
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
```

说明：

1. `parse_status` 和 `index_status` 分开，不要用一个字段糊弄
2. `overall_status` 给 UI、CLI、MCP 直接展示
3. `source_document_id` 用于关联已有附件持久化记录

### 5.2 `KnowledgeProjectIndexRecord`

```python
class KnowledgeProjectIndexRecord(BaseModel):
    project_id: str
    status: str
    document_count: int = 0
    ready_document_count: int = 0
    failed_document_count: int = 0
    parser_name: str = "docling"
    embedding_model: str
    query_default_mode: str = "hybrid"
    last_build_at: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 5.3 `CitationRecord`

```python
class CitationRecord(BaseModel):
    document_id: str
    filename: str | None = None
    chunk_id: str | None = None
    page_index: int | None = None
    block_type: str | None = None
    score: float | None = None
    snippet: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

这里的设计目标只有一个：

答案必须能追到原文块，不然这套系统对测试场景不可信。

### 5.4 `ProjectKnowledgeQueryRequest`

```python
class ProjectKnowledgeQueryRequest(BaseModel):
    project_id: str
    query: str
    mode: str = "hybrid"
    top_k: int = 8
    document_ids: list[str] = Field(default_factory=list)
    include_citations: bool = True
    include_debug_chunks: bool = False
```

### 5.5 `ProjectKnowledgeQueryResponse`

```python
class ProjectKnowledgeQueryResponse(BaseModel):
    project_id: str
    query: str
    answer: str
    mode: str
    citations: list[CitationRecord] = Field(default_factory=list)
    matched_document_ids: list[str] = Field(default_factory=list)
    debug_chunks: list[dict[str, Any]] = Field(default_factory=list)
    timing_ms: int | None = None
```

### 5.6 `KnowledgeRebuildRequest`

```python
class KnowledgeRebuildRequest(BaseModel):
    project_id: str
    document_id: str | None = None
    force_reparse: bool = False
```

### 5.7 `KnowledgeOperationResult`

```python
class KnowledgeOperationResult(BaseModel):
    accepted: bool
    project_id: str
    document_id: str | None = None
    operation: str
    status: str
    message: str = ""
    task_id: str | None = None
```

## 6. 内部服务接口建议

### 6.1 `ingest_service`

建议暴露：

```python
async def register_document(...)
async def ingest_document(...)
async def ingest_registered_document(...)
```

职责划分：

1. `register_document` 只负责登记，不做解析
2. `ingest_document` 适合一步到位场景
3. `ingest_registered_document` 适合异步任务和重试场景

### 6.2 `query_service`

建议暴露：

```python
async def query_project_knowledge(
    request: ProjectKnowledgeQueryRequest,
) -> ProjectKnowledgeQueryResponse
```

### 6.3 `admin_service`

建议暴露：

```python
async def list_project_documents(...)
async def get_document_status(...)
async def get_project_index_status(...)
async def rebuild_project_index(...)
async def debug_project_retrieval(...)
```

## 7. 暴露矩阵

### 7.1 内部应用服务层

暴露全部能力：

1. register
2. ingest
3. query
4. list/status
5. rebuild
6. debug retrieval

### 7.2 `test_case_service` 私有工具层

默认暴露：

1. `query_project_knowledge`
2. `list_project_knowledge_documents`
3. `get_project_knowledge_document_status`

可选暴露：

1. `debug_project_knowledge_retrieval`

不建议默认暴露：

1. ingest
2. rebuild
3. 删除

### 7.3 CLI 层

建议暴露：

1. `ingest`
2. `query`
3. `list-docs`
4. `doc-status`
5. `project-status`
6. `rebuild`
7. `debug-retrieve`

CLI 是开发和运维入口，不是给 agent 用的。

### 7.4 MCP 层

建议默认暴露：

1. `query_project_knowledge`
2. `list_project_knowledge_documents`
3. `get_project_knowledge_document_status`

建议灰度暴露：

1. `debug_project_knowledge_retrieval`
2. `rebuild_project_knowledge_index`

不建议第一版暴露：

1. `ingest_project_document`

原因：

1. ingest 牵涉文件源、权限、异步任务、重试和幂等
2. 这类能力对 LLM 工具来说过重
3. 第一版先保证查询稳定，比什么都强

## 8. `test_case_service` 内部工具建议

为了让 agent 真正能舒服用，我建议在服务私有工具层做两个版本：

### 8.1 对 agent 友好的私有工具

#### `query_project_knowledge_for_current_project`

入参：

- `query`
- `top_k`
- `mode`
- `document_ids` 可选

特点：

1. 不要求 agent 传 `project_id`
2. 由 `ToolRuntime` 自动从运行时上下文取当前项目

#### `list_current_project_knowledge_documents`

入参：

- `status` 可选
- `limit`

特点同上。

### 8.2 对外通用的 MCP 工具

#### `query_project_knowledge`

入参必须显式带：

- `project_id`
- `query`

这是外部系统调用的稳定契约，不依赖内部上下文注入。

至于外部系统最终是通过什么 registry、什么 append 方式、还是什么平台规范把这些工具挂进去，不在本方案中约束。

## 9. FastMCP 工具契约建议

### 9.1 `query_project_knowledge`

请求：

```json
{
  "project_id": "uuid",
  "query": "接口鉴权失败时系统应该如何处理？",
  "mode": "hybrid",
  "top_k": 8,
  "document_ids": []
}
```

响应：

```json
{
  "project_id": "uuid",
  "query": "接口鉴权失败时系统应该如何处理？",
  "answer": "根据项目文档，鉴权失败时应返回未授权错误并记录审计日志。",
  "mode": "hybrid",
  "matched_document_ids": ["doc_1"],
  "citations": [
    {
      "document_id": "doc_1",
      "filename": "接口文档.pdf",
      "page_index": 3,
      "chunk_id": "chunk_17",
      "score": 0.91,
      "snippet": "未登录或 token 无效时，接口返回 401..."
    }
  ],
  "timing_ms": 824
}
```

### 9.2 `list_project_knowledge_documents`

请求：

```json
{
  "project_id": "uuid",
  "status": "ready",
  "limit": 20
}
```

响应：

```json
{
  "project_id": "uuid",
  "count": 2,
  "documents": [
    {
      "document_id": "doc_1",
      "filename": "接口文档.pdf",
      "overall_status": "ready",
      "parse_status": "parsed",
      "index_status": "ready",
      "updated_at": "2026-04-02T12:00:00Z"
    }
  ]
}
```

### 9.3 `get_project_knowledge_document_status`

请求：

```json
{
  "project_id": "uuid",
  "document_id": "doc_1"
}
```

响应：

```json
{
  "document_id": "doc_1",
  "project_id": "uuid",
  "overall_status": "ready",
  "parse_status": "parsed",
  "index_status": "ready",
  "last_error": null,
  "updated_at": "2026-04-02T12:00:00Z"
}
```

### 9.4 `debug_project_knowledge_retrieval`

只返回检索块，不返回总结答案。

适合：

1. 调召回质量
2. 验证 chunk 命中
3. 排查答案胡编是模型问题还是检索问题

## 10. CLI 设计建议

建议文件：

- `runtime_service/devtools/test_case_knowledge_cli.py`

建议命令：

### 10.1 ingest

```bash
uv run python runtime_service/devtools/test_case_knowledge_cli.py ingest \
  --project-id <uuid> \
  --file /abs/path/to/file.pdf
```

### 10.2 query

```bash
uv run python runtime_service/devtools/test_case_knowledge_cli.py query \
  --project-id <uuid> \
  --query "登录失败场景有哪些约束？"
```

### 10.3 list-docs

```bash
uv run python runtime_service/devtools/test_case_knowledge_cli.py list-docs \
  --project-id <uuid>
```

### 10.4 doc-status

```bash
uv run python runtime_service/devtools/test_case_knowledge_cli.py doc-status \
  --project-id <uuid> \
  --document-id doc_1
```

### 10.5 rebuild

```bash
uv run python runtime_service/devtools/test_case_knowledge_cli.py rebuild \
  --project-id <uuid> \
  --document-id doc_1
```

### 10.6 debug-retrieve

```bash
uv run python runtime_service/devtools/test_case_knowledge_cli.py debug-retrieve \
  --project-id <uuid> \
  --query "token 失效时的返回码"
```

## 11. 持久化策略建议

### 11.1 文档元数据

生产方案建议：

1. 文档注册信息进入中心化存储
2. 如果文档来自现有 `test_case_service` 附件链路，优先复用已有文档记录
3. 新增知识索引相关状态字段，或增加知识专用 registry

### 11.2 RAGAnything working dir

建议放项目级持久化目录：

```text
{knowledge_root}/{project_id}/rag_workdir
```

这部分不能放在会话内存里，否则服务一重启知识库就跟死了一样。

### 11.3 parser 输出

建议保留：

```text
{knowledge_root}/{project_id}/parser
```

原因：

1. 失败排查要看
2. 重建索引时可复用
3. 未来 parser 替换时方便做对照

## 12. 状态机建议

### 12.1 文档状态机

```text
registered
  -> parsing
  -> parsed
  -> indexing
  -> ready

任意阶段
  -> failed

ready
  -> rebuilding
  -> ready
```

### 12.2 项目索引状态机

```text
empty
  -> building
  -> ready

ready
  -> rebuilding
  -> ready

任意阶段
  -> degraded
```

## 13. 推荐调用链

### 13.1 外部系统通过 MCP 查询

```text
FastMCP Tool
  -> query_service
  -> rag_engine
  -> RAGAnything.aquery(...)
  -> citations formatter
  -> structured result
```

### 13.2 `test_case_service` agent 内部查询

```text
Agent Tool
  -> tools_knowledge.py
  -> 从 ToolRuntime 注入 project_id
  -> query_service
  -> rag_engine
  -> 返回答案 + citations
```

### 13.3 CLI 建库

```text
argparse CLI
  -> ingest_service
  -> parser_adapter(docling)
  -> content_normalizer
  -> rag_engine.ingest_content_list(...)
  -> document_registry 更新状态
```

## 14. 当前建议的默认配置

### 14.1 系统默认

1. parser: `docling`
2. query mode: `hybrid`
3. top_k: `8`
4. citations: 默认开启
5. debug chunks: 默认关闭

### 14.2 不对外开放的配置

1. embedding model
2. embedding base url
3. parser implementation
4. chunk strategy
5. storage root

## 15. 下一步建议

接口级设计已经可以支撑落代码了。

如果继续推进，下一步建议直接进入下面两个动作中的一个：

1. 先写纯文档版“实现任务拆解清单”
2. 直接开始搭最小代码骨架，但先不接完整业务逻辑

我的偏好是第 2 个。

原因很简单：

这套接口已经够清楚了，再空转讨论就开始浪费时间了。

对应拆解文档已补充：

- `docs/rag_system_implementation_plan.md`
