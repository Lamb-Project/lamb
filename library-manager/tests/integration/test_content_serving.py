"""Content retrieval and management routes (``backend/routers/content.py``).

Ports ``tests/test_content_serving.py`` into the integration tier and
strengthens it: exercises listing (limit/offset/status/ids), full detail,
status, every content-serving format, the pages/images/original/metadata/
source_ref endpoints, deletion, and the 404 paths for each. Items with real
pages + images are produced by a faked ``markitdown_plus_import`` against a
``.pdf`` upload (markitdown + fitz are mocked at the boundary, so the bytes
on disk are irrelevant).
"""

from __future__ import annotations

import io

from _fakes import FakeFitzDoc, patch_fitz, patch_markitdown
from _helpers import AUTH_HEADERS, poll_until_ready, text_file
from httpx import AsyncClient


async def _upload_simple(client: AsyncClient, lib_id: str, content: str,
                         *, title: str = "Doc", filename: str = "doc.md") -> str:
    """Upload via simple_import, poll to ready, return the item id."""
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


async def _upload_pdf_with_pages_and_images(
    client: AsyncClient, lib_id: str, *, title: str = "PDF Doc"
) -> str:
    """Upload a fake .pdf through markitdown_plus → 2 pages + 1 image."""
    files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")}
    with patch_markitdown(text="p1\n\n---\n\np2"), patch_fitz(
        FakeFitzDoc(pages=1, images_per_page=1)
    ):
        resp = await client.post(
            f"/libraries/{lib_id}/import/file",
            headers=AUTH_HEADERS,
            files=files,
            data={
                "plugin_name": "markitdown_plus_import",
                "title": title,
                "plugin_params": '{"image_descriptions": "basic"}',
            },
        )
        assert resp.status_code == 202, resp.text
        item_id = resp.json()["item_id"]
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready", status
    return item_id


# ---------------------------------------------------------------------------
# Listing: limit, offset, status, ids
# ---------------------------------------------------------------------------


async def test_list_items_returns_uploaded(client: AsyncClient, library: dict) -> None:
    """GET /items returns the items uploaded into the library."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Listed")

    resp = await client.get(f"/libraries/{lib_id}/items", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == item_id


async def test_list_items_missing_library_404(client: AsyncClient) -> None:
    """GET /items on an unknown library returns 404."""
    resp = await client.get("/libraries/no-such-lib/items", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text


async def test_list_items_limit_offset(client: AsyncClient, library: dict) -> None:
    """limit + offset paginate; total stays the full count."""
    lib_id = library["id"]
    await _upload_simple(client, lib_id, "# A", title="A")
    await _upload_simple(client, lib_id, "# B", title="B")

    page1 = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"limit": 1, "offset": 0}
    )
    page2 = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"limit": 1, "offset": 1}
    )
    assert page1.status_code == 200, page1.text
    assert page2.status_code == 200, page2.text
    assert page1.json()["total"] == 2
    assert len(page1.json()["items"]) == 1
    assert len(page2.json()["items"]) == 1
    assert page1.json()["items"][0]["id"] != page2.json()["items"][0]["id"]


async def test_list_items_limit_out_of_range_422(client: AsyncClient, library: dict) -> None:
    """limit below 1 or above 500 is rejected by query validation."""
    lib_id = library["id"]
    too_small = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"limit": 0}
    )
    too_big = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"limit": 501}
    )
    assert too_small.status_code == 422, too_small.text
    assert too_big.status_code == 422, too_big.text


async def test_list_items_filter_by_status(client: AsyncClient, library: dict) -> None:
    """status filter returns only items in that status."""
    lib_id = library["id"]
    await _upload_simple(client, lib_id, "# Ready")

    resp = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"status": "ready"}
    )
    assert resp.status_code == 200, resp.text
    assert all(i["status"] == "ready" for i in resp.json()["items"])

    none = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"status": "failed"}
    )
    assert none.status_code == 200, none.text
    assert none.json()["total"] == 0


async def test_list_items_filter_by_ids_csv(client: AsyncClient, library: dict) -> None:
    """ids CSV filter returns only the requested items (whitespace tolerant)."""
    lib_id = library["id"]
    item1 = await _upload_simple(client, lib_id, "# 1", title="1")
    item2 = await _upload_simple(client, lib_id, "# 2", title="2")
    await _upload_simple(client, lib_id, "# 3", title="3")

    resp = await client.get(
        f"/libraries/{lib_id}/items",
        headers=AUTH_HEADERS,
        params={"ids": f" {item1} , {item2} , "},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 2
    assert {i["id"] for i in data["items"]} == {item1, item2}


# ---------------------------------------------------------------------------
# Item detail and status
# ---------------------------------------------------------------------------


async def test_get_item_detail(client: AsyncClient, library: dict) -> None:
    """GET /items/{id} returns the full detail dict with permalink_base."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Detail")

    resp = await client.get(f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["id"] == item_id
    assert "metadata" in detail
    assert "import_params" in detail
    assert detail["permalink_base"]


async def test_get_item_wrong_library_404(client: AsyncClient, library: dict) -> None:
    """An item id valid in one library 404s when queried under another."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# X")

    other = await client.post("/libraries", headers=AUTH_HEADERS, json={
        "id": "lib-other-cs", "organization_id": "org-test", "name": "Other CS Lib",
    })
    assert other.status_code in (201, 409), other.text
    resp = await client.get(
        f"/libraries/lib-other-cs/items/{item_id}", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_get_item_missing_404(client: AsyncClient, library: dict) -> None:
    """GET /items/{id} for an unknown item returns 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/no-such-item", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_get_item_status(client: AsyncClient, library: dict) -> None:
    """GET /items/{id}/status returns terminal status and stats."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Status")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["item_id"] == item_id
    assert data["status"] == "ready"
    assert data["error_message"] is None


async def test_get_status_missing_404(client: AsyncClient, library: dict) -> None:
    """Status of an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/nope/status", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Full content: markdown / text / html
# ---------------------------------------------------------------------------


async def test_content_default_markdown(client: AsyncClient, library: dict) -> None:
    """GET /content defaults to text/markdown and returns the body."""
    lib_id = library["id"]
    body = "# Title\n\nbody text"
    item_id = await _upload_simple(client, lib_id, body)

    resp = await client.get(f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    assert "text/markdown" in resp.headers["content-type"]
    assert resp.text == body


async def test_content_format_text(client: AsyncClient, library: dict) -> None:
    """?format=text returns text/plain."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Plain\n\npara")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
        params={"format": "text"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/plain" in resp.headers["content-type"]


async def test_content_format_html(client: AsyncClient, library: dict) -> None:
    """?format=html renders markdown to HTML."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Heading\n\nparagraph")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
        params={"format": "html"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/html" in resp.headers["content-type"]
    assert "<h1" in resp.text


async def test_content_missing_item_404(client: AsyncClient, library: dict) -> None:
    """GET /content for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/missing/content", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Pages (item built via faked markitdown_plus)
# ---------------------------------------------------------------------------


async def test_list_pages_and_get_page(client: AsyncClient, library: dict) -> None:
    """A 2-page PDF lists its pages and serves each by name."""
    lib_id = library["id"]
    item_id = await _upload_pdf_with_pages_and_images(client, lib_id)

    listing = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages", headers=AUTH_HEADERS
    )
    assert listing.status_code == 200, listing.text
    # The capability item_router wins on /content/pages — renderer JSON shape.
    body = listing.json()
    assert isinstance(body, list)
    assert [p["page"] for p in body] == [1, 2]

    page = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages/page_001",
        headers=AUTH_HEADERS,
    )
    assert page.status_code == 200, page.text
    assert page.text == "p1"


async def test_get_page_html_format(client: AsyncClient, library: dict) -> None:
    """A page can be rendered as HTML via ?format=html."""
    lib_id = library["id"]
    item_id = await _upload_pdf_with_pages_and_images(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages/page_002.md",
        headers=AUTH_HEADERS,
        params={"format": "html"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/html" in resp.headers["content-type"]


async def test_get_page_missing_404(client: AsyncClient, library: dict) -> None:
    """A nonexistent page name returns 404."""
    lib_id = library["id"]
    item_id = await _upload_pdf_with_pages_and_images(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages/page_999",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404, resp.text


async def test_list_pages_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Listing pages for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/content/pages", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


async def test_list_images_and_get_image_bytes(client: AsyncClient, library: dict) -> None:
    """An item with extracted images lists them and serves the raw bytes."""
    lib_id = library["id"]
    item_id = await _upload_pdf_with_pages_and_images(client, lib_id)

    listing = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images", headers=AUTH_HEADERS
    )
    assert listing.status_code == 200, listing.text
    # Capability renderer JSON shape (item_router wins on /content/images too).
    gallery = listing.json()
    assert isinstance(gallery, list)
    assert gallery
    filename = gallery[0]["filename"]

    # Legacy image-bytes route /content/images/{name} still works.
    img = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/{filename}",
        headers=AUTH_HEADERS,
    )
    assert img.status_code == 200, img.text
    assert img.content == b"\x89PNG-fake-image"


async def test_get_image_missing_404(client: AsyncClient, library: dict) -> None:
    """A nonexistent image returns 404."""
    lib_id = library["id"]
    item_id = await _upload_pdf_with_pages_and_images(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/missing.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404, resp.text


async def test_list_images_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Listing images for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/content/images", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Original file
# ---------------------------------------------------------------------------


async def test_get_original_file(client: AsyncClient, library: dict) -> None:
    """The original upload is servable by filename."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Orig\n\nbody", filename="orig.md")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/original/orig.md", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert "Orig" in resp.text


async def test_get_original_missing_404(client: AsyncClient, library: dict) -> None:
    """A nonexistent original filename returns 404."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# X", filename="x.md")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/original/nope.pdf", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_get_original_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Original for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/original/x.md", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# metadata / source_ref
# ---------------------------------------------------------------------------


async def test_get_metadata_has_permalinks(client: AsyncClient, library: dict) -> None:
    """metadata.json carries permalinks and item_id."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Meta\n\nbody")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/metadata", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    meta = resp.json()
    assert meta["item_id"] == item_id
    assert meta["permalinks"]["full_markdown"].endswith("/content/full.md")


async def test_get_metadata_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Metadata for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/metadata", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_get_source_ref(client: AsyncClient, library: dict) -> None:
    """source_ref.json describes the file import source."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Src")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/source_ref", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    src = resp.json()
    assert src["type"] == "file"
    assert "original_filename" in src


async def test_get_source_ref_missing_item_404(client: AsyncClient, library: dict) -> None:
    """source_ref for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/source_ref", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


async def test_delete_item_removes_content(client: AsyncClient, library: dict) -> None:
    """Deleting an item makes it (and its content) inaccessible."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Doomed")

    resp = await client.delete(f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    assert item_id in resp.json()["message"]

    gone = await client.get(f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS)
    assert gone.status_code == 404, gone.text
    content = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS
    )
    assert content.status_code == 404, content.text


async def test_delete_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Deleting an unknown item returns 404."""
    resp = await client.delete(
        f"/libraries/{library['id']}/items/ghost", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# On-disk-missing paths (DB row exists, files gone)
# ---------------------------------------------------------------------------


async def test_content_missing_on_disk_404(client: AsyncClient, library: dict) -> None:
    """When full.md is gone but the DB row remains, /content is 404."""
    from services import content_service  # noqa: PLC0415

    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Disk")
    base = content_service.get_item_base_path(library["organization_id"], lib_id, item_id)
    (base / "content" / "full.md").unlink()

    resp = await client.get(f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text
    assert "on disk" in resp.json()["detail"].lower()


async def test_metadata_missing_on_disk_404(client: AsyncClient, library: dict) -> None:
    """When metadata.json is gone but the DB row remains, /metadata is 404."""
    from services import content_service  # noqa: PLC0415

    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Meta gone")
    base = content_service.get_item_base_path(library["organization_id"], lib_id, item_id)
    (base / "metadata.json").unlink()

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/metadata", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_source_ref_missing_on_disk_404(client: AsyncClient, library: dict) -> None:
    """When source_ref.json is gone but the DB row remains, /source_ref is 404."""
    from services import content_service  # noqa: PLC0415

    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Src gone")
    base = content_service.get_item_base_path(library["organization_id"], lib_id, item_id)
    (base / "source_ref.json").unlink()

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/source_ref", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_get_page_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Single-page route 404s for an unknown item."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/content/pages/page_001",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404, resp.text


async def test_get_image_bytes_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Legacy image-bytes route 404s for an unknown item."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/content/images/x.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404, resp.text
