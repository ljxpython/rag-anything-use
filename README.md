# RAG-Anything Use

这个仓库不是 `RAG-Anything` 源码本体，而是一个基于 `RAG-Anything` 的使用与联调工程。

当前目标：

- 用 `docling` 作为主解析器
- 用 `.env` 管理模型与运行配置
- 跑通官方示例的核心能力
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
uv sync --frozen
```

如果只是正常同步依赖：

```bash
uv sync
```

## 使用 uv sync 时你需要知道的事

这个项目现在已经补齐了：

- `pyproject.toml`
- `uv.lock`

所以别人第一次拉代码后，可以直接：

```bash
uv sync --frozen
```

但这不代表就一定能立刻跑通，因为还有下面这些外部前提：

1. `.env` 必须填好
2. 你的模型接口必须可用
3. 你的 embedding 模型必须已经在服务端部署好
4. `test_data/` 里的路径必须真实存在

也就是说：

`uv sync` 解决的是 Python 依赖问题，不解决外部模型服务问题。

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

## 后续方向

接下来这个仓库更适合往“业务封装层”演进，而不是继续堆示例。

建议优先抽象：

- 文档摄入服务
- 查询服务
- 模型适配层
- 配置层

这样后面再做 API、任务队列和正式产品能力时，不会跟示例代码死绑在一起。
