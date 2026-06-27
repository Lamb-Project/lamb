"""Functional tests for ``ChromaDBBackend`` lookup / query / iteration methods.

Uses a real ``PersistentClient`` over a temp dir with the deterministic
``FakeEmbedding`` — covering ``query`` (incl. parent-text rewrite),
``get_chunks_by_id``, ``get_chunks_by_source``, ``delete_by_source``,
``iter_all_chunks``, and the embedding-adapter / add_chunks error paths.
"""

from __future__ import annotations

import pytest

from plugins.base import Chunk
from plugins.vector_db.chromadb_backend import ChromaDBBackend


@pytest.fixture
def populated(tmp_storage, fake_embedding):
    """A collection with three chunks (two sharing a source_item_id)."""
    be = ChromaDBBackend()
    cid = "kb_lookup_test"
    be.create_collection(
        collection_id=cid, storage_path=tmp_storage, embedding_function=fake_embedding
    )
    chunks = [
        Chunk(text="alpha doc one", metadata={
            "source_item_id": "src-1", "parent_text": "PARENT ONE"}),
        Chunk(text="alpha doc two", metadata={"source_item_id": "src-1"}),
        Chunk(text="beta document", metadata={"source_item_id": "src-2"}),
    ]
    be.add_chunks(
        collection_id=cid, storage_path=tmp_storage, chunks=chunks,
        embedding_function=fake_embedding,
    )
    return be, cid, tmp_storage, fake_embedding


def test_query_returns_results_with_chunk_id_and_parent_text(populated):
    be, cid, path, ef = populated
    results = be.query(
        collection_id=cid, storage_path=path, query_text="alpha doc one",
        top_k=3, embedding_function=ef,
    )
    assert results
    # The backend surfaces the internal chunk id on every result.
    assert results[0].metadata.get("chunk_id")
    # The chunk stored with parent_text returns the parent as its text.
    parent_hit = [r for r in results if r.text == "PARENT ONE"]
    assert parent_hit, "parent_text should be surfaced as the result text"


def test_get_chunks_by_source(populated):
    be, cid, path, ef = populated
    rows = be.get_chunks_by_source(
        collection_id=cid, storage_path=path, source_item_id="src-1",
        embedding_function=ef,
    )
    assert len(rows) == 2
    assert all(r.score == 0.72 for r in rows)
    assert all(r.metadata.get("chunk_id") for r in rows)
    # Unknown source -> empty.
    assert be.get_chunks_by_source(
        collection_id=cid, storage_path=path, source_item_id="nope",
        embedding_function=ef,
    ) == []


def test_get_chunks_by_id_roundtrip_and_parent(populated):
    be, cid, path, ef = populated
    # First grab real chunk ids via a source lookup.
    src_rows = be.get_chunks_by_source(
        collection_id=cid, storage_path=path, source_item_id="src-1",
        embedding_function=ef,
    )
    ids = [r.metadata["chunk_id"] for r in src_rows]
    out = be.get_chunks_by_id(
        collection_id=cid, storage_path=path, chunk_ids=ids, embedding_function=ef,
    )
    assert len(out) == 2
    assert all(r.score == 0.72 for r in out)
    # document_id is defaulted to the chunk id.
    assert all(r.metadata.get("document_id") for r in out)
    # The chunk that had parent_text returns it as text (popped from metadata).
    assert any(r.text == "PARENT ONE" for r in out)


def test_get_chunks_by_id_empty_and_error(populated, tmp_storage, fake_embedding):
    be, cid, path, ef = populated
    assert be.get_chunks_by_id(
        collection_id=cid, storage_path=path, chunk_ids=[], embedding_function=ef,
    ) == []
    # Unknown collection -> the except branch returns [].
    assert be.get_chunks_by_id(
        collection_id="does-not-exist", storage_path=path, chunk_ids=["x"],
        embedding_function=ef,
    ) == []


def test_get_chunks_by_source_error(populated):
    be, _cid, path, ef = populated
    assert be.get_chunks_by_source(
        collection_id="missing", storage_path=path, source_item_id="src-1",
        embedding_function=ef,
    ) == []


def test_delete_by_source_counts(populated):
    be, cid, path, ef = populated
    deleted = be.delete_by_source(
        collection_id=cid, storage_path=path, source_item_id="src-1",
    )
    assert deleted == 2
    # Deleting again finds nothing.
    assert be.delete_by_source(
        collection_id=cid, storage_path=path, source_item_id="src-1",
    ) == 0


def test_iter_all_chunks_paginates(populated):
    be, cid, path, ef = populated
    batches = list(be.iter_all_chunks(
        collection_id=cid, storage_path=path, embedding_function=ef, batch_size=2,
    ))
    total = sum(len(ids) for ids, _texts, _metas in batches)
    assert total == 3
    # batch_size=2 over 3 chunks -> at least two batches.
    assert len(batches) >= 2


def test_delete_absent_collection_when_dir_exists(tmp_storage, fake_embedding):
    # Create one collection so the client + dir exist, then delete a DIFFERENT
    # (non-existent) collection name -> the fast-path guard is bypassed and the
    # NotFoundError "already absent" branch is exercised.
    be = ChromaDBBackend()
    be.create_collection(
        collection_id="kb_present", storage_path=tmp_storage,
        embedding_function=fake_embedding,
    )
    # Must not raise.
    be.delete_collection(collection_id="kb_absent", storage_path=tmp_storage)


def test_add_chunks_empty_is_noop(tmp_storage, fake_embedding):
    be = ChromaDBBackend()
    cid = "kb_empty"
    be.create_collection(
        collection_id=cid, storage_path=tmp_storage, embedding_function=fake_embedding
    )
    assert be.add_chunks(
        collection_id=cid, storage_path=tmp_storage, chunks=[],
        embedding_function=fake_embedding,
    ) == 0


def test_add_chunks_embedding_error_wrapped(tmp_storage):
    """An embedding function that raises surfaces as a clean RuntimeError."""
    from plugins.base import EmbeddingFunction

    class _BoomEmbedding(EmbeddingFunction):
        name = "boom"

        def __init__(self):
            super().__init__(model="boom")

        def __call__(self, input):
            raise ValueError("embedding backend exploded")

    be = ChromaDBBackend()
    cid = "kb_boom"
    boom = _BoomEmbedding()
    be.create_collection(
        collection_id=cid, storage_path=tmp_storage, embedding_function=boom
    )
    with pytest.raises(RuntimeError):
        be.add_chunks(
            collection_id=cid, storage_path=tmp_storage,
            chunks=[Chunk(text="x", metadata={"source_item_id": "s"})],
            embedding_function=boom,
        )
