"""W3 tests — retention tiers, two-level deletion, KB deletion branches.

Decision C9 splits data by category, and decision C18 splits deletion into two
levels. Both are easy to get subtly wrong (deleting a conversation silently, or
deleting the assistant when only the document was meant), so they are pinned
here rather than left to the manual flow.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.lamb_classes import Assistant
from lamb.modules.workshop import kb, retention


def _activity(**overrides):
    activity = {
        "id": 1,
        "activity_type": "workshop",
        "owner_email": "teacher@school.edu",
        "organization_id": 10,
    }
    activity.update(overrides)
    return activity


def _session(**overrides):
    session = {
        "id": "ws-1",
        "activity_id": 1,
        "activity_user_id": 5,
        "assistant_id": 7,
        "kb_id": "kb-1",
        "saved_chat": '[{"role":"user","content":"hi"}]',
        "reflection": "I learned something.",
        "is_pilot": 0,
    }
    session.update(overrides)
    return session


def _assistant(**overrides):
    opts = dict(
        id=7, name="A", description="", owner="student@lamb-lti.local",
        api_callback="{}", system_prompt="S", prompt_template="T",
        organization_id=10, RAG_Top_k=3, RAG_collections="kb-1",
        pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
    )
    opts.update(overrides)
    return Assistant(**opts)


class TestRetentionWindow:
    """The window is opt-in: nothing is ever deleted without a configuration."""

    def test_default_is_disabled(self):
        assert retention.retention_days() is None
        assert retention.retention_cutoff() is None

    def test_env_sets_the_window(self):
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_DAYS": "180"}):
            assert retention.retention_days() == 180

    def test_org_feature_overrides_env(self):
        resolver = MagicMock()
        resolver.get_feature_value.return_value = 30
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_DAYS": "180"}), \
             patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   return_value=resolver):
            assert retention.retention_days(_activity()) == 30

    def test_garbage_values_do_not_enable_deletion(self):
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_DAYS": "soon"}):
            assert retention.retention_days() is None
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_DAYS": "0"}):
            assert retention.retention_days() is None

    def test_cutoff_is_days_before_now(self):
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_DAYS": "10"}):
            cutoff = retention.retention_cutoff(now=1_000_000)
        assert cutoff == 1_000_000 - 10 * 86400

    def test_sweep_is_off_unless_enabled(self):
        assert retention.retention_enabled() is False
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_ENABLED": "1"}):
            assert retention.retention_enabled() is True


class TestEraseSessionContent:
    """erase: content and KB go, the assistant stays (C18)."""

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_erases_content_and_deletes_the_collection(
            self, mock_db, mock_delete_kb):
        mock_delete_kb.return_value = {"deleted": True, "detail": "ok"}
        mock_db.return_value.erase_workshop_session_content.return_value = True

        result = await retention.erase_session_content(_session(), _activity())

        assert result["success"] is True
        assert result["level"] == "erase"
        assert result["assistant_preserved"] is True
        mock_delete_kb.assert_awaited_once()
        mock_db.return_value.erase_workshop_session_content.assert_called_once_with(
            "ws-1")
        # The assistant keeps existing; only its RAG wiring is cleared.
        mock_db.return_value.clear_assistant_rag_collections.assert_called_once_with(7)
        mock_db.return_value.delete_assistant.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_kb_failure_leaves_local_content_untouched(
            self, mock_db, mock_delete_kb):
        """No half-delete: if the KB server is down, nothing local is wiped."""
        mock_delete_kb.side_effect = RuntimeError("KB server unreachable")

        result = await retention.erase_session_content(_session(), _activity())

        assert result["success"] is False
        assert "Knowledge base deletion failed" in result["detail"]
        mock_db.return_value.erase_workshop_session_content.assert_not_called()
        mock_db.return_value.clear_assistant_rag_collections.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_session_without_kb_skips_the_remote_call(
            self, mock_db, mock_delete_kb):
        mock_db.return_value.erase_workshop_session_content.return_value = True

        result = await retention.erase_session_content(
            _session(kb_id=None), _activity())

        assert result["success"] is True
        mock_delete_kb.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.retention._db")
    async def test_missing_session_is_rejected(self, mock_db):
        result = await retention.erase_session_content({}, _activity())
        assert result["success"] is False
        mock_db.return_value.erase_workshop_session_content.assert_not_called()


class TestPurgeSession:
    """purge: erase plus the assistant row, with the reference detached."""

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_purge_deletes_assistant_and_detaches_it(
            self, mock_db, mock_delete_kb):
        mock_delete_kb.return_value = {"deleted": True, "detail": "ok"}
        mock_db.return_value.erase_workshop_session_content.return_value = True
        mock_db.return_value.get_assistant_by_id.return_value = _assistant()
        mock_db.return_value.delete_assistant.return_value = True

        result = await retention.purge_session(_session(), _activity())

        assert result["success"] is True
        assert result["level"] == "purge"
        assert result["assistant_deleted"] is True
        mock_db.return_value.delete_assistant.assert_called_once_with(
            7, "student@lamb-lti.local")
        # The session row survives but must not point at a deleted assistant.
        mock_db.return_value.detach_workshop_session_assistant.assert_called_once_with(
            "ws-1")

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_purge_stops_when_erase_failed(self, mock_db, mock_delete_kb):
        mock_delete_kb.side_effect = RuntimeError("down")

        result = await retention.purge_session(_session(), _activity())

        assert result["success"] is False
        mock_db.return_value.delete_assistant.assert_not_called()
        mock_db.return_value.detach_workshop_session_assistant.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_purge_without_assistant_still_detaches(
            self, mock_db, mock_delete_kb):
        mock_delete_kb.return_value = {"deleted": True, "detail": "ok"}
        mock_db.return_value.erase_workshop_session_content.return_value = True

        result = await retention.purge_session(
            _session(assistant_id=None), _activity())

        assert result["success"] is True
        assert result["assistant_deleted"] is False
        mock_db.return_value.detach_workshop_session_assistant.assert_called_once()


class TestRetentionSweep:
    """The automatic sweep honours the per-category rules of C9."""

    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        result = await retention.purge_expired_sessions()
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_enabled_without_a_window_does_nothing(self):
        with patch.dict("os.environ", {"WORKSHOP_RETENTION_ENABLED": "1"}):
            result = await retention.purge_expired_sessions()
        assert result["enabled"] is False
        assert "retention window" in result["reason"]

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_tiers_are_applied_per_category(self, mock_db, mock_delete_kb):
        mock_delete_kb.return_value = {"deleted": True, "detail": "ok"}
        mock_db.return_value.list_workshop_sessions_for_retention.return_value = [
            _session(),                                   # KB + content + assistant
            _session(id="ws-2", kb_id=None),              # content only
            _session(id="ws-3", kb_id=None, saved_chat=None,
                     reflection=None, assistant_id=None),  # nothing left
        ]
        mock_db.return_value.get_lti_activity_by_id.return_value = _activity()

        with patch.dict("os.environ", {
                "WORKSHOP_RETENTION_ENABLED": "1",
                "WORKSHOP_RETENTION_DAYS": "180"}):
            summary = await retention.purge_expired_sessions()

        # KB material really is deleted…
        assert [entry["session_id"] for entry in summary["kb_deleted"]] == ["ws-1"]
        # …conversations are only *reported*…
        assert summary["expiring"] == ["ws-1", "ws-2"]
        mock_db.return_value.erase_workshop_session_content.assert_not_called()
        # …and assistants are never touched (both candidate sessions still
        # have one: their rows must survive the sweep untouched).
        assert summary["assistants_preserved"] == 2
        mock_db.return_value.delete_assistant.assert_not_called()
        mock_db.return_value.clear_assistant_rag_collections.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.retention._db")
    async def test_kb_failures_are_recorded_not_fatal(self, mock_db, mock_delete_kb):
        mock_delete_kb.side_effect = RuntimeError("KB server unreachable")
        mock_db.return_value.list_workshop_sessions_for_retention.return_value = [
            _session(),
        ]
        mock_db.return_value.get_lti_activity_by_id.return_value = _activity()

        with patch.dict("os.environ", {
                "WORKSHOP_RETENTION_ENABLED": "1",
                "WORKSHOP_RETENTION_DAYS": "180"}):
            summary = await retention.purge_expired_sessions()

        assert summary["kb_deleted"] == []
        assert len(summary["kb_failed"]) == 1
        assert "unreachable" in summary["kb_failed"][0]["error"]
        # A failed sweep must never erase the LAMB-side content.
        mock_db.return_value.erase_workshop_session_content.assert_not_called()


class TestKbDeletionBranches:
    """C15: the owner decides how the collection is deleted."""

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    @patch("lamb.modules.workshop.kb.get_collection", new_callable=AsyncMock)
    async def test_creator_owned_collection_uses_the_manager(
            self, mock_get, mock_resolve):
        manager = MagicMock()
        manager.delete_knowledge_base = AsyncMock(return_value={"success": True})
        mock_resolve.return_value = {
            "manager": manager,
            "creator_user": {"id": 3, "email": "teacher@school.edu"},
            "config": {"url": "http://kb", "token": "t"},
        }
        mock_get.return_value = {"id": "kb-1", "owner": "3"}

        result = await kb.delete_session_kb(_activity(), "kb-1")

        assert result["deleted"] is True
        manager.delete_knowledge_base.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_collection_direct", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    @patch("lamb.modules.workshop.kb.get_collection", new_callable=AsyncMock)
    async def test_workshop_owned_collection_bypasses_the_manager(
            self, mock_get, mock_resolve, mock_delete):
        """`workshop:{id}` owners would hit a 403 in the manager (C15)."""
        manager = MagicMock()
        manager.delete_knowledge_base = AsyncMock()
        mock_resolve.return_value = {
            "manager": manager,
            "creator_user": {"id": 3, "email": "teacher@school.edu"},
            "config": {"url": "http://kb", "token": "t"},
        }
        mock_get.return_value = {"id": "kb-1", "owner": "workshop:1"}

        result = await kb.delete_session_kb(_activity(), "kb-1")

        assert result["deleted"] is True
        mock_delete.assert_awaited_once()
        manager.delete_knowledge_base.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    @patch("lamb.modules.workshop.kb.get_collection", new_callable=AsyncMock)
    async def test_missing_collection_is_a_success(self, mock_get, mock_resolve):
        """Deletion is idempotent: a sweep may retry the same session."""
        mock_get.return_value = None
        mock_resolve.return_value = {
            "manager": MagicMock(), "creator_user": None,
            "config": {"url": "http://kb", "token": "t"},
        }

        result = await kb.delete_session_kb(_activity(), "kb-1")

        assert result["deleted"] is True
        assert result["detail"] == "already deleted"

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    @patch("lamb.modules.workshop.kb.get_collection", new_callable=AsyncMock)
    async def test_manager_failure_is_not_swallowed(
            self, mock_get, mock_resolve):
        manager = MagicMock()
        manager.delete_knowledge_base = AsyncMock(
            side_effect=HTTPException(status_code=500, detail="boom"))
        mock_resolve.return_value = {
            "manager": manager,
            "creator_user": {"id": 3},
            "config": {"url": "http://kb", "token": "t"},
        }
        mock_get.return_value = {"id": "kb-1", "owner": "3"}

        with pytest.raises(HTTPException):
            await kb.delete_session_kb(_activity(), "kb-1")


class TestDashboardDeletionEndpoints:
    """The teacher-facing routes are behind the dashboard token."""

    @pytest.mark.asyncio
    async def test_erase_rejects_a_bad_token(self):
        from lamb import lti_router

        with patch.object(lti_router, "_validate_token", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await lti_router.workshop_dashboard_erase(
                    session_id="ws-1", resource_link_id="rl-1", token="bad")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_purge_rejects_a_bad_token(self):
        from lamb import lti_router

        with patch.object(lti_router, "_validate_token", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await lti_router.workshop_dashboard_purge(
                    session_id="ws-1", resource_link_id="rl-1", token="bad",
                    confirm="Ann")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.retention.purge_session", new_callable=AsyncMock)
    async def test_purge_requires_a_matching_name(self, mock_purge):
        from lamb import lti_router

        with patch.object(lti_router, "_require_dashboard_token",
                          return_value={"is_owner": True}), \
             patch.object(lti_router, "_get_workshop_activity",
                          return_value=_activity()), \
             patch.object(lti_router, "_workshop_session_in_activity",
                          return_value=_session()), \
             patch.object(lti_router, "_student_identifiers",
                          return_value={"ann smith", "ann@school.edu"}):
            # Missing confirmation.
            with pytest.raises(HTTPException) as exc:
                await lti_router.workshop_dashboard_purge(
                    session_id="ws-1", resource_link_id="rl-1", token="tok",
                    confirm="")
            assert exc.value.status_code == 400

            # Wrong name.
            with pytest.raises(HTTPException) as exc:
                await lti_router.workshop_dashboard_purge(
                    session_id="ws-1", resource_link_id="rl-1", token="tok",
                    confirm="someone else")
            assert exc.value.status_code == 400

            # Correct name (case-insensitive).
            mock_purge.return_value = {"success": True, "level": "purge"}
            result = await lti_router.workshop_dashboard_purge(
                session_id="ws-1", resource_link_id="rl-1", token="tok",
                confirm="Ann Smith")
            assert result.status_code == 200
            mock_purge.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.retention.erase_session_content",
           new_callable=AsyncMock)
    async def test_erase_reports_kb_failures_as_502(self, mock_erase):
        from lamb import lti_router

        mock_erase.return_value = {"success": False, "detail": "KB down"}
        with patch.object(lti_router, "_require_dashboard_token",
                          return_value={"is_owner": True}), \
             patch.object(lti_router, "_get_workshop_activity",
                          return_value=_activity()), \
             patch.object(lti_router, "_workshop_session_in_activity",
                          return_value=_session()):
            with pytest.raises(HTTPException) as exc:
                await lti_router.workshop_dashboard_erase(
                    session_id="ws-1", resource_link_id="rl-1", token="tok")
        assert exc.value.status_code == 502
