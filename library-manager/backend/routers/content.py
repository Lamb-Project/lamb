"""Content retrieval and management routes.

Handles listing, detail, status, deletion, and content serving for
library items. Also handles export/import of libraries.
"""

import json
import logging
from pathlib import Path

import markdown2
from database.connection import get_session
from database.models import ContentItem
from dependencies import verify_token
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from schemas.content import (
    ContentItemListResponse,
    ContentItemStatusResponse,
    ImageListResponse,
    PageListResponse,
)
from services import content_service, export_service
from services.library_service import get_library
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/libraries", tags=["Content"], dependencies=[Depends(verify_token)])


# ---------------------------------------------------------------------------
# Item listing and detail
# ---------------------------------------------------------------------------


@router.get("/{lib_id}/items", response_model=ContentItemListResponse)
async def list_items(
    lib_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str = Query(None, alias="status"),
    ids: str = Query(None, description="Comma-separated item IDs to filter."),
    db: Session = Depends(get_session),
) -> dict:
    """List content items for a library.

    Args:
        lib_id: Library UUID.
        limit: Max results.
        offset: Skip count.
        status_filter: Optional status filter.
        ids: Comma-separated item IDs.
        db: Database session.

    Returns:
        Paginated list of items.
    """
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")

    ids_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None

    items, total = content_service.list_content_items(
        db, lib_id, limit, offset, status_filter, ids_list
    )

    return {
        "items": [_item_to_summary(item) for item in items],
        "total": total,
    }


@router.get("/{lib_id}/items/{item_id}")
async def get_item(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Get full details for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        Full item detail including metadata and permalinks.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")
    return _item_to_detail(item)


@router.get("/{lib_id}/items/{item_id}/status", response_model=ContentItemStatusResponse)
async def get_item_status(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Get the import status for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        Status, error message, and processing stats.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    return {
        "item_id": item.id,
        "status": item.status,
        "error_message": item.error_message,
        "processing_stats": json.loads(item.processing_stats) if item.processing_stats else None,
    }


@router.delete("/{lib_id}/items/{item_id}")
async def delete_item(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Delete a content item from disk and database.

    LAMB validates usage (KB references) before calling this endpoint.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        Confirmation message.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    deleted = content_service.delete_content_item(
        db, item.organization_id, lib_id, item_id
    )
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete item.")

    return {"message": f"Item {item_id} deleted."}


# ---------------------------------------------------------------------------
# Content serving
# ---------------------------------------------------------------------------


@router.get("/{lib_id}/items/{item_id}/content")
async def get_full_content(
    lib_id: str,
    item_id: str,
    format: str = Query("markdown", description="Output format: markdown, text, html."),
    db: Session = Depends(get_session),
) -> Response:
    """Get the full extracted markdown for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        format: Response format (``markdown``, ``text``, or ``html``).
        db: Database session.

    Returns:
        The content in the requested format.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    text = content_service.read_full_markdown(item.organization_id, lib_id, item_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Content not found on disk.")

    return _format_response(text, format)


@router.get("/{lib_id}/items/{item_id}/content/pages", response_model=PageListResponse)
async def list_pages(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """List available page files for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        List of page filenames and count.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    pages = content_service.list_pages(item.organization_id, lib_id, item_id)
    return {"pages": pages, "count": len(pages)}


@router.get("/{lib_id}/items/{item_id}/content/pages/{page}")
async def get_page(
    lib_id: str,
    item_id: str,
    page: str,
    format: str = Query("markdown"),
    db: Session = Depends(get_session),
) -> Response:
    """Get a specific page's markdown content.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        page: Page filename (with or without ``.md`` extension).
        format: Response format.
        db: Database session.

    Returns:
        Page content in the requested format.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    text = content_service.read_page_markdown(item.organization_id, lib_id, item_id, page)
    if text is None:
        raise HTTPException(status_code=404, detail="Page not found.")

    return _format_response(text, format)


@router.get("/{lib_id}/items/{item_id}/content/images", response_model=ImageListResponse)
async def list_images(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """List available image files for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        List of image filenames and count.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    images = content_service.list_images(item.organization_id, lib_id, item_id)
    return {"images": images, "count": len(images)}


@router.get("/{lib_id}/items/{item_id}/content/images/{image_name}")
async def get_image(
    lib_id: str,
    item_id: str,
    image_name: str,
    db: Session = Depends(get_session),
) -> FileResponse:
    """Serve an extracted image file.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        image_name: Image filename.
        db: Database session.

    Returns:
        The image file.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    path = content_service.get_image_path(item.organization_id, lib_id, item_id, image_name)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    return FileResponse(path)


@router.get("/{lib_id}/items/{item_id}/original/{filename}")
async def get_original(
    lib_id: str,
    item_id: str,
    filename: str,
    db: Session = Depends(get_session),
) -> FileResponse:
    """Serve the original document file.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        filename: Original document filename.
        db: Database session.

    Returns:
        The original file.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    path = content_service.get_original_path(item.organization_id, lib_id, item_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Original file not found.")

    return FileResponse(path, filename=filename)


@router.get("/{lib_id}/items/{item_id}/metadata")
async def get_metadata(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Get the full metadata.json for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        Parsed metadata dict with permalink URLs.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    metadata = content_service.read_metadata_json(item.organization_id, lib_id, item_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Metadata not found.")

    return metadata


@router.get("/{lib_id}/items/{item_id}/source_ref")
async def get_source_ref(
    lib_id: str,
    item_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """Get the source reference for a content item.

    Args:
        lib_id: Library UUID.
        item_id: Content item UUID.
        db: Database session.

    Returns:
        Source reference dict.
    """
    item = content_service.get_content_item(db, item_id)
    if item is None or item.library_id != lib_id:
        raise HTTPException(status_code=404, detail="Item not found.")

    source_ref = content_service.read_source_ref(item.organization_id, lib_id, item_id)
    if source_ref is None:
        raise HTTPException(status_code=404, detail="Source reference not found.")

    return source_ref


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


@router.get("/{lib_id}/export")
async def export_library(
    lib_id: str,
    db: Session = Depends(get_session),
) -> StreamingResponse:
    """Export a library as a ZIP file.

    Args:
        lib_id: Library UUID.
        db: Database session.

    Returns:
        Streaming ZIP file download.
    """
    lib = get_library(db, lib_id)
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found.")

    buffer = export_service.export_library_zip(
        db=db,
        library_id=lib_id,
        organization_id=lib.organization_id,
        library_name=lib.name,
        import_config=json.loads(lib.import_config) if lib.import_config else None,
    )

    # Sanitize library name for Content-Disposition header.
    safe_name = lib.name.replace('"', "_").replace("\n", "_").replace("\r", "_")
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_library(
    organization_id: str = Query(..., description="Target organization ID."),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> dict:
    """Import a library from a ZIP file.

    Creates a new library with regenerated IDs. Does not re-run import
    plugins — structured content is restored directly from the ZIP.

    Args:
        organization_id: Target organization.
        file: The ZIP file.
        db: Database session.

    Returns:
        Import result with library_id, name, and item count.
    """
    import tempfile  # noqa: PLC0415

    from config import MAX_ZIP_IMPORT_SIZE_BYTES  # noqa: PLC0415

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        bytes_written = 0
        while chunk := await file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > MAX_ZIP_IMPORT_SIZE_BYTES:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"ZIP file exceeds maximum size "
                           f"({MAX_ZIP_IMPORT_SIZE_BYTES // (1024 * 1024)} MB).",
                )
            tmp.write(chunk)
        tmp.close()

        if bytes_written == 0:
            Path(tmp.name).unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Empty file.")

        zip_data = Path(tmp.name).read_bytes()
        result = export_service.import_library_zip(db, zip_data, organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item_to_summary(item: ContentItem) -> dict:
    """Convert a ContentItem ORM object to a summary dict."""
    return {
        "id": item.id,
        "title": item.title,
        "source_type": item.source_type,
        "original_filename": item.original_filename,
        "content_type": item.content_type,
        "file_size": item.file_size,
        "import_plugin": item.import_plugin,
        "status": item.status,
        "page_count": item.page_count,
        "image_count": item.image_count,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _item_to_detail(item: ContentItem) -> dict:
    """Convert a ContentItem ORM object to a full detail dict."""
    detail = _item_to_summary(item)
    detail.update({
        "source_url": item.source_url,
        "import_params": json.loads(item.import_params) if item.import_params else None,
        "metadata": json.loads(item.metadata_) if item.metadata_ else None,
        "processing_stats": json.loads(item.processing_stats) if item.processing_stats else None,
        "error_message": item.error_message,
        "permalink_base": item.permalink_base,
    })
    return detail


def _format_response(text: str, fmt: str) -> Response:
    """Format markdown text as the requested output format.

    Args:
        text: Raw markdown text.
        fmt: ``"markdown"``, ``"text"``, or ``"html"``.

    Returns:
        Appropriate Response object.
    """
    if fmt == "html":
        html = markdown2.markdown(
            text,
            extras=["fenced-code-blocks", "tables", "header-ids", "strike"],
        )
        return Response(content=html, media_type="text/html")
    if fmt == "text":
        return Response(content=text, media_type="text/plain")
    # Default: markdown
    return Response(content=text, media_type="text/markdown")
