import asyncio
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from src import demo_support


@pytest.mark.parametrize("invalid", [None, "dimensions", "indices", "nonfinite"])
def test_external_embedding_response(monkeypatch, invalid):
    settings = replace(
        demo_support.load_settings(),
        embedding_provider="openai",
        embedding_api_key="test-key",
        embedding_model="test-embed",
        embedding_dim=2,
    )
    rows = [
        SimpleNamespace(index=1, embedding=[3.0, 4.0]),
        SimpleNamespace(index=0, embedding=[1.0, 2.0]),
    ]
    if invalid == "dimensions":
        rows[0].embedding = [3.0]
        rows[1].embedding = [1.0]
    elif invalid == "indices":
        rows[0].index = 0
    elif invalid == "nonfinite":
        rows[0].embedding = [float("nan"), 4.0]

    class Client:
        def __init__(self, **kwargs):
            self.embeddings = self
            self.closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        async def create(self, **kwargs):
            assert kwargs == {
                "model": "test-embed",
                "input": ["first", "second"],
                "dimensions": 2,
                "encoding_format": "float",
            }
            return SimpleNamespace(data=rows)

    client = Client()
    monkeypatch.setattr(demo_support, "AsyncOpenAI", lambda **kwargs: client)
    if invalid:
        with pytest.raises(ValueError, match="invalid_embedding"):
            asyncio.run(demo_support._openai_embed(["first", "second"], settings))
    else:
        result = asyncio.run(demo_support._openai_embed(["first", "second"], settings))
        np.testing.assert_array_equal(result, [[1, 2], [3, 4]])
    assert client.closed


def test_external_embedding_requires_key():
    settings = replace(
        demo_support.load_settings(), embedding_provider="openai", embedding_api_key=""
    )
    with pytest.raises(RuntimeError, match="EMBEDDING_API_KEY"):
        demo_support.build_embedding_func(settings)
