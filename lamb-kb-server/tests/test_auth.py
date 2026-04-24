"""Bearer-token authentication tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_authorization_header(client: AsyncClient) -> None:
    """Missing Authorization header must be rejected."""
    r = await client.get("/collections")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_wrong_token_rejected(client: AsyncClient) -> None:
    r = await client.get(
        "/collections", headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_malformed_bearer(client: AsyncClient) -> None:
    r = await client.get(
        "/collections", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_correct_token_accepted(client: AsyncClient) -> None:
    r = await client.get(
        "/collections", headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 200
