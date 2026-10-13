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
    runner._migration_28(cursor)
    runner._migration_29(cursor)
    runner._migration_30(cursor)
    runner._migration_31(cursor)
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
    runner._migration_28(cursor)
    runner._migration_28(cursor)  # run again — must be a no-op
    runner._migration_29(cursor)
    runner._migration_29(cursor)  # run again — must be a no-op
    runner._migration_30(cursor)
    runner._migration_30(cursor)  # run again — must be a no-op
    runner._migration_31(cursor)
    runner._migration_31(cursor)  # run again — must be a no-op
    conn.commit()
    return conn


def test_latest_version_incremented():
    """LATEST_VERSION covers the workshop migrations."""
    assert LATEST_VERSION >= 30


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


def test_mg3_session_kb_columns():
    """MG3: v28 adds KB/document binding columns to lti_workshop_sessions."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(lti_workshop_sessions)")]
    for col in ["kb_id", "document_file_id", "document_name", "document_status"]:
        assert col in columns, f"Missing column: {col}"
    conn.close()


def test_mg4_activity_rubric_column():
    """MG4: v29 adds an optional rubric_id to lti_activities."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(lti_activities)")]
    assert "rubric_id" in columns
    conn.close()


def test_mg5_evaluations_table():
    """MG5: v30 creates workshop_evaluations with the expected columns."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    columns = [
        row[1] for row in cursor.execute(
            "PRAGMA table_info(workshop_evaluations)")
    ]
    for col in ["id", "session_id", "activity_id", "rubric_id", "evaluator",
                "model_used", "status", "total_score", "max_score", "criteria",
                "overall_feedback", "raw_response", "error_message",
                "created_at", "updated_at"]:
        assert col in columns, f"Missing column: {col}"
    conn.close()


# ── v31: consent versioning + the teacher pilot gate (C13/C20) ────────────

def test_mg6_consent_version_column():
    """MG6: v31 records which consent notice a student accepted."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    columns = [
        row[1] for row in cursor.execute("PRAGMA table_info(lti_activity_users)")
    ]
    assert "consent_version" in columns
    conn.close()


def test_mg7_pilot_columns_and_defaults():
    """MG7: v31 marks pilot runs on both the session and the roster row."""
    conn = _migrate_schema()
    cursor = conn.cursor()

    assert "pilot_completed_at" in [
        row[1] for row in cursor.execute("PRAGMA table_info(lti_activities)")]
    assert "is_pilot" in [
        row[1] for row in cursor.execute(
            "PRAGMA table_info(lti_workshop_sessions)")]
    assert "is_pilot" in [
        row[1] for row in cursor.execute(
            "PRAGMA table_info(lti_activity_users)")]

    # Existing rows must keep behaving as "not a pilot".
    cursor.execute(
        "INSERT INTO lti_activity_users (activity_id, user_email) "
        "VALUES (1, 'a@x')")
    cursor.execute("SELECT is_pilot FROM lti_activity_users WHERE user_email='a@x'")
    assert cursor.fetchone()[0] == 0

    cursor.execute(
        "INSERT INTO lti_activities (resource_link_id, organization_id, "
        "activity_type) VALUES ('rl_mg7', 1, 'workshop')")
    cursor.execute(
        "SELECT pilot_completed_at FROM lti_activities "
        "WHERE resource_link_id='rl_mg7'")
    assert cursor.fetchone()[0] is None  # gate open until the pilot is done
    conn.close()


def test_mg8_workshop_pilot_index():
    """MG8: the org+type index the gate queries is created."""
    conn = _migrate_schema()
    cursor = conn.cursor()
    indexes = {
        row[0] for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "idx_lti_activities_workshop_pilot" in indexes
    conn.close()


def test_migration_idempotency_leaves_one_of_each_column():
    """Rerunning v31 must not fail on already-present columns."""
    conn = _migrate_schema_idempotent()
    cursor = conn.cursor()

    for table, column in (
        ("lti_activities", "pilot_completed_at"),
        ("lti_workshop_sessions", "is_pilot"),
        ("lti_activity_users", "is_pilot"),
        ("lti_activity_users", "consent_version"),
    ):
        columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})")]
        assert columns.count(column) == 1, f"{table}.{column} duplicated"
    conn.close()
