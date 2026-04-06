"""Tests for content serving endpoints: pages, images, metadata, source_ref, original file."""

import asyncio
import io
import time

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}
_POLL_TIMEOUT = 15


async def _wait_for_ready(client, lib_id, item_id, timeout=_POLL_TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS
        )
        if resp.json()["status"] in ("ready", "failed"):
            return resp.json()["status"]
        await asyncio.sleep(0.5)
    return "timeout"


async def _upload_md(client, lib_id, content, title="Test Doc", filename="test.md"):
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": (filename, io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": title},
    )
    item_id = resp.json()["item_id"]
    await _wait_for_ready(client, lib_id, item_id)
    return item_id


@pytest.mark.asyncio
async def test_get_metadata_has_permalinks(client: AsyncClient, library: dict):
    """metadata.json should contain permalink URLs for all content pieces."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "# Test\n\nContent here.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/metadata", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    meta = resp.json()
    assert "permalinks" in meta
    assert meta["permalinks"]["full_markdown"].endswith("/content/full.md")
    assert meta["item_id"] == item_id


@pytest.mark.asyncio
async def test_get_source_ref(client: AsyncClient, library: dict):
    """source_ref.json should describe the import source."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "# Source Ref Test")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/source_ref", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    src = resp.json()
    assert src["type"] == "file"
    assert "original_filename" in src


@pytest.mark.asyncio
async def test_get_original_file(client: AsyncClient, library: dict):
    """Original file should be servable via /original/{filename}."""
    lib_id = library["id"]
    content = "# Original File Test\n\nContent."
    item_id = await _upload_md(client, lib_id, content, filename="original-test.md")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/original/original-test.md",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "Original File Test" in resp.text


@pytest.mark.asyncio
async def test_content_format_text(client: AsyncClient, library: dict):
    """?format=text should return plain text."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "# Text Format\n\nParagraph.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
        params={"format": "text"},
    )
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_pages_empty_for_text(client: AsyncClient, library: dict):
    """A plain text file should have no pages."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "No pages here.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_images_empty_for_text(client: AsyncClient, library: dict):
    """A plain text file should have no images."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "No images here.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_nonexistent_item_returns_404(client: AsyncClient, library: dict):
    """Requesting a non-existent item should return 404."""
    lib_id = library["id"]
    resp = await client.get(
        f"/libraries/{lib_id}/items/fake-item-id", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nonexistent_page_returns_404(client: AsyncClient, library: dict):
    """Requesting a non-existent page should return 404."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "No pages.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages/page_999",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nonexistent_image_returns_404(client: AsyncClient, library: dict):
    """Requesting a non-existent image should return 404."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "No images.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/fake.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nonexistent_original_returns_404(client: AsyncClient, library: dict):
    """Requesting a non-existent original file should return 404."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "Content.")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/original/nonexistent.pdf",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_item_removes_content(client: AsyncClient, library: dict):
    """Deleting an item should make its content inaccessible."""
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, "# Will Be Deleted")

    resp = await client.delete(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_items_filter_by_status(client: AsyncClient, library: dict):
    """Listing items with status filter should work."""
    lib_id = library["id"]
    await _upload_md(client, lib_id, "# Ready Item")

    resp = await client.get(
        f"/libraries/{lib_id}/items",
        headers=AUTH_HEADERS,
        params={"status": "ready"},
    )
    assert resp.status_code == 200
    assert all(i["status"] == "ready" for i in resp.json()["items"])


@pytest.mark.asyncio
async def test_items_filter_by_ids(client: AsyncClient, library: dict):
    """Listing items with ids filter should return only matching items."""
    lib_id = library["id"]
    item1 = await _upload_md(client, lib_id, "# Item 1", title="Item 1")
    await _upload_md(client, lib_id, "# Item 2", title="Item 2")

    resp = await client.get(
        f"/libraries/{lib_id}/items",
        headers=AUTH_HEADERS,
        params={"ids": item1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == item1
