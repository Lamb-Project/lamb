"""Import + content-serving edge cases and error paths.

Ports the import/content-serving portions of ``tests/test_edge_cases.py``
and strengthens them. Covers: the upload size limit (413), 0-byte rejection
(400), Unicode + spaced filenames, path traversal on the page / image /
original routes, malformed JSON in plugin_params / api_keys (400), wrong
file extension for a plugin (400), a nonexistent plugin (400), and a plugin
whose supported_source_types excludes the requested source (400).

Sources: ``backend/routers/importing.py``, ``backend/routers/content.py``.
"""

from __future__ import annotations

import io

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
# Upload size limit
# ---------------------------------------------------------------------------


async def test_upload_exceeds_size_limit_413(
    client: AsyncClient, library: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file larger than MAX_UPLOAD_SIZE_BYTES returns 413."""
    import config  # noqa: PLC0415
    import routers.importing as importing_mod  # noqa: PLC0415

    # importing.py did ``from config import MAX_UPLOAD_SIZE_BYTES`` — patch
    # both the source and the module-level name it bound.
    monkeypatch.setattr(config, "MAX_UPLOAD_SIZE_BYTES", 100)
    monkeypatch.setattr(importing_mod, "MAX_UPLOAD_SIZE_BYTES", 100)

    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("big.md", io.BytesIO(b"x" * 200), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Too Big"},
    )
    assert resp.status_code == 413, resp.text


# ---------------------------------------------------------------------------
# 0-byte rejection
# ---------------------------------------------------------------------------


async def test_empty_file_rejected_400(client: AsyncClient, library: dict) -> None:
    """A 0-byte upload is refused with 400 and creates no item."""
    lib_id = library["id"]
    before = await client.get(f"/libraries/{lib_id}/items", headers=AUTH_HEADERS)
    count_before = before.json()["total"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("empty.md", io.BytesIO(b""), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Empty"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"].lower()
    assert "empty" in detail or "0 bytes" in detail

    after = await client.get(f"/libraries/{lib_id}/items", headers=AUTH_HEADERS)
    assert after.json()["total"] == count_before


# ---------------------------------------------------------------------------
# Unicode + spaced filenames
# ---------------------------------------------------------------------------


async def test_unicode_filename_accepted(client: AsyncClient, library: dict) -> None:
    """A file with a Unicode name imports and serves its content."""
    lib_id = library["id"]
    content = "# Documento académico\n\nacentos: é è ê ë."
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("documento_académico.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Académico"},
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    assert await poll_until_ready(client, lib_id, item_id) == "ready"

    served = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS
    )
    assert "académico" in served.text


async def test_spaced_filename_accepted(client: AsyncClient, library: dict) -> None:
    """A file with spaces in its name imports successfully."""
    lib_id = library["id"]
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("my document file.md", io.BytesIO(b"# Spaced"), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Spaced"},
    )
    assert resp.status_code == 202, resp.text
    assert await poll_until_ready(client, lib_id, resp.json()["item_id"]) == "ready"


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------


async def test_path_traversal_page_blocked(client: AsyncClient, library: dict) -> None:
    """A ../ page name never escapes the item dir (404/400)."""
    lib_id = library["id"]
    item_id = await _upload_ready(client, lib_id, "# Safe")

    for attempt in ("../../metadata.json", "..%2F..%2Fetc%2Fpasswd"):
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/content/pages/{attempt}",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code in (400, 404), resp.text
        assert "passwd" not in resp.text.lower() or resp.status_code != 200


async def test_path_traversal_image_blocked(client: AsyncClient, library: dict) -> None:
    """A ../ image name never escapes the item dir (404/400)."""
    lib_id = library["id"]
    item_id = await _upload_ready(client, lib_id, "# Safe")

    for attempt in ("../../../metadata.json", "..%2F..%2F..%2Fetc%2Fpasswd"):
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/content/images/{attempt}",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code in (400, 404), resp.text


async def test_path_traversal_original_blocked(client: AsyncClient, library: dict) -> None:
    """A ../ original filename never escapes the item dir (404/400)."""
    lib_id = library["id"]
    item_id = await _upload_ready(client, lib_id, "# Safe")

    for attempt in ("../../metadata.json", "..%2F..%2Fetc%2Fpasswd"):
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/original/{attempt}",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code in (400, 404), resp.text


# ---------------------------------------------------------------------------
# Malformed JSON in form fields
# ---------------------------------------------------------------------------


async def test_malformed_plugin_params_json_400(client: AsyncClient, library: dict) -> None:
    """Invalid JSON in plugin_params returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("t.md", io.BytesIO(b"# T"), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "T", "plugin_params": "{not json"},
    )
    assert resp.status_code == 400, resp.text
    assert "plugin_params" in resp.json()["detail"].lower()


async def test_malformed_api_keys_json_400(client: AsyncClient, library: dict) -> None:
    """Invalid JSON in api_keys returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("t.md", io.BytesIO(b"# T"), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "T", "api_keys": "not json"},
    )
    assert resp.status_code == 400, resp.text
    assert "api_keys" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Plugin selection errors
# ---------------------------------------------------------------------------


async def test_nonexistent_plugin_400(client: AsyncClient, library: dict) -> None:
    """An unknown plugin name returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("t.md", io.BytesIO(b"# T"), "text/markdown")},
        data={"plugin_name": "nope_plugin", "title": "Bad"},
    )
    assert resp.status_code == 400, resp.text
    assert "not found" in resp.json()["detail"].lower()


async def test_wrong_extension_for_plugin_400(client: AsyncClient, library: dict) -> None:
    """An extension the plugin doesn't accept is rejected with 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("fake.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
        data={"plugin_name": "simple_import", "title": "Wrong Ext"},
    )
    assert resp.status_code == 400, resp.text
    assert "does not support" in resp.json()["detail"].lower()


async def test_file_plugin_does_not_support_file_source_400(
    client: AsyncClient, library: dict
) -> None:
    """A URL-only plugin (url_import) rejects file uploads with 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("t.md", io.BytesIO(b"# T"), "text/markdown")},
        data={"plugin_name": "url_import", "title": "Bad"},
    )
    assert resp.status_code == 400, resp.text
    assert "does not support file" in resp.json()["detail"].lower()
