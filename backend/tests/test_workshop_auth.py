"""
Tests for workshop restricted-creator authorization (core of the workshop).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.modules.workshop import routers
from lamb.lamb_classes import Assistant


def _make_principal(session_id="ws-1", email="student@lamb-lti.local",
                    activity_id=1, org_id=10):
    return {
        "scope": "workshop_student",
        "type": "workshop_student",
        "session_id": session_id,
        "activity_id": activity_id,
        "activity_user_id": 5,
        "owi_user_id": "owi-5",
        "email": email,
        "organization_id": org_id,
    }


def _token_payload(**overrides):
    p = {
        "scope": "workshop_student",
        "session_id": "ws-1",
        "activity_id": 1,
        "email": "student@lamb-lti.local",
        "organization_id": 10,
    }
    p.update(overrides)
    return p


class TestVerifyPrincipal:
    """Authorization boundary for the workshop token."""

    @patch("lamb.auth.decode_token")
    def test_valid_principal_ok(self, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1")
        principal = routers._verify_workshop_principal("ws-1", "tok")
        assert principal["scope"] == "workshop_student"

    @patch("lamb.auth.decode_token")
    def test_bad_scope_rejected(self, mock_decode):
        mock_decode.return_value = {"scope": "lti_unified"}
        with pytest.raises(HTTPException) as exc:
            routers._verify_workshop_principal("ws-1", "tok")
        assert exc.value.status_code == 401

    @patch("lamb.auth.decode_token")
    def test_session_mismatch_rejected(self, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-different")
        with pytest.raises(HTTPException) as exc:
            routers._verify_workshop_principal("ws-1", "tok")
        assert exc.value.status_code == 403


class TestRestrictedCreateAssistant:
    """WA1: student can create an assistant owned by them, scoped to org."""

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_create_assistant_success(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1", org_id=10)
        # No existing assistant in session
        mock_db.get_workshop_session_by_id.return_value = {"assistant_id": None}
        mock_db.add_assistant.return_value = 42

        result = await routers.create_workshop_assistant(
            session_id="ws-1",
            body={"name": "My Assistant", "system_prompt": "Be helpful."},
            token="tok",
        )
        assert result["success"] is True
        assert result["assistant_id"] == 42

        # Assistant created with owner = student email and the activity's org
        created = mock_db.add_assistant.call_args[0][0]
        assert isinstance(created, Assistant)
        assert created.owner == "student@lamb-lti.local"
        assert created.organization_id == 10

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_quota_enforced(self, mock_db, mock_decode):
        """WA4: second assistant creation is rejected (single-assistant quota)."""
        mock_decode.return_value = _token_payload(session_id="ws-1", org_id=10)
        mock_db.get_workshop_session_by_id.return_value = {"assistant_id": 99}

        with pytest.raises(HTTPException) as exc:
            await routers.create_workshop_assistant(
                session_id="ws-1", body={}, token="tok")
        assert exc.value.status_code == 429


class TestRestrictedOwnership:
    """WA3: no cross-tenant / touching others' work."""

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_cross_tenant_rejected(self, mock_db, mock_decode):
        # Principal belongs to org 10; assistant belongs to org 99
        mock_decode.return_value = _token_payload(session_id="ws-1", org_id=10)
        other = Assistant(
            id=7, name="Other", description="", owner="other@test.com",
            api_callback="{}", system_prompt="S", prompt_template="T",
            organization_id=99, RAG_Top_k=3, RAG_collections="[]",
            pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
        )
        mock_db.get_assistant_by_id.return_value = other

        with pytest.raises(HTTPException) as exc:
            await routers.connect_workshop_kb(
                session_id="ws-1", assistant_id=7, body={"kb_id": "kb-1"},
                token="tok")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_not_own_assistant_rejected(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1", org_id=10)
        other = Assistant(
            id=7, name="Other", description="", owner="someone@test.com",
            api_callback="{}", system_prompt="S", prompt_template="T",
            organization_id=10, RAG_Top_k=3, RAG_collections="[]",
            pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
        )
        mock_db.get_assistant_by_id.return_value = other

        with pytest.raises(HTTPException) as exc:
            await routers.attach_workshop_document(
                session_id="ws-1", assistant_id=7,
                file=MagicMock(filename="doc.txt"), token="tok")
        assert exc.value.status_code == 403


class TestRestrictedUpdateAssistant:
    """Workshop student can edit the assistant they created (e.g. instructions)."""

    def _own_assistant(self, **overrides):
        opts = dict(
            id=7, name="My Assistant", description="",
            owner="student@lamb-lti.local", api_callback="{}",
            system_prompt="old", prompt_template="{user_input}",
            organization_id=10, RAG_Top_k=3, RAG_collections="[]",
            pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
        )
        opts.update(overrides)
        return Assistant(**opts)

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_update_system_prompt_persisted(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1", org_id=10)
        mock_db.get_assistant_by_id.return_value = self._own_assistant()
        mock_db.update_assistant.return_value = True

        result = await routers.update_workshop_assistant(
            session_id="ws-1",
            assistant_id=7,
            body={"system_prompt": "Be a helpful tutor."},
            token="tok",
        )
        assert result["success"] is True
        assert result["assistant_id"] == 7

        updated = mock_db.update_assistant.call_args[0][1]
        assert isinstance(updated, Assistant)
        assert updated.system_prompt == "Be a helpful tutor."
        # Unrelated fields preserved from the existing record.
        assert updated.owner == "student@lamb-lti.local"
        assert updated.organization_id == 10

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_cannot_edit_others_assistant(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1", org_id=10)
        mock_db.get_assistant_by_id.return_value = self._own_assistant(
            owner="someone@test.com")

        with pytest.raises(HTTPException) as exc:
            await routers.update_workshop_assistant(
                session_id="ws-1",
                assistant_id=7,
                body={"system_prompt": "hi"},
                token="tok",
            )
        assert exc.value.status_code == 403
        mock_db.update_assistant.assert_not_called()


class TestConsent:
    """WE1/WE2: consent gate — first visit shows the page, later visits skip."""

    @staticmethod
    def _request():
        from starlette.requests import Request

        return Request({
            "type": "http",
            "method": "GET",
            "path": "/lamb/v1/workshop/consent",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("localhost", 80),
            "client": ("127.0.0.1", 1234),
        })

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_consent_submit_records_and_redirects(
            self, mock_db, mock_decode, mock_wizard):
        mock_decode.return_value = _token_payload(activity_id=1, email="s@lamb.com")
        resp = await routers.consent_submit(request=self._request(), token="tok")

        from fastapi.responses import RedirectResponse
        assert isinstance(resp, RedirectResponse)
        assert resp.status_code == 303
        assert resp.headers["location"] == "http://t/m/workshop/1?token=tok"
        mock_db.record_student_consent.assert_called_once_with(1, "s@lamb.com")

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_consent_page_first_visit_renders(
            self, mock_db, mock_decode, mock_wizard):
        """WE1: no consent_given_at yet → the consent page is served (200)."""
        mock_decode.return_value = _token_payload(activity_id=1, email="s@lamb.com")
        mock_db.get_activity_user.return_value = {"consent_given_at": None}

        resp = await routers.consent_page(request=self._request(), token="tok")
        assert resp.status_code == 200
        assert "text/html" in resp.media_type

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_consent_page_revisit_skips(
            self, mock_db, mock_decode, mock_wizard):
        """WE2: consent already given → straight to the wizard (303)."""
        mock_decode.return_value = _token_payload(activity_id=1, email="s@lamb.com")
        mock_db.get_activity_user.return_value = {"consent_given_at": 1770000000}

        resp = await routers.consent_page(request=self._request(), token="tok")

        from fastapi.responses import RedirectResponse
        assert isinstance(resp, RedirectResponse)
        assert resp.status_code == 303
        assert resp.headers["location"] == "http://t/m/workshop/1?token=tok"

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    async def test_consent_bad_token(self, mock_decode, mock_wizard):
        mock_decode.return_value = {"scope": "lti_unified"}
        with pytest.raises(HTTPException) as exc:
            await routers.consent_page(request=self._request(), token="tok")
        assert exc.value.status_code == 401


class TestSubmitPersistsBuildState:
    """WS1: submit forwards the wizard's build_state to the DB layer.

    Regression: the app used to persist only saved_chat + reflection, so the
    formative transcript and teacher dashboard read an empty build_state.
    """

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_submit_forwards_build_state(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(session_id="ws-1")

        result = await routers.submit_workshop(
            session_id="ws-1",
            body={
                "saved_chat": '[{"role":"user","content":"hi"}]',
                "reflection": "I learned that grounding matters.",
                "build_state": '{"selectedTools":["calculator"]}',
            },
            token="tok",
        )

        assert result["success"] is True
        _, kwargs = mock_db.submit_workshop_session.call_args
        assert kwargs["build_state"] == '{"selectedTools":["calculator"]}'
        assert kwargs["reflection"] == "I learned that grounding matters."

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_submit_without_build_state_still_works(self, mock_db, mock_decode):
        """Backward-compatible: older clients that omit build_state don't break."""
        mock_decode.return_value = _token_payload(session_id="ws-1")

        result = await routers.submit_workshop(
            session_id="ws-1",
            body={"saved_chat": "[]", "reflection": "ok"},
            token="tok",
        )

        assert result["success"] is True
        _, kwargs = mock_db.submit_workshop_session.call_args
        assert kwargs["build_state"] is None

