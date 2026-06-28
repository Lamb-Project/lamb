"""E2E HTTP error-code matrix over the real socket.

One assertion per status code the service can return, each exercising the real
code path: 400, 401, 404, 409, 413, 422. Proves the service maps failures to
the documented codes rather than leaking 500s.
"""

from __future__ import annotations

import httpx
import pytest
from _helpers import library_payload, text_file

from ._server import ServerProcess

pytestmark = pytest.mark.slow


def test_401_no_auth(server) -> None:
    """No bearer token on a protected route → 401."""
    with httpx.Client(base_url=server.base_url, timeout=10.0) as c:
        resp = c.get("/plugins")
    assert resp.status_code == 401, resp.text


def test_404_missing_library(http: httpx.Client) -> None:
    """GET on a non-existent library → 404."""
    resp = http.get("/libraries/does-not-exist")
    assert resp.status_code == 404, resp.text


def test_404_missing_item(http: httpx.Client) -> None:
    """GET an item under a real library that has no such item → 404."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201
    resp = http.get(f"/libraries/{lib['id']}/items/no-such-item")
    assert resp.status_code == 404, resp.text


def test_409_duplicate_library_id(http: httpx.Client) -> None:
    """Creating a library whose id already exists → 409 conflict."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201
    # Same id, different name → primary-key conflict.
    dup = library_payload(id=lib["id"], name="Different Name")
    resp = http.post("/libraries", json=dup)
    assert resp.status_code == 409, resp.text


def test_422_invalid_query_param(http: httpx.Client) -> None:
    """limit=0 violates the ge=1 constraint → 422 validation error."""
    resp = http.get("/libraries", params={"organization_id": "org-x", "limit": 0})
    assert resp.status_code == 422, resp.text


def test_422_missing_required_body_field(http: httpx.Client) -> None:
    """POST /libraries without the required 'id' field → 422."""
    resp = http.post("/libraries", json={"organization_id": "org-x", "name": "No Id"})
    assert resp.status_code == 422, resp.text


def test_400_empty_file(http: httpx.Client) -> None:
    """Uploading a 0-byte file → 400 (empty file rejected before queueing)."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201
    files = {"file": ("empty.md", b"", "text/markdown")}
    resp = http.post(
        f"/libraries/{lib['id']}/import/file",
        files=files,
        data={"plugin_name": "simple_import", "title": "Empty"},
    )
    assert resp.status_code == 400, resp.text


def test_400_unknown_plugin(http: httpx.Client) -> None:
    """Importing with an unregistered plugin name → 400."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201
    resp = http.post(
        f"/libraries/{lib['id']}/import/file",
        files=text_file("# X\n\nbody", "x.md"),
        data={"plugin_name": "nonexistent_plugin", "title": "X"},
    )
    assert resp.status_code == 400, resp.text


def test_413_oversize_upload() -> None:
    """An upload above MAX_UPLOAD_SIZE_BYTES → 413 (dedicated 1 KB-cap server)."""
    server = ServerProcess(env={"MAX_UPLOAD_SIZE_BYTES": "1024"})
    server.start()
    try:
        with server.client() as c:
            lib = library_payload()
            assert c.post("/libraries", json=lib).status_code == 201
            big = b"x" * 4096  # 4 KB > 1 KB cap
            files = {"file": ("big.md", big, "text/markdown")}
            resp = c.post(
                f"/libraries/{lib['id']}/import/file",
                files=files,
                data={"plugin_name": "simple_import", "title": "Big"},
            )
        assert resp.status_code == 413, resp.text
    finally:
        server.stop()
