import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.demo_support import build_raganything, get_test_image_path

async def insert_content_list_example():
    rag = build_raganything(working_dir="./rag_storage_content_list")
    image_path = get_test_image_path()

    content_list = [
        {
            "type": "text",
            "text": "这是一个通过 insert_content_list 直接插入的测试文档。",
            "page_idx": 0,
        },
        {
            "type": "image",
            "img_path": str(image_path.resolve()),
            "image_caption": ["测试图片：用于验证图片直插能力"],
            "image_footnote": ["来源：test_data"],
            "page_idx": 1,
        },
        {
            "type": "table",
            "table_body": "| Method | Accuracy | F1-Score |\n|--------|----------|----------|\n| Ours | 95.2% | 0.94 |\n| Baseline | 87.3% | 0.85 |",
            "table_caption": ["测试表格：性能对比"],
            "table_footnote": ["用于验证表格直插能力"],
            "page_idx": 2,
        },
        {
            "type": "equation",
            "latex": "P(d|q) = \\frac{P(q|d) \\cdot P(d)}{P(q)}",
            "text": "文档相关性概率公式",
            "page_idx": 3,
        },
        {
            "type": "text",
            "text": "结论：当前方法在准确率和 F1 指标上优于基线。",
            "page_idx": 4,
        },
    ]

    await rag.insert_content_list(
        content_list=content_list,
        file_path="direct_content_list_demo.pdf",
        split_by_character=None,
        split_by_character_only=False,
        doc_id=None,
        display_stats=True,
    )

    result = await rag.aquery(
        "请总结这份直插文档里的关键信息和性能指标。",
        mode="hybrid",
    )
    print("首次查询结果:\n", result)

    another_content_list = [
        {
            "type": "text",
            "text": "这是第二份通过内容列表插入的文档。",
            "page_idx": 0,
        },
        {
            "type": "table",
            "table_body": "| Feature | Value |\n|---------|-------|\n| Speed | Fast |\n| Accuracy | High |",
            "table_caption": ["第二份文档的特性对比"],
            "page_idx": 1,
        },
    ]

    await rag.insert_content_list(
        content_list=another_content_list,
        file_path="another_document.pdf",
        doc_id="custom-doc-id-123",
    )
    second_result = await rag.aquery(
        "第二份文档提到了哪些特性？",
        mode="hybrid",
    )
    print("第二次查询结果:\n", second_result)

    await rag.finalize_storages()

if __name__ == "__main__":
    asyncio.run(insert_content_list_example())
