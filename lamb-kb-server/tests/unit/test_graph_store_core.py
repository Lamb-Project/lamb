"""Unit tests for ``services.graph_store.GraphStore`` — core read/guard paths.

Covers construction/configuration guards, schema bootstrap, collection and
document deletion, change listing with every filter branch, and the static
relationship-matching helpers. Heavier write/transaction paths (revert,
rename, merge, edit, curation, ingest) are covered in companion modules.
"""

from __future__ import annotations

import json

import pytest

from services import graph_store as gs_module
from services.graph_store import GraphStore, get_graph_store, utc_now
from tests.unit._neo4j_fakes import FakeDriver, FakeResult, FakeSession, make_store


# ---------------------------------------------------------------------------
# module-level helpers + construction
# ---------------------------------------------------------------------------


def test_utc_now_is_iso8601_utc():
    value = utc_now()
    assert value.endswith("+00:00")


def test_get_graph_store_is_singleton(monkeypatch):
    monkeypatch.setattr(gs_module, "_GRAPH_STORE", None)
    a = get_graph_store()
    b = get_graph_store()
    assert a is b


def test_init_not_configured_leaves_driver_none():
    store = GraphStore(kg_config={"enabled": False})
    assert store.driver is None
    assert store.is_configured() is False


def test_init_configured_creates_driver(monkeypatch):
    created = {}

    class _FakeGraphDatabase:
        @staticmethod
        def driver(uri, auth):
            created["uri"] = uri
            created["auth"] = auth
            return "the-driver"

    monkeypatch.setattr(gs_module, "GraphDatabase", _FakeGraphDatabase)
    store = GraphStore(
        kg_config={
            "enabled": True,
            "neo4j_uri": "bolt://localhost:7687",
            "neo4j_user": "neo4j",
            "neo4j_password": "secret",
        }
    )
    assert store.driver == "the-driver"
    assert created["auth"] == ("neo4j", "secret")
    assert store.is_configured() is True


def test_init_driver_creation_failure_is_swallowed(monkeypatch):
    class _BoomGraphDatabase:
        @staticmethod
        def driver(uri, auth):
            raise RuntimeError("cannot connect")

    monkeypatch.setattr(gs_module, "GraphDatabase", _BoomGraphDatabase)
    store = GraphStore(
        kg_config={
            "enabled": True,
            "neo4j_uri": "bolt://x",
            "neo4j_user": "u",
            "neo4j_password": "p",
        }
    )
    assert store.driver is None


def test_is_configured_false_when_graphdatabase_missing(monkeypatch):
    monkeypatch.setattr(gs_module, "GraphDatabase", None)
    store = GraphStore(
        kg_config={
            "enabled": True,
            "neo4j_uri": "bolt://x",
            "neo4j_user": "u",
            "neo4j_password": "p",
        }
    )
    assert store.is_configured() is False


# ---------------------------------------------------------------------------
# close / is_available
# ---------------------------------------------------------------------------


def test_close_calls_driver_close():
    store, _ = make_store()
    store.close()
    assert store.driver.closed is True


def test_close_noop_when_no_driver():
    store = GraphStore(kg_config={"enabled": False})
    store.close()  # must not raise


def test_is_available_false_without_driver():
    store = GraphStore(kg_config={"enabled": False})
    assert store.is_available() is False


def test_is_available_true_when_connectivity_ok():
    store, _ = make_store()
    assert store.is_available() is True


def test_is_available_false_on_connectivity_error():
    sess = FakeSession()
    driver = FakeDriver(sess, connectivity_error=RuntimeError("down"))
    store, _ = make_store(driver=driver)
    assert store.is_available() is False


# ---------------------------------------------------------------------------
# ensure_schema
# ---------------------------------------------------------------------------


def test_ensure_schema_short_circuits_when_ready():
    store, sess = make_store(schema_ready=True)
    assert store.ensure_schema() is True
    assert sess.runs == []  # no statements executed


def test_ensure_schema_returns_false_when_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    assert store.ensure_schema() is False


def test_ensure_schema_runs_all_statements():
    store, sess = make_store(schema_ready=False)
    assert store.ensure_schema() is True
    # 8 schema statements (constraints + indexes).
    assert len(sess.runs) == 8
    assert store._schema_ready is True


def test_ensure_schema_handles_run_failure():
    class _BoomSession(FakeSession):
        def run(self, query, **params):
            raise RuntimeError("schema error")

    store, _ = make_store(session=_BoomSession(), schema_ready=False)
    assert store.ensure_schema() is False


# ---------------------------------------------------------------------------
# delete_collection / delete_document
# ---------------------------------------------------------------------------


def test_delete_collection_runs_three_statements():
    store, sess = make_store()
    store.delete_collection("col-1")
    assert len(sess.runs) == 3
    assert sess.runs[0]["params"]["collection_id"] == "col-1"


def test_delete_collection_aborts_if_schema_not_ready():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, sess = make_store(driver=driver, schema_ready=False)
    store.delete_collection("col-1")
    assert sess.runs == []


def test_delete_document_runs_three_statements():
    store, sess = make_store()
    store.delete_document("col-1", "org-1", "doc.pdf")
    assert len(sess.runs) == 3
    assert sess.runs[1]["params"]["filename"] == "doc.pdf"
    assert sess.runs[2]["params"]["org_id"] == "org-1"


def test_delete_document_aborts_when_not_configured():
    # is_configured() is False (enabled stays False, no uri/password).
    store = GraphStore(kg_config={"enabled": False})
    # Should return before touching any driver (driver is None).
    store.delete_document("c", "o", "f")  # must not raise


# ---------------------------------------------------------------------------
# list_changes filtering
# ---------------------------------------------------------------------------


def _event_row(**over):
    row = {
        "event_id": "e1",
        "collection_id": "c1",
        "org_id": "o1",
        "operation": "add_document",
        "actor": "user",
        "timestamp": "2026-06-20T00:00:00Z",
        "filename": "doc.pdf",
        "concepts": ["alpha", "beta"],
        "payload_json": None,
        "document_id": "d1",
        "file_id": 1,
    }
    row.update(over)
    return row


def test_list_changes_returns_false_when_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    assert store.list_changes("c1", "o1") == []


def test_list_changes_plain_no_filters():
    rows = [_event_row(), _event_row(event_id="e2")]
    store, sess = make_store(responses=[FakeResult(rows=rows)])
    out = store.list_changes("c1", "o1", limit=5)
    assert len(out) == 2
    assert sess.runs[0]["params"]["fetch_limit"] == 100  # clamped lower bound


def test_list_changes_limit_clamped_to_200():
    store, sess = make_store(responses=[FakeResult(rows=[])])
    store.list_changes("c1", "o1", limit=9999)
    # fetch_limit = min(max(limit*10, 100), 1000)
    assert sess.runs[0]["params"]["fetch_limit"] == 1000


def test_list_changes_concept_filter_drops_relationship_ops():
    rows = [
        _event_row(operation="add_document"),
        _event_row(event_id="e2", operation="manual_edit_relationship"),
        _event_row(event_id="e3", operation="manual_curate_relationship"),
    ]
    store, _ = make_store(responses=[FakeResult(rows=rows)])
    out = store.list_changes("c1", "o1", concept="Alpha")
    ops = {r["operation"] for r in out}
    assert ops == {"add_document"}


def test_list_changes_relationship_filter_matches_payload():
    payload = json.dumps(
        {"source": "alpha", "target": "beta", "relation": "uses"}
    )
    rows = [
        _event_row(event_id="match", payload_json=payload),
        _event_row(event_id="nomatch", payload_json=json.dumps(
            {"source": "gamma", "target": "delta", "relation": "uses"}
        )),
    ]
    store, _ = make_store(responses=[FakeResult(rows=rows)])
    out = store.list_changes(
        "c1",
        "o1",
        relationship_source="Alpha",
        relationship_target="Beta",
        relationship_relation="uses",
    )
    assert [r["event_id"] for r in out] == ["match"]


def test_list_changes_truncates_to_limit():
    rows = [_event_row(event_id=f"e{i}") for i in range(10)]
    store, _ = make_store(responses=[FakeResult(rows=rows)])
    out = store.list_changes("c1", "o1", limit=3)
    assert len(out) == 3


# ---------------------------------------------------------------------------
# _event_payload / _event_matches_relationship
# ---------------------------------------------------------------------------


def test_event_payload_parses_and_guards():
    assert GraphStore._event_payload({"payload_json": '{"a": 1}'}) == {"a": 1}
    assert GraphStore._event_payload({"payload_json": None}) == {}
    assert GraphStore._event_payload({"payload_json": "not-json"}) == {}
    # Valid JSON that isn't an object -> {}.
    assert GraphStore._event_payload({"payload_json": "[1,2]"}) == {}


def test_event_matches_relationship_via_relationship_details():
    row = {
        "payload_json": json.dumps(
            {"relationship_details": [{"source": "alpha", "target": "beta",
                                       "relation": "uses"}]}
        )
    }
    assert GraphStore._event_matches_relationship(row, "alpha", "beta", "uses")
    assert not GraphStore._event_matches_relationship(row, "alpha", "zeta", None)


def test_event_matches_relationship_via_removed_relationships():
    row = {
        "payload_json": json.dumps(
            {"removed_relationships": [{"source": "alpha", "target": "beta",
                                        "relation": "old"}]}
        )
    }
    assert GraphStore._event_matches_relationship(row, "alpha", None, None)


def test_event_matches_relationship_alternate_relation_keys():
    row = {
        "payload_json": json.dumps(
            {"source": "alpha", "target": "beta", "relation": "uses",
             "new_relation": "depends_on"}
        )
    }
    # Matches against the new_relation value too.
    assert GraphStore._event_matches_relationship(row, "alpha", "beta", "depends_on")


def test_event_matches_relationship_no_payload_match():
    row = {"payload_json": json.dumps({"unrelated": True})}
    assert GraphStore._event_matches_relationship(row, "alpha", None, None) is False


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


def test_get_change_returns_dict():
    row = _event_row()
    row["chunk_ids"] = ["chunk-1", "chunk-2"]
    store, _ = make_store(responses=[FakeResult(single=row)])
    out = store.get_change("c1", "o1", "e1")
    assert out["event_id"] == "e1"
    assert out["chunk_ids"] == ["chunk-1", "chunk-2"]


def test_get_change_returns_none_when_missing():
    store, _ = make_store(responses=[FakeResult(single=None)])
    assert store.get_change("c1", "o1", "missing") is None


def test_get_change_returns_none_when_schema_unavailable():
    driver = FakeDriver(FakeSession(), connectivity_error=RuntimeError("x"))
    store, _ = make_store(driver=driver, schema_ready=False)
    assert store.get_change("c1", "o1", "e1") is None
