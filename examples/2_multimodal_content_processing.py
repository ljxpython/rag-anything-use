import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from raganything.modalprocessors import ImageModalProcessor, TableModalProcessor
from src.demo_support import (
    build_lightrag,
    build_llm_model_func,
    build_vision_model_func,
    get_test_image_path,
    load_settings,
)

async def process_multimodal_content():
    settings = load_settings()
    llm_model_func = build_llm_model_func(settings)
    vision_model_func = build_vision_model_func(settings, llm_model_func)
    rag = build_lightrag("./rag_storage_multimodal")
    await rag.initialize_storages()

    image_processor = ImageModalProcessor(
        lightrag=rag,
        modal_caption_func=vision_model_func,
    )

    image_path = get_test_image_path()
    image_content = {
        "img_path": str(image_path),
        "image_caption": ["测试图片"],
        "image_footnote": ["用于验证多模态处理链路"],
    }

    image_description, image_entity_info, image_chunk_results = await image_processor.process_multimodal_content(
        modal_content=image_content,
        content_type="image",
        file_path="test_image.jpeg",
        entity_name="测试图片实体",
    )
    print("图片处理结果:\n", image_description)
    print("图片实体信息:\n", image_entity_info)
    print("图片抽取结果:\n", image_chunk_results)

    table_processor = TableModalProcessor(
        lightrag=rag,
        modal_caption_func=llm_model_func,
    )

    table_content = {
        "table_body": """
        | Method | Accuracy | F1-Score |
        |--------|----------|----------|
        | RAGAnything | 95.2% | 0.94 |
        | Baseline | 87.3% | 0.85 |
        """,
        "table_caption": ["性能对比测试表"],
        "table_footnote": ["用于验证表格处理链路"],
    }

    table_description, table_entity_info, table_chunk_results = await table_processor.process_multimodal_content(
        modal_content=table_content,
        content_type="table",
        file_path="test_table.md",
        entity_name="测试表格实体",
    )
    print("表格处理结果:\n", table_description)
    print("表格实体信息:\n", table_entity_info)
    print("表格抽取结果:\n", table_chunk_results)

    await rag.finalize_storages()

if __name__ == "__main__":
    asyncio.run(process_multimodal_content())
