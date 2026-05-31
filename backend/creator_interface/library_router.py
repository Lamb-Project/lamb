"""Creator Interface routes for library management.

Each endpoint: authenticate -> check ACL -> resolve org config -> call Library
Manager -> update LAMB DB -> audit log -> return response.
"""

import logging
import uuid
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
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
    folder_id: Optional[str] = None

class YouTubeImportRequest(BaseModel):
    video_url: str
    # Deprecated: prefer ``plugin_params["language"]`` so all plugin knobs
    # travel through the same dict. Kept for API clients that still send
    # ``language`` as a top-level field — the proxy folds it into
    # ``plugin_params`` only when ``plugin_params["language"]`` is missing.
    language: str = "en"
    title: Optional[str] = None
    plugin_name: str = "youtube_transcript_import"
    plugin_params: Optional[Dict[str, Any]] = None
    folder_id: Optional[str] = None


class FolderCreateBody(BaseModel):
    name: str
    parent_folder_id: Optional[str] = None


class FolderRenameBody(BaseModel):
    name: str


class FolderMoveBody(BaseModel):
    parent_folder_id: Optional[str] = None


class ItemsMoveBody(BaseModel):
    item_ids: list[str]
    folder_id: Optional[str] = None


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


@router.get("/capabilities")
async def list_capabilities(
    auth: AuthContext = Depends(get_auth_context),
):
    """List capability handlers registered on the Library Manager."""
    return await _client.get_capabilities(creator_user=auth.user)


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
    user_id = auth.user.get("id")
    libraries = _db.get_accessible_libraries(
        user_id=user_id,
        organization_id=auth.organization.get("id"),
    )
    for entry in libraries:
        entry["is_owner"] = entry.get("owner_user_id") == user_id
    return {"libraries": libraries}


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

    FR-10: blocked with 409 if any item in this library is still actively
    referenced by a Knowledge Store. Mirrors the per-item check in
    :func:`delete_item` so deleting the parent library cannot bypass the
    rule and orphan vectors in the KB Server.

    Deletes from Library Manager first, then from LAMB DB. If LM returns
    a server error (5xx), the LAMB row is preserved so the user can retry.
    A 404 from LM is tolerated (already gone on disk).
    """
    auth.require_library_access(library_id, level="owner")

    referencing_links = _db.get_kb_content_links_for_library(library_id)
    active_links = [
        l for l in referencing_links
        if l.get("status") != "failed"
    ]
    if active_links:
        blocking_stores: Dict[str, Dict[str, Any]] = {}
        for l in active_links:
            ks_id = l.get("knowledge_store_id")
            if ks_id and ks_id not in blocking_stores:
                blocking_stores[ks_id] = {
                    "id": ks_id,
                    "name": l.get("knowledge_store_name"),
                    "status": l.get("status"),
                }
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Cannot delete library: one or more of its items are "
                    "referenced by Knowledge Stores. Remove the content "
                    "from each Knowledge Store first."
                ),
                "knowledge_stores": list(blocking_stores.values()),
                "items": [
                    {
                        "id": l.get("library_item_id"),
                        "title": l.get("item_title"),
                        "knowledge_store_id": l.get("knowledge_store_id"),
                        "status": l.get("status"),
                    }
                    for l in active_links
                ],
            },
        )

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
    folder_id: Optional[str] = Form(None),
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
        folder_id=folder_id,
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
        folder_id=body.folder_id,
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
        plugin_params=body.plugin_params,
        api_keys=api_keys,
        folder_id=body.folder_id,
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
        # Resolve language from plugin_params first (the new schema-driven
        # path), then the legacy top-level field — both flows audit the
        # same value.
        audit_language = (body.plugin_params or {}).get("language", body.language)
        _audit(auth, "library.upload", "library_item", item_id, {
            "video_url": body.video_url,
            "language": audit_language,
        })

    return result


# ------------------------------------------------------------------
# Folders & tree
# ------------------------------------------------------------------


@router.get("/{library_id}/tree")
async def get_library_tree(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Return the folder + item tree for a library (flat lists)."""
    auth.require_library_access(library_id, level="any")
    return await _client.get_tree(library_id, creator_user=auth.user)


@router.post("/{library_id}/folders", status_code=201)
async def create_folder(
    library_id: str,
    body: FolderCreateBody,
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a folder in a library."""
    auth.require_library_access(library_id, level="any")
    result = await _client.create_folder(
        library_id,
        name=body.name,
        parent_folder_id=body.parent_folder_id,
        creator_user=auth.user,
    )
    _audit(auth, "library.folder.create", "library_folder", result.get("id", ""), {
        "name": body.name,
        "parent_folder_id": body.parent_folder_id,
    })
    return result


@router.put("/{library_id}/folders/{folder_id}")
async def rename_folder(
    library_id: str,
    folder_id: str,
    body: FolderRenameBody,
    auth: AuthContext = Depends(get_auth_context),
):
    """Rename a folder."""
    auth.require_library_access(library_id, level="any")
    result = await _client.rename_folder(
        library_id, folder_id, body.name, creator_user=auth.user
    )
    _audit(auth, "library.folder.rename", "library_folder", folder_id, {"name": body.name})
    return result


@router.put("/{library_id}/folders/{folder_id}/move")
async def move_folder(
    library_id: str,
    folder_id: str,
    body: FolderMoveBody,
    auth: AuthContext = Depends(get_auth_context),
):
    """Re-parent a folder."""
    auth.require_library_access(library_id, level="any")
    result = await _client.move_folder(
        library_id, folder_id, body.parent_folder_id, creator_user=auth.user
    )
    _audit(auth, "library.folder.move", "library_folder", folder_id, {
        "parent_folder_id": body.parent_folder_id,
    })
    return result


@router.delete("/{library_id}/folders/{folder_id}")
async def delete_folder(
    library_id: str,
    folder_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a folder. Items + subfolders reparent to its parent.

    Never cascade-deletes items; folder delete is unaffected by FR-10
    (item IDs are preserved).
    """
    auth.require_library_access(library_id, level="owner")
    result = await _client.delete_folder(library_id, folder_id, creator_user=auth.user)
    _audit(auth, "library.folder.delete", "library_folder", folder_id)
    return result


@router.post("/{library_id}/items/move")
async def move_items(
    library_id: str,
    body: ItemsMoveBody,
    auth: AuthContext = Depends(get_auth_context),
):
    """Move a batch of items to a folder (or to root)."""
    auth.require_library_access(library_id, level="any")
    if len(body.item_ids) > 500:
        raise HTTPException(status_code=413, detail="Too many items (max 500 per request).")
    result = await _client.move_items(
        library_id,
        item_ids=body.item_ids,
        folder_id=body.folder_id,
        creator_user=auth.user,
    )
    _audit(auth, "library.items.move", "library", library_id, {
        "count": len(body.item_ids),
        "folder_id": body.folder_id,
    })
    return result


# ------------------------------------------------------------------
# Content items
# ------------------------------------------------------------------


@router.get("/{library_id}/items")
async def list_items(
    library_id: str,
    limit: int = Query(20, ge=1, le=500),
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


MAX_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB inline-content cap


@router.get("/{library_id}/items/{item_id}/content")
async def get_item_content(
    library_id: str,
    item_id: str,
    format: Literal["markdown", "text"] = "markdown",
    auth: AuthContext = Depends(get_auth_context),
):
    """Return the full rendered content of an imported item.

    HTML output is intentionally not exposed — Library Manager's
    ``format=html`` uses an unsanitized server-side renderer. Clients
    that need HTML must request markdown and sanitize on their side.
    """
    auth.require_library_access(library_id, level="any")
    response = await _client.proxy_content(
        library_id=library_id,
        item_id=item_id,
        subpath=f"content?format={format}",
        creator_user=auth.user,
    )
    if len(response.content) > MAX_CONTENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Content exceeds {MAX_CONTENT_BYTES // (1024 * 1024)} MB. "
                "Download the original file instead."
            ),
        )
    default_media = "text/markdown" if format == "markdown" else "text/plain"
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", default_media),
    )


def _content_disposition(filename: str) -> str:
    """Build a safe Content-Disposition header value with RFC 5987 fallback.

    Keeps a plain ASCII ``filename`` for legacy clients and a ``filename*``
    UTF-8 encoded variant so non-ASCII names (Spanish/Catalan/Basque
    accented characters in this codebase) survive the round trip.
    """
    from urllib.parse import quote
    ascii_safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in filename)
    quoted = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_safe}\"; filename*=UTF-8''{quoted}"


@router.get("/{library_id}/items/{item_id}/capabilities")
async def get_item_capabilities(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """List capabilities exposed by a specific library item.

    Reads the item's ``metadata.json`` ``capabilities`` field on the
    Library Manager side. Legacy items default to ``["text"]``.
    """
    auth.require_library_access(library_id, level="any")
    return await _client.get_item_capabilities(
        library_id, item_id, creator_user=auth.user,
    )


@router.get("/{library_id}/items/{item_id}/content/{capability}")
async def get_item_capability_content(
    library_id: str,
    item_id: str,
    capability: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Dispatch to the capability handler for an item and forward the payload.

    The ``capability`` path segment must match a registered
    :class:`Capability` enum value (e.g. ``text``, ``pages``, ``images``).
    The 5 MB inline-content cap from ``get_item_content`` also applies here.
    """
    auth.require_library_access(library_id, level="any")
    response = await _client.get_item_content(
        library_id, item_id, capability, creator_user=auth.user,
    )
    if len(response.content) > MAX_CONTENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Content exceeds {MAX_CONTENT_BYTES // (1024 * 1024)} MB."
            ),
        )
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "application/octet-stream"),
    )


@router.get("/{library_id}/items/{item_id}/content/images/file/{filename}")
async def get_item_image_file(
    library_id: str,
    item_id: str,
    filename: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Serve a single extracted image file by name.

    The ``images`` capability handler returns gallery URLs of the form
    ``/libraries/{lib}/items/{item}/content/images/file/{filename}``. The
    ``ImagesRenderer`` in the frontend points ``<img src>`` at this route
    (proxied under ``/creator/...``); without it the renderer just shows
    broken-image placeholders.

    Inherits the standard library ACL.
    """
    auth.require_library_access(library_id, level="any")

    # Reject obvious path traversal attempts before they hit the LM. The
    # LM has its own safety but defense in depth is cheap here.
    if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    response = await _client.proxy_content(
        library_id=library_id,
        item_id=item_id,
        subpath=f"content/images/file/{filename}",
        creator_user=auth.user,
    )
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "application/octet-stream"),
    )


@router.get("/{library_id}/items/{item_id}/original")
async def get_item_original(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Return the original (pre-extraction) source file for a library item.

    Companion to ``/items/{item_id}/content`` (which returns extracted
    markdown). Resolves the filename server-side from the item's metadata so
    callers don't need to know it.

    Behavior by source type:
      - File / markitdown imports: streams the binary original with
        ``Content-Disposition: attachment``.
      - URL / YouTube imports (no binary): returns ``404`` with a body shaped
        ``{"detail": {"message": ..., "source_url": ..., "source_type": ...}}``
        so the client can fall back to opening the source URL.
    """
    auth.require_library_access(library_id, level="any")

    item = await _client.get_item(library_id, item_id, creator_user=auth.user)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    filename = item.get("original_filename")
    source_url = item.get("source_url")
    source_type = item.get("source_type")

    if not filename:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Item has no binary original file.",
                "source_url": source_url,
                "source_type": source_type,
            },
        )

    response = await _client.proxy_content(
        library_id=library_id,
        item_id=item_id,
        subpath=f"original/{filename}",
        creator_user=auth.user,
    )
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "application/octet-stream"),
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.get("/{library_id}/kb-links")
async def get_library_kb_links(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """List all active (item, KS) links for every item in this library.

    Pre-check used by the UI before showing the delete-confirm modal so it
    can surface blockers upfront without attempting a delete. Failed ingestions
    are excluded (FR-10 only blocks on active links).

    Returns:
        dict: Same shape as the FR-10 409 detail body —
            ``{"library_id": str, "items": [{id, title, knowledge_store_id}],
               "knowledge_stores": [{id, name}]}``.
    """
    auth.require_library_access(library_id, level="any")
    links = _db.get_kb_content_links_for_library(library_id)
    active = [l for l in links if l.get("status") != "failed"]
    ks_map = {}
    for l in active:
        ks_id = str(l.get("knowledge_store_id", ""))
        if ks_id and ks_id not in ks_map:
            ks_map[ks_id] = l.get("knowledge_store_name") or ks_id
    return {
        "library_id": library_id,
        "items": [
            {
                "id": str(l.get("library_item_id", "")),
                "title": l.get("item_title") or l.get("library_item_id", ""),
                "knowledge_store_id": str(l.get("knowledge_store_id", "")),
            }
            for l in active
        ],
        "knowledge_stores": [{"id": k, "name": v} for k, v in ks_map.items()],
    }


@router.get("/{library_id}/items/{item_id}/kb-links")
async def get_item_kb_links(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """List Knowledge Stores that actively reference this library item.

    Pre-check used by the UI before showing the delete-confirm modal so it
    can branch into "blocked" mode without round-tripping through a 409.
    Failed ingestions are excluded (FR-10 doesn't block on them).

    Returns:
        dict: ``{"item_id": str, "knowledge_stores": [{id, name, status}, ...]}``
        — same shape as ``detail.knowledge_stores`` in the FR-10 409 body.
    """
    auth.require_library_access(library_id, level="any")
    referencing_links = _db.get_kb_content_links_for_item(item_id)
    active_links = [
        l for l in referencing_links
        if l.get("status") != "failed"
    ]
    return {
        "item_id": item_id,
        "knowledge_stores": [
            {
                "id": l.get("knowledge_store_id"),
                "name": l.get("knowledge_store_name"),
                "status": l.get("status"),
            }
            for l in active_links
        ],
    }


@router.get("/{library_id}/knowledge-stores")
async def get_library_knowledge_stores(
    library_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """List Knowledge Stores that reference any item from this library.

    Inverse of ``GET /creator/knowledge-stores/{ks_id}/content``. Useful for
    answering "which KSs are populated from library X?" without scanning every
    KS's content list client-side.

    The caller must have at least read access to the library. The KS list is
    filtered to those the caller can also access (owned or shared within the
    same organization) — KSs from other users that happen to reference items
    of a shared library are hidden.

    Returns:
        ``{"library_id": str, "knowledge_stores": [{id, name, description,
        chunking_strategy, embedding_vendor, embedding_model,
        vector_db_backend, is_shared, item_count, ready_count, failed_count,
        access}]}``
    """
    auth.require_library_access(library_id, level="any")

    referencing = _db.get_knowledge_stores_for_library(library_id)
    visible = []
    for ks in referencing:
        access = auth.can_access_knowledge_store(ks["id"])
        if access == "none":
            continue
        visible.append({
            "id": ks["id"],
            "name": ks.get("name"),
            "description": ks.get("description"),
            "chunking_strategy": ks.get("chunking_strategy"),
            "embedding_vendor": ks.get("embedding_vendor"),
            "embedding_model": ks.get("embedding_model"),
            "vector_db_backend": ks.get("vector_db_backend"),
            "is_shared": ks.get("is_shared", False),
            "item_count": ks.get("item_count", 0),
            "ready_count": ks.get("ready_count", 0),
            "failed_count": ks.get("failed_count", 0),
            "access": access,
        })
    return {"library_id": library_id, "knowledge_stores": visible}


@router.delete("/{library_id}/items/{item_id}")
async def delete_item(
    library_id: str,
    item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete an imported item.

    FR-10: blocked with 409 if any active Knowledge Store still references
    this item via ``kb_content_links``. Caller must remove the content from
    every referencing KS first.
    """
    auth.require_library_access(library_id, level="owner")

    referencing_links = _db.get_kb_content_links_for_item(item_id)
    active_links = [
        l for l in referencing_links
        if l.get("status") != "failed"
    ]
    if active_links:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Cannot delete library item: it is referenced by one or more "
                    "Knowledge Stores. Remove the content from each Knowledge "
                    "Store first."
                ),
                "knowledge_stores": [
                    {
                        "id": l.get("knowledge_store_id"),
                        "name": l.get("knowledge_store_name"),
                        "status": l.get("status"),
                    }
                    for l in active_links
                ],
            },
        )

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
    config: Dict[str, Any] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a library's import configuration."""
    auth.require_library_access(library_id, level="owner")
    result = await _client.update_import_config(library_id, config, creator_user=auth.user)
    _audit(auth, "library.update_config", "library", library_id)
    return result


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
