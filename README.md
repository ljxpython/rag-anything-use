# RAG-Anything Use

项目资料的离线入库与只读 MCP 查询服务。文本索引使用 LightRAG；Docling / RAGAnything 作为可选文档解析依赖。查询服务不生成最终答案，由消费方 Agent 根据返回片段回答。

## 安装与边界

Python >=3.13、uv；查询/UTF-8 Markdown 和 TXT 入库：

```bash
uv sync --frozen --group dev
cp "env.example" ".env"
```

PDF/Office 入库或运行多模态 examples 另外安装：

```bash
uv sync --frozen --extra documents --group dev
```

锁定 FastMCP 3.2.0、LightRAG 1.4.12。Intel macOS 无锁定 Torch 2.11 wheel：文本模式可用，documents extra 需 ARM Mac 或受支持的 Linux；当前发布锁使用POSIX flock。不要将未验证的解析格式标为已支持。首版本地验证组合为 miaomiaoai `deepseek-v4.1-flash`、独立 Ollama `nomic-embed-text` / 768维。

## 最少配置

填写 `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY`、`EMBEDDING_BASE_URL/EMBEDDING_MODEL/EMBEDDING_DIM`、绝对 `KNOWLEDGE_ROOT_DIR`。文本查询不需要 TEST_DOCUMENT_PATH / TEST_IMAGE_PATH / VISION_*。

本地 miaomiaoai DeepSeek 抽取与关键词任务使用 `LLM_MAX_TOKENS=8192` 和 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`，确保有正文可解析；新版本资料已实测入库成功。该参数只用于支持此配置的供应商，其他供应商默认 `{}`。改变模型/Embedding 配置须重建新索引，不复用旧向量。

HTTP 还需服务端 Bearer → scope 映射。token 至少32字符；项目为 UUID，租户为 UUID 或平台已有的 `__default`。namespace 是本地不可变索引版本，允许单段字母、数字、下划线、短横线（最多96字符），不可共享给不同项目。

```dotenv
KNOWLEDGE_MCP_TOKEN_SCOPES_JSON={"replace-with-a-random-token-at-least-32-characters":{"tenant_id":"__default","project_id":"11111111-1111-4111-8111-111111111111","namespace":"project_a_v1"}}
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PATH=/mcp
```

凭据只写私有环境文件，不进入源码、模型参数或浏览器。文件权限600。以上 token 仅是占位，不可用于实际部署。

## 离线入库与发布

`--project-id` 是管理员 CLI 的索引 namespace，**不是网络工具参数**。当前文本资料以 UTF-8 保存。

```bash
uv run --frozen --env-file ".env" python "main.py" ingest --project-id project_a_v1 --file "资料/规范.md"
uv run --frozen --env-file ".env" python "main.py" list-docs --project-id project_a_v1
uv run --frozen --env-file ".env" python "main.py" publish --project-id project_a_v1
uv run --frozen --env-file ".env" python "src/mcp_server.py"
```

只有全部 ready 且模型/Embedding签名匹配的 namespace 才可服务。发布后冻结；失败或取消入库保留失败状态、不能发布；MCP运行时持有读锁，CLI不能同时写同一 namespace。更新资料需要新建 `project_a_v2`，完整导入、发布，再切换 token 配置并重启MCP；失败回到旧已发布版本，不删除目录。不要修改已有模型/维度后继续复用旧索引。

CLI `query` 和 `debug-retrieve` 是管理员诊断：可生成答案/输出内部路径和 raw_data。它们不通过MCP暴露，也不作为平台来源契约。

## MCP 契约

默认 Streamable HTTP `/mcp`，Bearer必需。stdio仅保留显式管理员模式，必须设置有效 `KNOWLEDGE_STDIO_TOKEN`。无匿名、公共库或未知范围回退。

- `mcp_query_project_knowledge(query, top_k=8)`：query去首尾空白后1–2000字符，top_k严格整数1–8，固定hybrid；只调用一次 `aquery_data`，不调用生成式 `aquery`。
- `list_project_knowledge_documents(limit=20)`：当前凭据范围的安全名称/状态，limit1–100。
- `get_project_knowledge_document_status(document_id)`：同一范围，opaque `kd_` ID。

查询返回同值JSON文本与structuredContent：`{"status":"ok","sources":[...]}`，无命中为 `{"status":"no_hit","sources":[]}`；服务失败为 MCP `isError=true`，不是no_hit。来源字段为 source_id / document_id / chunk_id / title / kind=knowledge / preview / truncated。最多8条、每片段800字符、JSON UTF-8最多12KiB；映射精确依据入库时的document_id，支持同名文件；不返回宿主路径、下载URL、页码、raw_data、凭据。供应商取消传播，单次检索60秒deadline。

所有网络工具为readOnly，不暴露上传/修改/删除接口。LightRAG hybrid可能调用关键词LLM与Embedding，外部调用费用需单独观察，不能把“无答案生成”理解为“无模型请求”。

```python
import asyncio
import os
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp", auth=os.environ["KNOWLEDGE_CLIENT_TOKEN"]) as client:
        result = await client.call_tool("mcp_query_project_knowledge", {"query": "登录凭证有效期？"})
        print(result.structured_content)

asyncio.run(main())
```

## 验证与交接

```bash
uv run --frozen --group dev python -m pytest "tests" -q
```

2026-10-11 本工程完整测试24项通过（10.42秒），包含HTTP/stdio、范围安全、初始化失败/取消、清理失败保留原异常及全部engine关闭。协议测试使用合成隔离样本，不自动调用真实模型。

独立本地服务另外完成两namespace真实入库/发布、两凭据HTTP检索、平台两主图真实Worker/DeepSeek链路；平台11项真实验收通过，含授权/撤权、Stop、fork和历史。读锁拒写、失败索引拒发布、新版本独立凭据、保留旧索引和MCP/Embedding重启也有证据。3份Markdown的30题合成检索验收：20题有答案Recall@8=100%，跨项目来源0；这不代表PDF或业务corpus准确率。PDF/Office Docling在Intel本机阻塞。

- [消费方接入契约](docs/mcp_receiver_integration_guide.md)
- [运行与更新](docs/rag_system_usage_guide.md)
- [当前能力与限制](docs/rag_system_current_progress.md)
- [Docling设计说明](docs/raganything_docling_guide.md)

`examples/` 为独立多模态实验，需documents extra、视觉模型与对应测试文件；示例历史记录不能代替当前服务验收。
