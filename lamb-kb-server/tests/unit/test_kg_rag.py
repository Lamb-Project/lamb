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

import pytest


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


# ---------------------------------------------------------------------------
# Benchmark route body shape — regression test for the FastAPI Body(embed=True)
# bug. The LAMB proxy sends a flat JSON body; the route must accept it without
# wrapping fields under ``request``.
# ---------------------------------------------------------------------------


def test_benchmark_run_request_validates_flat_proxy_body():
    """The exact JSON shape sent by ``KnowledgeStoreClient.run_benchmark``
    must validate as a ``BenchmarkRunRequest`` — including the embedded
    ``embedding_credentials`` sub-object."""
    from schemas.benchmark import BenchmarkRunRequest

    proxy_body = {
        "dataset_id": "educational",
        "top_k": 5,
        "graph_depth": 2,
        "threshold": 0.0,
        "embedding_credentials": {
            "api_key": "sk-test",
            "api_endpoint": "",
        },
    }
    parsed = BenchmarkRunRequest.model_validate(proxy_body)
    assert parsed.dataset_id == "educational"
    assert parsed.top_k == 5
    assert parsed.embedding_credentials.api_key == "sk-test"


def test_benchmark_run_request_credentials_optional():
    """Direct API callers may omit ``embedding_credentials`` entirely."""
    from schemas.benchmark import BenchmarkRunRequest

    parsed = BenchmarkRunRequest.model_validate(
        {"dataset_id": "educational", "top_k": 5}
    )
    # Default factory produces an empty-string credentials object.
    assert parsed.embedding_credentials.api_key == ""
    assert parsed.embedding_credentials.api_endpoint == ""


# ---------------------------------------------------------------------------
# Schema migration: graph_enabled column auto-added on init_db
# ---------------------------------------------------------------------------


def test_init_db_adds_graph_enabled_to_legacy_collections_table(
    tmp_path, monkeypatch
):
    """A DB that was created before this branch (no graph_enabled column)
    should get the column added by init_db without losing existing rows.

    The bug we're guarding: ``Base.metadata.create_all`` is a no-op on an
    existing table, so without _run_lightweight_migrations any query
    against ``collections`` would raise ``no such column``.

    We call the lightweight-migrations helper directly here rather than
    spinning up a second init_db — that keeps this test from clobbering
    the session-wide ``_engine`` / ``_SessionLocal`` that the rest of the
    suite depends on.
    """
    import sqlite3

    from sqlalchemy import create_engine

    db_path = tmp_path / "legacy.db"

    # Hand-roll the legacy schema (pre-branch) and seed a row.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE collections (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            chunking_strategy TEXT NOT NULL,
            chunking_params TEXT,
            embedding_vendor TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_endpoint TEXT,
            vector_db_backend TEXT NOT NULL,
            backend_collection_id TEXT,
            storage_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            error_message TEXT,
            document_count INTEGER NOT NULL DEFAULT 0,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO collections (
            id, organization_id, name, chunking_strategy, embedding_vendor,
            embedding_model, vector_db_backend, storage_path
        ) VALUES (
            'legacy-1', 'org-1', 'legacy', 'simple', 'fake',
            'fake-model', 'chromadb', '/tmp/legacy'
        );
        """
    )
    conn.commit()
    conn.close()

    legacy_engine = create_engine(f"sqlite:///{db_path}")
    from database.connection import _run_lightweight_migrations

    _run_lightweight_migrations(legacy_engine)
    legacy_engine.dispose()

    # After the migration runs, the legacy row should still be present AND
    # the new column must exist with the documented default.
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("PRAGMA table_info(collections)")
    columns = {row[1] for row in cur.fetchall()}
    assert "graph_enabled" in columns

    row = conn.execute(
        "SELECT graph_enabled FROM collections WHERE id = 'legacy-1'"
    ).fetchone()
    assert row == (0,)  # NOT NULL default 0

    # The migration must be idempotent — running it again is a no-op.
    legacy_engine = create_engine(f"sqlite:///{db_path}")
    _run_lightweight_migrations(legacy_engine)
    legacy_engine.dispose()
    cur = conn.execute("PRAGMA table_info(collections)")
    assert (
        sum(1 for row in cur.fetchall() if row[1] == "graph_enabled") == 1
    )
    conn.close()
