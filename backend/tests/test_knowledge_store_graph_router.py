"""Tests for ``creator_interface.knowledge_store_graph_router``.

The router is a thin ACL-checked proxy to the KB Server's ``/graph`` API.
We mount it on a bare app, override the auth dependency, and replace the
module-level ``_client`` (async KB Server client) and ``_db`` with fakes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import creator_interface.knowledge_store_graph_router as gr
from lamb.auth_context import get_auth_context


class _FakeClient:
    """Async KB Server client stub recording calls; every method echoes."""

    def __init__(self):
        self.calls = []

    def _record(self, name, **kw):
        self.calls.append((name, kw))
        return {"ok": True, "method": name, "args": kw}

    async def get_graph_status(self, **kw):
        return self._record("status", **kw)

    async def migrate_collection_to_graph(self, **kw):
        return self._record("migrate", **kw)

    async def get_graph_snapshot(self, **kw):
        return self._record("snapshot", **kw)

    async def list_graph_changes(self, **kw):
        return self._record("changes", **kw)

    async def graph_concept_rename(self, **kw):
        return self._record("rename", **kw)

    async def graph_concepts_merge(self, **kw):
        return self._record("merge", **kw)

    async def graph_concept_curation(self, **kw):
        return self._record("curate_concept", **kw)

    async def graph_relationship_edit(self, **kw):
        return self._record("edit_rel", **kw)

    async def graph_relationship_curation(self, **kw):
        return self._record("curate_rel", **kw)


def _auth(user_id="u1", org_id="org1"):
    return SimpleNamespace(
        user={"id": user_id, "email": "u@x.com"},
        organization={"id": org_id},
    )


def _ks(owner="u1", org="org1", shared=False):
    return {"owner_user_id": owner, "organization_id": org, "is_shared": shared}


@pytest.fixture
def env(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(gr, "_client", client)

    store_box = {"ks": _ks()}

    class _DB:
        def get_knowledge_store(self, ks_id):
            return store_box["ks"]

    monkeypatch.setattr(gr, "_db", _DB())

    app = FastAPI()
    app.include_router(gr.router)
    auth_box = {"auth": _auth()}
    app.dependency_overrides[get_auth_context] = lambda: auth_box["auth"]
    tc = TestClient(app)
    return SimpleNamespace(client=client, tc=tc, store_box=store_box, auth_box=auth_box)


# ---------------------------------------------------------------------------
# access control (_assert_ks_access)
# ---------------------------------------------------------------------------


def test_snapshot_404_when_ks_missing(env):
    env.store_box["ks"] = None
    assert env.tc.get("/ks-1/graph/snapshot").status_code == 404


def test_snapshot_403_when_not_owner_and_not_shared(env):
    env.store_box["ks"] = _ks(owner="someone-else", shared=False)
    assert env.tc.get("/ks-1/graph/snapshot").status_code == 403


def test_snapshot_403_when_org_mismatch(env):
    env.store_box["ks"] = _ks(owner="u1", org="other-org")
    assert env.tc.get("/ks-1/graph/snapshot").status_code == 403


def test_shared_store_in_same_org_is_allowed(env):
    env.store_box["ks"] = _ks(owner="someone-else", org="org1", shared=True)
    assert env.tc.get("/ks-1/graph/snapshot").status_code == 200


# ---------------------------------------------------------------------------
# status + read endpoints
# ---------------------------------------------------------------------------


def test_graph_status(env):
    resp = env.tc.get("/graph/status")
    assert resp.status_code == 200
    assert env.client.calls[0][0] == "status"


def test_snapshot_forwards_all_filters(env):
    resp = env.tc.get(
        "/ks-1/graph/snapshot",
        params={
            "concept": "alpha", "document_id": "d1", "chunk_id": "c1",
            "filename": "f.md", "include_chunks": "false", "limit": 10,
        },
    )
    assert resp.status_code == 200
    params = env.client.calls[0][1]["params"]
    assert params["concept"] == "alpha"
    assert params["document_id"] == "d1"
    assert params["chunk_id"] == "c1"
    assert params["filename"] == "f.md"
    assert params["include_chunks"] == "false"
    assert params["limit"] == 10


def test_changes_forwards_filters(env):
    resp = env.tc.get(
        "/ks-1/graph/changes",
        params={"concept": "alpha", "document_id": "d1", "filename": "f",
                "operation": "manual_rename_concept", "limit": 5},
    )
    assert resp.status_code == 200
    params = env.client.calls[0][1]["params"]
    assert params["operation"] == "manual_rename_concept"
    assert params["limit"] == 5


# ---------------------------------------------------------------------------
# migrate (org-config fallback)
# ---------------------------------------------------------------------------


def test_migrate_with_explicit_key(env):
    resp = env.tc.post("/ks-1/graph/migrate", json={"openai_api_key": "sk-explicit"})
    assert resp.status_code == 200
    assert env.client.calls[0][1]["openai_api_key"] == "sk-explicit"


def test_migrate_resolves_org_key(env, monkeypatch):
    import lamb.completions.org_config_resolver as ocr

    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_api_key(self, vendor):
            return "sk-from-org"

    monkeypatch.setattr(ocr, "OrganizationConfigResolver", _Resolver)
    resp = env.tc.post("/ks-1/graph/migrate", json={})
    assert resp.status_code == 200
    assert env.client.calls[0][1]["openai_api_key"] == "sk-from-org"


def test_migrate_resolver_failure_falls_back_to_empty(env, monkeypatch):
    import lamb.completions.org_config_resolver as ocr

    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_api_key(self, vendor):
            raise RuntimeError("no org config")

    monkeypatch.setattr(ocr, "OrganizationConfigResolver", _Resolver)
    resp = env.tc.post("/ks-1/graph/migrate", json={})
    assert resp.status_code == 200
    assert env.client.calls[0][1]["openai_api_key"] == ""


# ---------------------------------------------------------------------------
# curation endpoints
# ---------------------------------------------------------------------------


def test_rename_concept(env):
    resp = env.tc.patch(
        "/ks-1/graph/concepts/alpha/rename", json={"new_name": "beta"}
    )
    assert resp.status_code == 200
    name, kw = env.client.calls[0]
    assert name == "rename"
    assert kw["concept"] == "alpha"
    assert kw["body"]["new_name"] == "beta"


def test_merge_concepts(env):
    resp = env.tc.post(
        "/ks-1/graph/concepts/merge",
        json={"source_names": ["a", "b"], "target_name": "c"},
    )
    assert resp.status_code == 200
    assert env.client.calls[0][0] == "merge"


def test_curate_concept(env):
    resp = env.tc.patch(
        "/ks-1/graph/concepts/alpha/curation",
        json={"verification_state": "verified", "tags": ["t"]},
    )
    assert resp.status_code == 200
    assert env.client.calls[0][0] == "curate_concept"


def test_edit_relationship(env):
    resp = env.tc.patch(
        "/ks-1/graph/relationships",
        json={"source_concept": "a", "target_concept": "b", "relation": "uses",
              "new_relation": "depends_on"},
    )
    assert resp.status_code == 200
    assert env.client.calls[0][1]["body"]["new_relation"] == "depends_on"


def test_curate_relationship(env):
    resp = env.tc.patch(
        "/ks-1/graph/relationships/curation",
        json={"source_concept": "a", "target_concept": "b", "relation": "uses",
              "verification_state": "verified"},
    )
    assert resp.status_code == 200
    assert env.client.calls[0][0] == "curate_rel"


def test_merge_validation_error(env):
    # missing target_name -> 422 from pydantic before the proxy is hit.
    resp = env.tc.post("/ks-1/graph/concepts/merge", json={"source_names": ["a"]})
    assert resp.status_code == 422
