"""
Tests for knowledge_store_client.get_org_options — verifies that the
``/creator/knowledge-stores/options`` endpoint overrides the embedding
plugins' static ``api_endpoint`` default with the org-level
``setups[default].providers[<vendor>].endpoint`` so the UI's "create
Knowledge Store" form pre-fills with an endpoint that is reachable from
the kb-server-v2 container.

Regression test for defect D1 (lifecycle 2026-05-03).
"""

from unittest.mock import patch, AsyncMock

import pytest

from creator_interface.knowledge_store_client import KnowledgeStoreClient


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
