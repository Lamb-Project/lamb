"""Branch tests for ``services.collection_service`` via the collections router.

Covers the graph/extraction-validation branch, the plugin-params passthrough
logging, the update-time chunking_params validation, and deletion of a
graph-enabled collection.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests._helpers import AUTH_HEADERS


def _payload(org_id: str, name: str | None = None, **over) -> dict:
    base = {
        "organization_id": org_id,
        "name": name or f"kb-{uuid4().hex[:6]}",
        "description": "pytest",
        "chunking_strategy": "simple",
        "chunking_params": {"chunk_size": 400, "chunk_overlap": 50},
        "embedding": {"vendor": "fake", "model": "fake-model"},
        "vector_db_backend": "chromadb",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_create_graph_enabled_invalid_extraction_vendor(
    client: AsyncClient, org_id: str
) -> None:
    payload = _payload(org_id, graph_enabled=True, extraction={
        "vendor": "no-such-vendor", "model": "x",
    })
    resp = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 400
    assert "extraction vendor" in resp.text.lower()


@pytest.mark.asyncio
async def test_create_with_plugin_params_passthrough(
    client: AsyncClient, org_id: str
) -> None:
    # Non-empty embedding_params / vector_db_params exercise the
    # "received but not yet wired" logging branches.
    payload = _payload(
        org_id,
        embedding_params={"extra_knob": "v"},
        vector_db_params={"hnsw_ef": 64},
    )
    resp = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_update_chunking_params_valid_and_invalid(
    client: AsyncClient, org_id: str
) -> None:
    created = await client.post(
        "/collections", json=_payload(org_id), headers=AUTH_HEADERS
    )
    cid = created.json()["id"]

    # Valid chunking_params update applies.
    ok = await client.put(
        f"/collections/{cid}",
        json={"chunking_params": {"chunk_size": 800, "chunk_overlap": 80}},
        headers=AUTH_HEADERS,
    )
    assert ok.status_code == 200
    assert ok.json()["chunking_params"]["chunk_size"] == 800

    # Invalid chunking_params (typo'd key) is rejected at update time.
    bad = await client.put(
        f"/collections/{cid}",
        json={"chunking_params": {"chunk_size": 800, "bogus_key": 1}},
        headers=AUTH_HEADERS,
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_delete_graph_enabled_collection(
    client: AsyncClient, org_id: str
) -> None:
    # Creating + deleting a graph_enabled collection exercises the graph
    # teardown branch in delete (KG-RAG disabled in tests -> Neo4j call is
    # skipped, but the branch + config guard run).
    created = await client.post(
        "/collections", json=_payload(org_id, graph_enabled=True), headers=AUTH_HEADERS
    )
    cid = created.json()["id"]
    resp = await client.delete(f"/collections/{cid}", headers=AUTH_HEADERS)
    assert resp.status_code in (200, 204)


def test_delete_graph_enabled_calls_neo4j_teardown(monkeypatch):
    """Direct service call with KG-RAG enabled + an available fake graph store
    exercises the Neo4j subgraph-delete branch on collection delete."""
    import config as config_module
    import services.collection_service as cs
    import services.graph_store as gs_module
    from database.connection import get_session_direct
    from database.models import Collection

    cid = f"col-graphdel-{uuid4().hex[:8]}"
    session = get_session_direct()
    try:
        session.add(Collection(
            id=cid, organization_id="org-z", name=f"graphdel-{uuid4().hex[:6]}",
            chunking_strategy="simple", embedding_vendor="fake",
            embedding_model="fake-model", vector_db_backend="chromadb",
            storage_path="/tmp/does-not-matter", graph_enabled=True,
        ))
        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(config_module, "get_kg_rag_config", lambda: {"enabled": True})

    deleted = {"called": False}

    class _FakeStore:
        def is_configured(self):
            return True

        def is_available(self):
            return True

        def delete_collection(self, collection_id):
            deleted["called"] = collection_id == cid

    monkeypatch.setattr(gs_module, "get_graph_store", lambda: _FakeStore())

    session2 = get_session_direct()
    try:
        cs.delete_collection(session2, cid)
    finally:
        session2.close()
    assert deleted["called"] is True
