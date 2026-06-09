"""Integration tests for ``/creator/libraries/*`` Creator Interface routes.

These tests mount the real ``library_router`` on a minimal FastAPI app and
exercise the routes end-to-end, with all downstream services stubbed:
``LibraryManagerClient`` calls and ``LambDatabaseManager`` writes are
replaced by ``MagicMock``s. The auth dependency is overridden via the
fixtures in ``conftest.py``.
"""

from __future__ import annotations

import io
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _library_row(
    library_id: str = "lib-1",
    name: str = "My Library",
    owner_user_id: int = 1,
    organization_id: int = 1,
    is_shared: bool = False,
    status: str = "active",
) -> Dict[str, Any]:
    return {
        "id": library_id,
        "name": name,
        "owner_user_id": owner_user_id,
        "organization_id": organization_id,
        "is_shared": is_shared,
        "description": "",
        "import_config": {},
        "status": status,
        "created_at": 0,
        "updated_at": 0,
        "owner_name": "Creator User",
        "owner_email": "creator@example.com",
    }


# ---------------------------------------------------------------------------
# POST /creator/libraries
# ---------------------------------------------------------------------------


def test_create_library_happy_path(client, lib_db, lib_client, async_return):
    """Valid body -> 200, LAMB row inserted, downstream LM call mocked."""
    lib_db.create_library.return_value = "lib-uuid-1"
    lib_db.update_library_status.return_value = True
    lib_db.get_library.return_value = _library_row(library_id="lib-uuid-1", name="Bio 101")
    lib_client.create_library = async_return({"id": "lib-uuid-1"})

    response = client.post(
        "/creator/libraries",
        json={"name": "Bio 101", "description": "Course readings"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Bio 101"

    # The LAMB row was created provisional, then promoted.
    assert lib_db.create_library.called
    create_kwargs = lib_db.create_library.call_args.kwargs
    assert create_kwargs["name"] == "Bio 101"
    assert create_kwargs["status"] == "provisional"
    assert create_kwargs["organization_id"] == 1
    lib_db.update_library_status.assert_called_once()


def test_create_library_missing_name_returns_422(client, lib_db, lib_client):
    """Missing ``name`` field -> 422 from FastAPI's pydantic validation."""
    response = client.post("/creator/libraries", json={"description": "no name"})
    assert response.status_code == 422
    # No DB row created on a validation failure.
    lib_db.create_library.assert_not_called()


# ---------------------------------------------------------------------------
# GET /creator/libraries
# ---------------------------------------------------------------------------


def test_list_libraries_returns_owned_and_shared(client, lib_db):
    """List endpoint should return the DB result (owned + shared) verbatim."""
    lib_db.get_accessible_libraries.return_value = [
        _library_row(library_id="own-1", name="Mine", owner_user_id=1),
        _library_row(library_id="shared-1", name="Shared", owner_user_id=2, is_shared=True),
    ]

    response = client.get("/creator/libraries")
    assert response.status_code == 200
    payload = response.json()
    assert "libraries" in payload
    assert {lib["id"] for lib in payload["libraries"]} == {"own-1", "shared-1"}

    lib_db.get_accessible_libraries.assert_called_once_with(
        user_id=1, organization_id=1
    )


# ---------------------------------------------------------------------------
# POST /creator/libraries/{lib_id}/upload
# ---------------------------------------------------------------------------


def test_upload_file_happy_path(client, lib_db, lib_client, async_return):
    """File upload -> downstream forwarded with right form fields, item registered."""
    lib_db.user_can_access_library.return_value = (True, "owner")
    lib_db.get_library.return_value = _library_row(library_id="lib-1")
    lib_db.get_creator_user_by_id.return_value = {"id": 1, "organization_id": 1}
    lib_db.register_library_item.return_value = "item-1"

    lib_client.import_file = async_return({"item_id": "item-1", "status": "queued"})

    file_content = b"hello world"
    response = client.post(
        "/creator/libraries/lib-1/upload",
        files={"file": ("notes.txt", file_content, "text/plain")},
        data={"plugin_name": "simple_import", "title": "My Notes"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == "item-1"

    # The item was registered with the right metadata.
    register_kwargs = lib_db.register_library_item.call_args.kwargs
    assert register_kwargs["item_id"] == "item-1"
    assert register_kwargs["library_id"] == "lib-1"
    assert register_kwargs["title"] == "My Notes"
    assert register_kwargs["import_plugin"] == "simple_import"
    assert register_kwargs["original_filename"] == "notes.txt"
    assert register_kwargs["content_type"] == "text/plain"


def test_upload_file_empty_returns_400(client, lib_db, lib_client, async_raise):
    """Empty file uploaded — downstream rejects with 400, propagated to client.

    Regression for D2: the LM rejects empty files with 400; the backend
    must surface that status rather than swallowing it.
    """
    lib_db.user_can_access_library.return_value = (True, "owner")
    lib_db.get_library.return_value = _library_row(library_id="lib-1")
    lib_db.get_creator_user_by_id.return_value = {"id": 1, "organization_id": 1}

    lib_client.import_file = async_raise(
        HTTPException(status_code=400, detail="Library Manager error: file is empty")
    )

    response = client.post(
        "/creator/libraries/lib-1/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"plugin_name": "simple_import"},
    )

    assert response.status_code == 400
    # The library item must NOT be registered when ingestion is rejected.
    lib_db.register_library_item.assert_not_called()


# ---------------------------------------------------------------------------
# POST /creator/libraries/{lib_id}/import-url
# ---------------------------------------------------------------------------


def test_import_url_invalid_url_returns_4xx(client, lib_db, lib_client, async_raise):
    """Invalid URL — downstream returns 400, the backend surfaces 4xx."""
    lib_db.user_can_access_library.return_value = (True, "owner")
    lib_db.get_library.return_value = _library_row(library_id="lib-1")
    lib_db.get_creator_user_by_id.return_value = {"id": 1, "organization_id": 1}

    lib_client.import_url = async_raise(
        HTTPException(status_code=400, detail="Library Manager error: invalid URL")
    )

    response = client.post(
        "/creator/libraries/lib-1/import-url",
        json={"url": "not-a-valid-url", "plugin_name": "url_import"},
    )

    assert 400 <= response.status_code < 500
    lib_db.register_library_item.assert_not_called()


# ---------------------------------------------------------------------------
# DELETE /creator/libraries/{lib_id}/items/{item_id} — FR-10
# ---------------------------------------------------------------------------


def test_delete_item_blocked_by_active_ks_returns_409(client, lib_db, lib_client):
    """FR-10: cannot delete a library item that an active KS still references."""
    lib_db.user_can_access_library.return_value = (True, "owner")
    lib_db.get_library.return_value = _library_row(library_id="lib-1")
    lib_db.get_creator_user_by_id.return_value = {"id": 1, "organization_id": 1}
    lib_db.get_kb_content_links_for_item.return_value = [
        {
            "knowledge_store_id": "ks-1",
            "knowledge_store_name": "Course KS",
            "status": "ready",
        }
    ]

    response = client.delete("/creator/libraries/lib-1/items/item-99")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "knowledge_stores" in detail
    assert any(ks["id"] == "ks-1" for ks in detail["knowledge_stores"])

    # Critically: the downstream delete must NOT have been called.
    lib_client.delete_item.assert_not_called()
    lib_db.delete_library_item.assert_not_called()


def test_delete_item_unblocked_succeeds(client, lib_db, lib_client, async_return):
    """No active links — delete proceeds; downstream + LAMB DB called."""
    lib_db.user_can_access_library.return_value = (True, "owner")
    lib_db.get_library.return_value = _library_row(library_id="lib-1")
    lib_db.get_creator_user_by_id.return_value = {"id": 1, "organization_id": 1}
    lib_db.get_kb_content_links_for_item.return_value = []  # No references.
    lib_db.delete_library_item.return_value = True
    lib_client.delete_item = async_return({"status": "deleted"})

    response = client.delete("/creator/libraries/lib-1/items/item-99")

    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()

    lib_db.delete_library_item.assert_called_once_with("item-99")


def test_delete_item_with_only_failed_links_proceeds(
    client, lib_db, lib_client, async_return
):
    """Only ``status='failed'`` links don't block deletion — they're ignored."""
    lib_db.user_can_access_library.return_value = (True, "owner")
    lib_db.get_library.return_value = _library_row(library_id="lib-1")
    lib_db.get_creator_user_by_id.return_value = {"id": 1, "organization_id": 1}
    lib_db.get_kb_content_links_for_item.return_value = [
        {
            "knowledge_store_id": "ks-1",
            "knowledge_store_name": "Old KS",
            "status": "failed",
        }
    ]
    lib_db.delete_library_item.return_value = True
    lib_client.delete_item = async_return({})

    response = client.delete("/creator/libraries/lib-1/items/item-99")
    assert response.status_code == 200
