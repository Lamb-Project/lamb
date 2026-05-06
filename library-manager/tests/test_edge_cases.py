"""Tests for edge cases, error paths, and coverage gaps.

Covers: upload size limits, Unicode filenames, path traversal attempts,
empty files, malformed JSON params, stale job recovery, and source type
validation.
"""

import asyncio
import io
import time

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}
_POLL_TIMEOUT = 15


async def _wait_for_ready(client, lib_id, item_id, timeout=_POLL_TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS
        )
        if resp.json()["status"] in ("ready", "failed"):
            return resp.json()["status"]
        await asyncio.sleep(0.5)
    return "timeout"


# -----------------------------------------------------------------------
# Upload size limits
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_exceeds_size_limit(client: AsyncClient, library: dict):
    """Uploading a file larger than MAX_UPLOAD_SIZE_BYTES should return 413."""
    import routers.importing as importing_mod  # noqa: PLC0415

    original = importing_mod.MAX_UPLOAD_SIZE_BYTES
    importing_mod.MAX_UPLOAD_SIZE_BYTES = 100  # 100 bytes

    try:
        content = "x" * 200  # 200 bytes > 100 limit
        resp = await client.post(
            f"/libraries/{library['id']}/import/file",
            headers=AUTH_HEADERS,
            files={"file": ("big.md", io.BytesIO(content.encode()), "text/markdown")},
            data={"plugin_name": "simple_import", "title": "Too Big"},
        )
        assert resp.status_code == 413
    finally:
        importing_mod.MAX_UPLOAD_SIZE_BYTES = original


# -----------------------------------------------------------------------
# Unicode filenames
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unicode_filename(client: AsyncClient, library: dict):
    """Files with Unicode names should be imported successfully."""
    lib_id = library["id"]
    content = "# Documento académico\n\nContenido en español con acentos: é è ê ë."

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("documento_académico.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Documento Académico"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready"

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS
    )
    assert "académico" in resp.text


@pytest.mark.asyncio
async def test_filename_with_spaces(client: AsyncClient, library: dict):
    """Files with spaces in names should be imported successfully."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("my document file.md", io.BytesIO(b"# Spaced"), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Spaced Filename"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    assert status == "ready"


# -----------------------------------------------------------------------
# Path traversal attempts
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_path_traversal_in_page_name(client: AsyncClient, library: dict):
    """Requesting a page with ../ should not escape the content directory."""
    lib_id = library["id"]
    content = "# Safe Content"

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("safe.md", io.BytesIO(content.encode()), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Safe"},
    )
    item_id = resp.json()["item_id"]
    await _wait_for_ready(client, lib_id, item_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/pages/../../metadata.json",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_path_traversal_in_image_name(client: AsyncClient, library: dict):
    """Requesting an image with ../ should not escape the content directory."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("safe.md", io.BytesIO(b"# Content"), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Safe"},
    )
    item_id = resp.json()["item_id"]
    await _wait_for_ready(client, lib_id, item_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content/images/../../../metadata.json",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_path_traversal_in_original_name(client: AsyncClient, library: dict):
    """Requesting an original file with ../ should not escape."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("safe.md", io.BytesIO(b"# Content"), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Safe"},
    )
    item_id = resp.json()["item_id"]
    await _wait_for_ready(client, lib_id, item_id)

    resp = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/original/../../metadata.json",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# -----------------------------------------------------------------------
# Empty file
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_file_import(client: AsyncClient, library: dict):
    """An empty file should be imported (plugin handles empty content)."""
    lib_id = library["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("empty.md", io.BytesIO(b""), "text/markdown")},
        data={"plugin_name": "simple_import", "title": "Empty Doc"},
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    status = await _wait_for_ready(client, lib_id, item_id)
    # May be "ready" (empty content stored) or "failed" (plugin rejects empty).
    assert status in ("ready", "failed")


# -----------------------------------------------------------------------
# Malformed JSON in form fields
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_plugin_params_json(client: AsyncClient, library: dict):
    """Invalid JSON in plugin_params should return 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("test.md", io.BytesIO(b"# Test"), "text/markdown")},
        data={
            "plugin_name": "simple_import",
            "title": "Test",
            "plugin_params": "{not valid json",
        },
    )
    assert resp.status_code == 400
    assert "plugin_params" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_malformed_api_keys_json(client: AsyncClient, library: dict):
    """Invalid JSON in api_keys should return 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("test.md", io.BytesIO(b"# Test"), "text/markdown")},
        data={
            "plugin_name": "simple_import",
            "title": "Test",
            "api_keys": "not json",
        },
    )
    assert resp.status_code == 400
    assert "api_keys" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------
# Source type validation (cross-plugin)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_plugin_rejects_url_import(client: AsyncClient, library: dict):
    """A file-only plugin should not accept URL imports."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "title": "Bad",
            "plugin_name": "markitdown_import",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_url_plugin_rejects_file_upload(client: AsyncClient, library: dict):
    """A URL-only plugin should not accept file uploads."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("test.md", io.BytesIO(b"# Test"), "text/markdown")},
        data={"plugin_name": "url_import", "title": "Bad"},
    )
    assert resp.status_code == 400


# -----------------------------------------------------------------------
# Stale job recovery
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_job_recovery(client: AsyncClient, library: dict):
    """Jobs stuck in 'processing' should be recovered on startup.

    Simulates a crash by directly writing a 'processing' job to the DB,
    then calling recover_stale_jobs and verifying it resets to 'pending'.
    """
    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import ImportJob  # noqa: PLC0415
    from tasks.worker import recover_stale_jobs  # noqa: PLC0415

    db = get_session_direct()
    try:
        stale_job = ImportJob(
            id="stale-job-001",
            content_item_id="fake-item",
            library_id=library["id"],
            organization_id="org-test",
            source_type="file",
            plugin_name="simple_import",
            title="Stale Job",
            status="processing",
            attempts=1,
        )
        db.add(stale_job)
        db.commit()

        recover_stale_jobs()

        db.expire_all()
        refreshed = db.query(ImportJob).filter(ImportJob.id == "stale-job-001").first()
        assert refreshed is not None
        assert refreshed.status == "pending"
    finally:
        db.query(ImportJob).filter(ImportJob.id == "stale-job-001").delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_stale_job_exceeds_max_attempts(client: AsyncClient, library: dict):
    """Jobs exceeding max attempts should be marked failed, not retried."""
    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import ImportJob  # noqa: PLC0415
    from tasks.worker import recover_stale_jobs  # noqa: PLC0415

    db = get_session_direct()
    try:
        stale_job = ImportJob(
            id="stale-job-002",
            content_item_id="fake-item",
            library_id=library["id"],
            organization_id="org-test",
            source_type="file",
            plugin_name="simple_import",
            title="Stale Exhausted Job",
            status="processing",
            attempts=5,
        )
        db.add(stale_job)
        db.commit()

        recover_stale_jobs()

        db.expire_all()
        refreshed = db.query(ImportJob).filter(ImportJob.id == "stale-job-002").first()
        assert refreshed is not None
        assert refreshed.status == "failed"
        assert "max attempts" in refreshed.error_message.lower()
    finally:
        db.query(ImportJob).filter(ImportJob.id == "stale-job-002").delete()
        db.commit()
        db.close()


# -----------------------------------------------------------------------
# Nonexistent plugin
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_plugin(client: AsyncClient, library: dict):
    """Using a plugin name that doesn't exist should return 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("test.md", io.BytesIO(b"# Test"), "text/markdown")},
        data={"plugin_name": "nonexistent_plugin", "title": "Bad"},
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------
# Wrong file extension for plugin
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrong_extension_for_plugin(client: AsyncClient, library: dict):
    """Uploading a .pdf to simple_import (which only supports txt/md/html) should fail."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files={"file": ("fake.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
        data={"plugin_name": "simple_import", "title": "Wrong Extension"},
    )
    assert resp.status_code == 400
    assert "does not support" in resp.json()["detail"].lower()
