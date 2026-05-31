"""Tests for the folder + tree endpoints.

Covers:
- Folder CRUD (create / rename / move / delete).
- Cycle prevention server-side.
- Unique sibling-name enforcement.
- Delete reparents items + subfolders to the deleted folder's parent.
- Folder name validation (length, forbidden characters).
- Cross-library FK rejection.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from .conftest import AUTH_HEADERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_folder(client: AsyncClient, lib_id: str, name: str, parent_id: str | None = None) -> dict:
    resp = await client.post(
        f"/libraries/{lib_id}/folders",
        headers=AUTH_HEADERS,
        json={"name": name, "parent_folder_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_library(client: AsyncClient) -> dict:
    lib_id = f"lib-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={
            "id": lib_id,
            "organization_id": "org-test",
            "name": f"Lib {lib_id[-8:]}",
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_folder_at_root(client: AsyncClient, library: dict) -> None:
    folder = await _create_folder(client, library["id"], "Q1 Research")
    assert folder["name"] == "Q1 Research"
    assert folder["parent_folder_id"] is None
    assert "id" in folder


@pytest.mark.asyncio
async def test_create_folder_nested(client: AsyncClient, library: dict) -> None:
    parent = await _create_folder(client, library["id"], "Papers")
    child = await _create_folder(client, library["id"], "Biology", parent["id"])
    assert child["parent_folder_id"] == parent["id"]


@pytest.mark.asyncio
async def test_unique_sibling_names_rejected(client: AsyncClient, library: dict) -> None:
    await _create_folder(client, library["id"], "Drafts")
    resp = await client.post(
        f"/libraries/{library['id']}/folders",
        headers=AUTH_HEADERS,
        json={"name": "Drafts"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_same_name_in_different_parents_is_allowed(
    client: AsyncClient, library: dict
) -> None:
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B")
    # Both can have a child named "Drafts"
    await _create_folder(client, library["id"], "Drafts", a["id"])
    await _create_folder(client, library["id"], "Drafts", b["id"])


@pytest.mark.asyncio
async def test_rename_folder(client: AsyncClient, library: dict) -> None:
    folder = await _create_folder(client, library["id"], "Old")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{folder['id']}",
        headers=AUTH_HEADERS,
        json={"name": "New"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


@pytest.mark.asyncio
async def test_rename_collision_rejected(client: AsyncClient, library: dict) -> None:
    await _create_folder(client, library["id"], "Existing")
    other = await _create_folder(client, library["id"], "Other")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{other['id']}",
        headers=AUTH_HEADERS,
        json={"name": "Existing"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_move_folder(client: AsyncClient, library: dict) -> None:
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{b['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": a["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["parent_folder_id"] == a["id"]


@pytest.mark.asyncio
async def test_move_folder_to_root(client: AsyncClient, library: dict) -> None:
    parent = await _create_folder(client, library["id"], "P")
    child = await _create_folder(client, library["id"], "C", parent["id"])
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{child['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": None},
    )
    assert resp.status_code == 200
    assert resp.json()["parent_folder_id"] is None


# ---------------------------------------------------------------------------
# Cycle prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_move_folder_into_self(client: AsyncClient, library: dict) -> None:
    folder = await _create_folder(client, library["id"], "Self")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{folder['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": folder["id"]},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_move_folder_into_descendant(client: AsyncClient, library: dict) -> None:
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B", a["id"])
    c = await _create_folder(client, library["id"], "C", b["id"])
    # Moving A under C would create a cycle.
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{a['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": c["id"]},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete (reparents items + subfolders)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_folder_reparents_subfolders(
    client: AsyncClient, library: dict
) -> None:
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B", a["id"])
    c = await _create_folder(client, library["id"], "C", b["id"])

    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{b['id']}",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200

    # After deleting B, C should be a child of A.
    tree = (await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)).json()
    folders_by_id = {f["id"]: f for f in tree["folders"]}
    assert c["id"] in folders_by_id
    assert folders_by_id[c["id"]]["parent_folder_id"] == a["id"]
    assert b["id"] not in folders_by_id


@pytest.mark.asyncio
async def test_delete_folder_collision_renames_subfolder(
    client: AsyncClient, library: dict
) -> None:
    """If a moved-up subfolder collides with an existing sibling, suffix it."""
    a = await _create_folder(client, library["id"], "A")
    drafts_at_root = await _create_folder(client, library["id"], "Drafts")  # noqa: F841
    drafts_in_a = await _create_folder(client, library["id"], "Drafts", a["id"])  # noqa: F841

    # Delete A: its child "Drafts" moves up to root where another "Drafts" lives.
    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{a['id']}",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200

    tree = (await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)).json()
    root_folder_names = sorted(
        f["name"] for f in tree["folders"] if f["parent_folder_id"] is None
    )
    assert "Drafts" in root_folder_names
    assert any(n.startswith("Drafts (") for n in root_folder_names)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_name",
    [
        "",  # empty
        "   ",  # whitespace only
        "x" * 200,  # too long
        "with/slash",
        "with\\backslash",
        "with\x00null",
        "with\nnewline",
    ],
)
async def test_invalid_folder_names_rejected(
    client: AsyncClient, library: dict, bad_name: str
) -> None:
    resp = await client.post(
        f"/libraries/{library['id']}/folders",
        headers=AUTH_HEADERS,
        json={"name": bad_name},
    )
    # Pydantic 422 on min_length/max_length failures, 400 on custom validator
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_cross_library_parent_rejected(client: AsyncClient) -> None:
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_in_b = await _create_folder(client, lib_b["id"], "Foo")

    resp = await client.post(
        f"/libraries/{lib_a['id']}/folders",
        headers=AUTH_HEADERS,
        json={"name": "Bar", "parent_folder_id": folder_in_b["id"]},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tree response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_library_tree(client: AsyncClient, library: dict) -> None:
    resp = await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    tree = resp.json()
    assert tree["library_id"] == library["id"]
    assert tree["folders"] == []
    assert tree["items"] == []


@pytest.mark.asyncio
async def test_tree_returns_flat_lists(client: AsyncClient, library: dict) -> None:
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B", a["id"])
    c = await _create_folder(client, library["id"], "C")

    resp = await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree["folders"]) == 3
    ids = {f["id"] for f in tree["folders"]}
    assert {a["id"], b["id"], c["id"]} == ids


# ---------------------------------------------------------------------------
# Tree 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tree_on_missing_library_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/libraries/nonexistent/tree", headers=AUTH_HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tree_requires_auth(client: AsyncClient, library: dict) -> None:
    resp = await client.get(f"/libraries/{library['id']}/tree")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_folder_requires_auth(client: AsyncClient, library: dict) -> None:
    resp = await client.post(
        f"/libraries/{library['id']}/folders",
        json={"name": "NoAuth"},
    )
    assert resp.status_code in (401, 403)
