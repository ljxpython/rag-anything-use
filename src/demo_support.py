from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from contextvars import ContextVar
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib import request

import numpy as np
import httpx
from dotenv import load_dotenv
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache
from openai import AsyncOpenAI
from lightrag.utils import EmbeddingFunc

if TYPE_CHECKING:
    from raganything import RAGAnything, RAGAnythingConfig

import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)
_MULTIMODAL_WORKSPACE = ContextVar("knowledge_multimodal_workspace", default=None)


@dataclass(frozen=True)
class DemoSettings:
    parser: str
    parse_method: str
    working_dir: str
    output_dir: str
    test_document_path: str
    test_image_path: str
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    llm_max_tokens: int
    vision_base_url: str
    vision_model: str
    vision_api_key: str
    vision_max_tokens: int
    embedding_base_url: str
    embedding_model: str
    embedding_dim: int
    embedding_max_tokens: int
    embedding_provider: str = "ollama"
    embedding_api_key: str = ""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少必需环境变量: {name}")
    return value


def load_settings() -> DemoSettings:
    return DemoSettings(
        parser=os.getenv("PARSER", "docling"),
        parse_method=os.getenv("PARSE_METHOD", "auto"),
        working_dir=os.getenv("WORKING_DIR", "./rag_storage"),
        output_dir=os.getenv("OUTPUT_DIR", "./output"),
        test_document_path=os.getenv("TEST_DOCUMENT_PATH", ""),
        test_image_path=os.getenv("TEST_IMAGE_PATH", ""),
        llm_base_url=_require_env("LLM_BASE_URL"),
        llm_model=_require_env("LLM_MODEL"),
        llm_api_key=_require_env("LLM_API_KEY"),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        vision_base_url=os.getenv("VISION_BASE_URL", ""),
        vision_model=os.getenv("VISION_MODEL", ""),
        vision_api_key=os.getenv("VISION_API_KEY", ""),
        vision_max_tokens=int(os.getenv("VISION_MAX_TOKENS", "2048")),
        embedding_base_url=_require_env("EMBEDDING_BASE_URL"),
        embedding_model=_require_env("EMBEDDING_MODEL"),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "768")),
        embedding_max_tokens=int(os.getenv("EMBEDDING_MAX_TOKENS", "8192")),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "ollama"),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
    )


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def get_test_document_path() -> Path:
    path = _resolve_path(_require_env("TEST_DOCUMENT_PATH"))
    if not path.exists():
        raise FileNotFoundError(f"测试文档不存在: {path}")
    return path


def get_test_image_path() -> Path:
    path = _resolve_path(_require_env("TEST_IMAGE_PATH"))
    if not path.exists():
        raise FileNotFoundError(f"测试图片不存在: {path}")
    return path


def build_llm_model_func(settings: DemoSettings, *, usage=None):
    extra_body = json.loads(os.getenv("LLM_EXTRA_BODY_JSON", "{}"))
    if not isinstance(extra_body, dict):
        raise TypeError("invalid_llm_extra_body")

    def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        if usage is not None:
            kind = "graph_extraction" if system_prompt else "affected_graph_merge"

            async def measured():
                from tenacity import (
                    AsyncRetrying,
                    retry_if_exception_type,
                    stop_after_attempt,
                    wait_exponential,
                )
                from openai import APIConnectionError, APITimeoutError, RateLimitError
                from lightrag.llm.openai import InvalidResponseError

                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(min=4, max=10),
                    retry=retry_if_exception_type(
                        (
                            APIConnectionError,
                            APITimeoutError,
                            RateLimitError,
                            InvalidResponseError,
                        )
                    ),
                    reraise=True,
                ):
                    with attempt:
                        async with httpx.AsyncClient(
                            transport=UsageTransport(usage, kind)
                        ) as client:
                            # The upstream helper closes its supplied HTTP client each attempt.
                            return await openai_complete_if_cache.__wrapped__(
                                settings.llm_model,
                                prompt,
                                system_prompt=system_prompt,
                                history_messages=history_messages or [],
                                api_key=settings.llm_api_key,
                                base_url=settings.llm_base_url,
                                max_tokens=kwargs.get(
                                    "max_tokens", settings.llm_max_tokens
                                ),
                                extra_body=kwargs.get("extra_body", extra_body),
                                openai_client_configs={
                                    "http_client": client,
                                    "max_retries": 0,
                                },
                                **{
                                    key: value
                                    for key, value in kwargs.items()
                                    if key not in {"max_tokens", "extra_body"}
                                },
                            )

            return measured()
        return openai_complete_if_cache(
            settings.llm_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            max_tokens=kwargs.pop("max_tokens", settings.llm_max_tokens),
            extra_body=kwargs.pop("extra_body", extra_body),
            **kwargs,
        )

    return llm_model_func


def build_vision_model_func(settings: DemoSettings, llm_model_func):
    def vision_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        image_data: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        if messages:
            return openai_complete_if_cache(
                settings.vision_model,
                "",
                system_prompt=None,
                history_messages=[],
                messages=messages,
                api_key=settings.vision_api_key,
                base_url=settings.vision_base_url,
                max_tokens=kwargs.pop("max_tokens", settings.vision_max_tokens),
                **kwargs,
            )

        if image_data:
            multimodal_messages = [
                {"role": "system", "content": system_prompt} if system_prompt else None,
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                },
            ]
            return openai_complete_if_cache(
                settings.vision_model,
                "",
                system_prompt=None,
                history_messages=[],
                messages=[item for item in multimodal_messages if item is not None],
                api_key=settings.vision_api_key,
                base_url=settings.vision_base_url,
                max_tokens=kwargs.pop("max_tokens", settings.vision_max_tokens),
                **kwargs,
            )

        return llm_model_func(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            **kwargs,
        )

    return vision_model_func


def _ollama_embed_sync(texts: list[str], settings: DemoSettings) -> np.ndarray:
    payload = json.dumps(
        {
            "model": settings.embedding_model,
            "input": texts,
        }
    ).encode("utf-8")
    req = request.Request(
        f"{settings.embedding_base_url.rstrip('/')}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=60) as response:
        data = json.load(response)
    vectors = np.array(data["embeddings"], dtype=np.float32)
    if (
        vectors.shape != (len(texts), settings.embedding_dim)
        or not np.isfinite(vectors).all()
    ):
        raise ValueError("invalid_embedding_dimensions")
    return vectors


async def _ollama_embed(texts: list[str], settings: DemoSettings) -> np.ndarray:
    return await asyncio.to_thread(_ollama_embed_sync, texts, settings)


async def _openai_embed(
    texts: list[str], settings: DemoSettings, *, usage=None
) -> np.ndarray:
    async with AsyncOpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        timeout=60,
        max_retries=0,
        **(
            {
                "http_client": httpx.AsyncClient(
                    transport=UsageTransport(usage, "embedding")
                )
            }
            if usage is not None
            else {}
        ),
    ) as client:
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
            dimensions=settings.embedding_dim,
            encoding_format="float",
        )
    items = sorted(response.data, key=lambda item: item.index)
    if [item.index for item in items] != list(range(len(texts))):
        raise ValueError("invalid_embedding_indices")
    vectors = np.array([item.embedding for item in items], dtype=np.float32)
    if (
        vectors.shape != (len(texts), settings.embedding_dim)
        or not np.isfinite(vectors).all()
    ):
        raise ValueError("invalid_embedding_dimensions")
    return vectors


def build_embedding_func(settings: DemoSettings, *, usage=None) -> EmbeddingFunc:
    if settings.embedding_provider == "ollama":
        embed = _ollama_embed
    elif settings.embedding_provider == "openai":
        if not settings.embedding_api_key.strip():
            raise RuntimeError("缺少必需环境变量: EMBEDDING_API_KEY")
        embed = _openai_embed
    else:
        raise ValueError("invalid_embedding_provider")

    async def measured_embed(texts):
        if usage is None:
            return await embed(texts, settings)
        if embed is _openai_embed:
            return await embed(texts, settings, usage=usage)
        row = usage.begin("embedding", len(texts), stage=usage.embedding_stage(texts))
        try:
            result = await embed(texts, settings)
            usage.finish(row)
            return result
        except BaseException:
            usage.finish(row, status="unknown")
            raise

    return EmbeddingFunc(
        embedding_dim=settings.embedding_dim,
        max_token_size=settings.embedding_max_tokens,
        func=measured_embed,
    )


def build_rag_config(
    settings: DemoSettings, working_dir: str | None = None
) -> RAGAnythingConfig:
    from raganything import RAGAnythingConfig

    return RAGAnythingConfig(
        working_dir=working_dir or settings.working_dir,
        parser_output_dir=settings.output_dir,
        parser=settings.parser,
        parse_method=settings.parse_method,
        enable_image_processing=_parse_bool_env_alias(
            "ENABLE_IMAGE_PROCESSING",
            "KNOWLEDGE_ENABLE_IMAGE_PROCESSING",
            True,
        ),
        enable_table_processing=_parse_bool_env_alias(
            "ENABLE_TABLE_PROCESSING",
            "KNOWLEDGE_ENABLE_TABLE_PROCESSING",
            True,
        ),
        enable_equation_processing=_parse_bool_env_alias(
            "ENABLE_EQUATION_PROCESSING",
            "KNOWLEDGE_ENABLE_EQUATION_PROCESSING",
            True,
        ),
    )


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_bool_env_alias(primary: str, fallback: str, default: bool) -> bool:
    primary_value = os.getenv(primary)
    if primary_value is not None:
        return _parse_bool_env(primary, default)
    return _parse_bool_env(fallback, default)


def build_raganything(
    working_dir: str | None = None,
    *,
    lightrag: LightRAG | None = None,
    parser_name: str | None = None,
    parse_method: str | None = None,
    parser_output_dir: str | None = None,
    enable_image_processing: bool | None = None,
    enable_table_processing: bool | None = None,
    enable_equation_processing: bool | None = None,
) -> RAGAnything:
    from raganything import RAGAnything
    from raganything import modalprocessors
    from lightrag.kg import shared_storage

    # shortcut: private hooks target RAG-Anything 1.4.2/LightRAG 1.4.12; reverify on upgrade.
    if not getattr(shared_storage.get_namespace_data, "_knowledge_workspace", False):
        namespace_data = shared_storage.get_namespace_data
        pipeline_lock = shared_storage.get_pipeline_status_lock

        async def scoped_data(namespace, first_init=False, workspace=None):
            return await namespace_data(
                namespace,
                first_init=first_init,
                workspace=workspace
                if workspace is not None
                else _MULTIMODAL_WORKSPACE.get(),
            )

        def scoped_lock(enable_logging=False, workspace=None):
            return pipeline_lock(
                enable_logging=enable_logging,
                workspace=workspace
                if workspace is not None
                else _MULTIMODAL_WORKSPACE.get(),
            )

        # Upstream multimodal paths omit workspace; resolve it per task, not globally.
        scoped_data._knowledge_workspace = True
        shared_storage.get_namespace_data = scoped_data
        shared_storage.get_pipeline_status_lock = scoped_lock
        modalprocessors.get_namespace_data = scoped_data
        modalprocessors.get_pipeline_status_lock = scoped_lock

    asset_keys = ("img_path", "image_path", "table_img_path")
    asset_paths = ContextVar("knowledge_asset_paths", default=())

    def hide_paths(content, extra=()):
        for path in (*asset_paths.get(), *extra):
            if isinstance(path, str) and path:
                content = content.replace(
                    path, "asset:" + hashlib.sha256(path.encode()).hexdigest()[:24]
                )
        return content

    class KnowledgeRAGAnything(RAGAnything):
        async def parse_document(self, *args, **kwargs):
            # Parsing must start after its cache exists, including the first document.
            initialized = await self._ensure_lightrag_initialized()
            if not initialized.get("success"):
                raise RuntimeError("knowledge_parser_initialization_failed")
            return await super().parse_document(*args, **kwargs)

        async def _process_multimodal_content(self, multimodal_items, *args, **kwargs):
            initialized = await self._ensure_lightrag_initialized()
            if not initialized.get("success"):
                raise RuntimeError("knowledge_multimodal_initialization_failed")
            token = asset_paths.set(
                tuple(item.get(key) for item in multimodal_items for key in asset_keys)
            )
            workspace_token = _MULTIMODAL_WORKSPACE.set(self.lightrag.workspace)
            try:
                return await super()._process_multimodal_content(
                    multimodal_items, *args, **kwargs
                )
            finally:
                _MULTIMODAL_WORKSPACE.reset(workspace_token)
                asset_paths.reset(token)

        def _initialize_processors(self):
            super()._initialize_processors()
            # Individual fallback bypasses the batch template; scrub before it hashes/stores.
            for processor in self.modal_processors.values():
                original = processor._create_entity_and_chunk

                async def create(modal_chunk, *args, _create=original, **kwargs):
                    return await _create(hide_paths(modal_chunk), *args, **kwargs)

                processor._create_entity_and_chunk = create

        def _apply_chunk_template(self, content_type, original_item, description):
            # Parser assets are local inputs, not filesystem locators for MCP consumers.
            return hide_paths(
                super()._apply_chunk_template(content_type, original_item, description),
                tuple(original_item.get(key) for key in asset_keys),
            )

        def _convert_to_lightrag_chunks_type_aware(
            self, multimodal_data_list, *args, **kwargs
        ):
            # Upstream uses page zero for context lookup; stored provenance must remain unknown.
            for data in multimodal_data_list:
                data["item_info"]["page_idx"] = data["original_item"].get("page_idx")
            return super()._convert_to_lightrag_chunks_type_aware(
                multimodal_data_list, *args, **kwargs
            )

    settings = load_settings()
    llm_model_func = build_llm_model_func(settings)
    vision_model_func = build_vision_model_func(settings, llm_model_func)
    embedding_func = build_embedding_func(settings)
    config = build_rag_config(settings, working_dir=working_dir)
    if parser_name is not None:
        config.parser = parser_name
    if parse_method is not None:
        config.parse_method = parse_method
    if parser_output_dir is not None:
        config.parser_output_dir = parser_output_dir
    if enable_image_processing is not None:
        config.enable_image_processing = enable_image_processing
    if enable_table_processing is not None:
        config.enable_table_processing = enable_table_processing
    if enable_equation_processing is not None:
        config.enable_equation_processing = enable_equation_processing
    if any(
        (
            config.enable_image_processing,
            config.enable_table_processing,
            config.enable_equation_processing,
        )
    ) and not all(
        (settings.vision_base_url, settings.vision_model, settings.vision_api_key)
    ):
        raise RuntimeError("vision_configuration_required")
    rag = KnowledgeRAGAnything(
        lightrag=lightrag,
        config=config,
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func,
    )
    if config.parser == "docling":
        from src.knowledge.parser_adapter import build_docling_parser

        rag.doc_parser = build_docling_parser()
    return rag


def build_lightrag(working_dir: str, *, workspace: str = "", usage=None) -> LightRAG:
    settings = load_settings()
    llm_model_func = build_llm_model_func(settings, usage=usage)
    embedding_func = build_embedding_func(settings, usage=usage)
    return LightRAG(
        working_dir=working_dir,
        workspace=workspace,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
    )


class UsageTransport(httpx.AsyncBaseTransport):
    def __init__(self, usage, kind):
        self.usage, self.kind = usage, kind
        self.inner = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        body = json.loads(request.content)
        inputs = body.get("input", [])
        if not isinstance(inputs, list):
            inputs = [inputs]
        stage = self.usage.embedding_stage(inputs) if self.kind == "embedding" else None
        row = self.usage.begin(self.kind, len(inputs), stage=stage)
        try:
            response = await self.inner.handle_async_request(request)
            await response.aread()
            payload = response.json()
            self.usage.finish(
                row,
                payload.get("usage"),
                status="complete" if response.is_success else "failed",
            )
            return response
        except BaseException:
            self.usage.finish(row, status="unknown")
            raise

    async def aclose(self):
        await self.inner.aclose()


def encode_image_file(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def create_demo_image_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    return f"data:image/{suffix};base64,{encode_image_file(image_path)}"


def create_tiny_png_base64() -> str:
    from PIL import Image

    image = Image.new("RGB", (32, 32), color=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
