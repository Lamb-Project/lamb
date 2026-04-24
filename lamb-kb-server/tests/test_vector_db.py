"""Unit tests for the ChromaDB vector DB backend."""

import shutil
import tempfile
from uuid import uuid4

import pytest
from plugins.base import Chunk
from plugins.vector_db.chromadb_backend import ChromaDBBackend


@pytest.fixture
def tmp_storage() -> str:
    path = tempfile.mkdtemp(prefix="kbs-vdb-")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def fake_embedding():
    """Reuse the FakeEmbedding registered in conftest."""
    from plugins.base import EmbeddingRegistry  # noqa: PLC0415

    ef_class = EmbeddingRegistry._plugins["fake"]
    return ef_class(model="fake-model")


def test_chromadb_create_and_delete(tmp_storage: str, fake_embedding) -> None:
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
    backend_id = be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    assert backend_id  # ChromaDB returns a UUID
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)
    # Idempotent delete.
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)


def test_chromadb_add_and_query(tmp_storage: str, fake_embedding) -> None:
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    chunks = [
        Chunk(
            text="LAMB uses FastAPI and SQLAlchemy for the backend.",
            metadata={"source_item_id": "doc-a", "chunk_index": 0},
        ),
        Chunk(
            text="Libraries import content; knowledge bases ingest content.",
            metadata={"source_item_id": "doc-a", "chunk_index": 1},
        ),
        Chunk(
            text="Python is a programming language used widely for ML.",
            metadata={"source_item_id": "doc-b", "chunk_index": 0},
        ),
    ]
    n = be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )
    assert n == 3

    # Identical text should score ~1.0 (top match).
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="Python is a programming language used widely for ML.",
        top_k=3,
        embedding_function=fake_embedding,
    )
    assert len(results) >= 1
    top = results[0]
    assert top.metadata.get("source_item_id") == "doc-b"
    assert top.score > 0.95


def test_chromadb_delete_by_source(tmp_storage: str, fake_embedding) -> None:
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    chunks = [
        Chunk(text=f"chunk {i}", metadata={"source_item_id": "doc-x", "chunk_index": i})
        for i in range(5)
    ] + [
        Chunk(text="other", metadata={"source_item_id": "doc-y", "chunk_index": 0}),
    ]
    be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )
    removed = be.delete_by_source(
        collection_id=cid,
        storage_path=tmp_storage,
        source_item_id="doc-x",
    )
    assert removed == 5
    # Query should no longer return doc-x hits.
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="chunk 0",
        top_k=10,
        embedding_function=fake_embedding,
    )
    for r in results:
        assert r.metadata.get("source_item_id") != "doc-x"


def test_chromadb_parent_text_propagation(tmp_storage: str, fake_embedding) -> None:
    """When chunks carry parent_text, the backend returns that instead of the child text."""
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
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
                text="short child A",
                metadata={
                    "source_item_id": "doc-1",
                    "chunk_index": 0,
                    "parent_text": "FULL PARENT CONTEXT A",
                },
            ),
        ],
        embedding_function=fake_embedding,
    )
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="short child A",
        top_k=1,
        embedding_function=fake_embedding,
    )
    assert results
    assert results[0].text == "FULL PARENT CONTEXT A"
    assert "parent_text" not in results[0].metadata
