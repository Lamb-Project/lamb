"""Unit tests for ``GraphStore.ingest_chunks`` / ``_ingest_tx`` and the
``expand_from_concept_names`` graph-traversal seeding path.
"""

from __future__ import annotations

from services.concept_extraction import (
    ExtractedEntity,
    ExtractedRelationship,
    TextChunk,
)
from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


# ---------------------------------------------------------------------------
# ingest_chunks
# ---------------------------------------------------------------------------


def _chunk(cid="ch1", text="body", parent="parent", meta=None):
    return TextChunk(chunk_id=cid, text=text, parent_text=parent, metadata=meta or {})


def test_ingest_empty_chunks_returns_zero():
    store, sess = make_store()
    n = store.ingest_chunks(
        collection={"id": "c1"},
        file_id=1,
        filename="f.pdf",
        chunks=[],
        concepts_by_chunk={},
        entities={},
        relationships=[],
    )
    assert n == 0
    assert sess.runs == []


def test_ingest_schema_unavailable_returns_zero():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    n = store.ingest_chunks(
        collection={"id": "c1"},
        file_id=1,
        filename="f.pdf",
        chunks=[_chunk()],
        concepts_by_chunk={},
        entities={},
        relationships=[],
    )
    assert n == 0


def test_ingest_full_path_counts_and_writes():
    chunk = _chunk(
        meta={
            "permalink_original": "http://x/orig",
            "permalink_full_markdown": "http://x/md",
            "permalink_page": "http://x/p1",
            "section_title": "Intro",
            "source_label": "Chunk 1",
            "filename": "f.pdf",
        }
    )
    entities = {"alpha": ExtractedEntity(name="alpha", display_name="Alpha")}
    relationships = [
        ExtractedRelationship(source="alpha", target="beta", relation="uses")
    ]
    store, sess = make_store(
        config={"name": "Coll"},
    )
    n = store.ingest_chunks(
        collection={
            "id": "c1",
            "organization_id": "o1",
            "name": "Coll",
            "description": "Desc",
        },
        file_id=7,
        filename="f.pdf",
        chunks=[chunk],
        concepts_by_chunk={"ch1": ["alpha"]},
        entities=entities,
        relationships=relationships,
    )
    # 1 chunk + entity_map(alpha + beta from relationship) + 1 relationship + 1 event.
    assert n == 1 + 2 + 1 + 1
    # _ingest_tx issued multiple writes: org/coll/doc + 2 entities + chunk +
    # mention + relationship + event.
    assert len(sess.runs) == 1 + 2 + 1 + 1 + 1 + 1


def test_ingest_uses_owner_fallback_for_org_id():
    store, sess = make_store()
    n = store.ingest_chunks(
        collection={"id": "c1", "owner": "owner-org"},
        file_id=None,  # -> int(0)
        filename="f.pdf",
        chunks=[_chunk()],
        concepts_by_chunk={},
        entities={},
        relationships=[],
    )
    # 1 chunk + 0 entities + 0 rels + 1 = 2.
    assert n == 2
    # org/coll/doc write carries the owner fallback org id.
    assert sess.runs[0]["params"]["org_id"] == "owner-org"


# ---------------------------------------------------------------------------
# expand_from_concept_names
# ---------------------------------------------------------------------------


def test_expand_empty_names_returns_empty():
    store, sess = make_store()
    out = store.expand_from_concept_names("c1", "o1", ["", "  "], depth=2, limit=10)
    assert out["entry_concepts"] == []
    assert out["expanded_chunk_ids"] == []
    assert "graph_latency_ms" in out
    assert sess.runs == []  # returns before any query


def test_expand_schema_unavailable_warns():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.expand_from_concept_names("c1", "o1", ["Alpha"], depth=2, limit=10)
    assert out["entry_concepts"] == []
    assert any("KG expansion skipped" in c.get("warning", "")
               for c in out["latest_changes"])


def test_expand_no_entry_concepts():
    store, sess = make_store(responses=[FakeResult(rows=[])])  # matched empty
    out = store.expand_from_concept_names("c1", "o1", ["Alpha"], depth=2, limit=10)
    assert out["entry_concepts"] == []
    assert len(sess.runs) == 1


def test_expand_full_path_collects_chunks():
    responses = [
        FakeResult(rows=[{"name": "alpha", "mentions": 2}]),         # matched
        FakeResult(rows=[{"chunk_id": "ch1", "mentions": 5}]),        # direct
        FakeResult(rows=[{"chunk_id": "ch2"}, {"chunk_id": "ch1"}]),  # related (dedup)
    ]
    store, sess = make_store(responses=responses)
    out = store.expand_from_concept_names(
        "c1", "o1", ["Alpha"], depth=2, limit=10
    )
    assert out["entry_concepts"] == ["alpha"]
    # ch1 from direct, ch2 from related; ch1 deduped on second appearance.
    assert out["expanded_chunk_ids"] == ["ch1", "ch2"]
    assert len(sess.runs) == 3


def test_expand_clamps_depth_and_limit():
    responses = [
        FakeResult(rows=[{"name": "alpha", "mentions": 1}]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
    ]
    store, sess = make_store(responses=responses)
    # Negative limit exercises the max(1, ...) lower clamp; depth=99 clamps to 4
    # (interpolated into the related-query string).
    store.expand_from_concept_names("c1", "o1", ["Alpha"], depth=99, limit=-5)
    assert sess.runs[1]["params"]["limit"] == 1
    assert "RELATES_TO*1..4" in sess.runs[2]["query"]
