"""Diff-coverage unit tests for ``creator_interface.kb_server_manager``.

Targets the branch-added lines:
  - import-time bootstrap (15, 23, 29-30) — covered by importing the module
    with ``LAMB_KB_SERVER_TOKEN`` set so the top-level guard does not raise.
  - ``_get_kb_config_for_user`` org-config path + global fallback (82-83, 97)
  - ``is_kb_server_available`` URL-try loop (127-139, 141, 144-146)
  - ``create_knowledge_base`` host-redirect block (505-507)

All subprocess/httpx/filesystem/env interaction is mocked; no network needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Make ``backend/`` importable and ensure the import-time token guard passes.
_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("LAMB_KB_SERVER_TOKEN", "test-token")

from creator_interface import kb_server_manager as ksm  # noqa: E402


@pytest.fixture
def manager():
    """A KBServerManager with a known global URL/token regardless of env."""
    mgr = ksm.KBServerManager()
    mgr.global_kb_server_url = "http://kb:9090"
    mgr.global_kb_server_token = "global-token"
    mgr.kb_server_configured = True
    return mgr


# ---------------------------------------------------------------------------
# _get_kb_config_for_user — org-config path (lines 82-83) and fallback (97)
# ---------------------------------------------------------------------------


def test_get_kb_config_org_config_without_api_token(manager):
    """Org config present but missing api_token -> falls back to global token,
    resolves url via redirects (lines 82-83)."""
    fake_resolver = MagicMock()
    fake_resolver.organization = {"name": "Acme"}
    fake_resolver.get_knowledge_base_config.return_value = {
        "server_url": "http://org-kb:9090",
        # no api_token
    }

    with patch(
        "lamb.completions.org_config_resolver.OrganizationConfigResolver",
        return_value=fake_resolver,
    ):
        cfg = manager._get_kb_config_for_user({"email": "u@example.com"})

    assert cfg["url"] == "http://org-kb:9090"
    assert cfg["token"] == "global-token"  # fell back to global token (line 81-82)


def test_get_kb_config_org_config_with_redirect(manager):
    """server_url matches a redirect entry -> resolved_url uses the redirect."""
    fake_resolver = MagicMock()
    fake_resolver.organization = {"name": "Acme"}
    fake_resolver.get_knowledge_base_config.return_value = {
        "server_url": "http://org-kb:9090",
        "api_token": "org-token",
    }

    with patch.dict(ksm._KB_REDIRECTS, {"http://org-kb:9090": "http://redirected:9090"}, clear=False), \
        patch(
            "lamb.completions.org_config_resolver.OrganizationConfigResolver",
            return_value=fake_resolver,
        ):
        cfg = manager._get_kb_config_for_user({"email": "u@example.com"})

    assert cfg["url"] == "http://redirected:9090"
    assert cfg["token"] == "org-token"


def test_get_kb_config_fallback_to_global_with_redirect(manager):
    """No org config -> global fallback path; resolved via redirects (line 97)."""
    fake_resolver = MagicMock()
    fake_resolver.organization = {"name": "Acme"}
    fake_resolver.get_knowledge_base_config.return_value = None  # no org config

    with patch.dict(ksm._KB_REDIRECTS, {"http://kb:9090": "http://redirected:9090"}, clear=False), \
        patch(
            "lamb.completions.org_config_resolver.OrganizationConfigResolver",
            return_value=fake_resolver,
        ):
        cfg = manager._get_kb_config_for_user({"email": "u@example.com"})

    assert cfg["url"] == "http://redirected:9090"
    assert cfg["token"] == "global-token"


# ---------------------------------------------------------------------------
# is_kb_server_available — URL-try loop (127-139, 141, 144-146)
# ---------------------------------------------------------------------------


def _make_async_client(get_mock):
    """Build a context-manager mock standing in for httpx.AsyncClient."""
    client_instance = MagicMock()
    client_instance.get = get_mock
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client_instance)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


@pytest.mark.asyncio
async def test_is_available_primary_ok(manager):
    """Primary URL returns 200 -> True; covers urls_to_try build + 200 branch."""
    manager.global_kb_server_url = "http://kb:9090"

    resp = MagicMock()
    resp.status_code = 200
    get_mock = AsyncMock(return_value=resp)

    with patch.object(ksm.httpx, "AsyncClient", _make_async_client(get_mock)):
        result = await manager.is_kb_server_available()

    assert result is True
    # Only the primary URL should have been hit.
    get_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_available_fallback_to_docker_internal(manager):
    """Primary kb:9090 fails, host.docker.internal succeeds -> True and
    global_kb_server_url switched (lines 128-129, 137-139)."""
    manager.global_kb_server_url = "http://kb:9090"

    primary_resp = MagicMock()
    primary_resp.status_code = 500  # non-200 -> warning branch (141-143)
    fallback_resp = MagicMock()
    fallback_resp.status_code = 200

    get_mock = AsyncMock(side_effect=[primary_resp, fallback_resp])

    with patch.object(ksm.httpx, "AsyncClient", _make_async_client(get_mock)):
        result = await manager.is_kb_server_available()

    assert result is True
    assert manager.global_kb_server_url == "http://host.docker.internal:9090"
    assert get_mock.await_count == 2


@pytest.mark.asyncio
async def test_is_available_all_fail_raises(manager):
    """All attempts raise -> exception branch (144-145) then return False (146)."""
    manager.global_kb_server_url = "http://kb:9090"

    get_mock = AsyncMock(side_effect=RuntimeError("boom"))

    with patch.object(ksm.httpx, "AsyncClient", _make_async_client(get_mock)):
        result = await manager.is_kb_server_available()

    assert result is False
    assert get_mock.await_count == 2  # tried both primary + fallback


@pytest.mark.asyncio
async def test_is_available_config_resolution_failure(manager):
    """creator_user given but config resolution raises -> early False."""
    with patch.object(manager, "_get_kb_config_for_user", side_effect=ValueError("nope")):
        result = await manager.is_kb_server_available(creator_user={"email": "x@y.z"})
    assert result is False


@pytest.mark.asyncio
async def test_is_available_no_url_configured(manager):
    """URL blank -> warning + False (covers the not-configured guard)."""
    manager.global_kb_server_url = "   "
    result = await manager.is_kb_server_available()
    assert result is False


# ---------------------------------------------------------------------------
# create_knowledge_base — host-redirect block (lines 505-507)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_kb_applies_host_redirect(manager):
    """When kb_server_url is in _KB_REDIRECTS, it is swapped before the POST
    (lines 505-507). Verifies the redirected URL is used in the request."""
    kb_data = ksm.KnowledgeBaseCreate(name="My KB", description="d", access_control="private")

    # Stub config resolution to a URL that has a redirect entry.
    with patch.object(
        manager,
        "_get_kb_config_for_user",
        return_value={"url": "http://kb:9090", "token": "tok"},
    ), patch.dict(
        ksm._KB_REDIRECTS, {"http://kb:9090": "http://redirected:9090"}, clear=False
    ):
        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {"id": "abc123"}
        post_mock = AsyncMock(return_value=post_resp)

        client_instance = MagicMock()
        client_instance.post = post_mock
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client_instance)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ksm.httpx, "AsyncClient", MagicMock(return_value=cm)), \
            patch("lamb.database_manager.LambDatabaseManager") as DBM:
            DBM.return_value = MagicMock()
            result = await manager.create_knowledge_base(kb_data, {"id": 7, "organization_id": 1})

    assert result["id"] == "abc123"
    # The POST must have targeted the redirected host.
    called_url = post_mock.await_args.args[0]
    assert called_url == "http://redirected:9090/collections"
