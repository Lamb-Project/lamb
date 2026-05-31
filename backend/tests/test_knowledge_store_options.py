"""
Tests for knowledge_store_client.get_org_options — verifies that the
``/creator/knowledge-stores/options`` endpoint overrides the embedding
plugins' static ``api_endpoint`` default with the org-level
``setups[default].providers[<vendor>].endpoint`` so the UI's "create
Knowledge Store" form pre-fills with an endpoint that is reachable from
the kb-server-v2 container.

Regression test for defect D1 (lifecycle 2026-05-03).
"""

from pathlib import Path
from unittest.mock import patch, AsyncMock

import httpx
import pytest

from creator_interface.knowledge_store_client import (
    KnowledgeStoreClient,
    KnowledgeStoreUnavailable,
)


def _ollama_vendors_payload(default_endpoint="http://localhost:11434/api/embeddings"):
    """Match the shape returned by kb-server-v2's /embedding-vendors."""
    return {
        "vendors": [
            {
                "name": "ollama",
                "description": "Ollama local embeddings",
                "parameters": [
                    {
                        "name": "model",
                        "type": "string",
                        "description": "Ollama model name",
                        "default": "nomic-embed-text",
                    },
                    {
                        "name": "api_endpoint",
                        "type": "string",
                        "description": "Ollama API embeddings endpoint URL",
                        "default": default_endpoint,
                    },
                ],
            }
        ]
    }


def _make_creator_user(email="user@example.com"):
    return {"id": 1, "email": email, "name": "U"}


def _make_ks_config():
    """Match _get_ks_config's return shape for tests."""
    return {
        "url": "http://kb-server-v2:9092",
        "token": "test-token",
        "allowed_vector_db_backends": [],
        "allowed_chunking_strategies": [],
        "allowed_embedding_vendors": [],
        "allowed_embedding_models": {},
    }


@pytest.mark.asyncio
async def test_get_org_options_overrides_endpoint_from_org_config():
    """When the org has providers.ollama.endpoint set, the api_endpoint
    parameter default in the /options response must reflect that endpoint
    and not the kb-server-v2 plugin's static localhost default."""
    client = KnowledgeStoreClient()

    with patch.object(
        client, "_get_ks_config", return_value=_make_ks_config()
    ), patch.object(
        client, "get_backends", new=AsyncMock(return_value={"backends": []})
    ), patch.object(
        client,
        "get_chunking_strategies",
        new=AsyncMock(return_value={"strategies": []}),
    ), patch.object(
        client,
        "get_embedding_vendors",
        new=AsyncMock(return_value=_ollama_vendors_payload()),
    ), patch(
        "creator_interface.knowledge_store_client.OrganizationConfigResolver"
    ) as MockResolver:
        resolver_instance = MockResolver.return_value
        resolver_instance.get_provider_endpoint.return_value = (
            "http://172.18.0.1:11434"
        )

        result = await client.get_org_options(_make_creator_user())

    ollama = next(
        v for v in result["embedding_vendors"] if v["name"] == "ollama"
    )
    api_endpoint_param = next(
        p for p in ollama["parameters"] if p["name"] == "api_endpoint"
    )
    assert api_endpoint_param["default"] == "http://172.18.0.1:11434"


@pytest.mark.asyncio
async def test_get_org_options_falls_back_to_plugin_default_when_org_unset():
    """When the org config has no providers.<vendor>.endpoint, the plugin's
    static default (e.g. http://localhost:11434/api/embeddings) must be
    preserved as-is."""
    client = KnowledgeStoreClient()
    static_default = "http://localhost:11434/api/embeddings"

    with patch.object(
        client, "_get_ks_config", return_value=_make_ks_config()
    ), patch.object(
        client, "get_backends", new=AsyncMock(return_value={"backends": []})
    ), patch.object(
        client,
        "get_chunking_strategies",
        new=AsyncMock(return_value={"strategies": []}),
    ), patch.object(
        client,
        "get_embedding_vendors",
        new=AsyncMock(
            return_value=_ollama_vendors_payload(default_endpoint=static_default)
        ),
    ), patch(
        "creator_interface.knowledge_store_client.OrganizationConfigResolver"
    ) as MockResolver:
        resolver_instance = MockResolver.return_value
        resolver_instance.get_provider_endpoint.return_value = ""

        result = await client.get_org_options(_make_creator_user())

    ollama = next(
        v for v in result["embedding_vendors"] if v["name"] == "ollama"
    )
    api_endpoint_param = next(
        p for p in ollama["parameters"] if p["name"] == "api_endpoint"
    )
    assert api_endpoint_param["default"] == static_default


@pytest.mark.asyncio
async def test_get_org_options_resolver_failure_does_not_break_options():
    """If the resolver raises, the options endpoint must still return the
    plugin-level defaults rather than raising."""
    client = KnowledgeStoreClient()

    with patch.object(
        client, "_get_ks_config", return_value=_make_ks_config()
    ), patch.object(
        client, "get_backends", new=AsyncMock(return_value={"backends": []})
    ), patch.object(
        client,
        "get_chunking_strategies",
        new=AsyncMock(return_value={"strategies": []}),
    ), patch.object(
        client,
        "get_embedding_vendors",
        new=AsyncMock(return_value=_ollama_vendors_payload()),
    ), patch(
        "creator_interface.knowledge_store_client.OrganizationConfigResolver",
        side_effect=RuntimeError("boom"),
    ):
        result = await client.get_org_options(_make_creator_user())

    ollama = next(
        v for v in result["embedding_vendors"] if v["name"] == "ollama"
    )
    api_endpoint_param = next(
        p for p in ollama["parameters"] if p["name"] == "api_endpoint"
    )
    assert (
        api_endpoint_param["default"]
        == "http://localhost:11434/api/embeddings"
    )


# ---------------------------------------------------------------------------
# Unavailable-KB-Server behavior (Agent E refactor — issue #334 §5).
#
# The hardcoded ``_BUILTIN_BACKENDS`` / ``_BUILTIN_STRATEGIES`` /
# ``_BUILTIN_VENDORS`` fallbacks were removed: when the KB Server is
# unreachable, the discovery methods must raise ``KnowledgeStoreUnavailable``
# instead of silently returning stale plugin data.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_org_options_raises_when_kb_server_unreachable():
    """When the live registries can't be read, ``get_org_options`` must
    raise the typed ``KnowledgeStoreUnavailable`` exception so the router
    can return a structured 503 to the UI (no hardcoded fallback)."""
    client = KnowledgeStoreClient()

    async def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    with patch.object(
        client, "_get_ks_config", return_value=_make_ks_config()
    ), patch(
        "creator_interface.knowledge_store_client.httpx.AsyncClient.request",
        new=_boom,
    ):
        with pytest.raises(KnowledgeStoreUnavailable):
            await client.get_org_options(_make_creator_user())


@pytest.mark.asyncio
async def test_get_org_options_raises_when_kb_server_not_configured():
    """If ``LAMB_KB_SERVER_V2`` is not set, ``get_org_options`` must raise
    ``KnowledgeStoreUnavailable`` rather than fall back to a static catalog."""
    client = KnowledgeStoreClient()
    client.global_server_url = ""
    client.global_token = ""

    with patch(
        "creator_interface.knowledge_store_client.OrganizationConfigResolver",
        side_effect=RuntimeError("no org config"),
    ):
        with pytest.raises(KnowledgeStoreUnavailable):
            await client.get_org_options(_make_creator_user())


@pytest.mark.asyncio
async def test_get_backends_translates_500_to_unavailable():
    """A 5xx from the KB Server must be mapped to ``KnowledgeStoreUnavailable``
    so the options endpoint can surface a structured error to the UI."""
    client = KnowledgeStoreClient()

    class _FakeResp:
        is_success = False
        status_code = 500
        text = "internal error"
        content = b"internal error"

        def json(self):
            return {"detail": "internal error"}

    async def _fake_request(self, method, url, **kwargs):  # noqa: ARG001
        return _FakeResp()

    with patch.object(
        client, "_get_ks_config", return_value=_make_ks_config()
    ), patch(
        "creator_interface.knowledge_store_client.httpx.AsyncClient.request",
        new=_fake_request,
    ):
        with pytest.raises(KnowledgeStoreUnavailable):
            await client.get_backends(_make_creator_user())


# ---------------------------------------------------------------------------
# Invariant: the hardcoded fallback constants must NOT come back.
# This is a cheap grep-style regression check at the source level so a
# future refactor can't quietly re-introduce ``_BUILTIN_BACKENDS`` /
# ``_BUILTIN_STRATEGIES`` / ``_BUILTIN_VENDORS`` and silently hide new
# plugins behind a stale catalog whenever the KB Server is briefly down.
# ---------------------------------------------------------------------------


def test_knowledge_store_client_has_no_builtin_fallback_constants():
    """Source-level check: the three ``_BUILTIN_*`` constants must remain
    deleted. Comment / docstring mentions are tolerated; what we forbid is
    a Python assignment that resurrects the literal list."""
    source = (
        Path(__file__).parent.parent
        / "creator_interface"
        / "knowledge_store_client.py"
    ).read_text()
    for forbidden in (
        "_BUILTIN_BACKENDS: List",
        "_BUILTIN_STRATEGIES: List",
        "_BUILTIN_VENDORS: List",
        "_BUILTIN_BACKENDS = [",
        "_BUILTIN_STRATEGIES = [",
        "_BUILTIN_VENDORS = [",
    ):
        assert forbidden not in source, (
            f"Forbidden hardcoded fallback constant resurfaced: {forbidden!r}. "
            "The KB Server registries are the single source of truth — when "
            "unreachable, raise KnowledgeStoreUnavailable instead of falling "
            "back to a stale catalog."
        )
