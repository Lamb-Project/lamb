"""Focused unit tests for the KG-RAG migration.

Covered:

* ``config.get_kg_rag_config`` reads env vars and applies sensible defaults
  (disabled by default, sane bounds on ``graph_depth`` / ``limit_factor`` /
  ``extraction_max_workers``).
* The KG-RAG query plugin returns the baseline unchanged with explicit
  warnings when the feature is disabled, when the collection has not opted
  in, and when there are no seed chunks.
* The concept-extraction module's pure helpers (``normalize_concept`` /
  ``normalize_relation``) are deterministic and robust to Unicode noise.

These tests intentionally avoid Neo4j / OpenAI — the heavy paths are
exercised by integration / e2e suites that are gated on the optional
``kg-rag`` extra and Docker services.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest


@pytest.fixture()
def reload_config(monkeypatch) -> Iterator[None]:
    """Local copy of the reload_config fixture from test_config.py."""
    import config  # noqa: PLC0415

    yield
    importlib.reload(config)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def test_kg_rag_config_disabled_by_default(reload_config, monkeypatch):
    for var in (
        "KG_RAG_ENABLED",
        "KG_RAG_INDEX_ON_INGEST",
        "KG_RAG_OPENAI_API_KEY",
        "KG_RAG_NEO4J_URI",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    import config

    importlib.reload(config)
    cfg = config.get_kg_rag_config()
    assert cfg["enabled"] is False
    assert cfg["graph_depth"] == 2
    assert cfg["limit_factor"] == 4
    assert cfg["extraction_max_workers"] == 4


def test_kg_rag_config_clamps_graph_depth(reload_config, monkeypatch):
    monkeypatch.setenv("KG_RAG_ENABLED", "true")
    monkeypatch.setenv("KG_RAG_GRAPH_DEPTH", "99")
    monkeypatch.setenv("KG_RAG_LIMIT_FACTOR", "999")
    monkeypatch.setenv("KG_RAG_EXTRACTION_MAX_WORKERS", "999")
    import config

    importlib.reload(config)
    cfg = config.get_kg_rag_config()
    assert cfg["enabled"] is True
    assert cfg["graph_depth"] == 4
    assert cfg["limit_factor"] == 20
    assert cfg["extraction_max_workers"] == 16


def test_kg_rag_config_falls_back_to_openai_api_key(reload_config, monkeypatch):
    monkeypatch.delenv("KG_RAG_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fallback")
    import config

    importlib.reload(config)
    cfg = config.get_kg_rag_config()
    assert cfg["openai_api_key"] == "sk-test-fallback"


# ---------------------------------------------------------------------------
# concept extraction (pure helpers)
# ---------------------------------------------------------------------------


def test_normalize_concept_strips_accents_and_punct():
    from services.concept_extraction import normalize_concept

    assert normalize_concept("Café Society!") == "cafe society"
    assert normalize_concept("  multiple   spaces  ") == "multiple spaces"
    assert normalize_concept("") == ""


def test_normalize_relation_keeps_short_relation_keys():
    from services.concept_extraction import normalize_relation

    assert normalize_relation("Depends On") == "depends_on"
    assert normalize_relation(" improves --   ") == "improves"
    # Fallback for empty / unusable input.
    assert normalize_relation("---") == "related_to"


# ---------------------------------------------------------------------------
# KG-RAG query plugin: graceful degradation paths
# ---------------------------------------------------------------------------


class _StubCollection:
    """Minimal stand-in for the ORM Collection row."""

    def __init__(self, *, graph_enabled: bool = True):
        self.id = "stub-collection"
        self.organization_id = "stub-org"
        self.graph_enabled = graph_enabled
        self.backend_collection_id = "stub-backend"
        self.storage_path = "/tmp/does-not-matter"


def test_plugin_returns_baseline_when_kg_rag_disabled(monkeypatch):
    monkeypatch.delenv("KG_RAG_ENABLED", raising=False)

    from plugins.kg_rag_query import KGRAGQueryPlugin

    plugin = KGRAGQueryPlugin()
    baseline = [{"similarity": 0.9, "data": "hello", "metadata": {"document_id": "c1"}}]
    out = plugin.augment(
        db=None,
        collection=_StubCollection(),
        backend=None,
        embedding_function=None,
        query_text="anything",
        baseline_results=baseline,
        params={},
    )
    # Same payload, with a kg_rag trace attached that explains the no-op.
    assert len(out) == 1
    trace = out[0]["metadata"].get("kg_rag")
    assert trace is not None
    assert trace["enabled"] is False
    assert "KG-RAG is disabled" in " ".join(trace["warnings"])


def test_plugin_returns_baseline_when_collection_not_opted_in(monkeypatch):
    monkeypatch.setenv("KG_RAG_ENABLED", "true")

    from plugins.kg_rag_query import KGRAGQueryPlugin

    plugin = KGRAGQueryPlugin()
    out = plugin.augment(
        db=None,
        collection=_StubCollection(graph_enabled=False),
        backend=None,
        embedding_function=None,
        query_text="anything",
        baseline_results=[
            {"similarity": 0.9, "data": "x", "metadata": {"document_id": "c1"}}
        ],
        params={},
    )
    trace = out[0]["metadata"]["kg_rag"]
    assert any("graph_enabled=false" in w for w in trace["warnings"])


def test_plugin_returns_baseline_when_no_seed_ids(monkeypatch):
    monkeypatch.setenv("KG_RAG_ENABLED", "true")

    from plugins.kg_rag_query import KGRAGQueryPlugin

    plugin = KGRAGQueryPlugin()
    out = plugin.augment(
        db=None,
        collection=_StubCollection(),
        backend=None,
        embedding_function=None,
        query_text="anything",
        # Baseline result has no chunk-like id, so seed extraction is empty.
        baseline_results=[
            {"similarity": 0.9, "data": "x", "metadata": {}}
        ],
        params={},
    )
    trace = out[0]["metadata"]["kg_rag"]
    assert any("No vector seed chunks" in w for w in trace["warnings"])
