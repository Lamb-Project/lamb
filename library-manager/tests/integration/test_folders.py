"""Folder + tree endpoints.

Ports ``tests/test_folders.py`` and strengthens the status-code assertions
to the exact codes the ``FolderError`` subclasses map to (see
``backend/services/folder_service.py`` and ``_raise_for_folder_error`` in
``backend/routers/folders.py``):

* ``FolderNotFoundError`` -> 404
* ``FolderConflictError`` -> 409
* ``FolderCycleError`` -> 400
* ``FolderValidationError`` -> 400

Source: ``backend/routers/folders.py``, ``backend/schemas/folders.py``.
"""

from __future__ import annotations

import pytest
from _helpers import AUTH_HEADERS, library_payload, unique_id
from httpx import AsyncClient


async def _create_folder(
    client: AsyncClient, lib_id: str, name: str, parent_id: str | None = None
) -> dict:
    resp = await client.post(
        f"/libraries/{lib_id}/folders",
        headers=AUTH_HEADERS,
        json={"name": name, "parent_folder_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_library(client: AsyncClient) -> dict:
    resp = await client.post("/libraries", headers=AUTH_HEADERS, json=library_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


async def test_empty_library_tree(client: AsyncClient, library: dict) -> None:
    """A fresh library's tree has its id and two empty lists."""
    resp = await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    tree = resp.json()
    assert tree["library_id"] == library["id"]
    assert tree["folders"] == []
    assert tree["items"] == []


async def test_tree_returns_flat_lists(client: AsyncClient, library: dict) -> None:
    """The tree returns every folder as a flat list the frontend nests."""
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B", a["id"])
    c = await _create_folder(client, library["id"], "C")
    resp = await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    ids = {f["id"] for f in resp.json()["folders"]}
    assert ids == {a["id"], b["id"], c["id"]}


async def test_tree_on_missing_library_404(client: AsyncClient) -> None:
    """The tree endpoint 404s for an unknown library."""
    resp = await client.get(f"/libraries/{unique_id('missing')}/tree", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_folder_at_root(client: AsyncClient, library: dict) -> None:
    """A root folder has a null parent and a server-assigned id."""
    folder = await _create_folder(client, library["id"], "Q1 Research")
    assert folder["name"] == "Q1 Research"
    assert folder["parent_folder_id"] is None
    assert folder["id"]


async def test_create_folder_nested(client: AsyncClient, library: dict) -> None:
    """A nested folder records its parent id."""
    parent = await _create_folder(client, library["id"], "Papers")
    child = await _create_folder(client, library["id"], "Biology", parent["id"])
    assert child["parent_folder_id"] == parent["id"]


async def test_duplicate_sibling_name_409(client: AsyncClient, library: dict) -> None:
    """A second sibling with the same name returns 409 (FolderConflictError)."""
    await _create_folder(client, library["id"], "Drafts")
    resp = await client.post(
        f"/libraries/{library['id']}/folders", headers=AUTH_HEADERS, json={"name": "Drafts"}
    )
    assert resp.status_code == 409, resp.text


async def test_same_name_different_parents_allowed(client: AsyncClient, library: dict) -> None:
    """Uniqueness is scoped per parent: same name under two parents is fine."""
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B")
    await _create_folder(client, library["id"], "Drafts", a["id"])
    await _create_folder(client, library["id"], "Drafts", b["id"])


async def test_create_under_missing_parent_404(client: AsyncClient, library: dict) -> None:
    """A non-existent parent folder id returns 404 (FolderNotFoundError)."""
    resp = await client.post(
        f"/libraries/{library['id']}/folders",
        headers=AUTH_HEADERS,
        json={"name": "Orphan", "parent_folder_id": unique_id("nope")},
    )
    assert resp.status_code == 404, resp.text


async def test_create_under_missing_library_404(client: AsyncClient) -> None:
    """Creating a folder in an unknown library returns 404."""
    resp = await client.post(
        f"/libraries/{unique_id('missing')}/folders",
        headers=AUTH_HEADERS,
        json={"name": "X"},
    )
    assert resp.status_code == 404, resp.text


async def test_cross_library_parent_400(client: AsyncClient) -> None:
    """A parent from another library returns 400 (FolderValidationError)."""
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_in_b = await _create_folder(client, lib_b["id"], "Foo")
    resp = await client.post(
        f"/libraries/{lib_a['id']}/folders",
        headers=AUTH_HEADERS,
        json={"name": "Bar", "parent_folder_id": folder_in_b["id"]},
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


async def test_rename_folder(client: AsyncClient, library: dict) -> None:
    """Renaming a folder returns 200 with the new name."""
    folder = await _create_folder(client, library["id"], "Old")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{folder['id']}",
        headers=AUTH_HEADERS,
        json={"name": "New"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "New"


async def test_rename_collision_409(client: AsyncClient, library: dict) -> None:
    """Renaming onto an existing sibling name returns 409."""
    await _create_folder(client, library["id"], "Existing")
    other = await _create_folder(client, library["id"], "Other")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{other['id']}",
        headers=AUTH_HEADERS,
        json={"name": "Existing"},
    )
    assert resp.status_code == 409, resp.text


async def test_rename_missing_folder_404(client: AsyncClient, library: dict) -> None:
    """Renaming an unknown folder returns 404 (router pre-check)."""
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{unique_id('nope')}",
        headers=AUTH_HEADERS,
        json={"name": "Whatever"},
    )
    assert resp.status_code == 404, resp.text


async def test_rename_folder_from_other_library_404(client: AsyncClient) -> None:
    """A folder id that belongs to another library is treated as not found."""
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_in_b = await _create_folder(client, lib_b["id"], "Foo")
    resp = await client.put(
        f"/libraries/{lib_a['id']}/folders/{folder_in_b['id']}",
        headers=AUTH_HEADERS,
        json={"name": "Renamed"},
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Move
# ---------------------------------------------------------------------------


async def test_move_folder(client: AsyncClient, library: dict) -> None:
    """Re-parenting a folder returns 200 with the new parent id."""
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{b['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": a["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["parent_folder_id"] == a["id"]


async def test_move_folder_to_root(client: AsyncClient, library: dict) -> None:
    """Moving with parent_folder_id null re-homes the folder at the root."""
    parent = await _create_folder(client, library["id"], "P")
    child = await _create_folder(client, library["id"], "C", parent["id"])
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{child['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": None},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["parent_folder_id"] is None


async def test_move_into_self_400(client: AsyncClient, library: dict) -> None:
    """Moving a folder into itself returns 400 (FolderCycleError)."""
    folder = await _create_folder(client, library["id"], "Self")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{folder['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": folder["id"]},
    )
    assert resp.status_code == 400, resp.text


async def test_move_into_descendant_400(client: AsyncClient, library: dict) -> None:
    """Moving a folder under its own descendant returns 400 (FolderCycleError)."""
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B", a["id"])
    c = await _create_folder(client, library["id"], "C", b["id"])
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{a['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": c["id"]},
    )
    assert resp.status_code == 400, resp.text


async def test_move_to_missing_destination_404(client: AsyncClient, library: dict) -> None:
    """Moving under a non-existent destination returns 404."""
    folder = await _create_folder(client, library["id"], "F")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{folder['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": unique_id("nope")},
    )
    assert resp.status_code == 404, resp.text


async def test_move_missing_folder_404(client: AsyncClient, library: dict) -> None:
    """Moving an unknown folder returns 404 (router pre-check)."""
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{unique_id('nope')}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": None},
    )
    assert resp.status_code == 404, resp.text


async def test_move_collision_409(client: AsyncClient, library: dict) -> None:
    """Moving into a parent that already has a same-named child returns 409."""
    parent = await _create_folder(client, library["id"], "Parent")
    await _create_folder(client, library["id"], "Dup", parent["id"])
    loose = await _create_folder(client, library["id"], "Dup")
    resp = await client.put(
        f"/libraries/{library['id']}/folders/{loose['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": parent["id"]},
    )
    assert resp.status_code == 409, resp.text


async def test_move_across_library_400(client: AsyncClient) -> None:
    """Moving a folder under a destination in another library returns 400.

    The router's pre-check resolves the folder within ``lib_a`` first, so the
    moved folder and the destination must both be addressable from lib_a's
    path. We therefore exercise the service-level cross-library guard by
    routing through the folder's own library but targeting a foreign parent.
    """
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_a = await _create_folder(client, lib_a["id"], "Mover")
    dest_b = await _create_folder(client, lib_b["id"], "Dest")
    resp = await client.put(
        f"/libraries/{lib_a['id']}/folders/{folder_a['id']}/move",
        headers=AUTH_HEADERS,
        json={"parent_folder_id": dest_b["id"]},
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# Delete (reparents children + items up)
# ---------------------------------------------------------------------------


async def test_delete_folder_reparents_subfolders(client: AsyncClient, library: dict) -> None:
    """Deleting a middle folder re-homes its subfolders under its parent."""
    a = await _create_folder(client, library["id"], "A")
    b = await _create_folder(client, library["id"], "B", a["id"])
    c = await _create_folder(client, library["id"], "C", b["id"])
    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{b['id']}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["items_reparented_to"] == a["id"]

    tree = (await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)).json()
    folders_by_id = {f["id"]: f for f in tree["folders"]}
    assert b["id"] not in folders_by_id
    assert folders_by_id[c["id"]]["parent_folder_id"] == a["id"]


async def test_delete_collision_renames_subfolder(client: AsyncClient, library: dict) -> None:
    """A reparented subfolder colliding with a sibling gets a numeric suffix."""
    a = await _create_folder(client, library["id"], "A")
    await _create_folder(client, library["id"], "Drafts")  # root-level Drafts
    await _create_folder(client, library["id"], "Drafts", a["id"])  # A/Drafts
    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{a['id']}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text

    tree = (await client.get(f"/libraries/{library['id']}/tree", headers=AUTH_HEADERS)).json()
    root_names = sorted(f["name"] for f in tree["folders"] if f["parent_folder_id"] is None)
    assert "Drafts" in root_names
    assert any(n.startswith("Drafts (") for n in root_names)


async def test_delete_missing_folder_404(client: AsyncClient, library: dict) -> None:
    """Deleting an unknown folder returns 404."""
    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{unique_id('nope')}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_delete_folder_from_other_library_404(client: AsyncClient) -> None:
    """Deleting a folder via the wrong library's path returns 404."""
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_in_b = await _create_folder(client, lib_b["id"], "Foo")
    resp = await client.delete(
        f"/libraries/{lib_a['id']}/folders/{folder_in_b['id']}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Name validation (schema)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        "   ",
        "x" * 200,
        "with/slash",
        "with\\backslash",
        "with\x00null",
        "with\nnewline",
    ],
)
async def test_invalid_folder_names_rejected(
    client: AsyncClient, library: dict, bad_name: str
) -> None:
    """Invalid names fail validation: 422 (min/max length) or 400 (validator)."""
    resp = await client.post(
        f"/libraries/{library['id']}/folders", headers=AUTH_HEADERS, json={"name": bad_name}
    )
    assert resp.status_code in (400, 422), resp.text


async def test_folder_name_trimmed(client: AsyncClient, library: dict) -> None:
    """A surrounding-whitespace name is trimmed by the validator before storing."""
    resp = await client.post(
        f"/libraries/{library['id']}/folders",
        headers=AUTH_HEADERS,
        json={"name": "  Padded  "},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Padded"
