"""Tests for the workshop teacher dashboard.

Covers tool-usage summarization, aggregate stats, per-student progress,
session detail, the instructor launch redirect, dashboard-token
authorization, and the JSON routes.
"""

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.database_manager import LambDatabaseManager
from lamb.modules.workshop import dashboard as dash
from lamb.modules.workshop import module as workshop_module


def _saved_chat(*tool_names):
    messages = [{"role": "user", "content": "hi"}]
    for name in tool_names:
        messages.append({
            "role": "assistant",
            "content": "",
            "hidden": True,
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": name, "arguments": "{}"},
            }],
        })
    return json.dumps(messages)


# ─────────────────────────────────────────────────────────────────────────────
# Tool usage
# ─────────────────────────────────────────────────────────────────────────────

class TestSummarizeToolUsage:
    def test_counts_tool_calls_by_name(self):
        chat = _saved_chat("calculator", "calculator", "kb_query")
        assert dash.summarize_tool_usage(chat) == {
            "calculator": 2, "kb_query": 1}

    def test_ignores_plain_messages(self):
        chat = json.dumps([
            {"role": "user", "content": "what is 2+2?"},
            {"role": "assistant", "content": "4"},
        ])
        assert dash.summarize_tool_usage(chat) == {}

    def test_tolerates_bad_input(self):
        assert dash.summarize_tool_usage("not json") == {}
        assert dash.summarize_tool_usage(None) == {}
        assert dash.summarize_tool_usage([]) == {}


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardStats:
    @patch.object(dash, "_db_manager")
    def test_counts_sessions_and_tools(self, mock_db):
        mock_db.get_activity_students.return_value = {"total": 4}
        mock_db.get_workshop_sessions_by_activity.return_value = [
            {"id": "s1", "status": "in_progress",
             "saved_chat": _saved_chat("calculator")},
            {"id": "s2", "status": "submitted",
             "saved_chat": _saved_chat("calculator", "kb_query"),
             "reflection": "hello"},
        ]
        mock_db.get_workshop_evaluations_by_activity.return_value = [
            {"session_id": "s2", "status": "completed"},
            {"session_id": "s2", "status": "failed"},
        ]

        stats = dash.workshop_dashboard_stats({"id": 1})

        assert stats["total_students"] == 4
        assert stats["in_progress"] == 1
        assert stats["submitted"] == 1
        # Evaluated counts distinct completed sessions, not rows.
        assert stats["evaluated"] == 1
        assert stats["tool_calls"] == {"calculator": 2, "kb_query": 1}
        assert stats["tool_calls_total"] == 3
        assert stats["avg_reflection_length"] == 5
        assert stats["teacher_pilot_required"] is False

    def test_missing_activity_id(self):
        assert "error" in dash.workshop_dashboard_stats({})


# ─────────────────────────────────────────────────────────────────────────────
# Students
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardStudents:
    @patch.object(dash, "_db_manager")
    def test_left_join_keeps_students_without_sessions(self, mock_db):
        mock_db.get_activity_students_with_sessions.return_value = [
            {
                "user_display_name": "Ada", "user_name": "ada",
                "user_email": "ada@x", "last_access_at": 123,
                "access_count": 2, "session_id": "s1",
                "session_status": "submitted", "session_assistant_id": 7,
                "session_saved_chat": _saved_chat("calculator"),
                "session_reflection": "Because reasons",
                "session_updated_at": 124,
            },
            {
                "user_display_name": "Bob", "user_name": "bob",
                "user_email": "bob@x", "session_id": None,
                "session_status": None, "session_saved_chat": None,
                "session_reflection": None,
            },
        ]
        mock_db.get_workshop_evaluations_by_activity.return_value = [
            {"session_id": "s1", "status": "completed"},
        ]

        students = dash.workshop_dashboard_students({"id": 1})

        assert len(students) == 2
        assert students[0]["session_status"] == "submitted"
        assert students[0]["tools_used"] == ["calculator"]
        assert students[0]["evaluation_status"] == "completed"
        # Bob never started a session but is still on the roster.
        assert students[1]["session_id"] is None
        assert students[1]["session_status"] == "not_started"
        assert students[1]["evaluation_status"] == "not_evaluated"


# ─────────────────────────────────────────────────────────────────────────────
# Session detail
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardSession:
    @patch.object(dash, "_db_manager")
    def test_detail_includes_transcript_and_evaluation(self, mock_db):
        mock_db.get_workshop_evaluation.return_value = {"status": "completed"}
        session = {
            "id": "s1", "activity_id": 1, "status": "submitted",
            "build_state": json.dumps({"instructions": "Be nice"}),
            "saved_chat": json.dumps([{"role": "user", "content": "hi"}]),
            "reflection": "ok",
        }

        detail = dash.workshop_dashboard_session(session)

        assert detail["build_state"]["instructions"] == "Be nice"
        assert detail["evaluation"]["status"] == "completed"
        assert "Student: hi" in detail["transcript"]


# ─────────────────────────────────────────────────────────────────────────────
# Instructor launch dispatch
# ─────────────────────────────────────────────────────────────────────────────

class TestInstructorLaunch:
    def test_redirect_to_workshop_dashboard(self):
        result = workshop_module.on_instructor_launch({
            "activity": {"id": 1, "resource_link_id": "rl-1"},
            "public_base": "http://lamb",
            "dashboard_token": "tok",
        })
        assert result["redirect"] == (
            "http://lamb/lamb/v1/lti/workshop/dashboard"
            "?resource_link_id=rl-1&token=tok"
        )
        assert result["type"] == "workshop_dashboard"

    @patch.object(dash, "_db_manager")
    def test_falls_back_to_stats_without_token(self, mock_db):
        mock_db.get_activity_students.return_value = {"total": 0}
        mock_db.get_workshop_sessions_by_activity.return_value = []
        mock_db.get_workshop_evaluations_by_activity.return_value = []

        result = workshop_module.on_instructor_launch({"id": 1})
        assert result["type"] == "workshop"


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard-token authorization
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardTokenAuth:
    def test_rejects_non_dashboard_token(self):
        from lamb import lti_router

        with patch("lamb.lti_router._validate_token",
                   return_value={"type": "setup"}):
            with pytest.raises(HTTPException) as exc:
                lti_router._require_dashboard_token("t", "rl")
        assert exc.value.status_code == 403

    def test_rejects_resource_link_mismatch(self):
        from lamb import lti_router

        with patch("lamb.lti_router._validate_token",
                   return_value={"type": "dashboard",
                                 "resource_link_id": "other"}):
            with pytest.raises(HTTPException) as exc:
                lti_router._require_dashboard_token("t", "rl")
        assert exc.value.status_code == 403

    def test_accepts_matching_dashboard_token(self):
        from lamb import lti_router

        with patch("lamb.lti_router._validate_token",
                   return_value={"type": "dashboard",
                                 "resource_link_id": "rl"}):
            data = lti_router._require_dashboard_token("t", "rl")
        assert data["type"] == "dashboard"


# ─────────────────────────────────────────────────────────────────────────────
# JSON routes
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardRoutes:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.dashboard.workshop_dashboard_stats",
           return_value={"total_students": 3, "type": "workshop"})
    @patch("lamb.lti_router._get_workshop_activity",
           return_value={"id": 1, "activity_type": "workshop"})
    @patch("lamb.lti_router._require_dashboard_token",
           return_value={"type": "dashboard"})
    async def test_stats_route(self, mock_auth, mock_activity, mock_stats):
        from lamb import lti_router

        resp = await lti_router.workshop_dashboard_stats_api(
            resource_link_id="rl", token="t")
        assert json.loads(resp.body)["total_students"] == 3

    @pytest.mark.asyncio
    @patch("lamb.lti_router.db_manager")
    @patch("lamb.lti_router._get_workshop_activity",
           return_value={"id": 1, "activity_type": "workshop"})
    @patch("lamb.lti_router._require_dashboard_token",
           return_value={"type": "dashboard"})
    async def test_session_detail_rejects_other_activity(
            self, mock_auth, mock_activity, mock_db):
        from lamb import lti_router

        mock_db.get_workshop_session_by_id.return_value = {
            "id": "s1", "activity_id": 99}
        with pytest.raises(HTTPException) as exc:
            await lti_router.workshop_dashboard_session_api(
                "s1", resource_link_id="rl", token="t")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.evaluation.evaluate_session",
           new_callable=AsyncMock)
    @patch("lamb.lti_router.db_manager")
    @patch("lamb.lti_router._get_workshop_activity",
           return_value={"id": 1, "activity_type": "workshop"})
    @patch("lamb.lti_router._require_dashboard_token",
           return_value={"type": "dashboard"})
    async def test_evaluate_route(self, mock_auth, mock_activity, mock_db,
                                  mock_eval):
        from lamb import lti_router

        mock_db.get_workshop_session_by_id.return_value = {
            "id": "s1", "activity_id": 1}
        mock_eval.return_value = {"configured": True, "status": "completed"}

        resp = await lti_router.workshop_dashboard_evaluate(
            "s1", resource_link_id="rl", token="t")

        assert json.loads(resp.body)["status"] == "completed"
        mock_eval.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────────
# DB accessors
# ─────────────────────────────────────────────────────────────────────────────

class _FakeDb:
    """Duck-typed db_manager: methods are called unbound with this as self."""

    table_prefix = ""

    def __init__(self, path):
        self._path = path

    def get_connection(self):
        return sqlite3.connect(self._path)


def _init_dashboard_db(path):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE lti_activity_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL DEFAULT '',
            user_display_name TEXT NOT NULL DEFAULT '',
            last_access_at INTEGER,
            access_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE lti_workshop_sessions (
            id TEXT PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            activity_user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress',
            assistant_id INTEGER,
            saved_chat TEXT,
            reflection TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    cursor.execute(
        "INSERT INTO lti_activity_users "
        "(activity_id, user_email, user_name, created_at) "
        "VALUES (1, 'a@x', 'ada', 1), (1, 'b@x', 'bob', 2), (2, 'c@x', 'cid', 3)")
    cursor.execute(
        "INSERT INTO lti_workshop_sessions "
        "(id, activity_id, activity_user_id, status, created_at, updated_at) "
        "VALUES ('s1', 1, 1, 'submitted', 1, 1)")
    conn.commit()
    conn.close()


class TestDashboardDb:
    def test_get_workshop_sessions_by_activity(self, tmp_path):
        db_path = str(tmp_path / "dash.db")
        _init_dashboard_db(db_path)

        rows = LambDatabaseManager.get_workshop_sessions_by_activity(
            _FakeDb(db_path), 1)
        assert [r["id"] for r in rows] == ["s1"]
        # A different activity has no sessions.
        assert LambDatabaseManager.get_workshop_sessions_by_activity(
            _FakeDb(db_path), 2) == []

    def test_get_activity_students_with_sessions(self, tmp_path):
        db_path = str(tmp_path / "dash2.db")
        _init_dashboard_db(db_path)

        rows = LambDatabaseManager.get_activity_students_with_sessions(
            _FakeDb(db_path), 1)
        by_email = {r["user_email"]: r for r in rows}

        assert set(by_email) == {"a@x", "b@x"}
        assert by_email["a@x"]["session_id"] == "s1"
        assert by_email["a@x"]["session_status"] == "submitted"
        # Bob has no session but is still returned (LEFT JOIN).
        assert by_email["b@x"]["session_id"] is None
