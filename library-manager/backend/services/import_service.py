"""Orchestrates document import: queues jobs and executes them.

This module is the bridge between the API layer (which queues jobs) and the
plugin layer (which does the actual conversion). It also writes the
structured content to disk and updates database records.
"""

import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import CONTENT_DIR, PERMALINK_PREFIX
from database.models import ContentImage, ContentItem, ImportJob
from plugins.base import PluginRegistry
from sqlalchemy.orm import Session
from tasks.worker import store_api_keys

from services import content_service
from services.library_service import ensure_organization

logger = logging.getLogger(__name__)


def queue_file_import(
    db: Session,
    library_id: str,
    organization_id: str,
    title: str,
    plugin_name: str,
    file_path: str,
    original_filename: str,
    content_type: str | None = None,
    file_size: int | None = None,
    plugin_params: dict[str, Any] | None = None,
    api_keys: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Create a content item and queue an import job for a file upload.

    Args:
        db: Database session.
        library_id: Parent library UUID.
        organization_id: Organization ID.
        title: Document title.
        plugin_name: Import plugin to use.
        file_path: Path to the uploaded file on disk.
        original_filename: Original filename from the upload.
        content_type: MIME type.
        file_size: File size in bytes.
        plugin_params: Plugin-specific parameters.
        api_keys: Org API keys (held in job row until processing starts).

    Returns:
        Tuple of (content_item_id, job_id).
    """
    item_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    ensure_organization(db, organization_id)

    permalink_base = f"{PERMALINK_PREFIX}/{organization_id}/{library_id}/{item_id}"

    item = ContentItem(
        id=item_id,
        library_id=library_id,
        organization_id=organization_id,
        title=title,
        source_type="file",
        original_filename=original_filename,
        content_type=content_type,
        file_size=file_size,
        base_path=str(CONTENT_DIR / organization_id / library_id / item_id),
        permalink_base=permalink_base,
        import_plugin=plugin_name,
        import_params=json.dumps(plugin_params) if plugin_params else None,
        status="pending",
    )
    db.add(item)

    job = ImportJob(
        id=job_id,
        content_item_id=item_id,
        library_id=library_id,
        organization_id=organization_id,
        source_type="file",
        plugin_name=plugin_name,
        plugin_params=json.dumps(plugin_params) if plugin_params else None,
        source_path=file_path,
        title=title,
        status="pending",
    )
    db.add(job)
    db.commit()
    store_api_keys(job_id, api_keys)

    logger.info(
        "Queued file import: item=%s, job=%s, plugin=%s",
        item_id, job_id, plugin_name,
    )
    return item_id, job_id


def queue_url_import(
    db: Session,
    library_id: str,
    organization_id: str,
    title: str,
    plugin_name: str,
    url: str,
    plugin_params: dict[str, Any] | None = None,
    api_keys: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Create a content item and queue an import job for a URL.

    Args:
        db: Database session.
        library_id: Parent library UUID.
        organization_id: Organization ID.
        title: Document title.
        plugin_name: Import plugin to use.
        url: URL to import.
        plugin_params: Plugin-specific parameters.
        api_keys: Org API keys.

    Returns:
        Tuple of (content_item_id, job_id).
    """
    item_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    ensure_organization(db, organization_id)

    permalink_base = f"{PERMALINK_PREFIX}/{organization_id}/{library_id}/{item_id}"

    item = ContentItem(
        id=item_id,
        library_id=library_id,
        organization_id=organization_id,
        title=title,
        source_type="url",
        source_url=url,
        base_path=str(CONTENT_DIR / organization_id / library_id / item_id),
        permalink_base=permalink_base,
        import_plugin=plugin_name,
        import_params=json.dumps(plugin_params) if plugin_params else None,
        status="pending",
    )
    db.add(item)

    job = ImportJob(
        id=job_id,
        content_item_id=item_id,
        library_id=library_id,
        organization_id=organization_id,
        source_type="url",
        plugin_name=plugin_name,
        plugin_params=json.dumps(plugin_params) if plugin_params else None,
        source_url=url,
        title=title,
        status="pending",
    )
    db.add(job)
    db.commit()
    store_api_keys(job_id, api_keys)

    logger.info("Queued URL import: item=%s, job=%s, url=%s", item_id, job_id, url)
    return item_id, job_id


def queue_youtube_import(
    db: Session,
    library_id: str,
    organization_id: str,
    title: str,
    plugin_name: str,
    video_url: str,
    plugin_params: dict[str, Any] | None = None,
    api_keys: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Create a content item and queue an import job for a YouTube video.

    Args:
        db: Database session.
        library_id: Parent library UUID.
        organization_id: Organization ID.
        title: Document title.
        plugin_name: Import plugin to use.
        video_url: YouTube video URL.
        plugin_params: Plugin-specific parameters.
        api_keys: Org API keys.

    Returns:
        Tuple of (content_item_id, job_id).
    """
    item_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    ensure_organization(db, organization_id)

    permalink_base = f"{PERMALINK_PREFIX}/{organization_id}/{library_id}/{item_id}"

    item = ContentItem(
        id=item_id,
        library_id=library_id,
        organization_id=organization_id,
        title=title,
        source_type="youtube",
        source_url=video_url,
        base_path=str(CONTENT_DIR / organization_id / library_id / item_id),
        permalink_base=permalink_base,
        import_plugin=plugin_name,
        import_params=json.dumps(plugin_params) if plugin_params else None,
        status="pending",
    )
    db.add(item)

    job = ImportJob(
        id=job_id,
        content_item_id=item_id,
        library_id=library_id,
        organization_id=organization_id,
        source_type="youtube",
        plugin_name=plugin_name,
        plugin_params=json.dumps(plugin_params) if plugin_params else None,
        source_url=video_url,
        title=title,
        status="pending",
    )
    db.add(job)
    db.commit()
    store_api_keys(job_id, api_keys)

    logger.info("Queued YouTube import: item=%s, job=%s", item_id, job_id)
    return item_id, job_id


# ---------------------------------------------------------------------------
# Job execution (called by the worker in tasks/worker.py)
# ---------------------------------------------------------------------------


def execute_import_job(
    db: Session,
    job: ImportJob,
    api_keys: dict[str, str],
) -> None:
    """Execute a single import job using the specified plugin.

    This function is called by the background worker. It:
    1. Instantiates the plugin.
    2. Runs the plugin's ``import_content`` method.
    3. Writes the structured content to disk.
    4. Updates the ContentItem record with results.

    Args:
        db: Database session.
        job: The ImportJob row (already marked as ``processing``).
        api_keys: Decrypted API keys for this job.

    Raises:
        RuntimeError: If the plugin is not found or import fails.
    """
    plugin = PluginRegistry.get_plugin(job.plugin_name)
    if plugin is None:
        raise RuntimeError(f"Plugin not found: {job.plugin_name}")

    source = job.source_path or job.source_url
    if not source:
        raise RuntimeError(f"Job {job.id} has no source_path or source_url")

    params = json.loads(job.plugin_params) if job.plugin_params else {}
    sanitized_params = PluginRegistry.sanitize_params(job.plugin_name, params)

    result = plugin.import_content(
        source, api_keys=api_keys, **sanitized_params
    )

    original_file_path = Path(job.source_path) if job.source_path else None
    item = db.query(ContentItem).filter(ContentItem.id == job.content_item_id).first()
    if item is None:
        raise RuntimeError(f"ContentItem {job.content_item_id} not found")

    # Override temp filename with the real original name in plugin output.
    real_filename = item.original_filename
    if real_filename and job.source_type == "file":
        result.source_ref["original_filename"] = real_filename
        if "original_filename" in result.metadata:
            result.metadata["original_filename"] = real_filename

    item_dir = CONTENT_DIR / job.organization_id / job.library_id / item.id
    try:
        base_path = content_service.write_structured_content(
            item_id=item.id,
            library_id=job.library_id,
            organization_id=job.organization_id,
            title=job.title,
            full_text=result.full_text,
            pages=result.pages,
            images=result.images,
            item_metadata=result.metadata,
            source_ref=result.source_ref,
            original_file_path=original_file_path,
            original_filename=item.original_filename,
        )
    except Exception:
        if item_dir.exists():
            shutil.rmtree(item_dir, ignore_errors=True)
        raise

    for img in result.images:
        db_img = ContentImage(
            id=str(uuid.uuid4()),
            content_item_id=item.id,
            image_path=f"content/images/{img.filename}",
            llm_description=img.description,
            page_number=img.page_number,
        )
        db.add(db_img)

    metadata_on_disk = content_service.read_metadata_json(
        job.organization_id, job.library_id, item.id
    )

    item.status = "ready"
    item.base_path = str(base_path)
    item.full_markdown_path = str(base_path / "content" / "full.md")
    item.page_count = len(result.pages)
    item.image_count = len(result.images)
    item.metadata_ = json.dumps(metadata_on_disk) if metadata_on_disk else None
    item.source_ref = json.dumps(result.source_ref)
    item.processing_stats = json.dumps(result.metadata.get("processing_stats"))
    item.updated_at = datetime.now(UTC)

    if result.metadata.get("file_size"):
        item.file_size = result.metadata["file_size"]
    if result.metadata.get("content_type"):
        item.content_type = result.metadata["content_type"]
    if result.metadata.get("character_count"):
        pass  # Stored in metadata JSON, not a separate column.

    db.commit()

    if job.source_path:
        temp_file = Path(job.source_path)
        if temp_file.is_file():
            try:
                temp_file.unlink()
            except OSError:
                logger.warning("Failed to delete temp file: %s", temp_file)

    logger.info("Import job %s completed: item %s is ready", job.id, item.id)
