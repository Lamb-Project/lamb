"""Business logic for content item retrieval and disk operations.

This module handles:
- Writing structured content to disk (after plugin produces ImportResult)
- Reading content from disk (for API retrieval endpoints)
- Generating metadata.json with permalink URLs
- Deleting content items from disk and database
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from config import CONTENT_DIR, PERMALINK_PREFIX
from database.models import ContentItem
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Writing structured content to disk
# ---------------------------------------------------------------------------


def write_structured_content(
    item_id: str,
    library_id: str,
    organization_id: str,
    title: str,
    full_text: str,
    pages: list,
    images: list,
    item_metadata: dict[str, Any],
    source_ref: dict[str, Any],
    original_file_path: Path | None = None,
    original_filename: str | None = None,
) -> Path:
    """Write the common structured format to disk.

    Creates the directory tree::

        {CONTENT_DIR}/{org}/{lib}/{item}/
            metadata.json
            source_ref.json
            original/{filename}
            content/full.md
            content/pages/page_001.md
            content/images/img_001.png

    Args:
        item_id: Content item UUID.
        library_id: Parent library UUID.
        organization_id: Organization ID.
        title: Document title.
        full_text: Full markdown content.
        pages: List of PageContent objects.
        images: List of ExtractedImage objects.
        item_metadata: Metadata dict from the plugin.
        source_ref: Source reference dict from the plugin.
        original_file_path: Path to the uploaded original file (copy it).
        original_filename: Filename for the original document.

    Returns:
        The base path of the content directory.
    """
    base_dir = CONTENT_DIR / organization_id / library_id / item_id
    base_dir.mkdir(parents=True, exist_ok=True)

    permalink_base = f"{PERMALINK_PREFIX}/{organization_id}/{library_id}/{item_id}"

    # --- Original file ---
    original_dir = base_dir / "original"
    original_permalink = None
    if original_file_path and original_file_path.is_file():
        original_dir.mkdir(exist_ok=True)
        dest_name = _sanitize_filename(original_filename or original_file_path.name)
        dest = original_dir / dest_name
        shutil.copy2(str(original_file_path), str(dest))
        original_permalink = f"{permalink_base}/original/{dest_name}"

    # --- Full markdown ---
    content_dir = base_dir / "content"
    content_dir.mkdir(exist_ok=True)

    full_md_path = content_dir / "full.md"
    full_md_path.write_text(full_text, encoding="utf-8")
    full_md_permalink = f"{permalink_base}/content/full.md"

    # --- Per-page files ---
    page_permalinks = []
    pages_dir = content_dir / "pages"
    if pages:
        pages_dir.mkdir(exist_ok=True)
        for page in pages:
            page_filename = f"page_{page.page_number:03d}.md"
            page_path = pages_dir / page_filename
            page_path.write_text(page.text, encoding="utf-8")
            page_permalinks.append(
                f"{permalink_base}/content/pages/{page_filename}"
            )

    # --- Extracted images ---
    image_permalinks = []
    images_dir = content_dir / "images"
    if images:
        images_dir.mkdir(exist_ok=True)
        for img in images:
            safe_name = _sanitize_filename(img.filename)
            img_path = images_dir / safe_name
            img_path.write_bytes(img.data)
            image_permalinks.append(
                f"{permalink_base}/content/images/{safe_name}"
            )

    # --- source_ref.json ---
    source_ref_path = base_dir / "source_ref.json"
    source_ref_path.write_text(
        json.dumps(source_ref, indent=2, default=str),
        encoding="utf-8",
    )

    # --- metadata.json (with permalinks) ---
    metadata_obj = {
        "item_id": item_id,
        "title": title,
        **item_metadata,
        "permalinks": {
            "original": original_permalink,
            "full_markdown": full_md_permalink,
            "pages": page_permalinks,
            "images": image_permalinks,
        },
        "source_ref": source_ref,
    }
    metadata_path = base_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata_obj, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info("Wrote structured content for item %s at %s", item_id, base_dir)
    return base_dir


# ---------------------------------------------------------------------------
# Reading content from disk
# ---------------------------------------------------------------------------


def get_item_base_path(
    organization_id: str, library_id: str, item_id: str
) -> Path:
    """Return the base directory for a content item.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        Path to the item's directory.
    """
    return CONTENT_DIR / organization_id / library_id / item_id


def _safe_resolve(path: Path, expected_parent: Path) -> Path | None:
    """Resolve a path and verify it stays within the expected directory.

    Prevents path traversal via symlinks or ``..`` components.

    Args:
        path: The path to verify.
        expected_parent: The directory the path must be within.

    Returns:
        The resolved path, or ``None`` if traversal was detected.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(expected_parent.resolve()):
        logger.warning("Path traversal attempt blocked: %s", path)
        return None
    return resolved


def read_full_markdown(
    organization_id: str, library_id: str, item_id: str
) -> str | None:
    """Read the full.md file for a content item.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        Markdown text, or ``None`` if not found.
    """
    base = get_item_base_path(organization_id, library_id, item_id)
    path = _safe_resolve(base / "content" / "full.md", base)
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def read_page_markdown(
    organization_id: str, library_id: str, item_id: str, page_name: str
) -> str | None:
    """Read a specific page markdown file.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.
        page_name: Page filename (e.g. ``"page_001.md"`` or ``"page_001"``).

    Returns:
        Markdown text, or ``None`` if not found.
    """
    if not page_name.endswith(".md"):
        page_name = f"{page_name}.md"
    page_name = _sanitize_filename(page_name)

    base = get_item_base_path(organization_id, library_id, item_id)
    path = _safe_resolve(base / "content" / "pages" / page_name, base)
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def read_metadata_json(
    organization_id: str, library_id: str, item_id: str
) -> dict | None:
    """Read metadata.json for a content item.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        Parsed JSON dict, or ``None`` if not found.
    """
    base = get_item_base_path(organization_id, library_id, item_id)
    path = _safe_resolve(base / "metadata.json", base)
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_source_ref(
    organization_id: str, library_id: str, item_id: str
) -> dict | None:
    """Read source_ref.json for a content item.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        Parsed JSON dict, or ``None`` if not found.
    """
    base = get_item_base_path(organization_id, library_id, item_id)
    path = _safe_resolve(base / "source_ref.json", base)
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_pages(
    organization_id: str, library_id: str, item_id: str
) -> list[str]:
    """List available page markdown files for a content item.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        Sorted list of page filenames.
    """
    pages_dir = (
        get_item_base_path(organization_id, library_id, item_id) / "content" / "pages"
    )
    if not pages_dir.is_dir():
        return []
    return sorted(f.name for f in pages_dir.iterdir() if f.suffix == ".md")


def list_images(
    organization_id: str, library_id: str, item_id: str
) -> list[str]:
    """List available image files for a content item.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        Sorted list of image filenames.
    """
    images_dir = (
        get_item_base_path(organization_id, library_id, item_id) / "content" / "images"
    )
    if not images_dir.is_dir():
        return []
    return sorted(f.name for f in images_dir.iterdir() if f.is_file())


def get_image_path(
    organization_id: str, library_id: str, item_id: str, image_name: str
) -> Path | None:
    """Get the absolute path to an image file.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.
        image_name: Image filename.

    Returns:
        Path if file exists, ``None`` otherwise.
    """
    safe_name = _sanitize_filename(image_name)
    base = get_item_base_path(organization_id, library_id, item_id)
    path = _safe_resolve(base / "content" / "images" / safe_name, base)
    if path is None or not path.is_file():
        return None
    return path


def get_original_path(
    organization_id: str, library_id: str, item_id: str, filename: str
) -> Path | None:
    """Get the absolute path to the original document file.

    Args:
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.
        filename: Original document filename.

    Returns:
        Path if file exists, ``None`` otherwise.
    """
    safe_name = _sanitize_filename(filename)
    base = get_item_base_path(organization_id, library_id, item_id)
    path = _safe_resolve(base / "original" / safe_name, base)
    if path is None or not path.is_file():
        return None
    return path


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


def delete_content_item(
    db: Session,
    organization_id: str,
    library_id: str,
    item_id: str,
) -> bool:
    """Delete a content item from disk and database.

    Args:
        db: Database session.
        organization_id: Organization ID.
        library_id: Library UUID.
        item_id: Content item UUID.

    Returns:
        ``True`` if deleted, ``False`` if not found.
    """
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if item is None:
        return False

    # DB first, then disk — if crash occurs between, DB is clean.
    db.delete(item)
    db.commit()

    item_dir = get_item_base_path(organization_id, library_id, item_id)
    if item_dir.exists():
        shutil.rmtree(item_dir, ignore_errors=True)

    logger.info("Deleted content item %s", item_id)
    return True


# ---------------------------------------------------------------------------
# DB queries for content items
# ---------------------------------------------------------------------------


def get_content_item(db: Session, item_id: str) -> ContentItem | None:
    """Fetch a content item by ID.

    Args:
        db: Database session.
        item_id: Content item UUID.

    Returns:
        ContentItem row, or ``None``.
    """
    return db.query(ContentItem).filter(ContentItem.id == item_id).first()


def list_content_items(
    db: Session,
    library_id: str,
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None,
    ids_filter: list[str] | None = None,
) -> tuple[list[ContentItem], int]:
    """List content items for a library.

    Args:
        db: Database session.
        library_id: Filter by library.
        limit: Max results.
        offset: Skip count.
        status_filter: Optional status filter.
        ids_filter: Optional list of item IDs to return.

    Returns:
        Tuple of (items list, total count).
    """
    query = db.query(ContentItem).filter(ContentItem.library_id == library_id)

    if status_filter:
        query = query.filter(ContentItem.status == status_filter)
    if ids_filter:
        query = query.filter(ContentItem.id.in_(ids_filter))

    total = query.count()
    items = query.order_by(ContentItem.created_at.desc()).offset(offset).limit(limit).all()
    return items, total


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_filename(name: str) -> str:
    """Remove path-traversal characters from a filename.

    Strips directory separators and relative path components to prevent
    writing or reading outside the expected directory.

    Args:
        name: Raw filename string.

    Returns:
        Sanitized filename safe for use in file paths.
    """
    # Take only the final component (no directory traversal).
    name = Path(name).name
    # Remove any remaining suspicious characters.
    name = name.replace("\x00", "").strip()
    if not name or name in (".", ".."):
        name = "unnamed"
    return name
