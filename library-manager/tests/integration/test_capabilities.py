"""Capability handler endpoints (``backend/routers/capabilities.py``).

Ports ``tests/test_capabilities.py`` (HTTP portions) into the integration
tier and strengthens it. Covers the registry list, per-item capability list
(including the legacy ``["text"]`` fallback), capability dispatch (text →
markdown, pages → JSON, images → JSON gallery), the 404 paths (unknown
capability, no handler, handler-unavailable) and the 500 path (handler
crash). Critically it asserts ROUTE ORDERING from ``backend/main.py``:

* ``/content/{capability}`` (item_router) wins over the legacy literal
  ``/content/pages`` and ``/content/images`` list routes — so those URLs
  return the renderer JSON shape, not bare filename lists.
* ``/content/images/file/{filename}`` (raw_router) wins over the legacy
  ``/content/images/{image_name}`` route and serves raw bytes.
* The legacy single-page ``/content/pages/{page}`` and image-bytes
  ``/content/images/{name}`` routes still resolve (extra path segments).
"""

from __future__ import annotations

import io
import json
from unittest import mock

from _fakes import FakeFitzDoc, patch_fitz, patch_markitdown
from _helpers import AUTH_HEADERS, poll_until_ready, text_file
from httpx import AsyncClient


async def _upload_simple(client: AsyncClient, lib_id: str, content: str,
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


async def _upload_pdf(client: AsyncClient, lib_id: str, *, title: str = "PDF") -> str:
    """Build an item with pages + images via faked markitdown_plus."""
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
# Registry
# ---------------------------------------------------------------------------


async def test_capabilities_registry_lists_handlers(client: AsyncClient) -> None:
    """GET /capabilities lists every registered handler."""
    resp = await client.get("/capabilities", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    names = {row["capability"] for row in resp.json()["capabilities"]}
    assert {"text", "pages", "images"}.issubset(names)


# ---------------------------------------------------------------------------
# Per-item capability list
# ---------------------------------------------------------------------------


async def test_item_capabilities_text_only(client: AsyncClient, library: dict) -> None:
    """A markdown upload exposes only the text capability."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Hi\n\nbody")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/capabilities", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["item_id"] == item_id
    assert data["capabilities"] == ["text"]


async def test_item_capabilities_pdf_has_pages_images(client: AsyncClient, library: dict) -> None:
    """A faked PDF exposes text, pages and images."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/capabilities", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["capabilities"]) == {"text", "pages", "images"}


async def test_item_capabilities_legacy_fallback(client: AsyncClient, library: dict) -> None:
    """An item whose metadata.json lacks 'capabilities' defaults to ['text']."""
    from services import content_service  # noqa: PLC0415

    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# Legacy")

    detail = await client.get(f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS)
    org_id = library["organization_id"]
    base = content_service.get_item_base_path(org_id, lib_id, item_id)
    meta_path = base / "metadata.json"
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    raw.pop("capabilities", None)
    meta_path.write_text(json.dumps(raw), encoding="utf-8")
    assert detail.status_code == 200, detail.text

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/capabilities", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["capabilities"] == ["text"]


async def test_item_capabilities_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Capabilities for an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/capabilities", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Capability dispatch — text
# ---------------------------------------------------------------------------


async def test_content_text_returns_markdown(client: AsyncClient, library: dict) -> None:
    """GET /content/text returns the full markdown body (text/markdown)."""
    lib_id = library["id"]
    body = "# Title\n\nthe quick brown fox"
    item_id = await _upload_simple(client, lib_id, body)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/text", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert "text/markdown" in resp.headers["content-type"]
    assert resp.text == body


# ---------------------------------------------------------------------------
# Route ordering — the heart of this module
# ---------------------------------------------------------------------------


async def test_content_pages_returns_renderer_json(client: AsyncClient, library: dict) -> None:
    """/content/pages resolves to the capability handler → renderer JSON list."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert "application/json" in resp.headers["content-type"]
    body = resp.json()
    # Renderer shape: a list of {page, markdown}, NOT the legacy {pages, count}.
    assert isinstance(body, list)
    assert [p["page"] for p in body] == [1, 2]
    assert body[0]["markdown"] == "p1"


async def test_content_images_returns_renderer_json(client: AsyncClient, library: dict) -> None:
    """/content/images resolves to the capability handler → renderer JSON gallery."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert "application/json" in resp.headers["content-type"]
    body = resp.json()
    # Renderer shape: a list of {filename, mime, url}, NOT legacy {images, count}.
    assert isinstance(body, list)
    assert body
    assert "filename" in body[0]
    assert "/content/images/file/" in body[0]["url"]


async def test_image_file_raw_route_wins_and_serves_bytes(
    client: AsyncClient, library: dict
) -> None:
    """/content/images/file/{fn} (raw_router) beats the legacy route and serves bytes."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    gallery = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images", headers=AUTH_HEADERS
    )
    filename = gallery.json()[0]["filename"]

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/file/{filename}",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.content == b"\x89PNG-fake-image"
    assert "image/png" in resp.headers["content-type"]


async def test_image_file_raw_route_missing_404(client: AsyncClient, library: dict) -> None:
    """The raw image-file route 404s for a missing filename."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/file/missing.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404, resp.text


async def test_image_file_raw_route_missing_item_404(client: AsyncClient, library: dict) -> None:
    """The raw image-file route 404s for an unknown item."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/content/images/file/x.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404, resp.text


async def test_legacy_single_page_route_still_works(client: AsyncClient, library: dict) -> None:
    """The legacy /content/pages/{page} route still serves a single page's markdown."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages/page_001",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert "text/markdown" in resp.headers["content-type"]
    assert resp.text == "p1"


async def test_legacy_image_bytes_route_still_works(client: AsyncClient, library: dict) -> None:
    """The legacy /content/images/{name} route still serves raw image bytes."""
    lib_id = library["id"]
    item_id = await _upload_pdf(client, lib_id)

    gallery = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images", headers=AUTH_HEADERS
    )
    filename = gallery.json()[0]["filename"]

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/{filename}",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.content == b"\x89PNG-fake-image"


# ---------------------------------------------------------------------------
# Dispatch error paths
# ---------------------------------------------------------------------------


async def test_unknown_capability_404(client: AsyncClient, library: dict) -> None:
    """A capability value not in the enum returns 404."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "x")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/sparkles", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text
    assert "unknown capability" in resp.json()["detail"].lower()


async def test_capability_no_handler_404(client: AsyncClient, library: dict) -> None:
    """A valid enum value with no registered handler (audio) returns 404."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "x")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/audio", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_capability_dispatch_missing_item_404(client: AsyncClient, library: dict) -> None:
    """Capability dispatch on an unknown item is 404."""
    resp = await client.get(
        f"/libraries/{library['id']}/items/ghost/content/text", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_capability_unavailable_for_item_404(client: AsyncClient, library: dict) -> None:
    """Asking for pages on a text-only item → HandlerUnavailable → 404."""
    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "no pages here")

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text


async def test_capability_dispatch_item_dir_missing_404(
    client: AsyncClient, library: dict
) -> None:
    """When the on-disk item dir is gone but the DB row remains → 404."""
    import shutil  # noqa: PLC0415

    from services import content_service  # noqa: PLC0415

    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# gone on disk")
    base = content_service.get_item_base_path(library["organization_id"], lib_id, item_id)
    shutil.rmtree(base)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/text", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404, resp.text
    assert "missing on disk" in resp.json()["detail"].lower()


async def test_capability_handler_crash_500(client: AsyncClient, library: dict) -> None:
    """An unexpected handler exception is surfaced as a 500."""
    from plugins.content_handlers.capability import Capability, CapabilityRegistry  # noqa: PLC0415

    lib_id = library["id"]
    item_id = await _upload_simple(client, lib_id, "# crashy")

    # ``CapabilityRegistry.get`` returns a fresh instance per call, so patch
    # the handler class's ``get`` method (every instance shares it).
    handler_cls = CapabilityRegistry._handlers[Capability.TEXT]
    with mock.patch.object(handler_cls, "get", side_effect=RuntimeError("boom")):
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/content/text", headers=AUTH_HEADERS
        )
    assert resp.status_code == 500, resp.text
    assert "failed" in resp.json()["detail"].lower()
