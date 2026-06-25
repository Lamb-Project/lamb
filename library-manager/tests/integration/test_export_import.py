"""Library export / import via ZIP (``backend/routers/content.py`` +
``backend/services/export_service.py``).

Ports ``tests/test_export_import.py`` and strengthens it: validates the
manifest (format_version 1.0, type, content/{item}/ layout), that only
``ready`` items are exported, a full export→import round-trip with NEW ids
and permalinks, and the import error paths (invalid zip, missing manifest,
non-.zip filename, bad org id, empty file, oversize).
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from _helpers import AUTH_HEADERS, poll_until_ready, text_file
from httpx import AsyncClient


async def _upload_ready(client: AsyncClient, lib_id: str, content: str,
                        *, title: str = "Doc", filename: str = "doc.md") -> str:
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files=text_file(content, filename),
        data={"plugin_name": "simple_import", "title": title},
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready", status
    return item_id


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def test_export_produces_valid_zip(client: AsyncClient, library: dict) -> None:
    """Export streams a ZIP with a 1.0 manifest and content/{item}/ files."""
    lib_id = library["id"]
    await _upload_ready(client, lib_id, "# Exported\n\nbody", title="Export Doc")

    resp = await client.get(f"/libraries/{lib_id}/export", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    assert "application/zip" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "manifest.json" in names
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["format_version"] == "1.0"
    assert manifest["type"] == "library_export"
    assert len(manifest["items"]) == 1
    assert manifest["items"][0]["title"] == "Export Doc"

    item_id = manifest["items"][0]["id"]
    content_files = [n for n in names if n.startswith(f"content/{item_id}/")]
    assert any(n.endswith("metadata.json") for n in content_files)
    assert any(n.endswith("full.md") for n in content_files)


async def test_export_excludes_non_ready_items(client: AsyncClient, library: dict) -> None:
    """Only ready items appear in the export manifest."""
    lib_id = library["id"]
    ready_id = await _upload_ready(client, lib_id, "# Ready", title="Ready")

    # Force a failed item by faking simple_import to blow up. simple_import
    # reads the file directly, so an undecodable byte sequence with a forced
    # plugin error isn't available — instead inject a failed row directly.
    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import ContentItem  # noqa: PLC0415

    db = get_session_direct()
    failed_id = "item-failed-export"
    try:
        db.add(ContentItem(
            id=failed_id, library_id=lib_id, organization_id="org-test",
            title="Failed One", source_type="file", import_plugin="simple_import",
            base_path="/nonexistent/failed", permalink_base="/docs/x/y/z",
            status="failed", error_message="boom",
        ))
        db.commit()

        resp = await client.get(f"/libraries/{lib_id}/export", headers=AUTH_HEADERS)
        assert resp.status_code == 200, resp.text
        manifest = json.loads(zipfile.ZipFile(io.BytesIO(resp.content)).read("manifest.json"))
        ids = {i["id"] for i in manifest["items"]}
        assert ready_id in ids
        assert failed_id not in ids
    finally:
        db.query(ContentItem).filter(ContentItem.id == failed_id).delete()
        db.commit()
        db.close()


async def test_export_missing_library_404(client: AsyncClient) -> None:
    """Export of an unknown library is 404."""
    resp = await client.get("/libraries/no-such-lib/export", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Round-trip import
# ---------------------------------------------------------------------------


async def test_import_roundtrip_new_ids_and_permalinks(
    client: AsyncClient, library: dict
) -> None:
    """Exported ZIP re-imports into a NEW library with new ids + permalinks."""
    lib_id = library["id"]
    item_id = await _upload_ready(
        client, lib_id, "# Roundtrip\n\nsurvives", title="Roundtrip Doc"
    )

    exported = await client.get(f"/libraries/{lib_id}/export", headers=AUTH_HEADERS)
    zip_data = exported.content

    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-imported"},
        files={"file": ("export.zip", io.BytesIO(zip_data), "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()
    assert result["item_count"] == 1
    new_lib_id = result["library_id"]
    assert new_lib_id != lib_id

    items = await client.get(f"/libraries/{new_lib_id}/items", headers=AUTH_HEADERS)
    assert items.status_code == 200, items.text
    new_items = items.json()["items"]
    assert len(new_items) == 1
    new_item_id = new_items[0]["id"]
    assert new_item_id != item_id
    assert new_items[0]["status"] == "ready"

    content = await client.get(
        f"/libraries/{new_lib_id}/items/{new_item_id}/content", headers=AUTH_HEADERS
    )
    assert content.status_code == 200, content.text
    assert "Roundtrip" in content.text

    meta = await client.get(
        f"/libraries/{new_lib_id}/items/{new_item_id}/metadata", headers=AUTH_HEADERS
    )
    assert meta.status_code == 200, meta.text
    full = meta.json()["permalinks"]["full_markdown"]
    assert new_lib_id in full
    assert new_item_id in full


# ---------------------------------------------------------------------------
# Import error paths
# ---------------------------------------------------------------------------


async def test_import_invalid_zip_400(client: AsyncClient) -> None:
    """A .zip-named file that isn't a real ZIP returns 400."""
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-bad"},
        files={"file": ("not-a-zip.zip", io.BytesIO(b"not a zip"), "application/zip")},
    )
    assert resp.status_code == 400, resp.text


async def test_import_zip_missing_manifest_400(client: AsyncClient) -> None:
    """A valid ZIP without manifest.json returns 400."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("random.txt", "hello")
    buf.seek(0)
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-nomanifest"},
        files={"file": ("x.zip", buf, "application/zip")},
    )
    assert resp.status_code == 400, resp.text


async def test_import_non_zip_filename_400(client: AsyncClient) -> None:
    """A file not ending in .zip is rejected with 400."""
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-test"},
        files={"file": ("file.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert resp.status_code == 400, resp.text


async def test_import_bad_org_id_400(client: AsyncClient) -> None:
    """An org id that violates the [a-zA-Z0-9_-]+ regex returns 400."""
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "bad org/../id"},
        files={"file": ("x.zip", io.BytesIO(b"PK"), "application/zip")},
    )
    assert resp.status_code == 400, resp.text


async def test_import_missing_org_id_422(client: AsyncClient) -> None:
    """The organization_id query param is required."""
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        files={"file": ("x.zip", io.BytesIO(b"PK"), "application/zip")},
    )
    assert resp.status_code == 422, resp.text


async def test_import_empty_file_400(client: AsyncClient) -> None:
    """A 0-byte upload is rejected with 400."""
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-empty"},
        files={"file": ("x.zip", io.BytesIO(b""), "application/zip")},
    )
    assert resp.status_code == 400, resp.text


async def test_import_duplicate_name_409(client: AsyncClient, library: dict) -> None:
    """Importing the same library name twice into one org returns 409."""
    lib_id = library["id"]
    await _upload_ready(client, lib_id, "# Dup", title="Dup Doc")
    zip_data = (await client.get(f"/libraries/{lib_id}/export", headers=AUTH_HEADERS)).content

    org = "org-dup-import"
    first = await client.post(
        "/libraries/import", headers=AUTH_HEADERS, params={"organization_id": org},
        files={"file": ("e.zip", io.BytesIO(zip_data), "application/zip")},
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/libraries/import", headers=AUTH_HEADERS, params={"organization_id": org},
        files={"file": ("e.zip", io.BytesIO(zip_data), "application/zip")},
    )
    assert second.status_code == 409, second.text


async def test_import_oversize_413(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ZIP exceeding MAX_ZIP_IMPORT_SIZE_BYTES returns 413."""
    import config  # noqa: PLC0415

    # The route imports the name locally from config at call time.
    monkeypatch.setattr(config, "MAX_ZIP_IMPORT_SIZE_BYTES", 10)
    resp = await client.post(
        "/libraries/import",
        headers=AUTH_HEADERS,
        params={"organization_id": "org-big"},
        files={"file": ("x.zip", io.BytesIO(b"x" * 100), "application/zip")},
    )
    assert resp.status_code == 413, resp.text
