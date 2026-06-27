"""Branch tests for ``services.ingestion_service`` worker logic.

Drives ``execute_ingestion_job`` directly (invalid params, cooperative
cancellation, oversized-chunk re-split) and unit-tests the graph
index/delete helpers with fakes — the branches the happy-path pipeline
tests don't reach.
"""

from __future__ import annotations

import json
import tempfile
from types import SimpleNamespace
from uuid import uuid4

import pytest

import services.ingestion_service as ing
from services.ingestion_service import (
    JobCancelledError,
    _maybe_delete_graph_document,
    _maybe_index_graph,
    execute_ingestion_job,
)


def _mk_collection(session, **over):
    from database.models import Collection

    cid = over.pop("id", f"col-ing-{uuid4().hex[:8]}")
    fields = dict(
        id=cid,
        organization_id="org-ing",
        name=f"ing-{uuid4().hex[:6]}",
        chunking_strategy="simple",
        chunking_params=json.dumps({"chunk_size": 200, "chunk_overlap": 20}),
        embedding_vendor="fake",
        embedding_model="fake-model",
        vector_db_backend="chromadb",
        backend_collection_id=cid,
        storage_path=tempfile.mkdtemp(prefix="ing-"),
    )
    fields.update(over)  # caller overrides win, no kwarg collision
    col = Collection(**fields)
    session.add(col)
    session.commit()
    session.refresh(col)
    return col


def _mk_job(session, collection_id, docs, status="processing"):
    from database.models import IngestionJob

    jid = f"job-ing-{uuid4().hex[:8]}"
    job = IngestionJob(
        id=jid,
        collection_id=collection_id,
        organization_id="org-ing",
        documents_json=json.dumps(docs),
        documents_total=len(docs),
        status=status,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


_DOC = {"source_item_id": "s1", "title": "T", "text": "LAMB ingestion text body.",
        "permalinks": {}, "pages": [], "extra_metadata": {}}


# ---------------------------------------------------------------------------
# execute_ingestion_job
# ---------------------------------------------------------------------------


def test_execute_invalid_chunking_params_raises():
    from database.connection import get_session_direct

    session = get_session_direct()
    try:
        col = _mk_collection(
            session, chunking_params=json.dumps({"bogus_param": 1})
        )
        job = _mk_job(session, col.id, [_DOC])
        with pytest.raises(RuntimeError):
            execute_ingestion_job(session, job, col, {"api_key": "k"})
    finally:
        session.close()


def test_execute_cancelled_job_raises():
    from database.connection import get_session_direct

    session = get_session_direct()
    try:
        col = _mk_collection(session)
        job = _mk_job(session, col.id, [_DOC], status="cancelled")
        with pytest.raises(JobCancelledError):
            execute_ingestion_job(session, job, col, {"api_key": "k"})
    finally:
        session.close()


def test_execute_oversized_chunks_resplit(monkeypatch):
    from database.connection import get_session_direct
    from plugins.vector_db.chromadb_backend import ChromaDBBackend
    from tests._fakes import FakeEmbedding

    # MAX between the two chunk sizes so one chunk is re-split (else branch)
    # and one is kept as-is (if branch) — covers both sides of the guard loop.
    monkeypatch.setattr(ing, "_MAX_EMBED_CHARS", 50)
    monkeypatch.setattr(ing, "_RESPLIT_CHUNK_SIZE", 40)
    monkeypatch.setattr(ing, "_RESPLIT_OVERLAP", 5)

    storage = tempfile.mkdtemp(prefix="ing-resplit-")
    session = get_session_direct()
    try:
        # chunk_size 100 over "a*100 b*20" -> a 100-char chunk (>50, re-split)
        # and a 20-char chunk (<=50, kept).
        col = _mk_collection(
            session, storage_path=storage,
            chunking_params=json.dumps({"chunk_size": 100, "chunk_overlap": 0}),
        )
        # The backend collection must exist for add_chunks.
        ChromaDBBackend().create_collection(
            collection_id=col.backend_collection_id, storage_path=storage,
            embedding_function=FakeEmbedding(),
        )
        mixed_text = "a" * 100 + " " + "b" * 20
        job = _mk_job(session, col.id, [dict(_DOC, text=mixed_text)])
        execute_ingestion_job(session, job, col, {"api_key": "k"})
        session.refresh(job)
        assert job.documents_processed == 1
        assert job.chunks_created >= 1
    finally:
        session.close()


# ---------------------------------------------------------------------------
# _maybe_index_graph
# ---------------------------------------------------------------------------


class _FakeItem:
    def __init__(self, text, metadata):
        self.text = text
        self.metadata = metadata


class _FakeBackend:
    def __init__(self, *, rows=None, raises=False):
        self._rows = rows
        self._raises = raises

    def get_chunks_by_source(self, **kw):
        if self._raises:
            raise RuntimeError("backend boom")
        return self._rows or []


def _coll(**over):
    base = dict(
        graph_enabled=True, vector_db_backend="chromadb",
        backend_collection_id="bc", id="c1", storage_path="/tmp/x",
        organization_id="org",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_maybe_index_graph_not_enabled():
    # graph_enabled False -> immediate return (no config read).
    _maybe_index_graph(
        collection=_coll(graph_enabled=False), docs_list=[_DOC],
        backend=_FakeBackend(), embedding_function=None,
    )  # must not raise


def test_maybe_index_graph_kg_disabled(monkeypatch):
    import config as config_module
    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: {"enabled": False})
    _maybe_index_graph(
        collection=_coll(), docs_list=[_DOC],
        backend=_FakeBackend(), embedding_function=None,
    )


def test_maybe_index_graph_backend_error_and_empty(monkeypatch):
    import config as config_module
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"enabled": True, "index_on_ingest": True},
    )
    # Backend raises for the source -> warning + continue (no crash).
    _maybe_index_graph(
        collection=_coll(), docs_list=[_DOC],
        backend=_FakeBackend(raises=True), embedding_function=None,
    )
    # Backend returns no rows -> skip branch.
    _maybe_index_graph(
        collection=_coll(), docs_list=[_DOC],
        backend=_FakeBackend(rows=[]), embedding_function=None,
    )


def test_maybe_index_graph_indexes_and_logs_error(monkeypatch):
    import config as config_module
    import services.graph_indexing as gi

    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"enabled": True, "index_on_ingest": True},
    )
    calls = {}

    def fake_index(**kw):
        calls.update(kw)
        return {"error": "neo4j_unavailable"}  # exercises the error-log branch

    monkeypatch.setattr(gi, "index_chunks_for_collection", fake_index)
    rows = [_FakeItem("chunk text", {"chunk_id": "ck1"})]
    _maybe_index_graph(
        collection=_coll(), docs_list=[_DOC],
        backend=_FakeBackend(rows=rows), embedding_function=None,
        openai_api_key="sk",
    )
    assert calls["ids"] == ["ck1"]
    assert calls["filename"] == "s1"


# ---------------------------------------------------------------------------
# _maybe_delete_graph_document
# ---------------------------------------------------------------------------


def test_maybe_delete_graph_document_not_enabled():
    _maybe_delete_graph_document(_coll(graph_enabled=False), "s1")


def test_maybe_delete_graph_document_kg_disabled(monkeypatch):
    import config as config_module
    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: {"enabled": False})
    _maybe_delete_graph_document(_coll(), "s1")


def test_maybe_delete_graph_document_calls_store(monkeypatch):
    import config as config_module
    import services.graph_store as gs_module

    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: {"enabled": True})
    deleted = {}

    class _Store:
        def delete_document(self, cid, org, sid):
            deleted["args"] = (cid, org, sid)

    monkeypatch.setattr(gs_module, "get_graph_store", lambda: _Store())
    _maybe_delete_graph_document(_coll(id="c9", organization_id="org9"), "s9")
    assert deleted["args"] == ("c9", "org9", "s9")


def test_maybe_delete_graph_document_store_error(monkeypatch):
    import config as config_module
    import services.graph_store as gs_module

    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: {"enabled": True})

    class _Store:
        def delete_document(self, *a):
            raise RuntimeError("neo4j down")

    monkeypatch.setattr(gs_module, "get_graph_store", lambda: _Store())
    # Exception is swallowed (logged) — must not raise.
    _maybe_delete_graph_document(_coll(), "s1")
