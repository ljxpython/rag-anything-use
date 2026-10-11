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
