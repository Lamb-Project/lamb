"""Unit tests for ``GraphStore`` concept rename/merge curation operations.

These exercise ``rename_concept`` / ``merge_concepts`` and, through them, the
shared ``_move_concept_in_collection_tx`` (7 Cypher writes) and
``_manual_change_event_tx`` audit-event helper.
"""

from __future__ import annotations

from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


def _move_responses(*, source_found=True, counts=None, event_id="evt-1"):
    """Response queue for one successful _move + audit event.

    _move issues: source lookup, MERGE target, removed_between, mentions,
    outgoing, incoming, deleted_source. Then the caller records an event.
    """
    counts = counts or {}
    if not source_found:
        return [FakeResult(single=None)]
    return [
        FakeResult(single={
            "name": "alpha", "old_notes": None, "old_tags": None,
            "old_verification_state": None,
        }),
        FakeResult(),  # MERGE target
        FakeResult(single={"count": counts.get("removed_between", 0)}),
        FakeResult(single={"count": counts.get("mentions", 3)}),
        FakeResult(single={"count": counts.get("outgoing", 1)}),
        FakeResult(single={"count": counts.get("incoming", 2)}),
        FakeResult(single={"count": counts.get("deleted_source", 1)}),
    ] + ([FakeResult(single={"event_id": event_id})] if event_id else [])


# ---------------------------------------------------------------------------
# rename_concept
# ---------------------------------------------------------------------------


def test_rename_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.rename_concept("c1", "o1", "Old", "New")
    assert out == {"ok": False, "reason": "neo4j_not_available"}


def test_rename_invalid_name():
    store, sess = make_store(responses=[])
    out = store.rename_concept("c1", "o1", "!!!", "New")
    assert out["reason"] == "invalid_concept_name"
    assert sess.runs == []


def test_rename_equal_names():
    store, _ = make_store(responses=[])
    out = store.rename_concept("c1", "o1", "Same Name", "same name")
    assert out["reason"] == "concept_names_are_equal"


def test_rename_source_not_found():
    store, sess = make_store(responses=_move_responses(source_found=False))
    out = store.rename_concept("c1", "o1", "Old Name", "New Name")
    assert out["ok"] is False
    assert out["reason"] == "source_concept_not_found"
    assert len(sess.runs) == 1


def test_rename_success():
    store, sess = make_store(
        responses=_move_responses(counts={"mentions": 5}, event_id="evt-9")
    )
    out = store.rename_concept("c1", "o1", "Old Name", "New Name", reason="cleanup")
    assert out["ok"] is True
    assert out["operation"] == "manual_rename_concept"
    assert out["event_id"] == "evt-9"
    assert out["details"]["mentions"] == 5
    # 7 move writes + 1 audit event.
    assert len(sess.runs) == 8


# ---------------------------------------------------------------------------
# merge_concepts
# ---------------------------------------------------------------------------


def test_merge_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.merge_concepts("c1", "o1", ["a"], "b")
    assert out == {"ok": False, "reason": "neo4j_not_available"}


def test_merge_invalid_request_no_sources():
    store, sess = make_store(responses=[])
    # Only source equals target after normalization -> nothing to merge.
    out = store.merge_concepts("c1", "o1", ["Target"], "Target")
    assert out["reason"] == "invalid_merge_request"
    assert sess.runs == []


def test_merge_invalid_request_empty_target():
    store, _ = make_store(responses=[])
    out = store.merge_concepts("c1", "o1", ["a"], "!!!")
    assert out["reason"] == "invalid_merge_request"


def test_merge_all_sources_missing():
    store, sess = make_store(responses=_move_responses(source_found=False))
    out = store.merge_concepts("c1", "o1", ["Ghost"], "Target")
    assert out["ok"] is False
    assert out["reason"] == "source_concepts_not_found"
    assert out["missing"] == ["ghost"]


def test_merge_success_one_source():
    store, sess = make_store(
        responses=_move_responses(counts={"mentions": 4}, event_id="merge-evt")
    )
    out = store.merge_concepts("c1", "o1", ["Source One"], "Target", reason="dedupe")
    assert out["ok"] is True
    assert out["operation"] == "manual_merge_concepts"
    assert out["event_id"] == "merge-evt"
    assert out["details"]["target"] == "target"
    assert len(out["details"]["moved"]) == 1
    # 7 move writes + 1 audit event.
    assert len(sess.runs) == 8


def test_merge_partial_missing_source_still_succeeds():
    # First source moves; second source is missing -> still ok overall.
    responses = (
        _move_responses(event_id=None)  # first source: 7 writes, no event yet
        + [FakeResult(single=None)]      # second source: not found (1 write)
        + [FakeResult(single={"event_id": "merge-evt"})]  # audit event
    )
    store, sess = make_store(responses=responses)
    out = store.merge_concepts(
        "c1", "o1", ["First Source", "Second Source"], "Target"
    )
    assert out["ok"] is True
    assert out["details"]["missing"] == ["second source"]
    assert len(out["details"]["moved"]) == 1
