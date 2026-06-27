"""Branch-coverage tests for org_config_resolver Knowledge Store / provider helpers.

These exercise ``get_knowledge_store_config``, ``get_provider_api_key`` and
``get_provider_endpoint`` directly by constructing an
``OrganizationConfigResolver`` and pre-seeding its lazily loaded ``_org`` so
no real DB is touched (``LambDatabaseManager`` is also patched at construction).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lamb.completions.org_config_resolver import OrganizationConfigResolver


def make_resolver(org: dict, setup_name: str = "default") -> OrganizationConfigResolver:
    """Build a resolver whose organization is pre-seeded (no DB access)."""
    with patch(
        "lamb.completions.org_config_resolver.LambDatabaseManager",
        return_value=MagicMock(name="db_manager"),
    ):
        resolver = OrganizationConfigResolver("owner@example.com", setup_name)
    resolver._org = org  # skip lazy DB load
    return resolver


# ---------------------------------------------------------------------------
# get_knowledge_store_config  (lines 165-168, 170-171, 176-177, 190)
# ---------------------------------------------------------------------------


def test_ks_config_from_setup():
    """ks_config present in setup -> normalized dict returned (176-189)."""
    org = {
        "is_system": False,
        "config": {
            "setups": {
                "default": {
                    "knowledge_store": {
                        "url": "http://ks:9092",
                        "api_key": "secret",
                        "allowed_vector_db_backends": ["chromadb"],
                        "allowed_chunking_strategies": ["simple"],
                        "allowed_embedding_vendors": ["openai"],
                        "allowed_embedding_models": {"openai": ["text-embedding-3-small"]},
                    }
                }
            }
        },
    }
    result = make_resolver(org).get_knowledge_store_config()
    assert result["server_url"] == "http://ks:9092"
    assert result["api_token"] == "secret"
    assert result["allowed_vector_db_backends"] == ["chromadb"]
    assert result["allowed_chunking_strategies"] == ["simple"]
    assert result["allowed_embedding_vendors"] == ["openai"]
    assert result["allowed_embedding_models"] == {"openai": ["text-embedding-3-small"]}


def test_ks_config_token_precedence():
    """server_url/api_token keys win over url/api_key/token aliases."""
    org = {
        "is_system": False,
        "config": {
            "setups": {
                "default": {
                    "knowledge_store": {
                        "server_url": "http://primary:9092",
                        "api_token": "primary-token",
                    }
                }
            }
        },
    }
    result = make_resolver(org).get_knowledge_store_config()
    assert result["server_url"] == "http://primary:9092"
    assert result["api_token"] == "primary-token"


def test_ks_config_empty_returns_empty_non_system():
    """No ks_config and not system org -> empty dict (line 190)."""
    org = {"is_system": False, "config": {"setups": {"default": {}}}}
    assert make_resolver(org).get_knowledge_store_config() == {}


def test_ks_config_env_fallback_system_org():
    """No ks_config but system org -> env fallback (lines 170-174)."""
    org = {"is_system": True, "config": {"setups": {"default": {}}}}
    env = {
        "LAMB_KB_SERVER_V2": "http://env-ks:9092",
        "LAMB_KB_SERVER_V2_TOKEN": "env-token",
    }
    with patch.dict("os.environ", env, clear=False):
        result = make_resolver(org).get_knowledge_store_config()
    assert result["server_url"] == "http://env-ks:9092"
    assert result["api_token"] == "env-token"


def test_ks_config_env_fallback_defaults():
    """System org, env vars unset -> defaulted url and empty token."""
    org = {"is_system": True, "config": {}}
    with patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        result = make_resolver(org).get_knowledge_store_config()
    assert result["server_url"] == "http://kb-server:9092"
    # empty-string env default falls through the ``or`` chain to None
    assert result["api_token"] is None


# ---------------------------------------------------------------------------
# get_provider_api_key  (lines 205-206)
# ---------------------------------------------------------------------------


def test_provider_api_key_present():
    org = {
        "is_system": False,
        "config": {
            "setups": {
                "default": {"providers": {"openai": {"api_key": "sk-123"}}}
            }
        },
    }
    assert make_resolver(org).get_provider_api_key("openai") == "sk-123"


def test_provider_api_key_missing_provider_returns_empty():
    """get_provider_config returns {} -> empty string (the falsy branch)."""
    org = {"is_system": False, "config": {"setups": {"default": {"providers": {}}}}}
    assert make_resolver(org).get_provider_api_key("openai") == ""


def test_provider_api_key_provider_without_key():
    """Provider config exists but no api_key key -> empty string."""
    org = {
        "is_system": False,
        "config": {
            "setups": {"default": {"providers": {"openai": {"models": ["gpt-4"]}}}}
        },
    }
    assert make_resolver(org).get_provider_api_key("openai") == ""


# ---------------------------------------------------------------------------
# get_provider_endpoint  (lines 219-226)
# ---------------------------------------------------------------------------


def test_provider_endpoint_missing_provider_returns_empty():
    """No provider config -> early empty return (lines 220-221)."""
    org = {"is_system": False, "config": {"setups": {"default": {"providers": {}}}}}
    assert make_resolver(org).get_provider_endpoint("openai") == ""


@pytest.mark.parametrize(
    "provider_cfg,expected",
    [
        ({"endpoint": "http://e1"}, "http://e1"),
        ({"base_url": "http://e2"}, "http://e2"),
        ({"api_endpoint": "http://e3"}, "http://e3"),
        # precedence: endpoint wins over later keys
        ({"endpoint": "http://e1", "base_url": "http://e2"}, "http://e1"),
    ],
)
def test_provider_endpoint_resolves_keys(provider_cfg, expected):
    """First of endpoint/base_url/api_endpoint that is set wins (222-225)."""
    org = {
        "is_system": False,
        "config": {
            "setups": {"default": {"providers": {"openai": provider_cfg}}}
        },
    }
    assert make_resolver(org).get_provider_endpoint("openai") == expected


def test_provider_endpoint_no_matching_key_returns_empty():
    """Provider config present but none of the endpoint keys set -> '' (line 226)."""
    org = {
        "is_system": False,
        "config": {
            "setups": {"default": {"providers": {"openai": {"api_key": "sk"}}}}
        },
    }
    assert make_resolver(org).get_provider_endpoint("openai") == ""
