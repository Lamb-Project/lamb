"""Unit tests for ``plugins.kg_rag_query.KGRAGQueryPlugin`` active paths.

The graceful-degradation no-ops (disabled / not-opted-in / no-seed) are
covered in ``test_kg_rag.py``. Here we drive the *active* augmentation path
with a fake graph store + fake vector backend, plus the static helpers
(``_as_bool``, ``_result_chunk_id``, ``_rrf_merge``, ``_attach_trace``,
``_fetch_expanded_results``) and the LLM-based question-entity extractor.
"""

from __future__ import annotations

import types

import pytest

import config as config_module
import services.graph_store as gs_module
from plugins.kg_rag_query import KGRAGQueryPlugin


class _Collection:
    def __init__(self, **over):
        self.id = "col-1"
        self.organization_id = "org-1"
        self.graph_enabled = True
        self.backend_collection_id = "backend-col"
        self.storage_path = "/tmp/store"
        self.extraction_vendor = None
        self.extraction_model = None
        self.extraction_endpoint = None
        self.__dict__.update(over)


class _FakeItem:
    def __init__(self, text, score, metadata):
        self.text = text
        self.score = score
        self.metadata = metadata


class _FakeBackend:
    def __init__(self, *, items=None, raises=False):
        self._items = items or []
        self._raises = raises
        self.calls = []

    def get_chunks_by_id(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("backend boom")
        return self._items


class _FakeGraphStore:
    def __init__(self, *, configured=True, expansion=None, raises=False):
        self._configured = configured
        self._expansion = expansion or {}
        self._raises = raises

    def is_configured(self):
        return self._configured

    def expand_from_concept_names(self, **kwargs):
        if self._raises:
            raise RuntimeError("expand boom")
        return self._expansion


# ---------------------------------------------------------------------------
# static helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        (None, False),
        ("yes", True),
        ("ON", True),
        ("enabled", True),
        ("0", False),
        ("nope", False),
    ],
)
def test_as_bool(value, expected):
    assert KGRAGQueryPlugin._as_bool(value) is expected


def test_result_chunk_id_precedence():
    assert KGRAGQueryPlugin._result_chunk_id(
        {"metadata": {"document_id": "d", "chunk_id": "c"}}
    ) == "d"
    assert KGRAGQueryPlugin._result_chunk_id(
        {"metadata": {"child_chunk_id": "cc", "chunk_id": "c"}}
    ) == "cc"
    assert KGRAGQueryPlugin._result_chunk_id({"metadata": {"chunk_id": "c"}}) == "c"
    assert KGRAGQueryPlugin._result_chunk_id({"metadata": {}}) is None
    assert KGRAGQueryPlugin._result_chunk_id({}) is None


def test_attach_trace_toggle():
    results = [{"data": "x", "metadata": {"a": 1}}]
    trace = {"mode": "kg_rag"}
    # include_trace False -> unchanged objects.
    assert KGRAGQueryPlugin._attach_trace(results, trace, False) is results
    traced = KGRAGQueryPlugin._attach_trace(results, trace, True)
    assert traced[0]["metadata"]["kg_rag"] == trace
    assert traced[0]["metadata"]["a"] == 1


def test_rrf_merge_fuses_and_boosts_overlap():
    plugin = KGRAGQueryPlugin()
    baseline = [
        {"similarity": 0.9, "data": "A", "metadata": {"chunk_id": "a"}},
        {"similarity": 0.8, "data": "B", "metadata": {"chunk_id": "b"}},
    ]
    expanded = [
        {"similarity": 0.7, "data": "A", "metadata": {"chunk_id": "a"}},  # overlap
        {"similarity": 0.6, "data": "C", "metadata": {"chunk_id": "c"}},
    ]
    merged = plugin._rrf_merge(
        baseline_results=baseline, expanded_results=expanded, top_k=5
    )
    by_id = {KGRAGQueryPlugin._result_chunk_id(m): m for m in merged}
    # "a" appears in both lists -> fusion_lists has both.
    assert by_id["a"]["fusion_lists"] == ["baseline", "graph"]
    assert "rrf_score" in by_id["a"]
    # Overlapping "a" should outrank single-list entries.
    assert merged[0]["metadata"]["chunk_id"] == "a"


def test_fetch_expanded_results_empty_ids():
    plugin = KGRAGQueryPlugin()
    out = plugin._fetch_expanded_results(
        backend=_FakeBackend(), collection=_Collection(),
        embedding_function=None, expanded_ids=[], return_parent_context=True,
    )
    assert out == []


def test_fetch_expanded_results_backend_error_returns_empty():
    plugin = KGRAGQueryPlugin()
    out = plugin._fetch_expanded_results(
        backend=_FakeBackend(raises=True), collection=_Collection(),
        embedding_function=None, expanded_ids=["c1"], return_parent_context=True,
    )
    assert out == []


def test_fetch_expanded_results_with_parent_context():
    items = [
        _FakeItem("child text", 0.5, {"parent_text": "PARENT", "chunk_id": "c1"}),
        _FakeItem("only child", None, {"chunk_id": "c2"}),
    ]
    plugin = KGRAGQueryPlugin()
    out = plugin._fetch_expanded_results(
        backend=_FakeBackend(items=items), collection=_Collection(),
        embedding_function=None, expanded_ids=["c1", "c2"],
        return_parent_context=True,
    )
    # First item uses parent_text as data; origin tag added; parent_text popped.
    assert out[0]["data"] == "PARENT"
    assert out[0]["metadata"]["kg_rag_origin"] == "graph_expansion"
    assert "parent_text" not in out[0]["metadata"]
    # Second item had no score -> default 0.72; data falls back to text.
    assert out[1]["similarity"] == 0.72
    assert out[1]["data"] == "only child"


def test_fetch_expanded_results_without_parent_context():
    items = [_FakeItem("child", 0.5, {"parent_text": "PARENT", "chunk_id": "c1"})]
    plugin = KGRAGQueryPlugin()
    out = plugin._fetch_expanded_results(
        backend=_FakeBackend(items=items), collection=_Collection(),
        embedding_function=None, expanded_ids=["c1"],
        return_parent_context=False,
    )
    # data uses the child text (parent context not requested).
    assert out[0]["data"] == "child"


# ---------------------------------------------------------------------------
# augment active path
# ---------------------------------------------------------------------------


def _baseline():
    return [{"similarity": 0.9, "data": "seed", "metadata": {"document_id": "seed-1"}}]


def test_augment_neo4j_not_configured(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config", lambda: {"enabled": True, "graph_depth": 2}
    )
    monkeypatch.setattr(
        gs_module, "get_graph_store", lambda: _FakeGraphStore(configured=False)
    )
    out = KGRAGQueryPlugin().augment(
        db=None, collection=_Collection(), backend=_FakeBackend(),
        embedding_function=None, query_text="q", baseline_results=_baseline(),
        params={},
    )
    trace = out[0]["metadata"]["kg_rag"]
    assert any("Neo4j is not configured" in w for w in trace["warnings"])


def test_augment_full_path_merges_expansion(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config", lambda: {"enabled": True, "graph_depth": 2}
    )
    expansion = {
        "entry_concepts": ["alpha"],
        "expanded_chunk_ids": ["exp-1"],
        "graph_latency_ms": 12.0,
    }
    monkeypatch.setattr(
        gs_module, "get_graph_store", lambda: _FakeGraphStore(expansion=expansion)
    )
    monkeypatch.setattr(
        KGRAGQueryPlugin, "_extract_question_entities",
        classmethod(lambda cls, q, c: ["alpha"]),
    )
    backend = _FakeBackend(
        items=[_FakeItem("expanded text", 0.6, {"chunk_id": "exp-1"})]
    )
    out = KGRAGQueryPlugin().augment(
        db=None, collection=_Collection(), backend=backend,
        embedding_function=None, query_text="what is alpha?",
        baseline_results=_baseline(), params={"top_k": 5},
    )
    trace = out[0]["metadata"]["kg_rag"]
    assert trace["graph_expanded"] is True
    assert trace["entry_concepts"] == ["alpha"]
    assert trace["expanded_chunk_ids"] == ["exp-1"]
    # Both seed and expanded chunks present in the merged output.
    ids = {KGRAGQueryPlugin._result_chunk_id(r) for r in out}
    assert "seed-1" in ids and "exp-1" in ids


def test_augment_expansion_failure_adds_warning(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config", lambda: {"enabled": True, "graph_depth": 2}
    )
    monkeypatch.setattr(
        gs_module, "get_graph_store", lambda: _FakeGraphStore(raises=True)
    )
    monkeypatch.setattr(
        KGRAGQueryPlugin, "_extract_question_entities",
        classmethod(lambda cls, q, c: ["alpha"]),
    )
    out = KGRAGQueryPlugin().augment(
        db=None, collection=_Collection(), backend=_FakeBackend(),
        embedding_function=None, query_text="q", baseline_results=_baseline(),
        params={},
    )
    trace = out[0]["metadata"]["kg_rag"]
    assert any("Graph expansion failed" in w for w in trace["warnings"])


def test_augment_no_expanded_chunks_warns(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config", lambda: {"enabled": True, "graph_depth": 2}
    )
    monkeypatch.setattr(
        gs_module, "get_graph_store",
        lambda: _FakeGraphStore(expansion={"entry_concepts": [], "expanded_chunk_ids": []}),
    )
    monkeypatch.setattr(
        KGRAGQueryPlugin, "_extract_question_entities",
        classmethod(lambda cls, q, c: []),
    )
    out = KGRAGQueryPlugin().augment(
        db=None, collection=_Collection(), backend=_FakeBackend(),
        embedding_function=None, query_text="q", baseline_results=_baseline(),
        params={},
    )
    trace = out[0]["metadata"]["kg_rag"]
    assert any("Graph returned no additional chunks" in w for w in trace["warnings"])


# ---------------------------------------------------------------------------
# _extract_question_entities (LLM-based)
# ---------------------------------------------------------------------------


class _FakeExtractionBackend:
    def __init__(self, payload):
        self._payload = payload

    def chat_json(self, *, system, user, fallback_model=None):
        return self._payload


@pytest.fixture(autouse=True)
def _clear_question_cache():
    KGRAGQueryPlugin._question_cache.clear()
    yield
    KGRAGQueryPlugin._question_cache.clear()


def test_extract_entities_empty_question():
    assert KGRAGQueryPlugin._extract_question_entities("   ", _Collection()) == []


def test_extract_entities_openai_no_key(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"openai_api_key": "", "chat_model": "gpt-4o-mini"},
    )
    assert KGRAGQueryPlugin._extract_question_entities("q", _Collection()) == []


def test_extract_entities_success_and_cache(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"openai_api_key": "sk-x", "chat_model": "gpt-4o-mini"},
    )
    import plugins.base as base_module

    built = {"count": 0}

    def fake_build(vendor, **kwargs):
        built["count"] += 1
        return _FakeExtractionBackend({"entities": ["alpha", " beta ", ""]})

    monkeypatch.setattr(base_module.LLMExtractionRegistry, "build", fake_build)
    out = KGRAGQueryPlugin._extract_question_entities("what is alpha?", _Collection())
    assert out == ["alpha", "beta"]
    # Second identical call is served from cache (build not called again).
    out2 = KGRAGQueryPlugin._extract_question_entities("what is alpha?", _Collection())
    assert out2 == ["alpha", "beta"]
    assert built["count"] == 1


def test_extract_entities_vendor_unavailable(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"openai_api_key": "sk-x", "chat_model": "gpt-4o-mini"},
    )
    import plugins.base as base_module

    def fake_build(vendor, **kwargs):
        raise ValueError("not registered")

    monkeypatch.setattr(base_module.LLMExtractionRegistry, "build", fake_build)
    assert KGRAGQueryPlugin._extract_question_entities("q", _Collection()) == []


def test_extract_entities_non_dict_payload(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"openai_api_key": "sk-x", "chat_model": "gpt-4o-mini"},
    )
    import plugins.base as base_module

    monkeypatch.setattr(
        base_module.LLMExtractionRegistry, "build",
        lambda vendor, **kwargs: _FakeExtractionBackend(["not", "a", "dict"]),
    )
    assert KGRAGQueryPlugin._extract_question_entities("q", _Collection()) == []


def test_extract_entities_custom_vendor_skips_key_check(monkeypatch):
    # A non-openai vendor doesn't require an OpenAI key.
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"openai_api_key": "", "chat_model": "gpt-4o-mini"},
    )
    import plugins.base as base_module

    monkeypatch.setattr(
        base_module.LLMExtractionRegistry, "build",
        lambda vendor, **kwargs: _FakeExtractionBackend({"entities": ["x"]}),
    )
    coll = _Collection(extraction_vendor="ollama", extraction_model="llama3.1:8b")
    assert KGRAGQueryPlugin._extract_question_entities("q", coll) == ["x"]


def test_extract_entities_cache_eviction(monkeypatch):
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"openai_api_key": "sk-x", "chat_model": "gpt-4o-mini"},
    )
    import plugins.base as base_module

    monkeypatch.setattr(
        base_module.LLMExtractionRegistry, "build",
        lambda vendor, **kwargs: _FakeExtractionBackend({"entities": ["e"]}),
    )
    # Fill the cache beyond its bound to exercise FIFO eviction.
    monkeypatch.setattr(KGRAGQueryPlugin, "_QUESTION_CACHE_SIZE", 3)
    for i in range(5):
        KGRAGQueryPlugin._extract_question_entities(f"question {i}", _Collection())
    assert len(KGRAGQueryPlugin._question_cache) <= 3
