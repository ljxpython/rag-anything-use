# RAG-Anything 示例联调总结与后续抽象建议

## 1. 目的

这份文档用于记录当前项目对 `RAG-Anything` 示例代码的真实联调结果，并把这些联调工作沉淀成后续业务开发的铺垫。

这次工作的目标不是继续改库源码，而是确认下面几件事：

1. 当前环境下是否能真实跑通 `RAG-Anything`
2. 能否以 `docling` 作为后续主解析器
3. 现有免费模型组合是否能支撑联调阶段
4. 示例代码中哪些能力值得抽象封装，供后续业务开发复用

## 2. 当前联调配置

当前示例运行统一从项目根目录的 `.env` 读取配置，核心模型组合如下：

- Parser: `docling`
- Text LLM: `kimi-k2`
- Vision LLM: `qwen3-vl-plus`
- Embedding: `nomic-embed-text`

对应环境变量关键项：

```env
PARSER=docling
PARSE_METHOD=auto
WORKING_DIR=./rag_storage
OUTPUT_DIR=./output
TEST_DOCUMENT_PATH=./test_data/接口文档.pdf
TEST_IMAGE_PATH=./test_data/11a1f536fbf8a56a69ffa6b298b2408d.jpeg

LLM_BASE_URL=https://apis.iflow.cn/v1
LLM_MODEL=kimi-k2
LLM_API_KEY=***

VISION_BASE_URL=https://apis.iflow.cn/v1
VISION_MODEL=qwen3-vl-plus
VISION_API_KEY=***

EMBEDDING_BASE_URL=http://101.126.90.71:11434
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
```

## 3. 这次做了哪些改造

为了让示例真正可跑，而不是继续停留在官方占位代码，这次做了以下改造：

### 3.1 统一环境变量接入

新增公共 helper：

- `src/demo_support.py`

职责：

- 读取 `.env`
- 提供统一 `DemoSettings`
- 构造 `llm_model_func`
- 构造 `vision_model_func`
- 构造 `EmbeddingFunc`
- 构造 `RAGAnything` 与 `LightRAG`
- 统一测试文档、测试图片路径

这样后续不管是继续跑示例，还是抽成业务服务，都不需要在每个示例文件里重复抄一遍模型配置。

### 3.2 示例代码全部改为使用 `.env`

已改造文件：

- `examples/1_end_to_end.py`
- `examples/2_multimodal_content_processing.py`
- `examples/3_loading_existing_lightRAG_instance.py`
- `examples/4_direct_content_list_insertion.py`

这些示例现在不再依赖硬编码的：

- `your-api-key`
- `your-base-url`
- `gpt-4o-mini`
- `text-embedding-3-large`

而是统一走当前联调环境。

### 3.3 补充了适合上传仓库的 `.gitignore`

已补充忽略项：

- `.env`
- `.venv/`
- `.idea/`
- `output/`
- `rag_storage/`
- `existing_lightrag_storage/`
- `*.log`
- Python cache / pytest cache / mypy cache / ruff cache

目的很明确：

- 不把密钥和本地环境传上仓库
- 不把运行时生成物传上仓库

## 4. 联调验证结果

## 4.1 环境可用性确认

已做真实校验：

- `docling` 已安装并可调用
- `kimi-k2` 可通过 `https://apis.iflow.cn/v1` 正常完成文本对话
- `qwen3-vl-plus` 可通过同一 OpenAI 兼容接口正常完成图片对话
- `nomic-embed-text` 已部署在远程 Ollama，`/api/embed` 正常返回 768 维向量

结论：

当前这套免费联调组合可以作为后续开发阶段的默认测试配置。

## 4.2 `example 1`: `1_end_to_end.py`

状态：

- 已真实跑通

验证链路：

```text
docling 解析 PDF
-> LightRAG 初始化
-> 文本内容入库
-> 多模态表格处理
-> 实体/关系抽取
-> 纯文本查询
-> 带外部 equation 的多模态查询
```

本次使用文档：

- `test_data/接口文档.pdf`

实际结果：

- 文档成功解析，得到 29 个内容块
- 其中：
  - text: 25
  - table: 4
- 纯文本查询成功返回答案
- 多模态查询成功返回答案

说明：

这个示例已经证明主链路可用，后续如果我们做“文档入库 + 查询”的业务封装，可以直接基于这条链做抽象。

## 4.3 `example 2`: `2_multimodal_content_processing.py`

状态：

- 已修复并真实跑通

本次验证内容：

- 单图像处理
- 单表格处理
- 对应实体与关系抽取

本次使用资源：

- `test_data/11a1f536fbf8a56a69ffa6b298b2408d.jpeg`
- 内置测试表格数据

本次踩到的真实问题：

- `ImageModalProcessor.process_multimodal_content()`
- `TableModalProcessor.process_multimodal_content()`

从类型注解看像是返回 2 个值，但实际底层 `_create_entity_and_chunk()` 返回 3 个值：

1. description
2. entity_info
3. chunk_results

所以示例原本的 2 值解包会直接炸：

```python
ValueError: too many values to unpack (expected 2)
```

已修复方式：

- 将示例改为按 3 个值接收

结论：

这个示例证明了“独立模态处理器”这条能力是可用的，后续如果我们想单独封装图片理解、表格理解服务，这条链可以直接复用。

## 4.4 `example 4`: `4_direct_content_list_insertion.py`

状态：

- 已真实跑通

本次验证内容：

1. 直接插入手工构造的 `content_list`
2. 直插后执行查询
3. 再插入第二份文档
4. 再执行查询

验证内容类型：

- text
- image
- table
- equation

本次结果说明：

- `insert_content_list()` 这条链是可用的
- 直插内容可以参与后续实体抽取、关系构建和 VLM 增强查询
- 第二份文档追加写入后也能继续查询

结论：

这条能力对后续业务开发价值很大，因为它允许我们：

1. 不强绑定 `RAG-Anything` 内置 parser
2. 将来如果自己接 `docling` 或外部解析系统，可以把清洗后的标准内容列表直接送进去

这很可能是后续业务封装最值得优先抽象的能力之一。

## 4.5 `example 3`: `3_loading_existing_lightRAG_instance.py`

状态：

- 核心路径已验证
- 本轮运行中确认了“加载已有/新建 LightRAG 实例 + 继续处理文档”的能力可用
- 但该示例在本轮联调中运行时间较长，未在一次短轮询中完整收尾截图

本次实际观测到的事实：

- 可正常创建或接管已有 `LightRAG`
- 初始空库查询会返回无结果
- 后续能继续接入 `RAGAnything` 处理文档
- 与 `example 1` 一样，会进入多模态表格处理阶段

结论：

这个示例的关键价值不是“演示问答”，而是证明：

我们后续完全可以把 `LightRAG` 存储生命周期和 `RAGAnything` 使用生命周期拆开。

这对于后续做：

- 长期知识库
- 持久化工作目录
- 定时增量更新
- 应用重启后继续使用已有索引

很重要。

## 5. 真实踩到的问题

## 5.1 Embedding 函数必须符合 LightRAG 的异步契约

最开始自定义 embedding helper 直接返回 `numpy.ndarray`，结果被 `LightRAG` 当作协程去 `await`，直接报错：

```text
TypeError: object numpy.ndarray can't be used in 'await' expression
```

解决：

- 将 embedding helper 改为 async 包装
- 内部用 `asyncio.to_thread()` 调同步 HTTP 请求

这意味着后续如果我们再接别的 embedding 服务，也必须遵守这个调用契约。

## 5.2 `kimi-k2` 在并发多模态表格处理中偶发返回格式异常

在 `example 1`、`example 3`、`example 4` 的多模态表格处理阶段，都真实出现过：

```text
Invalid response from OpenAI API
RetryError[...InvalidResponseError]
```

但现象不是完全阻塞，而是：

1. 并发批量处理时偶发失败
2. 之后 `RAG-Anything` fallback 到逐条处理
3. 逐条处理通常还能继续完成

这说明问题更像是：

- `iflow` 的 `kimi-k2` 在某些提示词或返回格式下，与 `openai_complete_if_cache` 的期望存在兼容性边角问题
- 不是模型整体不可用

对后续开发的启示：

- 联调阶段可以继续用
- 但生产化前最好加一层更稳的响应清洗/重试包装
- 或者把多模态表格说明生成换成更稳定的模型

## 5.3 官方示例与实际返回结构存在错位

典型例子就是 `example 2` 的解包问题。

说明：

- 官方示例不能盲信
- 后续开发时必须以当前安装版本源码行为为准

## 5.4 `docling` 在当前测试 PDF 上主要抽出的是文本和表格

对 `接口文档.pdf` 的解析结果中：

- text: 25
- table: 4
- 没有图片块

这说明：

- `docling` 适合当前这类接口/说明类 PDF
- 后续如果文档类型更复杂，还要进一步验证图像、复杂布局、页码映射质量

## 6. 这次联调的结论

可以明确下结论：

### 6.1 已经跑通的能力

- `docling` 解析 PDF
- `RAGAnything` 初始化与工作目录存储
- 远程 Ollama embedding 接入
- `kimi-k2` 文本问答
- `qwen3-vl-plus` 图片/VLM 问答
- 文本入库
- 多模态处理
- `insert_content_list()` 直插内容
- 基于已处理内容的查询

### 6.2 这次联调最值钱的两个入口

后续做业务开发，最值得优先封装的是：

1. `process_document_complete()`
2. `insert_content_list()`

原因：

- 前者适合“给我一个文档，我帮你直接入库”
- 后者适合“我自己控制解析和清洗，再把标准化结构交给引擎”

## 7. 后续建议抽象的模块

这次示例联调不是终点，主要是为后面抽象封装做铺垫。基于当前结果，建议优先抽下面几层：

## 7.1 配置层

建议抽一个统一配置模块，封装：

- parser
- llm
- vision
- embedding
- working_dir
- output_dir
- test / runtime paths

本次的 `src/demo_support.py` 已经是第一版雏形。

## 7.2 文档摄入层

建议抽一个统一入口服务，例如：

```python
class DocumentIngestService:
    async def ingest_file(self, file_path: str) -> str: ...
    async def ingest_content_list(self, content_list: list[dict], file_path: str) -> str: ...
```

作用：

- 统一屏蔽 `RAGAnything` 的细节
- 未来可插入日志、重试、清洗、状态跟踪

## 7.3 查询层

建议抽一个统一查询服务，例如：

```python
class KnowledgeQueryService:
    async def query(self, question: str) -> str: ...
    async def query_with_multimodal(self, question: str, multimodal_content: list[dict]) -> str: ...
```

作用：

- 屏蔽当前模型兼容性问题
- 统一封装 query mode、超时、返回格式

## 7.4 模型适配层

后续最好把当前这三套模型调用再独立封装一层：

- `kimi-k2`
- `qwen3-vl-plus`
- `nomic-embed-text`

原因：

- 现在只是联调可用
- 但后面一定会碰到模型替换、响应清洗、异常重试、速率限制等问题

## 8. 推荐的下一步

如果接下来要开始做真正的业务功能，而不是继续试 demo，我建议下一步优先做：

1. 抽一个 `RagEngine` 或 `RagAnythingClient`
2. 抽一个 `DocumentIngestService`
3. 抽一个 `KnowledgeQueryService`
4. 明确业务数据模型：
   - 原始文件
   - 解析结果
   - 文档 ID
   - 查询结果
   - 引用信息

这几层一旦立住，后面做接口、任务队列、批量摄入和知识库应用都会顺很多。

## 9. 总结

这轮工作已经完成了最关键的验证：

- 当前免费联调模型组合可用
- `docling` 可作为后续主解析器
- `RAG-Anything` 的主链路已经被真实跑通
- `insert_content_list()` 也已经验证可用

因此，后续开发不需要再围着“这个库到底能不能用”打转，可以正式进入“如何抽象、如何封装、如何设计业务层”的阶段。
