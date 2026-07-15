"""Integration tests for ``/creator/libraries/{id}/{folders,tree}`` routes.

Exercises the LAMB Creator Interface proxy endpoints with the downstream
``LibraryManagerClient`` stubbed via ``MagicMock`` (see ``conftest.py``).
Covers happy paths, ACL boundary, FR-10 regression on tree-path item
delete, and payload caps.
"""

from __future__ import annotations

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Tree endpoint
# ---------------------------------------------------------------------------


def test_get_tree_happy_path(client, lib_client, async_return):
    lib_client.get_tree = async_return({
        "library_id": "lib-1",
        "folders": [
            {"id": "f1", "name": "Q1", "parent_folder_id": None,
             "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
        ],
        "items": [
            {"id": "i1", "title": "Doc", "folder_id": "f1",
             "source_type": "file", "import_plugin": "simple_import",
             "status": "ready", "page_count": 0, "image_count": 0,
             "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
        ],
    })

    response = client.get("/creator/libraries/lib-1/tree")
    assert response.status_code == 200
    body = response.json()
    assert body["library_id"] == "lib-1"
    assert len(body["folders"]) == 1
    assert body["folders"][0]["id"] == "f1"
    assert body["items"][0]["folder_id"] == "f1"


def test_get_tree_acl_denied(client, lib_client, auth_ctx):
    """Non-owner without any share access -> 404 (anti-enumeration)."""
    def _no_access(_lib_id):
        return "none"
    auth_ctx.can_access_library = _no_access  # type: ignore[assignment]

    response = client.get("/creator/libraries/lib-1/tree")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------


def test_create_folder(client, lib_client, lib_db, async_return):
    lib_client.create_folder = async_return({
        "id": "f-new",
        "name": "Drafts",
        "parent_folder_id": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    })

    response = client.post(
        "/creator/libraries/lib-1/folders",
        json={"name": "Drafts"},
    )
    assert response.status_code == 201
    assert response.json()["id"] == "f-new"
    lib_db.write_audit_log.assert_called()


def test_create_folder_acl_denied(client, lib_client, auth_ctx, async_return):
    def _no_access(_lib_id):
        return "none"
    auth_ctx.can_access_library = _no_access  # type: ignore[assignment]
    lib_client.create_folder = async_return({})

    response = client.post(
        "/creator/libraries/lib-1/folders",
        json={"name": "Drafts"},
    )
    # require_library_access returns 404 (anti-enumeration), not 403.
    assert response.status_code == 404


def test_rename_folder(client, lib_client, async_return):
    lib_client.rename_folder = async_return({
        "id": "f-1",
        "name": "Renamed",
        "parent_folder_id": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    })

    response = client.put(
        "/creator/libraries/lib-1/folders/f-1",
        json={"name": "Renamed"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_move_folder(client, lib_client, async_return):
    lib_client.move_folder = async_return({
        "id": "f-1",
        "name": "F1",
        "parent_folder_id": "f-2",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    })

    response = client.put(
        "/creator/libraries/lib-1/folders/f-1/move",
        json={"parent_folder_id": "f-2"},
    )
    assert response.status_code == 200
    assert response.json()["parent_folder_id"] == "f-2"


def test_delete_folder_requires_owner(client, lib_client, auth_ctx, async_return):
    """Delete folder must require owner-level access (shared user is rejected with 403)."""
    def _shared_only(_lib_id):
        return "shared"
    auth_ctx.can_access_library = _shared_only  # type: ignore[assignment]
    lib_client.delete_folder = async_return({"message": "Folder deleted."})

    response = client.delete("/creator/libraries/lib-1/folders/f-1")
    # "shared" is not "owner" -> require_library_access raises 403
    assert response.status_code == 403


def test_delete_folder_owner_allowed(client, lib_client, async_return):
    lib_client.delete_folder = async_return({
        "message": "Folder deleted.",
        "items_reparented_to": None,
    })
    response = client.delete("/creator/libraries/lib-1/folders/f-1")
    assert response.status_code == 200
    assert response.json()["items_reparented_to"] is None


# ---------------------------------------------------------------------------
# Item move
# ---------------------------------------------------------------------------


def test_move_items(client, lib_client, async_return):
    lib_client.move_items = async_return({"moved": 3, "folder_id": "f-1"})

    response = client.post(
        "/creator/libraries/lib-1/items/move",
        json={"item_ids": ["a", "b", "c"], "folder_id": "f-1"},
    )
    assert response.status_code == 200
    assert response.json()["moved"] == 3


def test_move_items_payload_cap(client, lib_client, async_return):
    """Bodies with > 500 item_ids must be rejected with 413."""
    lib_client.move_items = async_return({})
    big = [f"item-{i}" for i in range(501)]
    response = client.post(
        "/creator/libraries/lib-1/items/move",
        json={"item_ids": big, "folder_id": None},
    )
    assert response.status_code == 413


def test_move_items_acl_denied(client, lib_client, auth_ctx, async_return):
    def _no_access(_lib_id):
        return "none"
    auth_ctx.can_access_library = _no_access  # type: ignore[assignment]
    lib_client.move_items = async_return({})

    response = client.post(
        "/creator/libraries/lib-1/items/move",
        json={"item_ids": ["a"], "folder_id": None},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Upload-with-folder_id (regression that the existing endpoint forwards
# the new optional form field)
# ---------------------------------------------------------------------------


def test_upload_forwards_folder_id(client, lib_client, lib_db, async_return):
    """The /upload endpoint must forward folder_id to the Library Manager client."""
    import io
    from unittest.mock import MagicMock

    lib_db.get_library.return_value = {
        "id": "lib-1", "organization_id": 1, "owner_user_id": 1, "is_shared": False,
        "name": "lib", "description": "", "import_config": {}, "status": "active",
    }
    lib_db.register_library_item.return_value = None

    forwarded: dict = {}

    async def _import_file(**kwargs):
        forwarded.update(kwargs)
        return {"item_id": "i-1", "job_id": "j-1", "status": "processing"}

    lib_client.import_file = _import_file

    response = client.post(
        "/creator/libraries/lib-1/upload",
        files={"file": ("a.txt", io.BytesIO(b"x"), "text/plain")},
        data={"plugin_name": "simple_import", "title": "X", "folder_id": "f-1"},
    )
    assert response.status_code == 200
    assert forwarded["folder_id"] == "f-1"
