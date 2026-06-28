"""Shared, dependency-light test helpers.

Consolidates the upload / poll / payload helpers that were copy-pasted across
the old flat test modules. Importable from any tier as ``from _helpers import
...`` (``tests/`` is on ``sys.path``).

Nothing here imports the application at module scope, so this module is safe to
import from the root ``conftest.py`` before the app is loaded.
"""

from __future__ import annotations

import io
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import httpx

# The single bearer token every tier authenticates with (matches the
# ``LAMB_API_TOKEN`` set in the root conftest before the app is imported).
AUTH_HEADERS: dict[str, str] = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Identifier factories — unique per call so tests isolate without DB resets.
# ---------------------------------------------------------------------------


def unique_id(prefix: str) -> str:
    """Return a short unique identifier like ``lib-3f9a1c2b``."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def library_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid ``POST /libraries`` body with a fresh id/org.

    Pass keyword overrides to change any field (e.g. ``organization_id``).
    """
    lib_id = overrides.pop("id", None) or unique_id("lib")
    payload = {
        "id": lib_id,
        "organization_id": "org-test",
        "name": f"Test Library {lib_id[-8:]}",
    }
    payload.update(overrides)
    return payload


def text_file(content: str = "# Hello\n\nWorld.", filename: str = "doc.md") -> dict[str, Any]:
    """Return ``files=`` kwargs for a multipart upload of a small text file."""
    return {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/markdown")}


def file_bytes(
    data: bytes, filename: str, mime: str = "application/octet-stream"
) -> dict[str, Any]:
    """Return ``files=`` kwargs for a multipart upload of raw bytes."""
    return {"file": (filename, io.BytesIO(data), mime)}


# ---------------------------------------------------------------------------
# Async polling (integration tier — in-process ASGI client)
# ---------------------------------------------------------------------------


async def poll_until_ready(
    client: httpx.AsyncClient,
    lib_id: str,
    item_id: str,
    *,
    timeout: float = 30.0,
    interval: float = 0.2,
) -> str:
    """Poll an item's status until it leaves the in-flight states.

    Returns the terminal status (``"ready"`` or ``"failed"``). Raises
    ``AssertionError`` with the last seen status if the item is still
    ``pending``/``processing`` after ``timeout`` seconds.
    """
    deadline = time.monotonic() + timeout
    last = "unknown"
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS
        )
        if resp.status_code == 200:
            last = resp.json()["status"]
            if last in ("ready", "failed"):
                return last
        import asyncio  # noqa: PLC0415

        await asyncio.sleep(interval)
    raise AssertionError(
        f"item {item_id} did not reach a terminal status within {timeout}s (last={last})"
    )


# ---------------------------------------------------------------------------
# Sync polling (e2e tier — real HTTP to a subprocess)
# ---------------------------------------------------------------------------


def poll_until_ready_sync(
    client: httpx.Client,
    lib_id: str,
    item_id: str,
    *,
    timeout: float = 30.0,
    interval: float = 0.3,
) -> str:
    """Synchronous twin of :func:`poll_until_ready` for the e2e tier."""
    deadline = time.monotonic() + timeout
    last = "unknown"
    while time.monotonic() < deadline:
        resp = client.get(f"/libraries/{lib_id}/items/{item_id}/status", headers=AUTH_HEADERS)
        if resp.status_code == 200:
            last = resp.json()["status"]
            if last in ("ready", "failed"):
                return last
        time.sleep(interval)
    raise AssertionError(
        f"item {item_id} did not reach a terminal status within {timeout}s (last={last})"
    )
