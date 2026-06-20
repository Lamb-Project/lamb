"""Unit tests for ``lamb.completions.rag.knowledge_store_rag``.

The module-level ``_client`` (KB Server v2 HTTP client) and ``_db`` (LAMB DB
manager) are replaced with fakes so nothing touches the network or a real
database. Covers the serialization/source-extraction helpers, the per-KS
query wrapper, and the async ``_run`` / ``rag_processor`` orchestration.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import lamb.completions.rag.knowledge_store_rag as ksr


class _FakeClient:
    def __init__(self, *, query_result=None, query_exc=None, api_key="sk-resolved"):
        self._query_result = query_result or {"results": []}
        self._query_exc = query_exc
        self._api_key = api_key
        self.query_calls = []

    def resolve_embedding_api_key(self, *, creator_user, vendor):
        return self._api_key

    async def query(self, **kwargs):
        self.query_calls.append(kwargs)
        if self._query_exc is not None:
            raise self._query_exc
        return self._query_result


class _FakeDB:
    def __init__(self, store=None):
        self._store = store

    def get_knowledge_store(self, ks_id):
        return self._store


@pytest.fixture
def patch_module(monkeypatch):
    def _apply(*, client, db):
        monkeypatch.setattr(ksr, "_client", client)
        monkeypatch.setattr(ksr, "_db", db)

    return _apply


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def test_serialize_assistant_none():
    assert ksr._serialize_assistant(None) == {}


def test_serialize_assistant_json_safe_and_fallback():
    class _Weird:
        def __init__(self):
            self.id = "a1"
            self.name = "Asst"
            self.RAG_Top_k = 3
            # Not JSON-serializable -> stringified.
            self.RAG_collections = object()

    out = ksr._serialize_assistant(_Weird())
    assert out["id"] == "a1"
    assert out["name"] == "Asst"
    assert isinstance(out["RAG_collections"], str)  # fell back to str()


def test_build_user_dict_from_owner():
    assert ksr._build_user_dict_from_owner("a@b.com") == {"email": "a@b.com"}


def test_extract_sources_full_metadata():
    results = [
        {
            "score": 0.9,
            "text": "chunk text",
            "metadata": {
                "source_title": "Doc Title",
                "source_item_id": "item-1",
                "permalink_original": "/docs/o/l/i/orig",
                "permalink_markdown": "/docs/o/l/i/md",
                "permalink_page": "/docs/o/l/i/p1",
                "library_id": "lib-1",
                "library_name": "Lib One",
            },
        }
    ]
    sources = ksr._extract_sources("ks-1", results)
    s = sources[0]
    assert s["knowledge_store_id"] == "ks-1"
    assert s["title"] == "Doc Title"
    assert s["score"] == 0.9
    assert s["library_id"] == "lib-1"
    # primary url prefers permalink_page.
    assert s["url"] == "/docs/o/l/i/p1"
    assert s["permalink_markdown"] == "/docs/o/l/i/md"


def test_extract_sources_title_fallback_and_no_permalink():
    results = [{"score": 0.1, "metadata": {}}]
    sources = ksr._extract_sources("ks-1", results)
    assert sources[0]["title"] == "Source"  # final fallback
    assert "url" not in sources[0]


# ---------------------------------------------------------------------------
# _query_one_ks
# ---------------------------------------------------------------------------


def test_query_one_ks_not_found(patch_module):
    patch_module(client=_FakeClient(), db=_FakeDB(store=None))
    out = asyncio.run(ksr._query_one_ks("ks-x", "q", 3, "owner@x.com"))
    assert out["status"] == "error"
    assert "not found" in out["error"]


def test_query_one_ks_success(patch_module):
    client = _FakeClient(query_result={"results": [{"text": "hi"}]})
    patch_module(
        client=client,
        db=_FakeDB(store={"embedding_vendor": "openai", "embedding_endpoint": ""}),
    )
    out = asyncio.run(ksr._query_one_ks("ks-1", "q", 5, "owner@x.com"))
    assert out["status"] == "success"
    assert out["data"]["results"][0]["text"] == "hi"
    assert client.query_calls[0]["top_k"] == 5


def test_query_one_ks_query_exception(patch_module):
    client = _FakeClient(query_exc=RuntimeError("boom"))
    patch_module(
        client=client,
        db=_FakeDB(store={"embedding_vendor": "ollama"}),
    )
    out = asyncio.run(ksr._query_one_ks("ks-1", "q", 3, "owner@x.com"))
    assert out["status"] == "error"
    assert "boom" in out["error"]


# ---------------------------------------------------------------------------
# _run / rag_processor
# ---------------------------------------------------------------------------


def _assistant(**over):
    base = dict(
        id="a1", name="Asst", RAG_collections="ks-1, ks-2", RAG_Top_k=4,
        owner="owner@x.com",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_run_no_assistant():
    out = asyncio.run(ksr._run([{"role": "user", "content": "q"}], None, None))
    assert "No Knowledge Stores specified" in out["context"]
    assert out["sources"] == []


def test_run_no_rag_collections():
    a = _assistant(RAG_collections="")
    out = asyncio.run(ksr._run([{"role": "user", "content": "q"}], a, None))
    assert "No Knowledge Stores specified" in out["context"]


def test_run_no_user_message():
    a = _assistant()
    out = asyncio.run(ksr._run([{"role": "system", "content": "x"}], a, None))
    assert "No user message found" in out["context"]


def test_run_collections_only_whitespace():
    a = _assistant(RAG_collections="  ,  , ")
    out = asyncio.run(ksr._run([{"role": "user", "content": "q"}], a, None))
    assert "empty or improperly formatted" in out["context"]


def test_run_success_aggregates_two_stores(patch_module):
    client = _FakeClient(
        query_result={"results": [{"text": "chunk A", "score": 0.8, "metadata": {}}]}
    )
    patch_module(
        client=client,
        db=_FakeDB(store={"embedding_vendor": "openai", "embedding_endpoint": ""}),
    )
    a = _assistant(RAG_collections="ks-1, ks-2")
    out = asyncio.run(ksr._run([{"role": "user", "content": "what is X?"}], a, None))
    # Two stores each return one chunk -> combined context + 2 sources.
    assert out["context"].count("chunk A") == 2
    assert len(out["sources"]) == 2
    assert set(out["raw_responses"]) == {"ks-1", "ks-2"}


def test_run_partial_failure(patch_module):
    # The DB returns None for the store -> _query_one_ks errors for both.
    patch_module(client=_FakeClient(), db=_FakeDB(store=None))
    a = _assistant(RAG_collections="ks-1")
    out = asyncio.run(ksr._run([{"role": "user", "content": "q"}], a, None))
    assert out["context"] == ""  # no successful chunks
    assert out["raw_responses"]["ks-1"]["status"] == "error"


def test_rag_processor_delegates_to_run(patch_module):
    client = _FakeClient(
        query_result={"results": [{"text": "hi", "metadata": {}}]}
    )
    patch_module(
        client=client,
        db=_FakeDB(store={"embedding_vendor": "openai"}),
    )
    a = _assistant(RAG_collections="ks-1")
    out = asyncio.run(
        ksr.rag_processor([{"role": "user", "content": "q"}], assistant=a)
    )
    assert "hi" in out["context"]
    assert out["assistant_data"]["id"] == "a1"
