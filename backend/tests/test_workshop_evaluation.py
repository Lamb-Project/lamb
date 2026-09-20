"""Tests for workshop_formative_evaluation (AI Workshop formative feedback).

Covers transcript serialization, rubric-driven evaluation (LLM mocked — no real
calls), tolerant JSON parsing, graceful no-rubric / failure paths, and the
evaluation read/write DB methods.
"""

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.database_manager import LambDatabaseManager
from lamb.migrations import MigrationRunner
from lamb.modules.workshop import evaluation as ev
from lamb.modules.workshop import routers


def _token_payload(**overrides):
    payload = {
        "scope": "workshop_student",
        "session_id": "ws-1",
        "activity_id": 1,
        "email": "student@lamb-lti.local",
        "organization_id": 10,
    }
    payload.update(overrides)
    return payload


def _rubric_data():
    return {
        "rubricId": "rub-1",
        "title": "Assistant Design",
        "maxScore": 10,
        "criteria": [
            {
                "id": "c1",
                "name": "Clarity",
                "description": "Is the instruction clear?",
                "weight": 100,
                "levels": [
                    {"id": "l1", "score": 4, "label": "Excellent",
                     "description": "very clear"},
                    {"id": "l2", "score": 1, "label": "Poor",
                     "description": "unclear"},
                ],
            }
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Transcript serialization
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildTranscript:
    def _session(self):
        return {
            "id": "ws-1",
            "activity_id": 1,
            "build_state": json.dumps({
                "instructions": "Be a friendly tutor",
                "attachedFileMeta": {"name": "notes.pdf", "path": "file-1"},
                "kbCollection": "kb-123",
                "selectedTools": ["calculator", "kb_query"],
            }),
            "saved_chat": json.dumps([
                {"role": "user", "content": "What is (3+5)*2?"},
                {
                    "role": "assistant",
                    "content": "",
                    "hidden": True,
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": "{\"expression\": \"(3+5)*2\"}",
                        },
                    }],
                },
                {
                    "role": "tool",
                    "name": "calculator",
                    "tool_call_id": "call-1",
                    "content": "16",
                    "hidden": True,
                },
                {"role": "assistant", "content": "The answer is 16."},
                {"role": "assistant", "content": "scratch pad note", "hidden": True},
            ]),
            "reflection": "I learned the document grounds the answer.",
        }

    def test_covers_decisions_conversation_tools_reflection(self):
        text = ev.build_transcript(self._session())

        assert "Be a friendly tutor" in text
        assert "notes.pdf" in text
        assert "kb-123" in text
        assert "calculator" in text and "kb_query" in text

        assert "Student: What is (3+5)*2?" in text
        assert "[tool call: calculator" in text
        assert "[tool result (calculator)]: 16" in text
        assert "Assistant: The answer is 16." in text

        assert "I learned the document grounds the answer." in text

    def test_hidden_entries_not_rendered_but_tool_trace_kept(self):
        text = ev.build_transcript(self._session())
        # Hidden assistant text is plumbing — must not leak into the transcript.
        assert "scratch pad note" not in text
        # The hidden tool exchange, however, is the observable trace and is kept.
        assert "[tool call: calculator" in text
        assert "[tool result (calculator)]: 16" in text

    def test_tolerates_missing_fields(self):
        text = ev.build_transcript({"build_state": "{}", "saved_chat": "[]"})
        assert "BUILD DECISIONS" in text
        assert "STUDENT REFLECTION" in text


# ─────────────────────────────────────────────────────────────────────────────
# JSON parsing / normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestParseEvaluationJson:
    def test_strips_markdown_fence(self):
        raw = "```json\n{\"overall_feedback\": \"ok\"}\n```"
        assert ev.parse_evaluation_json(raw)["overall_feedback"] == "ok"

    def test_extracts_object_from_surrounding_prose(self):
        raw = "Here is the evaluation:\n{\"total_score\": 8}\nHope that helps!"
        assert ev.parse_evaluation_json(raw)["total_score"] == 8

    def test_bad_json_raises_value_error(self):
        with pytest.raises(ValueError):
            ev.parse_evaluation_json("this is not json")


class TestNormalizeEvaluation:
    def test_maps_alternate_keys(self):
        data = {
            "criterion_evaluations": [{
                "name": "Clarity",
                "level": "Excellent",
                "level_score": 4,
                "weight": 100,
                "justification": "clear and concise",
            }],
            "totalScore": 9.5,
            "maxScore": 10,
            "overallFeedback": "Nice work",
        }
        result = ev.normalize_evaluation(data, {})
        assert result["criteria"][0] == {
            "criterion": "Clarity",
            "level": "Excellent",
            "score": 4,
            "weight": 100,
            "feedback": "clear and concise",
        }
        assert result["total_score"] == 9.5
        assert result["max_score"] == 10
        assert result["overall_feedback"] == "Nice work"

    def test_falls_back_to_rubric_max_score(self):
        result = ev.normalize_evaluation({}, {"maxScore": 20})
        assert result["max_score"] == 20
        assert result["criteria"] == []


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_session
# ─────────────────────────────────────────────────────────────────────────────

def _session():
    return {
        "id": "ws-1",
        "activity_id": 1,
        "build_state": "{}",
        "saved_chat": json.dumps([{"role": "user", "content": "hi"}]),
        "reflection": "done",
    }


def _activity(rubric_id="rub-1"):
    return {
        "id": 1,
        "owner_email": "teacher@example.com",
        "rubric_id": rubric_id,
    }


def _llm_response(content):
    return {"model": "small-fast", "choices": [{"message": {"content": content}}]}


class TestEvaluateSession:
    @pytest.mark.asyncio
    async def test_no_rubric_skips_llm(self):
        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm:
            result = await ev.evaluate_session(_session(), {"id": 1}, None)
        assert result == {"configured": False}
        mock_rub.get_rubric_by_id.assert_not_called()
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_rubric_not_found_skips_llm(self):
        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm:
            mock_rub.get_rubric_by_id.return_value = None
            result = await ev.evaluate_session(_session(), _activity(), "rub-1")
        assert result["configured"] is False
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_persists_and_returns_criteria(self):
        llm_content = json.dumps({
            "criteria": [{
                "criterion": "Clarity",
                "level": "Excellent",
                "score": 4,
                "weight": 100,
                "feedback": "well done",
            }],
            "total_score": 10,
            "max_score": 10,
            "overall_feedback": "Great work",
        })
        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm, \
                patch.object(ev, "_db_manager") as mock_db:
            mock_rub.get_rubric_by_id.return_value = {
                "rubric_data": _rubric_data()}
            mock_llm.return_value = _llm_response(llm_content)

            result = await ev.evaluate_session(_session(), _activity(), None)

        assert result["configured"] is True
        assert result["status"] == "completed"
        assert result["criteria"][0]["criterion"] == "Clarity"
        assert result["overall_feedback"] == "Great work"
        assert result["total_score"] == 10.0
        mock_db.upsert_workshop_evaluation.assert_called_once()
        kwargs = mock_db.upsert_workshop_evaluation.call_args.kwargs
        assert kwargs["status"] == "completed"
        assert kwargs["rubric_id"] == "rub-1"

    @pytest.mark.asyncio
    async def test_malformed_json_marks_failed_keeps_raw(self):
        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm, \
                patch.object(ev, "_db_manager") as mock_db:
            mock_rub.get_rubric_by_id.return_value = {
                "rubric_data": _rubric_data()}
            mock_llm.return_value = _llm_response("oh no, not json")

            result = await ev.evaluate_session(_session(), _activity(), None)

        assert result["configured"] is True
        assert result["status"] == "failed"
        assert result["error_message"]
        kwargs = mock_db.upsert_workshop_evaluation.call_args.kwargs
        assert kwargs["status"] == "failed"
        assert kwargs["raw_response"] == "oh no, not json"

    @pytest.mark.asyncio
    async def test_llm_failure_marks_failed_without_raising(self):
        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm, \
                patch.object(ev, "_db_manager") as mock_db:
            mock_rub.get_rubric_by_id.return_value = {
                "rubric_data": _rubric_data()}
            mock_llm.side_effect = ValueError("small-fast-model not configured")

            result = await ev.evaluate_session(_session(), _activity(), None)

        assert result["configured"] is True
        assert result["status"] == "failed"
        assert "not configured" in result["error_message"]
        mock_db.upsert_workshop_evaluation.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# DB read/write
# ─────────────────────────────────────────────────────────────────────────────

class _FakeDb:
    """Duck-typed db_manager: methods are called unbound with this as self."""
    table_prefix = ""

    def __init__(self, path):
        self._path = path

    def get_connection(self):
        return sqlite3.connect(self._path)


def _init_eval_db(path):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE lti_workshop_sessions (
            id TEXT PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            activity_user_id INTEGER NOT NULL
        )
    """)
    runner = MigrationRunner(type("_F", (), {"table_prefix": ""})())
    runner._migration_30(cursor)
    conn.commit()
    conn.close()


class TestEvaluationDb:
    def test_upsert_and_get_roundtrip(self, tmp_path):
        db_path = str(tmp_path / "eval.db")
        _init_eval_db(db_path)
        fake = _FakeDb(db_path)

        LambDatabaseManager.upsert_workshop_evaluation(
            fake,
            session_id="ws-1",
            activity_id=1,
            rubric_id="rub-1",
            criteria=[{"criterion": "Clarity", "score": 4}],
            overall_feedback="Good",
            total_score=8.0,
            max_score=10.0,
        )
        row = LambDatabaseManager.get_workshop_evaluation(fake, "ws-1")
        assert row["overall_feedback"] == "Good"
        assert row["criteria"] == [{"criterion": "Clarity", "score": 4}]
        assert row["total_score"] == 8.0
        assert row["status"] == "completed"

        # Re-evaluating overwrites the single row (one evaluation per session).
        LambDatabaseManager.upsert_workshop_evaluation(
            fake, session_id="ws-1", activity_id=1,
            overall_feedback="Second pass", status="completed")
        rows = LambDatabaseManager.get_workshop_evaluations_by_activity(fake, 1)
        assert len(rows) == 1
        assert rows[0]["overall_feedback"] == "Second pass"

    def test_get_missing_returns_none(self, tmp_path):
        db_path = str(tmp_path / "eval2.db")
        _init_eval_db(db_path)
        assert LambDatabaseManager.get_workshop_evaluation(
            _FakeDb(db_path), "nope") is None


# ─────────────────────────────────────────────────────────────────────────────
# Routes — authorization + wiring
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateRoute:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.evaluation.evaluate_session",
           new_callable=AsyncMock)
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_evaluate_success(self, mock_db, mock_decode, mock_eval):
        mock_decode.return_value = _token_payload(session_id="ws-1")
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1}
        mock_db.get_lti_activity_by_id.return_value = {"id": 1, "rubric_id": "r"}
        mock_eval.return_value = {"configured": True, "status": "completed"}

        result = await routers.evaluate_workshop_session("ws-1", {}, "tok")
        assert result["configured"] is True
        mock_eval.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_evaluate_session_mismatch_403(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-other")
        with pytest.raises(HTTPException) as exc:
            await routers.evaluate_workshop_session("ws-1", {}, "tok")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_evaluate_missing_session_404(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1")
        mock_db.get_workshop_session_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await routers.evaluate_workshop_session("ws-1", {}, "tok")
        assert exc.value.status_code == 404


class TestGetEvaluationRoute:
    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_restores_stored_evaluation(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1")
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1}
        mock_db.get_lti_activity_by_id.return_value = {"id": 1, "rubric_id": "r"}
        mock_db.get_workshop_evaluation.return_value = {
            "session_id": "ws-1", "overall_feedback": "Good"}

        result = await routers.get_workshop_evaluation("ws-1", "tok")
        assert result["configured"] is True
        assert result["evaluation"]["overall_feedback"] == "Good"

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_no_rubric_no_evaluation_reports_unconfigured(
            self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1")
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1}
        mock_db.get_lti_activity_by_id.return_value = {"id": 1}
        mock_db.get_workshop_evaluation.return_value = None

        result = await routers.get_workshop_evaluation("ws-1", "tok")
        assert result == {"configured": False, "evaluation": None}