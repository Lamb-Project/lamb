"""Router tests for ``routers.graph`` via FastAPI TestClient.

Auth + DB-session dependencies are overridden; ``get_graph_store`` and the
service layer are monkeypatched so the tests exercise the routing,
validation, status-code mapping, and response shaping in isolation.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config as config_module
import routers.graph as graph_router
from database.connection import get_session
from dependencies import verify_token


class _Collection:
    def __init__(self, **over):
        self.id = "col-1"
        self.organization_id = "org-1"
        self.vector_db_backend = "chromadb"
        self.embedding_vendor = "fake"
        self.embedding_model = "fake-model"
        self.embedding_endpoint = ""
        self.backend_collection_id = "backend-col"
        self.storage_path = "/tmp/store"
        self.graph_enabled = False
        self.__dict__.update(over)


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._result


class _FakeDB:
    def __init__(self, collection):
        self._c = collection
        self.committed = False

    def query(self, _model):
        return _FakeQuery(self._c)

    def commit(self):
        self.committed = True


class _FakeGraphStore:
    def __init__(self, *, configured=True, available=True, **methods):
        self._configured = configured
        self._available = available
        self._methods = methods

    def is_configured(self):
        return self._configured

    def is_available(self):
        return self._available

    def __getattr__(self, name):
        # Return a stub that yields the preconfigured value for any graph op.
        result = self.__dict__.get("_methods", {}).get(name, {})
        return lambda **kwargs: result


def _make_client(collection, store, monkeypatch, *, kg_enabled=True):
    monkeypatch.setattr(graph_router, "get_graph_store", lambda: store)
    monkeypatch.setattr(
        config_module, "get_kg_rag_config",
        lambda: {"enabled": kg_enabled, "index_on_ingest": True},
    )
    app = FastAPI()
    app.include_router(graph_router.router)
    app.dependency_overrides[verify_token] = lambda: "token"
    db = _FakeDB(collection)
    app.dependency_overrides[get_session] = lambda: db
    client = TestClient(app)
    client._db = db  # expose for assertions
    return client


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status(monkeypatch):
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    resp = client.get("/graph/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["neo4j_configured"] is True
    assert body["neo4j_available"] is True


def test_status_unavailable_when_connectivity_raises(monkeypatch):
    class _Boom(_FakeGraphStore):
        def is_available(self):
            raise RuntimeError("down")

    client = _make_client(_Collection(), _Boom(), monkeypatch)
    resp = client.get("/graph/status")
    assert resp.json()["neo4j_available"] is False


# ---------------------------------------------------------------------------
# snapshot / changes / get_change
# ---------------------------------------------------------------------------


def test_snapshot_404_when_collection_missing(monkeypatch):
    client = _make_client(None, _FakeGraphStore(), monkeypatch)
    assert client.get("/graph/collections/col-1/snapshot").status_code == 404


def test_snapshot_503_when_not_configured(monkeypatch):
    client = _make_client(
        _Collection(), _FakeGraphStore(configured=False), monkeypatch
    )
    assert client.get("/graph/collections/col-1/snapshot").status_code == 503


def test_snapshot_503_when_unavailable(monkeypatch):
    client = _make_client(
        _Collection(), _FakeGraphStore(available=False), monkeypatch
    )
    assert client.get("/graph/collections/col-1/snapshot").status_code == 503


def test_snapshot_success(monkeypatch):
    snapshot = {
        "collection_id": "col-1", "nodes": [], "edges": [],
        "filters": {}, "counts": {},
    }
    store = _FakeGraphStore(get_collection_graph=snapshot)
    client = _make_client(_Collection(), store, monkeypatch)
    resp = client.get("/graph/collections/col-1/snapshot?concept=alpha&limit=10")
    assert resp.status_code == 200
    assert resp.json()["collection_id"] == "col-1"


def test_list_changes_success(monkeypatch):
    changes = [{
        "event_id": "e1", "collection_id": "col-1", "org_id": "org-1",
        "operation": "add_document", "concepts": [],
    }]
    store = _FakeGraphStore(list_changes=changes)
    client = _make_client(_Collection(), store, monkeypatch)
    resp = client.get("/graph/collections/col-1/changes?limit=5")
    assert resp.status_code == 200
    assert resp.json()[0]["event_id"] == "e1"


def test_concept_changes_and_document_changes(monkeypatch):
    store = _FakeGraphStore(list_changes=[])
    client = _make_client(_Collection(), store, monkeypatch)
    assert client.get(
        "/graph/collections/col-1/concepts/alpha/changes").status_code == 200
    assert client.get(
        "/graph/collections/col-1/documents/doc1/changes").status_code == 200


def test_get_change_success_and_404(monkeypatch):
    change = {
        "event_id": "e1", "collection_id": "col-1", "org_id": "org-1",
        "operation": "add_document", "concepts": [], "chunk_ids": [],
    }
    client = _make_client(
        _Collection(), _FakeGraphStore(get_change=change), monkeypatch
    )
    assert client.get("/graph/collections/col-1/changes/e1").status_code == 200

    client2 = _make_client(
        _Collection(), _FakeGraphStore(get_change=None), monkeypatch
    )
    assert client2.get("/graph/collections/col-1/changes/missing").status_code == 404


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------


def test_revert_success(monkeypatch):
    result = {"reverted": True, "event_id": "e1", "chunk_ids": []}
    client = _make_client(
        _Collection(), _FakeGraphStore(revert_change=result), monkeypatch
    )
    resp = client.post(
        "/graph/collections/col-1/changes/e1/revert", json={"actor": "me"}
    )
    assert resp.status_code == 200
    assert resp.json()["reverted"] is True


def test_revert_not_found(monkeypatch):
    result = {"reverted": False, "reason": "change_not_found"}
    client = _make_client(
        _Collection(), _FakeGraphStore(revert_change=result), monkeypatch
    )
    resp = client.post(
        "/graph/collections/col-1/changes/x/revert", json={}
    )
    assert resp.status_code == 404


def test_revert_unsupported_400(monkeypatch):
    result = {"reverted": False, "reason": "unsupported_operation"}
    client = _make_client(
        _Collection(), _FakeGraphStore(revert_change=result), monkeypatch
    )
    resp = client.post(
        "/graph/collections/col-1/changes/x/revert", json={}
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# curation operations (rename / merge / curate / edit / curate-rel)
# ---------------------------------------------------------------------------


def test_rename_concept_ok_and_400(monkeypatch):
    ok = {"ok": True, "operation": "manual_rename_concept", "event_id": "e"}
    client = _make_client(
        _Collection(), _FakeGraphStore(rename_concept=ok), monkeypatch
    )
    resp = client.patch(
        "/graph/collections/col-1/concepts/alpha/rename",
        json={"new_name": "beta"},
    )
    assert resp.status_code == 200

    bad = {"ok": False, "reason": "invalid_concept_name"}
    client2 = _make_client(
        _Collection(), _FakeGraphStore(rename_concept=bad), monkeypatch
    )
    resp2 = client2.patch(
        "/graph/collections/col-1/concepts/alpha/rename",
        json={"new_name": "beta"},
    )
    assert resp2.status_code == 400


def test_merge_concepts_ok_and_400(monkeypatch):
    ok = {"ok": True, "operation": "manual_merge_concepts", "event_id": "e"}
    client = _make_client(
        _Collection(), _FakeGraphStore(merge_concepts=ok), monkeypatch
    )
    resp = client.post(
        "/graph/collections/col-1/concepts/merge",
        json={"source_names": ["a"], "target_name": "b"},
    )
    assert resp.status_code == 200

    bad = {"ok": False, "reason": "invalid_merge_request"}
    client2 = _make_client(
        _Collection(), _FakeGraphStore(merge_concepts=bad), monkeypatch
    )
    resp2 = client2.post(
        "/graph/collections/col-1/concepts/merge",
        json={"source_names": ["a"], "target_name": "b"},
    )
    assert resp2.status_code == 400


def test_curate_concept_ok_and_400(monkeypatch):
    ok = {"ok": True, "operation": "manual_curate_concept", "event_id": "e"}
    client = _make_client(
        _Collection(), _FakeGraphStore(update_concept_curation=ok), monkeypatch
    )
    resp = client.patch(
        "/graph/collections/col-1/concepts/alpha/curation",
        json={"notes": "n", "verification_state": "verified"},
    )
    assert resp.status_code == 200

    bad = {"ok": False, "reason": "concept_not_found"}
    client2 = _make_client(
        _Collection(), _FakeGraphStore(update_concept_curation=bad), monkeypatch
    )
    resp2 = client2.patch(
        "/graph/collections/col-1/concepts/alpha/curation",
        json={"verification_state": "verified"},
    )
    assert resp2.status_code == 400


def test_edit_relationship_ok_and_400(monkeypatch):
    ok = {"ok": True, "operation": "manual_edit_relationship", "event_id": "e"}
    client = _make_client(
        _Collection(), _FakeGraphStore(edit_relationship=ok), monkeypatch
    )
    resp = client.patch(
        "/graph/collections/col-1/relationships",
        json={"source_concept": "a", "target_concept": "b", "relation": "uses",
              "new_relation": "depends_on"},
    )
    assert resp.status_code == 200

    bad = {"ok": False, "reason": "relationship_not_found"}
    client2 = _make_client(
        _Collection(), _FakeGraphStore(edit_relationship=bad), monkeypatch
    )
    resp2 = client2.patch(
        "/graph/collections/col-1/relationships",
        json={"source_concept": "a", "target_concept": "b", "relation": "uses"},
    )
    assert resp2.status_code == 400


def test_curate_relationship_ok_and_400(monkeypatch):
    ok = {"ok": True, "operation": "manual_curate_relationship", "event_id": "e"}
    client = _make_client(
        _Collection(), _FakeGraphStore(edit_relationship=ok), monkeypatch
    )
    resp = client.patch(
        "/graph/collections/col-1/relationships/curation",
        json={"source_concept": "a", "target_concept": "b", "relation": "uses",
              "verification_state": "verified"},
    )
    assert resp.status_code == 200

    bad = {"ok": False, "reason": "relationship_not_found"}
    client2 = _make_client(
        _Collection(), _FakeGraphStore(edit_relationship=bad), monkeypatch
    )
    resp2 = client2.patch(
        "/graph/collections/col-1/relationships/curation",
        json={"source_concept": "a", "target_concept": "b", "relation": "uses"},
    )
    assert resp2.status_code == 400


def test_status_not_configured_skips_availability(monkeypatch):
    client = _make_client(
        _Collection(), _FakeGraphStore(configured=False), monkeypatch
    )
    body = client.get("/graph/status").json()
    assert body["neo4j_configured"] is False
    assert body["neo4j_available"] is False


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------


def test_migrate_disabled_503(monkeypatch):
    client = _make_client(
        _Collection(), _FakeGraphStore(), monkeypatch, kg_enabled=False
    )
    resp = client.post("/graph/collections/col-1/migrate")
    assert resp.status_code == 503


def test_migrate_collection_404(monkeypatch):
    client = _make_client(None, _FakeGraphStore(), monkeypatch)
    assert client.post("/graph/collections/col-1/migrate").status_code == 404


def test_migrate_backend_unavailable_503(monkeypatch):
    import plugins.base as base_module

    monkeypatch.setattr(base_module.VectorDBRegistry, "get",
                        classmethod(lambda cls, name: None))
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    assert client.post("/graph/collections/col-1/migrate").status_code == 503


class _FakeBackend:
    def __init__(self, batches=None, raises=None):
        self._batches = batches or []
        self._raises = raises

    def iter_all_chunks(self, **kwargs):
        if self._raises:
            raise self._raises
        yield from self._batches


def _patch_migrate_backend(monkeypatch, backend):
    import plugins.base as base_module

    monkeypatch.setattr(base_module.VectorDBRegistry, "get",
                        classmethod(lambda cls, name: backend))
    monkeypatch.setattr(base_module.EmbeddingRegistry, "build",
                        classmethod(lambda cls, vendor, **kw: object()))


def test_migrate_not_implemented_400(monkeypatch):
    backend = _FakeBackend(raises=NotImplementedError())
    _patch_migrate_backend(monkeypatch, backend)
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    assert client.post("/graph/collections/col-1/migrate").status_code == 400


def test_migrate_backend_collection_missing_404(monkeypatch):
    backend = _FakeBackend(raises=RuntimeError("missing"))
    _patch_migrate_backend(monkeypatch, backend)
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    assert client.post("/graph/collections/col-1/migrate").status_code == 404


def test_migrate_no_chunks_sets_graph_enabled(monkeypatch):
    backend = _FakeBackend(batches=[])  # no batches -> no ids
    _patch_migrate_backend(monkeypatch, backend)
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    resp = client.post("/graph/collections/col-1/migrate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_enabled"] is True
    assert body["indexed"] is False
    assert client._db.committed is True


def test_migrate_success(monkeypatch):
    backend = _FakeBackend(batches=[(["c1"], ["chunk text"], [{"filename": "f.md"}])])
    _patch_migrate_backend(monkeypatch, backend)
    import services.graph_indexing as gi

    monkeypatch.setattr(
        gi, "index_chunks_for_collection",
        lambda **kwargs: {"indexed": True, "chunks": 1, "entities": 2},
    )
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    resp = client.post(
        "/graph/collections/col-1/migrate",
        headers={"X-OpenAI-Api-Key": "sk-x"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["chunks_seen"] == 1
    assert body["indexed"] is True


def test_migrate_skips_empty_text_chunks(monkeypatch):
    # First text is empty -> skipped; only c2 is collected.
    backend = _FakeBackend(
        batches=[(["c1", "c2"], ["", "real text"], [{}, {"filename": "f.md"}])]
    )
    _patch_migrate_backend(monkeypatch, backend)
    import services.graph_indexing as gi

    captured = {}

    def fake_index(**kwargs):
        captured["ids"] = kwargs["ids"]
        return {"indexed": True, "chunks": len(kwargs["ids"])}

    monkeypatch.setattr(gi, "index_chunks_for_collection", fake_index)
    client = _make_client(_Collection(), _FakeGraphStore(), monkeypatch)
    resp = client.post("/graph/collections/col-1/migrate")
    assert resp.status_code == 200
    assert captured["ids"] == ["c2"]
