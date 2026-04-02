# MCP 接收方接入说明

## 1. 结论先说

对于这套知识库能力，接收方正式接入时推荐：

- `SSE`

而不是：

- `stdio`

`stdio` 只作为本地单机联调、开发调试和最小验证手段保留。

## 2. 为什么正式推荐 SSE

原因很现实，不是为了追时髦：

1. 未来知识库服务不会和所有接收方部署在同一台机器上。
2. 接收方和知识库服务会逐步变成独立部署单元。
3. `stdio` 天生适合“本地拉起一个子进程”，不适合跨机器、跨容器、跨服务治理。
4. `SSE` 更符合后续演进方向：
   - 独立部署
   - 远程访问
   - 网络层治理
   - 容器化
   - 统一鉴权和观测

所以这里的推荐策略非常明确：

- 本地联调：`stdio`
- 正式接入：`SSE`

## 3. 两种模式怎么理解

### 3.1 `stdio`

特点：

- 接收方本地直接拉起 MCP server 进程
- 配置简单
- 适合开发和单机调试

问题：

- 接收方必须能访问当前仓库和 Python 环境
- 进程生命周期绑在调用方本机
- 不适合远程部署和多服务共享

### 3.2 `SSE`

特点：

- 知识库 MCP server 独立运行成一个远程服务
- 接收方通过 URL 访问
- 更适合跨机器部署

优势：

- 可以独立扩容和迁移
- 接收方只关心 URL，不关心内部 Python 环境
- 更适合后续挂到网关、鉴权、监控体系里

## 4. 当前推荐的部署拓扑

推荐把知识库 MCP server 独立部署为一个远程服务：

```text
接收方 Agent / Runtime
        |
        |  MCP over SSE
        v
RAG Knowledge MCP Server
        |
        |  本地知识库目录 / 模型服务 / embedding 服务
        v
RAGAnything + LightRAG + Docling
```

换句话说：

- 接收方只接 MCP
- 知识库服务自己管理 `.env`、模型、embedding、索引目录

## 5. 服务端如何启动 SSE

当前仓库的 `src/mcp_server.py` 已经支持通过环境变量切换 transport。

### 5.1 推荐启动命令

```bash
MCP_TRANSPORT=sse \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
MCP_PATH=/sse \
MCP_MESSAGE_PATH=/messages/ \
uv run python src/mcp_server.py
```

说明：

- `MCP_TRANSPORT=sse`
  明确使用 SSE

- `MCP_HOST=0.0.0.0`
  对外监听

- `MCP_PORT=8000`
  服务端口

- `MCP_PATH=/sse`
  SSE 连接路径

- `MCP_MESSAGE_PATH=/messages/`
  SSE 消息路径

### 5.2 当前默认值

如果你没配，代码默认是：

- `MCP_TRANSPORT=stdio`
- `MCP_HOST=127.0.0.1`
- `MCP_PORT=8000`
- `MCP_PATH=/sse`
- `MCP_MESSAGE_PATH=/messages/`

所以正式部署时不要偷懒，至少把 `MCP_TRANSPORT` 和 `MCP_HOST` 改掉。

## 6. 接收方应该怎么配

接收方视角最重要的是：

- 只关心 MCP server 的 SSE URL
- 不需要知道这个服务内部是不是 Python、是不是 `uv`

### 6.1 推荐配置示意

如果接收方支持 MCP 配置对象，可以按这种思路配：

```json
{
  "mcpServers": {
    "test_case_knowledge": {
      "transport": "sse",
      "url": "http://rag-knowledge-service:8000/sse"
    }
  }
}
```

如果是 HTTPS：

```json
{
  "mcpServers": {
    "test_case_knowledge": {
      "transport": "sse",
      "url": "https://rag-knowledge.example.com/sse"
    }
  }
}
```

### 6.2 接收方只需要暴露哪些工具

当前建议只挂这三个：

- `query_project_knowledge`
- `list_project_knowledge_documents`
- `get_project_knowledge_document_status`

不建议接收方直接把 ingest 工具暴露给 agent。

## 7. 接收方为什么不推荐直接走 stdio

接收方如果直接用 `stdio`，通常意味着它要这么干：

1. 拿到当前仓库代码
2. 本地安装依赖
3. 本地配置 `.env`
4. 本地拉起 `uv run python src/mcp_server.py`

这个方式在联调时当然能跑，但正式环境有几个硬伤：

1. 接收方和知识库服务强耦合
2. 每个接收方节点都要重复配置依赖
3. 模型与索引目录难统一治理
4. 后续多实例部署会变得很乱

所以 `stdio` 的定位就一句话：

- 本地调试可以
- 正式接入不推荐

## 8. 本地联调时的 stdio 兜底方案

虽然正式推荐 SSE，但本地联调还是可以用 `stdio` 做最小验证。

启动：

```bash
uv run python src/mcp_server.py
```

本地 Python 侧验证：

```python
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
```

## 9. 推荐的接入顺序

建议接收方按这个顺序推进：

1. 先在当前仓库本地跑通 CLI
2. 再本地用 `stdio` 验证 MCP 工具是否正常
3. 再把服务端切成 `SSE`
4. 再让接收方用远程 URL 接入
5. 最后再做网关、鉴权、服务治理

这个顺序的好处是：

- 问题定位更清楚
- 不会一上来把“代码问题”和“网络问题”搅成一锅粥

## 10. 当前接收方最小参数约定

接收方调用时，最核心的参数约定是：

### 10.1 `query_project_knowledge`

必须传：

- `project_id`
- `query`

建议显式传：

- `top_k`
- `mode`

### 10.2 `list_project_knowledge_documents`

必须传：

- `project_id`

可选：

- `status`
- `limit`

### 10.3 `get_project_knowledge_document_status`

必须传：

- `project_id`
- `document_id`

## 11. 未来如果要继续升级

当前先推荐 `SSE`，已经足够支撑“远程服务化接入”。

如果以后继续演进，再考虑：

- `streamable-http`
- 网关鉴权
- 服务发现
- 统一日志与 tracing
- 容器化和滚动发布

但这都是下一阶段的事，不影响现在先把 `SSE` 作为正式接入标准定下来。
