"""Import routes: file upload, URL import, YouTube import."""

import json
import logging
import time
import uuid
from pathlib import Path

from config import DATA_DIR, MAX_UPLOAD_SIZE_BYTES
from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from plugins.base import PluginRegistry
from schemas.content import (
    ImportAcceptedResponse,
    UrlImportRequest,
    YoutubeImportRequest,
)
from services import import_service
from services.library_service import get_library
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/libraries", tags=["Importing"], dependencies=[Depends(verify_token)])

# Temporary upload directory — files are moved to permanent storage by the worker.
_UPLOAD_DIR = DATA_DIR / "tmp-uploads"

# Maximum age (seconds) for files in the temp upload directory before purging.
_UPLOAD_MAX_AGE_SECONDS = 2 * 60 * 60  # 2 hours


def purge_stale_uploads() -> None:
    """Remove temp upload files older than ``_UPLOAD_MAX_AGE_SECONDS``.

    Called once at startup (via lifespan) and can be called periodically.
    Errors on individual files are logged and skipped so the purge is
    best-effort.
    """
    if not _UPLOAD_DIR.exists():
        return
    cutoff = time.time() - _UPLOAD_MAX_AGE_SECONDS
    removed = 0
    for entry in _UPLOAD_DIR.iterdir():
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
                removed += 1
        except OSError:
            logger.warning("Failed to remove stale upload %s", entry, exc_info=True)
    if removed:
        logger.info("Purged %d stale upload(s) from %s", removed, _UPLOAD_DIR)


@router.post(
    "/{lib_id}/import/file",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportAcceptedResponse,
)
async def import_file(
    lib_id: str,
    file: UploadFile = File(...),
    plugin_name: str = Form(...),
    title: str = Form(...),
    plugin_params: str = Form("{}"),
    api_keys: str = Form("{}"),
    db: Session = Depends(get_session),
) -> dict:
    """Upload a file and queue it for import.

    The file is saved to a temporary directory. The background worker
    picks up the job, runs the plugin, writes structured content, and
    updates the status.

    Args:
        lib_id: Library UUID.
        file: The uploaded file.
        plugin_name: Import plugin to use.
        title: Document title.
        plugin_params: JSON string of plugin parameters.
        api_keys: JSON string of API keys (held only during processing).
        db: Database session.

    Returns:
        Accepted response with item_id and job_id.
    """
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")

    plugin = PluginRegistry.get_plugin(plugin_name)
    if plugin is None:
        raise HTTPException(
            status_code=400,
            detail=f"Import plugin '{plugin_name}' not found or disabled.",
        )

    if "file" not in plugin.supported_source_types:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin '{plugin_name}' does not support file uploads. "
                   f"Supported sources: {', '.join(sorted(plugin.supported_source_types))}",
        )

    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if plugin.supported_file_types and ext not in plugin.supported_file_types:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin '{plugin_name}' does not support .{ext} files. "
                   f"Supported: {', '.join(sorted(plugin.supported_file_types))}",
        )

    try:
        parsed_params = json.loads(plugin_params) if plugin_params else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid plugin_params JSON.") from exc

    try:
        parsed_keys = json.loads(api_keys) if api_keys else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid api_keys JSON.") from exc

    # Sanitize the original filename (prevent path traversal in temp dir).
    safe_filename = Path(file.filename or "unnamed").name.replace("\x00", "")
    if not safe_filename or safe_filename in (".", ".."):
        safe_filename = "unnamed"

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = _UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_filename}"
    try:
        bytes_written = 0
        with temp_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_SIZE_BYTES:
                    temp_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum upload size "
                               f"({MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB).",
                    )
                f.write(chunk)
    finally:
        await file.close()

    file_size = temp_path.stat().st_size

    try:
        item_id, job_id = import_service.queue_file_import(
            db=db,
            library_id=lib_id,
            organization_id=lib.organization_id,
            title=title,
            plugin_name=plugin_name,
            file_path=str(temp_path),
            original_filename=file.filename or "unnamed",
            content_type=file.content_type,
            file_size=file_size,
            plugin_params=parsed_params,
            api_keys=parsed_keys,
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return {"item_id": item_id, "job_id": job_id, "status": "processing"}


@router.post(
    "/{lib_id}/import/url",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportAcceptedResponse,
)
async def import_url(
    lib_id: str,
    body: UrlImportRequest,
    db: Session = Depends(get_session),
) -> dict:
    """Queue a URL for import.

    Args:
        lib_id: Library UUID.
        body: URL import parameters.
        db: Database session.

    Returns:
        Accepted response with item_id and job_id.
    """
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")

    plugin = PluginRegistry.get_plugin(body.plugin_name)
    if plugin is None:
        raise HTTPException(
            status_code=400,
            detail=f"Import plugin '{body.plugin_name}' not found or disabled.",
        )

    if "url" not in plugin.supported_source_types:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin '{body.plugin_name}' does not support URL imports.",
        )

    item_id, job_id = import_service.queue_url_import(
        db=db,
        library_id=lib_id,
        organization_id=lib.organization_id,
        title=body.title,
        plugin_name=body.plugin_name,
        url=body.url,
        plugin_params=body.plugin_params,
        api_keys=body.api_keys,
    )

    return {"item_id": item_id, "job_id": job_id, "status": "processing"}


@router.post(
    "/{lib_id}/import/youtube",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportAcceptedResponse,
)
async def import_youtube(
    lib_id: str,
    body: YoutubeImportRequest,
    db: Session = Depends(get_session),
) -> dict:
    """Queue a YouTube video for transcript import.

    Args:
        lib_id: Library UUID.
        body: YouTube import parameters.
        db: Database session.

    Returns:
        Accepted response with item_id and job_id.
    """
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")

    plugin = PluginRegistry.get_plugin(body.plugin_name)
    if plugin is None:
        raise HTTPException(
            status_code=400,
            detail=f"Import plugin '{body.plugin_name}' not found or disabled.",
        )

    if "youtube" not in plugin.supported_source_types:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin '{body.plugin_name}' does not support YouTube imports.",
        )

    # Merge language into plugin_params.
    params = body.plugin_params or {}
    params["language"] = body.language

    item_id, job_id = import_service.queue_youtube_import(
        db=db,
        library_id=lib_id,
        organization_id=lib.organization_id,
        title=body.title,
        plugin_name=body.plugin_name,
        video_url=body.video_url,
        plugin_params=params,
        api_keys=body.api_keys,
    )

    return {"item_id": item_id, "job_id": job_id, "status": "processing"}
