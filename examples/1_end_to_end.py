import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.demo_support import build_raganything, get_test_document_path

async def main():
    rag = build_raganything()
    document_path = get_test_document_path()
    print(f"开始处理文档: {document_path}")

    await rag.process_document_complete(
        file_path=str(document_path),
        output_dir="./output",
        parse_method="auto",
    )

    text_result = await rag.aquery(
        "请总结这份文档的核心主题，并列出其中最重要的3个信息点。",
        mode="hybrid",
    )
    print("文本查询结果:\n", text_result)

    multimodal_result = await rag.aquery_with_multimodal(
        "请结合这个公式风格的内容，说明文档里是否涉及概率、评分或推断相关概念。",
        multimodal_content=[
            {
                "type": "equation",
                "latex": "P(d|q) = \\frac{P(q|d) \\cdot P(d)}{P(q)}",
                "equation_caption": "Document relevance probability",
            }
        ],
        mode="hybrid",
    )
    print("多模态查询结果:\n", multimodal_result)

    await rag.finalize_storages()

if __name__ == "__main__":
    asyncio.run(main())
