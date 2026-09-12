"""
Tests for workshop restricted-creator authorization (core of Phase 3).
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
                session_id="ws-1", assistant_id=7, body={"title": "Doc"},
                token="tok")
        assert exc.value.status_code == 403


class TestConsent:
    """WE1/WE2: consent flow records via the existing consent method."""

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_consent_submit_records(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload(activity_id=1, email="s@lamb.com")
        result = await routers.consent_submit(body={}, token="tok")
        assert result["success"] is True
        mock_db.record_student_consent.assert_called_once_with(1, "s@lamb.com")

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    async def test_consent_bad_token(self, mock_decode):
        mock_decode.return_value = {"scope": "lti_unified"}
        with pytest.raises(HTTPException) as exc:
            await routers.consent_submit(body={}, token="tok")
        assert exc.value.status_code == 401
