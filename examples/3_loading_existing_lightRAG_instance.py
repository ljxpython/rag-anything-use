import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from raganything import RAGAnything
from lightrag import LightRAG
from lightrag.kg.shared_storage import initialize_pipeline_status
import os

from src.demo_support import (
    build_embedding_func,
    build_llm_model_func,
    build_rag_config,
    build_vision_model_func,
    get_test_document_path,
    load_settings,
)

async def load_existing_lightrag():
    settings = load_settings()
    llm_model_func = build_llm_model_func(settings)
    embedding_func = build_embedding_func(settings)

    lightrag_working_dir = "./existing_lightrag_storage"

    if os.path.exists(lightrag_working_dir) and os.listdir(lightrag_working_dir):
        print("✅ Found existing LightRAG instance, loading...")
    else:
        print("❌ No existing LightRAG instance found, will create new one")

    lightrag_instance = LightRAG(
        working_dir=lightrag_working_dir,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
    )

    await lightrag_instance.initialize_storages()
    await initialize_pipeline_status()

    vision_model_func = build_vision_model_func(settings, llm_model_func)

    rag = RAGAnything(
        lightrag=lightrag_instance,
        vision_model_func=vision_model_func,
        config=build_rag_config(settings, working_dir=lightrag_working_dir),
    )

    result = await rag.aquery(
        "这个 LightRAG 实例里目前有什么内容？",
        mode="hybrid",
    )
    print("首次查询结果:\n", result)

    await rag.process_document_complete(
        file_path=str(get_test_document_path()),
        output_dir="./output",
    )
    result_after_insert = await rag.aquery(
        "请总结新加入文档的内容。",
        mode="hybrid",
    )
    print("追加文档后的查询结果:\n", result_after_insert)

    await rag.finalize_storages()

if __name__ == "__main__":
    asyncio.run(load_existing_lightrag())
