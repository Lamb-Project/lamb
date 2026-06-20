"""Error/dispatch branch tests for ``routers.capabilities``.

Complements ``test_capabilities.py`` (registry + handler unit tests) by
exercising the HTTP router branches: 404s for missing items / unknown
capabilities, the capability-content dispatch for a real item, and the
HandlerUnavailable path.
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


async def _upload_md(client, lib_id, content="# Hi\n\nbody", title="Doc"):
    import asyncio
    import time

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("t.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": title},
    )
    item_id = resp.json()["item_id"]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        st = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS
        )
        if st.json()["status"] in ("ready", "failed"):
            break
        await asyncio.sleep(0.3)
    return item_id


# ---------------------------------------------------------------------------
# 404 branches (no real item needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_item_capabilities_not_found(client: AsyncClient, library):
    lib_id = library["id"]
    resp = await client.get(
        f"/libraries/{lib_id}/items/does-not-exist/capabilities",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_capability_content_unknown_capability(client: AsyncClient, library):
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id)
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/bogus-capability",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404
    assert "Unknown capability" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_capability_content_item_not_found(client: AsyncClient, library):
    lib_id = library["id"]
    resp = await client.get(
        f"/libraries/{lib_id}/items/missing/content/text",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_image_raw_item_not_found(client: AsyncClient, library):
    lib_id = library["id"]
    resp = await client.get(
        f"/libraries/{lib_id}/items/missing/content/images/file/x.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# real-item dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_item_capabilities_lists_text(client: AsyncClient, library):
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id)
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/capabilities", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert "text" in resp.json()["capabilities"]


@pytest.mark.asyncio
async def test_capability_content_text_dispatch(client: AsyncClient, library):
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id, content="# Title\n\nHello world")
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/text", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert "Hello world" in resp.text


@pytest.mark.asyncio
async def test_capability_content_pages_unavailable(client: AsyncClient, library):
    # A simple_import .md item has no per-page split -> pages handler reports
    # the capability as unavailable -> 404.
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id)
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_image_raw_image_not_found(client: AsyncClient, library):
    lib_id = library["id"]
    item_id = await _upload_md(client, lib_id)
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/file/missing.png",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404
