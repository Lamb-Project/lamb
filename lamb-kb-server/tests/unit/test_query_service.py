"""Unit tests for ``services.query_service``.

Exercises both entry points (``query_collection`` and ``query_with_plugin``)
with fake registries, a fake vector backend, and a stub DB session — including
the KG-RAG auto-routing branch, its graceful degradation on failure, the
threshold filter, and the 404 / 503 error paths.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import config as config_module
import plugins.kg_rag_query as kg_module
import services.query_service as qs
from plugins.base import QueryResult
from schemas.query import QueryRequest


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._result


class _FakeDB:
    def __init__(self, collection):
        self._c = collection

    def query(self, _model):
        return _FakeQuery(self._c)


class _Collection:
    def __init__(self, **over):
        self.id = "col-1"
        self.embedding_vendor = "openai"
        self.embedding_model = "text-embedding-3-small"
        self.embedding_endpoint = ""
        self.vector_db_backend = "chromadb"
        self.backend_collection_id = "backend-col"
        self.storage_path = "/tmp/store"
        self.graph_enabled = False
        self.__dict__.update(over)


class _FakeBackend:
    def __init__(self, results):
        self._results = results

    def query(self, **kwargs):
        return self._results


@pytest.fixture
def patch_registries(monkeypatch):
    """Patch EmbeddingRegistry.build + VectorDBRegistry.get. Returns a setter
    for the backend the registry hands back (None -> 503)."""
    monkeypatch.setattr(
        qs.EmbeddingRegistry, "build",
        classmethod(lambda cls, vendor, **kwargs: object()),
    )

    state = {"backend": None}

    monkeypatch.setattr(
        qs.VectorDBRegistry, "get",
        classmethod(lambda cls, name: state["backend"]),
    )

    def _set_backend(backend):
        state["backend"] = backend

    return _set_backend


def _req(top_k=5):
    return QueryRequest.model_validate(
        {
            "query_text": "what is alpha?",
            "top_k": top_k,
            "embedding_credentials": {"api_key": "sk-x", "api_endpoint": ""},
        }
    )


# ---------------------------------------------------------------------------
# query_collection
# ---------------------------------------------------------------------------


def test_query_collection_not_found(patch_registries):
    with pytest.raises(HTTPException) as exc:
        qs.query_collection(_FakeDB(None), "missing", _req())
    assert exc.value.status_code == 404


def test_query_collection_backend_unavailable(patch_registries):
    patch_registries(None)  # registry returns no backend
    with pytest.raises(HTTPException) as exc:
        qs.query_collection(_FakeDB(_Collection()), "col-1", _req())
    assert exc.value.status_code == 503


def test_query_collection_plain_vector(patch_registries):
    patch_registries(_FakeBackend([QueryResult(text="hit", score=0.9, metadata={})]))
    out = qs.query_collection(_FakeDB(_Collection()), "col-1", _req())
    assert len(out) == 1
    assert out[0].text == "hit"


def test_query_collection_graph_enabled_but_kg_disabled(
    patch_registries, monkeypatch
):
    monkeypatch.setattr(config_module, "KG_RAG_ENABLED", False)
    patch_registries(_FakeBackend([QueryResult(text="hit", score=0.9, metadata={})]))
    out = qs.query_collection(
        _FakeDB(_Collection(graph_enabled=True)), "col-1", _req()
    )
    # No augmentation applied -> baseline result preserved.
    assert out[0].text == "hit"


def test_query_collection_kg_rag_augments(patch_registries, monkeypatch):
    monkeypatch.setattr(config_module, "KG_RAG_ENABLED", True)
    patch_registries(_FakeBackend([QueryResult(text="hit", score=0.9, metadata={})]))

    def fake_augment(self, **kwargs):
        return [
            {"similarity": 0.95, "data": "augmented", "metadata": {"kg_rag": {}}},
        ]

    monkeypatch.setattr(kg_module.KGRAGQueryPlugin, "augment", fake_augment)
    out = qs.query_collection(
        _FakeDB(_Collection(graph_enabled=True)), "col-1", _req()
    )
    assert out[0].text == "augmented"
    assert out[0].score == 0.95


def test_query_collection_kg_rag_failure_degrades(patch_registries, monkeypatch):
    monkeypatch.setattr(config_module, "KG_RAG_ENABLED", True)
    patch_registries(_FakeBackend([QueryResult(text="baseline", score=0.8, metadata={})]))

    def boom(self, **kwargs):
        raise RuntimeError("augment failed")

    monkeypatch.setattr(kg_module.KGRAGQueryPlugin, "augment", boom)
    out = qs.query_collection(
        _FakeDB(_Collection(graph_enabled=True)), "col-1", _req()
    )
    # Falls back to the vector baseline.
    assert out[0].text == "baseline"


# ---------------------------------------------------------------------------
# query_with_plugin
# ---------------------------------------------------------------------------


def test_query_with_plugin_not_found(patch_registries):
    with pytest.raises(HTTPException) as exc:
        qs.query_with_plugin(db=_FakeDB(None), collection_id="x", query_text="q")
    assert exc.value.status_code == 404


def test_query_with_plugin_backend_unavailable(patch_registries):
    patch_registries(None)
    with pytest.raises(HTTPException) as exc:
        qs.query_with_plugin(
            db=_FakeDB(_Collection()), collection_id="col-1", query_text="q"
        )
    assert exc.value.status_code == 503


def test_query_with_plugin_simple_applies_threshold(patch_registries):
    patch_registries(
        _FakeBackend(
            [
                QueryResult(text="keep", score=0.9, metadata={}),
                QueryResult(text="drop", score=0.1, metadata={}),
            ]
        )
    )
    out = qs.query_with_plugin(
        db=_FakeDB(_Collection()),
        collection_id="col-1",
        query_text="q",
        plugin_params={"top_k": 5, "threshold": 0.5},
    )
    texts = [r["data"] for r in out["results"]]
    assert texts == ["keep"]
    assert out["query"] == "q"
    assert out["top_k"] == 5
    assert "total_ms" in out["timing"]


def test_query_with_plugin_kg_rag_augments(patch_registries, monkeypatch):
    patch_registries(_FakeBackend([QueryResult(text="seed", score=0.9, metadata={})]))

    def fake_augment(self, **kwargs):
        return [{"similarity": 0.9, "data": "graph-added", "metadata": {}}]

    monkeypatch.setattr(kg_module.KGRAGQueryPlugin, "augment", fake_augment)
    out = qs.query_with_plugin(
        db=_FakeDB(_Collection()),
        collection_id="col-1",
        query_text="q",
        plugin_name="kg_rag_query",
    )
    assert out["results"][0]["data"] == "graph-added"


def test_query_with_plugin_kg_rag_failure_degrades(patch_registries, monkeypatch):
    patch_registries(_FakeBackend([QueryResult(text="seed", score=0.9, metadata={})]))

    def boom(self, **kwargs):
        raise RuntimeError("augment failed")

    monkeypatch.setattr(kg_module.KGRAGQueryPlugin, "augment", boom)
    out = qs.query_with_plugin(
        db=_FakeDB(_Collection()),
        collection_id="col-1",
        query_text="q",
        plugin_name="kg_rag_query",
    )
    # Degrades to the formatted baseline.
    assert out["results"][0]["data"] == "seed"
