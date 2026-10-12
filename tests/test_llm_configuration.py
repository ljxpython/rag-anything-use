from unittest.mock import Mock

import pytest

from src import demo_support


def test_provider_extra_body_is_forwarded_for_structured_extraction(
    published_config, monkeypatch
):
    monkeypatch.setenv("LLM_EXTRA_BODY_JSON", '{"thinking":{"type":"disabled"}}')
    provider = Mock(return_value="result")
    monkeypatch.setattr(demo_support, "openai_complete_if_cache", provider)
    invoke = demo_support.build_llm_model_func(demo_support.load_settings())
    assert invoke("extract") == "result"
    assert provider.call_args.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    invoke("override", extra_body={"other": True})
    assert provider.call_args.kwargs["extra_body"] == {"other": True}
    monkeypatch.setenv("LLM_EXTRA_BODY_JSON", "[]")
    with pytest.raises(TypeError, match="invalid_llm_extra_body"):
        demo_support.build_llm_model_func(demo_support.load_settings())


def test_measured_llm_retry_creates_fresh_client_and_counts_each_http(
    published_config, monkeypatch
):
    import asyncio
    import httpx
    from tenacity import wait_none
    import lightrag.llm.openai as provider_module

    attempts, clients = [], []

    class Recorder:
        stage = "indexing"

        def begin(self, *args, **kwargs):
            attempts.append(args)
            return len(attempts)

        def finish(self, *args, **kwargs):
            pass

    calls = 0

    async def provider(model, prompt, **kwargs):
        nonlocal calls
        calls += 1
        client = kwargs["openai_client_configs"]["http_client"]
        clients.append(client)
        assert not client.is_closed

        async def response(request):
            return httpx.Response(200, json={"usage": {"prompt_tokens": 3}})

        client._transport.inner = httpx.MockTransport(response)
        await client.post("http://provider/chat/completions", json={"messages": []})
        await client.aclose()
        if calls == 1:
            raise provider_module.InvalidResponseError("empty")
        return "result"

    monkeypatch.setattr(
        provider_module.openai_complete_if_cache, "__wrapped__", provider
    )
    import tenacity

    original = tenacity.AsyncRetrying
    monkeypatch.setattr(
        tenacity,
        "AsyncRetrying",
        lambda **kwargs: original(**{**kwargs, "wait": wait_none()}),
    )
    result = asyncio.run(
        demo_support.build_llm_model_func(
            demo_support.load_settings(), usage=Recorder()
        )("extract", system_prompt="schema")
    )
    assert result == "result" and len(attempts) == 2
    assert clients[0] is not clients[1] and all(client.is_closed for client in clients)
