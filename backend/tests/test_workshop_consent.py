"""W3 tests — consent disclosure, versioning and re-consent.

The consent page tells students what happens to their work. Two properties are
non-negotiable and pinned here:

* the model disclosure comes from the **live** completion configuration
  (decision C17) — the page must not be able to describe a model setup the
  deployment does not have;
* a notice change can be made to re-ask (decision C8/C20), and the teacher can
  see how many students will be asked again.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.modules.workshop import dashboard, routers


def _activity(**overrides):
    activity = {
        "id": 1,
        "activity_type": "workshop",
        "owner_email": "teacher@school.edu",
        "organization_id": 10,
        "resource_link_id": "rl-1",
    }
    activity.update(overrides)
    return activity


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


class TestModelClassClassification:
    """`local` / `external` / `unknown`, judged from the resolved provider."""

    @pytest.mark.parametrize("connector,base_url,expected", [
        ("ollama", "http://host.docker.internal:11434", "local"),
        ("bypass", "", "local"),
        ("openai", "https://api.openai.com/v1", "external"),
        ("anthropic", "https://api.anthropic.com", "external"),
        ("google", "https://generativelanguage.googleapis.com", "external"),
        ("", "", "unknown"),
    ])
    def test_known_providers(self, connector, base_url, expected):
        assert routers.classify_model_class(connector, base_url) == expected

    def test_custom_endpoint_is_judged_by_its_url(self):
        # A self-hosted OpenAI-compatible endpoint stays local…
        assert routers.classify_model_class(
            "llm", "http://localhost:8000/v1") == "local"
        assert routers.classify_model_class(
            "llm", "http://192.168.1.10:8000/v1") == "local"
        assert routers.classify_model_class(
            "llm", "http://host.docker.internal:8000/v1") == "local"
        # …anything else leaves the deployment.
        assert routers.classify_model_class(
            "llm", "https://models.example.com/v1") == "external"

    def test_unknown_provider_without_url_over_discloses(self):
        """Erring towards telling the student more is the safe direction."""
        assert routers.classify_model_class("some-new-vendor", "") == "external"


class TestConsentModelInfo:
    """C17: the disclosure is derived, never written down."""

    def test_uses_the_real_resolution_chain(self):
        resolver = MagicMock()
        resolver.resolve_model_for_completion.return_value = {
            "provider": "openai", "model": "gpt-4o-mini"}
        resolver.get_provider_config.return_value = {
            "base_url": "https://api.openai.com/v1"}

        with patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   return_value=resolver), \
             patch("lamb.completions.main.load_plugins", return_value={}):
            info = routers.resolve_consent_model_info(_activity())

        assert info["model_class"] == "external"
        assert info["model"] == "gpt-4o-mini"
        assert info["connector"] == "openai"
        resolver.resolve_model_for_completion.assert_called_once()

    def test_local_model_is_reported_as_local(self):
        resolver = MagicMock()
        resolver.resolve_model_for_completion.return_value = {
            "provider": "ollama", "model": "qwen3.5:9b"}
        resolver.get_provider_config.return_value = {
            "base_url": "http://host.docker.internal:11434"}

        with patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   return_value=resolver), \
             patch("lamb.completions.main.load_plugins", return_value={}):
            info = routers.resolve_consent_model_info(_activity())

        assert info["model_class"] == "local"

    def test_unresolvable_config_says_unknown(self):
        """A misconfigured deployment must not claim a model it cannot resolve."""
        resolver = MagicMock()
        resolver.resolve_model_for_completion.side_effect = ValueError("no model")

        with patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   return_value=resolver), \
             patch("lamb.completions.main.load_plugins", return_value={}):
            info = routers.resolve_consent_model_info(_activity())

        assert info["model_class"] == "unknown"
        assert info["model"] == ""

    def test_no_owner_is_unknown(self):
        info = routers.resolve_consent_model_info({"id": 1})
        assert info["model_class"] == "unknown"


class TestConsentInfoEndpoint:
    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_reports_model_class_and_retention(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_lti_activity_by_id.return_value = _activity()

        with patch.object(routers, "resolve_consent_model_info",
                          return_value={"model_class": "external",
                                        "model": "gpt-4o-mini",
                                        "connector": "openai"}), \
             patch("lamb.modules.workshop.retention.retention_days",
                   return_value=180):
            info = await routers.consent_info(token="tok")

        assert info["model_class"] == "external"
        assert info["retention_days"] == 180
        assert info["consent_version"] == routers.CONSENT_VERSION

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_unknown_activity_is_404(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_lti_activity_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await routers.consent_info(token="tok")
        assert exc.value.status_code == 404


class TestReconsent:
    """C8/C20: a notice change re-asks by default, and the teacher can see it."""

    def test_version_mismatch_asks_again(self):
        assert routers._needs_reconsent(
            _activity(), {"consent_given_at": 1, "consent_version": "2020-01"}) is True

    def test_matching_version_skips(self):
        assert routers._needs_reconsent(
            _activity(),
            {"consent_given_at": 1,
             "consent_version": routers.CONSENT_VERSION}) is False

    def test_missing_version_asks_again(self):
        """Students who consented before versioning existed are re-asked."""
        assert routers._needs_reconsent(
            _activity(), {"consent_given_at": 1, "consent_version": None}) is True

    @pytest.mark.parametrize("value,expected", [
        (0, False), ("0", False), (False, False),
        ("false", False), ("no", False), ("off", False),
        (1, True), ("1", True), (True, True),
    ])
    def test_activity_switch_disables_reasking(self, value, expected):
        resolver = MagicMock()
        resolver.get_feature_value.return_value = value
        with patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   return_value=resolver):
            assert routers._reconsent_required(_activity()) is expected

    def test_switch_defaults_to_on(self):
        resolver = MagicMock()
        resolver.get_feature_value.return_value = 1
        with patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   return_value=resolver):
            assert routers._reconsent_required(_activity()) is True

    def test_unresolvable_org_defaults_to_asking(self):
        with patch("lamb.completions.org_config_resolver.OrganizationConfigResolver",
                   side_effect=ValueError("no org")):
            assert routers._reconsent_required(_activity()) is True


class TestConsentFlow:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_stale_version_is_asked_again(
            self, mock_db, mock_decode, mock_wizard):
        mock_decode.return_value = _token_payload()
        mock_db.get_lti_activity_by_id.return_value = _activity()
        mock_db.get_activity_user.return_value = {
            "consent_given_at": 1770000000, "consent_version": "2020-01"}

        request = MagicMock()
        request.headers = {"accept-language": "es"}

        resp = await routers.consent_page(request=request, token="tok")
        assert resp.status_code == 200
        body = resp.body.decode()
        # Spanish copy, and the notice is actually shown again.
        assert "Antes de empezar" in body

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_current_version_gets_the_wizard(
            self, mock_db, mock_decode, mock_wizard):
        mock_decode.return_value = _token_payload()
        mock_db.get_lti_activity_by_id.return_value = _activity()
        mock_db.get_activity_user.return_value = {
            "consent_given_at": 1770000000,
            "consent_version": routers.CONSENT_VERSION}

        request = MagicMock()
        request.headers = {"accept-language": "en"}
        resp = await routers.consent_page(request=request, token="tok")
        assert resp.status_code == 303

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._wizard_url",
           return_value="http://t/m/workshop/1?token=tok")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_submit_records_the_version(
            self, mock_db, mock_decode, mock_wizard):
        mock_decode.return_value = _token_payload()
        request = MagicMock()

        resp = await routers.consent_submit(request=request, token="tok")

        assert resp.status_code == 303
        mock_db.record_student_consent.assert_called_once_with(
            1, "student@lamb-lti.local", consent_version=routers.CONSENT_VERSION)


class TestConsentPageRendering:
    """The rendered page must state the three purposes and the real model class."""

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_external_model_is_disclosed_with_its_name(
            self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_lti_activity_by_id.return_value = _activity()
        mock_db.get_activity_user.return_value = None

        request = MagicMock()
        request.headers = {"accept-language": "en"}

        with patch.object(routers, "resolve_consent_model_info",
                          return_value={"model_class": "external",
                                        "model": "gpt-4o-mini",
                                        "connector": "openai"}), \
             patch("lamb.modules.workshop.retention.retention_days",
                   return_value=90):
            resp = await routers.consent_page(request=request, token="tok")

        body = resp.body.decode()
        assert "gpt-4o-mini" in body            # the real model
        assert "external service" in body
        assert "reviewed by a model" in body    # the third purpose
        assert "90 days" in body                # the retention window
        assert 'lang="en"' in body

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_unknown_model_tells_the_student_nothing_is_sent(
            self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_lti_activity_by_id.return_value = _activity()
        mock_db.get_activity_user.return_value = None

        request = MagicMock()
        request.headers = {"accept-language": "en"}

        with patch.object(routers, "resolve_consent_model_info",
                          return_value={"model_class": "unknown", "model": ""}), \
             patch("lamb.modules.workshop.retention.retention_days",
                   return_value=None):
            resp = await routers.consent_page(request=request, token="tok")

        assert "not configured yet" in resp.body.decode()


class TestDashboardConsentStats:
    def test_pending_reconsent_is_counted_with_the_current_version(self):
        with patch.object(dashboard, "_db_manager") as mock_db:
            mock_db.count_pending_reconsent.return_value = 3
            assert dashboard.pending_reconsent_count(_activity()) == 3
            mock_db.count_pending_reconsent.assert_called_once_with(
                1, routers.CONSENT_VERSION)

    def test_counting_failure_does_not_break_the_dashboard(self):
        with patch.object(dashboard, "_db_manager") as mock_db:
            mock_db.count_pending_reconsent.side_effect = RuntimeError("db down")
            assert dashboard.pending_reconsent_count(_activity()) == 0


class TestDashboardRetentionStats:
    def test_expiring_soon_counts_only_sessions_with_content(self):
        with patch.object(dashboard, "_db_manager") as mock_db, \
             patch("lamb.modules.workshop.retention.retention_cutoff",
                   return_value=123):
            mock_db.list_workshop_sessions_for_retention.return_value = [
                {"id": "ws-1", "activity_id": 1, "reflection": "text"},
                {"id": "ws-2", "activity_id": 1, "saved_chat": None,
                 "reflection": None},
                {"id": "ws-3", "activity_id": 2, "reflection": "other activity"},
            ]
            assert dashboard.expiring_soon_count(1) == 1

    def test_expiring_soon_is_zero_when_retention_is_off(self):
        with patch("lamb.modules.workshop.retention.retention_cutoff",
                   return_value=None):
            assert dashboard.expiring_soon_count(1) == 0

    def test_warns_when_external_model_has_no_retention(self):
        with patch("lamb.modules.workshop.retention.retention_days",
                   return_value=None), \
             patch.object(routers, "resolve_consent_model_info",
                          return_value={"model_class": "external"}):
            assert dashboard.retention_warning(_activity()) is True

    def test_no_warning_when_retention_is_configured(self):
        with patch("lamb.modules.workshop.retention.retention_days",
                   return_value=180):
            assert dashboard.retention_warning(_activity()) is False

    def test_no_warning_for_a_local_model(self):
        with patch("lamb.modules.workshop.retention.retention_days",
                   return_value=None), \
             patch.object(routers, "resolve_consent_model_info",
                          return_value={"model_class": "local"}):
            assert dashboard.retention_warning(_activity()) is False

    def test_stats_expose_the_new_fields(self):
        with patch.object(dashboard, "_db_manager") as mock_db, \
             patch.object(dashboard, "is_teacher_pilot_required",
                          return_value=False), \
             patch.object(dashboard, "pending_reconsent_count", return_value=2), \
             patch.object(dashboard, "expiring_soon_count", return_value=1), \
             patch.object(dashboard, "retention_warning", return_value=False), \
             patch("lamb.modules.workshop.retention.retention_days",
                   return_value=180):
            mock_db.get_activity_students.return_value = {"total": 12}
            mock_db.get_workshop_sessions_by_activity.return_value = []
            mock_db.get_workshop_evaluations_by_activity.return_value = []

            stats = dashboard.workshop_dashboard_stats(_activity())

        assert stats["pending_reconsent"] == 2
        assert stats["expiring_soon"] == 1
        assert stats["retention_warning"] is False
        assert stats["retention_days"] == 180
        # The roster count must exclude pilot rows (C13).
        assert mock_db.get_activity_students.call_args.kwargs["include_pilot"] is False
