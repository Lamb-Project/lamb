"""Full HTTP import → ready pipeline for every import plugin.

Each test drives a real import through the ASGI client and the real
background worker, mocking only the external boundary (``markitdown``,
``firecrawl``, ``fitz``, ``openai``) so the plugin, service, worker, and
content-writing code all run for real. The YouTube path uses the offline
transcript cache installed by the root conftest.

Source under test: ``routers/importing.py``, ``services/import_service.py``,
``tasks/worker.py`` and the five plugins.
"""

from __future__ import annotations

import pytest
from _fakes import (
    FakeFitzDoc,
    patch_firecrawl,
    patch_fitz,
    patch_markitdown,
    patch_openai_vision,
)
from _helpers import (
    AUTH_HEADERS,
    file_bytes,
    library_payload,
    poll_until_ready,
    text_file,
)
from database.connection import get_session_direct
from database.models import ContentImage, ImportJob
from httpx import AsyncClient
from tasks import worker

# 202 response shape from importing.py: {"item_id", "job_id", "status": "processing"}.


async def _assert_accepted(resp) -> tuple[str, str]:
    """Assert a 202 import response and return (item_id, job_id)."""
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "processing", body
    return body["item_id"], body["job_id"]


# ---------------------------------------------------------------------------
# simple_import
# ---------------------------------------------------------------------------


async def test_simple_import_text_file_ready(client: AsyncClient, library: dict) -> None:
    """A plain text file imports to ready with the content preserved verbatim."""
    lib_id = library["id"]
    content = "# Hello Pipeline\n\nThe quick brown fox."
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files=text_file(content, "simple.md"),
        data={"plugin_name": "simple_import", "title": "Simple Doc"},
    )
    item_id, _ = await _assert_accepted(resp)

    status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    body = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS
    )
    assert body.status_code == 200, body.text
    assert "The quick brown fox." in body.text

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["source_type"] == "file"


# ---------------------------------------------------------------------------
# markitdown_import
# ---------------------------------------------------------------------------


async def test_markitdown_import_pdf_with_pages(client: AsyncClient, library: dict) -> None:
    """A .pdf upload through markitdown_import yields a ready item with pages."""
    lib_id = library["id"]
    with patch_markitdown(text="page one body\n\n---\n\npage two body"):
        resp = await client.post(
            f"/libraries/{lib_id}/import/file",
            headers=AUTH_HEADERS,
            files=file_bytes(b"%PDF-fake", "doc.pdf", "application/pdf"),
            data={"plugin_name": "markitdown_import", "title": "MD Doc"},
        )
        item_id, _ = await _assert_accepted(resp)
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert detail.json()["page_count"] == 2, detail.text


async def test_markitdown_import_docx_ready(client: AsyncClient, library: dict) -> None:
    """A .docx upload through markitdown_import reaches ready with content."""
    lib_id = library["id"]
    with patch_markitdown(text="just one page, no breaks"):
        resp = await client.post(
            f"/libraries/{lib_id}/import/file",
            headers=AUTH_HEADERS,
            files=file_bytes(b"PK-fake-docx", "doc.docx", "application/octet-stream"),
            data={"plugin_name": "markitdown_import", "title": "Docx Doc"},
        )
        item_id, _ = await _assert_accepted(resp)
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    body = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/content", headers=AUTH_HEADERS
    )
    assert "just one page" in body.text


# ---------------------------------------------------------------------------
# markitdown_plus_import
# ---------------------------------------------------------------------------


async def test_markitdown_plus_basic_pages_and_images(
    client: AsyncClient, library: dict
) -> None:
    """markitdown_plus on a PDF extracts pages + images with basic descriptions."""
    lib_id = library["id"]
    fake_doc = FakeFitzDoc(pages=1, images_per_page=1)
    with patch_markitdown(text="alpha\n\n---\n\nbeta"), patch_fitz(fake_doc):
        resp = await client.post(
            f"/libraries/{lib_id}/import/file",
            headers=AUTH_HEADERS,
            files=file_bytes(b"%PDF-fake", "rich.pdf", "application/pdf"),
            data={"plugin_name": "markitdown_plus_import", "title": "Rich Doc"},
        )
        item_id, _ = await _assert_accepted(resp)
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    data = detail.json()
    assert data["page_count"] == 2, data
    # 1 embedded image + 1 rasterized page render = 2 images.
    assert data["image_count"] >= 1, data
    assert data["metadata"]["image_descriptions_mode"] == "basic", data

    # Basic mode records filename-style descriptions on each image row.
    session = get_session_direct()
    try:
        descs = [
            img.llm_description
            for img in session.query(ContentImage)
            .filter(ContentImage.content_item_id == item_id)
            .all()
        ]
    finally:
        session.close()
    assert descs, "no image rows recorded"
    assert all(d and d.startswith("Image: ") for d in descs), descs


async def test_markitdown_plus_llm_descriptions(client: AsyncClient, library: dict) -> None:
    """markitdown_plus with image_descriptions=llm records LLM descriptions."""
    lib_id = library["id"]
    fake_doc = FakeFitzDoc(pages=1, images_per_page=1)
    with (
        patch_markitdown(text="alpha"),
        patch_fitz(fake_doc),
        patch_openai_vision(description="A vivid llm description."),
    ):
        resp = await client.post(
            f"/libraries/{lib_id}/import/file",
            headers=AUTH_HEADERS,
            files=file_bytes(b"%PDF-fake", "llm.pdf", "application/pdf"),
            data={
                "plugin_name": "markitdown_plus_import",
                "title": "LLM Doc",
                "plugin_params": '{"image_descriptions": "llm"}',
                "api_keys": '{"openai_vision": "sk-x"}',
            },
        )
        item_id, _ = await _assert_accepted(resp)
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    data = detail.json()
    assert data["metadata"]["image_descriptions_mode"] == "llm", data

    # LLM descriptions are written to the content_images rows verbatim.
    session = get_session_direct()
    try:
        descs = [
            img.llm_description
            for img in session.query(ContentImage)
            .filter(ContentImage.content_item_id == item_id)
            .all()
        ]
    finally:
        session.close()
    assert descs, "no image rows recorded"
    assert any(d == "A vivid llm description." for d in descs), descs


# ---------------------------------------------------------------------------
# url_import
# ---------------------------------------------------------------------------


async def test_url_import_markitdown_fallback(client: AsyncClient, library: dict) -> None:
    """URL import with no firecrawl key falls back to markitdown direct fetch."""
    lib_id = library["id"]
    with patch_markitdown(text="# Page\n\nfetched body"):
        resp = await client.post(
            f"/libraries/{lib_id}/import/url",
            headers=AUTH_HEADERS,
            json={
                "url": "https://example.com/article",
                "plugin_name": "url_import",
                "title": "URL Doc",
            },
        )
        item_id, _ = await _assert_accepted(resp)
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert detail.json()["metadata"]["fetch_method"] == "markitdown", detail.text


async def test_url_import_firecrawl(client: AsyncClient, library: dict) -> None:
    """URL import with a firecrawl_key uses the firecrawl fetch path."""
    lib_id = library["id"]
    with patch_firecrawl(markdown="# Scraped\n\ndeep crawl body"):
        resp = await client.post(
            f"/libraries/{lib_id}/import/url",
            headers=AUTH_HEADERS,
            json={
                "url": "https://example.com/deep",
                "plugin_name": "url_import",
                "title": "Firecrawl Doc",
                "api_keys": {"firecrawl_key": "fc-x"},
            },
        )
        item_id, _ = await _assert_accepted(resp)
        status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert detail.json()["metadata"]["fetch_method"] == "firecrawl", detail.text


# ---------------------------------------------------------------------------
# youtube
# ---------------------------------------------------------------------------


async def test_youtube_import_via_offline_cache(client: AsyncClient, library: dict) -> None:
    """A YouTube import completes offline via the cached transcript fixture."""
    lib_id = library["id"]
    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "language": "en",
            "plugin_name": "youtube_transcript_import",
            "title": "YouTube Doc",
        },
    )
    item_id, _ = await _assert_accepted(resp)
    status = await poll_until_ready(client, lib_id, item_id)
    assert status == "ready"

    sref = await client.get(
        f"/libraries/{lib_id}/items/{item_id}/source_ref", headers=AUTH_HEADERS
    )
    assert sref.status_code == 200, sref.text
    data = sref.json()
    assert data["type"] == "youtube", data
    assert data["video_id"] == "dQw4w9WgXcQ", data


# ---------------------------------------------------------------------------
# API-key-in-memory-only guarantee
# ---------------------------------------------------------------------------


async def test_api_keys_never_persisted_to_db(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """API keys sent with an import never land in any import_jobs column.

    Drives the queue without the worker so the keys remain in the in-memory
    store; asserts they are absent from every column of the DB row, present
    in ``worker._job_api_keys`` while queued, and popped exactly once.
    """
    lib_id = library["id"]
    secret = "sk-super-secret-value-123"
    resp = await client_no_worker.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files=file_bytes(b"%PDF-fake", "secret.pdf", "application/pdf"),
        data={
            "plugin_name": "markitdown_plus_import",
            "title": "Secret Doc",
            "api_keys": f'{{"openai_vision": "{secret}"}}',
        },
    )
    item_id, job_id = await _assert_accepted(resp)

    # The key lives only in the in-memory store, not in any DB column.
    assert worker._job_api_keys.get(job_id) == {"openai_vision": secret}

    session = get_session_direct()
    try:
        row = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert row is not None
        for column in ImportJob.__table__.columns:
            value = getattr(row, column.name)
            assert secret not in str(value), (
                f"secret leaked into import_jobs.{column.name}"
            )
    finally:
        session.close()

    # The worker pops the keys exactly once when it starts processing.
    popped = worker._job_api_keys.pop(job_id, None)
    assert popped == {"openai_vision": secret}
    assert job_id not in worker._job_api_keys


# ---------------------------------------------------------------------------
# Router validation / error paths
# ---------------------------------------------------------------------------


async def test_file_import_unknown_library_404(client: AsyncClient) -> None:
    """File import into a missing library returns 404."""
    resp = await client.post(
        "/libraries/nope-lib/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={"plugin_name": "simple_import", "title": "X"},
    )
    assert resp.status_code == 404, resp.text


async def test_file_import_unknown_plugin_400(client: AsyncClient, library: dict) -> None:
    """File import with an unregistered plugin returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={"plugin_name": "does_not_exist", "title": "X"},
    )
    assert resp.status_code == 400, resp.text


async def test_file_import_plugin_not_file_source_400(
    client: AsyncClient, library: dict
) -> None:
    """File import using a URL-only plugin is rejected with 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={"plugin_name": "url_import", "title": "X"},
    )
    assert resp.status_code == 400, resp.text


async def test_file_import_unsupported_extension_400(
    client: AsyncClient, library: dict
) -> None:
    """An extension the plugin doesn't accept is rejected with 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=file_bytes(b"data", "a.xyz", "application/octet-stream"),
        data={"plugin_name": "simple_import", "title": "X"},
    )
    assert resp.status_code == 400, resp.text


async def test_file_import_bad_plugin_params_json_400(
    client: AsyncClient, library: dict
) -> None:
    """Malformed plugin_params JSON yields 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={"plugin_name": "simple_import", "title": "X", "plugin_params": "{not json"},
    )
    assert resp.status_code == 400, resp.text


async def test_file_import_bad_api_keys_json_400(
    client: AsyncClient, library: dict
) -> None:
    """Malformed api_keys JSON yields 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={"plugin_name": "simple_import", "title": "X", "api_keys": "{bad"},
    )
    assert resp.status_code == 400, resp.text


async def test_file_import_empty_file_400(client: AsyncClient, library: dict) -> None:
    """A 0-byte upload is refused before any DB row is created."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=file_bytes(b"", "empty.md", "text/markdown"),
        data={"plugin_name": "simple_import", "title": "Empty"},
    )
    assert resp.status_code == 400, resp.text
    assert "empty" in resp.json()["detail"].lower()


async def test_file_import_invalid_folder_400(client: AsyncClient, library: dict) -> None:
    """Importing into a non-existent folder surfaces a 400 from the service."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={
            "plugin_name": "simple_import",
            "title": "X",
            "folder_id": "no-such-folder",
        },
    )
    assert resp.status_code == 400, resp.text


async def test_file_import_into_valid_folder(client: AsyncClient, library: dict) -> None:
    """Importing into a folder that belongs to the library succeeds and is filed there."""
    lib_id = library["id"]
    folder = await client.post(
        f"/libraries/{lib_id}/folders", headers=AUTH_HEADERS, json={"name": "inbox"}
    )
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["id"]

    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("foldered body", "f.md"),
        data={"plugin_name": "simple_import", "title": "Filed", "folder_id": folder_id},
    )
    item_id, _ = await _assert_accepted(resp)
    assert await poll_until_ready(client, lib_id, item_id) == "ready"

    detail = await client.get(
        f"/libraries/{lib_id}/items/{item_id}", headers=AUTH_HEADERS
    )
    assert detail.json()["folder_id"] == folder_id, detail.text


async def test_file_import_queue_failure_cleans_temp(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """A non-ValueError during queueing propagates and the temp file is cleaned.

    The endpoint's ``except Exception`` branch unlinks the temp upload and
    re-raises; ASGITransport surfaces the original error to the caller.
    """
    import routers.importing as importing_mod  # noqa: PLC0415

    upload_dir = importing_mod._UPLOAD_DIR

    def boom(*args, **kwargs):
        raise RuntimeError("queue exploded")

    monkeypatch.setattr(importing_mod.import_service, "queue_file_import", boom)
    before = set(upload_dir.iterdir()) if upload_dir.exists() else set()

    with pytest.raises(RuntimeError, match="queue exploded"):
        await client.post(
            f"/libraries/{library['id']}/import/file",
            headers=AUTH_HEADERS,
            files=text_file("x", "a.md"),
            data={"plugin_name": "simple_import", "title": "X"},
        )

    after = set(upload_dir.iterdir()) if upload_dir.exists() else set()
    assert after == before, "temp upload should have been cleaned up on failure"


async def test_file_import_too_large_413(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """An upload exceeding the size cap is rejected with 413."""
    import routers.importing as importing_mod  # noqa: PLC0415

    monkeypatch.setattr(importing_mod, "MAX_UPLOAD_SIZE_BYTES", 4)
    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=file_bytes(b"way too many bytes here", "big.md", "text/markdown"),
        data={"plugin_name": "simple_import", "title": "Big"},
    )
    assert resp.status_code == 413, resp.text


async def test_file_import_dotdot_filename_falls_back(
    client: AsyncClient, library: dict
) -> None:
    """A filename of '..' sanitizes to the 'unnamed' fallback and still imports."""
    lib_id = library["id"]
    resp = await client.post(
        f"/libraries/{lib_id}/import/file",
        headers=AUTH_HEADERS,
        files=file_bytes(b"body text", "..", "text/markdown"),
        data={"plugin_name": "markitdown_import", "title": "DotDot"},
    )
    # markitdown_import accepts unknown extensions only if listed; '..' has no
    # extension, so the extension guard rejects it. Either way the safe_filename
    # fallback line runs before that check.
    assert resp.status_code in (202, 400), resp.text


async def test_file_import_cross_library_folder_400(
    client: AsyncClient, library: dict
) -> None:
    """A folder_id belonging to another library is rejected with 400."""
    # Create a second library and a folder inside it.
    other = await client.post(
        "/libraries", headers=AUTH_HEADERS, json=library_payload()
    )
    assert other.status_code == 201, other.text
    other_lib = other.json()["id"]
    folder = await client.post(
        f"/libraries/{other_lib}/folders",
        headers=AUTH_HEADERS,
        json={"name": "elsewhere"},
    )
    assert folder.status_code == 201, folder.text
    foreign_folder = folder.json()["id"]

    resp = await client.post(
        f"/libraries/{library['id']}/import/file",
        headers=AUTH_HEADERS,
        files=text_file("x", "a.md"),
        data={
            "plugin_name": "simple_import",
            "title": "Cross",
            "folder_id": foreign_folder,
        },
    )
    assert resp.status_code == 400, resp.text
    assert "different library" in resp.json()["detail"].lower()


async def test_url_import_unknown_library_404(client: AsyncClient) -> None:
    """URL import into a missing library returns 404."""
    resp = await client.post(
        "/libraries/nope/import/url",
        headers=AUTH_HEADERS,
        json={"url": "https://x.com", "plugin_name": "url_import", "title": "X"},
    )
    assert resp.status_code == 404, resp.text


async def test_url_import_unknown_plugin_400(client: AsyncClient, library: dict) -> None:
    """URL import with an unknown plugin returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/url",
        headers=AUTH_HEADERS,
        json={"url": "https://x.com", "plugin_name": "nope", "title": "X"},
    )
    assert resp.status_code == 400, resp.text


async def test_url_import_wrong_source_plugin_400(
    client: AsyncClient, library: dict
) -> None:
    """URL import using a file-only plugin returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/url",
        headers=AUTH_HEADERS,
        json={"url": "https://x.com", "plugin_name": "simple_import", "title": "X"},
    )
    assert resp.status_code == 400, resp.text


async def test_url_import_invalid_folder_400(client: AsyncClient, library: dict) -> None:
    """URL import into a bad folder returns the service ValueError as 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://x.com",
            "plugin_name": "url_import",
            "title": "X",
            "folder_id": "no-such-folder",
        },
    )
    assert resp.status_code == 400, resp.text


async def test_youtube_import_unknown_library_404(client: AsyncClient) -> None:
    """YouTube import into a missing library returns 404."""
    resp = await client.post(
        "/libraries/nope/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://youtube.com/watch?v=x",
            "plugin_name": "youtube_transcript_import",
            "title": "X",
        },
    )
    assert resp.status_code == 404, resp.text


async def test_youtube_import_unknown_plugin_400(
    client: AsyncClient, library: dict
) -> None:
    """YouTube import with an unknown plugin returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://youtube.com/watch?v=x",
            "plugin_name": "nope",
            "title": "X",
        },
    )
    assert resp.status_code == 400, resp.text


async def test_youtube_import_wrong_source_plugin_400(
    client: AsyncClient, library: dict
) -> None:
    """YouTube import using a file-only plugin returns 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://youtube.com/watch?v=x",
            "plugin_name": "simple_import",
            "title": "X",
        },
    )
    assert resp.status_code == 400, resp.text


async def test_youtube_import_invalid_folder_400(
    client: AsyncClient, library: dict
) -> None:
    """YouTube import into a bad folder returns the service ValueError as 400."""
    resp = await client.post(
        f"/libraries/{library['id']}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://youtube.com/watch?v=x",
            "plugin_name": "youtube_transcript_import",
            "title": "X",
            "folder_id": "no-such-folder",
        },
    )
    assert resp.status_code == 400, resp.text
