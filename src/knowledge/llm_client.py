import asyncio
import os
from typing import Any, List, Optional
import numpy as np
import openai
from lightrag.utils import EmbeddingFunc


def get_llm_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.environ.get("LLM_API_KEY", ""),
        timeout=float(os.environ.get("LLM_TIMEOUT", "60.0")),
    )


def get_embedding_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        base_url=os.environ.get(
            "EMBEDDING_BASE_URL", "https://api.openai.com/v1"
        ),
        api_key=os.environ.get("EMBEDDING_API_KEY", ""),
        timeout=float(os.environ.get("EMBEDDING_TIMEOUT", "30.0")),
    )


async def unified_llm_func(
    prompt: str,
    system_prompt: Optional[str] = None,
    history_messages: Optional[List[dict]] = None,
    **kwargs: Any,
) -> str:
    """Unified LLM completion function with retry logic and extra_body injection."""
    client = get_llm_client()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    extra_body_str = os.environ.get("LLM_EXTRA_BODY_JSON", "{}")
    try:
        extra_body = eval(extra_body_str) if extra_body_str else {}
    except Exception:
        extra_body = {}

    model = os.environ.get("LLM_MODEL", "deepseek-v4.1-flash")
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "8192"))

    last_error = None
    for attempt in range(4):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body=extra_body,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            if attempt < 3:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                break
    raise RuntimeError(f"unified_llm_func failed after 4 retries: {last_error}")


async def unified_embed_func(texts: List[str]) -> np.ndarray:
    """Unified Embedding function with retry logic."""
    client = get_embedding_client()
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-v4")
    dim = int(os.environ.get("EMBEDDING_DIM", "1024"))

    last_error = None
    for attempt in range(4):
        try:
            resp = await client.embeddings.create(
                model=model,
                input=texts,
                dimensions=dim,
            )
            return np.array([item.embedding for item in resp.data])
        except Exception as e:
            last_error = e
            if attempt < 3:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                break
    raise RuntimeError(f"unified_embed_func failed after 4 retries: {last_error}")


def create_lightrag_embedding_func() -> EmbeddingFunc:
    dim = int(os.environ.get("EMBEDDING_DIM", "1024"))
    max_token_size = int(os.environ.get("EMBEDDING_MAX_TOKENS", "8192"))
    return EmbeddingFunc(
        embedding_dim=dim,
        max_token_size=max_token_size,
        func=unified_embed_func,
    )
