"""Edge-case coverage for small branch-added lines across the new KB server:
config int parsing, the auth TypeError guard, chunking-param numeric
validation, vector-DB base defaults, embedding-plugin error fallbacks, and
the plugin-discovery import-failure path.
"""

from __future__ import annotations

import sys
import types

import httpx
import pytest
from fastapi import HTTPException

from plugins.base import (
    Chunk,
    EmbeddingFunction,
    PluginParameter,
    QueryResult,
    VectorDBBackend,
)


# ---------------------------------------------------------------------------
# config._env_int
# ---------------------------------------------------------------------------


def test_env_int_invalid_returns_default(monkeypatch):
    import config

    monkeypatch.setenv("KBTEST_INT", "not-an-int")
    assert config._env_int("KBTEST_INT", 7, 1, 100) == 7


def test_env_int_clamps(monkeypatch):
    import config

    monkeypatch.setenv("KBTEST_INT", "999")
    assert config._env_int("KBTEST_INT", 7, 1, 50) == 50


# ---------------------------------------------------------------------------
# dependencies.verify_token TypeError guard
# ---------------------------------------------------------------------------


def test_verify_token_non_ascii_raises_401():
    import asyncio

    from dependencies import verify_token

    creds = types.SimpleNamespace(credentials="tök")  # non-ASCII -> hmac TypeError
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_token(creds))
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# chunking _common.validate_chunking_params numeric branches
# ---------------------------------------------------------------------------


class _FakeStrategy:
    name = "fake-strategy"

    def get_parameters(self):
        return [PluginParameter(name="size", type="int", min_value=10, max_value=100)]


def test_validate_chunking_params_numeric_branches():
    from plugins.chunking._common import validate_chunking_params

    s = _FakeStrategy()
    with pytest.raises(ValueError, match="must be numeric"):
        validate_chunking_params(s, {"size": "x"})
    with pytest.raises(ValueError, match="below the declared"):
        validate_chunking_params(s, {"size": 5})
    with pytest.raises(ValueError, match="above the declared"):
        validate_chunking_params(s, {"size": 500})
    # In-range passes.
    validate_chunking_params(s, {"size": 50})


# ---------------------------------------------------------------------------
# VectorDBBackend / LLMExtractionFunction default no-op implementations
# ---------------------------------------------------------------------------


class _BareBackend(VectorDBBackend):
    name = "bare"

    def create_collection(self, **kw):
        return "id"

    def delete_collection(self, **kw):
        return None

    def add_chunks(self, **kw):
        return 0

    def delete_by_source(self, **kw):
        return 0

    def query(self, **kw):
        return []


def test_vector_db_base_defaults_return_empty():
    be = _BareBackend()
    assert be.get_chunks_by_id(
        collection_id="c", storage_path="/x", chunk_ids=["a"], embedding_function=None
    ) == []
    assert be.get_chunks_by_source(
        collection_id="c", storage_path="/x", source_item_id="s",
        embedding_function=None,
    ) == []
    assert be.get_parameters() == []


def test_llm_extraction_get_parameters_default():
    from plugins.llm_extraction.openai import OpenAIExtraction

    # The instance method is the base default (-> []); class_parameters is separate.
    assert OpenAIExtraction(model="gpt-4o-mini").get_parameters() == []


# ---------------------------------------------------------------------------
# embedding plugin error fallbacks
# ---------------------------------------------------------------------------


def test_ollama_embedding_attribute_error_fallback(monkeypatch):
    fake = types.ModuleType("ollama")

    class FakeClient:
        def __init__(self, **kw):
            pass

        def embed(self, model, input):
            return object()  # no `.embeddings` attribute -> AttributeError

        def embeddings(self, model, prompt):
            return {"embedding": [0.1, 0.2]}

    fake.Client = FakeClient
    monkeypatch.setitem(sys.modules, "ollama", fake)

    from plugins.embedding.ollama import OllamaEmbedding

    out = OllamaEmbedding(api_endpoint="http://h:1234/api/embeddings")(["t1", "t2"])
    assert out == [[0.1, 0.2], [0.1, 0.2]]


def test_openai_embedding_connection_error_wrapped(monkeypatch):
    import openai

    class FakeOpenAI:
        def __init__(self, **kw):
            self.embeddings = self

        def create(self, model, input):
            raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)

    from plugins.embedding.openai import OpenAIEmbedding

    with pytest.raises(RuntimeError, match="cannot connect"):
        OpenAIEmbedding(model="text-embedding-3-small", api_key="k")(["t"])


# ---------------------------------------------------------------------------
# main._discover_plugins import-failure path
# ---------------------------------------------------------------------------


def test_discover_plugins_bad_package_is_swallowed():
    import main

    # A non-existent package -> import_module raises -> logged + return (no raise).
    main._discover_plugins("nonexistent_pkg_xyz_123")


# ---------------------------------------------------------------------------
# database._run_lightweight_migrations non-SQLite early return
# ---------------------------------------------------------------------------


def test_lightweight_migrations_skips_non_sqlite():
    from database.connection import _run_lightweight_migrations

    # The helper only inspects ``str(engine.url)``; a non-SQLite URL hits the
    # early return. A stub avoids needing a real Postgres driver installed.
    stub_engine = types.SimpleNamespace(url="postgresql://user:pass@localhost:5432/db")
    _run_lightweight_migrations(stub_engine)  # must return without connecting
