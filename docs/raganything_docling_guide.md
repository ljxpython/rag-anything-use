# RAG-Anything 使用说明与二次开发指南

## 1. 文档目的

这份文档用于给当前项目做技术底稿，目标不是分析 RAG-Anything 源码实现细节本身，而是回答下面几个开发问题：

1. RAG-Anything 这个库到底负责什么
2. 它的核心模块怎么协作
3. 如果我们后续基于这个库做自己的功能，应该怎么调用
4. 当我们明确选择 `docling` 作为解析器时，正确的使用方式是什么
5. 当前仓库文档和示例里有哪些地方与源码不完全一致，需要提前避坑

说明：本文内容基于官方仓库源码阅读整理，重点参考以下模块：

- `raganything/raganything.py`
- `raganything/config.py`
- `raganything/processor.py`
- `raganything/query.py`
- `raganything/parser.py`
- `raganything/modalprocessors.py`
- `examples/raganything_example.py`
- `docs/context_aware_processing.md`
- `docs/batch_processing.md`

## 2. 项目定位

RAG-Anything 不是一个单纯的聊天 SDK，它更像一个“多模态文档 RAG 流水线封装器”。

它主要解决的是这件事：

1. 输入复杂文档，例如 PDF、Word、PPT、Excel、HTML、图片
2. 调用解析器把文档拆成结构化内容列表 `content_list`
3. 把纯文本写进 LightRAG
4. 把图片、表格、公式等多模态内容交给专门处理器做说明、实体提取和关系构建
5. 最终通过 LightRAG 提供文本检索、多模态检索和增强问答

一句话总结：

RAG-Anything = 文档解析层 + 多模态处理层 + LightRAG 入库层 + 查询层

## 3. 核心模块关系图

下面这个图是按“库的职责边界”来画的，不是按文件夹硬堆。

```text
+---------------------------+
|  你的业务代码 / 应用层    |
|  API / Worker / CLI       |
+-------------+-------------+
              |
              v
+---------------------------+
|       RAGAnything         |
|  统一入口与胶水编排层     |
|  - process_document_*     |
|  - insert_content_list    |
|  - aquery                 |
|  - aquery_with_multimodal |
+------+------+-------------+
       |      |
       |      +-----------------------------+
       |                                    |
       v                                    v
+--------------+                  +-------------------+
| ProcessorMixin|                 |   QueryMixin      |
| 文档摄入流程   |                 | 查询与多模态查询   |
+------+-------+                  +---------+---------+
       |                                      |
       v                                      v
+--------------+                  +-------------------+
| Parser 层     |                  |   LightRAG        |
| mineru/docling|                  | 向量/图谱/状态存储 |
| paddleocr     |                  | 检索与生成         |
+------+-------+                  +-------------------+
       |
       v
+-------------------------+
| content_list            |
| text / image / table /  |
| equation / generic      |
+-----------+-------------+
            |
            +--------------------------+
            |                          |
            v                          v
+-------------------+        +------------------------+
| 文本内容分离与入库 |        | Modal Processors       |
| insert_text_*     |        | Image / Table / Eq     |
| 调用 LightRAG     |        | ContextExtractor       |
+-------------------+        +-----------+------------+
                                            |
                                            v
                                 +------------------------+
                                 | 实体/关系构建与补充入库 |
                                 | 供后续检索使用          |
                                 +------------------------+
```

## 4. 主要文件职责

### 4.1 `raganything/raganything.py`

这是统一入口类 `RAGAnything`。

职责：

- 持有 `LightRAG`
- 持有 `llm_model_func`
- 持有 `vision_model_func`
- 持有 `embedding_func`
- 读取 `RAGAnythingConfig`
- 选择 parser
- 初始化多模态处理器
- 暴露完整 API 给上层业务使用

它本身不做重算法，核心作用是“组装”。

### 4.2 `raganything/config.py`

这是配置层。

最重要的配置有：

- `working_dir`：LightRAG 存储目录
- `parser_output_dir`：解析产物目录
- `parser`：`mineru` / `docling` / `paddleocr`
- `parse_method`：`auto` / `ocr` / `txt`
- `enable_image_processing`
- `enable_table_processing`
- `enable_equation_processing`
- `context_window`
- `context_mode`

如果后续你要做自己的功能，建议把这些配置统一收口到你自己的项目配置文件，不要在业务代码里散着传。

### 4.3 `raganything/parser.py`

这是解析器层，负责把原始文件转换成统一结构的 `content_list`。

内置三种 parser：

- `MineruParser`
- `DoclingParser`
- `PaddleOCRParser`

它们最终都要尽量输出统一结构，例如：

```python
{"type": "text", "text": "...", "page_idx": 0}
{"type": "image", "img_path": "/abs/path/a.png", "image_caption": "...", "page_idx": 1}
{"type": "table", "table_body": "...", "table_caption": "...", "page_idx": 2}
{"type": "equation", "text": "...", "page_idx": 3}
```

这个统一结构非常关键，因为后续的分流、上下文提取、模态处理都依赖它。

### 4.4 `raganything/processor.py`

这是最核心的摄入流程模块。

主要做四件事：

1. `parse_document()`：解析文档并做缓存
2. `separate_content()`：把文本和多模态内容拆开
3. `insert_text_content()`：把文本写入 LightRAG
4. `_process_multimodal_content()`：处理图片、表格、公式

真正常用的高层入口是：

- `process_document_complete()`
- `insert_content_list()`

### 4.5 `raganything/modalprocessors.py`

这是多模态处理层。

包括：

- `ImageModalProcessor`
- `TableModalProcessor`
- `EquationModalProcessor`
- `GenericModalProcessor`
- `ContextExtractor`

这里的核心思想是：

不同类型内容走不同处理器，但都支持拿到“周边上下文”，让 LLM/VLM 在处理图片、表格、公式时别瞎猜。

### 4.6 `raganything/query.py`

这是查询层。

核心方法：

- `aquery()`：纯文本查询
- `aquery_with_multimodal()`：查询时额外附带图片/表格/公式
- `aquery_vlm_enhanced()`：当命中文档里包含图片且提供了视觉模型时，把图像一起送进 VLM

### 4.7 `raganything/batch.py` 与 `raganything/batch_parser.py`

这是批处理层。

适合做：

- 批量灌库
- 文件夹级别处理
- 离线预处理任务

如果你后面做自己的产品，这块更适合作为后台 ingestion worker，而不是在线请求链路。

## 5. 核心调用链

### 5.1 文档处理调用链

这是最重要的一条链：

```text
业务代码
  -> RAGAnything(...)
  -> process_document_complete(file_path)
  -> _ensure_lightrag_initialized()
  -> parse_document(file_path)
  -> 当前 parser 解析文件
  -> 得到 content_list
  -> separate_content(content_list)
  -> 文本部分进入 LightRAG.ainsert(...)
  -> 多模态部分进入对应 ModalProcessor
  -> 多模态说明/实体/关系继续写回 LightRAG
  -> 文档处理完成
```

### 5.2 查询调用链

```text
业务代码
  -> rag.aquery(query, mode="hybrid")
  -> QueryMixin.aquery()
  -> LightRAG.aquery(...)
  -> 返回文本回答
```

### 5.3 多模态查询调用链

```text
业务代码
  -> rag.aquery_with_multimodal(query, multimodal_content=[...])
  -> QueryMixin.aquery_with_multimodal()
  -> 对输入的图片/表格/公式做描述增强
  -> 把增强后的查询交给 LightRAG
  -> 返回综合回答
```

### 5.4 直接插入内容列表调用链

```text
外部系统 / 自定义解析器
  -> 产出 content_list
  -> rag.insert_content_list(content_list, file_path=...)
  -> separate_content(content_list)
  -> 文本入库
  -> 多模态处理
  -> 后续可直接查询
```

这一条对二次开发非常有价值，因为它允许你绕开内置 parser。

## 6. 推荐的使用姿势

### 6.1 把 RAG-Anything 当引擎，不要当业务层

后面你开发自己的功能，建议这样分层：

```text
你的 API / 应用服务层
  -> 你的 DocumentService / RetrievalService
  -> RAGAnything
  -> LightRAG / Parser / LLM / VLM
```

不要把业务逻辑直接塞到 RAG-Anything 里。

正确做法是：

- 你自己封装一层应用服务
- 在那一层里调用 `RAGAnything`
- 未来你要换 parser、换向量库、换模型，都不会把业务代码搞死

### 6.2 推荐你优先使用这三个 API

1. `process_document_complete()`
2. `insert_content_list()`
3. `aquery()`

如果要做增强问答，再加：

4. `aquery_with_multimodal()`

### 6.3 两种典型接入方式

#### 方式 A：让 RAG-Anything 负责解析

适合：

- 你手里是现成的 PDF / DOCX / HTML
- 你想少写代码，先跑通链路

入口：

- `process_document_complete(file_path=...)`

#### 方式 B：你自己控制解析，只把结果交给 RAG-Anything

适合：

- 你已经有自己的文档预处理
- 你以后可能会换解析器
- 你想保留更强的可控性

入口：

- `insert_content_list(content_list=...)`

如果你们后面明确使用 `docling`，我建议前期先用方式 A 跑通，后期如果对字段质量、页码、图片抽取或表格结构有更高要求，再逐步切到方式 B。

## 7. 使用 `docling` 的正确方式

## 7.1 `docling` 适合什么

从当前源码看，`DoclingParser` 更适合：

- PDF
- Office 文档：`.doc` `.docx` `.ppt` `.pptx` `.xls` `.xlsx`
- HTML：`.html` `.htm` `.xhtml`

它的优势是：

- 对 Office / HTML 比较友好
- 文档结构保留更好
- 不需要像 MinerU 一样走另一套复杂参数

## 7.2 `docling` 不适合什么

当前 `DoclingParser` 没有实现 `parse_image()`。

这意味着：

- 你把 `config.parser` 设成 `docling`
- 然后输入一个图片文件
- `processor.py` 会先尝试 `docling.parse_image()`
- 触发 `NotImplementedError`
- 然后自动 fallback 到 `MineruParser().parse_image()`

所以如果你的业务里有大量图片文件单独入库，`docling` 不是完整方案，只能算“文档主 parser”。

## 7.3 `docling` 在当前源码中的工作方式

`DoclingParser` 不是 Python API 直调，它是通过命令行执行：

```bash
docling --output <dir> --to json --to md <input>
```

然后 RAG-Anything 再读取：

- `*.json`
- `*.md`

并把 Docling 的 JSON 结构转换成自己的 `content_list`。

也就是说，核心流程是：

```text
文件
  -> docling CLI
  -> docling 输出 json / md
  -> RAG-Anything 读取 json
  -> 转成统一 content_list
  -> 后续走标准入库流程
```

## 7.4 `docling` 的推荐初始化方式

不要依赖 README 里那种“在 `process_document_complete()` 里直接传 `parser='docling'`”的写法。

更稳的方式是：在初始化 `RAGAnythingConfig` 时就把 parser 定死。

推荐示例：

```python
import os
from raganything import RAGAnything, RAGAnythingConfig
from lightrag.utils import EmbeddingFunc
from lightrag.llm.openai import openai_complete_if_cache, openai_embed


def build_rag(api_key: str, base_url: str | None = None) -> RAGAnything:
    config = RAGAnythingConfig(
        working_dir="./rag_storage",
        parser_output_dir="./output",
        parser="docling",
        parse_method="auto",
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
        context_window=1,
        context_mode="page",
    )

    def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
        return openai_complete_if_cache(
            "gpt-4o-mini",
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    def vision_model_func(
        prompt,
        system_prompt=None,
        history_messages=None,
        image_data=None,
        messages=None,
        **kwargs,
    ):
        if messages:
            return openai_complete_if_cache(
                "gpt-4o",
                "",
                messages=messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )
        return openai_complete_if_cache(
            "gpt-4o",
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    embedding_dim = int(os.getenv("EMBEDDING_DIM", "3072"))

    embedding_func = EmbeddingFunc(
        embedding_dim=embedding_dim,
        max_token_size=8192,
        func=lambda texts: openai_embed.func(
            texts,
            model=embedding_model,
            api_key=api_key,
            base_url=base_url,
        ),
    )

    return RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func,
    )
```

### 7.5 `docling` 版最小使用示例

```python
import asyncio


async def main():
    rag = build_rag(api_key="YOUR_API_KEY")

    await rag.process_document_complete(
        file_path="./docs/sample.docx",
        output_dir="./output",
    )

    answer = await rag.aquery(
        "这份文档的核心主题是什么？",
        mode="hybrid",
    )
    print(answer)


asyncio.run(main())
```

### 7.6 如果你已有 Docling 解析结果

如果后续你自己直接调 `docling`，或者你想在 RAG-Anything 之外先加工结构化结果，那就推荐走：

- `insert_content_list()`

你需要自己构造标准内容列表，例如：

```python
content_list = [
    {"type": "text", "text": "第一章 绪论", "page_idx": 0},
    {"type": "text", "text": "这是正文内容", "page_idx": 0},
    {
        "type": "image",
        "img_path": "/abs/path/figure1.png",
        "image_caption": ["系统架构图"],
        "page_idx": 1,
    },
    {
        "type": "table",
        "table_body": "|A|B|\n|---|---|\n|1|2|",
        "table_caption": ["实验结果"],
        "page_idx": 2,
    },
]

await rag.insert_content_list(
    content_list=content_list,
    file_path="sample.docx",
)
```

这个模式最适合真正做产品，因为解析质量和字段清洗完全由你控制。

## 8. 常用 API 说明

### 8.1 `process_document_complete()`

用途：

- 最完整的文档处理入口

做的事情：

1. 初始化 LightRAG
2. 解析文档
3. 文本入库
4. 多模态处理
5. 更新状态

适合：

- 单文档入库
- 原型验证
- 后端 ingestion 任务

### 8.2 `parse_document()`

用途：

- 仅做解析和缓存

返回：

- `content_list`
- `doc_id`

适合：

- 你只想验证 parser 输出
- 你要自己决定是否入库

### 8.3 `insert_content_list()`

用途：

- 跳过解析，直接把标准化内容写进系统

适合：

- 自定义 parser
- 第三方解析服务
- 复杂清洗流程后再入库

### 8.4 `aquery()`

用途：

- 纯文本问答

常见 `mode`：

- `hybrid`
- `local`
- `global`
- `naive`
- `mix`

如果不确定，先用 `hybrid`。

### 8.5 `aquery_with_multimodal()`

用途：

- 查询时附带额外图片、表格、公式

适合：

- “请结合这张图和库里的文档一起分析”
- “把这张表和历史文档结果对比”

## 9. `docling` 相关注意事项与已知坑

### 9.1 README 示例与源码有不一致

当前仓库文档里有示例把 `parser="docling"` 当作 `process_document_complete()` 的普通参数传入。

但从源码看，真正决定 parser 的是：

- `RAGAnythingConfig(parser="docling")`
- 或环境变量 `PARSER=docling`

高层结论：

不要把“传 `parser` 参数给 `process_document_complete()`”当成可靠用法。

### 9.2 `parse_method` 对 `DoclingParser` 基本没有实际作用

`DoclingParser.parse_pdf()` 保留了 `method` 参数，但内部执行 `docling` CLI 时并没有使用这个参数。

也就是说：

- 对 MinerU 而言，`auto/ocr/txt` 有意义
- 对 Docling 而言，当前源码里这个参数基本只是接口兼容

### 9.3 `DoclingParser` 对图片文件不是完整支持

图片文件走 `docling` 会 fallback 到 MinerU。

如果你们后续系统里有下面这种需求：

- 用户直接上传 `.png/.jpg`
- 你还要求固定走 `docling`

那这条路不成立，得单独设计图片处理策略。

### 9.4 `DoclingParser` 里页码是估算值

当前 `read_from_block()` 里 `page_idx` 使用的是 `cnt // 10` 这种粗略分配方式，不是真正从原始页码精确映射过来的。

这会影响：

- 上下文抽取
- 多模态内容与页码相关的定位
- 你后面要做引用高亮或页码跳转

如果你的产品强依赖精确页码，建议后续自己接管 Docling 结果清洗。

### 9.5 `table_body` 字段质量要自己验证

`DoclingParser` 当前把表格内容直接取自 `block.get("data", [])`。

这意味着：

- 它不一定天然是 markdown 字符串
- 也不一定是最适合直接喂给下游 LLM 的格式

如果表格分析是你的重点功能，建议在入库前自己做一次标准化。

### 9.6 示例和测试文件存在过时痕迹

例如某些示例仍按老接口理解 `parse_document()` 返回值。

所以后续开发时，应该以源码签名为准，不要完全相信 README 示例。

## 10. 推荐的二次开发方案

如果你们后面是“基于这个库做自己的功能”，我建议按下面的结构做：

### 10.1 建议分三层

```text
presentation 层
  FastAPI / CLI / 定时任务

application 层
  DocumentIngestService
  DocumentQueryService
  ContentNormalizationService

infrastructure 层
  RAGAnything 封装
  模型函数封装
  文件存储
  自己的元数据存储
```

### 10.2 最先做的不是改库，而是封装库

建议你先做一个自己的适配器，例如：

```python
class RagAnythingClient:
    async def ingest_document(self, file_path: str) -> str: ...
    async def query(self, question: str) -> str: ...
    async def query_with_image(self, question: str, image_path: str) -> str: ...
    async def ingest_content_list(self, content_list: list[dict], file_path: str) -> str: ...
```

这样做的好处：

- 未来换库不至于炸业务层
- 方便加鉴权、日志、异常处理
- 方便统一接 `docling` 清洗逻辑

### 10.3 `docling` 场景下的推荐路线

第一阶段：

- 直接使用 `RAGAnything + parser=docling`
- 快速跑通 Word/PPT/HTML/PDF 的 ingest + query

第二阶段：

- 单独验证 `DoclingParser` 产出的 `content_list`
- 补齐页码、表格、标题层级等字段

第三阶段：

- 在应用层自己接 Docling
- 再通过 `insert_content_list()` 送入 RAG-Anything

这是更稳、更可控的演进路线。

## 11. 建议优先验证的场景

为了避免后面瞎忙，建议先做下面几组验证：

1. `docx` 文档解析后，标题层级和正文是否合理
2. `pptx` 文档里图片与文本是否能一起入库
3. `xlsx` 里的表格是否适合直接做问答
4. `html` 文档是否能稳定保留结构
5. 查询命中的内容里，引用路径和来源是否满足你的产品需求

## 12. 结论

对你当前这个目标来说，RAG-Anything 最适合扮演“多模态 RAG 引擎”，而不是你直接往里面加业务代码。

如果后面你们明确用 `docling`，推荐做法是：

1. 初始化阶段把 `parser` 固定为 `docling`
2. 先用 `process_document_complete()` 跑通主链路
3. 逐步评估 `content_list` 的质量
4. 一旦对字段质量有更高要求，就切到“自己调 Docling + `insert_content_list()`”的模式

这套路线最务实，后面扩展性也最好。
