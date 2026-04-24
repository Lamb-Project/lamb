"""CRUD tests for /collections endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import AUTH_HEADERS


def _create_payload(org_id: str, name: str | None = None) -> dict:
    return {
        "organization_id": org_id,
        "name": name or f"kb-{uuid4().hex[:6]}",
        "description": "pytest",
        "chunking_strategy": "simple",
        "chunking_params": {"chunk_size": 400, "chunk_overlap": 50},
        "embedding": {"vendor": "fake", "model": "fake-model"},
        "vector_db_backend": "chromadb",
    }


@pytest.mark.asyncio
async def test_create_collection_success(client: AsyncClient, org_id: str) -> None:
    response = await client.post(
        "/collections", json=_create_payload(org_id), headers=AUTH_HEADERS
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["organization_id"] == org_id
    assert body["chunking_strategy"] == "simple"
    assert body["chunking_params"]["chunk_size"] == 400
    assert body["embedding"]["vendor"] == "fake"
    assert body["vector_db_backend"] == "chromadb"
    assert body["status"] == "ready"
    assert body["document_count"] == 0
    assert body["chunk_count"] == 0


@pytest.mark.asyncio
async def test_create_collection_unknown_chunking(
    client: AsyncClient, org_id: str
) -> None:
    payload = _create_payload(org_id)
    payload["chunking_strategy"] = "bogus"
    response = await client.post(
        "/collections", json=payload, headers=AUTH_HEADERS
    )
    assert response.status_code == 400
    assert "bogus" in response.text


@pytest.mark.asyncio
async def test_create_collection_unknown_embedding(
    client: AsyncClient, org_id: str
) -> None:
    payload = _create_payload(org_id)
    payload["embedding"]["vendor"] = "bogus-vendor"
    response = await client.post(
        "/collections", json=payload, headers=AUTH_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_collection_duplicate_name(
    client: AsyncClient, org_id: str
) -> None:
    payload = _create_payload(org_id, name="shared-name")
    r1 = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert r1.status_code == 201
    r2 = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_same_name_different_orgs(client: AsyncClient) -> None:
    """Name uniqueness is scoped per org."""
    r1 = await client.post(
        "/collections",
        json=_create_payload("org-A", name="same-name"),
        headers=AUTH_HEADERS,
    )
    r2 = await client.post(
        "/collections",
        json=_create_payload("org-B", name="same-name"),
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 201 and r2.status_code == 201


@pytest.mark.asyncio
async def test_get_collection(client: AsyncClient, collection: dict) -> None:
    response = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["id"] == collection["id"]


@pytest.mark.asyncio
async def test_get_collection_not_found(client: AsyncClient) -> None:
    response = await client.get(
        "/collections/does-not-exist", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_collections_filters_by_org(
    client: AsyncClient, org_id: str
) -> None:
    # Seed two collections in different orgs.
    await client.post(
        "/collections",
        json=_create_payload(org_id, name="a"),
        headers=AUTH_HEADERS,
    )
    other_org = f"org-{uuid4().hex[:8]}"
    await client.post(
        "/collections",
        json=_create_payload(other_org, name="b"),
        headers=AUTH_HEADERS,
    )

    r = await client.get(
        f"/collections?organization_id={org_id}", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    for c in body["collections"]:
        assert c["organization_id"] == org_id


@pytest.mark.asyncio
async def test_update_collection_mutable_fields(
    client: AsyncClient, collection: dict
) -> None:
    r = await client.put(
        f"/collections/{collection['id']}",
        json={"name": "renamed", "description": "new desc"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"
    assert r.json()["description"] == "new desc"


@pytest.mark.asyncio
async def test_update_collection_store_setup_is_ignored(
    client: AsyncClient, collection: dict
) -> None:
    """Update schema ignores chunking/embedding fields (ADR-3: store setup immutable)."""
    r = await client.put(
        f"/collections/{collection['id']}",
        # Extra fields — should be silently ignored by pydantic (no explicit rejection here).
        json={"chunking_strategy": "by_page"},
        headers=AUTH_HEADERS,
    )
    # Pydantic defaults ignore unknown keys unless model_config forbids them.
    # Whether 200 or 422, chunking_strategy must NOT have changed.
    body = (
        r.json()
        if r.status_code == 200
        else (
            await client.get(
                f"/collections/{collection['id']}", headers=AUTH_HEADERS
            )
        ).json()
    )
    assert body["chunking_strategy"] == "simple"


@pytest.mark.asyncio
async def test_delete_collection(client: AsyncClient, collection: dict) -> None:
    r = await client.delete(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert r.status_code == 204
    # Subsequent get → 404
    r2 = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_collection(client: AsyncClient) -> None:
    r = await client.delete("/collections/nope", headers=AUTH_HEADERS)
    assert r.status_code == 404
