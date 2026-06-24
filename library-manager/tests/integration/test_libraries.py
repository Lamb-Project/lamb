"""Library CRUD + pagination boundaries.

Ports ``tests/test_libraries.py`` and adds pagination-boundary coverage for
``GET /libraries`` (limit bounds 1..100, offset windowing). Isolation comes
from unique library ids / per-test organization ids — never from global
counts.

Source: ``backend/routers/libraries.py``, ``backend/schemas/libraries.py``.
"""

from __future__ import annotations

from _helpers import AUTH_HEADERS, library_payload, unique_id
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_library(client: AsyncClient) -> None:
    """POST /libraries returns 201 with id, org, and a zero item_count."""
    payload = library_payload(organization_id="org-crud")
    resp = await client.post("/libraries", headers=AUTH_HEADERS, json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == payload["id"]
    assert data["organization_id"] == "org-crud"
    assert data["item_count"] == 0
    assert data["import_config"] is None


async def test_create_with_import_config(client: AsyncClient) -> None:
    """An import_config supplied at creation round-trips on the response."""
    payload = library_payload(import_config={"image_descriptions": "basic"})
    resp = await client.post("/libraries", headers=AUTH_HEADERS, json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["import_config"] == {"image_descriptions": "basic"}


async def test_duplicate_id_rejected(client: AsyncClient) -> None:
    """Reusing an existing library id returns 409."""
    payload = library_payload()
    resp1 = await client.post("/libraries", headers=AUTH_HEADERS, json=payload)
    assert resp1.status_code == 201, resp1.text
    dup = library_payload(id=payload["id"], name="Different Name")
    resp2 = await client.post("/libraries", headers=AUTH_HEADERS, json=dup)
    assert resp2.status_code == 409, resp2.text


async def test_duplicate_name_in_org_rejected(client: AsyncClient) -> None:
    """Two libraries with the same name in one org return 409 on the second."""
    org = unique_id("org")
    name = "Duplicate Test"
    resp1 = await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org, name=name)
    )
    assert resp1.status_code == 201, resp1.text
    resp2 = await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org, name=name)
    )
    assert resp2.status_code == 409, resp2.text


async def test_same_name_different_org_allowed(client: AsyncClient) -> None:
    """The name uniqueness constraint is scoped per organization."""
    name = "Shared Name"
    r1 = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json=library_payload(organization_id=unique_id("org"), name=name),
    )
    r2 = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json=library_payload(organization_id=unique_id("org"), name=name),
    )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text


async def test_missing_required_field_422(client: AsyncClient) -> None:
    """Omitting a required field (name) fails schema validation with 422."""
    resp = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={"id": unique_id("lib"), "organization_id": "org-test"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_library(client: AsyncClient, library: dict) -> None:
    """GET /libraries/{id} returns details including item_count."""
    resp = await client.get(f"/libraries/{library['id']}", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == library["name"]
    assert data["item_count"] == 0


async def test_get_nonexistent_library_404(client: AsyncClient) -> None:
    """GET on an unknown library id returns 404."""
    resp = await client.get(f"/libraries/{unique_id('missing')}", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# List + pagination boundaries
# ---------------------------------------------------------------------------


async def test_list_includes_created(client: AsyncClient, library: dict) -> None:
    """Listing by org includes a library just created in that org."""
    resp = await client.get(
        "/libraries",
        headers=AUTH_HEADERS,
        params={"organization_id": library["organization_id"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 1
    assert library["id"] in [lib["id"] for lib in data["libraries"]]


async def test_list_requires_organization_id_422(client: AsyncClient) -> None:
    """organization_id is a required query parameter."""
    resp = await client.get("/libraries", headers=AUTH_HEADERS)
    assert resp.status_code == 422, resp.text


async def test_list_filters_by_org(client: AsyncClient) -> None:
    """Listing one org never leaks libraries from another org."""
    org_a, org_b = unique_id("org"), unique_id("org")
    await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org_a)
    )
    await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org_b)
    )
    resp = await client.get("/libraries", headers=AUTH_HEADERS, params={"organization_id": org_a})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert {lib["organization_id"] for lib in data["libraries"]} == {org_a}


async def test_list_limit_zero_rejected_422(client: AsyncClient) -> None:
    """limit below the minimum (1) is rejected by the query validator."""
    resp = await client.get(
        "/libraries", headers=AUTH_HEADERS, params={"organization_id": "org-test", "limit": 0}
    )
    assert resp.status_code == 422, resp.text


async def test_list_limit_over_max_rejected_422(client: AsyncClient) -> None:
    """limit above the maximum (100) is rejected by the query validator."""
    resp = await client.get(
        "/libraries", headers=AUTH_HEADERS, params={"organization_id": "org-test", "limit": 101}
    )
    assert resp.status_code == 422, resp.text


async def test_list_negative_offset_rejected_422(client: AsyncClient) -> None:
    """offset below 0 is rejected by the query validator."""
    resp = await client.get(
        "/libraries", headers=AUTH_HEADERS, params={"organization_id": "org-test", "offset": -1}
    )
    assert resp.status_code == 422, resp.text


async def test_list_limit_boundaries_accepted(client: AsyncClient) -> None:
    """limit=1 and limit=100 are both accepted (inclusive bounds)."""
    org = unique_id("org")
    await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org)
    )
    for limit in (1, 100):
        resp = await client.get(
            "/libraries",
            headers=AUTH_HEADERS,
            params={"organization_id": org, "limit": limit},
        )
        assert resp.status_code == 200, resp.text


async def test_offset_pagination_windows(client: AsyncClient) -> None:
    """Create 5 libs in one org; assert limit/offset returns the right slices."""
    org = unique_id("org")
    created = []
    for _ in range(5):
        resp = await client.post(
            "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org)
        )
        assert resp.status_code == 201, resp.text
        created.append(resp.json()["id"])

    # Full list, paged 2 + 2 + 1, must reconstruct the whole set with no overlap.
    seen: list[str] = []
    for offset in (0, 2, 4):
        resp = await client.get(
            "/libraries",
            headers=AUTH_HEADERS,
            params={"organization_id": org, "limit": 2, "offset": offset},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 5
        page = [lib["id"] for lib in data["libraries"]]
        assert len(page) == (2 if offset < 4 else 1)
        seen.extend(page)

    assert sorted(seen) == sorted(created)
    assert len(set(seen)) == 5  # no duplicates across windows


async def test_offset_past_end_returns_empty(client: AsyncClient) -> None:
    """An offset beyond the result set returns an empty page with the true total."""
    org = unique_id("org")
    await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload(organization_id=org)
    )
    resp = await client.get(
        "/libraries",
        headers=AUTH_HEADERS,
        params={"organization_id": org, "limit": 20, "offset": 50},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["libraries"] == []


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_library(client: AsyncClient) -> None:
    """DELETE removes the library; a subsequent GET 404s."""
    payload = library_payload(organization_id="org-del")
    await client.post("/libraries", headers=AUTH_HEADERS, json=payload)
    resp = await client.delete(f"/libraries/{payload['id']}", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    assert payload["id"] in resp.json()["message"]
    follow = await client.get(f"/libraries/{payload['id']}", headers=AUTH_HEADERS)
    assert follow.status_code == 404, follow.text


async def test_delete_nonexistent_404(client: AsyncClient) -> None:
    """Deleting a library that does not exist returns 404."""
    resp = await client.delete(f"/libraries/{unique_id('missing')}", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Import config
# ---------------------------------------------------------------------------


async def test_import_config_roundtrip(client: AsyncClient, library: dict) -> None:
    """PUT then GET import-config returns the stored config with a warning on PUT."""
    config = {"image_descriptions": "llm", "max_discovery_depth": 5}
    put = await client.put(
        f"/libraries/{library['id']}/import-config", headers=AUTH_HEADERS, json=config
    )
    assert put.status_code == 200, put.text
    assert "warning" in put.json()
    assert put.json()["import_config"] == config

    get = await client.get(
        f"/libraries/{library['id']}/import-config", headers=AUTH_HEADERS
    )
    assert get.status_code == 200, get.text
    assert get.json()["import_config"] == config


async def test_import_config_default_empty(client: AsyncClient, library: dict) -> None:
    """A library created without import_config reports an empty config dict."""
    resp = await client.get(
        f"/libraries/{library['id']}/import-config", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["import_config"] == {}


async def test_get_import_config_missing_library_404(client: AsyncClient) -> None:
    """GET import-config for an unknown library returns 404."""
    resp = await client.get(
        f"/libraries/{unique_id('missing')}/import-config", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_put_import_config_missing_library_404(client: AsyncClient) -> None:
    """PUT import-config for an unknown library returns 404."""
    resp = await client.put(
        f"/libraries/{unique_id('missing')}/import-config", headers=AUTH_HEADERS, json={}
    )
    assert resp.status_code == 404, resp.text
