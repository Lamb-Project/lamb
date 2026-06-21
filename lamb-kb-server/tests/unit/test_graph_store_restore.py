"""Unit tests for ``GraphStore`` expunge-restore reverts and remaining guards.

When ``revert_change`` targets a ``manual_expunge_relationship`` or
``manual_expunge_concept`` event, it delegates into the restore unit-of-work
helpers (``_restore_relationship_payload_tx``, ``_restore_concept_node_tx``,
``_restore_expunged_*_tx``, ``_create_revert_event_tx``). These tests drive
those paths and also close a few residual guard branches.
"""

from __future__ import annotations

import json

from services.graph_store import GraphStore
from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


# ---------------------------------------------------------------------------
# _relationship_restore_weight (pure)
# ---------------------------------------------------------------------------


def test_relationship_restore_weight():
    assert GraphStore._relationship_restore_weight(2.5) == 2.5
    assert GraphStore._relationship_restore_weight(None) == 1.0
    assert GraphStore._relationship_restore_weight("not-a-number") == 1.0


# ---------------------------------------------------------------------------
# revert of manual_expunge_relationship
# ---------------------------------------------------------------------------


def test_revert_expunged_relationship_success():
    payload = {
        "source": "alpha",
        "target": "beta",
        "relation": "uses",
        "old_weight": 2.0,
        "old_description": "d",
        "old_evidence": "e",
        "old_chunk_id": "ch1",
        "old_notes": "n",
        "old_tags": ["t"],
    }
    event_row = {
        "operation": "manual_expunge_relationship",
        "filename": "f.pdf",
        "concepts": ["alpha", "beta"],
        "payload_json": json.dumps(payload),
        "document_id": None,
    }
    responses = [
        FakeResult(single=event_row),         # event lookup
        FakeResult(),                          # restore source Concept
        FakeResult(),                          # restore target Concept
        FakeResult(),                          # MERGE relationship
        FakeResult(single={"revert_event_id": "rev-1"}),  # audit revert event
    ]
    store, sess = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1", reason="undo")
    assert out["reverted"] is True
    assert out["operation"] == "manual_expunge_relationship"
    assert out["revert_event_id"] == "rev-1"
    assert out["chunk_ids"] == []
    assert len(sess.runs) == 5


def test_revert_expunged_relationship_invalid_payload():
    # Empty source -> restore returns None -> invalid_expunge_payload.
    payload = {"source": "", "target": "beta", "relation": "uses"}
    event_row = {
        "operation": "manual_expunge_relationship",
        "filename": "f.pdf",
        "concepts": [],
        "payload_json": json.dumps(payload),
        "document_id": None,
    }
    responses = [
        FakeResult(single=event_row),  # event lookup
        FakeResult(),                  # restore target Concept (source skipped)
    ]
    store, _ = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1")
    assert out["reverted"] is False
    assert out["reason"] == "invalid_expunge_payload"


# ---------------------------------------------------------------------------
# revert of manual_expunge_concept
# ---------------------------------------------------------------------------


def test_revert_expunged_concept_success():
    payload = {
        "concept": "alpha",
        "old_notes": "n",
        "old_tags": ["t"],
        "removed_chunk_mentions": ["ch1", "ch2"],
        "removed_relationships": [
            {"source": "alpha", "target": "beta", "relation": "uses"},
            "not-a-dict",  # skipped
        ],
    }
    event_row = {
        "operation": "manual_expunge_concept",
        "filename": "f.pdf",
        "concepts": ["alpha"],
        "payload_json": json.dumps(payload),
        "document_id": None,
    }
    responses = [
        FakeResult(single=event_row),  # event lookup
        FakeResult(),                  # restore concept node
        FakeResult(),                  # restore chunk mention ch1
        FakeResult(),                  # restore chunk mention ch2
        FakeResult(),                  # restore rel: source node
        FakeResult(),                  # restore rel: target node
        FakeResult(),                  # restore rel: MERGE relationship
        FakeResult(single={"revert_event_id": "rev-2"}),  # audit revert event
    ]
    store, sess = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1")
    assert out["reverted"] is True
    assert out["operation"] == "manual_expunge_concept"
    assert out["chunk_ids"] == ["ch1", "ch2"]
    assert out["revert_event_id"] == "rev-2"
    assert len(sess.runs) == 8


def test_revert_expunged_concept_skips_unrestorable_relationship():
    # A removed relationship whose source is empty cannot be restored and is
    # skipped (the ``if restored:`` false branch).
    payload = {
        "concept": "alpha",
        "removed_chunk_mentions": [],
        "removed_relationships": [
            {"source": "", "target": "beta", "relation": "uses"},  # unrestorable
        ],
    }
    event_row = {
        "operation": "manual_expunge_concept",
        "filename": "f.pdf",
        "concepts": ["alpha"],
        "payload_json": json.dumps(payload),
        "document_id": None,
    }
    responses = [
        FakeResult(single=event_row),  # event lookup
        FakeResult(),                  # restore concept node
        FakeResult(),                  # restore rel: target node (source skipped)
        FakeResult(single={"revert_event_id": "rev-3"}),  # audit event
    ]
    store, _ = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1")
    assert out["reverted"] is True
    assert out["chunk_ids"] == []


def test_revert_expunged_concept_invalid_payload():
    # No concept name available -> restore returns "" -> invalid_expunge_payload.
    payload = {"concept": ""}
    event_row = {
        "operation": "manual_expunge_concept",
        "filename": "f.pdf",
        "concepts": [""],
        "payload_json": json.dumps(payload),
        "document_id": None,
    }
    store, _ = make_store(responses=[FakeResult(single=event_row)])
    out = store.revert_change("c1", "o1", "e1")
    assert out["reverted"] is False
    assert out["reason"] == "invalid_expunge_payload"


# ---------------------------------------------------------------------------
# residual guard branches
# ---------------------------------------------------------------------------


def test_delete_document_aborts_when_schema_not_ready():
    # is_configured() is True (make_store sets uri/password) but the schema
    # bootstrap fails -> early return at the ensure_schema guard.
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, sess = make_store(driver=driver, schema_ready=False)
    store.delete_document("c1", "o1", "doc.pdf")
    assert sess.runs == []


def test_snapshot_without_chunks_skips_document_missing_id():
    concepts = [{
        "name": "alpha", "display_name": "Alpha", "entity_type": "concept",
        "description": "", "confidence": 0.9, "notes": "", "tags": [],
        "chunk_count": 1,
    }]
    coll_vs = [{"name": "alpha", "vs": "verified"}]
    documents = [
        {"document_id": None, "filename": "ghost", "chunk_count": 0,
         "concepts": ["alpha"]},  # skipped in document-mention loop
    ]
    store, _ = make_store(
        responses=[
            FakeResult(rows=concepts),
            FakeResult(rows=coll_vs),
            FakeResult(rows=documents),
            FakeResult(rows=[]),  # relationships
        ]
    )
    out = store.get_collection_graph("c1", "o1", include_chunks=False)
    # No document-mention edges were produced (the only doc had no id).
    assert all(not e["id"].startswith("document-mention:") for e in out["edges"])
