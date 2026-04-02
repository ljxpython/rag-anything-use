# RAG-Anything Use

这个仓库不是 `RAG-Anything` 源码本体，而是一个基于 `RAG-Anything` 的使用与联调工程。

当前目标：

- 用 `docling` 作为主解析器
- 用 `.env` 管理模型与运行配置
- 跑通官方示例的核心能力
- 基于 `RAGAnything` 封装可复用的知识库 CLI 与 MCP 服务
- 为后续业务开发做抽象与封装铺垫

当前已经验证过的一组联调模型组合：

- Text LLM: `kimi-k2`
- Vision LLM: `qwen3-vl-plus`
- Embedding: `nomic-embed-text`
- Parser: `docling`

同时保留了上线备用模型配置：

- Text LLM: `deepseek-chat`
- Vision LLM: `doubao-seed-1-6-251015`

## 目录说明

- `examples/`
  RAG-Anything 示例代码，已改造成通过 `.env` 读取配置

- `src/demo_support.py`
  示例公共 helper，负责读取环境变量并构造：
  - `RAGAnything`
  - `LightRAG`
  - `llm_model_func`
  - `vision_model_func`
  - `embedding_func`

- `docs/`
  当前项目的分析文档与联调总结

- `src/knowledge/`
  当前业务封装层，负责项目级知识库的 ingest、query、registry 和配置管理

- `src/cli.py`
  当前知识库命令行入口

- `src/mcp_server.py`
  基于 `fastmcp` 的 MCP server，只暴露查询和文档状态相关工具

- `test_data/`
  本地测试文件

- `env.example`
  脱敏环境变量模板

## 环境要求

### 1. Python

当前项目要求：

```bash
python >= 3.13
```

### 2. uv

先安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

确认版本：

```bash
uv --version
```

### 3. 外部服务

这仓库虽然可以通过 `uv sync` 安装 Python 依赖，但还有几样东西不是 `uv` 自动帮你变出来的：

- 一个可用的文本推理模型接口
- 一个可用的多模态视觉模型接口
- 一个可用的 embedding 服务
- 测试文档和测试图片

当前默认配置下，外部依赖是：

- `https://apis.iflow.cn/v1`
  - `kimi-k2`
  - `qwen3-vl-plus`

- `http://<your-ollama-host>:11434`
  - `nomic-embed-text`

### 4. docling

`docling` 已经写入 `pyproject.toml` 依赖中，`uv sync` 会自动安装其 Python 包和命令行工具。

安装完成后可以验证：

```bash
uv run docling --version
```

## 安装步骤

### 1. 克隆仓库

```bash
git clone <your-repo-url>
cd rag-anything-use
```

### 2. 复制环境变量模板

```bash
cp env.example .env
```

### 3. 修改 `.env`

至少要确认这些字段：

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

### 4. 安装依赖

如果你希望严格按锁文件安装：

```bash
uv sync --frozen --group dev
```

如果只是正常同步依赖：

```bash
uv sync --group dev
```

## 使用 uv sync 时你需要知道的事

这个项目现在已经补齐了：

- `pyproject.toml`
- `uv.lock`

所以别人第一次拉代码后，可以直接：

```bash
uv sync --frozen --group dev
```

但这不代表就一定能立刻跑通，因为还有下面这些外部前提：

1. `.env` 必须填好
2. 你的模型接口必须可用
3. 你的 embedding 模型必须已经在服务端部署好
4. `test_data/` 里的路径必须真实存在

也就是说：

`uv sync` 解决的是 Python 依赖问题，不解决外部模型服务问题。

另外这一句别漏了：

- 如果你要跑 `pytest`、做 MCP 协议验证，应该用 `uv sync --group dev`
- 如果只跑 examples，`uv sync` 也能用，但现在仓库默认建议直接带上 `--group dev`

## 环境变量说明

当前 `.env` 里有两组和“多模态开关”相关的变量：

- `KNOWLEDGE_ENABLE_*`
  当前知识库封装层使用，默认建议全部设为 `false`，保证联调稳态

- `ENABLE_*`
  官方 examples 使用；如果你没单独设置，代码会自动回退读取 `KNOWLEDGE_ENABLE_*`

所以现在推荐的联调稳态就是：

```bash
KNOWLEDGE_ENABLE_IMAGE_PROCESSING=false
KNOWLEDGE_ENABLE_TABLE_PROCESSING=false
KNOWLEDGE_ENABLE_EQUATION_PROCESSING=false

ENABLE_IMAGE_PROCESSING=false
ENABLE_TABLE_PROCESSING=false
ENABLE_EQUATION_PROCESSING=false
```

## 运行示例

推荐使用 `uv run`，不用手动激活虚拟环境。

### 1. 端到端文档处理与查询

```bash
uv run python examples/1_end_to_end.py
```

这个示例会做：

1. 用 `docling` 解析测试 PDF
2. 用 `RAGAnything` 完成文本入库与多模态处理
3. 执行一次文本查询
4. 执行一次带外部 equation 的多模态查询

### 2. 独立模态处理

```bash
uv run python examples/2_multimodal_content_processing.py
```

这个示例会验证：

- 图片处理
- 表格处理
- 对应的实体/关系抽取

### 3. 基于已有 LightRAG 实例继续处理

```bash
uv run python examples/3_loading_existing_lightRAG_instance.py
```

这个示例适合验证：

- 已有工作目录复用
- 基于已有 `LightRAG` 实例继续处理文档

### 4. 直接插入 content_list

```bash
uv run python examples/4_direct_content_list_insertion.py
```

这个示例适合验证：

- 跳过解析
- 直接插入标准化 `content_list`
- 追加多份内容再查询

## 知识库 CLI

当前仓库已经补了一层项目级知识库 CLI，适合后续业务封装和手工联调。

### 1. 导入文档

```bash
uv run python main.py ingest --project-id demo-project --file "test_data/接口文档.pdf"
```

### 2. 查询知识库

```bash
uv run python main.py query --project-id demo-project --query "客户登录接口使用什么方法？" --mode hybrid --top-k 8
```

### 3. 查看检索上下文

```bash
uv run python main.py debug-retrieve --project-id demo-project --query "客户登录接口使用什么方法？" --mode hybrid --top-k 8
```

### 4. 查看已导入文档

```bash
uv run python main.py list-docs --project-id demo-project
```

### 5. 查看单文档状态

```bash
uv run python main.py doc-status --project-id demo-project --document-id "<document-id>"
```

当前 `query` 命令已经补齐：

- `top_k` 真正传到底层检索
- `citations`
- `matched_document_ids`
- 可选 `debug_chunks`

## MCP 服务

当前仓库已经提供 `fastmcp` server，后续别的系统只需要把这个 MCP 服务挂进去即可。

当前 transport 策略：

- 正式远程接入推荐 `SSE`
- 本地联调保留 `stdio`

### 1. 本地 `stdio` 启动

```bash
uv run python src/mcp_server.py
```

### 2. 正式推荐的 `SSE` 启动

```bash
MCP_TRANSPORT=sse \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
MCP_PATH=/sse \
MCP_MESSAGE_PATH=/messages/ \
uv run python src/mcp_server.py
```

### 3. 当前暴露的工具

- `query_project_knowledge`
- `list_project_knowledge_documents`
- `get_project_knowledge_document_status`

### 4. 本地协议验证示例

```bash
uv run python - <<'PY'
import asyncio
from pathlib import Path
from fastmcp import Client

async def main():
    async with Client(Path("src/mcp_server.py")) as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools])
        result = await client.call_tool(
            "list_project_knowledge_documents",
            {"project_id": "demo-project"},
        )
        print(result.data)

asyncio.run(main())
PY
```

## 测试

### 1. 跑单测

```bash
uv run python -m pytest tests -q
```

### 2. 当前已验证过的真实链路

```bash
uv run python main.py ingest --project-id real-pdf-demo-v4 --file "test_data/接口文档.pdf"
uv run python main.py list-docs --project-id real-pdf-demo-v4
uv run python main.py query --project-id real-pdf-demo-v4 --query "这份接口文档主要描述了什么内容？" --mode hybrid
```

## 常见问题

### 1. 为什么 `uv sync` 完了还是跑不起来？

最常见原因不是 Python 依赖，而是这些外部条件没满足：

- `.env` 没填
- API key 无效
- embedding 服务不可用
- `docling` 可以执行但测试文件路径不对

### 2. 为什么多模态表格处理偶尔会报 `Invalid response from OpenAI API`？

当前联调阶段使用的是免费模型组合。真实联调里观察到：

- `kimi-k2` 在某些结构化抽取 prompt 下偶发返回格式不稳定
- `RAG-Anything` 通常会 fallback 到逐条处理

这不影响我们当前把主链路跑通，但后面如果要上生产，建议：

- 加强响应清洗
- 或者为结构化抽取切换更稳定的模型

### 3. 为什么 `.env` 里有两套模型配置？

因为当前联调用的是免费模型，目的是省成本；上线时计划切回：

- `deepseek-chat`
- `doubao-seed-1-6-251015`

所以把这组配置保留成了备注，后续切换时不用再翻聊天记录。

## 已有文档

- [docs/raganything_docling_guide.md](./docs/raganything_docling_guide.md)
  RAG-Anything 使用说明与 `docling` 方案解读

- [docs/raganything_examples_validation.md](./docs/raganything_examples_validation.md)
  示例联调总结、踩坑记录和后续抽象建议

- [docs/rag_system_current_progress.md](./docs/rag_system_current_progress.md)
  当前知识库封装、CLI、MCP 和真实验证进度

- [docs/rag_system_usage_guide.md](./docs/rag_system_usage_guide.md)
  从本地 CLI 到 MCP 调用的完整使用说明

- [docs/mcp_receiver_integration_guide.md](./docs/mcp_receiver_integration_guide.md)
  从接收方视角说明为什么正式推荐 SSE，以及应该如何接入

## 后续方向

接下来这个仓库更适合往“业务封装层”演进，而不是继续堆示例。

建议优先抽象：

- 文档摄入服务
- 查询服务
- 模型适配层
- 配置层

这样后面再做 API、任务队列和正式产品能力时，不会跟示例代码死绑在一起。
