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


class TestTranscriptStructuredReflection:
    """D5/D2/D3: the transcript carries the design answers and observations."""

    @staticmethod
    def _session(build_state, reflection=None):
        return {
            "id": "ws-1",
            "activity_id": 1,
            "saved_chat": json.dumps([
                {"role": "user", "content": "What is a fraction?"},
                {"role": "assistant", "content": "Equal parts of a whole."},
            ]),
            "reflection": reflection if reflection is not None else (
                "### What did you ask your assistant to do, and why?\n"
                "Explain fractions."),
            "build_state": json.dumps(build_state),
        }

    def test_design_questions_are_labelled(self):
        transcript = ev.build_transcript(self._session({
            "instructions": "Explain fractions",
            "reflectionAnswers": {
                "q1": "Explain fractions simply.",
                "q2": "It received 45 chunks of my notes.",
                "q3": "I would add worked examples.",
            },
        }))

        assert "=== DESIGN QUESTIONS ===" in transcript
        for _key, heading in ev.DESIGN_QUESTIONS:
            assert heading in transcript
        assert "A: Explain fractions simply." in transcript
        assert "A: It received 45 chunks of my notes." in transcript
        assert "A: I would add worked examples." in transcript

    def test_legacy_submission_says_so_instead_of_duplicating(self):
        transcript = ev.build_transcript(self._session(
            {"instructions": "Explain fractions"},
            reflection="Free text from before the guided questions."))

        assert "=== STUDENT REFLECTION ===" in transcript
        assert "Free text from before the guided questions." in transcript
        assert "predates the guided reflection" in transcript

    def test_partially_answered_questions_keep_their_slots(self):
        transcript = ev.build_transcript(self._session({
            "reflectionAnswers": {"q1": "only the first"},
        }))
        assert "A: only the first" in transcript
        assert "(not answered)" in transcript

    def test_document_chunking_facts_are_included(self):
        transcript = ev.build_transcript(self._session({
            "observations": [{
                "step": 2,
                "kind": "document",
                "data": {"files": [{
                    "original_filename": "notes.md",
                    "document_count": 45,
                    "status": "completed",
                    "plugin_params": {"chunk_size": 1000, "chunk_overlap": 200},
                }]},
            }],
        }))

        assert "=== OBSERVABILITY SNAPSHOTS ===" in transcript
        assert "notes.md → 45 chunk(s)" in transcript
        assert "chunk_size=1000" in transcript
        assert "overlap=200" in transcript

    def test_retrieval_probes_are_included(self):
        transcript = ev.build_transcript(self._session({
            "observations": [{
                "step": 3,
                "kind": "probe",
                "data": {"query": "what is a fraction", "count": 3, "results": []},
            }],
        }))
        assert "Retrieval probe" in transcript
        assert "3 excerpt(s)" in transcript

    def test_ab_history_records_the_rag_mode_per_turn(self):
        transcript = ev.build_transcript(self._session({
            "obsHistory": [
                {"turn": 1, "ragMode": "on", "question": "What is a fraction?",
                 "sources": [{}, {}], "answer": "Equal parts of a whole."},
                {"turn": 2, "ragMode": "off", "question": "What is a fraction?",
                 "sources": [], "answer": "I don't know."},
            ],
        }))

        assert "[knowledge base ON]" in transcript
        assert "[knowledge base OFF]" in transcript
        assert "excerpts sent: 2" in transcript
        assert "excerpts sent: 0" in transcript

    def test_missing_observations_state_it_explicitly(self):
        transcript = ev.build_transcript(self._session({"instructions": "x"}))
        assert "(no build-time observations recorded)" in transcript
        assert "did not run the knowledge-base comparison" in transcript

    def test_snapshot_list_is_limited(self):
        """A long lesson must not bury the rubric in raw frames."""
        history = [
            {"turn": i, "ragMode": "on" if i % 2 else "off",
             "question": f"question {i}", "sources": [], "answer": f"answer {i}"}
            for i in range(1, 21)
        ]
        transcript = ev.build_transcript(self._session({"obsHistory": history}))

        assert transcript.count("[knowledge base") == ev.MAX_TRANSCRIPT_SNAPSHOTS
        # The most recent turns are the ones kept.
        assert "answer 20" in transcript
        assert "answer 1 |" not in transcript

    def test_legacy_transcript_shape_is_unchanged(self):
        """Regression: the original sections still lead the transcript."""
        transcript = ev.build_transcript(self._session({"instructions": "Teach"}))
        assert transcript.startswith("=== BUILD DECISIONS ===")
        assert "=== CONVERSATION ===" in transcript
        assert "=== STUDENT REFLECTION ===" in transcript


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
# Truncated / malformed LLM output (observed in the wild)
# ─────────────────────────────────────────────────────────────────────────────

# Verbatim shape of a real response from a small local model: every criterion
# and both scores are there, but generation stopped inside `overall_feedback`
# (the closing quote and both braces are missing). The old parser sliced from
# the first `{` to the *last* `}`, which turned this into
# "Expecting ',' delimiter" and threw the whole evaluation away.
TRUNCATED_RESPONSE = """{
  "criteria": [
    {
      "criterion": "Design Decisions",
      "level": "Proficient",
      "score": 3,
      "weight": 30,
      "feedback": "The assistant demonstrates a clear understanding of the attached notes."
    },
    {
      "criterion": "Conversational Flow",
      "level": "Beginning",
      "score": 1,
      "weight": 40,
      "feedback": "The student could improve the conversational flow by providing more context."
    },
    {
      "criterion": "Tool Awareness",
      "level": "Proficient",
      "score": 3,
      "weight": 30,
      "feedback": "The student demonstrates a good understanding of when to use the calculator."
    }
  ],
  "total_score": 6,
  "max_score": 12,
  "overall_feedback": "The assistant demonstrates a solid understanding of the attached notes. However, there is room for improvement in terms of conversational flow and tool awareness."""


class TestTruncatedEvaluationJson:
    """A cut-off response must not cost the student their whole evaluation."""

    def test_recovers_every_criterion_and_the_score(self):
        data, note = ev.parse_evaluation_json_detailed(TRUNCATED_RESPONSE)

        assert len(data["criteria"]) == 3
        assert data["total_score"] == 6
        assert data["max_score"] == 12
        assert "[knowledge" not in data["overall_feedback"]  # sanity
        # The caller is told the payload was repaired, so it can say so.
        assert note and "cut off" in note

    def test_marks_the_clipped_sentence_rather_than_faking_a_full_stop(self):
        data, _note = ev.parse_evaluation_json_detailed(TRUNCATED_RESPONSE)
        assert data["overall_feedback"].endswith("…")
        assert "tool awareness" in data["overall_feedback"].lower()

    def test_missing_only_the_envelope_brace_is_repaired(self):
        payload = '{"criteria": [], "total_score": 3, "max_score": 10'
        data, note = ev.parse_evaluation_json_detailed(payload)
        assert data["total_score"] == 3
        assert note is not None

    def test_trailing_comma_is_tolerated(self):
        payload = '{"criteria": [{"criterion": "A", "score": 2,},], "total_score": 2,}'
        data, _note = ev.parse_evaluation_json_detailed(payload)
        assert data["criteria"][0]["criterion"] == "A"

    def test_truncated_inside_a_string_recovers_the_earlier_fields(self):
        payload = ('{"criteria": [{"criterion": "A", "level": "Good", '
                   '"score": 3, "weight": 50, "feedback": "It works becau')
        data, note = ev.parse_evaluation_json_detailed(payload)
        assert data["criteria"][0]["criterion"] == "A"
        assert data["criteria"][0]["feedback"].endswith("…")
        assert note is not None

    def test_a_clean_response_is_untouched_and_unflagged(self):
        clean = json.dumps({
            "criteria": [{"criterion": "A", "score": 3}],
            "total_score": 3, "max_score": 4, "overall_feedback": "Good.",
        })
        data, note = ev.parse_evaluation_json_detailed(clean)
        assert note is None
        assert data["overall_feedback"] == "Good."

    def test_fences_and_prose_around_the_object_still_parse(self):
        payload = f"Here is the evaluation:\n```json\n{TRUNCATED_RESPONSE}\n```\nHope it helps!"
        data, _note = ev.parse_evaluation_json_detailed(payload)
        assert len(data["criteria"]) == 3

    def test_prose_after_a_complete_object_is_ignored(self):
        payload = '{"total_score": 5, "max_score": 10}\n\nLet me know if you need more detail.'
        data, note = ev.parse_evaluation_json_detailed(payload)
        assert data["total_score"] == 5
        assert note is None

    def test_unrecoverable_output_still_raises(self):
        with pytest.raises(ValueError) as exc:
            ev.parse_evaluation_json_detailed("I could not evaluate this work.")
        assert "JSON" in str(exc.value)

    def test_empty_output_raises(self):
        with pytest.raises(ValueError):
            ev.parse_evaluation_json_detailed("")

    def test_public_parser_keeps_its_contract(self):
        """Regression: parse_evaluation_json still returns a plain dict."""
        assert isinstance(ev.parse_evaluation_json(TRUNCATED_RESPONSE), dict)


class TestClampForPrompt:
    """The prompt budget guard (the rubric alone is ~5 000 characters)."""

    def test_short_transcripts_pass_through_untouched(self):
        text = "=== BUILD DECISIONS ===\nshort"
        assert ev.clamp_for_prompt(text) == text

    def test_long_transcripts_keep_both_ends_and_say_so(self):
        head = "HEAD-MARKER " + ("a" * 4000)
        tail = ("b" * 4000) + " TAIL-MARKER"
        clamped = ev.clamp_for_prompt(head + tail, 1000)

        assert len(clamped) <= 1000
        assert clamped.startswith("HEAD-MARKER")
        assert clamped.endswith("TAIL-MARKER")
        assert "shortened for length" in clamped

    def test_a_zero_budget_disables_clamping(self):
        text = "x" * 100
        assert ev.clamp_for_prompt(text, 0) == text

    def test_the_directive_asks_for_concise_feedback(self):
        """Headroom depends on the answer staying short (see 9.1 numbers)."""
        assert "two short sentences" in ev._JSON_OUTPUT_DIRECTIVE


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
    async def test_truncated_response_still_produces_feedback(self):
        """The real-world failure mode: generation cut short inside the tail.

        Marking this `failed` threw away three complete criteria and the score,
        so the student saw "feedback could not be generated" for an evaluation
        the model had in fact produced.
        """
        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm, \
                patch.object(ev, "_db_manager") as mock_db:
            mock_rub.get_rubric_by_id.return_value = {
                "rubric_data": _rubric_data()}
            mock_llm.return_value = _llm_response(TRUNCATED_RESPONSE)

            result = await ev.evaluate_session(_session(), _activity(), None)

        assert result["status"] == "completed"
        assert len(result["criteria"]) == 3
        assert result["total_score"] == 6.0
        # …but the truncation is disclosed, not silently swallowed.
        assert "cut off" in (result["error_message"] or "")

        kwargs = mock_db.upsert_workshop_evaluation.call_args.kwargs
        assert kwargs["status"] == "completed"
        assert kwargs["raw_response"] == TRUNCATED_RESPONSE
        assert "cut off" in (kwargs["error_message"] or "")

    @pytest.mark.asyncio
    async def test_prompt_transcript_is_bounded_but_the_model_sees_a_marker(self):
        long_chat = json.dumps([
            {"role": "user", "content": "question " * 400},
            {"role": "assistant", "content": "answer " * 400},
        ])
        session = dict(_session(), saved_chat=long_chat)

        with patch.object(ev, "_rubric_db") as mock_rub, \
                patch.object(ev, "invoke_small_fast_model",
                             new_callable=AsyncMock) as mock_llm, \
                patch.object(ev, "_db_manager"):
            mock_rub.get_rubric_by_id.return_value = {
                "rubric_data": _rubric_data()}
            mock_llm.return_value = _llm_response(
                '{"criteria": [], "total_score": 0, "max_score": 1}')

            await ev.evaluate_session(session, _activity(), None)

        sent = mock_llm.call_args.kwargs["messages"][1]["content"]
        assert len(sent) <= ev.MAX_EVALUATION_TRANSCRIPT_CHARS
        assert "shortened for length" in sent

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
