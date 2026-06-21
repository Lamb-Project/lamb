"""Unit tests for ``GraphStore.get_collection_graph`` (the snapshot builder).

The method issues up to five sequential Cypher reads:
  1. concepts, 2. per-collection verification states, 3. documents,
  4. relationships, 5. chunks (only when ``include_chunks``).
We program the fake session's response queue in that order and assert the
node/edge assembly, counts, filter echo, and the early-return branches.
"""

from __future__ import annotations

from services.graph_store import GraphStore
from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


def _concept(name, display=None, **extra):
    row = {
        "name": name,
        "display_name": display or name.title(),
        "entity_type": "concept",
        "description": f"about {name}",
        "confidence": 0.9,
        "notes": "",
        "tags": [],
        "chunk_count": 1,
    }
    row.update(extra)
    return row


def test_snapshot_returns_empty_when_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.get_collection_graph("c1", "o1", concept="Alpha", limit=10)
    assert out["nodes"] == [] and out["edges"] == []
    assert out["counts"] == {"concepts": 0, "documents": 0, "chunks": 0, "edges": 0}
    # Filters echo the request even on the empty path.
    assert out["filters"]["concept"] == "Alpha"
    assert out["filters"]["limit"] == 10


def test_snapshot_empty_when_no_concepts_match():
    store, sess = make_store(responses=[FakeResult(rows=[])])  # concept query empty
    out = store.get_collection_graph("c1", "o1")
    assert out["counts"]["concepts"] == 0
    # Only the concept query ran; it short-circuits before verification query.
    assert len(sess.runs) == 1


def test_snapshot_full_path_with_chunks():
    concepts = [_concept("alpha"), _concept("beta")]
    coll_vs = [{"name": "alpha", "vs": "verified"}, {"name": "beta", "vs": None}]
    documents = [
        {
            "document_id": "d1",
            "filename": "doc.pdf",
            "file_id": 7,
            "chunk_count": 2,
            "concepts": ["alpha", "beta"],
        },
        # row with missing document_id -> skipped during node assembly.
        {"document_id": None, "filename": "ghost", "chunk_count": 0, "concepts": []},
    ]
    relationships = [
        {
            "source": "alpha",
            "target": "beta",
            "type": "RELATES_TO",
            "relation": "uses",
            "weight": 2.0,
            "description": "d",
            "evidence": "e",
            "chunk_id": "chunk-1",
            "notes": "",
            "tags": [],
            "verification_state": "verified",
        }
    ]
    chunks = [
        {
            "chunk_id": "chunk-1",
            "source_label": "Chunk 1",
            "filename": "doc.pdf",
            "document_id": "d1",
            "text_preview": "preview",
            "permalink_original": "",
            "permalink_full_markdown": "",
            "permalink_page": "",
            "concepts": ["alpha"],
        },
        # missing chunk_id -> skipped.
        {"chunk_id": None, "concepts": []},
    ]
    store, sess = make_store(
        responses=[
            FakeResult(rows=concepts),
            FakeResult(rows=coll_vs),
            FakeResult(rows=documents),
            FakeResult(rows=relationships),
            FakeResult(rows=chunks),
        ]
    )
    out = store.get_collection_graph("c1", "o1", include_chunks=True)

    node_ids = {n["id"] for n in out["nodes"]}
    assert "concept:alpha" in node_ids
    assert "concept:beta" in node_ids
    assert "document:d1" in node_ids
    assert "chunk:chunk-1" in node_ids

    edge_ids = {e["id"] for e in out["edges"]}
    assert "relationship:alpha:uses:beta" in edge_ids
    assert "mention:chunk-1:alpha" in edge_ids
    assert "contains:d1:chunk-1" in edge_ids

    # verification_state for alpha comes from the per-collection map.
    alpha = next(n for n in out["nodes"] if n["id"] == "concept:alpha")
    assert alpha["data"]["verification_state"] == "verified"
    beta = next(n for n in out["nodes"] if n["id"] == "concept:beta")
    assert beta["data"]["verification_state"] == "unverified"

    assert out["counts"]["concepts"] == 2
    assert out["counts"]["documents"] == 2  # both rows counted (len)
    assert out["counts"]["chunks"] == 2
    assert len(sess.runs) == 5


def test_snapshot_rejected_concept_is_filtered_out():
    concepts = [_concept("alpha"), _concept("beta")]
    coll_vs = [{"name": "alpha", "vs": "verified"}, {"name": "beta", "vs": "rejected"}]
    store, _ = make_store(
        responses=[
            FakeResult(rows=concepts),
            FakeResult(rows=coll_vs),
            FakeResult(rows=[]),  # documents
            FakeResult(rows=[]),  # relationships
            FakeResult(rows=[]),  # chunks
        ]
    )
    out = store.get_collection_graph("c1", "o1", include_chunks=True)
    node_ids = {n["id"] for n in out["nodes"]}
    assert "concept:alpha" in node_ids
    assert "concept:beta" not in node_ids  # rejected in this collection
    assert out["counts"]["concepts"] == 1


def test_snapshot_without_chunks_builds_document_mention_edges():
    concepts = [_concept("alpha")]
    coll_vs = [{"name": "alpha", "vs": "verified"}]
    documents = [
        {
            "document_id": "d1",
            "filename": "doc.pdf",
            "file_id": 1,
            "chunk_count": 1,
            "concepts": ["alpha"],
        }
    ]
    store, sess = make_store(
        responses=[
            FakeResult(rows=concepts),
            FakeResult(rows=coll_vs),
            FakeResult(rows=documents),
            FakeResult(rows=[]),  # relationships
        ]
    )
    out = store.get_collection_graph("c1", "o1", include_chunks=False)
    # No chunk query issued.
    assert len(sess.runs) == 4
    edge_ids = {e["id"] for e in out["edges"]}
    assert "document-mention:d1:alpha" in edge_ids
    assert out["filters"]["include_chunks"] is False
    assert out["counts"]["chunks"] == 0
