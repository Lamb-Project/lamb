"""Capabilities-router dispatch branches: JSON payload, raw image serve,
missing-content 404, handler-exception 500, plus the importing-router
ValueError→400 paths (invalid folder_id)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from .conftest import AUTH_HEADERS


async def _mk_library(client: AsyncClient) -> str:
    lib_id = f"lib-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/libraries", headers=AUTH_HEADERS,
        json={"id": lib_id, "organization_id": "org-cap", "name": f"Cap {lib_id[-6:]}"},
    )
    assert resp.status_code == 201
    return lib_id


def _seed_item_with_content(lib_id: str, *, with_content: bool) -> str:
    """Insert a ContentItem row; optionally write a full structured layout
    (text + a page + an image) to disk."""
    from database.connection import get_session_direct
    from database.models import ContentItem
    from services import content_service as cs

    item_id = uuid.uuid4().hex
    org_id = "org-cap"
    base = cs.get_item_base_path(org_id, lib_id, item_id)
    if with_content:
        from plugins.base import ExtractedImage, PageContent

        cs.write_structured_content(
            item_id=item_id, library_id=lib_id, organization_id=org_id,
            title="Doc", full_text="# Full\n\nbody",
            pages=[PageContent(page_number=1, text="p1")],
            images=[ExtractedImage(filename="img_001.png", data=b"PNGBYTES")],
            item_metadata={}, source_ref={"type": "file"},
        )

    session = get_session_direct()
    try:
        session.add(ContentItem(
            id=item_id, library_id=lib_id, organization_id=org_id, title="Doc",
            source_type="file", base_path=str(base),
            permalink_base=f"/library/{org_id}/{lib_id}/{item_id}",
            import_plugin="simple_import", status="ready",
        ))
        session.commit()
    finally:
        session.close()
    return item_id


@pytest.mark.asyncio
async def test_capability_content_json_payload(client: AsyncClient):
    lib = await _mk_library(client)
    item = _seed_item_with_content(lib, with_content=True)
    # images handler returns application/json -> JSONResponse branch.
    resp = await client.get(
        f"/libraries/{lib}/items/{item}/content/images", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_image_raw_file_served(client: AsyncClient):
    lib = await _mk_library(client)
    item = _seed_item_with_content(lib, with_content=True)
    resp = await client.get(
        f"/libraries/{lib}/items/{item}/content/images/file/img_001.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.content == b"PNGBYTES"


@pytest.mark.asyncio
async def test_capability_content_missing_on_disk_404(client: AsyncClient):
    lib = await _mk_library(client)
    item = _seed_item_with_content(lib, with_content=False)  # row but no disk
    resp = await client.get(
        f"/libraries/{lib}/items/{item}/content/text", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_capability_handler_exception_500(client: AsyncClient, monkeypatch):
    lib = await _mk_library(client)
    item = _seed_item_with_content(lib, with_content=True)

    import plugins.content_handlers.capability as capmod

    class _BoomHandler:
        def get(self, item_path):
            raise RuntimeError("handler kaboom")

    monkeypatch.setattr(
        capmod.CapabilityRegistry, "get", classmethod(lambda cls, c: _BoomHandler())
    )
    resp = await client.get(
        f"/libraries/{lib}/items/{item}/content/text", headers=AUTH_HEADERS
    )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# importing router: ValueError -> 400 (invalid folder_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_url_bad_folder_400(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.post(
        f"/libraries/{lib}/import/url", headers=AUTH_HEADERS,
        json={"url": "https://example.com", "title": "T", "folder_id": "missing-folder"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_youtube_bad_folder_400(client: AsyncClient):
    lib = await _mk_library(client)
    resp = await client.post(
        f"/libraries/{lib}/import/youtube", headers=AUTH_HEADERS,
        json={"video_url": "https://youtu.be/abc12345678", "title": "T", "folder_id": "missing-folder"},
    )
    assert resp.status_code == 400
