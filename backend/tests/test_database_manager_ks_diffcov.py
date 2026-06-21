"""Diff-coverage tests for Knowledge-Store / kb_content_links DB methods.

These exercise the real ``LambDatabaseManager`` against a temporary SQLite
database (built by the manager's own migrations under a tmp dir). Both the
happy paths and the error / None / not-found branches of the methods in the
``lamb.database_manager`` target range (7715-8364) are covered.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import config


@pytest.fixture
def dbm(tmp_path, monkeypatch):
    """Construct a real manager backed by a fresh temp lamb_v4.db.

    Seeds one organization and two creator users so the FK constraints on
    ``knowledge_stores`` / ``kb_content_links`` are satisfiable.
    """
    monkeypatch.setattr(config, "LAMB_DB_PATH", str(tmp_path))
    from lamb.database_manager import LambDatabaseManager

    manager = LambDatabaseManager()

    # __init__ auto-creates the system organization with id=1; reuse it.
    conn = manager.get_connection()
    now = int(time.time())
    with conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {manager.table_prefix}Creator_users "
            f"(id, organization_id, user_email, user_name, user_type, user_config, created_at, updated_at) "
            f"VALUES (10, 1, 'owner@example.com', 'Owner', 'creator', '{{}}', ?, ?)",
            (now, now),
        )
        cur.execute(
            f"INSERT INTO {manager.table_prefix}Creator_users "
            f"(id, organization_id, user_email, user_name, user_type, user_config, created_at, updated_at) "
            f"VALUES (11, 1, 'other@example.com', 'Other', 'creator', '{{}}', ?, ?)",
            (now, now),
        )
    conn.close()
    return manager


def _make_ks(dbm, ks_id="ks-1", name="KS One", owner=10, org=1,
             chunking_params=None, status="active"):
    return dbm.create_knowledge_store(
        knowledge_store_id=ks_id,
        name=name,
        owner_user_id=owner,
        organization_id=org,
        chunking_strategy="simple",
        embedding_vendor="openai",
        embedding_model="text-embedding-3-small",
        vector_db_backend="chromadb",
        description="desc",
        chunking_params=chunking_params,
        status=status,
    )


# ---------------------------------------------------------------------------
# create_knowledge_store
# ---------------------------------------------------------------------------


def test_create_knowledge_store_success(dbm):
    result = _make_ks(dbm, chunking_params={"size": 500})
    assert result == "ks-1"


def test_create_knowledge_store_duplicate_name(dbm):
    assert _make_ks(dbm, ks_id="ks-a", name="Dup") == "ks-a"
    # Same org + name violates UNIQUE -> IntegrityError -> None
    assert _make_ks(dbm, ks_id="ks-b", name="Dup") is None


def test_create_knowledge_store_db_error(dbm):
    # Invalid SQL via bad table prefix triggers sqlite3.Error branch
    dbm.table_prefix = "nonexistent_"
    assert _make_ks(dbm, ks_id="ks-err") is None


def test_create_knowledge_store_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert _make_ks(dbm, ks_id="ks-nc") is None


# ---------------------------------------------------------------------------
# update_knowledge_store_status
# ---------------------------------------------------------------------------


def test_update_status_success_and_missing(dbm):
    _make_ks(dbm, ks_id="ks-s", status="provisional")
    assert dbm.update_knowledge_store_status("ks-s", "active") is True
    assert dbm.update_knowledge_store_status("missing", "active") is False


def test_update_status_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.update_knowledge_store_status("ks-s", "active") is False


def test_update_status_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.update_knowledge_store_status("ks-s", "active") is False


# ---------------------------------------------------------------------------
# get_knowledge_store
# ---------------------------------------------------------------------------


def test_get_knowledge_store_success(dbm):
    _make_ks(dbm, ks_id="ks-g", chunking_params={"size": 100})
    ks = dbm.get_knowledge_store("ks-g")
    assert ks is not None
    assert ks["id"] == "ks-g"
    assert ks["is_shared"] is False
    assert ks["chunking_params"] == {"size": 100}
    assert ks["owner_email"] == "owner@example.com"


def test_get_knowledge_store_bad_json_params(dbm):
    _make_ks(dbm, ks_id="ks-bad")
    # Corrupt chunking_params to a non-JSON string -> except -> {}
    conn = dbm.get_connection()
    with conn:
        conn.execute(
            f"UPDATE {dbm.table_prefix}knowledge_stores SET chunking_params = 'not json' WHERE id = ?",
            ("ks-bad",),
        )
    conn.close()
    ks = dbm.get_knowledge_store("ks-bad")
    assert ks["chunking_params"] == {}


def test_get_knowledge_store_not_found(dbm):
    assert dbm.get_knowledge_store("nope") is None


def test_get_knowledge_store_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_knowledge_store("ks-g") is None


def test_get_knowledge_store_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_knowledge_store("ks-g") is None


# ---------------------------------------------------------------------------
# get_accessible_knowledge_stores
# ---------------------------------------------------------------------------


def test_get_accessible_knowledge_stores(dbm):
    _make_ks(dbm, ks_id="ks-own", name="Owned", owner=10)
    _make_ks(dbm, ks_id="ks-shared", name="Shared", owner=11)
    dbm.toggle_knowledge_store_sharing("ks-shared", True)
    # Also a non-shared KS owned by other user -> not visible
    _make_ks(dbm, ks_id="ks-hidden", name="Hidden", owner=11)
    # corrupt the params on one to hit the json-decode except branch
    conn = dbm.get_connection()
    with conn:
        conn.execute(
            f"UPDATE {dbm.table_prefix}knowledge_stores SET chunking_params = 'bad' WHERE id = ?",
            ("ks-own",),
        )
    conn.close()

    rows = dbm.get_accessible_knowledge_stores(user_id=10, organization_id=1)
    ids = {r["id"] for r in rows}
    assert ids == {"ks-own", "ks-shared"}
    own = next(r for r in rows if r["id"] == "ks-own")
    assert own["chunking_params"] == {}
    assert own["is_shared"] is False


def test_get_accessible_knowledge_stores_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_accessible_knowledge_stores(10, 1) == []


def test_get_accessible_knowledge_stores_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_accessible_knowledge_stores(10, 1) == []


# ---------------------------------------------------------------------------
# user_can_access_knowledge_store
# ---------------------------------------------------------------------------


def test_user_can_access_owner(dbm):
    _make_ks(dbm, ks_id="ks-acc", owner=10)
    assert dbm.user_can_access_knowledge_store("ks-acc", 10) == (True, "owner")


def test_user_can_access_shared(dbm):
    _make_ks(dbm, ks_id="ks-acc2", owner=10)
    dbm.toggle_knowledge_store_sharing("ks-acc2", True)
    assert dbm.user_can_access_knowledge_store("ks-acc2", 11) == (True, "shared")


def test_user_can_access_none_not_shared(dbm):
    _make_ks(dbm, ks_id="ks-acc3", owner=10)
    assert dbm.user_can_access_knowledge_store("ks-acc3", 11) == (False, "none")


def test_user_can_access_missing_ks(dbm):
    assert dbm.user_can_access_knowledge_store("missing", 10) == (False, "none")


# ---------------------------------------------------------------------------
# toggle_knowledge_store_sharing
# ---------------------------------------------------------------------------


def test_toggle_sharing_success_and_missing(dbm):
    _make_ks(dbm, ks_id="ks-t")
    assert dbm.toggle_knowledge_store_sharing("ks-t", True) is True
    assert dbm.toggle_knowledge_store_sharing("missing", True) is False


def test_toggle_sharing_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.toggle_knowledge_store_sharing("ks-t", True) is False


def test_toggle_sharing_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.toggle_knowledge_store_sharing("ks-t", True) is False


# ---------------------------------------------------------------------------
# update_knowledge_store
# ---------------------------------------------------------------------------


def test_update_knowledge_store_all_fields(dbm):
    _make_ks(dbm, ks_id="ks-u")
    assert dbm.update_knowledge_store(
        "ks-u", name="New", description="New desc",
        chunking_params={"size": 999},
    ) is True
    ks = dbm.get_knowledge_store("ks-u")
    assert ks["name"] == "New"
    assert ks["description"] == "New desc"
    assert ks["chunking_params"] == {"size": 999}


def test_update_knowledge_store_no_optional_fields(dbm):
    _make_ks(dbm, ks_id="ks-u2")
    # Only updated_at set -> still updates the existing row
    assert dbm.update_knowledge_store("ks-u2") is True
    # Missing id -> no rows
    assert dbm.update_knowledge_store("missing") is False


def test_update_knowledge_store_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.update_knowledge_store("ks-u", name="x") is False


def test_update_knowledge_store_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.update_knowledge_store("ks-u", name="x") is False


# ---------------------------------------------------------------------------
# delete_knowledge_store
# ---------------------------------------------------------------------------


def test_delete_knowledge_store_success_and_missing(dbm):
    _make_ks(dbm, ks_id="ks-d")
    assert dbm.delete_knowledge_store("ks-d") is True
    assert dbm.delete_knowledge_store("ks-d") is False


def test_delete_knowledge_store_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.delete_knowledge_store("ks-d") is False


def test_delete_knowledge_store_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.delete_knowledge_store("ks-d") is False


# ---------------------------------------------------------------------------
# register_kb_content_link
# ---------------------------------------------------------------------------


def _seed_library_item(dbm, lib_id="lib-1", item_id="item-1",
                       title="Item Title", org=1, owner=10):
    now = int(time.time())
    conn = dbm.get_connection()
    with conn:
        conn.execute(
            f"INSERT OR IGNORE INTO {dbm.table_prefix}libraries "
            f"(id, organization_id, name, description, owner_user_id, status, created_at, updated_at) "
            f"VALUES (?, ?, ?, '', ?, 'active', ?, ?)",
            (lib_id, org, f"Library {lib_id}", owner, now, now),
        )
        conn.execute(
            f"INSERT INTO {dbm.table_prefix}library_items "
            f"(id, library_id, organization_id, title, source_type, import_plugin, status, uploader_user_id, created_at, updated_at) "
            f"VALUES (?, ?, ?, ?, 'file', 'simple', 'ready', ?, ?, ?)",
            (item_id, lib_id, org, title, owner, now, now),
        )
    conn.close()


def test_register_kb_content_link_success(dbm):
    _make_ks(dbm, ks_id="ks-link")
    _seed_library_item(dbm)
    link_id = dbm.register_kb_content_link(
        knowledge_store_id="ks-link", library_id="lib-1",
        library_item_id="item-1", organization_id=1,
        created_by_user_id=10, kb_job_id="job-1", status="pending",
    )
    assert isinstance(link_id, int)


def test_register_kb_content_link_duplicate(dbm):
    _make_ks(dbm, ks_id="ks-link2")
    _seed_library_item(dbm)
    assert dbm.register_kb_content_link(
        "ks-link2", "lib-1", "item-1", 1, 10,
    ) is not None
    # Duplicate (ks, item) -> UNIQUE violation -> None
    assert dbm.register_kb_content_link(
        "ks-link2", "lib-1", "item-1", 1, 10,
    ) is None


def test_register_kb_content_link_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.register_kb_content_link("ks", "lib", "item", 1, 10) is None


def test_register_kb_content_link_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.register_kb_content_link("ks", "lib", "item", 1, 10) is None


# ---------------------------------------------------------------------------
# update_kb_content_link_status
# ---------------------------------------------------------------------------


def test_update_link_status_by_id(dbm):
    _make_ks(dbm, ks_id="ks-up")
    _seed_library_item(dbm)
    link_id = dbm.register_kb_content_link("ks-up", "lib-1", "item-1", 1, 10)
    assert dbm.update_kb_content_link_status(
        link_id=link_id, status="ready", kb_job_id="j2",
        chunks_created=7, error_message="none",
    ) is True
    row = dbm.get_kb_content_link("ks-up", "item-1")
    assert row["status"] == "ready"
    assert row["chunks_created"] == 7


def test_update_link_status_by_ks_item_pair(dbm):
    _make_ks(dbm, ks_id="ks-up2")
    _seed_library_item(dbm)
    dbm.register_kb_content_link("ks-up2", "lib-1", "item-1", 1, 10)
    assert dbm.update_kb_content_link_status(
        knowledge_store_id="ks-up2", library_item_id="item-1", status="failed",
    ) is True


def test_update_link_status_no_lookup_keys(dbm):
    # Neither link_id nor (ks, item) pair -> returns False without query
    assert dbm.update_kb_content_link_status(status="ready") is False


def test_update_link_status_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.update_kb_content_link_status(link_id=1, status="x") is False


def test_update_link_status_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.update_kb_content_link_status(link_id=1, status="x") is False


# ---------------------------------------------------------------------------
# delete_kb_content_link
# ---------------------------------------------------------------------------


def test_delete_link_success_and_missing(dbm):
    _make_ks(dbm, ks_id="ks-dl")
    _seed_library_item(dbm)
    dbm.register_kb_content_link("ks-dl", "lib-1", "item-1", 1, 10)
    assert dbm.delete_kb_content_link("ks-dl", "item-1") is True
    assert dbm.delete_kb_content_link("ks-dl", "item-1") is False


def test_delete_link_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.delete_kb_content_link("ks", "item") is False


def test_delete_link_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.delete_kb_content_link("ks", "item") is False


# ---------------------------------------------------------------------------
# get_kb_content_links_for_ks
# ---------------------------------------------------------------------------


def test_get_links_for_ks_with_item(dbm):
    _make_ks(dbm, ks_id="ks-list")
    _seed_library_item(dbm)
    dbm.register_kb_content_link("ks-list", "lib-1", "item-1", 1, 10)
    rows = dbm.get_kb_content_links_for_ks("ks-list")
    assert len(rows) == 1
    assert rows[0]["item_title"] == "Item Title"
    assert rows[0]["library_name"] == "Library lib-1"
    assert rows[0]["library_deleted"] is False
    assert rows[0]["item_deleted"] is False


def test_get_links_for_ks_orphan_uses_audit_log(dbm):
    """Link whose library/item rows are gone falls back to audit_log."""
    _make_ks(dbm, ks_id="ks-orphan")
    now = int(time.time())
    conn = dbm.get_connection()
    with conn:
        # audit log entries for the recovered names
        conn.execute(
            f"INSERT INTO {dbm.table_prefix}audit_log "
            f"(organization_id, actor_user_id, action, target_type, target_id, details, created_at) "
            f"VALUES (1, 10, 'library.create', 'library', 'gone-lib', ?, ?)",
            ('{"name": "Gone Library"}', now),
        )
        conn.execute(
            f"INSERT INTO {dbm.table_prefix}audit_log "
            f"(organization_id, actor_user_id, action, target_type, target_id, details, created_at) "
            f"VALUES (1, 10, 'library.upload', 'library_item', 'gone-item', ?, ?)",
            ('{"filename": "gone.pdf"}', now),
        )
        # content link pointing at non-existent library/item
        conn.execute(
            f"INSERT INTO {dbm.table_prefix}kb_content_links "
            f"(knowledge_store_id, library_id, library_item_id, organization_id, status, chunks_created, created_by_user_id, created_at, updated_at) "
            f"VALUES ('ks-orphan', 'gone-lib', 'gone-item', 1, 'ready', 0, 10, ?, ?)",
            (now, now),
        )
    conn.close()
    rows = dbm.get_kb_content_links_for_ks("ks-orphan")
    assert len(rows) == 1
    assert rows[0]["item_title"] == "gone.pdf"
    assert rows[0]["library_name"] == "Gone Library"
    assert rows[0]["library_deleted"] is True
    assert rows[0]["item_deleted"] is True


def test_get_links_for_ks_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_kb_content_links_for_ks("ks") == []


def test_get_links_for_ks_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_kb_content_links_for_ks("ks") == []


# ---------------------------------------------------------------------------
# get_kb_content_link
# ---------------------------------------------------------------------------


def test_get_kb_content_link_found_and_missing(dbm):
    _make_ks(dbm, ks_id="ks-one")
    _seed_library_item(dbm)
    dbm.register_kb_content_link("ks-one", "lib-1", "item-1", 1, 10)
    row = dbm.get_kb_content_link("ks-one", "item-1")
    assert row["knowledge_store_id"] == "ks-one"
    assert dbm.get_kb_content_link("ks-one", "nope") is None


def test_get_kb_content_link_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_kb_content_link("ks", "item") is None


def test_get_kb_content_link_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_kb_content_link("ks", "item") is None


# ---------------------------------------------------------------------------
# get_kb_content_links_for_item
# ---------------------------------------------------------------------------


def test_get_links_for_item(dbm):
    _make_ks(dbm, ks_id="ks-fi", name="KS FI")
    _seed_library_item(dbm)
    dbm.register_kb_content_link("ks-fi", "lib-1", "item-1", 1, 10)
    rows = dbm.get_kb_content_links_for_item("item-1")
    assert len(rows) == 1
    assert rows[0]["knowledge_store_name"] == "KS FI"


def test_get_links_for_item_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_kb_content_links_for_item("item") == []


def test_get_links_for_item_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_kb_content_links_for_item("item") == []


# ---------------------------------------------------------------------------
# get_kb_content_links_for_library
# ---------------------------------------------------------------------------


def test_get_links_for_library(dbm):
    _make_ks(dbm, ks_id="ks-fl", name="KS FL")
    _seed_library_item(dbm)
    dbm.register_kb_content_link("ks-fl", "lib-1", "item-1", 1, 10)
    rows = dbm.get_kb_content_links_for_library("lib-1")
    assert len(rows) == 1
    assert rows[0]["knowledge_store_name"] == "KS FL"
    assert rows[0]["item_title"] == "Item Title"


def test_get_links_for_library_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_kb_content_links_for_library("lib") == []


def test_get_links_for_library_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_kb_content_links_for_library("lib") == []


# ---------------------------------------------------------------------------
# get_knowledge_stores_for_library
# ---------------------------------------------------------------------------


def test_get_knowledge_stores_for_library(dbm):
    _make_ks(dbm, ks_id="ks-gsl", name="KS GSL")
    _seed_library_item(dbm, lib_id="lib-2", item_id="item-2")
    _seed_library_item(dbm, lib_id="lib-2", item_id="item-3", title="Item Three")
    # two links: one ready, one failed -> exercises the count branches
    dbm.register_kb_content_link("ks-gsl", "lib-2", "item-2", 1, 10, status="ready")
    dbm.register_kb_content_link("ks-gsl", "lib-2", "item-3", 1, 10, status="failed")
    rows = dbm.get_knowledge_stores_for_library("lib-2")
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == "ks-gsl"
    assert r["is_shared"] is False
    assert r["item_count"] == 2
    assert r["ready_count"] == 1
    assert r["failed_count"] == 1


def test_get_knowledge_stores_for_library_no_links(dbm):
    # No links at all -> empty result (counts-None branch not triggered, but
    # the SUM/COUNT-None normalization path is covered when a GROUP has nulls).
    assert dbm.get_knowledge_stores_for_library("no-such-lib") == []


def test_get_knowledge_stores_for_library_null_counts(dbm):
    """A row whose count columns come back NULL hits the ``d[k] = 0`` branch.

    The real SQL can't produce NULL counts for a matched group, so a fake
    connection returns a crafted row to exercise that normalization line.
    """
    from contextlib import contextmanager

    class _FakeCursor:
        description = [
            ("id",), ("name",), ("description",), ("chunking_strategy",),
            ("embedding_vendor",), ("embedding_model",), ("vector_db_backend",),
            ("is_shared",), ("organization_id",), ("owner_user_id",),
            ("created_at",), ("updated_at",), ("item_count",),
            ("ready_count",), ("failed_count",),
        ]

        def execute(self, *a, **k):
            return self

        def fetchall(self):
            return [(
                "ks-x", "X", "", "simple", "openai", "m", "chromadb",
                1, 1, 10, 0, 0, None, None, None,
            )]

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def close(self):
            pass

    with patch.object(dbm, "get_connection", return_value=_FakeConn()):
        rows = dbm.get_knowledge_stores_for_library("lib-x")
    assert rows[0]["item_count"] == 0
    assert rows[0]["ready_count"] == 0
    assert rows[0]["failed_count"] == 0
    assert rows[0]["is_shared"] is True


def test_get_knowledge_stores_for_library_no_connection(dbm):
    with patch.object(dbm, "get_connection", return_value=None):
        assert dbm.get_knowledge_stores_for_library("lib") == []


def test_get_knowledge_stores_for_library_db_error(dbm):
    dbm.table_prefix = "nonexistent_"
    assert dbm.get_knowledge_stores_for_library("lib") == []
