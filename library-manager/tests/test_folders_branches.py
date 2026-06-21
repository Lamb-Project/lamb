"""Error/edge-path tests for the folder service + router.

Router pre-checks shadow some service not-found guards, so those are driven
by direct service calls; the rest go through the HTTP router to also cover
its error→status mapping.
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient

from .conftest import AUTH_HEADERS


async def _mk_library(client: AsyncClient) -> str:
    lib_id = f"lib-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/libraries", headers=AUTH_HEADERS,
        json={"id": lib_id, "organization_id": "org-fb", "name": f"L {lib_id[-6:]}"},
    )
    assert resp.status_code == 201
    return lib_id


async def _mk_folder(client, lib_id, name, parent=None) -> dict:
    resp = await client.post(
        f"/libraries/{lib_id}/folders", headers=AUTH_HEADERS,
        json={"name": name, "parent_folder_id": parent},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# create_folder branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_in_missing_library_404(client: AsyncClient):
    resp = await client.post(
        "/libraries/nope/folders", headers=AUTH_HEADERS, json={"name": "X"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_with_missing_parent_404(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.post(
        f"/libraries/{lib}/folders", headers=AUTH_HEADERS,
        json={"name": "X", "parent_folder_id": "missing-parent"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_sibling_conflict(client: AsyncClient):
    lib = await _mk_library(client)
    await _mk_folder(client, lib, "Dup")
    resp = await client.post(
        f"/libraries/{lib}/folders", headers=AUTH_HEADERS, json={"name": "Dup"}
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# rename / move / delete via router (router 404 mappings)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_missing_folder_404(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.put(
        f"/libraries/{lib}/folders/missing", headers=AUTH_HEADERS,
        json={"name": "New"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rename_same_name_noop(client: AsyncClient):
    lib = await _mk_library(client)
    f = await _mk_folder(client, lib, "Keep")
    resp = await client.put(
        f"/libraries/{lib}/folders/{f['id']}", headers=AUTH_HEADERS,
        json={"name": "Keep"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Keep"


@pytest.mark.asyncio
async def test_move_missing_folder_404(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.put(
        f"/libraries/{lib}/folders/missing/move", headers=AUTH_HEADERS,
        json={"parent_folder_id": None},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_move_into_itself_cycle(client: AsyncClient):
    lib = await _mk_library(client)
    f = await _mk_folder(client, lib, "Self")
    resp = await client.put(
        f"/libraries/{lib}/folders/{f['id']}/move", headers=AUTH_HEADERS,
        json={"parent_folder_id": f["id"]},
    )
    assert resp.status_code == 400  # FolderCycleError


@pytest.mark.asyncio
async def test_move_missing_destination_404(client: AsyncClient):
    lib = await _mk_library(client)
    f = await _mk_folder(client, lib, "F")
    resp = await client.put(
        f"/libraries/{lib}/folders/{f['id']}/move", headers=AUTH_HEADERS,
        json={"parent_folder_id": "missing-dest"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_move_into_descendant_cycle(client: AsyncClient):
    lib = await _mk_library(client)
    parent = await _mk_folder(client, lib, "Parent")
    child = await _mk_folder(client, lib, "Child", parent=parent["id"])
    resp = await client.put(
        f"/libraries/{lib}/folders/{parent['id']}/move", headers=AUTH_HEADERS,
        json={"parent_folder_id": child["id"]},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_move_across_libraries_rejected(client: AsyncClient):
    lib_a = await _mk_library(client)
    lib_b = await _mk_library(client)
    fa = await _mk_folder(client, lib_a, "A")
    fb = await _mk_folder(client, lib_b, "B")
    # Move A under B's folder — cross-library.
    resp = await client.put(
        f"/libraries/{lib_a}/folders/{fa['id']}/move", headers=AUTH_HEADERS,
        json={"parent_folder_id": fb["id"]},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_delete_missing_folder_404(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.delete(
        f"/libraries/{lib}/folders/missing", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_reparents_with_name_collision(client: AsyncClient):
    # Root already has "Drafts"; folder X also contains "Drafts". Deleting X
    # reparents its "Drafts" to root, which collides -> suffixed "Drafts (2)".
    lib = await _mk_library(client)
    await _mk_folder(client, lib, "Drafts")
    x = await _mk_folder(client, lib, "X")
    await _mk_folder(client, lib, "Drafts", parent=x["id"])
    resp = await client.delete(
        f"/libraries/{lib}/folders/{x['id']}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    tree = (await client.get(f"/libraries/{lib}/tree", headers=AUTH_HEADERS)).json()
    names = sorted(f["name"] for f in tree["folders"])
    assert "Drafts" in names and "Drafts (2)" in names


# ---------------------------------------------------------------------------
# move_items branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_move_items_missing_library_404(client: AsyncClient):
    resp = await client.post(
        "/libraries/nope/items/move", headers=AUTH_HEADERS,
        json={"item_ids": ["x"], "folder_id": None},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_move_items_missing_destination_404(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.post(
        f"/libraries/{lib}/items/move", headers=AUTH_HEADERS,
        json={"item_ids": ["x"], "folder_id": "missing-dest"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_move_items_unknown_item_404(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.post(
        f"/libraries/{lib}/items/move", headers=AUTH_HEADERS,
        json={"item_ids": ["unknown-item"], "folder_id": None},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Direct service calls for the not-found guards the router pre-check shadows
# ---------------------------------------------------------------------------


def test_service_not_found_guards():
    from database.connection import get_session_direct
    from services import folder_service as fs

    db = get_session_direct()
    try:
        with pytest.raises(fs.FolderNotFoundError):
            fs.rename_folder(db, "missing", "x")
        with pytest.raises(fs.FolderNotFoundError):
            fs.move_folder(db, "missing", None)
        with pytest.raises(fs.FolderNotFoundError):
            fs.delete_folder(db, "missing")
        # Empty item list short-circuits to 0 (schema blocks this via HTTP).
        assert fs.move_items(db, "any-lib", [], None) == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_delete_reparents_with_double_name_collision(client: AsyncClient):
    # Root has both "Notes" and "Notes (2)"; folder X also contains "Notes".
    # Deleting X reparents its "Notes" to root, where "Notes" AND "Notes (2)"
    # are taken -> the suffix loop must advance to "Notes (3)" (folder_service
    # _next_available_name `except FolderConflictError: n += 1`).
    lib = await _mk_library(client)
    await _mk_folder(client, lib, "Notes")
    await _mk_folder(client, lib, "Notes (2)")
    x = await _mk_folder(client, lib, "X")
    await _mk_folder(client, lib, "Notes", parent=x["id"])
    resp = await client.delete(
        f"/libraries/{lib}/folders/{x['id']}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    tree = (await client.get(f"/libraries/{lib}/tree", headers=AUTH_HEADERS)).json()
    names = sorted(f["name"] for f in tree["folders"])
    assert "Notes (3)" in names


@pytest.mark.asyncio
async def test_delete_folder_service_error_mapped(client: AsyncClient, monkeypatch):
    # Router pre-check passes (folder exists), but delete_folder raises a
    # FolderError -> router's `except FolderError` translates it to a status.
    lib = await _mk_library(client)
    f = await _mk_folder(client, lib, "Boom")

    from services import folder_service as fs

    def _raise(db, folder_id):
        raise fs.FolderConflictError("synthetic")

    monkeypatch.setattr(fs, "delete_folder", _raise)
    resp = await client.delete(
        f"/libraries/{lib}/folders/{f['id']}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 409
