"""Unit tests for ``GraphStore.revert_change`` and its automatic-ingestion
unit-of-work ``_revert_change_tx``.

The transaction issues a deterministic sequence of ``tx.run`` calls; we
program the fake session's response queue to match and assert each guard
branch plus the full revert path (weight decrement, document/chunk deletion,
orphan cleanup, and the audit ``revert_change`` event).
"""

from __future__ import annotations

import json

from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


def test_revert_returns_unavailable_when_schema_down():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.revert_change("c1", "o1", "e1")
    assert out == {"reverted": False, "reason": "neo4j_not_available"}


def test_revert_change_not_found():
    store, _ = make_store(responses=[FakeResult(single=None)])
    out = store.revert_change("c1", "o1", "missing")
    assert out["reverted"] is False
    assert out["reason"] == "change_not_found"


def test_revert_unsupported_operation():
    event_row = {
        "operation": "manual_rename_concept",
        "filename": "",
        "concepts": [],
        "payload_json": "{}",
        "document_id": None,
    }
    store, _ = make_store(responses=[FakeResult(single=event_row)])
    out = store.revert_change("c1", "o1", "e1")
    assert out["reason"] == "unsupported_operation"
    assert out["operation"] == "manual_rename_concept"


def test_revert_automatic_ingestion_without_document():
    event_row = {
        "operation": "automatic_ingestion",
        "filename": "doc.pdf",
        "concepts": ["alpha"],
        "payload_json": "{}",
        "document_id": None,
    }
    store, _ = make_store(responses=[FakeResult(single=event_row)])
    out = store.revert_change("c1", "o1", "e1")
    assert out["reason"] == "change_has_no_document"


def test_revert_automatic_ingestion_full_path():
    payload = json.dumps(
        {
            "relationship_details": [
                {"source": "alpha", "target": "beta", "relation": "uses",
                 "confidence": 1.0},
                "not-a-dict",  # skipped by the loop
            ]
        }
    )
    event_row = {
        "operation": "automatic_ingestion",
        "filename": "doc.pdf",
        "concepts": ["alpha", "beta"],
        "payload_json": payload,
        "document_id": "d1",
    }
    responses = [
        FakeResult(single=event_row),                       # event lookup
        FakeResult(single={"chunk_ids": ["chunk-1", "chunk-2"]}),  # chunk ids
        FakeResult(),                                        # relationship decrement
        FakeResult(),                                        # delete doc + chunks
        FakeResult(),                                        # orphan concept cleanup
        FakeResult(single={"revert_event_id": "rev-1"}),     # audit event
    ]
    store, sess = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1", actor="me", reason="oops")
    assert out["reverted"] is True
    assert out["operation"] == "automatic_ingestion"
    assert out["document_id"] == "d1"
    assert out["chunk_ids"] == ["chunk-1", "chunk-2"]
    assert out["revert_event_id"] == "rev-1"
    # event + chunk + 1 relationship + delete + orphan + audit = 6 runs.
    assert len(sess.runs) == 6


def test_revert_full_path_uses_relationships_key_fallback():
    # No "relationship_details"; the tx falls back to "relationships".
    payload = json.dumps(
        {"relationships": [{"source": "a", "target": "b", "relation": "rel"}]}
    )
    event_row = {
        "operation": "automatic_ingestion",
        "filename": "doc.pdf",
        "concepts": [],
        "payload_json": payload,
        "document_id": "d1",
    }
    responses = [
        FakeResult(single=event_row),
        FakeResult(single=None),  # chunk row None -> chunk_ids == []
        FakeResult(),             # relationship decrement
        FakeResult(),             # delete
        FakeResult(),             # orphan
        FakeResult(single=None),  # audit event row None -> revert_event_id None
    ]
    store, _ = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1")
    assert out["reverted"] is True
    assert out["chunk_ids"] == []
    assert out["revert_event_id"] is None


def test_revert_bad_payload_json_is_tolerated():
    event_row = {
        "operation": "automatic_ingestion",
        "filename": "doc.pdf",
        "concepts": [],
        "payload_json": "not-json{",
        "document_id": "d1",
    }
    responses = [
        FakeResult(single=event_row),
        FakeResult(single={"chunk_ids": []}),
        FakeResult(),  # delete (no relationships to decrement)
        FakeResult(),  # orphan
        FakeResult(single={"revert_event_id": "rev-9"}),
    ]
    store, _ = make_store(responses=responses)
    out = store.revert_change("c1", "o1", "e1")
    assert out["reverted"] is True
    assert out["revert_event_id"] == "rev-9"
