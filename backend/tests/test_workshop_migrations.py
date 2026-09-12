"""
Tests for workshop database migrations (_migration_26, _migration_27).
"""

import sqlite3
from types import SimpleNamespace

from lamb.migrations import MigrationRunner, LATEST_VERSION


class _FakeDb:
    """Minimal db_manager stand-in for direct migration runner calls."""
    def __init__(self):
        self.table_prefix = ""


def _migrate_schema():
    """Apply migrations 26 and 27 against a fresh in-memory DB.

    Returns (conn, cursor). We set up the prerequisite tables (lti_activities,
    lti_activity_users) so FK references resolve.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()
    # Prerequisite tables for FK targets
    cursor.execute("""
        CREATE TABLE lti_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_link_id TEXT NOT NULL UNIQUE,
            organization_id INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE lti_activity_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_email TEXT NOT NULL
        )
    """)

    runner = MigrationRunner(_FakeDb())
    runner._migration_26(cursor)
    runner._migration_27(cursor)
    conn.commit()
    return conn


def _migrate_schema_idempotent():
    """Apply migrations twice to verify idempotency (no error/duplicates)."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE lti_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_link_id TEXT NOT NULL UNIQUE,
            organization_id INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE lti_activity_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_email TEXT NOT NULL
        )
    """)
    runner = MigrationRunner(_FakeDb())
    runner._migration_26(cursor)
    runner._migration_26(cursor)  # run again — must be a no-op
    runner._migration_27(cursor)
    runner._migration_27(cursor)  # run again — must be a no-op
    conn.commit()
    return conn


def test_latest_version_incremented():
    """LATEST_VERSION covers the workshop migrations."""
    assert LATEST_VERSION >= 27


def test_mg1_activity_type_column():
    """MG1: lti_activities.activity_type exists, default 'chat'."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(lti_activities)")]
    assert "activity_type" in columns

    # Default value is 'chat'
    cursor.execute("""
        INSERT INTO lti_activities (resource_link_id, organization_id)
        VALUES ('rl_1', 1)
    """)
    cursor.execute("""
        SELECT activity_type FROM lti_activities WHERE resource_link_id = 'rl_1'
    """)
    (value,) = cursor.fetchone()
    assert value == "chat"
    conn.close()


def test_mg2_workshop_sessions_table():
    """MG2: lti_workshop_sessions table exists with expected columns."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(lti_workshop_sessions)")]
    for col in ["id", "activity_id", "activity_user_id", "owi_user_id",
                "assistant_id", "build_state", "saved_chat", "reflection",
                "status", "created_at", "updated_at"]:
        assert col in columns, f"Missing column: {col}"
    conn.close()


def test_migration_idempotency():
    """Rerunning migrations produces no error and single schema."""
    conn = _migrate_schema_idempotent()
    cursor = conn.cursor()
    assert "activity_type" in [row[1] for row in cursor.execute("PRAGMA table_info(lti_activities)")]
    assert "lti_workshop_sessions" in [
        row[0] for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
    ]
    conn.close()
