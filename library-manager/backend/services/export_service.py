"""Library export and import via ZIP files.

Export produces a ZIP containing a manifest.json and all structured content
directories. Import re-creates a library from such a ZIP.

Import does NOT re-run plugins — the structured content (markdown, images,
metadata) is already in the ZIP. It simply stores the files and registers
them in the database. This makes import fast and key-free.
"""

import json
import logging
import uuid
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from config import CONTENT_DIR, PERMALINK_PREFIX
from database.models import ContentItem
from sqlalchemy.orm import Session

from services.library_service import create_library, ensure_organization

logger = logging.getLogger(__name__)


def export_library_zip(
    db: Session,
    library_id: str,
    organization_id: str,
    library_name: str,
    import_config: dict | None,
    exported_by: str = "",
) -> BytesIO:
    """Export a library and all its items as a ZIP file.

    Args:
        db: Database session.
        library_id: Library UUID.
        organization_id: Organization ID.
        library_name: Library display name.
        import_config: Library's import config.
        exported_by: Email or identifier of the exporter.

    Returns:
        In-memory BytesIO containing the ZIP archive.
    """
    items = (
        db.query(ContentItem)
        .filter(
            ContentItem.library_id == library_id,
            ContentItem.status == "ready",
        )
        .all()
    )

    manifest = {
        "format_version": "1.0",
        "type": "library_export",
        "library": {
            "name": library_name,
            "import_config": import_config,
        },
        "items": [],
        "exported_at": datetime.now(UTC).isoformat(),
        "exported_by": exported_by,
    }

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            manifest["items"].append({
                "id": item.id,
                "title": item.title,
                "source_type": item.source_type,
                "original_filename": item.original_filename,
                "content_type": item.content_type,
                "import_plugin": item.import_plugin,
                "import_params": json.loads(item.import_params) if item.import_params else None,
                "metadata": json.loads(item.metadata_) if item.metadata_ else None,
            })

            item_dir = CONTENT_DIR / organization_id / library_id / item.id
            if item_dir.is_dir():
                for file_path in item_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = f"content/{item.id}/{file_path.relative_to(item_dir)}"
                        zf.write(str(file_path), arcname)

        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

    buffer.seek(0)
    logger.info(
        "Exported library %s: %d items, %d bytes",
        library_id, len(items), buffer.getbuffer().nbytes,
    )
    return buffer


def import_library_zip(
    db: Session,
    zip_data: bytes,
    organization_id: str,
) -> dict[str, Any]:
    """Import a library from a ZIP file.

    Creates a new library with new IDs (no collision with existing data).
    Does NOT re-run import plugins — structured content is already in the ZIP.

    Args:
        db: Database session.
        zip_data: Raw ZIP file bytes.
        organization_id: Target organization.

    Returns:
        Dict with ``library_id``, ``library_name``, ``item_count``.

    Raises:
        ValueError: If the ZIP or manifest is invalid.
    """
    ensure_organization(db, organization_id)

    try:
        zf_obj = zipfile.ZipFile(BytesIO(zip_data), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid ZIP file: {exc}") from exc

    with zf_obj as zf:
        if "manifest.json" not in zf.namelist():
            raise ValueError("ZIP is missing manifest.json")

        manifest = json.loads(zf.read("manifest.json"))

        if manifest.get("format_version") != "1.0":
            raise ValueError(
                f"Unsupported manifest version: {manifest.get('format_version')}"
            )
        if manifest.get("type") != "library_export":
            raise ValueError(
                f"Unexpected manifest type: {manifest.get('type')}"
            )

        lib_meta = manifest.get("library", {})
        lib_name = lib_meta.get("name", f"Imported Library {uuid.uuid4().hex[:6]}")
        import_config = lib_meta.get("import_config")

        new_lib_id = str(uuid.uuid4())
        create_library(
            db, new_lib_id, organization_id, lib_name, import_config
        )

        items_created = 0
        for item_manifest in manifest.get("items", []):
            old_item_id = item_manifest.get("id", "")
            new_item_id = str(uuid.uuid4())

            permalink_base = (
                f"{PERMALINK_PREFIX}/{organization_id}/{new_lib_id}/{new_item_id}"
            )

            new_item_dir = CONTENT_DIR / organization_id / new_lib_id / new_item_id
            new_item_dir.mkdir(parents=True, exist_ok=True)

            prefix = f"content/{old_item_id}/"
            resolved_base = new_item_dir.resolve()
            for zip_entry in zf.namelist():
                if zip_entry.startswith(prefix) and not zip_entry.endswith("/"):
                    relative = zip_entry[len(prefix):]
                    target = (new_item_dir / relative).resolve()
                    # ZIP slip guard: ensure target stays within the item dir.
                    if not target.is_relative_to(resolved_base):
                        logger.warning("Zip slip attempt blocked: %s", zip_entry)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(zip_entry))

            _regenerate_metadata(new_item_dir, new_item_id, permalink_base, item_manifest)

            pages_dir = new_item_dir / "content" / "pages"
            images_dir = new_item_dir / "content" / "images"
            page_count = len(list(pages_dir.glob("*.md"))) if pages_dir.is_dir() else 0
            image_count = len(list(images_dir.iterdir())) if images_dir.is_dir() else 0

            metadata_on_disk = None
            metadata_path = new_item_dir / "metadata.json"
            if metadata_path.is_file():
                metadata_on_disk = json.loads(metadata_path.read_text("utf-8"))

            item = ContentItem(
                id=new_item_id,
                library_id=new_lib_id,
                organization_id=organization_id,
                title=item_manifest.get("title", "Untitled"),
                source_type=item_manifest.get("source_type", "file"),
                original_filename=item_manifest.get("original_filename"),
                content_type=item_manifest.get("content_type"),
                base_path=str(new_item_dir),
                original_path=(
                    str(new_item_dir / "original")
                    if (new_item_dir / "original").is_dir()
                    else None
                ),
                full_markdown_path=str(new_item_dir / "content" / "full.md"),
                page_count=page_count,
                image_count=image_count,
                permalink_base=permalink_base,
                metadata_=json.dumps(metadata_on_disk) if metadata_on_disk else None,
                import_plugin=item_manifest.get("import_plugin", "unknown"),
                import_params=json.dumps(item_manifest.get("import_params")),
                status="ready",
            )
            db.add(item)
            items_created += 1

        db.commit()

    logger.info(
        "Imported library %s (%s): %d items", new_lib_id, lib_name, items_created
    )
    return {
        "library_id": new_lib_id,
        "library_name": lib_name,
        "item_count": items_created,
    }


def _regenerate_metadata(
    item_dir: Path,
    item_id: str,
    permalink_base: str,
    item_manifest: dict[str, Any],
) -> None:
    """Regenerate metadata.json with new item ID and permalinks.

    Args:
        item_dir: Path to the item's content directory.
        item_id: New item UUID.
        permalink_base: New permalink base path.
        item_manifest: Manifest entry for this item.
    """
    pages_dir = item_dir / "content" / "pages"
    images_dir = item_dir / "content" / "images"

    page_links = []
    if pages_dir.is_dir():
        for p in sorted(pages_dir.glob("*.md")):
            page_links.append(f"{permalink_base}/content/pages/{p.name}")

    image_links = []
    if images_dir.is_dir():
        for img in sorted(images_dir.iterdir()):
            if img.is_file():
                image_links.append(f"{permalink_base}/content/images/{img.name}")

    original_link = None
    orig_dir = item_dir / "original"
    if orig_dir.is_dir():
        for f in orig_dir.iterdir():
            if f.is_file():
                original_link = f"{permalink_base}/original/{f.name}"
                break

    metadata = {
        "item_id": item_id,
        "title": item_manifest.get("title", "Untitled"),
        "source_type": item_manifest.get("source_type"),
        "original_filename": item_manifest.get("original_filename"),
        "content_type": item_manifest.get("content_type"),
        "import_plugin": item_manifest.get("import_plugin"),
        "permalinks": {
            "original": original_link,
            "full_markdown": f"{permalink_base}/content/full.md",
            "pages": page_links,
            "images": image_links,
        },
    }

    # Merge in any extra metadata from the manifest.
    old_meta = item_manifest.get("metadata") or {}
    for key in ("page_count", "language", "character_count", "description", "citation"):
        if key in old_meta:
            metadata[key] = old_meta[key]

    metadata_path = item_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
