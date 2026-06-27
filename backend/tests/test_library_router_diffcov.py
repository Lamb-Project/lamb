"""Diff-coverage tests for ``creator_interface.library_router``.

Targets the error/edge branches added by the feature branch: capabilities
proxy, FR-10 library-delete blocking, youtube audit-language resolution,
capability content dispatch + caps, image-file traversal guard, original-file
resolution, and the kb-links / knowledge-stores aggregation endpoints.

These reuse the shared ``client``, ``lib_client``, ``lib_db``, ``auth_ctx``,
``async_return`` fixtures from ``conftest.py``.
"""

from __future__ import annotations

import httpx

from creator_interface import library_router


def _resp(content: bytes, content_type: str = "application/octet-stream"):
    """Build an async stub mimicking the LibraryManagerClient httpx.Response."""

    async def _proxy(*args, **kwargs):  # noqa: ARG001
        return httpx.Response(
            status_code=200,
            content=content,
            headers={"content-type": content_type},
        )

    return _proxy


# ---------------------------------------------------------------------------
# /capabilities (line 123)
# ---------------------------------------------------------------------------


def test_list_capabilities(client, lib_client, async_return):
    lib_client.get_capabilities = async_return({"handlers": ["text", "pages"]})
    resp = client.get("/creator/libraries/capabilities")
    assert resp.status_code == 200
    assert resp.json()["handlers"] == ["text", "pages"]


# ---------------------------------------------------------------------------
# delete_library FR-10 blocking (lines 269-279, 284)
# ---------------------------------------------------------------------------


def test_delete_library_blocked_by_active_links(client, lib_client, lib_db, async_return):
    lib_db.get_kb_content_links_for_library.return_value = [
        {
            "knowledge_store_id": "KS-1",
            "knowledge_store_name": "Course",
            "status": "ready",
            "library_item_id": "I1",
            "item_title": "Doc",
        },
        # duplicate KS id -> exercises the "already in blocking_stores" skip
        {
            "knowledge_store_id": "KS-1",
            "knowledge_store_name": "Course",
            "status": "processing",
            "library_item_id": "I2",
            "item_title": "Doc2",
        },
        # link without ks_id -> exercises the falsy-ks_id branch
        {
            "knowledge_store_id": None,
            "knowledge_store_name": None,
            "status": "ready",
            "library_item_id": "I3",
            "item_title": "Doc3",
        },
        # failed link -> filtered out before blocking
        {
            "knowledge_store_id": "KS-9",
            "knowledge_store_name": "Bad",
            "status": "failed",
            "library_item_id": "I4",
            "item_title": "Doc4",
        },
    ]
    lib_client.delete_library = async_return({})

    resp = client.delete("/creator/libraries/lib-1")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    ks_ids = {ks["id"] for ks in detail["knowledge_stores"]}
    assert ks_ids == {"KS-1"}
    # Failed link excluded from items list (active_links only).
    assert len(detail["items"]) == 3


# ---------------------------------------------------------------------------
# import_youtube audit_language from plugin_params (line 482)
# ---------------------------------------------------------------------------


def test_import_youtube_audit_language_from_plugin_params(client, lib_client, lib_db, async_return):
    lib_db.get_library.return_value = {
        "id": "lib-1", "organization_id": 1, "owner_user_id": 1, "is_shared": False,
        "name": "lib", "description": "", "import_config": {}, "status": "active",
    }
    lib_db.register_library_item.return_value = None
    lib_client.import_youtube = async_return(
        {"item_id": "i-1", "job_id": "j-1", "status": "processing"}
    )

    resp = client.post(
        "/creator/libraries/lib-1/import-youtube",
        json={
            "video_url": "https://youtu.be/x",
            "plugin_params": {"language": "es"},
        },
    )
    assert resp.status_code == 200
    # Audit was written with the plugin_params language.
    call = lib_db.write_audit_log.call_args
    assert call.kwargs["details"]["language"] == "es"


# ---------------------------------------------------------------------------
# get_item_capabilities (lines 720-721)
# ---------------------------------------------------------------------------


def test_get_item_capabilities(client, lib_client, async_return):
    lib_client.get_item_capabilities = async_return({"capabilities": ["text", "images"]})
    resp = client.get("/creator/libraries/lib-1/items/i-1/capabilities")
    assert resp.status_code == 200
    assert resp.json()["capabilities"] == ["text", "images"]


# ---------------------------------------------------------------------------
# get_item_capability_content (lines 739-740, 743-744, 750) + _content_disposition
# ---------------------------------------------------------------------------


def test_get_item_capability_content_happy(client, lib_client):
    lib_client.get_item_content = _resp(b"hello", "text/plain")
    resp = client.get("/creator/libraries/lib-1/items/i-1/content/text")
    assert resp.status_code == 200
    assert resp.content == b"hello"
    assert resp.headers["content-type"].startswith("text/plain")


def test_get_item_capability_content_too_large(client, lib_client):
    huge = b"x" * (library_router.MAX_CONTENT_BYTES + 1)
    lib_client.get_item_content = _resp(huge)
    resp = client.get("/creator/libraries/lib-1/items/i-1/content/images")
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# get_item_image_file (lines 773, 777-778, 780, 786) + _content_disposition (703-706)
# ---------------------------------------------------------------------------


def test_get_item_image_file_happy(client, lib_client):
    lib_client.proxy_content = _resp(b"\x89PNG", "image/png")
    resp = client.get("/creator/libraries/lib-1/items/i-1/content/images/file/pic.png")
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG"
    assert resp.headers["content-type"] == "image/png"


def test_get_item_image_file_traversal_rejected(client, lib_client):
    lib_client.proxy_content = _resp(b"unreachable")
    # Backslash traversal hits the validation branch (a forward slash would
    # change the route and not reach this handler).
    resp = client.get("/creator/libraries/lib-1/items/i-1/content/images/file/..%5Cetc")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid filename"


# ---------------------------------------------------------------------------
# get_item_original (lines 811, 813-815, 817-819, 821-822, 831, 837)
# ---------------------------------------------------------------------------


def test_get_item_original_binary(client, lib_client, async_return):
    # Filename with a space + parens exercises the ascii_safe sanitizer (chars
    # replaced with "_") and the RFC 5987 quote() path. Avoid raw non-ASCII
    # bytes in the header itself (the TestClient decodes headers as latin-1).
    lib_client.get_item = async_return({
        "original_filename": "my report (1).pdf",
        "source_url": None,
        "source_type": "file",
    })
    lib_client.proxy_content = _resp(b"%PDF-1.4", "application/pdf")

    resp = client.get("/creator/libraries/lib-1/items/i-1/original")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4"
    cd = resp.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd
    assert "filename=" in cd
    # Parens were sanitized out of the ascii_safe variant but survive in quoted.
    assert "%281%29" in cd


def test_get_item_original_not_found(client, lib_client, async_return):
    lib_client.get_item = async_return(None)
    resp = client.get("/creator/libraries/lib-1/items/i-1/original")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Item not found"


def test_get_item_original_no_binary(client, lib_client, async_return):
    lib_client.get_item = async_return({
        "original_filename": None,
        "source_url": "https://youtu.be/x",
        "source_type": "youtube",
    })
    resp = client.get("/creator/libraries/lib-1/items/i-1/original")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["source_url"] == "https://youtu.be/x"
    assert detail["source_type"] == "youtube"


# ---------------------------------------------------------------------------
# get_library_kb_links (lines 860-868)
# ---------------------------------------------------------------------------


def test_get_library_kb_links(client, lib_db):
    lib_db.get_kb_content_links_for_library.return_value = [
        {
            "knowledge_store_id": "KS-1",
            "knowledge_store_name": "Course",
            "status": "ready",
            "library_item_id": "I1",
            "item_title": "Doc",
        },
        # duplicate KS id -> dedup branch
        {
            "knowledge_store_id": "KS-1",
            "knowledge_store_name": "Course",
            "status": "processing",
            "library_item_id": "I2",
            "item_title": None,
        },
        # failed -> filtered out
        {
            "knowledge_store_id": "KS-2",
            "knowledge_store_name": "Bad",
            "status": "failed",
            "library_item_id": "I3",
            "item_title": "Doc3",
        },
    ]
    resp = client.get("/creator/libraries/lib-1/kb-links")
    assert resp.status_code == 200
    body = resp.json()
    assert body["library_id"] == "lib-1"
    assert len(body["items"]) == 2
    assert [ks["id"] for ks in body["knowledge_stores"]] == ["KS-1"]
    # item_title falls back to library_item_id when None.
    titles = {it["id"]: it["title"] for it in body["items"]}
    assert titles["I2"] == "I2"


# ---------------------------------------------------------------------------
# get_library_knowledge_stores (lines 939, 941-947, 961)
# ---------------------------------------------------------------------------


def test_get_library_knowledge_stores_filters_inaccessible(client, lib_db, auth_ctx):
    lib_db.get_knowledge_stores_for_library.return_value = [
        {
            "id": "KS-vis", "name": "Visible", "description": "d",
            "chunking_strategy": "simple", "embedding_vendor": "openai",
            "embedding_model": "m", "vector_db_backend": "chroma",
            "is_shared": True, "item_count": 3, "ready_count": 2, "failed_count": 1,
        },
        {
            "id": "KS-hidden", "name": "Hidden", "description": "d",
            "chunking_strategy": "simple", "embedding_vendor": "openai",
            "embedding_model": "m", "vector_db_backend": "chroma",
            "is_shared": False, "item_count": 0, "ready_count": 0, "failed_count": 0,
        },
    ]

    def _access(ks_id):
        return "none" if ks_id == "KS-hidden" else "owner"

    auth_ctx.can_access_knowledge_store = _access  # type: ignore[assignment]

    resp = client.get("/creator/libraries/lib-1/knowledge-stores")
    assert resp.status_code == 200
    body = resp.json()
    assert body["library_id"] == "lib-1"
    assert len(body["knowledge_stores"]) == 1
    visible = body["knowledge_stores"][0]
    assert visible["id"] == "KS-vis"
    assert visible["access"] == "owner"
    assert visible["item_count"] == 3
