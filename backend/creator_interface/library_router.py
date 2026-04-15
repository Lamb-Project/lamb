"""Creator Interface routes for library management.

Each endpoint: authenticate -> check ACL -> resolve org config -> call Library
Manager -> update LAMB DB -> audit log -> return response.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from lamb.auth_context import AuthContext, get_auth_context
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.database_manager import LambDatabaseManager

from .library_manager_client import LibraryManagerClient

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB


class LibraryCreate(BaseModel):
    name: str
    description: str = ""

class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class LibraryShareToggle(BaseModel):
    is_shared: bool

class URLImportRequest(BaseModel):
    url: str
    plugin_name: str = "url_import"
    title: Optional[str] = None
    plugin_params: Optional[Dict[str, Any]] = None

class YouTubeImportRequest(BaseModel):
    video_url: str
    language: str = "en"
    title: Optional[str] = None
    plugin_name: str = "youtube_transcript_import"


router = APIRouter()
_client = LibraryManagerClient()
_db = LambDatabaseManager()


def _audit(auth: AuthContext, action: str, target_type: str, target_id: str,
           details: dict = None):
    """Write an audit log entry for the current user's action."""
    _db.write_audit_log(
        organization_id=auth.organization.get("id"),
        actor_user_id=auth.user.get("id"),
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


def _resolve_api_keys(auth: AuthContext) -> dict:
    """Resolve org-level API keys for import plugins."""
    try:
        resolver = OrganizationConfigResolver(auth.user.get("email"))
        lib_config = resolver.get_library_config()
        return lib_config.get("external_service_keys", {})
    except Exception as e:
        logger.warning(f"Could not resolve API keys for {auth.user.get('email')}: {e}")
        return {}


# ------------------------------------------------------------------
# Static routes MUST be registered before parameterized /{library_id}
# to prevent FastAPI from matching "plugins" or "import" as a library_id.
# ------------------------------------------------------------------


@router.get("/plugins")
async def list_plugins(
    auth: AuthContext = Depends(get_auth_context),
):
    """List available import plugins (filtered by org config)."""
    return await _client.get_plugins(creator_user=auth.user)


@router.post("/import")
async def import_library(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
):
    """Import a library from a ZIP file."""
    org_id = auth.organization.get("id")
    zip_data = await file.read()

    result = await _client.import_library_zip(org_id, zip_data, creator_user=auth.user)

    new_lib_id = result.get("library_id")
    if new_lib_id:
        _db.create_library(
            library_id=new_lib_id,
            name=result.get("library_name", "Imported Library"),
            owner_user_id=auth.user.get("id"),
            organization_id=org_id,
        )
        _audit(auth, "library.create", "library", new_lib_id, {"source": "zip_import"})

    return result


# ------------------------------------------------------------------
# Library CRUD
# ------------------------------------------------------------------


@router.post("")
async def create_library(
    body: LibraryCreate,
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new library in the current organization.

    The LAMB row is created with ``status='provisional'`` so that if the
    process crashes before the Library Manager call completes, the row
    won't appear in user listings.  On success the status is promoted to
    ``'active'``; on failure the provisional row is removed.
    """
    library_id = str(uuid.uuid4())
    org_id = auth.organization.get("id")

    result = _db.create_library(
        library_id=library_id,
        name=body.name,
        owner_user_id=auth.user.get("id"),
        organization_id=org_id,
        description=body.description,
        status="provisional",
    )
    if not result:
        raise HTTPException(status_code=409, detail="Library name already taken in this organization.")

    try:
        await _client.create_library(
            library_id=library_id,
            organization_id=org_id,
            name=body.name,
            creator_user=auth.user,
        )
    except Exception as e:
        _db.delete_library(library_id)
        raise HTTPException(status_code=502, detail=f"Library Manager error: {e}")

    _db.update_library_status(library_id, "active")
    _audit(auth, "library.create", "library", library_id, {"name": body.name})
    return _db.get_library(library_id)


@router.get("")
async def list_libraries(
    auth: AuthContext = Depends(get_auth_context),
):
    """List libraries accessible to the current user (owned + shared)."""
    return {
        "libraries": _db.get_accessible_libraries(
            user_id=auth.user.get("id"),
            organization_id=auth.organization.get("id"),
        )
    }


@router.get("/{library_id}")
async def get_library(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get library details."""
    auth.require_library_access(library_id, level="any")
    entry = _db.get_library(library_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Library not found")

    try:
        lm_data = await _client.get_library(library_id, creator_user=auth.user)
        entry["item_count"] = lm_data.get("item_count", 0)
    except Exception as e:
        logger.warning(f"Could not fetch item_count from Library Manager for {library_id}: {e}")
        entry["item_count"] = None

    entry["is_owner"] = entry.get("owner_user_id") == auth.user.get("id")
    return entry


@router.put("/{library_id}")
async def update_library(
    library_id: str,
    body: LibraryUpdate,
    auth: AuthContext = Depends(get_auth_context),
):
    """Update library name and/or description."""
    auth.require_library_access(library_id, level="owner")
    if body.name is None and body.description is None:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    success = _db.update_library(library_id, name=body.name, description=body.description)
    if not success:
        raise HTTPException(status_code=404, detail="Library not found")
    _audit(auth, "library.update", "library", library_id)
    return _db.get_library(library_id)


@router.delete("/{library_id}")
async def delete_library(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a library and all its content.

    Deletes from Library Manager first, then from LAMB DB. If LM returns
    a server error (5xx), the LAMB row is preserved so the user can retry.
    A 404 from LM is tolerated (already gone on disk).
    """
    auth.require_library_access(library_id, level="owner")

    try:
        await _client.delete_library(library_id, creator_user=auth.user)
    except HTTPException as e:
        if e.status_code == 404:
            pass
        elif e.status_code >= 500:
            raise HTTPException(
                status_code=502,
                detail=f"Library Manager error during delete: {e.detail}",
            )
        else:
            raise

    _db.delete_library(library_id)
    _audit(auth, "library.delete", "library", library_id)
    return {"message": f"Library {library_id} deleted."}


@router.put("/{library_id}/share")
async def toggle_sharing(
    library_id: str,
    body: LibraryShareToggle,
    auth: AuthContext = Depends(get_auth_context),
):
    """Enable or disable organization-wide sharing."""
    auth.require_library_access(library_id, level="owner")
    _db.toggle_library_sharing(library_id, body.is_shared)
    action = "library.share" if body.is_shared else "library.unshare"
    _audit(auth, action, "library", library_id)
    state = "shared with organization" if body.is_shared else "private"
    return {"library_id": library_id, "is_shared": body.is_shared, "message": f"Library is now {state}."}


# ------------------------------------------------------------------
# Content importing
# ------------------------------------------------------------------


@router.post("/{library_id}/upload")
async def upload_file(
    library_id: str,
    file: UploadFile = File(...),
    plugin_name: str = Form(None),
    title: str = Form(None),
    auth: AuthContext = Depends(get_auth_context),
):
    """Upload a file for import into the library."""
    if file.size is not None and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {MAX_UPLOAD_SIZE // (1024 * 1024)} MB.",
        )

    auth.require_library_access(library_id, level="any")
    entry = _db.get_library(library_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Library not found")

    file_title = title or file.filename or "Untitled"
    api_keys = _resolve_api_keys(auth)

    result = await _client.import_file(
        library_id=library_id,
        file=file,
        plugin_name=plugin_name or "simple_import",
        title=file_title,
        api_keys=api_keys,
        creator_user=auth.user,
    )

    item_id = result.get("item_id")
    if item_id:
        _db.register_library_item(
            item_id=item_id,
            library_id=library_id,
            organization_id=entry["organization_id"],
            title=file_title,
            source_type="file",
            import_plugin=plugin_name or "simple_import",
            uploader_user_id=auth.user.get("id"),
            original_filename=file.filename,
            content_type=file.content_type,
        )
        _audit(auth, "library.upload", "library_item", item_id, {
            "filename": file.filename,
            "plugin": plugin_name or "simple_import",
        })

    return result


@router.post("/{library_id}/import-url")
async def import_url(
    library_id: str,
    body: URLImportRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Import content from a URL."""
    auth.require_library_access(library_id, level="any")
    entry = _db.get_library(library_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Library not found")

    api_keys = _resolve_api_keys(auth)
    result = await _client.import_url(
        library_id=library_id,
        url=body.url,
        plugin_name=body.plugin_name,
        title=body.title or body.url,
        plugin_params=body.plugin_params,
        api_keys=api_keys,
        creator_user=auth.user,
    )

    item_id = result.get("item_id")
    if item_id:
        _db.register_library_item(
            item_id=item_id,
            library_id=library_id,
            organization_id=entry["organization_id"],
            title=body.title or body.url,
            source_type="url",
            import_plugin=body.plugin_name,
            uploader_user_id=auth.user.get("id"),
            source_url=body.url,
        )
        _audit(auth, "library.upload", "library_item", item_id, {
            "url": body.url,
            "plugin": body.plugin_name,
        })

    return result


@router.post("/{library_id}/import-youtube")
async def import_youtube(
    library_id: str,
    body: YouTubeImportRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Import a YouTube video transcript."""
    auth.require_library_access(library_id, level="any")
    entry = _db.get_library(library_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Library not found")

    api_keys = _resolve_api_keys(auth)
    result = await _client.import_youtube(
        library_id=library_id,
        video_url=body.video_url,
        plugin_name=body.plugin_name,
        title=body.title or body.video_url,
        language=body.language,
        api_keys=api_keys,
        creator_user=auth.user,
    )

    item_id = result.get("item_id")
    if item_id:
        _db.register_library_item(
            item_id=item_id,
            library_id=library_id,
            organization_id=entry["organization_id"],
            title=body.title or body.video_url,
            source_type="youtube",
            import_plugin=body.plugin_name,
            uploader_user_id=auth.user.get("id"),
            source_url=body.video_url,
        )
        _audit(auth, "library.upload", "library_item", item_id, {
            "video_url": body.video_url,
            "language": body.language,
        })

    return result


# ------------------------------------------------------------------
# Content items
# ------------------------------------------------------------------


@router.get("/{library_id}/items")
async def list_items(
    library_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
):
    """List imported items in a library."""
    auth.require_library_access(library_id, level="any")
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    return await _client.get_items(library_id, creator_user=auth.user, **params)


@router.get("/{library_id}/items/{item_id}")
async def get_item(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get details of an imported item."""
    auth.require_library_access(library_id, level="any")
    result = await _client.get_item(library_id, item_id, creator_user=auth.user)

    lm_status = result.get("status")
    lamb_item = _db.get_library_item(item_id)
    if lamb_item and lamb_item.get("status") != lm_status:
        _db.update_library_item_status(item_id, lm_status, result.get("metadata"))

    return result


@router.get("/{library_id}/items/{item_id}/status")
async def get_item_status(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get the import status for an item."""
    auth.require_library_access(library_id, level="any")
    result = await _client.get_item_status(library_id, item_id, creator_user=auth.user)

    lm_status = result.get("status")
    lamb_item = _db.get_library_item(item_id)
    if lamb_item and lamb_item.get("status") != lm_status:
        _db.update_library_item_status(item_id, lm_status)

    return result


@router.delete("/{library_id}/items/{item_id}")
async def delete_item(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete an imported item."""
    auth.require_library_access(library_id, level="owner")
    await _client.delete_item(library_id, item_id, creator_user=auth.user)
    _db.delete_library_item(item_id)
    _audit(auth, "library.delete_item", "library_item", item_id)
    return {"message": f"Item {item_id} deleted."}


# ------------------------------------------------------------------
# Import config
# ------------------------------------------------------------------


@router.get("/{library_id}/import-config")
async def get_import_config(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a library's import configuration."""
    auth.require_library_access(library_id, level="any")
    return await _client.get_import_config(library_id, creator_user=auth.user)


@router.put("/{library_id}/import-config")
async def update_import_config(
    library_id: str,
    config: dict,
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a library's import configuration."""
    auth.require_library_access(library_id, level="owner")
    return await _client.update_import_config(library_id, config, creator_user=auth.user)


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------


@router.get("/{library_id}/export")
async def export_library(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Export a library as a ZIP file."""
    auth.require_library_access(library_id, level="any")
    response = await _client.export_library(library_id, creator_user=auth.user)

    entry = _db.get_library(library_id)
    name = entry.get("name", "library") if entry else "library"
    safe_name = "".join(c if c.isalnum() or c in " -_." else "_" for c in name)

    return Response(
        content=response.content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


# ======================================================================
# Permalink proxy — mounted at /docs/ on the main app (not /creator/)
# ======================================================================

permalink_proxy_router = APIRouter()


@permalink_proxy_router.get("/docs/{org_id}/{library_id}/{item_id}/{subpath:path}")
async def permalink_proxy(
    org_id: str,
    library_id: str,
    item_id: str,
    subpath: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Proxy permalink requests to the Library Manager with ACL enforcement."""
    user_org_id = auth.organization.get("id")
    try:
        if int(org_id) != user_org_id:
            raise HTTPException(status_code=404, detail="Not found")
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Not found")

    auth.require_library_access(library_id, level="any")

    entry = _db.get_library(library_id)
    if not entry or entry["organization_id"] != int(org_id):
        raise HTTPException(status_code=404, detail="Not found")

    response = await _client.proxy_content(
        library_id=library_id,
        item_id=item_id,
        subpath=subpath,
        creator_user=auth.user,
    )

    content_type = response.headers.get("content-type", "application/octet-stream")
    return Response(
        content=response.content,
        media_type=content_type,
    )
