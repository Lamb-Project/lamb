"""Tests for library CRUD operations."""

import uuid

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_create_library(client: AsyncClient):
    """Creating a library should return 201 with correct fields."""
    lib_id = f"lib-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={
            "id": lib_id,
            "organization_id": "org-crud",
            "name": f"CRUD Test {lib_id[-8:]}",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == lib_id
    assert data["organization_id"] == "org-crud"
    assert data["item_count"] == 0


@pytest.mark.asyncio
async def test_get_library(client: AsyncClient, library: dict):
    """Getting a library should return its details."""
    resp = await client.get(
        f"/libraries/{library['id']}",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == library["name"]


@pytest.mark.asyncio
async def test_get_nonexistent_library(client: AsyncClient):
    """Getting a non-existent library should return 404."""
    resp = await client.get("/libraries/fake-id", headers=AUTH_HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_libraries(client: AsyncClient, library: dict):
    """Listing libraries should include the created library."""
    resp = await client.get(
        "/libraries",
        headers=AUTH_HEADERS,
        params={"organization_id": library["organization_id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [lib["id"] for lib in data["libraries"]]
    assert library["id"] in ids


@pytest.mark.asyncio
async def test_duplicate_name_rejected(client: AsyncClient):
    """Creating two libraries with the same name in one org should fail."""
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    name = "Duplicate Test"

    resp1 = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={"id": f"lib-{uuid.uuid4().hex[:8]}", "organization_id": org_id, "name": name},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={"id": f"lib-{uuid.uuid4().hex[:8]}", "organization_id": org_id, "name": name},
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_delete_library(client: AsyncClient):
    """Deleting a library should remove it from the database."""
    lib_id = f"lib-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={"id": lib_id, "organization_id": "org-del", "name": f"Del {lib_id[-6:]}"},
    )

    resp = await client.delete(f"/libraries/{lib_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200

    resp = await client.get(f"/libraries/{lib_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_config_roundtrip(client: AsyncClient, library: dict):
    """Setting and reading import config should produce consistent results."""
    config = {"image_descriptions": "llm", "max_discovery_depth": 5}

    resp = await client.put(
        f"/libraries/{library['id']}/import-config",
        headers=AUTH_HEADERS,
        json=config,
    )
    assert resp.status_code == 200
    assert "warning" in resp.json()

    resp = await client.get(
        f"/libraries/{library['id']}/import-config",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()["import_config"]
    assert data["image_descriptions"] == "llm"
    assert data["max_discovery_depth"] == 5
