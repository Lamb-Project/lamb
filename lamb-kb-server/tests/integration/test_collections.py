"""CRUD tests for /collections endpoints."""

import os
from pathlib import Path
from unittest.mock import patch
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


# ---------------------------------------------------------------------------
# Pagination edge-case tests (new)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination_limit_boundary(client: AsyncClient) -> None:
    """Create 5 collections in one org; paginate through them 2-at-a-time."""
    org = f"org-{uuid4().hex[:8]}"
    names = [f"col-{i}" for i in range(5)]
    for name in names:
        r = await client.post(
            "/collections", json=_create_payload(org, name=name), headers=AUTH_HEADERS
        )
        assert r.status_code == 201

    # Page 0: expect 2 results, total=5
    r = await client.get(
        f"/collections?organization_id={org}&limit=2&offset=0", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["collections"]) == 2

    # Page 1: next 2
    r = await client.get(
        f"/collections?organization_id={org}&limit=2&offset=2", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["collections"]) == 2

    # Page 2: last 1
    r = await client.get(
        f"/collections?organization_id={org}&limit=2&offset=4", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["collections"]) == 1


@pytest.mark.asyncio
async def test_pagination_limit_greater_than_total(client: AsyncClient) -> None:
    """limit > total: returns all collections."""
    org = f"org-{uuid4().hex[:8]}"
    for i in range(5):
        r = await client.post(
            "/collections",
            json=_create_payload(org, name=f"c{i}"),
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 201

    r = await client.get(
        f"/collections?organization_id={org}&limit=100", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["collections"]) == 5


@pytest.mark.asyncio
async def test_pagination_offset_beyond_total(client: AsyncClient) -> None:
    """offset > total: returns empty results array but correct total."""
    org = f"org-{uuid4().hex[:8]}"
    for i in range(3):
        r = await client.post(
            "/collections",
            json=_create_payload(org, name=f"col{i}"),
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 201

    r = await client.get(
        f"/collections?organization_id={org}&offset=50", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["collections"] == []


@pytest.mark.asyncio
async def test_list_collections_no_org_filter(client: AsyncClient) -> None:
    """GET /collections without organization_id returns all collections (no filter)."""
    org_a = f"org-{uuid4().hex[:8]}"
    org_b = f"org-{uuid4().hex[:8]}"
    r_a = await client.post(
        "/collections", json=_create_payload(org_a), headers=AUTH_HEADERS
    )
    r_b = await client.post(
        "/collections", json=_create_payload(org_b), headers=AUTH_HEADERS
    )
    assert r_a.status_code == 201
    assert r_b.status_code == 201

    r = await client.get("/collections", headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    # Both collections from both orgs should appear in the unfiltered list
    org_ids = {c["organization_id"] for c in body["collections"]}
    assert org_a in org_ids
    assert org_b in org_ids
    assert body["total"] >= 2


@pytest.mark.asyncio
async def test_cross_org_listing_isolation(client: AsyncClient) -> None:
    """Collections created in org-A must not appear when listing org-B."""
    org_a = f"org-{uuid4().hex[:8]}"
    org_b = f"org-{uuid4().hex[:8]}"
    for i in range(2):
        r = await client.post(
            "/collections", json=_create_payload(org_a, name=f"a{i}"), headers=AUTH_HEADERS
        )
        assert r.status_code == 201
    r = await client.post(
        "/collections", json=_create_payload(org_b, name="b0"), headers=AUTH_HEADERS
    )
    assert r.status_code == 201

    r = await client.get(
        f"/collections?organization_id={org_a}", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    for c in body["collections"]:
        assert c["organization_id"] == org_a

    r = await client.get(
        f"/collections?organization_id={org_b}", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["collections"][0]["organization_id"] == org_b


# ---------------------------------------------------------------------------
# Delete cascade tests (new)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_cascades_to_filesystem(
    client: AsyncClient, collection: dict
) -> None:
    """DELETE removes the on-disk storage directory."""
    from config import STORAGE_DIR  # noqa: PLC0415

    coll_id = collection["id"]
    org_id = collection["organization_id"]
    storage_path = STORAGE_DIR / org_id / coll_id
    assert storage_path.exists(), f"Storage path missing before delete: {storage_path}"

    r = await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r.status_code == 204
    assert not storage_path.exists(), f"Storage path still exists after delete: {storage_path}"


@pytest.mark.asyncio
async def test_delete_cascades_to_chromadb(
    client: AsyncClient, collection: dict
) -> None:
    """DELETE evicts the ChromaDB collection from the module-level client cache."""
    from plugins.vector_db.chromadb_backend import _clients  # noqa: PLC0415

    coll_id = collection["id"]
    storage_path = collection.get("storage_path") or str(
        Path(os.environ["DATA_DIR"]) / "storage" / collection["organization_id"] / coll_id
    )

    r = await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r.status_code == 204
    # The client for this storage_path should have been evicted from the cache
    assert storage_path not in _clients


@pytest.mark.asyncio
async def test_put_after_delete_returns_404(
    client: AsyncClient, collection: dict
) -> None:
    """PUT on a deleted collection returns 404."""
    coll_id = collection["id"]
    r_del = await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r_del.status_code == 204

    r_put = await client.put(
        f"/collections/{coll_id}",
        json={"name": "new-name"},
        headers=AUTH_HEADERS,
    )
    assert r_put.status_code == 404


@pytest.mark.asyncio
async def test_get_after_delete_returns_404(
    client: AsyncClient, collection: dict
) -> None:
    """GET on a deleted collection returns 404."""
    coll_id = collection["id"]
    r_del = await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r_del.status_code == 204

    r_get = await client.get(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r_get.status_code == 404


# ---------------------------------------------------------------------------
# Update edge-case tests (new)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_empty_body_is_noop(
    client: AsyncClient, collection: dict
) -> None:
    """PUT with empty body {} is a no-op: returns 200 with unchanged fields.

    UpdateCollectionRequest has both name and description as Optional[str]
    defaulting to None, so an empty body is valid — it just changes nothing.
    """
    coll_id = collection["id"]
    original_name = collection["name"]
    original_desc = collection["description"]

    r = await client.put(f"/collections/{coll_id}", json={}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == original_name
    assert body["description"] == original_desc


@pytest.mark.asyncio
async def test_put_only_description_updates(
    client: AsyncClient, collection: dict
) -> None:
    """PUT with only description changes description but not name."""
    coll_id = collection["id"]
    original_name = collection["name"]

    r = await client.put(
        f"/collections/{coll_id}",
        json={"description": "updated-desc"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == original_name
    assert body["description"] == "updated-desc"


@pytest.mark.asyncio
async def test_update_rename_conflicts_with_existing(
    client: AsyncClient, org_id: str
) -> None:
    """Renaming a collection to an existing name in the same org returns 409."""
    r1 = await client.post(
        "/collections", json=_create_payload(org_id, name="first"), headers=AUTH_HEADERS
    )
    r2 = await client.post(
        "/collections", json=_create_payload(org_id, name="second"), headers=AUTH_HEADERS
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    second_id = r2.json()["id"]

    # Try to rename "second" → "first" (already taken in same org)
    r = await client.put(
        f"/collections/{second_id}",
        json={"name": "first"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 409
    assert "first" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Create with explicit ID (new)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_with_explicit_id(client: AsyncClient, org_id: str) -> None:
    """Server respects the caller-supplied id field."""
    custom_id = f"custom-{uuid4().hex[:8]}"
    payload = _create_payload(org_id)
    payload["id"] = custom_id

    r = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 201
    assert r.json()["id"] == custom_id


@pytest.mark.asyncio
async def test_create_same_id_different_orgs_conflict(
    client: AsyncClient,
) -> None:
    """Collection id is globally unique (primary key), not scoped per org.

    The Collection table uses ``id`` as primary key (not per-org). Creating a
    second collection with the same explicit id raises a DB integrity error that
    propagates through the ASGI transport (unhandled SQLAlchemy IntegrityError).
    """
    import sqlalchemy.exc  # noqa: PLC0415

    shared_id = f"shared-{uuid4().hex[:8]}"
    payload_a = _create_payload("org-X", name="alpha")
    payload_a["id"] = shared_id
    payload_b = _create_payload("org-Y", name="beta")
    payload_b["id"] = shared_id

    r1 = await client.post("/collections", json=payload_a, headers=AUTH_HEADERS)
    assert r1.status_code == 201

    # The IntegrityError propagates through the ASGI transport because the app
    # has no handler for SQLAlchemy exceptions — it re-raises from the service.
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await client.post("/collections", json=payload_b, headers=AUTH_HEADERS)


# ---------------------------------------------------------------------------
# Unknown vector_db_backend — covers collection_service.py line 27
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_collection_unknown_vector_db_backend(
    client: AsyncClient, org_id: str
) -> None:
    """Unknown vector_db_backend triggers 400 (line 27 of collection_service.py)."""
    payload = _create_payload(org_id)
    payload["vector_db_backend"] = "unknown-backend"
    r = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 400
    assert "unknown-backend" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Exception-path tests — covers lines 140-145 and 289-290
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_collection_backend_exception_cleans_up_storage(
    client: AsyncClient, org_id: str
) -> None:
    """If vector backend raises during create, storage dir is cleaned up (lines 143-145).

    The RuntimeError propagates through the ASGI transport (the app has no
    generic exception handler), so we use pytest.raises to capture it.
    The key invariant is that the storage directory is removed even on failure.
    """
    from config import STORAGE_DIR  # noqa: PLC0415
    from plugins.base import VectorDBRegistry  # noqa: PLC0415

    original_get = VectorDBRegistry.get

    def _fail_get(name: str):
        backend = original_get(name)
        if backend is not None:

            class _FailBackend:
                def create_collection(self, **kwargs):
                    raise RuntimeError("simulated backend failure")

            return _FailBackend()
        return backend

    payload = _create_payload(org_id, name=f"fail-{uuid4().hex[:6]}")

    # The RuntimeError propagates through ASGI transport — capture it.
    with patch.object(VectorDBRegistry, "get", side_effect=_fail_get):
        with pytest.raises(RuntimeError, match="simulated backend failure"):
            await client.post("/collections", json=payload, headers=AUTH_HEADERS)

    # Storage dir must have been cleaned up by the except block (lines 143-145).
    org_storage = STORAGE_DIR / org_id
    if org_storage.exists():
        for child in org_storage.iterdir():
            # Any leftover dir is an orphan — the except block calls shutil.rmtree
            assert False, f"Orphan storage dir found after failed create: {child}"


@pytest.mark.asyncio
async def test_delete_collection_backend_exception_still_removes_row(
    client: AsyncClient, collection: dict
) -> None:
    """If vector backend delete raises, DB row is still removed (lines 289-290)."""
    from plugins.base import VectorDBRegistry  # noqa: PLC0415

    coll_id = collection["id"]
    original_get = VectorDBRegistry.get

    def _fail_delete_get(name: str):
        backend = original_get(name)
        if backend is not None:

            class _FailDeleteBackend:
                def delete_collection(self, **kwargs):
                    raise RuntimeError("simulated vector delete failure")

            return _FailDeleteBackend()
        return backend

    with patch.object(VectorDBRegistry, "get", side_effect=_fail_delete_get):
        r = await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)

    # Despite backend failure, the delete should succeed (204)
    assert r.status_code == 204

    # Subsequent GET must return 404 (DB row was removed)
    r2 = await client.get(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_delete_collection_backend_none_still_removes_row(
    client: AsyncClient, collection: dict
) -> None:
    """If VectorDBRegistry.get returns None, delete still removes DB row (line 284->296)."""
    from plugins.base import VectorDBRegistry  # noqa: PLC0415

    coll_id = collection["id"]

    with patch.object(VectorDBRegistry, "get", return_value=None):
        r = await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)

    assert r.status_code == 204

    r2 = await client.get(f"/collections/{coll_id}", headers=AUTH_HEADERS)
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_create_collection_http_exception_in_try_cleans_up_storage(
    client: AsyncClient, org_id: str
) -> None:
    """If an HTTPException is raised inside the try block, storage is cleaned up (lines 141-142).

    The HTTPException path re-raises after cleanup, so the response is a 4xx/5xx
    HTTP response (FastAPI catches HTTPException and converts it to a response).
    """
    from fastapi import HTTPException as FastAPIHTTPException  # noqa: PLC0415

    from config import STORAGE_DIR  # noqa: PLC0415
    from plugins.base import VectorDBRegistry  # noqa: PLC0415

    original_get = VectorDBRegistry.get

    def _http_exception_get(name: str):
        backend = original_get(name)
        if backend is not None:

            class _HttpExceptionBackend:
                def create_collection(self, **kwargs):
                    raise FastAPIHTTPException(
                        status_code=503, detail="simulated backend unavailable"
                    )

            return _HttpExceptionBackend()
        return backend

    payload = _create_payload(org_id, name=f"http-fail-{uuid4().hex[:6]}")

    with patch.object(VectorDBRegistry, "get", side_effect=_http_exception_get):
        r = await client.post("/collections", json=payload, headers=AUTH_HEADERS)

    # HTTPException is caught, storage cleaned up, then re-raised → FastAPI converts to response
    assert r.status_code == 503

    # No orphan storage dirs should remain
    org_storage = STORAGE_DIR / org_id
    if org_storage.exists():
        for child in org_storage.iterdir():
            assert False, f"Orphan storage dir found after HTTPException: {child}"
