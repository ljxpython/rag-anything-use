# RAG 知识库当前实现进度

## 1. 当前定位

这个仓库现在已经不只是官方 `examples/` 联调工程，还补了一层可复用的知识库封装，目标是：

- 继续以 `RAGAnything` 作为核心引擎
- 用 `docling` 作为默认解析器
- 以“项目知识库”为单位进行文档摄入和查询
- 通过 CLI 做联调
- 通过 MCP 暴露给外部 agent / runtime 系统调用

当前实现仍然坚持一个原则：

- 文档嵌入与入库流程不直接暴露给 agent
- MCP 只暴露必要查询和文档状态工具

## 2. 已实现模块

### 2.1 核心代码

- `src/knowledge/config.py`
  知识库封装层配置

- `src/knowledge/project_paths.py`
  项目级目录结构约定

- `src/knowledge/document_registry.py`
  文档 manifest 管理

- `src/knowledge/parser_adapter.py`
  基于 `docling` 的解析接入

- `src/knowledge/ingest_service.py`
  文档导入入口

- `src/knowledge/rag_engine.py`
  `RAGAnything` / `LightRAG` 的项目级封装

- `src/knowledge/query_service.py`
  查询服务

- `src/knowledge/admin_service.py`
  文档列表与状态查询

- `src/mcp_server.py`
  基于 `fastmcp` 的 MCP server

- `src/cli.py`
  命令行调试入口

### 2.2 当前 CLI 能力

- `ingest`
- `query`
- `debug-retrieve`
- `list-docs`
- `doc-status`

### 2.3 当前 MCP 工具

- `query_project_knowledge`
- `list_project_knowledge_documents`
- `get_project_knowledge_document_status`

## 3. 当前实现细节

### 3.1 稳态联调策略

为了保证“真实跑通”，当前默认关闭知识库封装层里的多模态增强：

```env
KNOWLEDGE_ENABLE_IMAGE_PROCESSING=false
KNOWLEDGE_ENABLE_TABLE_PROCESSING=false
KNOWLEDGE_ENABLE_EQUATION_PROCESSING=false
```

同时为了兼容官方 examples，又补了：

```env
ENABLE_IMAGE_PROCESSING=false
ENABLE_TABLE_PROCESSING=false
ENABLE_EQUATION_PROCESSING=false
```

如果 examples 没有显式设置 `ENABLE_*`，代码会自动回退读取 `KNOWLEDGE_ENABLE_*`。

### 3.2 查询返回结构

当前项目级查询结果已经补齐：

- `answer`
- `citations`
- `matched_document_ids`
- `debug_chunks`

其中 `citations` 和 `matched_document_ids` 不是 mock，而是通过：

1. `LightRAG.aquery_data()` 获取结构化检索结果
2. 基于 `document_registry` 的 `filename/source_uri -> document_id` 映射
3. 组装为当前业务侧响应结构

### 3.3 MCP 协议层修正

在做真实 MCP 校验时，发现一个关键问题：

- `src/mcp_server.py` 作为脚本运行时，Python 的 `sys.path` 不包含仓库根目录
- 直接导致 `import src.*` 失败

当前已经修复这个问题，因此 `fastmcp.Client(Path("src/mcp_server.py"))` 可以真实连通 stdio server。

### 3.4 MCP transport 现状

当前 `src/mcp_server.py` 已支持通过环境变量切换 transport：

- `MCP_TRANSPORT=stdio`
- `MCP_TRANSPORT=sse`
- `MCP_TRANSPORT=http`
- `MCP_TRANSPORT=streamable-http`

当前策略已经明确：

- 本地联调保留 `stdio`
- 正式远程接入推荐 `SSE`

## 4. 当前验证结果

### 4.1 自动化验证

- `tests/test_knowledge_smoke.py`
  覆盖基础配置、CLI parser、citation 构建等烟雾测试

- `tests/test_mcp_stdio.py`
  真实起 `stdio` MCP server，验证：
  - `list_tools`
  - `list_project_knowledge_documents`
  - `get_project_knowledge_document_status`

### 4.2 手工真实验证

已经验证过：

```bash
uv run python main.py ingest --project-id real-pdf-demo-v4 --file "test_data/接口文档.pdf"
uv run python main.py list-docs --project-id real-pdf-demo-v4
uv run python main.py query --project-id real-pdf-demo-v4 --query "这份接口文档主要描述了什么内容？" --mode hybrid
```

并且补充验证了：

- `ProjectRAGEngine.query(...)` 已返回真实 `citations`
- `fastmcp.Client(Path("src/mcp_server.py"))` 已能真实连接 MCP server
- `MCP_TRANSPORT=sse uv run python src/mcp_server.py` 已能真实起远程 SSE 服务
- `fastmcp.Client("http://127.0.0.1:8765/sse")` 已能真实通过 SSE 调用 `query_project_knowledge`

## 5. 当前仍保留的边界

以下内容目前没有继续做深，属于后续可选项：

- 基于 `document_ids` 做真正的检索范围过滤
- 更细粒度的 chunk / page 级 citation 映射
- 文档删除、重建索引、批量导入任务化
- 查询结果 rerank 模型接入
- 多模态增强重新放开后的稳定性治理

## 6. 下一步建议

如果继续往业务化推进，建议下一步优先做：

1. 统一 service facade，收敛 CLI 和 MCP 共用入口
2. 明确 ingest job / query job 的错误码和响应结构
3. 增加文档删除、重建索引和项目级清理能力
4. 再考虑挂到外部 runtime-service 或 agent tool 注册体系
