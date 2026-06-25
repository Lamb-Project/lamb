"""E2E real local imports end-to-end over HTTP.

Drives the only network-free plugins — ``simple_import`` (.txt/.md) and
``markitdown_import`` on a local .html file — through the real subprocess and
its real background worker. No mocking. Asserts each item reaches 'ready',
serves its converted content, and exposes metadata + source_ref.
"""

from __future__ import annotations

import httpx
import pytest
from _helpers import file_bytes, library_payload, poll_until_ready_sync, text_file

pytestmark = pytest.mark.slow


def _import_to_ready(
    http: httpx.Client, lib_id: str, *, files: dict, plugin: str, title: str
) -> str:
    """Queue a file import, poll to a terminal state, and return the item_id."""
    resp = http.post(
        f"/libraries/{lib_id}/import/file",
        files=files,
        data={"plugin_name": plugin, "title": title},
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    status = poll_until_ready_sync(http, lib_id, item_id, timeout=40)
    assert status == "ready", f"expected ready, got {status}"
    return item_id


def test_simple_import_txt(http: httpx.Client) -> None:
    """simple_import of a .txt file reaches 'ready' and serves the verbatim text."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201

    content = "Plain text body. Lorem ipsum dolor sit amet."
    files = {"file": ("notes.txt", content.encode("utf-8"), "text/plain")}
    item_id = _import_to_ready(
        http, lib["id"], files=files, plugin="simple_import", title="Notes"
    )

    got = http.get(f"/libraries/{lib['id']}/items/{item_id}/content")
    assert got.status_code == 200, got.text
    assert "Lorem ipsum" in got.text


def test_simple_import_md(http: httpx.Client) -> None:
    """simple_import of a .md file reaches 'ready' and serves the markdown."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201

    content = "# Heading\n\nA markdown paragraph with **bold** text."
    item_id = _import_to_ready(
        http,
        lib["id"],
        files=text_file(content, "doc.md"),
        plugin="simple_import",
        title="Markdown Doc",
    )

    got = http.get(f"/libraries/{lib['id']}/items/{item_id}/content")
    assert got.status_code == 200, got.text
    assert "markdown paragraph" in got.text


def test_markitdown_import_html(http: httpx.Client) -> None:
    """markitdown_import converts a local .html file to markdown → 'ready'."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201

    html = (
        "<html><head><title>Report</title></head><body>"
        "<h1>Quarterly Report</h1>"
        "<p>Revenue grew by forty two percent this quarter.</p>"
        "</body></html>"
    )
    item_id = _import_to_ready(
        http,
        lib["id"],
        files=file_bytes(html.encode("utf-8"), "report.html", "text/html"),
        plugin="markitdown_import",
        title="HTML Report",
    )

    got = http.get(f"/libraries/{lib['id']}/items/{item_id}/content")
    assert got.status_code == 200, got.text
    assert "forty two percent" in got.text


def test_metadata_and_source_ref_endpoints(http: httpx.Client) -> None:
    """A ready item exposes its metadata.json and source_ref.json over HTTP."""
    lib = library_payload()
    assert http.post("/libraries", json=lib).status_code == 201

    item_id = _import_to_ready(
        http,
        lib["id"],
        files=text_file("# Meta\n\nbody", "meta.md"),
        plugin="simple_import",
        title="Meta Doc",
    )

    meta = http.get(f"/libraries/{lib['id']}/items/{item_id}/metadata")
    assert meta.status_code == 200, meta.text
    assert isinstance(meta.json(), dict)

    src = http.get(f"/libraries/{lib['id']}/items/{item_id}/source_ref")
    assert src.status_code == 200, src.text
    assert isinstance(src.json(), dict)
