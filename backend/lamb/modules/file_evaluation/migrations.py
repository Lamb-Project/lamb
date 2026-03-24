"""
Database migrations for the file_evaluation module.

All statements use CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS
for idempotent execution on every startup.
"""

import sqlite3

from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")


def repair_file_eval_schema_if_needed(conn: sqlite3.Connection, table_prefix: str) -> None:
    """
    If ``mod_file_eval_*`` was created while ``LAMB_DB_PREFIX`` was empty, FKs reference
    ``lti_activities`` but the real table is ``{prefix}lti_activities``. SQLite then fails
    inserts with "no such table: main.lti_activities". Drop module tables so migrations
    recreate them with the correct FK (data in these tables is lost).
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='mod_file_eval_submissions'"
    ).fetchone()
    if not row or not row[0]:
        return
    ddl = row[0]
    if not table_prefix:
        return
    if f"REFERENCES {table_prefix}lti_activities(" in ddl:
        return
    if "REFERENCES lti_activities(" not in ddl:
        return
    logger.warning(
        "Recreating file_evaluation module tables: FKs referenced lti_activities but "
        "LAMB_DB_PREFIX=%r requires %slti_activities",
        table_prefix,
        table_prefix,
    )
    conn.execute("DROP TABLE IF EXISTS mod_file_eval_student_submissions")
    conn.execute("DROP TABLE IF EXISTS mod_file_eval_grades")
    conn.execute("DROP TABLE IF EXISTS mod_file_eval_submissions")


MIGRATION_SQL = [
    # ── File Submissions (one per individual or group upload) ──────────────
    """
    CREATE TABLE IF NOT EXISTS mod_file_eval_submissions (
        id              TEXT PRIMARY KEY,
        activity_id     INTEGER NOT NULL REFERENCES {table_prefix}lti_activities(id) ON DELETE CASCADE,
        file_name       TEXT NOT NULL,
        file_path       TEXT NOT NULL,
        file_size       INTEGER,
        file_type       TEXT,
        uploaded_by     TEXT NOT NULL,
        uploaded_at     INTEGER NOT NULL,
        group_code          TEXT,
        group_display_name  TEXT,
        max_group_members   INTEGER DEFAULT 1,
        student_note        TEXT,
        evaluation_status       TEXT,
        evaluation_started_at   INTEGER,
        evaluation_error        TEXT
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_mod_fe_sub_activity ON mod_file_eval_submissions(activity_id)",
    "CREATE INDEX IF NOT EXISTS idx_mod_fe_sub_eval_status ON mod_file_eval_submissions(evaluation_status)",
    "CREATE INDEX IF NOT EXISTS idx_mod_fe_sub_group_code ON mod_file_eval_submissions(group_code)",

    # ── Student Submissions (one per student – links student to a file submission) ─
    """
    CREATE TABLE IF NOT EXISTS mod_file_eval_student_submissions (
        id                      TEXT PRIMARY KEY,
        file_submission_id      TEXT NOT NULL REFERENCES mod_file_eval_submissions(id) ON DELETE CASCADE,
        student_id              TEXT NOT NULL,
        activity_id             INTEGER NOT NULL REFERENCES {table_prefix}lti_activities(id) ON DELETE CASCADE,
        lis_result_sourcedid    TEXT,
        joined_at               INTEGER NOT NULL,
        sent_to_moodle          INTEGER DEFAULT 0,
        sent_to_moodle_at       INTEGER,
        UNIQUE(student_id, activity_id)
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_mod_fe_ssub_file ON mod_file_eval_student_submissions(file_submission_id)",
    "CREATE INDEX IF NOT EXISTS idx_mod_fe_ssub_student ON mod_file_eval_student_submissions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_mod_fe_ssub_activity ON mod_file_eval_student_submissions(activity_id)",

    # ── Grades (one per file submission – dual AI + professor model) ───────
    """
    CREATE TABLE IF NOT EXISTS mod_file_eval_grades (
        id                  TEXT PRIMARY KEY,
        file_submission_id  TEXT NOT NULL UNIQUE REFERENCES mod_file_eval_submissions(id) ON DELETE CASCADE,
        ai_score            REAL,
        ai_comment          TEXT,
        ai_evaluated_at     INTEGER,
        score               REAL,
        comment             TEXT,
        created_at          INTEGER NOT NULL,
        updated_at          INTEGER
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_mod_fe_grade_file ON mod_file_eval_grades(file_submission_id)",
]
