"""Unit tests for the ChromaDB vector DB backend."""

import shutil
import tempfile
from uuid import uuid4

import plugins.vector_db.chromadb_backend as chromadb_backend
import pytest
from chromadb.api.types import EmbeddingFunction as ChromaEmbeddingFunction
from plugins.base import Chunk, EmbeddingFunction
from plugins.vector_db.chromadb_backend import ChromaDBBackend, _to_chroma_ef


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


# ---------------------------------------------------------------------------
# Client-cache tests
# ---------------------------------------------------------------------------


def test_client_cache_reuse(tmp_storage: str, fake_embedding) -> None:
    """Two create_collection calls with the same storage_path reuse one PersistentClient."""
    # Evict any pre-existing cached entry for this path.
    chromadb_backend._clients.pop(tmp_storage, None)

    be = ChromaDBBackend()
    cid1 = f"kb_{uuid4().hex[:20]}"
    cid2 = f"kb_{uuid4().hex[:20]}"

    be.create_collection(
        collection_id=cid1,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    client_after_first = chromadb_backend._clients.get(tmp_storage)
    assert client_after_first is not None

    be.create_collection(
        collection_id=cid2,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    client_after_second = chromadb_backend._clients.get(tmp_storage)

    # Same object — no new client was created.
    assert client_after_second is client_after_first


def test_client_cache_different_paths(fake_embedding) -> None:
    """Different storage_paths produce different PersistentClient instances."""
    path_a = tempfile.mkdtemp(prefix="kbs-vdb-a-")
    path_b = tempfile.mkdtemp(prefix="kbs-vdb-b-")
    try:
        chromadb_backend._clients.pop(path_a, None)
        chromadb_backend._clients.pop(path_b, None)

        be = ChromaDBBackend()
        cid_a = f"kb_{uuid4().hex[:20]}"
        cid_b = f"kb_{uuid4().hex[:20]}"

        be.create_collection(
            collection_id=cid_a,
            storage_path=path_a,
            embedding_function=fake_embedding,
        )
        be.create_collection(
            collection_id=cid_b,
            storage_path=path_b,
            embedding_function=fake_embedding,
        )

        client_a = chromadb_backend._clients.get(path_a)
        client_b = chromadb_backend._clients.get(path_b)
        assert client_a is not None
        assert client_b is not None
        assert client_a is not client_b
    finally:
        # Clean up both paths (delete_collection evicts the cache entry).
        be.delete_collection(collection_id=cid_a, storage_path=path_a)
        be.delete_collection(collection_id=cid_b, storage_path=path_b)


# ---------------------------------------------------------------------------
# _to_chroma_ef adapter tests
# ---------------------------------------------------------------------------


def test_to_chroma_ef_native_path() -> None:
    """_to_chroma_ef always wraps in an adapter — no short-circuit for native CEFs.

    Even when the plugin internally holds a native ChromaEmbeddingFunction, the
    adapter layer is still created so our plugin's __call__ is used directly
    (avoids depending on old SDK-specific wrappers).
    """
    called_with: list = []

    class _WrapperEmbedding(EmbeddingFunction):
        name = "wrapper"
        description = "wrapper"

        def __init__(self):
            super().__init__(model="test-model")

        def __call__(self, input):
            called_with.append(input)
            return [[0.5, 0.5] for _ in input]

    wrapper = _WrapperEmbedding()
    result = _to_chroma_ef(wrapper)

    # Always an adapter — never the raw plugin itself.
    assert isinstance(result, ChromaEmbeddingFunction)
    assert result is not wrapper

    # The adapter delegates to wrapper.__call__.
    out = result(["hello", "world"])
    assert called_with == [["hello", "world"]]
    # Convert to plain lists in case chromadb wraps in numpy arrays.
    assert [list(v) for v in out] == [[0.5, 0.5], [0.5, 0.5]]


def test_to_chroma_ef_adapter_name(fake_embedding) -> None:
    """The adapter's ``name()`` method returns the plugin class's ``name`` attribute."""
    adapter = _to_chroma_ef(fake_embedding)
    # FakeEmbedding.name == "fake"; adapter must expose it via name().
    assert adapter.name() == "fake"


# ---------------------------------------------------------------------------
# add_chunks edge cases
# ---------------------------------------------------------------------------


def test_add_chunks_empty_list(tmp_storage: str, fake_embedding) -> None:
    """add_chunks with an empty list returns 0 without touching ChromaDB (line 172)."""
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
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


def test_add_chunks_batch_boundary(tmp_storage: str, fake_embedding) -> None:
    """101 chunks trigger two batches: 100 + 1. Total stored == 101."""
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    chunks = [
        Chunk(text=f"chunk text {i}", metadata={"source_item_id": "src", "chunk_index": i})
        for i in range(101)
    ]
    n = be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=chunks,
        embedding_function=fake_embedding,
    )
    assert n == 101

    # Verify ChromaDB actually stored all 101 documents.

    client = chromadb_backend._clients[tmp_storage]
    collection = client.get_collection(name=cid)
    assert collection.count() == 101


# ---------------------------------------------------------------------------
# delete_collection idempotency
# ---------------------------------------------------------------------------


def test_delete_collection_already_absent(tmp_storage: str, fake_embedding) -> None:
    """Deleting an already-absent collection does not raise (idempotent)."""
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)
    # Second delete — collection and directory are already gone.
    be.delete_collection(collection_id=cid, storage_path=tmp_storage)


# ---------------------------------------------------------------------------
# delete_by_source edge cases
# ---------------------------------------------------------------------------


def test_delete_by_source_no_match(tmp_storage: str, fake_embedding) -> None:
    """delete_by_source returns 0 when no chunks match the source (line 225)."""
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
            Chunk(text="hello", metadata={"source_item_id": "doc-z", "chunk_index": 0}),
        ],
        embedding_function=fake_embedding,
    )
    removed = be.delete_by_source(
        collection_id=cid,
        storage_path=tmp_storage,
        source_item_id="nonexistent-source",
    )
    assert removed == 0


# ---------------------------------------------------------------------------
# query edge cases
# ---------------------------------------------------------------------------


def test_query_score_clamped(tmp_storage: str, fake_embedding) -> None:
    """Query scores are always clamped to [0, 1] regardless of distance."""
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
            Chunk(text=f"document {i}", metadata={"source_item_id": "src", "chunk_index": i})
            for i in range(3)
        ],
        embedding_function=fake_embedding,
    )
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="completely unrelated query xyz",
        top_k=3,
        embedding_function=fake_embedding,
    )
    for r in results:
        assert 0.0 <= r.score <= 1.0


def test_query_top_k_exceeds_stored(tmp_storage: str, fake_embedding) -> None:
    """Querying with top_k > stored count returns only the stored count."""
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
            Chunk(text=f"item {i}", metadata={"source_item_id": "src", "chunk_index": i})
            for i in range(3)
        ],
        embedding_function=fake_embedding,
    )
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text="item",
        top_k=10,
        embedding_function=fake_embedding,
    )
    assert len(results) == 3


def test_query_no_parent_text_returns_chunk_text(tmp_storage: str, fake_embedding) -> None:
    """When parent_text is absent, query returns the raw chunk text unchanged."""
    be = ChromaDBBackend()
    cid = f"kb_{uuid4().hex[:20]}"
    be.create_collection(
        collection_id=cid,
        storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    chunk_text = "plain chunk without parent"
    be.add_chunks(
        collection_id=cid,
        storage_path=tmp_storage,
        chunks=[
            Chunk(
                text=chunk_text,
                metadata={"source_item_id": "doc-plain", "chunk_index": 0},
            ),
        ],
        embedding_function=fake_embedding,
    )
    results = be.query(
        collection_id=cid,
        storage_path=tmp_storage,
        query_text=chunk_text,
        top_k=1,
        embedding_function=fake_embedding,
    )
    assert results
    assert results[0].text == chunk_text
    assert "parent_text" not in results[0].metadata
