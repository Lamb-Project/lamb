"""Tests for item move (single + bulk) and upload-with-folder_id."""

from __future__ import annotations

import asyncio
import io
import time
import uuid

import pytest
from httpx import AsyncClient

from .conftest import AUTH_HEADERS

_POLL_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Helpers (mirror the patterns in test_content_serving.py)
# ---------------------------------------------------------------------------


async def _wait_for_ready(client: AsyncClient, lib_id: str, item_id: str) -> str:
    deadline = time.monotonic() + _POLL_TIMEOUT
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS
        )
        if resp.json()["status"] in ("ready", "failed"):
            return resp.json()["status"]
        await asyncio.sleep(0.5)
    return "timeout"


async def _upload(
    client: AsyncClient,
    lib_id: str,
    title: str = "Doc",
    folder_id: str | None = None,
) -> str:
    data = {"plugin_name": "simple_import", "title": title}
    if folder_id is not None:
        data["folder_id"] = folder_id
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("a.md", io.BytesIO(b"# x"), "text/markdown")},
        data=data,
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    status = await _wait_for_ready(client, lib_id, item_id)
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
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Upload with folder_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_lands_at_root_by_default(client: AsyncClient, library: dict) -> None:
    item_id = await _upload(client, library["id"])
    resp = await client.get(
        f"/libraries/{library['id']}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["folder_id"] is None


@pytest.mark.asyncio
async def test_upload_with_folder_id(client: AsyncClient, library: dict) -> None:
    folder_id = await _create_folder(client, library["id"], "Q1 Research")
    item_id = await _upload(client, library["id"], folder_id=folder_id)
    resp = await client.get(
        f"/libraries/{library['id']}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert resp.json()["folder_id"] == folder_id


@pytest.mark.asyncio
async def test_upload_with_invalid_folder_rejected(
    client: AsyncClient, library: dict
) -> None:
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("a.md", io.BytesIO(b"# x"), "text/markdown")},
        data={
            "plugin_name": "simple_import",
            "title": "x",
            "folder_id": "nonexistent-folder-id",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_cross_library_folder_rejected(client: AsyncClient) -> None:
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    folder_in_b = await _create_folder(client, lib_b, "Foo")

    resp = await client.post(
        f"/libraries/{lib_a}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("a.md", io.BytesIO(b"# x"), "text/markdown")},
        data={
            "plugin_name": "simple_import",
            "title": "x",
            "folder_id": folder_in_b,
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Bulk item move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_move_items_to_folder(client: AsyncClient, library: dict) -> None:
    folder_id = await _create_folder(client, library["id"], "Target")
    item1 = await _upload(client, library["id"], title="One")
    item2 = await _upload(client, library["id"], title="Two")

    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item1, item2], "folder_id": folder_id},
    )
    assert resp.status_code == 200
    assert resp.json()["moved"] == 2

    for iid in (item1, item2):
        d = await client.get(
            f"/libraries/{library['id']}/items/{iid}", headers=AUTH_HEADERS
        )
        assert d.json()["folder_id"] == folder_id


@pytest.mark.asyncio
async def test_move_items_to_root(client: AsyncClient, library: dict) -> None:
    folder_id = await _create_folder(client, library["id"], "T")
    item_id = await _upload(client, library["id"], folder_id=folder_id)

    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_id], "folder_id": None},
    )
    assert resp.status_code == 200
    d = await client.get(
        f"/libraries/{library['id']}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert d.json()["folder_id"] is None


@pytest.mark.asyncio
async def test_move_items_cross_library_rejected(client: AsyncClient) -> None:
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    item_in_b = await _upload(client, lib_b)

    # Try to move an item that belongs to lib_b through lib_a's endpoint.
    resp = await client.post(
        f"/libraries/{lib_a}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_in_b], "folder_id": None},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_move_to_cross_library_folder_rejected(client: AsyncClient) -> None:
    lib_a = await _create_library(client)
    lib_b = await _create_library(client)
    item_a = await _upload(client, lib_a)
    folder_b = await _create_folder(client, lib_b, "Foreign")

    resp = await client.post(
        f"/libraries/{lib_a}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [item_a], "folder_id": folder_b},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_move_empty_item_list_rejected(client: AsyncClient, library: dict) -> None:
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": [], "folder_id": None},
    )
    # Pydantic min_length=1 → 422
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_move_payload_cap(client: AsyncClient, library: dict) -> None:
    """Request bodies with > 500 item_ids should be rejected by the schema."""
    big = [f"item-{i}" for i in range(501)]
    resp = await client.post(
        f"/libraries/{library['id']}/items/move",
        headers=AUTH_HEADERS,
        json={"item_ids": big, "folder_id": None},
    )
    # Pydantic max_length=500 → 422
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Folder delete reparents items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_folder_delete_reparents_items(client: AsyncClient, library: dict) -> None:
    parent = await _create_folder(client, library["id"], "Parent")
    child = await _create_folder(client, library["id"], "Child", parent)
    item_id = await _upload(client, library["id"], folder_id=child)

    # Delete the child folder; its item should reparent to Parent.
    resp = await client.delete(
        f"/libraries/{library['id']}/folders/{child}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200

    d = await client.get(
        f"/libraries/{library['id']}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert d.json()["folder_id"] == parent
