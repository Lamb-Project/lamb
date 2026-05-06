"""Tests for library export and import via ZIP files."""

import asyncio
import io
import json
import time
import zipfile

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}

_POLL_TIMEOUT = 15


async def _wait_for_ready(client, lib_id, item_id, timeout=_POLL_TIMEOUT):
    """Poll until item is ready or failed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status",
            headers=AUTH_HEADERS,
        )
        status = resp.json()["status"]
        if status in ("ready", "failed"):
            return status
        await asyncio.sleep(0.5)
    return "timeout"


@pytest.mark.asyncio
async def test_export_library(client: AsyncClient, library: dict):
    """Exporting a library should produce a valid ZIP with manifest + content."""
    lib_id = library["id"]

    # Upload a file first so the export has content.
    content = "# Export Test\n\nThis content should appear in the ZIP."
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("export-test.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Export Test Doc"},
    )
    item_id = resp.json()["item_id"]
    await _wait_for_ready(client, lib_id, item_id)

    # Export.
    resp = await client.get(f"/libraries/{lib_id}/export", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "application/zip" in resp.headers.get("content-type", "")

    # Validate ZIP structure.
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "manifest.json" in names

    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["format_version"] == "1.0"
    assert manifest["type"] == "library_export"
    assert len(manifest["items"]) == 1
    assert manifest["items"][0]["title"] == "Export Test Doc"

    # Check content files are present.
    content_files = [n for n in names if n.startswith("content/")]
    assert len(content_files) >= 2  # At least metadata.json + full.md


@pytest.mark.asyncio
async def test_import_library_from_zip(client: AsyncClient, library: dict):
    """Importing a library from ZIP should create a new library with new IDs."""
    lib_id = library["id"]

    # Upload content.
    content = "# Import Roundtrip\n\nThis should survive export+import."
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("roundtrip.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Roundtrip Doc"},
    )
    item_id = resp.json()["item_id"]
    await _wait_for_ready(client, lib_id, item_id)

    # Export.
    resp = await client.get(f"/libraries/{lib_id}/export", headers=AUTH_HEADERS)
    zip_data = resp.content

    # Import into a different org.
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-imported"},
        files={"file": ("export.zip", io.BytesIO(zip_data), "application/zip")},
    )
    assert resp.status_code == 201
    result = resp.json()
    assert result["item_count"] == 1
    new_lib_id = result["library_id"]
    assert new_lib_id != lib_id  # New ID generated

    # Verify imported content is readable.
    resp = await client.get(
        f"/libraries/{new_lib_id}/items",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    new_item_id = items[0]["id"]
    assert new_item_id != item_id  # New ID generated
    assert items[0]["status"] == "ready"

    # Read markdown from imported item.
    resp = await client.get(
        f"/libraries/{new_lib_id}/items/{new_item_id}/content",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "Import Roundtrip" in resp.text

    # Verify permalinks point to the NEW IDs.
    resp = await client.get(
        f"/libraries/{new_lib_id}/items/{new_item_id}/metadata",
        headers=AUTH_HEADERS,
    )
    meta = resp.json()
    assert new_lib_id in meta["permalinks"]["full_markdown"]
    assert new_item_id in meta["permalinks"]["full_markdown"]


@pytest.mark.asyncio
async def test_import_invalid_zip(client: AsyncClient):
    """Importing a non-ZIP file should return 400."""
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-bad"},
        files={"file": ("not-a-zip.zip", io.BytesIO(b"not a zip"), "application/zip")},
    )
    assert resp.status_code == 400
