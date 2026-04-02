# RAG 知识库使用说明

## 1. 文档目的

这份文档不讨论架构取舍，只解决一件事：

- 当前这套基于 `RAGAnything` 的知识库能力，开发时怎么用
- 本地 CLI 怎么用
- MCP server 怎么启动
- MCP 工具怎么调用

如果你要看设计背景和实现进度，另外参考：

- `docs/rag_system_design_for_test_case_service.md`
- `docs/rag_system_interface_spec.md`
- `docs/rag_system_current_progress.md`

## 2. 当前能力边界

当前仓库已经提供两层使用方式：

### 2.1 本地工具层

通过 CLI 做开发联调：

- 导入文档
- 查询知识库
- 查看检索上下文
- 查看文档列表
- 查看文档状态

### 2.2 MCP 暴露层

通过 `fastmcp` 对外暴露查询和状态能力：

- `query_project_knowledge`
- `list_project_knowledge_documents`
- `get_project_knowledge_document_status`

当前有一个明确边界：

- 文档导入和嵌入过程不暴露给 agent
- MCP 只暴露必要查询和文档状态工具

## 3. 环境准备

### 3.1 安装依赖

建议直接安装开发依赖组：

```bash
uv sync --group dev
```

如果你严格按锁文件安装：

```bash
uv sync --frozen --group dev
```

### 3.2 环境变量

复制模板：

```bash
cp env.example .env
```

至少确认这些配置已经填对：

- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`
- `VISION_BASE_URL`
- `VISION_MODEL`
- `VISION_API_KEY`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL`
- `TEST_DOCUMENT_PATH`
- `TEST_IMAGE_PATH`

### 3.3 当前推荐联调模式

为了保证“真实跑通”而不是碰运气，当前建议保持稳态配置：

```env
KNOWLEDGE_ENABLE_IMAGE_PROCESSING=false
KNOWLEDGE_ENABLE_TABLE_PROCESSING=false
KNOWLEDGE_ENABLE_EQUATION_PROCESSING=false

ENABLE_IMAGE_PROCESSING=false
ENABLE_TABLE_PROCESSING=false
ENABLE_EQUATION_PROCESSING=false
```

说明：

- `KNOWLEDGE_ENABLE_*` 给当前知识库封装层用
- `ENABLE_*` 给官方 examples 用
- 如果 examples 没单独设置 `ENABLE_*`，代码会回退读取 `KNOWLEDGE_ENABLE_*`

### 3.4 外部模型依赖

当前默认联调组合：

- 文本模型：`kimi-k2`
- 多模态模型：`qwen3-vl-plus`
- embedding：`nomic-embed-text`
- parser：`docling`

embedding 服务默认假设你本机或远端有可访问的 Ollama：

```bash
curl "http://127.0.0.1:11434/api/tags"
```

如果这个接口都不通，后面导入和查询别指望能正常工作。

## 4. 使用路径

当前推荐的开发路径很简单：

1. 先用 CLI 把 ingest 和 query 跑通
2. 再启动 MCP server
3. 再用 MCP client 做协议级调用验证
4. 最后才挂到外部系统

换句话说：

- CLI 是开发调试入口
- MCP 是系统集成入口

## 5. CLI 使用说明

当前入口：

```bash
uv run python main.py <command> ...
```

### 5.1 导入文档

命令：

```bash
uv run python main.py ingest --project-id demo-project --file "test_data/接口文档.pdf"
```

参数：

- `--project-id`
  项目标识，知识库按项目隔离

- `--file`
  本地文档路径

用途：

- 注册文档
- 解析文档
- 规范化 `content_list`
- 调用 `RAGAnything` 建索引
- 更新文档状态

成功后会返回：

- `accepted`
- `project_id`
- `document_id`
- `status`
- `message`

### 5.2 查询知识库

命令：

```bash
uv run python main.py query --project-id demo-project --query "客户登录接口使用什么方法？" --mode hybrid --top-k 8
```

参数：

- `--project-id`
  要查询的项目知识库

- `--query`
  查询问题

- `--mode`
  当前支持 `local`、`global`、`hybrid`、`naive`、`mix`、`bypass`

- `--top-k`
  传到底层检索的召回规模

返回重点：

- `answer`
- `citations`
- `matched_document_ids`

说明：

- 当前 `query` 命令已经把 `top_k` 真正传到底层
- `citations` 不是硬编码，是从 `LightRAG.aquery_data()` 的结构化检索结果里组出来的

### 5.3 查看检索上下文

命令：

```bash
uv run python main.py debug-retrieve --project-id demo-project --query "客户登录接口使用什么方法？" --mode hybrid --top-k 8
```

这个命令是开发期排障入口，主要看：

- `matched_document_ids`
- `citations`
- `chunks`
- `raw_data`

什么时候用：

- 你怀疑召回文档不对
- 模型答案不对，想确认是“没召回到”还是“召回到了但生成歪了”
- 你要看 LightRAG 返回的实体、关系、chunk 细节

### 5.4 查看文档列表

命令：

```bash
uv run python main.py list-docs --project-id demo-project
```

可选参数：

```bash
uv run python main.py list-docs --project-id demo-project --status ready --limit 20
```

用途：

- 查看项目下已登记文档
- 过滤状态
- 排查有没有 ingest 成功但你忘了文档 ID

### 5.5 查看单文档状态

命令：

```bash
uv run python main.py doc-status --project-id demo-project --document-id "kd_xxx"
```

重点字段：

- `overall_status`
- `parse_status`
- `index_status`
- `last_error`

### 5.6 当前真实验证过的命令

```bash
uv run python main.py ingest --project-id real-pdf-demo-v4 --file "test_data/接口文档.pdf"
uv run python main.py list-docs --project-id real-pdf-demo-v4
uv run python main.py query --project-id real-pdf-demo-v4 --query "客户登录接口使用什么方法？" --mode hybrid --top-k 8
uv run python main.py debug-retrieve --project-id real-pdf-demo-v4 --query "客户登录接口使用什么方法？" --mode hybrid --top-k 8
```

## 6. MCP 使用说明

当前 MCP server 文件：

- `src/mcp_server.py`

当前 transport 策略：

- 正式接入推荐：`SSE`
- 本地联调兜底：`stdio`

### 6.1 本地 `stdio` 启动

```bash
uv run python src/mcp_server.py
```

### 6.2 正式推荐的 `SSE` 启动

```bash
MCP_TRANSPORT=sse \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
MCP_PATH=/sse \
MCP_MESSAGE_PATH=/messages/ \
uv run python src/mcp_server.py
```

### 6.3 当前暴露的工具

#### 1. `query_project_knowledge`

用途：

- 查询指定项目知识库

参数：

- `project_id: str`
- `query: str`
- `top_k: int = 8`
- `mode: str = "hybrid"`

返回：

- `project_id`
- `query`
- `answer`
- `mode`
- `citations`
- `matched_document_ids`
- `debug_chunks`

注意：

- 当前 MCP 查询默认会带 `citations`
- 当前没有把 ingest 暴露成 MCP 工具

#### 2. `list_project_knowledge_documents`

用途：

- 列出项目知识文档

参数：

- `project_id: str`
- `status: str | None = None`
- `limit: int = 20`

返回：

- `project_id`
- `count`
- `documents`

#### 3. `get_project_knowledge_document_status`

用途：

- 查看单个文档状态

参数：

- `project_id: str`
- `document_id: str`

返回：

- 文档完整状态对象
- 如果文档不存在，会返回 `overall_status=not_found`

## 7. MCP 调用示例

### 7.1 用 `fastmcp.Client` 做本地 `stdio` 验证

```python
import asyncio
from pathlib import Path

from fastmcp import Client


async def main():
    async with Client(Path("src/mcp_server.py")) as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools])

        result = await client.call_tool(
            "query_project_knowledge",
            {
                "project_id": "real-pdf-demo-v4",
                "query": "客户登录接口使用什么方法？",
                "top_k": 8,
                "mode": "hybrid",
            },
        )
        print(result.data)


asyncio.run(main())
```

运行方式：

```bash
uv run python - <<'PY'
import asyncio
from pathlib import Path
from fastmcp import Client

async def main():
    async with Client(Path("src/mcp_server.py")) as client:
        result = await client.call_tool(
            "query_project_knowledge",
            {
                "project_id": "real-pdf-demo-v4",
                "query": "客户登录接口使用什么方法？",
                "top_k": 8,
                "mode": "hybrid",
            },
        )
        print(result.data)

asyncio.run(main())
PY
```

### 7.2 用 `fastmcp.Client` 连 `SSE` 地址

```bash
uv run python - <<'PY'
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/sse") as client:
        result = await client.call_tool(
            "query_project_knowledge",
            {
                "project_id": "real-pdf-demo-v4",
                "query": "客户登录接口使用什么方法？",
                "top_k": 8,
                "mode": "hybrid",
            },
        )
        print(result.data)

asyncio.run(main())
PY
```

### 7.3 查看当前工具列表

```bash
uv run python - <<'PY'
import asyncio
from pathlib import Path
from fastmcp import Client

async def main():
    async with Client(Path("src/mcp_server.py")) as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools])

asyncio.run(main())
PY
```

### 7.4 调文档列表工具

```bash
uv run python - <<'PY'
import asyncio
from pathlib import Path
from fastmcp import Client

async def main():
    async with Client(Path("src/mcp_server.py")) as client:
        result = await client.call_tool(
            "list_project_knowledge_documents",
            {"project_id": "real-pdf-demo-v4"},
        )
        print(result.data)

asyncio.run(main())
PY
```

## 8. 外部系统如何接

当前这边保证的是：

1. MCP server 可以独立启动
2. 工具名稳定
3. 参数和返回结构稳定

外部系统后面怎么注册、怎么 append 到自己的 tools 列表，那是外部系统的规范问题。

从这边的视角，只需要知道两件事：

### 8.1 正式接入时这是一个 SSE MCP server

也就是外部系统最终更应该通过远程 URL 接它，例如：

```bash
http://rag-knowledge-service:8000/sse
```

### 8.2 当前建议只给 agent 暴露这三类能力

- 查询知识库
- 查看项目文档列表
- 查看单文档状态

本地联调时，仍然可以退回 `stdio`。

不要直接把 ingest 暴露给 agent，原因很简单：

- agent 不适合直接操作文档入库
- ingest 更适合后台任务或明确的业务服务入口
- 否则后面权限、幂等、重复导入这些破事会一股脑全冒出来

## 9. 排障建议

### 9.1 `uv sync` 成功了，但命令还是跑不起来

先别怪 Python，优先检查：

- `.env` 有没有填
- `EMBEDDING_BASE_URL` 对不对
- Ollama 服务在不在
- 模型 API key 能不能用
- `TEST_DOCUMENT_PATH` 指向的文件是不是真存在

### 9.2 ingest 失败

优先查：

```bash
uv run python main.py doc-status --project-id demo-project --document-id "kd_xxx"
```

看：

- `last_error`
- `parse_status`
- `index_status`

### 9.3 query 结果不对

先跑：

```bash
uv run python main.py debug-retrieve --project-id demo-project --query "你的问题"
```

如果 `chunks` 就不对，问题在召回；
如果 `chunks` 对但 `answer` 乱，问题在生成模型。

### 9.4 MCP client 连不上

先做最小验证：

```bash
uv run python -m pytest tests/test_mcp_stdio.py -q
```

如果这都过不了，先别碰外部系统接入。

## 10. 当前已验证状态

目前已经验证：

- `pytest` 通过
- CLI 真查询可用
- CLI `debug-retrieve` 可用
- `fastmcp.Client(Path("src/mcp_server.py"))` 可真实连接并调用工具

这意味着当前这套东西已经可以作为后续业务封装和外部接入的底座继续往下做了。
