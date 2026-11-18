"""Grade delivery must leave the shared SQLite writer available between results."""
import sqlite3
from types import SimpleNamespace

import pytest

from lamb import database_manager, lti_activity_manager
from lamb.lti13 import grades
from lamb.modules.file_evaluation.lti_passback import LTIGradePassback


@pytest.fixture(params=["lti11", "lti13"])
def delivery(tmp_path, monkeypatch, request):
    path = tmp_path / "grades.db"

    def connect():
        return sqlite3.connect(path, timeout=0.1)

    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE T_lti_activities (
                id INTEGER PRIMARY KEY, resource_link_id TEXT,
                lis_outcome_service_url TEXT);
            CREATE TABLE mod_file_eval_submissions (id TEXT PRIMARY KEY);
            CREATE TABLE mod_file_eval_student_submissions (
                id TEXT PRIMARY KEY, file_submission_id TEXT, activity_id INTEGER,
                student_id TEXT, lis_result_sourcedid TEXT,
                sent_to_moodle INTEGER DEFAULT 0, sent_to_moodle_at INTEGER);
            CREATE TABLE mod_file_eval_grades (
                file_submission_id TEXT, score REAL, comment TEXT);
            CREATE TABLE unrelated_settings (id INTEGER PRIMARY KEY, value INTEGER);
            INSERT INTO unrelated_settings VALUES (1, 0);
        """)
        resource = "lti13_test_activity" if request.param == "lti13" else "activity"
        conn.execute("INSERT INTO T_lti_activities VALUES (1, ?, ?)",
                     (resource, "https://moodle.example.test/outcomes"))
        for n in range(3):
            conn.execute("INSERT INTO mod_file_eval_submissions VALUES (?)", (f"file-{n}",))
            conn.execute("""INSERT INTO mod_file_eval_student_submissions
                (id, file_submission_id, activity_id, student_id, lis_result_sourcedid)
                VALUES (?, ?, 1, ?, ?)""",
                (f"submission-{n}", f"file-{n}", f"student-{n}", f"target-{n}"))
            conn.execute("INSERT INTO mod_file_eval_grades VALUES (?, 8, 'Reviewed')",
                         (f"file-{n}",))
        conn.commit()
    finally:
        conn.close()

    db = SimpleNamespace(table_prefix="T_", get_connection=connect)
    monkeypatch.setattr(database_manager, "LambDatabaseManager", lambda: db)
    monkeypatch.setattr(lti_activity_manager, "LtiActivityManager",
                        lambda: SimpleNamespace(get_lti_credentials=lambda: ("key", "secret")))

    def transport(callback):
        if request.param == "lti13":
            monkeypatch.setattr(grades, "send_score",
                                lambda resource, student, score, comment: callback(student))
        else:
            monkeypatch.setattr(LTIGradePassback, "send_grade_to_moodle",
                                lambda **kw: callback(kw["lis_result_sourcedid"].replace("target-", "student-")))

    def flags():
        c = connect()
        try:
            return dict(c.execute("SELECT student_id, sent_to_moodle FROM mod_file_eval_student_submissions"))
        finally:
            c.close()

    return SimpleNamespace(connect=connect, transport=transport, flags=flags)


def test_unrelated_writes_and_completed_results_are_available_during_delivery(delivery):
    completed = []

    def send(student):
        # A separate connection writes another table while the LMS request is active.
        other = delivery.connect()
        try:
            with other:
                other.execute("UPDATE unrelated_settings SET value = value + 1 WHERE id = 1")
            saved = delivery.flags()
            assert all(saved[previous] == 1 for previous in completed)
        finally:
            other.close()
        completed.append(student)
        return {"success": True, "status_code": 200}

    delivery.transport(send)
    result = LTIGradePassback.send_activity_grades(1)
    assert result["success"] is True
    assert result["sent"] == 3 and result["failed"] == 0
    assert all(delivery.flags().values())


def test_partial_delivery_keeps_successes_and_reports_the_failed_student(delivery):
    attempted = []

    def send(student):
        attempted.append(student)
        if len(attempted) == 2:
            return {"success": False, "status_code": 503, "error_message": "LMS unavailable"}
        return {"success": True, "status_code": 200}

    delivery.transport(send)
    result = LTIGradePassback.send_activity_grades(1)
    assert result["success"] is False
    assert result["sent"] == 2 and result["failed"] == 1
    assert result["error"] == f"{attempted[1]}: LMS unavailable"
    assert delivery.flags() == {student: int(i != 1) for i, student in enumerate(attempted)}
    assert [r["success"] for r in result["results"]] == [True, False, True]


def test_later_interruption_does_not_lose_a_successful_delivery_record(delivery):
    attempted = []

    def send(student):
        attempted.append(student)
        if len(attempted) == 2:
            raise RuntimeError("Delivery interrupted")
        return {"success": True, "status_code": 200}

    delivery.transport(send)
    with pytest.raises(RuntimeError, match="Delivery interrupted"):
        LTIGradePassback.send_activity_grades(1)
    saved = delivery.flags()
    assert saved[attempted[0]] == 1
    assert sum(saved.values()) == 1


def test_failed_status_write_releases_the_lock_and_keeps_earlier_results(delivery):
    attempted = []

    def send(student):
        attempted.append(student)
        if len(attempted) == 2:
            other = delivery.connect()
            try:
                other.execute("""CREATE TRIGGER reject_status BEFORE UPDATE
                    ON mod_file_eval_student_submissions
                    BEGIN SELECT RAISE(ABORT, 'Cannot save status'); END""")
            finally:
                other.close()
        return {"success": True, "status_code": 200}

    delivery.transport(send)
    with pytest.raises(sqlite3.IntegrityError, match="Cannot save status"):
        LTIGradePassback.send_activity_grades(1)
    assert delivery.flags()[attempted[0]] == 1
    other = delivery.connect()
    try:
        with other:
            other.execute("UPDATE unrelated_settings SET value = 99")
    finally:
        other.close()
