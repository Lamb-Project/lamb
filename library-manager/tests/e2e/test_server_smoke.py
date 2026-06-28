"""E2E smoke: the real uvicorn process boots, serves, and imports a file.

Drives the shared ``server`` subprocess over real loopback HTTP — no mocking.
Proves the process actually answers, lists its plugins, rejects anonymous
callers, and completes one real ``simple_import`` end-to-end.
"""

from __future__ import annotations

import httpx
import pytest
from _helpers import library_payload, poll_until_ready_sync, text_file

pytestmark = pytest.mark.slow

# The five import plugins the service registers at startup.
_EXPECTED_PLUGINS = {
    "simple_import",
    "markitdown_import",
    "markitdown_plus_import",
    "url_import",
    "youtube_transcript_import",
}


def test_health_ok(http: httpx.Client) -> None:
    """GET /health returns 200 with status 'ok' (db + worker both up)."""
    resp = http.get("/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok", body
    assert body["service"] == "library-manager", body


def test_plugins_lists_all_five(http: httpx.Client) -> None:
    """GET /plugins lists the five registered import plugins."""
    resp = http.get("/plugins")
    assert resp.status_code == 200, resp.text
    names = {p["name"] for p in resp.json()["plugins"]}
    assert names >= _EXPECTED_PLUGINS, names


def test_protected_route_rejects_anonymous(server) -> None:
    """A request to a protected route with no auth is rejected with 401."""
    with httpx.Client(base_url=server.base_url, timeout=10.0) as anon:
        resp = anon.get("/plugins")
    assert resp.status_code == 401, resp.text


def test_real_simple_import_roundtrip(http: httpx.Client) -> None:
    """A real simple_import of a .md file reaches 'ready' and serves its text."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201

    content = "# Smoke Test\n\nThe quick brown fox jumps over the lazy dog."
    resp = http.post(
        f"/libraries/{lib['id']}/import/file",
        files=text_file(content, "smoke.md"),
        data={"plugin_name": "simple_import", "title": "Smoke Doc"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "processing", body
    item_id = body["item_id"]

    status = poll_until_ready_sync(http, lib["id"], item_id, timeout=30)
    assert status == "ready", status

    got = http.get(f"/libraries/{lib['id']}/items/{item_id}/content")
    assert got.status_code == 200, got.text
    assert "quick brown fox" in got.text
