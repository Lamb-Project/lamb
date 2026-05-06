"""End-to-end tests for each import plugin.

Each test:
1. Creates a library
2. Uploads/imports content using the specific plugin
3. Polls until status is "ready" (or "failed")
4. Verifies markdown content is available
5. Verifies metadata.json has correct structure and permalinks
6. Verifies source_ref.json is correct
7. Verifies original file is served (for file-based plugins)

Plugins that require external services (url_import → Firecrawl) test the
error path instead, since the external service is not available in CI.
"""

import asyncio
import io
import time

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}

# Maximum time (seconds) to wait for an import job to complete.
_POLL_TIMEOUT = 20
_POLL_INTERVAL = 0.5


async def _wait_for_ready(
    client: AsyncClient,
    lib_id: str,
    item_id: str,
    timeout: float = _POLL_TIMEOUT,
) -> str:
    """Poll item status until it leaves 'pending'/'processing'.

    Args:
        client: HTTP client.
        lib_id: Library ID.
        item_id: Content item ID.
        timeout: Max seconds to wait.

    Returns:
        Final status string ('ready' or 'failed').
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status",
            headers=AUTH_HEADERS,
        )
        status = resp.json()["status"]
        if status in ("ready", "failed"):
            return status
        await asyncio.sleep(_POLL_INTERVAL)
    return "timeout"


# -----------------------------------------------------------------------
# Plugin 1: simple_import — plain text/markdown/html
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simple_import_markdown(client: AsyncClient, library: dict):
    """simple_import should import a .md file and serve it back as markdown."""
    lib_id = library["id"]
    content = (
        "# Biology Notes\n\n"
        "## Cell Structure\n\n"
        "The cell is the basic unit of life.\n\n"
        "- Nucleus\n"
        "- Mitochondria\n"
        "- Cell membrane\n"
    )

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("biology.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Biology Notes"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready", f"Expected ready, got {status}"

    # Verify markdown content.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
        params={"format": "markdown"},
    )
    assert resp.status_code == 200
    assert "# Biology Notes" in resp.text
    assert "Cell membrane" in resp.text

    # Verify HTML rendering.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
        params={"format": "html"},
    )
    assert resp.status_code == 200
    assert "<h1" in resp.text

    # Verify metadata.json.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/metadata",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["item_id"] == item_id
    assert meta["permalinks"]["full_markdown"].endswith("/content/full.md")
    assert meta["permalinks"]["original"] is not None

    # Verify source_ref.json.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/source_ref",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    src = resp.json()
    assert src["type"] == "file"
    assert src["original_filename"] == "biology.md"

    # Verify original file.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/original/biology.md",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "Biology Notes" in resp.text


@pytest.mark.asyncio
async def test_simple_import_html(client: AsyncClient, library: dict):
    """simple_import should import a .html file."""
    lib_id = library["id"]
    content = (
        "<html><body>"
        "<h1>HTML Test</h1>"
        "<p>Paragraph with <strong>bold</strong> text.</p>"
        "</body></html>"
    )

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("test.html", io.BytesIO(content.encode()), "text/html")},
        data={"plugin_name": "simple_import", "title": "HTML Test"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready"

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
        params={"format": "markdown"},
    )
    assert resp.status_code == 200
    assert "HTML Test" in resp.text


@pytest.mark.asyncio
async def test_simple_import_txt(client: AsyncClient, library: dict):
    """simple_import should import a .txt file."""
    lib_id = library["id"]
    content = "This is a plain text file.\nLine two.\nLine three."

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("notes.txt", io.BytesIO(content.encode()), "text/plain")},
        data={"plugin_name": "simple_import", "title": "Plain Text"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready"

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "plain text file" in resp.text


# -----------------------------------------------------------------------
# Plugin 2: markitdown_import — MarkItDown conversion
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_markitdown_import(client: AsyncClient, library: dict):
    """markitdown_import should convert a markdown file via MarkItDown."""
    lib_id = library["id"]
    content = (
        "# MarkItDown Test\n\n"
        "| Column A | Column B |\n"
        "|----------|----------|\n"
        "| Cell 1   | Cell 2   |\n"
        "| Cell 3   | Cell 4   |\n"
    )

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("table.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "markitdown_import", "title": "MarkItDown Table Test"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready"

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    text = resp.text
    assert "MarkItDown Test" in text or "Column A" in text

    # Verify item detail.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["import_plugin"] == "markitdown_import"
    assert detail["status"] == "ready"
    assert detail["metadata"]["permalinks"]["full_markdown"] is not None


# -----------------------------------------------------------------------
# Plugin 3: markitdown_plus_import — enhanced with image/page awareness
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_markitdown_plus_import(client: AsyncClient, library: dict):
    """markitdown_plus_import should convert with enhanced features."""
    lib_id = library["id"]
    content = (
        "<html><body>"
        "<h1>Enhanced Import</h1>"
        "<h2>Section 1</h2>"
        "<p>First section content.</p>"
        "<h2>Section 2</h2>"
        "<p>Second section content with a <em>formula</em>.</p>"
        "</body></html>"
    )

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("enhanced.html", io.BytesIO(content.encode()), "text/html")},
        data={
            "plugin_name": "markitdown_plus_import",
            "title": "Enhanced Import Test",
            "plugin_params": '{"image_descriptions": "none"}',
        },
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready"

    # Verify markdown.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "Enhanced Import" in resp.text or "Section 1" in resp.text

    # Verify metadata.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/metadata",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["import_plugin"] == "markitdown_plus_import"
    assert "permalinks" in meta

    # Verify pages and images endpoints exist (may be empty for HTML).
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "count" in resp.json()

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert "count" in resp.json()


# -----------------------------------------------------------------------
# Plugin 4: url_import — Firecrawl (tests error path without service)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_url_import_no_firecrawl(client: AsyncClient, library: dict):
    """url_import should fail gracefully when Firecrawl is unavailable."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "title": "Example.com",
            "plugin_name": "url_import",
            "api_keys": {"firecrawl_key": "dummy", "firecrawl_url": "http://localhost:3002"},
        },
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id, timeout=15)
    assert status == "failed", "Expected failure without Firecrawl service"

    # Verify error is recorded.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/status",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["error_message"] is not None


@pytest.mark.asyncio
async def test_url_import_source_type_validation(client: AsyncClient, library: dict):
    """Attempting to use a file plugin for URL import should fail."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "title": "Bad Plugin",
            "plugin_name": "simple_import",
        },
    )
    assert resp.status_code == 400


# -----------------------------------------------------------------------
# Plugin 5: youtube_transcript_import
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_youtube_import(client: AsyncClient, library: dict):
    """youtube_transcript_import should download and convert a transcript.

    Uses a well-known video with reliable subtitles.
    """
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "language": "en",
            "title": "Never Gonna Give You Up",
            "plugin_name": "youtube_transcript_import",
        },
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    # YouTube downloads can take time — allow up to 30s.
    status = await _wait_for_ready(client, lib_id, item_id, timeout=30)

    if status == "failed":
        # YouTube may rate-limit in CI — check that error was recorded properly.
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status",
            headers=AUTH_HEADERS,
        )
        error = resp.json().get("error_message", "")
        pytest.skip(f"YouTube import failed (likely rate-limited): {error[:100]}")

    assert status == "ready"

    # Verify markdown content exists.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    text = resp.text

    # YouTube may rate-limit subtitle requests — if no transcript was
    # obtained, the plugin returns a placeholder. Both cases are valid.
    if "No transcript available" in text:
        pytest.skip("YouTube subtitles unavailable (likely rate-limited)")

    assert "Transcript" in text or "**[" in text  # Timestamped entries

    # Verify source_ref.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/source_ref",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    src = resp.json()
    assert src["type"] == "youtube"
    assert src["video_id"] == "dQw4w9WgXcQ"

    # Verify metadata.
    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/metadata",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["import_plugin"] == "youtube_transcript_import"


@pytest.mark.asyncio
async def test_youtube_source_type_validation(client: AsyncClient, library: dict):
    """Attempting to use a file plugin for YouTube import should fail."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "language": "en",
            "title": "Bad Plugin",
            "plugin_name": "simple_import",
        },
    )
    assert resp.status_code == 400
