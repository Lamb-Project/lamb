"""D4 tests — the teacher-first pilot gate (decision C13).

The gate exists to land "train the teacher first" without hijacking a class
that is already running. Three limits are load-bearing and pinned here:

* granularity is **per teacher** (owner), so a colleague's pilot does not
  unblock a teacher who has never run it;
* an activity with submitted work is **exempt** — a gate switched on mid-course
  must never lock students out of a lesson in progress;
* students are *informed*, teachers are *guided*, and the owner's
  ``?skip_pilot=1`` escape hatch leaves an audit trail.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.modules.workshop import dashboard, service


def _activity(**overrides):
    activity = {
        "id": 1,
        "activity_type": "workshop",
        "status": "active",
        "activity_name": "Fractions workshop",
        "owner_email": "teacher@school.edu",
        "organization_id": 10,
        "resource_link_id": "rl-1",
    }
    activity.update(overrides)
    return activity


class TestPilotBlocking:
    """`is_teacher_pilot_blocking` — flag + per-owner + not-running."""

    def _patch_flag(self, enabled=True):
        return patch.object(
            dashboard, "is_teacher_pilot_required", return_value=enabled)

    def test_flag_off_never_blocks(self):
        with self._patch_flag(False):
            assert dashboard.is_teacher_pilot_blocking(_activity()) is False

    def test_owner_without_pilot_is_blocked(self):
        with self._patch_flag(), patch.object(dashboard, "_db_manager") as db:
            db.has_submitted_sessions.return_value = False
            db.has_completed_workshop_pilot.return_value = False
            assert dashboard.is_teacher_pilot_blocking(_activity()) is True
            # Per-owner granularity: the query is scoped to this owner + org.
            db.has_completed_workshop_pilot.assert_called_once_with(
                "teacher@school.edu", 10)

    def test_owner_with_a_completed_pilot_is_not_blocked(self):
        with self._patch_flag(), patch.object(dashboard, "_db_manager") as db:
            db.has_submitted_sessions.return_value = False
            db.has_completed_workshop_pilot.return_value = True
            assert dashboard.is_teacher_pilot_blocking(_activity()) is False

    def test_another_teachers_pilot_does_not_unblock_this_one(self):
        """Per-owner: the gate is about *this* teacher's readiness."""
        with self._patch_flag(), patch.object(dashboard, "_db_manager") as db:
            db.has_submitted_sessions.return_value = False
            # The DB answers per-owner; a different owner simply returns False.
            db.has_completed_workshop_pilot.return_value = False
            assert dashboard.is_teacher_pilot_blocking(
                _activity(owner_email="new-teacher@school.edu")) is True

    def test_running_activity_is_exempt(self):
        with self._patch_flag(), patch.object(dashboard, "_db_manager") as db:
            db.has_submitted_sessions.return_value = True
            db.has_completed_workshop_pilot.return_value = False
            assert dashboard.is_teacher_pilot_blocking(_activity()) is False
            # Never even asks about the pilot once work has been submitted.
            db.has_completed_workshop_pilot.assert_not_called()

    def test_lookup_failure_does_not_lock_students_out(self):
        with self._patch_flag(), patch.object(dashboard, "_db_manager") as db:
            db.has_submitted_sessions.side_effect = RuntimeError("db down")
            assert dashboard.is_teacher_pilot_blocking(_activity()) is False

    def test_missing_owner_is_not_blocking(self):
        with self._patch_flag(), patch.object(dashboard, "_db_manager"):
            assert dashboard.is_teacher_pilot_blocking(
                {"id": 1, "activity_type": "workshop"}) is False


class TestPilotWorkspace:
    """`initialize_workshop_workspace(pilot=True)` marks both rows."""

    def _ctx(self):
        return {
            "activity": _activity(),
            "username": "teacher",
            "display_name": "Teacher Name",
            "lms_user_id": "lms-1",
            "public_base": "https://lamb.example",
            "locale": "es",
        }

    @patch("lamb.modules.workshop.service._create_workshop_token",
           return_value="tok")
    @patch("lamb.modules.workshop.service._db_manager")
    @patch("lamb.modules.workshop.service.LtiActivityManager")
    def test_pilot_marks_session_and_roster_row(
            self, mock_manager_cls, mock_db, mock_token):
        manager = mock_manager_cls.return_value
        manager.handle_student_launch.return_value = "owi-token"
        manager.generate_student_email.return_value = "teacher@lamb-lti.local"
        mock_db.get_activity_user.return_value = {
            "id": 5, "owi_user_id": "owi-5", "consent_given_at": None}
        mock_db.get_or_create_workshop_session.return_value = {
            "id": "ws-1", "is_pilot": 1}

        result = service.initialize_workshop_workspace(self._ctx(), pilot=True)

        # The session is created in pilot mode…
        assert mock_db.get_or_create_workshop_session.call_args.kwargs["is_pilot"] is True
        # …and the roster row is flagged, because total_students counts it.
        mock_db.mark_activity_user_pilot.assert_called_once_with(
            1, "teacher@lamb-lti.local", True)
        assert result["is_pilot"] is True
        # The teacher configured the disclosure; they are not asked to accept it.
        assert result["redirect"].startswith("https://lamb.example/m/workshop/1")

    @patch("lamb.modules.workshop.service._create_workshop_token",
           return_value="tok")
    @patch("lamb.modules.workshop.service._db_manager")
    @patch("lamb.modules.workshop.service.LtiActivityManager")
    def test_student_launch_is_unchanged(
            self, mock_manager_cls, mock_db, mock_token):
        manager = mock_manager_cls.return_value
        manager.handle_student_launch.return_value = "owi-token"
        manager.generate_student_email.return_value = "s@lamb-lti.local"
        mock_db.get_activity_user.return_value = {
            "id": 6, "owi_user_id": "owi-6", "consent_given_at": 123}
        mock_db.get_or_create_workshop_session.return_value = {
            "id": "ws-2", "is_pilot": 0}

        result = service.initialize_workshop_workspace(self._ctx())

        assert mock_db.get_or_create_workshop_session.call_args.kwargs["is_pilot"] is False
        mock_db.mark_activity_user_pilot.assert_not_called()
        assert result["is_pilot"] is False

    @patch("lamb.modules.workshop.service._create_workshop_token",
           return_value="tok")
    @patch("lamb.modules.workshop.service._db_manager")
    @patch("lamb.modules.workshop.service.LtiActivityManager")
    def test_pilot_still_carries_the_lms_locale(
            self, mock_manager_cls, mock_db, mock_token):
        manager = mock_manager_cls.return_value
        manager.handle_student_launch.return_value = "owi-token"
        manager.generate_student_email.return_value = "teacher@lamb-lti.local"
        mock_db.get_activity_user.return_value = {
            "id": 5, "owi_user_id": "owi-5", "consent_given_at": None}
        mock_db.get_or_create_workshop_session.return_value = {"id": "ws-1"}

        result = service.initialize_workshop_workspace(self._ctx(), pilot=True)
        assert "lang=es" in result["redirect"]


class TestPilotCompletion:
    """Submitting the pilot opens the activity for students."""

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_pilot_submit_marks_completion(self, mock_db, mock_decode):
        mock_decode.return_value = {
            "scope": "workshop_student", "session_id": "ws-1",
            "activity_id": 1, "email": "teacher@lamb-lti.local",
        }
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1, "is_pilot": 1}

        from lamb.modules.workshop import routers

        result = await routers.submit_workshop(
            session_id="ws-1", body={"saved_chat": "[]"}, token="tok")

        assert result["pilot_completed"] is True
        mock_db.mark_workshop_pilot_completed.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_student_submit_does_not_touch_the_pilot_flag(
            self, mock_db, mock_decode):
        mock_decode.return_value = {
            "scope": "workshop_student", "session_id": "ws-2",
            "activity_id": 1, "email": "student@lamb-lti.local",
        }
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-2", "activity_id": 1, "is_pilot": 0}

        from lamb.modules.workshop import routers

        result = await routers.submit_workshop(
            session_id="ws-2", body={"saved_chat": "[]"}, token="tok")

        assert "pilot_completed" not in result
        mock_db.mark_workshop_pilot_completed.assert_not_called()


class TestDashboardExcludesPilot:
    """A pilot must not be counted as a student anywhere."""

    def test_roster_count_excludes_pilot_rows(self):
        with patch.object(dashboard, "_db_manager") as db, \
             patch.object(dashboard, "is_teacher_pilot_required",
                          return_value=False), \
             patch.object(dashboard, "pending_reconsent_count", return_value=0), \
             patch.object(dashboard, "expiring_soon_count", return_value=0), \
             patch.object(dashboard, "retention_warning", return_value=False), \
             patch.object(dashboard, "_retention_days", return_value=None):
            db.get_activity_students.return_value = {"total": 3}
            db.get_workshop_sessions_by_activity.return_value = [
                {"id": "ws-1", "status": "submitted", "is_pilot": 1},
                {"id": "ws-2", "status": "submitted"},
            ]
            db.get_workshop_evaluations_by_activity.return_value = []

            stats = dashboard.workshop_dashboard_stats(_activity())

        assert db.get_activity_students.call_args.kwargs["include_pilot"] is False
        # The pilot session is not counted as a submission either.
        assert stats["submitted"] == 1

    def test_student_list_filters_pilot_rows_and_sessions(self):
        with patch.object(dashboard, "_db_manager") as db:
            db.get_activity_students_with_sessions.return_value = [
                {"user_email": "pilot@lamb-lti.local", "is_pilot": 1,
                 "session_id": "ws-1", "session_status": "submitted"},
                {"user_email": "s2@lamb-lti.local", "is_pilot": 0,
                 "session_id": "ws-2", "session_status": "submitted",
                 "session_is_pilot": 1},
                {"user_email": "s3@lamb-lti.local", "is_pilot": 0,
                 "session_id": "ws-3", "session_status": "submitted"},
            ]
            db.get_workshop_evaluations_by_activity.return_value = []

            students = dashboard.workshop_dashboard_students(_activity())

        assert [s["email"] for s in students] == ["s3@lamb-lti.local"]

    def test_default_roster_behaviour_is_untouched(self):
        """Regression: chat dashboards still count everyone (opt-in filter)."""
        from lamb.database_manager import LambDatabaseManager

        with patch.object(LambDatabaseManager, "get_connection",
                          return_value=None):
            # A missing connection returns the empty shape, not an exception.
            assert LambDatabaseManager().get_activity_students(1) == {
                "students": [], "total": 0}


class TestAuditTrail:
    """The escape hatch must leave a trace."""

    def test_skip_writes_an_audit_entry(self):
        from lamb import lti_router

        with patch.object(lti_router, "db_manager") as db:
            db.get_creator_user_by_email.return_value = {"id": 42}
            lti_router._audit_pilot_skip(_activity(), "teacher@school.edu")

            db.write_audit_log.assert_called_once()
            kwargs = db.write_audit_log.call_args.kwargs
            assert kwargs["action"] == "workshop.pilot_skip"
            assert kwargs["actor_user_id"] == 42
            assert kwargs["target_id"] == "1"
            assert "skip_pilot" in kwargs["details"]["reason"]

    def test_audit_failure_never_breaks_the_launch(self):
        from lamb import lti_router

        with patch.object(lti_router, "db_manager") as db:
            db.get_creator_user_by_email.side_effect = RuntimeError("db down")
            # Must not raise: auditing is not worth failing a lesson for.
            lti_router._audit_pilot_skip(_activity(), "teacher@school.edu")


class TestSkipPilotIsOwnerOnly:
    """`?skip_pilot=1` is the owner's escape hatch, not any instructor's (C13)."""

    @staticmethod
    def _request(value=None):
        request = MagicMock()
        request.query_params = {} if value is None else {"skip_pilot": value}
        return request

    def test_owner_may_skip(self):
        from lamb import lti_router

        for value in ("1", "true", "YES", " on "):
            assert lti_router._pilot_skip_granted(
                self._request(value), True, _activity(), "teacher@school.edu"
            ) is True

    def test_non_owner_is_ignored_and_logged(self, caplog):
        from lamb import lti_router

        with caplog.at_level("WARNING"):
            granted = lti_router._pilot_skip_granted(
                self._request("1"), False, _activity(), "assistant@school.edu")

        assert granted is False
        assert "non-owner" in caplog.text
        assert "assistant@school.edu" in caplog.text

    def test_no_parameter_or_unrelated_value_never_skips(self):
        from lamb import lti_router

        for request in (self._request(), self._request("0"), self._request("")):
            assert lti_router._pilot_skip_granted(
                request, True, _activity(), "teacher@school.edu") is False

    def _launch(self, lms_email, skip="1"):
        """Run a full instructor launch against a blocking, configured activity."""
        from lamb import lti_router
        from lamb.modules.workshop import module as workshop_module

        request = MagicMock()
        request.query_params = {"skip_pilot": skip}
        request.form = lambda: _async_form({
            "oauth_consumer_key": "key",
            "resource_link_id": "rl-1",
            "roles": "Instructor",
            "user_id": "u-1",
            "lis_person_contact_email_primary": lms_email,
        })

        with patch.object(lti_router.manager, "get_lti_credentials",
                          return_value=("key", "secret")),              patch.object(lti_router.manager, "validate_oauth_signature",
                          return_value=True),              patch.object(lti_router.manager, "is_instructor",
                          return_value=True),              patch.object(lti_router.db_manager,
                          "get_lti_activity_by_resource_link",
                          return_value=_activity()),              patch.object(lti_router.manager, "get_public_base_url",
                          return_value="https://lamb.example"),              patch.object(dashboard, "is_teacher_pilot_blocking",
                          return_value=True),              patch.object(lti_router, "is_teacher_pilot_required",
                          return_value=True),              patch.object(lti_router, "_audit_pilot_skip") as audit,              patch.object(workshop_module, "on_student_launch",
                          return_value={"redirect": "https://lamb.example/pilot"}
                          ) as pilot,              patch.object(workshop_module, "on_instructor_launch",
                          return_value={"redirect": "https://lamb.example/dash"}
                          ) as dash:
            import asyncio

            response = asyncio.run(lti_router.lti_launch(request))
        return response, pilot, dash, audit

    def test_non_owner_with_skip_still_goes_through_the_pilot(self):
        response, pilot, dash, audit = self._launch("assistant@school.edu")

        assert response.headers["location"] == "https://lamb.example/pilot"
        assert pilot.call_args.args[0]["pilot"] is True
        dash.assert_not_called()
        audit.assert_not_called()

    def test_owner_with_skip_reaches_the_dashboard_and_is_audited(self):
        response, pilot, dash, audit = self._launch("teacher@school.edu")

        assert response.headers["location"] == "https://lamb.example/dash"
        pilot.assert_not_called()
        audit.assert_called_once()
        assert audit.call_args.args[1] == "teacher@school.edu"


class TestStudentWaitingPage:
    """Students are informed, and in their own language."""

    @pytest.mark.asyncio
    async def test_waiting_page_renders_in_the_launch_locale(self):
        from lamb import lti_router

        request = MagicMock()
        request.headers = {"accept-language": "en"}

        with patch.object(lti_router.manager, "get_lti_credentials",
                          return_value=("key", "secret")), \
             patch.object(lti_router.manager, "validate_oauth_signature",
                          return_value=True), \
             patch.object(lti_router.manager, "is_instructor",
                          return_value=False), \
             patch.object(lti_router.db_manager,
                          "get_lti_activity_by_resource_link",
                          return_value=_activity()), \
             patch.object(lti_router.manager, "get_public_base_url",
                          return_value="https://lamb.example"), \
             patch.object(dashboard, "is_teacher_pilot_blocking",
                          return_value=True), \
             patch.object(lti_router, "is_teacher_pilot_required",
                          return_value=True):
            request.form = lambda: _async_form({
                "oauth_consumer_key": "key",
                "resource_link_id": "rl-1",
                "roles": "Learner",
                "user_id": "u-1",
                "launch_presentation_locale": "eu",
            })

            response = await lti_router.lti_launch(request)

        body = response.body.decode()
        assert response.status_code == 200
        assert 'lang="eu"' in body
        assert "Oraindik ez dago irekita" in body


async def _async_form(data):
    return data
