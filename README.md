# RAG-Anything Use

项目资料的离线管理、只读 MCP 查询和平台精确授权的受管附件异步入库服务。在线入库默认关闭，首版能力为 UTF-8 Markdown/TXT；文本索引使用 LightRAG，Docling / RAGAnything 是后置格式能力。查询服务不生成最终答案，由消费方 Agent 根据返回片段回答。

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

锁定 FastMCP 3.2.0、LightRAG 1.4.12、httpx 0.28.1、Starlette 0.52.1。Intel macOS 无锁定 Torch 2.11 wheel：MD/TXT可用，documents extra 需 ARM Mac 或受支持的 Linux；当前发布锁使用POSIX flock。不要将未验证的解析格式标为已支持。本轮真实RAG证据使用 miaomiaoai `deepseek-v4.1-flash`、百炼兼容 `text-embedding-v4` / 1024维；旧Ollama/768索引不可混用。

## 最少配置

填写 `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY`、`EMBEDDING_BASE_URL/EMBEDDING_MODEL/EMBEDDING_DIM`、绝对 `KNOWLEDGE_ROOT_DIR`。文本查询不需要 TEST_DOCUMENT_PATH / TEST_IMAGE_PATH / VISION_*。

Embedding 默认使用 Ollama（`EMBEDDING_PROVIDER=ollama`）。外部兼容 `/embeddings` 的 API 设置 `EMBEDDING_PROVIDER=openai`、`EMBEDDING_API_KEY` 和对应的兼容接口根地址；例如百炼 `text-embedding-v4` 使用 1024 维。该调用发送 `dimensions` 参数，供应商需要支持指定维度。切换嵌入模型或维度后必须新建索引。

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

在线逻辑项目还需独立授权端点、`KNOWLEDGE_AUTHORIZATION_KEY_ID/SECRET` 和 `knowledge_base_id` scope；`KNOWLEDGE_ONLINE_ENABLED=false` 时不会开放写入。管理员先注册/迁移旧库并确认完整处理签名，再显式启用项目上传：

```bash
uv run --frozen --env-file ".env" python "main.py" init-project-knowledge --tenant-id __default --project-id 11111111-1111-4111-8111-111111111111
uv run --frozen --env-file ".env" python "main.py" migrate-project-knowledge --knowledge-base-id <kb_id> --namespace <legacy_namespace> --processing-signature <confirmed_signature>
uv run --frozen --env-file ".env" python "main.py" activate-knowledge-generation --knowledge-base-id <kb_id> --uploads on
```

内部 PUT 只接收 Runtime 传来的实际原字节和六字段 FileRef；MCP 提交工具只接受 `file_ref`，由官方 interceptor 注入短时 grant 与 upload ticket。RAG 使用完整冻结快照恢复到独立候选，只处理新文档，校验后原子激活；不直接改 active namespace，不自动全量重建。详见 [RAG 接线交接](docs/projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md)。

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
- online 逻辑库另外提供 `mcp_submit_project_knowledge_document(file_ref)` 和 `mcp_get_project_knowledge_ingest_job(job_id)`；提交立即返回 bounded queued/reused 回执，任务后台执行，旧三工具和来源字段保持不变。迁移旧文档复用允许 `job_id=null`，前端不轮询空ID。

查询返回同值JSON文本与structuredContent：`{"status":"ok","sources":[...]}`，无命中为 `{"status":"no_hit","sources":[]}`；服务失败为 MCP `isError=true`，不是no_hit。来源字段为 source_id / document_id / chunk_id / title / kind=knowledge / preview / truncated。最多8条、每片段800字符、JSON UTF-8最多12KiB；映射精确依据入库时的document_id，支持同名文件；不返回宿主路径、下载URL、页码、raw_data、凭据。供应商取消传播，单次检索60秒deadline。

legacy scope 的网络工具为只读，不暴露管理员接口；online 写入只开放上述精确工具并要求平台 grant/ticket，不能用静态 Bearer 提权。LightRAG hybrid可能调用关键词LLM与Embedding，外部调用费用需单独观察，不能把“无答案生成”理解为“无模型请求”。

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

2026-10-12 RAG范围完整测试67项通过（35.76秒），包含HTTP/stdio、范围安全、持久任务、原件票据、快照增量、调用计数、迁移/回退、故障进程回收及候选缓存回收。另有真实 DeepSeek/Embedding + worker/HTTP/MCP 隔离链路证据；生产IAM、前端、Linux格式和部署尚未联合验收。

独立本地服务另外完成两namespace真实入库/发布、两凭据HTTP检索、平台两主图真实Worker/DeepSeek链路；平台11项真实验收通过，含授权/撤权、Stop、fork和历史。读锁拒写、失败索引拒发布、新版本独立凭据、保留旧索引和MCP/Embedding重启也有证据。3份Markdown的30题合成检索验收：20题有答案Recall@8=100%，跨项目来源0；这不代表PDF或业务corpus准确率。PDF/Office Docling在Intel本机阻塞。

- [消费方接入契约](docs/mcp_receiver_integration_guide.md)
- [运行与更新](docs/rag_system_usage_guide.md)
- [当前能力与限制](docs/rag_system_current_progress.md)
- [Docling设计说明](docs/raganything_docling_guide.md)
- [项目成员 Agent MCP 异步入库](docs/projects/20261012-project-member-knowledge-upload/README.md)（RAG文本范围完成，整专项partial）

`examples/` 为独立多模态实验，需documents extra、视觉模型与对应测试文件；示例历史记录不能代替当前服务验收。
