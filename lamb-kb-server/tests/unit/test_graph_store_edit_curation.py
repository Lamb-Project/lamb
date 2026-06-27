"""Unit tests for ``GraphStore`` relationship-edit and concept-curation paths,
plus the pure change-detection helpers they rely on.
"""

from __future__ import annotations

from services.graph_store import GraphStore
from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


# ---------------------------------------------------------------------------
# pure change-detection helpers
# ---------------------------------------------------------------------------


def test_optional_text_changed():
    assert GraphStore._optional_text_changed("a", None) is False  # None = no request
    assert GraphStore._optional_text_changed("a", "a") is False
    assert GraphStore._optional_text_changed("a", "b") is True
    assert GraphStore._optional_text_changed(None, "") is False


def test_optional_tags_changed():
    assert GraphStore._optional_tags_changed(["a"], None) is False
    assert GraphStore._optional_tags_changed(["a"], ["a"]) is False
    assert GraphStore._optional_tags_changed(["a"], ["a", "b"]) is True
    assert GraphStore._optional_tags_changed(None, []) is False


def test_optional_weight_changed():
    assert GraphStore._optional_weight_changed(1.0, None) is False
    assert GraphStore._optional_weight_changed(1.0, 1.0) is False
    assert GraphStore._optional_weight_changed(1.0, 2.0) is True
    # None current defaults to 1.0.
    assert GraphStore._optional_weight_changed(None, 1.0) is False
    # Non-numeric falls back to equality comparison.
    assert GraphStore._optional_weight_changed("x", "x") is False


def test_optional_state_changed():
    assert GraphStore._optional_state_changed("verified", None) is False
    assert GraphStore._optional_state_changed(None, "unverified") is False  # default
    assert GraphStore._optional_state_changed("unverified", "verified") is True


def test_relationship_update_has_changes():
    base = {
        "old_weight": 1.0,
        "old_description": "d",
        "old_evidence": "e",
        "old_notes": "n",
        "old_tags": ["t"],
        "old_verification_state": "verified",
    }
    # Relation change alone -> True.
    assert GraphStore._relationship_update_has_changes(
        base, current_relation="uses", target_relation="depends_on",
        weight=None, description=None, evidence=None, notes=None, tags=None,
        verification_state=None,
    )
    # Nothing changes -> False.
    assert not GraphStore._relationship_update_has_changes(
        base, current_relation="uses", target_relation="uses",
        weight=None, description=None, evidence=None, notes=None, tags=None,
        verification_state=None,
    )


def test_concept_update_has_changes():
    row = {"old_notes": "n", "old_tags": ["t"], "old_verification_state": "verified"}
    assert GraphStore._concept_update_has_changes(
        row, notes="new", tags=None, verification_state=None
    )
    assert not GraphStore._concept_update_has_changes(
        row, notes=None, tags=None, verification_state=None
    )


# ---------------------------------------------------------------------------
# edit_relationship
# ---------------------------------------------------------------------------


def _rel_row(**over):
    row = {
        "old_weight": 1.0,
        "old_description": "d",
        "old_evidence": "e",
        "old_chunk_id": "ch1",
        "old_notes": "n",
        "old_tags": ["t"],
        "old_verification_state": "verified",
    }
    row.update(over)
    return row


def test_edit_relationship_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.edit_relationship(
        "c1", "o1", source_name="a", target_name="b", relation="uses"
    )
    assert out == {"ok": False, "reason": "neo4j_not_available"}


def test_edit_relationship_invalid_identity():
    store, sess = make_store(responses=[])
    out = store.edit_relationship(
        "c1", "o1", source_name="!!!", target_name="b", relation="uses"
    )
    assert out["reason"] == "invalid_relationship_identity"
    assert sess.runs == []


def test_edit_relationship_not_found():
    store, _ = make_store(responses=[FakeResult(single=None)])
    out = store.edit_relationship(
        "c1", "o1", source_name="a", target_name="b", relation="uses"
    )
    assert out["reason"] == "relationship_not_found"


def test_edit_relationship_rejected_expunges():
    responses = [
        FakeResult(single=_rel_row()),         # rel lookup
        FakeResult(single={"event_id": "ev"}),  # audit event
        FakeResult(),                            # delete relationship
    ]
    store, sess = make_store(responses=responses)
    out = store.edit_relationship(
        "c1", "o1", source_name="Alpha", target_name="Beta", relation="uses",
        verification_state="rejected",
    )
    assert out["ok"] is True
    assert out["operation"] == "manual_expunge_relationship"
    assert out["details"]["expunged"] is True
    assert len(sess.runs) == 3


def test_edit_relationship_no_change():
    store, sess = make_store(responses=[FakeResult(single=_rel_row())])
    out = store.edit_relationship(
        "c1", "o1", source_name="Alpha", target_name="Beta", relation="uses",
    )
    assert out["reason"] == "no_change"
    assert out["details"]["changed"] is False
    assert len(sess.runs) == 1


def test_edit_relationship_same_relation_update():
    responses = [
        FakeResult(single=_rel_row()),          # rel lookup
        FakeResult(),                            # SET update
        FakeResult(single={"event_id": "ev2"}),  # audit event
    ]
    store, sess = make_store(responses=responses)
    out = store.edit_relationship(
        "c1", "o1", source_name="Alpha", target_name="Beta", relation="uses",
        weight=5.0,
    )
    assert out["ok"] is True
    assert out["operation"] == "manual_edit_relationship"
    assert out["event_id"] == "ev2"
    assert out["details"]["new_relation"] == "uses"
    assert len(sess.runs) == 3


def test_edit_relationship_changed_relation_recreates():
    responses = [
        FakeResult(single=_rel_row()),          # rel lookup
        FakeResult(),                            # MERGE new + DELETE old
        FakeResult(single={"event_id": "ev3"}),  # audit event
    ]
    store, sess = make_store(responses=responses)
    out = store.edit_relationship(
        "c1", "o1", source_name="Alpha", target_name="Beta", relation="uses",
        new_relation="depends on",
    )
    assert out["ok"] is True
    assert out["details"]["old_relation"] == "uses"
    assert out["details"]["new_relation"] == "depends_on"


# ---------------------------------------------------------------------------
# update_concept_curation
# ---------------------------------------------------------------------------


def _concept_row(**over):
    row = {
        "name": "alpha",
        "old_notes": "n",
        "old_tags": ["t"],
        "old_verification_state": "verified",
    }
    row.update(over)
    return row


def test_curation_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    out = store.update_concept_curation("c1", "o1", "Alpha")
    assert out == {"ok": False, "reason": "neo4j_not_available"}


def test_curation_invalid_name():
    store, sess = make_store(responses=[])
    out = store.update_concept_curation("c1", "o1", "!!!")
    assert out["reason"] == "invalid_concept_name"
    assert sess.runs == []


def test_curation_concept_not_found():
    store, _ = make_store(responses=[FakeResult(single=None)])
    out = store.update_concept_curation("c1", "o1", "Alpha", notes="x")
    assert out["reason"] == "concept_not_found"


def test_curation_no_change():
    # notes/tags/state all None -> no change.
    store, sess = make_store(responses=[FakeResult(single=_concept_row())])
    out = store.update_concept_curation("c1", "o1", "Alpha")
    assert out["reason"] == "no_change"
    assert len(sess.runs) == 1


def test_curation_notes_only_update():
    responses = [
        FakeResult(single=_concept_row(old_notes="old")),  # concept lookup
        FakeResult(),                                        # SET notes/tags
        FakeResult(single={"event_id": "ce"}),               # audit event
    ]
    store, sess = make_store(responses=responses)
    out = store.update_concept_curation("c1", "o1", "Alpha", notes="new notes")
    assert out["ok"] is True
    assert out["operation"] == "manual_curate_concept"
    assert len(sess.runs) == 3


def test_curation_verified_promotes_org_node():
    responses = [
        FakeResult(single=_concept_row(old_verification_state="verified")),  # lookup
        FakeResult(single={"vs": None}),  # per-collection mentions vs
        FakeResult(),  # SET mentions vs
        FakeResult(),  # promote org-level concept to verified
        FakeResult(),  # SET concept notes/tags
        FakeResult(single={"event_id": "ce2"}),  # audit event
    ]
    store, sess = make_store(responses=responses)
    out = store.update_concept_curation(
        "c1", "o1", "Alpha", verification_state="verified"
    )
    assert out["ok"] is True
    assert out["operation"] == "manual_curate_concept"
    assert len(sess.runs) == 6


def test_curation_unverified_does_not_promote_org_node():
    # verification_state is set but not "verified" -> mentions vs is cleared and
    # the org-level promote is skipped.
    responses = [
        FakeResult(single=_concept_row(old_verification_state="verified")),  # lookup
        FakeResult(single={"vs": "verified"}),  # per-collection mentions vs
        FakeResult(),  # SET mentions vs (cleared to null)
        FakeResult(),  # SET concept notes/tags
        FakeResult(single={"event_id": "ce4"}),  # audit event
    ]
    store, sess = make_store(responses=responses)
    out = store.update_concept_curation(
        "c1", "o1", "Alpha", verification_state="unverified"
    )
    assert out["ok"] is True
    assert out["operation"] == "manual_curate_concept"
    # No org-promote query (that path only runs for "verified").
    assert len(sess.runs) == 5


def test_curation_rejected_expunges_concept():
    responses = [
        FakeResult(single=_concept_row()),         # concept lookup
        FakeResult(single={"vs": "verified"}),      # per-collection mentions vs
        FakeResult(single={"chunk_ids": ["ch1"]}),  # chunk ids
        FakeResult(rows=[{"source": "alpha", "target": "beta",
                          "relation": "uses"}]),    # relationships
        FakeResult(single={"event_id": "ce3"}),     # audit event
        FakeResult(),  # delete mentions
        FakeResult(),  # delete relationships
        FakeResult(),  # orphan delete
    ]
    store, sess = make_store(responses=responses)
    out = store.update_concept_curation(
        "c1", "o1", "Alpha", verification_state="rejected"
    )
    assert out["ok"] is True
    assert out["operation"] == "manual_expunge_concept"
    assert out["details"]["expunged"] is True
    assert out["details"]["removed_chunk_mentions"] == 1
    assert out["details"]["removed_relationships"] == 1
    assert len(sess.runs) == 8
