"""Capability handler endpoints.

Three concerns live here:

* ``GET /capabilities`` — list registered capability handlers (registry).
* ``GET /libraries/{lib_id}/items/{item_id}/capabilities`` — list the
  capabilities **this item actually has** (read from ``metadata.json``).
* ``GET /libraries/{lib_id}/items/{item_id}/content/{capability}`` —
  dispatch to the appropriate :class:`ContentHandler`.
* ``GET /libraries/{lib_id}/items/{item_id}/content/images/file/{filename}``
  — raw file serve for the images handler (declared on its payload URLs).

The image raw-serve route is declared on a separate ``raw_router`` whose
prefix is ``/libraries`` (parameterised on ``lib_id`` and ``item_id``); see
below for why it must be registered *before* the general content router so
its more-specific path wins.
"""

from __future__ import annotations

import logging
import mimetypes

from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from plugins.content_handlers.capability import (
    Capability,
    CapabilityRegistry,
    HandlerUnavailable,
)
from services import content_service
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry endpoint
# ---------------------------------------------------------------------------

registry_router = APIRouter(tags=["Capabilities"], dependencies=[Depends(verify_token)])


@registry_router.get("/capabilities")
async def list_registered_capabilities() -> dict:
    """List all registered capability handlers.

    Returns:
        ``{"capabilities": [{"capability": str, "description": str}, ...]}``.
        Sorted by capability value for deterministic output.
    """
    return {"capabilities": CapabilityRegistry.list_handlers()}


# ---------------------------------------------------------------------------
# Per-item endpoints
# ---------------------------------------------------------------------------
#
# Two routers are exposed for ordering reasons:
#   * ``raw_router`` — must be registered BEFORE the legacy content router
#     so its ``/content/images/file/{filename}`` literal beats the legacy
#     ``/content/images/{image_name}`` parameterised route.
#   * ``item_router`` — must be registered AFTER the legacy content router
#     so existing literal paths (``/content``, ``/content/pages`` etc.)
#     keep their original semantics; capability dispatch only catches
#     paths that don't already match (e.g. ``/content/text``).

raw_router = APIRouter(
    prefix="/libraries",
    tags=["Capabilities"],
    dependencies=[Depends(verify_token)],
)

item_router = APIRouter(
    prefix="/libraries",
    tags=["Capabilities"],
    dependencies=[Depends(verify_token)],
)


@raw_router.get(
    "/{lib_id}/items/{item_id}/content/images/file/{filename}",
    name="capability_image_raw_file",
)
async def get_capability_image_raw_file(
    lib_id: str,
    item_id: str,
    filename: str,
    db: Session = Depends(get_session),
) -> FileResponse:
    """Raw image file serve for URLs produced by the images handler.

    The images handler returns URLs of the form
    ``/libraries/{lib}/items/{item}/content/images/file/{filename}``.
    This route honours those URLs. The path is **more specific** than the
    existing ``/content/images/{image_name}`` route in ``content.py`` (it
    contains the literal ``file`` segment) so FastAPI will not collide
    with that route.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        filename: Image filename.
        db: Database session.

    Returns:
        The image file.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    path = content_service.get_image_path(item.organization_id, lib_id, item_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mime or "application/octet-stream")


@item_router.get("/{lib_id}/items/{item_id}/capabilities")
async def get_item_capabilities(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Return the capabilities this specific item exposes.

    Reads the ``capabilities`` field from ``metadata.json``. Legacy items
    imported before this field existed default to ``["text"]`` because
    every successful import wrote ``content/full.md``.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        ``{"item_id": str, "capabilities": [str, ...]}``.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    metadata = content_service.read_metadata_json(item.organization_id, lib_id, item_id)

    capabilities: list[str]
    if metadata and isinstance(metadata.get("capabilities"), list):
        capabilities = [str(c) for c in metadata["capabilities"]]
    else:
        # Legacy fallback: every pre-capability import wrote content/full.md.
        # Defaulting to TEXT keeps the UI functional for old items.
        capabilities = [Capability.TEXT.value]

    return {"item_id": item_id, "capabilities": capabilities}


@item_router.get("/{lib_id}/items/{item_id}/content/{capability}")
async def get_item_capability_content(
    lib_id: str,
    item_id: str,
    capability: str,
    db: Session = Depends(get_session),
) -> Response:
    """Dispatch to the registered handler for ``capability``.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        capability: Capability key (must match a :class:`Capability` value).
        db: Database session.

    Returns:
        The handler's payload. JSON payloads are returned as
        ``application/json``; text payloads honour the handler's mime type.

    Raises:
        HTTPException(404): If the item doesn't exist, the capability is
            unknown, or the item doesn't expose this capability.
    """
    try:
        capability_enum = Capability(capability)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown capability: {capability}",
        )

    handler = CapabilityRegistry.get(capability_enum)
    if handler is None:
        raise HTTPException(
            status_code=404,
            detail=f"No handler registered for capability: {capability}",
        )

    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    item_path = content_service.get_item_base_path(item.organization_id, lib_id, item_id)
    if not item_path.is_dir():
        raise HTTPException(status_code=404, detail="Item content missing on disk.")

    try:
        payload = handler.get(item_path)
    except HandlerUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception(
            "Capability handler %s failed for item %s",
            capability,
            item_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Capability handler {capability} failed",
        )

    if payload.mime == "application/json":
        return JSONResponse(content=payload.body)
    if isinstance(payload.body, bytes):
        return Response(content=payload.body, media_type=payload.mime)
    return Response(content=str(payload.body), media_type=payload.mime)
