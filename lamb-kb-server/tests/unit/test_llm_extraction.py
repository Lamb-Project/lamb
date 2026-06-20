"""Unit tests for the KG-RAG LLM-extraction backends.

Both ``OpenAIExtraction`` and ``OllamaExtraction`` lazily import their
vendor SDK inside ``chat_json``. We inject fakes via ``sys.modules`` so the
tests never touch the network, and exercise every branch:

* missing SDK (ImportError)
* missing API key (OpenAI only)
* happy path (valid JSON object)
* custom endpoint / auth header forwarding
* primary-model failure with fallback success / fallback failure / no fallback
* invalid JSON and non-dict JSON bodies

``class_parameters`` is asserted to keep the plugin-UI schema honest.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _make_openai_module(*, behaviors):
    """Return a fake ``openai`` module whose ``OpenAI`` client replays
    ``behaviors`` (a list of either a content string or an Exception) for
    successive ``chat.completions.create`` calls."""
    calls: list[dict[str, Any]] = []

    class _Message:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.message = _Message(content)

    class _Response:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            behavior = behaviors.pop(0)
            if isinstance(behavior, Exception):
                raise behavior
            return _Response(behavior)

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class FakeOpenAI:
        last_init_kwargs: dict[str, Any] = {}

        def __init__(self, **kwargs):
            FakeOpenAI.last_init_kwargs = kwargs
            self.chat = _Chat()

    mod = types.ModuleType("openai")
    mod.OpenAI = FakeOpenAI
    mod._calls = calls
    mod._FakeOpenAI = FakeOpenAI
    return mod


def _make_ollama_module(*, behaviors):
    """Fake ``ollama`` module; ``Client.chat`` replays ``behaviors`` (each a
    dict response or an Exception)."""
    calls: list[dict[str, Any]] = []

    class FakeClient:
        last_init_kwargs: dict[str, Any] = {}

        def __init__(self, **kwargs):
            FakeClient.last_init_kwargs = kwargs

        def chat(self, **kwargs):
            calls.append(kwargs)
            behavior = behaviors.pop(0)
            if isinstance(behavior, Exception):
                raise behavior
            return behavior

    mod = types.ModuleType("ollama")
    mod.Client = FakeClient
    mod._calls = calls
    mod._FakeClient = FakeClient
    return mod


@pytest.fixture
def patch_openai(monkeypatch):
    def _install(behaviors):
        mod = _make_openai_module(behaviors=list(behaviors))
        monkeypatch.setitem(sys.modules, "openai", mod)
        return mod

    return _install


@pytest.fixture
def patch_ollama(monkeypatch):
    def _install(behaviors):
        mod = _make_ollama_module(behaviors=list(behaviors))
        monkeypatch.setitem(sys.modules, "ollama", mod)
        return mod

    return _install


# ---------------------------------------------------------------------------
# OpenAIExtraction
# ---------------------------------------------------------------------------


def test_openai_missing_sdk_returns_empty(monkeypatch):
    from plugins.llm_extraction.openai import OpenAIExtraction

    # Make `from openai import OpenAI` raise ImportError.
    monkeypatch.setitem(sys.modules, "openai", None)
    out = OpenAIExtraction(api_key="sk-x").chat_json(system="s", user="u")
    assert out == {}


def test_openai_no_api_key_returns_empty(monkeypatch, patch_openai):
    monkeypatch.delenv("KG_RAG_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    patch_openai(['{"x": 1}'])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(api_key="").chat_json(system="s", user="u")
    assert out == {}


def test_openai_uses_env_key_fallback(monkeypatch, patch_openai):
    monkeypatch.delenv("KG_RAG_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    mod = patch_openai(['{"entities": []}'])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(api_key="").chat_json(system="s", user="u")
    assert out == {"entities": []}
    assert mod._FakeOpenAI.last_init_kwargs["api_key"] == "sk-env"


def test_openai_happy_path_and_endpoint(monkeypatch, patch_openai):
    mod = patch_openai(['{"entities": ["a"], "relationships": []}'])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(
        model="gpt-4o", api_key="sk-x", api_endpoint="https://proxy.example/v1/"
    ).chat_json(system="s", user="u")
    assert out == {"entities": ["a"], "relationships": []}
    # base_url is forwarded with the trailing slash stripped.
    assert mod._FakeOpenAI.last_init_kwargs["base_url"] == "https://proxy.example/v1"
    # The requested model is used.
    assert mod._calls[0]["model"] == "gpt-4o"
    assert mod._calls[0]["response_format"] == {"type": "json_object"}


def test_openai_fallback_model_success(patch_openai):
    mod = patch_openai([RuntimeError("json mode unsupported"), '{"ok": true}'])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(model="gpt-5-nano", api_key="sk-x").chat_json(
        system="s", user="u", fallback_model="gpt-4o-mini"
    )
    assert out == {"ok": True}
    assert mod._calls[0]["model"] == "gpt-5-nano"
    assert mod._calls[1]["model"] == "gpt-4o-mini"


def test_openai_fallback_model_also_fails(patch_openai):
    patch_openai([RuntimeError("boom"), RuntimeError("boom2")])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(model="m1", api_key="sk-x").chat_json(
        system="s", user="u", fallback_model="m2"
    )
    assert out == {}


def test_openai_failure_no_fallback(patch_openai):
    patch_openai([RuntimeError("boom")])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(model="m1", api_key="sk-x").chat_json(system="s", user="u")
    assert out == {}


def test_openai_failure_fallback_equals_primary(patch_openai):
    # fallback_model == primary -> treated as "no usable fallback".
    patch_openai([RuntimeError("boom")])

    from plugins.llm_extraction.openai import OpenAIExtraction

    out = OpenAIExtraction(model="m1", api_key="sk-x").chat_json(
        system="s", user="u", fallback_model="m1"
    )
    assert out == {}


def test_openai_invalid_json_returns_empty(patch_openai):
    patch_openai(["this is not json"])

    from plugins.llm_extraction.openai import OpenAIExtraction

    assert OpenAIExtraction(api_key="sk-x").chat_json(system="s", user="u") == {}


def test_openai_non_dict_json_returns_empty(patch_openai):
    patch_openai(["[1, 2, 3]"])

    from plugins.llm_extraction.openai import OpenAIExtraction

    assert OpenAIExtraction(api_key="sk-x").chat_json(system="s", user="u") == {}


def test_openai_null_content_defaults_to_empty_object(patch_openai):
    # message.content is None -> falls back to "{}".
    patch_openai([None])

    from plugins.llm_extraction.openai import OpenAIExtraction

    assert OpenAIExtraction(api_key="sk-x").chat_json(system="s", user="u") == {}


def test_openai_class_parameters():
    from plugins.llm_extraction.openai import OpenAIExtraction

    params = OpenAIExtraction.class_parameters()
    names = [p.name for p in params]
    assert "model" in names and "api_endpoint" in names


# ---------------------------------------------------------------------------
# OllamaExtraction
# ---------------------------------------------------------------------------


def test_ollama_missing_sdk_returns_empty(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)

    from plugins.llm_extraction.ollama import OllamaExtraction

    assert OllamaExtraction().chat_json(system="s", user="u") == {}


def test_ollama_happy_path_default_host(monkeypatch, patch_ollama):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    mod = patch_ollama([{"message": {"content": '{"entities": ["x"]}'}}])

    from plugins.llm_extraction.ollama import OllamaExtraction

    out = OllamaExtraction(model="qwen2.5:7b").chat_json(system="s", user="u")
    assert out == {"entities": ["x"]}
    assert mod._FakeClient.last_init_kwargs["host"] == "http://localhost:11434"
    # No auth header without an api_key.
    assert mod._FakeClient.last_init_kwargs["headers"] == {}
    assert mod._calls[0]["format"] == "json"


def test_ollama_env_host_and_auth_header(monkeypatch, patch_ollama):
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama-host:11434")
    mod = patch_ollama([{"message": {"content": "{}"}}])

    from plugins.llm_extraction.ollama import OllamaExtraction

    OllamaExtraction(api_key="secret-token").chat_json(system="s", user="u")
    # api_endpoint empty -> env host wins.
    assert mod._FakeClient.last_init_kwargs["host"] == "http://ollama-host:11434"
    assert (
        mod._FakeClient.last_init_kwargs["headers"]["Authorization"]
        == "Bearer secret-token"
    )


def test_ollama_explicit_endpoint_overrides_env(monkeypatch, patch_ollama):
    monkeypatch.setenv("OLLAMA_HOST", "http://ignored:11434")
    mod = patch_ollama([{"message": {"content": "{}"}}])

    from plugins.llm_extraction.ollama import OllamaExtraction

    OllamaExtraction(api_endpoint="http://explicit:9999").chat_json(
        system="s", user="u"
    )
    assert mod._FakeClient.last_init_kwargs["host"] == "http://explicit:9999"


def test_ollama_fallback_success(patch_ollama):
    mod = patch_ollama(
        [RuntimeError("model missing"), {"message": {"content": '{"ok": 1}'}}]
    )

    from plugins.llm_extraction.ollama import OllamaExtraction

    out = OllamaExtraction(model="llama3.1:70b").chat_json(
        system="s", user="u", fallback_model="llama3.2:3b"
    )
    assert out == {"ok": 1}
    assert mod._calls[1]["model"] == "llama3.2:3b"


def test_ollama_fallback_also_fails(patch_ollama):
    patch_ollama([RuntimeError("a"), RuntimeError("b")])

    from plugins.llm_extraction.ollama import OllamaExtraction

    assert (
        OllamaExtraction(model="m1").chat_json(
            system="s", user="u", fallback_model="m2"
        )
        == {}
    )


def test_ollama_failure_no_fallback(patch_ollama):
    patch_ollama([RuntimeError("boom")])

    from plugins.llm_extraction.ollama import OllamaExtraction

    assert OllamaExtraction(model="m1").chat_json(system="s", user="u") == {}


def test_ollama_invalid_json(patch_ollama):
    patch_ollama([{"message": {"content": "not json"}}])

    from plugins.llm_extraction.ollama import OllamaExtraction

    assert OllamaExtraction().chat_json(system="s", user="u") == {}


def test_ollama_non_dict_json(patch_ollama):
    patch_ollama([{"message": {"content": "[1,2]"}}])

    from plugins.llm_extraction.ollama import OllamaExtraction

    assert OllamaExtraction().chat_json(system="s", user="u") == {}


def test_ollama_missing_message_defaults(patch_ollama):
    # response without "message" -> .get(...) default "{}" -> empty dict.
    patch_ollama([{}])

    from plugins.llm_extraction.ollama import OllamaExtraction

    assert OllamaExtraction().chat_json(system="s", user="u") == {}


def test_ollama_class_parameters():
    from plugins.llm_extraction.ollama import OllamaExtraction

    names = [p.name for p in OllamaExtraction.class_parameters()]
    assert "model" in names and "api_endpoint" in names
