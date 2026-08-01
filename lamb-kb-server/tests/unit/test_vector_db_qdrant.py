"""Unit tests for the Qdrant vector DB backend.

The session conftest sets ``VECTOR_DB_QDRANT=DISABLE`` to avoid registering
the plugin during the discovery phase.  We import the backend class directly
so the env var does not matter for instantiation.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from plugins.base import Chunk
from plugins.vector_db.qdrant_backend import QdrantBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cid() -> str:
    return f"kb_{uuid4().hex[:20]}"


# ---------------------------------------------------------------------------
# 1. Local mode by default (no QDRANT_URL set)
# ---------------------------------------------------------------------------

def test_qdrant_local_mode_create_and_delete(tmp_storage: str, fake_embedding) -> None:
    """create_collection works with local on-disk client (no QDRANT_URL set)."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    backend_id = be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    assert backend_id == cid

    # Storage directory must exist after creation.
    assert os.path.isdir(tmp_storage)

    # Cleanup must not raise.
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)


# ---------------------------------------------------------------------------
# 2. Embedding dimension probing
# ---------------------------------------------------------------------------

def test_qdrant_embedding_dimension_probe(tmp_storage: str) -> None:
    """create_collection calls the embedding function with a single-element list."""
    os.environ.pop("QDRANT_URL", None)

    calls: list[list[str]] = []

    class RecordingEmbedding:
        _dim = 16

        def __call__(self, texts: list[str]) -> list[list[float]]:
            calls.append(list(texts))
            # Return a unit vector of the right dimension for each input.
            return [[1.0 / self._dim] * self._dim for _ in texts]

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=RecordingEmbedding(),
    )

    # First call must be a single-element probe to detect the dimension.
    assert calls, "embedding function was never called"
    assert calls[0] == ["dimension probe"], (
        f"expected probe call with ['dimension probe'], got {calls[0]!r}"
    )


# ---------------------------------------------------------------------------
# 3. Create + add + query roundtrip
# ---------------------------------------------------------------------------

def test_qdrant_add_and_query(tmp_storage: str, fake_embedding) -> None:
    """5 chunks can be added; querying with an exact text returns it as top result."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    chunks = [
        Chunk(text="LAMB uses FastAPI and SQLAlchemy.", metadata={"source_item_id": "src-a", "chunk_index": 0}),
        Chunk(text="Libraries import; knowledge bases ingest.", metadata={"source_item_id": "src-a", "chunk_index": 1}),
        Chunk(text="Python is widely used for machine learning.", metadata={"source_item_id": "src-b", "chunk_index": 0}),
        Chunk(text="Qdrant supports cosine, dot, and L2 distance.", metadata={"source_item_id": "src-b", "chunk_index": 1}),
        Chunk(text="FastAPI makes building APIs straightforward.", metadata={"source_item_id": "src-c", "chunk_index": 0}),
    ]

    n = be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )
    assert n == 5

    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="Python is widely used for machine learning.",
        top_k=5,
        embedding_function=fake_embedding,
    )
    assert len(results) >= 1
    top = results[0]
    assert top.metadata.get("source_item_id") == "src-b"
    assert top.score > 0.95


# ---------------------------------------------------------------------------
# 4. Score normalisation: returned scores must be in [0, 1]
# ---------------------------------------------------------------------------

def test_qdrant_score_normalisation(tmp_storage: str, fake_embedding) -> None:
    """Query scores are normalised from Qdrant's [-1, 1] to [0, 1]."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    chunks = [
        Chunk(text=f"document number {i}", metadata={"source_item_id": "src-norm", "chunk_index": i})
        for i in range(5)
    ]
    be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )

    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="document number 0",
        top_k=5,
        embedding_function=fake_embedding,
    )
    assert results, "expected at least one result"
    for r in results:
        assert 0.0 <= r.score <= 1.0, f"score {r.score} is outside [0, 1]"


# ---------------------------------------------------------------------------
# 5. _TEXT_KEY="_text" — chunk text is recoverable via query
# ---------------------------------------------------------------------------

def test_qdrant_text_key_stored_and_recovered(tmp_storage: str, fake_embedding) -> None:
    """Text stored under _TEXT_KEY is returned correctly by query."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    target_text = "unique marker text for _TEXT_KEY test"
    be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=[Chunk(text=target_text, metadata={"source_item_id": "src-text", "chunk_index": 0})],
        embedding_function=fake_embedding,
    )

    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text=target_text,
        top_k=1,
        embedding_function=fake_embedding,
    )
    assert results
    assert results[0].text == target_text
    # The internal _text key must not leak into metadata.
    assert "_text" not in results[0].metadata


# ---------------------------------------------------------------------------
# 6. parent_text propagation
# ---------------------------------------------------------------------------

def test_qdrant_parent_text_propagation(tmp_storage: str, fake_embedding) -> None:
    """When parent_text is in metadata, query returns it as the result text."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=[
            Chunk(
                text="short child chunk",
                metadata={
                    "source_item_id": "src-parent",
                    "chunk_index": 0,
                    "parent_text": "FULL PARENT CONTEXT — much longer text",
                },
            )
        ],
        embedding_function=fake_embedding,
    )

    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="short child chunk",
        top_k=1,
        embedding_function=fake_embedding,
    )
    assert results
    assert results[0].text == "FULL PARENT CONTEXT — much longer text"
    assert "parent_text" not in results[0].metadata


# ---------------------------------------------------------------------------
# 7. delete_by_source filter
# ---------------------------------------------------------------------------

def test_qdrant_delete_by_source(tmp_storage: str, fake_embedding) -> None:
    """delete_by_source removes only chunks for the specified source_item_id."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    chunks = (
        [Chunk(text=f"alpha chunk {i}", metadata={"source_item_id": "src-alpha", "chunk_index": i}) for i in range(3)]
        + [Chunk(text=f"beta chunk {i}", metadata={"source_item_id": "src-beta", "chunk_index": i}) for i in range(2)]
    )
    be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )

    removed = be.delete_by_source(
        collection_id=cid,
        storage_path=tmp_storage,
        source_item_id="src-alpha",
    )
    assert removed == 3

    # Only beta chunks should remain.
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="alpha chunk 0",
        top_k=10,
        embedding_function=fake_embedding,
    )
    for r in results:
        assert r.metadata.get("source_item_id") != "src-alpha", (
            f"deleted source_item_id still appears in results: {r}"
        )


# ---------------------------------------------------------------------------
# 8. Idempotent delete_collection
# ---------------------------------------------------------------------------

def test_qdrant_delete_collection_idempotent(tmp_storage: str, fake_embedding) -> None:
    """Calling delete_collection twice must not raise."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)
    # Second call: collection and directory are gone; must not raise.
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)


# ---------------------------------------------------------------------------
# 9. Batch upsert boundary — 101 chunks trigger two batches
# ---------------------------------------------------------------------------

def test_qdrant_batch_upsert_boundary(tmp_storage: str, fake_embedding) -> None:
    """101 chunks must be stored correctly across two batches of 100 + 1."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    chunks = [
        Chunk(text=f"batch boundary chunk {i}", metadata={"source_item_id": "src-batch", "chunk_index": i})
        for i in range(101)
    ]
    n = be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )
    assert n == 101

    # Verify via a query that chunks from both batches are present.
    results_first = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="batch boundary chunk 0",
        top_k=1,
        embedding_function=fake_embedding,
    )
    results_last = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="batch boundary chunk 100",
        top_k=1,
        embedding_function=fake_embedding,
    )
    assert results_first and results_first[0].metadata.get("source_item_id") == "src-batch"
    assert results_last and results_last[0].metadata.get("source_item_id") == "src-batch"


# ---------------------------------------------------------------------------
# 10. add_chunks([]) returns 0, no upsert
# ---------------------------------------------------------------------------

def test_qdrant_add_chunks_empty(tmp_storage: str, fake_embedding) -> None:
    """add_chunks with an empty list returns 0 without error."""
    os.environ.pop("QDRANT_URL", None)

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    n = be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=[],
        embedding_function=fake_embedding,
    )
    assert n == 0


# ---------------------------------------------------------------------------
# 11. Remote mode detection via monkeypatch + mock
# ---------------------------------------------------------------------------

def test_qdrant_delete_collection_exception_swallowed(tmp_storage: str, fake_embedding) -> None:
    """delete_collection swallows exceptions from the Qdrant client (warning branch)."""
    os.environ.pop("QDRANT_URL", None)

    import plugins.vector_db.qdrant_backend as qdrant_mod

    be = QdrantBackend()
    cid = _make_cid()
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )

    # Patch _make_client to return a client whose delete_collection always raises.
    broken_client = MagicMock()
    broken_client.delete_collection.side_effect = RuntimeError("forced failure")

    with patch.object(qdrant_mod, "_make_client", return_value=broken_client):
        # Must not raise — exception is swallowed with a warning log.
        be.delete_collection(collection_id=cid, storage_path=tmp_storage)

    broken_client.delete_collection.assert_called_once_with(collection_name=cid)


def test_qdrant_remote_mode_uses_url(monkeypatch, tmp_storage: str) -> None:
    """When QDRANT_URL is set, QdrantClient is constructed with url= not path=."""
    # Use monkeypatch.setattr only — it auto-restores after the test. Do NOT
    # call importlib.reload(config), because that permanently rebinds module
    # attributes from current env, leaking into integration tests.
    import plugins.vector_db.qdrant_backend as qdrant_mod
    monkeypatch.setattr(qdrant_mod.config, "QDRANT_URL", "http://invalid-host-9999:9999")
    monkeypatch.setattr(qdrant_mod.config, "QDRANT_API_KEY", "test-key")

    captured_kwargs: dict = {}

    original_QdrantClient = qdrant_mod.QdrantClient

    class CapturingClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            # Raise immediately so we don't actually try to connect.
            raise ConnectionError("mock: not connecting")

    with patch.object(qdrant_mod, "QdrantClient", CapturingClient):
        be = QdrantBackend()
        cid = _make_cid()
        with pytest.raises((ConnectionError, Exception)):
            be.create_collection(
                collection_id=cid,
                storage_path=tmp_storage,
                embedding_function=lambda texts: [[0.0] * 16 for _ in texts],
            )

    assert "url" in captured_kwargs, (
        f"Expected 'url' kwarg for remote mode, got: {captured_kwargs}"
    )
    assert "path" not in captured_kwargs, (
        f"'path' kwarg must not be present in remote mode, got: {captured_kwargs}"
    )
    assert captured_kwargs["url"] == "http://invalid-host-9999:9999"
