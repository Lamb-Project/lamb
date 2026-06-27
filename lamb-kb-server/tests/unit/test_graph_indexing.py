"""Unit tests for ``services.graph_indexing``.

Drives ``index_chunks_for_collection`` through every return branch with a
fake ``ConceptExtractor`` and a fake graph store, and tests the ``_build_chunks``
filter helper directly.
"""

from __future__ import annotations

import pytest

import config as config_module
import services.graph_indexing as gi
import services.graph_store as gs_module
from services.concept_extraction import (
    ExtractedEntity,
    ExtractedRelationship,
    GraphExtraction,
)


class _Collection:
    def __init__(self, **over):
        self.id = "col-1"
        self.name = "Coll"
        self.organization_id = "org-1"
        self.extraction_vendor = None
        self.extraction_model = None
        self.extraction_endpoint = None
        self.__dict__.update(over)


class _FakeExtractor:
    def __init__(self, *args, extraction=None, raises=False, **kwargs):
        self._extraction = extraction or GraphExtraction()
        self._raises = raises
        _FakeExtractor.last_kwargs = kwargs

    def extract_for_chunks(self, chunks):
        if self._raises:
            raise RuntimeError("extraction boom")
        return self._extraction


class _FakeGraphStore:
    def __init__(self, *, configured=True, available=True, ingest_raises=False):
        self._configured = configured
        self._available = available
        self._ingest_raises = ingest_raises
        self.ingest_calls = []

    def is_configured(self):
        return self._configured

    def is_available(self):
        return self._available

    def ingest_chunks(self, **kwargs):
        self.ingest_calls.append(kwargs)
        if self._ingest_raises:
            raise RuntimeError("ingest boom")
        return 5


# ---------------------------------------------------------------------------
# _build_chunks
# ---------------------------------------------------------------------------


def test_build_chunks_filters_and_parent_text():
    chunks = gi._build_chunks(
        ids=["c1", "", "c3", "c4"],
        texts=["text one", "skipped", "   ", "text four"],
        metadatas=[{"parent_text": "PARENT"}, {}, {}],  # c4 has no metadata entry
    )
    # "" id dropped, "   " whitespace text dropped.
    ids = [c.chunk_id for c in chunks]
    assert ids == ["c1", "c4"]
    # parent_text taken from metadata when present.
    assert chunks[0].parent_text == "PARENT"
    # c4 has no metadata -> parent_text falls back to its own text.
    assert chunks[1].parent_text == "text four"


def test_build_chunks_drops_ids_beyond_texts():
    chunks = gi._build_chunks(ids=["c1", "c2"], texts=["only one"], metadatas=[{}])
    assert [c.chunk_id for c in chunks] == ["c1"]


# ---------------------------------------------------------------------------
# index_chunks_for_collection
# ---------------------------------------------------------------------------


def _enable_kg(monkeypatch, **extra):
    cfg = {"enabled": True, "openai_api_key": "sk-env"}
    cfg.update(extra)
    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: cfg)


def test_index_disabled(monkeypatch):
    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: {"enabled": False})
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=["c1"], texts=["t"], metadatas=[{}]
    )
    assert out == {"indexed": False, "chunks": 0, "reason": "kg_rag_disabled"}


def test_index_no_chunks(monkeypatch):
    _enable_kg(monkeypatch)
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=[], texts=[], metadatas=[]
    )
    assert out["reason"] == "no_chunks"


def test_index_openai_requires_key(monkeypatch):
    # enabled, openai vendor, but no key anywhere.
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"enabled": True, "openai_api_key": ""},
    )
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=["c1"], texts=["text"], metadatas=[{}],
        openai_api_key="",
    )
    assert out["reason"] == "no_openai_api_key"
    assert "OpenAI API key" in out["error"]


def test_index_extraction_failure(monkeypatch):
    _enable_kg(monkeypatch)
    monkeypatch.setattr(
        gi, "ConceptExtractor",
        lambda *a, **k: _FakeExtractor(raises=True),
    )
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=["c1"], texts=["text"], metadatas=[{}],
        openai_api_key="sk-x",
    )
    assert "concept_extraction_failed" in out["error"]


def test_index_neo4j_unavailable(monkeypatch):
    _enable_kg(monkeypatch)
    monkeypatch.setattr(
        gi, "ConceptExtractor", lambda *a, **k: _FakeExtractor()
    )
    monkeypatch.setattr(
        gs_module, "get_graph_store",
        lambda: _FakeGraphStore(available=False),
    )
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=["c1"], texts=["text"], metadatas=[{}],
        openai_api_key="sk-x",
    )
    assert out["error"] == "neo4j_unavailable"


def test_index_graph_write_failure(monkeypatch):
    _enable_kg(monkeypatch)
    monkeypatch.setattr(
        gi, "ConceptExtractor", lambda *a, **k: _FakeExtractor()
    )
    monkeypatch.setattr(
        gs_module, "get_graph_store",
        lambda: _FakeGraphStore(ingest_raises=True),
    )
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=["c1"], texts=["text"], metadatas=[{}],
        openai_api_key="sk-x",
    )
    assert "graph_write_failed" in out["error"]
    assert "extraction_ms" in out


def test_index_success_with_filename_resolution(monkeypatch):
    _enable_kg(monkeypatch)
    extraction = GraphExtraction(
        concepts_by_chunk={"c1": ["alpha"]},
        entities={"alpha": ExtractedEntity(name="alpha", display_name="Alpha")},
        relationships=[
            ExtractedRelationship(source="alpha", target="beta", relation="uses")
        ],
    )
    monkeypatch.setattr(
        gi, "ConceptExtractor", lambda *a, **k: _FakeExtractor(extraction=extraction)
    )
    store = _FakeGraphStore()
    monkeypatch.setattr(gs_module, "get_graph_store", lambda: store)
    out = gi.index_chunks_for_collection(
        collection=_Collection(),
        ids=["c1"],
        texts=["body"],
        metadatas=[{"source_label": "Doc Title"}],  # filename resolved from here
        openai_api_key="sk-x",
    )
    assert out["indexed"] is True
    assert out["chunks"] == 1
    assert out["entities"] == 1
    assert out["relationships"] == 1
    assert "extraction_ms" in out and "graph_ms" in out
    # Filename was resolved from chunk metadata.
    assert store.ingest_calls[0]["filename"] == "Doc Title"


def test_index_success_default_filename(monkeypatch):
    _enable_kg(monkeypatch)
    monkeypatch.setattr(
        gi, "ConceptExtractor", lambda *a, **k: _FakeExtractor()
    )
    store = _FakeGraphStore()
    monkeypatch.setattr(gs_module, "get_graph_store", lambda: store)
    out = gi.index_chunks_for_collection(
        collection=_Collection(), ids=["c1"], texts=["body"], metadatas=[{}],
        openai_api_key="sk-x",
    )
    assert out["indexed"] is True
    # No filename anywhere -> default sentinel.
    assert store.ingest_calls[0]["filename"] == "collection_chunks"


def test_index_ollama_vendor_no_key_required(monkeypatch):
    _enable_kg(monkeypatch, openai_api_key="")
    monkeypatch.setattr(
        gi, "ConceptExtractor", lambda *a, **k: _FakeExtractor()
    )
    store = _FakeGraphStore()
    monkeypatch.setattr(gs_module, "get_graph_store", lambda: store)
    out = gi.index_chunks_for_collection(
        collection=_Collection(extraction_vendor="ollama"),
        ids=["c1"], texts=["body"], metadatas=[{}],
    )
    # Ollama doesn't require an OpenAI key -> proceeds to indexing.
    assert out["indexed"] is True
