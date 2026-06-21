"""Unit tests for ``creator_interface.knowledge_store_client.KnowledgeStoreClient``.

``httpx`` and ``OrganizationConfigResolver`` are mocked so nothing leaves the
process. Covers the request/header/config internals, every thin proxy method
(via a mocked ``_request``), discovery error-wrapping, the org-options
aggregation, and allow-list validation.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import creator_interface.knowledge_store_client as ksc
from creator_interface.knowledge_store_client import (
    KnowledgeStoreClient,
    KnowledgeStoreUnavailable,
)


def _cfg(**over):
    base = {
        "url": "http://kb", "token": "tok",
        "allowed_vector_db_backends": [], "allowed_chunking_strategies": [],
        "allowed_embedding_vendors": [], "allowed_embedding_models": {},
    }
    base.update(over)
    return base


@pytest.fixture
def client(monkeypatch):
    c = KnowledgeStoreClient()
    monkeypatch.setattr(c, "_get_ks_config", lambda creator_user=None: _cfg())
    return c


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _headers
# ---------------------------------------------------------------------------


def test_headers_requires_token():
    c = KnowledgeStoreClient()
    with pytest.raises(ValueError):
        c._headers("")
    assert c._headers("tok") == {"Authorization": "Bearer tok"}


# ---------------------------------------------------------------------------
# _get_ks_config
# ---------------------------------------------------------------------------


def test_get_ks_config_from_org_resolver(monkeypatch):
    class _Resolver:
        def __init__(self, email):
            pass

        def get_knowledge_store_config(self):
            return {
                "server_url": "http://org-kb",
                "api_token": "org-tok",
                "allowed_embedding_vendors": ["openai"],
            }

    monkeypatch.setattr(ksc, "OrganizationConfigResolver", _Resolver)
    cfg = KnowledgeStoreClient()._get_ks_config({"email": "u@x.com"})
    assert cfg["url"] == "http://org-kb"
    assert cfg["token"] == "org-tok"
    assert cfg["allowed_embedding_vendors"] == ["openai"]


def test_get_ks_config_resolver_error_falls_back_to_global(monkeypatch):
    class _Resolver:
        def __init__(self, email):
            raise RuntimeError("no config")

    monkeypatch.setattr(ksc, "OrganizationConfigResolver", _Resolver)
    c = KnowledgeStoreClient()
    c.global_server_url = "http://global-kb"
    cfg = c._get_ks_config({"email": "u@x.com"})
    assert cfg["url"] == "http://global-kb"


def test_get_ks_config_no_global_raises(monkeypatch):
    c = KnowledgeStoreClient()
    c.global_server_url = ""
    with pytest.raises(KnowledgeStoreUnavailable):
        c._get_ks_config(None)


# ---------------------------------------------------------------------------
# resolve_embedding_api_key
# ---------------------------------------------------------------------------


def test_resolve_embedding_api_key_no_email():
    assert KnowledgeStoreClient().resolve_embedding_api_key(None, "openai") == ""


def test_resolve_embedding_api_key_success(monkeypatch):
    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_api_key(self, vendor):
            return "sk-org"

    monkeypatch.setattr(ksc, "OrganizationConfigResolver", _Resolver)
    out = KnowledgeStoreClient().resolve_embedding_api_key({"email": "u@x.com"}, "openai")
    assert out == "sk-org"


def test_resolve_embedding_api_key_resolver_error(monkeypatch):
    class _Resolver:
        def __init__(self, email):
            raise RuntimeError("boom")

    monkeypatch.setattr(ksc, "OrganizationConfigResolver", _Resolver)
    assert KnowledgeStoreClient().resolve_embedding_api_key({"email": "u@x.com"}, "x") == ""


# ---------------------------------------------------------------------------
# _wrap_discovery_error
# ---------------------------------------------------------------------------


def test_wrap_discovery_error():
    assert isinstance(
        KnowledgeStoreClient._wrap_discovery_error(HTTPException(503, "down")),
        KnowledgeStoreUnavailable,
    )
    assert KnowledgeStoreClient._wrap_discovery_error(HTTPException(400, "bad")) is None


# ---------------------------------------------------------------------------
# _request (httpx mocked)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, *, success=True, status=200, content=b"{}", payload=None,
                 text="", raise_json=False):
        self.is_success = success
        self.status_code = status
        self.content = content
        self._payload = payload if payload is not None else {}
        self.text = text
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


def _install_httpx(monkeypatch, *, response=None, request_error=None):
    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, headers=None, **kwargs):
            if request_error is not None:
                raise request_error
            return response

        async def post(self, url, headers=None, **kwargs):
            if request_error is not None:
                raise request_error
            return response

    monkeypatch.setattr(ksc.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        ksc.httpx, "RequestError", ksc.httpx.RequestError, raising=False
    )


def test_request_success_json(client, monkeypatch):
    _install_httpx(monkeypatch, response=_Resp(payload={"k": "v"}, content=b"{}"))
    out = run(client._request("GET", "/x", _cfg()))
    assert out == {"k": "v"}


def test_request_204_empty(client, monkeypatch):
    _install_httpx(monkeypatch, response=_Resp(content=b""))
    assert run(client._request("DELETE", "/x", _cfg(), expect_204=True)) == {}


def test_request_error_with_json_detail(client, monkeypatch):
    _install_httpx(
        monkeypatch,
        response=_Resp(success=False, status=409, payload={"detail": "conflict"}),
    )
    with pytest.raises(HTTPException) as exc:
        run(client._request("POST", "/x", _cfg()))
    assert exc.value.status_code == 409
    assert "conflict" in exc.value.detail


def test_request_error_non_json_text(client, monkeypatch):
    _install_httpx(
        monkeypatch,
        response=_Resp(success=False, status=500, text="boom", raise_json=True),
    )
    with pytest.raises(HTTPException) as exc:
        run(client._request("POST", "/x", _cfg()))
    assert exc.value.status_code == 500


def test_request_connection_error_503(client, monkeypatch):
    _install_httpx(monkeypatch, request_error=ksc.httpx.ConnectError("refused"))
    with pytest.raises(HTTPException) as exc:
        run(client._request("GET", "/x", _cfg()))
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# proxy methods (mock _request)
# ---------------------------------------------------------------------------


@pytest.fixture
def proxied(client):
    client._request = AsyncMock(return_value={"ok": True})
    return client


def _last_call(c):
    args, kwargs = c._request.call_args
    return args, kwargs


def test_create_collection_payload(proxied):
    run(proxied.create_collection(
        knowledge_store_id="ks1", organization_id=5, name="N",
        chunking_strategy="simple", embedding_vendor="openai",
        embedding_model="m", vector_db_backend="chromadb",
        graph_enabled=True, extraction_vendor="openai", extraction_model="gpt",
    ))
    args, kwargs = _last_call(proxied)
    assert args[0] == "POST" and args[1] == "/collections"
    payload = kwargs["json"]
    assert payload["id"] == "ks1"
    assert payload["graph_enabled"] is True
    assert payload["extraction"]["vendor"] == "openai"


def test_create_collection_no_extraction_when_graph_disabled(proxied):
    run(proxied.create_collection(
        knowledge_store_id="ks1", organization_id=5, name="N",
        chunking_strategy="simple", embedding_vendor="openai",
        embedding_model="m", vector_db_backend="chromadb",
        graph_enabled=False, extraction_vendor="openai",
    ))
    _, kwargs = _last_call(proxied)
    assert "extraction" not in kwargs["json"]


def test_simple_proxy_methods(proxied):
    cases = [
        (proxied.get_llm_vendors(), "GET", "/llm-vendors"),
        (proxied.get_collection("ks1"), "GET", "/collections/ks1"),
        (proxied.delete_collection("ks1"), "DELETE", "/collections/ks1"),
        (proxied.delete_content_by_source("ks1", "src1"), "DELETE",
         "/collections/ks1/content/src1"),
        (proxied.get_job_status("j1"), "GET", "/jobs/j1"),
        (proxied.cancel_job("j1"), "POST", "/jobs/j1/cancel"),
        (proxied.get_graph_status(), "GET", "/graph/status"),
    ]
    for coro, method, path in cases:
        proxied._request.reset_mock()
        run(coro)
        args, _ = _last_call(proxied)
        assert (args[0], args[1]) == (method, path)


def test_update_collection_builds_partial_body(proxied):
    run(proxied.update_collection("ks1", name="New", chunking_params={"x": 1}))
    args, kwargs = _last_call(proxied)
    assert args[0] == "PUT"
    assert kwargs["json"] == {"name": "New", "chunking_params": {"x": 1}}


def test_add_content_and_query_payloads(proxied):
    run(proxied.add_content("ks1", [{"d": 1}], embedding_api_key="sk"))
    _, kwargs = _last_call(proxied)
    assert kwargs["json"]["embedding_credentials"]["api_key"] == "sk"

    proxied._request.reset_mock()
    run(proxied.query("ks1", "hello", embedding_api_key="sk", top_k=7))
    args, kwargs = _last_call(proxied)
    assert args[1] == "/collections/ks1/query"
    assert kwargs["json"]["top_k"] == 7


def test_graph_proxy_methods(proxied):
    cases = [
        (proxied.get_graph_snapshot("ks1", params={"limit": 1}), "GET",
         "/graph/collections/ks1/snapshot"),
        (proxied.list_graph_changes("ks1", params={}), "GET",
         "/graph/collections/ks1/changes"),
        (proxied.graph_concept_rename("ks1", "alpha", {"new_name": "b"}), "PATCH",
         "/graph/collections/ks1/concepts/alpha/rename"),
        (proxied.graph_concepts_merge("ks1", {"target_name": "t"}), "POST",
         "/graph/collections/ks1/concepts/merge"),
        (proxied.graph_concept_curation("ks1", "alpha", {}), "PATCH",
         "/graph/collections/ks1/concepts/alpha/curation"),
        (proxied.graph_relationship_edit("ks1", {}), "PATCH",
         "/graph/collections/ks1/relationships"),
        (proxied.graph_relationship_curation("ks1", {}), "PATCH",
         "/graph/collections/ks1/relationships/curation"),
    ]
    for coro, method, path in cases:
        proxied._request.reset_mock()
        run(coro)
        args, _ = _last_call(proxied)
        assert (args[0], args[1]) == (method, path)


# ---------------------------------------------------------------------------
# discovery error wrapping
# ---------------------------------------------------------------------------


def test_get_backends_success(client):
    client._request = AsyncMock(return_value={"backends": [{"name": "chromadb"}]})
    assert run(client.get_backends())["backends"][0]["name"] == "chromadb"


def test_get_backends_5xx_wrapped(client):
    client._request = AsyncMock(side_effect=HTTPException(503, "down"))
    with pytest.raises(KnowledgeStoreUnavailable):
        run(client.get_backends())


def test_get_chunking_strategies_4xx_reraised(client):
    client._request = AsyncMock(side_effect=HTTPException(400, "bad"))
    with pytest.raises(HTTPException) as exc:
        run(client.get_chunking_strategies())
    assert exc.value.status_code == 400


def test_get_chunking_strategies_5xx_wrapped(client):
    client._request = AsyncMock(side_effect=HTTPException(502, "down"))
    with pytest.raises(KnowledgeStoreUnavailable):
        run(client.get_chunking_strategies())


def test_get_embedding_vendors_5xx_wrapped(client):
    client._request = AsyncMock(side_effect=HTTPException(500, "boom"))
    with pytest.raises(KnowledgeStoreUnavailable):
        run(client.get_embedding_vendors())


def test_get_backends_4xx_reraised(client):
    client._request = AsyncMock(side_effect=HTTPException(403, "forbidden"))
    with pytest.raises(HTTPException) as exc:
        run(client.get_backends())
    assert exc.value.status_code == 403


def test_get_embedding_vendors_4xx_reraised(client):
    client._request = AsyncMock(side_effect=HTTPException(404, "missing"))
    with pytest.raises(HTTPException) as exc:
        run(client.get_embedding_vendors())
    assert exc.value.status_code == 404


def test_update_collection_description_only(proxied):
    run(proxied.update_collection("ks1", description="desc only"))
    _, kwargs = _last_call(proxied)
    assert kwargs["json"] == {"description": "desc only"}


# ---------------------------------------------------------------------------
# migrate_collection_to_graph (httpx mocked)
# ---------------------------------------------------------------------------


def test_migrate_success_with_key(client, monkeypatch):
    _install_httpx(monkeypatch, response=_Resp(payload={"status": "ok"}, content=b"{}"))
    out = run(client.migrate_collection_to_graph("ks1", openai_api_key="sk"))
    assert out == {"status": "ok"}


def test_migrate_error(client, monkeypatch):
    _install_httpx(
        monkeypatch,
        response=_Resp(success=False, status=503, payload={"detail": "no neo4j"}),
    )
    with pytest.raises(HTTPException) as exc:
        run(client.migrate_collection_to_graph("ks1"))
    assert exc.value.status_code == 503


def test_migrate_connection_error(client, monkeypatch):
    _install_httpx(monkeypatch, request_error=ksc.httpx.ConnectError("refused"))
    with pytest.raises(HTTPException) as exc:
        run(client.migrate_collection_to_graph("ks1"))
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# get_org_options
# ---------------------------------------------------------------------------


def _vendor(name, *, model_default="m", endpoint_default="http://static"):
    return {
        "name": name,
        "parameters": [
            {"name": "model", "default": model_default},
            {"name": "api_endpoint", "default": endpoint_default},
        ],
    }


def test_get_org_options_no_user(monkeypatch):
    c = KnowledgeStoreClient()
    monkeypatch.setattr(c, "_get_ks_config", lambda cu=None: _cfg())
    c.get_backends = AsyncMock(return_value={"backends": [{"name": "chromadb"}]})
    c.get_chunking_strategies = AsyncMock(
        return_value={"strategies": [{"name": "simple"}]})
    c.get_embedding_vendors = AsyncMock(
        return_value={"vendors": [_vendor("openai")]})
    out = run(c.get_org_options(None))
    assert out["vector_db_backends"][0]["name"] == "chromadb"
    # No user -> api_key_configured defaults True; model fallback from plugin.
    assert out["embedding_vendors"][0]["api_key_configured"] is True
    assert out["embedding_models"]["openai"] == ["m"]


def test_get_org_options_with_org_config(monkeypatch):
    c = KnowledgeStoreClient()
    monkeypatch.setattr(
        c, "_get_ks_config",
        lambda cu=None: _cfg(allowed_embedding_vendors=["openai"],
                             allowed_embedding_models={"openai": ["text-embed-3"]}),
    )
    c.get_backends = AsyncMock(return_value={"backends": [{"name": "chromadb"}]})
    c.get_chunking_strategies = AsyncMock(return_value={"strategies": []})
    c.get_embedding_vendors = AsyncMock(
        return_value={"vendors": [_vendor("openai"), _vendor("cohere")]})

    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_config(self, vendor):
            return {"api_key": "sk"} if vendor == "openai" else {}

        def get_provider_endpoint(self, vendor):
            return "http://org-endpoint"

    monkeypatch.setattr(ksc, "OrganizationConfigResolver", _Resolver)
    out = run(c.get_org_options({"email": "u@x.com"}))
    # allow-list trims to openai only.
    assert [v["name"] for v in out["embedding_vendors"]] == ["openai"]
    vendor = out["embedding_vendors"][0]
    assert vendor["api_key_configured"] is True
    # org endpoint overrode the static default.
    ep = next(p for p in vendor["parameters"] if p["name"] == "api_endpoint")
    assert ep["default"] == "http://org-endpoint"
    # explicit allowed-models list wins over plugin fallback.
    assert out["embedding_models"]["openai"] == ["text-embed-3"]


def test_get_org_options_resolver_edge_branches(monkeypatch):
    c = KnowledgeStoreClient()
    monkeypatch.setattr(c, "_get_ks_config", lambda cu=None: _cfg())
    c.get_backends = AsyncMock(return_value={"backends": []})
    c.get_chunking_strategies = AsyncMock(return_value={"strategies": []})
    # One nameless vendor (skipped) + one whose provider lookups raise.
    c.get_embedding_vendors = AsyncMock(return_value={
        "vendors": [{"parameters": []}, _vendor("openai")],
    })

    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_config(self, vendor):
            raise RuntimeError("no provider cfg")

        def get_provider_endpoint(self, vendor):
            raise ValueError("no endpoint")

    monkeypatch.setattr(ksc, "OrganizationConfigResolver", _Resolver)
    out = run(c.get_org_options({"email": "u@x.com"}))
    # The nameless vendor is preserved in the list but skipped for tagging;
    # openai gets api_key_configured=False (provider cfg lookup failed).
    openai = next(v for v in out["embedding_vendors"] if v.get("name") == "openai")
    assert openai["api_key_configured"] is False


# ---------------------------------------------------------------------------
# validate_against_allow_list
# ---------------------------------------------------------------------------


def test_validate_all_allowed_returns_none(monkeypatch):
    c = KnowledgeStoreClient()
    monkeypatch.setattr(c, "_get_ks_config", lambda cu=None: _cfg())
    assert c.validate_against_allow_list(
        {}, "simple", "openai", "m", "chromadb") is None


@pytest.mark.parametrize(
    "field,cfg_key,bad",
    [
        ("chunking", "allowed_chunking_strategies", "Chunking strategy"),
        ("vendor", "allowed_embedding_vendors", "Embedding vendor"),
        ("backend", "allowed_vector_db_backends", "Vector DB backend"),
    ],
)
def test_validate_rejects_disallowed(monkeypatch, field, cfg_key, bad):
    c = KnowledgeStoreClient()
    cfg = _cfg(**{cfg_key: ["allowed-only"]})
    monkeypatch.setattr(c, "_get_ks_config", lambda cu=None: cfg)
    msg = c.validate_against_allow_list(
        {}, "simple", "openai", "m", "chromadb")
    assert bad in msg


def test_validate_rejects_disallowed_model(monkeypatch):
    c = KnowledgeStoreClient()
    cfg = _cfg(allowed_embedding_models={"openai": ["good-model"]})
    monkeypatch.setattr(c, "_get_ks_config", lambda cu=None: cfg)
    msg = c.validate_against_allow_list({}, "simple", "openai", "bad-model", "chromadb")
    assert "Embedding model" in msg
