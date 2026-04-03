"""Async HTTP client for liteshell — calls Creator Interface via ASGI transport.

Uses httpx.AsyncClient with ASGITransport to call the FastAPI app
directly in-process. No TCP, no worker contention, no deadlock.
Same code path as external HTTP clients (frontend, lamb-cli) —
all Creator Interface validation and auth applies.
"""

from __future__ import annotations

from typing import Any

import httpx

from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")


class AsyncLambClient:
    """In-process async HTTP client for LAMB Creator Interface.

    Uses ASGI transport to call the FastAPI app directly — avoids the
    TCP deadlock that occurs when a single-worker uvicorn server tries
    to call itself over HTTP.
    """

    def __init__(self, token: str):
        from main import app  # the FastAPI app instance
        self._transport = httpx.ASGITransport(app=app)
        self._token = token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                transport=self._transport,
                base_url="http://lamb-internal",  # dummy, ASGI ignores it
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=60.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        return await self._request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self._request("DELETE", path, **kwargs)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        client = await self._get_client()
        try:
            resp = await client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ValueError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ValueError(f"HTTP error: {exc}") from exc
        return self._handle_response(resp)

    def _handle_response(self, resp: httpx.Response) -> Any:
        if resp.is_success:
            if not resp.content:
                return {}
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                return resp.json()
            return resp.text
        # Map errors
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text or f"HTTP {resp.status_code}"
        raise ValueError(f"API error ({resp.status_code}): {detail}")
