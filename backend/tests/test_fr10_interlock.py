"""Cross-service FR-10 interlock tests.

FR-10 (issue #334): a Library item that is referenced by any active
Knowledge Store cannot be deleted from its Library — LAMB enforces this
in ``DELETE /creator/libraries/{lib}/items/{item}`` against the
``kb_content_links`` table. After unlinking the item from every
referencing Knowledge Store, the same delete must succeed.

These tests intentionally cross both router boundaries: they call the
``DELETE`` library-item route, then the ``DELETE`` knowledge-store
content route, then the library-item route again, verifying the
interlock behaves as a transactional invariant against the LAMB DB.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock


def _library_row(library_id: str = "lib-1") -> Dict[str, Any]:
    return {
        "id": library_id,
        "name": "Course",
        "owner_user_id": 1,
        "organization_id": 1,
        "is_shared": False,
        "status": "active",
        "description": "",
        "import_config": {},
        "created_at": 0,
        "updated_at": 0,
    }


def _link(
    *,
    ks_id: str = "ks-1",
    ks_name: str = "Course KS",
    item_id: str = "item-1",
    status: str = "ready",
) -> Dict[str, Any]:
    return {
        "knowledge_store_id": ks_id,
        "knowledge_store_name": ks_name,
        "library_item_id": item_id,
        "status": status,
        "id": 42,
    }


# ---------------------------------------------------------------------------
# 409 when the item is still referenced
# ---------------------------------------------------------------------------


def test_delete_item_blocked_lists_blocking_ks_in_409(client, lib_db, lib_client):
    """When a single KS still references the item, DELETE responds 409 with
    the KS id+name in ``detail.knowledge_stores``."""
    lib_db.get_library.return_value = _library_row()
    lib_db.get_kb_content_links_for_item.return_value = [
        _link(ks_id="ks-1", ks_name="Course KS", status="ready")
    ]

    response = client.delete("/creator/libraries/lib-1/items/item-1")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "knowledge_stores" in detail
    assert detail["knowledge_stores"] == [
        {"id": "ks-1", "name": "Course KS", "status": "ready"}
    ]

    # The downstream delete must NOT have been issued and the LAMB row must
    # NOT have been removed.
    lib_client.delete_item.assert_not_called()
    lib_db.delete_library_item.assert_not_called()


def test_delete_item_blocked_lists_multiple_kses(client, lib_db, lib_client):
    """When multiple KSes reference the same item, all are reported in 409."""
    lib_db.get_library.return_value = _library_row()
    lib_db.get_kb_content_links_for_item.return_value = [
        _link(ks_id="ks-a", ks_name="KS A", status="processing"),
        _link(ks_id="ks-b", ks_name="KS B", status="ready"),
    ]

    response = client.delete("/creator/libraries/lib-1/items/item-1")

    assert response.status_code == 409
    detail = response.json()["detail"]
    ks_ids = {ks["id"] for ks in detail["knowledge_stores"]}
    assert ks_ids == {"ks-a", "ks-b"}


# ---------------------------------------------------------------------------
# Unlink-then-delete sequence (the interlock)
# ---------------------------------------------------------------------------


def test_unlink_then_delete_succeeds(
    client, lib_db, lib_client, ks_db, ks_client
):
    """Full sequence: blocked -> unlink from KS -> delete proceeds.

    Simulates the ``kb_content_links`` table flipping from "has an active
    link" to "no links" between the two delete calls. Mirrors the
    realistic UX of the user clicking 'remove from KS' before retrying.
    """
    lib_db.get_library.return_value = _library_row()
    lib_client.delete_item = AsyncMock(return_value={})
    lib_db.delete_library_item.return_value = True

    # ---- Step 1: first DELETE blocked by an active link ----
    lib_db.get_kb_content_links_for_item.return_value = [
        _link(ks_id="ks-1", ks_name="Course KS", status="ready")
    ]

    blocked = client.delete("/creator/libraries/lib-1/items/item-1")
    assert blocked.status_code == 409
    lib_client.delete_item.assert_not_called()

    # ---- Step 2: caller unlinks the item from KS ----
    ks_db.get_kb_content_link.return_value = {
        "id": 42,
        "knowledge_store_id": "ks-1",
        "library_item_id": "item-1",
        "status": "ready",
    }
    ks_client.delete_content_by_source = AsyncMock(return_value={"status": "deleted"})
    ks_db.delete_kb_content_link.return_value = True

    unlink = client.delete("/creator/knowledge-stores/ks-1/content/item-1")
    assert unlink.status_code == 200

    ks_client.delete_content_by_source.assert_called_once()
    ks_db.delete_kb_content_link.assert_called_once_with("ks-1", "item-1")

    # ---- Step 3: now the LAMB DB reports no active links -> retry succeeds. ----
    lib_db.get_kb_content_links_for_item.return_value = []  # link removed.

    retry = client.delete("/creator/libraries/lib-1/items/item-1")
    assert retry.status_code == 200
    lib_client.delete_item.assert_called_once()
    lib_db.delete_library_item.assert_called_once_with("item-1")
