"""Item move (single + bulk) and upload-with-folder_id.

Ports ``tests/test_items_move.py``. Uploads use the real ``simple_import``
plugin through the running worker (fast, no mocking) and ``poll_until_ready``
to reach the terminal status before asserting placement.

Source: ``backend/routers/folders.py`` (move route),
``backend/routers/importing.py``, ``backend/schemas/folders.py``
(``ItemsMoveRequest`` caps the list at 1..500).
"""

from __future__ import annotations

from _helpers import AUTH_HEADERS, library_payload, poll_until_ready, text_file, unique_id
from httpx import AsyncClient


async def _upload(
    client: AsyncClient, lib_id: str, *, title: str = "Doc", folder_id: str | None = None
) -> str:
    data = {"plugin_name": "simple_import", "title": title}
    if folder_id is not None:
        data["folder_id"] = folder_id
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("# x", "a.md"),
        data=data,
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready", f"upload did not become ready: {status}"
    return item_id


async def _create_folder(
    client: AsyncClient, lib_id: str, name: str, parent_id: str | None = None
) -> str:
    resp = await client.post(
        f"/libraries/{lib_id}/folders",
        headers=AUTH_HEADERS,
        json={"name": name, "parent_folder_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_library(client: AsyncClient) -> str:
    resp = await client.post("/libraries", headers=AUTH_HEADERS, json=library_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _folder_id_of(client: AsyncClient, lib_id: str, item_id: str) -> str | None:
    resp = await client.get(f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    return resp.json()["folder_id"]


# ---------------------------------------------------------------------------
# Upload with folder_id
# ---------------------------------------------------------------------------


async def test_upload_lands_at_root_by_default(client: AsyncClient, library: dict) -> None:
    """An upload with no folder_id ends up at the library root."""
    item_id = await _upload(client, library["id"])
    assert await _folder_id_of(client, library["id"], item_id) is None


async def test_upload_with_folder_id(client: AsyncClient, library: dict) -> None:
    """An upload with a valid folder_id lands inside that folder."""
    folder_id = await _create_folder(client, library["id"], "Q1 Research")
    item_id = await _upload(client, library["id"], folder_id=folder_id)
    assert await _folder_id_of(client, library["id"], item_id) == folder_id


async def test_upload_with_invalid_folder_400(client: AsyncClient, library: dict) -> None:
    """An unknown folder_id on upload is rejected with 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("# x", "a.md"),
        data={"plugin_name": "simple_import", "title": "x", "folder_id": unique_id("nope")},
    )
    assert resp.status_code == 400, resp.text


async def test_upload_cross_library_folder_400(client: AsyncClient) -> None:
    """A folder_id from another library is rejected with 400."""
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_in_b = await _create_folder(client, lib_b, "Foo")
    resp = await client.post(
        f"/libraries/{lib_a}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("# x", "a.md"),
        data={"plugin_name": "simple_import", "title": "x", "folder_id": folder_in_b},
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# Bulk move
# ---------------------------------------------------------------------------


async def test_bulk_move_items_to_folder(client: AsyncClient, library: dict) -> None:
    """Bulk-moving two items reports moved=2 and updates each item's folder."""
    folder_id = await _create_folder(client, library["id"], "Target")
    item1 = await _upload(client, library["id"], title="One")
    item2 = await _upload(client, library["id"], title="Two")
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item1, item2], "folder_id": folder_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"moved": 2, "folder_id": folder_id}
    for iid in (item1, item2):
        assert await _folder_id_of(client, library["id"], iid) == folder_id


async def test_single_move_item(client: AsyncClient, library: dict) -> None:
    """A single-item move list works the same as a bulk move."""
    folder_id = await _create_folder(client, library["id"], "Solo")
    item_id = await _upload(client, library["id"])
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_id], "folder_id": folder_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["moved"] == 1
    assert await _folder_id_of(client, library["id"], item_id) == folder_id


async def test_move_items_to_root(client: AsyncClient, library: dict) -> None:
    """Moving with folder_id=null sends items back to the root."""
    folder_id = await _create_folder(client, library["id"], "T")
    item_id = await _upload(client, library["id"], folder_id=folder_id)
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_id], "folder_id": None},
    )
    assert resp.status_code == 200, resp.text
    assert await _folder_id_of(client, library["id"], item_id) is None


async def test_move_missing_library_404(client: AsyncClient) -> None:
    """Moving items within an unknown library returns 404."""
    resp = await client.post(
        f"/libraries/{unique_id('missing')}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [unique_id("item")], "folder_id": None},
    )
    assert resp.status_code == 404, resp.text


async def test_move_unknown_item_404(client: AsyncClient, library: dict) -> None:
    """A move referencing an item that does not exist returns 404."""
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [unique_id("ghost")], "folder_id": None},
    )
    assert resp.status_code == 404, resp.text


async def test_move_to_missing_folder_404(client: AsyncClient, library: dict) -> None:
    """A destination folder that does not exist returns 404."""
    item_id = await _upload(client, library["id"])
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_id], "folder_id": unique_id("nope")},
    )
    assert resp.status_code == 404, resp.text


async def test_move_items_cross_library_400(client: AsyncClient) -> None:
    """Moving an item that belongs to another library returns 400."""
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    item_in_b = await _upload(client, lib_b)
    resp = await client.post(
        f"/libraries/{lib_a}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_in_b], "folder_id": None},
    )
    assert resp.status_code == 400, resp.text


async def test_move_to_cross_library_folder_400(client: AsyncClient) -> None:
    """Moving an item into a folder from another library returns 400."""
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    item_a = await _upload(client, lib_a)
    folder_b = await _create_folder(client, lib_b, "Foreign")
    resp = await client.post(
        f"/libraries/{lib_a}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_a], "folder_id": folder_b},
    )
    assert resp.status_code == 400, resp.text


async def test_move_empty_list_422(client: AsyncClient, library: dict) -> None:
    """An empty item_ids list violates min_length=1 → 422."""
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [], "folder_id": None},
    )
    assert resp.status_code == 422, resp.text


async def test_move_payload_cap_422(client: AsyncClient, library: dict) -> None:
    """More than 500 item_ids violates max_length=500 → 422."""
    big = [f"item-{i}" for i in range(501)]
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": big, "folder_id": None},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Folder delete reparents items
# ---------------------------------------------------------------------------


async def test_folder_delete_reparents_items(client: AsyncClient, library: dict) -> None:
    """Deleting a folder re-homes its items under the folder's parent."""
    parent = await _create_folder(client, library["id"], "Parent")
    child = await _create_folder(client, library["id"], "Child", parent)
    item_id = await _upload(client, library["id"], folder_id=child)
    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{child}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert await _folder_id_of(client, library["id"], item_id) == parent
