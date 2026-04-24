"""Tests for the system router: /health, /backends, /chunking-strategies, /embedding-vendors."""

import pytest
from httpx import AsyncClient

from tests.conftest import AUTH_HEADERS


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "kb-server"
    assert body["version"] == "1.0.0"
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["worker"] == "ok"


@pytest.mark.asyncio
async def test_health_is_public(client: AsyncClient) -> None:
    """Health must not require auth — it's used by orchestrators."""
    response = await client.get("/health")  # no headers
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_backends_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/backends")
    # HTTPBearer returns 403 when missing (some FastAPI builds may return 401).
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_backends_rejects_bad_token(client: AsyncClient) -> None:
    response = await client.get(
        "/backends", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_backends_lists_chromadb(client: AsyncClient) -> None:
    response = await client.get("/backends", headers=AUTH_HEADERS)
    assert response.status_code == 200
    names = [b["name"] for b in response.json()["backends"]]
    assert "chromadb" in names


@pytest.mark.asyncio
async def test_chunking_strategies_lists_all_four(client: AsyncClient) -> None:
    response = await client.get(
        "/chunking-strategies", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    names = [s["name"] for s in response.json()["strategies"]]
    for expected in ("simple", "hierarchical", "by_page", "by_section"):
        assert expected in names, f"{expected} missing; got {names}"


@pytest.mark.asyncio
async def test_chunking_strategy_has_parameters(client: AsyncClient) -> None:
    response = await client.get(
        "/chunking-strategies", headers=AUTH_HEADERS
    )
    simple = next(
        s for s in response.json()["strategies"] if s["name"] == "simple"
    )
    param_names = {p["name"] for p in simple["parameters"]}
    assert "chunk_size" in param_names
    assert "chunk_overlap" in param_names


@pytest.mark.asyncio
async def test_embedding_vendors_includes_fake_and_openai(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/embedding-vendors", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    names = [v["name"] for v in response.json()["vendors"]]
    # 'fake' is registered by conftest; 'openai' and 'ollama' are real plugins.
    assert "fake" in names
    assert "openai" in names or "ollama" in names
