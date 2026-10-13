# RAG-Anything Use

项目资料的离线管理、只读 MCP 查询和平台精确授权的受管附件异步入库服务。在线入库默认关闭；基础能力为 UTF-8 Markdown/TXT，启用完整 documents 依赖及多模态配置后支持 PDF／DOCX／PPTX／PNG／JPEG；文本索引使用 LightRAG，Docling / RAGAnything 提供可选文档解析与多模态处理。查询服务不生成最终答案，由消费方 Agent 根据返回片段回答。

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

锁定 RAG-Anything 1.4.2、MinerU 3.4.5、Docling 2.84.0；FastMCP 3.2.0、LightRAG 1.4.12、httpx 0.28.1、Starlette 0.52.1保留。Intel macOS 无锁定 Torch 2.11 wheel：MD/TXT可用，documents extra 需 ARM Mac 或受支持的 Linux；当前发布锁使用POSIX flock。Ubuntu 隔离环境已通过文本／扫描／混合 PDF、DOCX、PPTX 完整入库→发布→鉴权 HTTP MCP 与图表／公式／图片事实验收；PNG／JPEG 在线入库及恢复已通过，逐轮结果见[本轮验证](docs/projects/20261013-online-documents/verification.md)。真实RAG证据使用 miaomiaoai `deepseek-v4.1-flash`、百炼兼容 `text-embedding-v4` / 1024维；旧Ollama/768索引不可混用。

## 最少配置

填写 `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY`、`EMBEDDING_BASE_URL/EMBEDDING_MODEL/EMBEDDING_DIM`、绝对 `KNOWLEDGE_ROOT_DIR`。文本查询不需要 TEST_DOCUMENT_PATH / TEST_IMAGE_PATH / VISION_*。

Embedding 默认使用 Ollama（`EMBEDDING_PROVIDER=ollama`）。外部兼容 `/embeddings` 的 API 设置 `EMBEDDING_PROVIDER=openai`、`EMBEDDING_API_KEY` 和对应的兼容接口根地址；例如百炼 `text-embedding-v4` 使用 1024 维。该调用发送 `dimensions` 参数，供应商需要支持指定维度。切换嵌入模型或维度后必须新建索引。

本地 miaomiaoai DeepSeek 抽取与关键词任务使用 `LLM_MAX_TOKENS=8192` 和 `LLM_EXTRA_BODY_JSON='{"thinking":{"type":"disabled"},"reasoning_effort":"off"}'`，按当前供应商实测减少推理挤占正文预算；`none` 曾在复杂文档节点返回 400，最终五格式用 `off` 复跑通过。该参数只用于支持此配置的供应商，其他供应商默认 `{}`。改变模型/Embedding 配置须重建新索引，不复用旧向量。

当前文本／视觉均使用 miaomiaoai `deepseek-v4.1-flash`。视觉三项 `VISION_BASE_URL/MODEL/API_KEY` 在私有 `.env` 中显式填写与对应 LLM 相同的值，`VISION_MAX_TOKENS=8192`；项目示例已删除旧供应商和备用配置。文本模式不调用视觉接口，多模态开关默认关闭。更换视觉配置也会改变 online 处理签名；已有逻辑库不绕过签名校验，正式切换需独立新库／候选验证。

最终五格式未出现多模态分析失败或 individual fallback；供应商仍可能限流，最终质量基线出现两次 Embedding 429 后按现有策略恢复。解析／索引失败查私有日志并用独立候选复验，旧已发布库不受失败候选影响。

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

在线文档能力需 `PARSER=docling`、`ENABLE_IMAGE_PROCESSING/ENABLE_TABLE_PROCESSING/ENABLE_EQUATION_PROCESSING=true` 和已安装 documents extra；依赖或开关缺失时能力只报告 MD/TXT。原件 20MiB，验证真实容器；受管图片与 content-list 完整保存／校验，旧快照恢复不重新解析或调用模型。已下载完整 Docling 模型缓存可设置 `HF_HUB_OFFLINE=1`，缺缓存显式失败。图片平台 ImageRef 可信收据仍待接入，RAG 支持不能直接等同平台浏览器图片入库。详见 [在线文档专项](docs/projects/20261013-online-documents/README.md)。

内部 PUT 只接收 Runtime 传来的实际原字节和六字段 FileRef；MCP 提交工具只接受 `file_ref`，由官方 interceptor 注入短时 grant 与 upload ticket。RAG 使用完整冻结快照恢复到独立候选，只处理新文档，校验后原子激活；不直接改 active namespace，不自动全量重建。详见 [RAG 接线交接](docs/projects/20261012-project-member-knowledge-upload/implementation/rag-handoff.md)。

失 ACK 后使用同 request_id 的内部 GET＋新 upload grant 只读回查，不再次 submit/换 key；后台持久保存原 graph/来源/文件字段并重新申请 start/activate 租约。旧版本任务缺可信字段时不自动补造来源，须重新明确提交合法请求。详见 [平台契约修复与升级](docs/projects/20261012-rag-provider-contract-alignment/README.md)。

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

- `mcp_query_project_knowledge(query, top_k=8, sources_version=1)`：query去首尾空白后1–2000字符，top_k严格整数1–8，固定hybrid；只调用一次 `aquery_data`，不调用生成式 `aquery`。
- `list_project_knowledge_documents(limit=20)`：当前凭据范围的安全名称/状态，limit1–100。
- `get_project_knowledge_document_status(document_id)`：同一范围，opaque `kd_` ID。
- online 逻辑库另外提供 `mcp_submit_project_knowledge_document(file_ref)` 和 `mcp_get_project_knowledge_ingest_job(job_id)`；提交立即返回 bounded queued/reused 回执，任务后台执行，旧三工具和来源字段保持不变。迁移旧文档复用允许 `job_id=null`，前端不轮询空ID。

查询返回同值JSON文本与structuredContent：`{"status":"ok","sources":[...]}`，无命中为 `{"status":"no_hit","sources":[]}`；服务失败为 MCP `isError=true`，不是no_hit。来源字段为 source_id / document_id / chunk_id / title / kind=knowledge / preview / truncated。最多8条、每片段800字符、JSON UTF-8最多12KiB；映射精确依据入库时的document_id，支持同名文件；v1 不返回页码；两版均不返回宿主路径、下载URL、raw_data、凭据。供应商取消传播，单次检索60秒deadline。

显式 `sources_version=2` 增加顶层版本和每来源 `locator:{unit,start,end,block_type}`；PDF 页、可靠 PPTX 幻灯片从绑定的真实 chunk 读取，均为 1-based 范围；DOCX／图片／未知位置返回 unknown 和 null，不猜页。旧平台保持默认 v1，平台 v2 DTO 与展示合入顺序见 [平台协同方案](docs/projects/20261013-online-documents/platform-contract.md)。

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

RAG 交接统一使用 `main`：2026-10-13 经用户批准，将验收分支 `feat/online-documents-20261013@2bd5818` 快进合入，保留全部原主线提交。本地目录为 `/Users/lijiaxin/PyCharmMiscProject/rag-anything-use`，Ubuntu 为 `/home/ubuntu/PyCharmMiscProject/rag-anything-use`；两处跟踪 `origin/main`。合入后 Ubuntu 全套再次 **119 passed / 26.07s**。平台同事从远端 `main` 获取代码和下列交接文档；平台原知识 worktree 及其未提交改动仍按协同方案保留。私有配置、依赖安装目录和知识库按环境管理，不进入 Git 同步。

```bash
uv run --frozen --group dev python -m pytest "tests" -q
```

测试需要私有 `.env` 中的模型配置；测试替换实际模型调用，不要求发业务资料。无 `.env` 时可用临时假配置执行：

```bash
LLM_BASE_URL=http://127.0.0.1:1 LLM_MODEL=test-llm LLM_API_KEY=test-key EMBEDDING_BASE_URL=http://127.0.0.1:1 EMBEDDING_MODEL=test-embed uv run --frozen pytest "tests" -q
```

2026-10-13 本轮最终 Ubuntu **119 passed / 27.32s**；16 个变更 Python 文件 ruff format／check、compileall、frozen lock 与 pip check 均通过。旧授权／失 ACK、增量／迁移／回退测试保留。平台临时 union 的真实成员上传、Worker、浏览器 ready、另一成员新旧查询、撤权／Stop／重启／Fork／重复零新增调用通过；platform-api/runtime/web 相关知识与 Token／后台回归通过，详见 [最终验证](docs/projects/20261013-online-documents/verification.md)。平台主工作区尚未正式合并本期补丁，现役未部署。

最终 3 份公开合成 API／运维／发布资料、19 题评测：16 道有答案 Recall@8／证据完整率 100%，跨项目来源 0，检索 P50／P95 为 **2.948／3.564 秒**。三类无答案问题仍可能返回无关来源，真实 Agent 均拒答；检索服务不自行宣称“找到了答案”。私有业务语料与生产 SLA 尚未提供，不外推。20MiB 双页 PDF、两项目排队期间旧库查询、30 次确定性快照与读恢复／锁回收均有证据，费用金额未知为 null。

可复跑入口（均创建独立临时 namespace；前两个使用配置的模型并产生调用费用）：

```bash
uv run --frozen --env-file ".env" python "scripts/evaluate_knowledge.py" --output "/tmp/rag-evaluation.json"
HF_HUB_OFFLINE=1 uv run --frozen --env-file ".env" python "scripts/verify_document_formats.py" --output "/tmp/rag-formats.json"
uv run --frozen python "scripts/benchmark_knowledge_snapshots.py" --documents 30 --output "/tmp/rag-capacity.json"
```

格式脚本需 documents extra、完整 Docling 模型缓存及视觉配置。五格式最终独立复跑 13 事实命中，PNG／JPEG 真模型入库／复用／reader 重启通过；图片测试授权边界为受控 fixture，不冒充平台 ImageRef 浏览器闭环。首次失败和供应商参数修复证据保留在专项，平台正式 v2 展示、图片可信收据及部署计划见 [协同方案](docs/projects/20261013-online-documents/platform-contract.md)，音视频按用户决定延期。

- [消费方接入契约](docs/mcp_receiver_integration_guide.md)
- [运行与更新](docs/rag_system_usage_guide.md)
- [当前能力与限制](docs/rag_system_current_progress.md)
- [剩余开发、验收与 Ubuntu 用途](docs/remaining-work.md)
- [Ubuntu 在线文档与联合验收](docs/projects/20261013-online-documents/README.md)（本期实现／验收通过，main 交付）
- [模型供应商配置清理](docs/projects/20261013-model-provider-cleanup/README.md)
- [Docling设计说明](docs/raganything_docling_guide.md)
- [项目成员 Agent MCP 异步入库](docs/projects/20261012-project-member-knowledge-upload/README.md)（RAG文本范围完成，整专项partial）
- [平台后台授权与失ACK回查](docs/projects/20261012-rag-provider-contract-alignment/README.md)（done；主线修复保留）
- [项目优化与 RAG-Anything 升级](docs/projects/20261012-rag-optimization/README.md)（done；2026-10-13用户验收本期范围通过，复杂格式/多模态限制与后置项保留）

`examples/` 为独立多模态实验，需documents extra、视觉模型与对应测试文件；示例历史记录不能代替当前服务验收。
