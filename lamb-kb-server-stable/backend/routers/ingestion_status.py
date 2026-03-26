"""
Ingestion Status Router - Endpoints for tracking ingestion job status.

This module provides endpoints for:
- Listing ingestion jobs for a collection
- Getting detailed status of a specific job
- Getting summary statistics
- Retrying failed jobs
- Cancelling processing jobs

All endpoints are nested under /collections/{collection_id}/ingestion-jobs
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from database.connection import get_db
from database.models import Collection, FileRegistry, FileStatus
from database.service import CollectionService
from schemas.files import (
    IngestionJobResponse,
    IngestionJobListResponse,
    IngestionStatusSummary,
    IngestionProgress,
    StatusCount,
    RetryIngestionRequest,
    IngestionStatus,
    ProcessingStats
)
from services.ingestion import IngestionService
from dependencies import verify_token


router = APIRouter(
    prefix="/collections",
    tags=["Ingestion Status"],
    dependencies=[Depends(verify_token)]
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _file_registry_to_job_response(
    file_reg: FileRegistry, 
    collection_name: Optional[str] = None
) -> IngestionJobResponse:
    """Convert FileRegistry model to IngestionJobResponse."""
    import json
    
    # Build progress object
    progress = IngestionProgress(
        current=file_reg.progress_current or 0,
        total=file_reg.progress_total or 0,
        percentage=file_reg.progress_percentage if hasattr(file_reg, 'progress_percentage') else 0.0,
        message=file_reg.progress_message
    )
    
    # Calculate duration if available
    duration = None
    if file_reg.processing_started_at and file_reg.processing_completed_at:
        delta = file_reg.processing_completed_at - file_reg.processing_started_at
        duration = delta.total_seconds()
    
    # Map FileStatus to IngestionStatus
    status_mapping = {
        FileStatus.PENDING: IngestionStatus.PENDING,
        FileStatus.PROCESSING: IngestionStatus.PROCESSING,
        FileStatus.COMPLETED: IngestionStatus.COMPLETED,
        FileStatus.FAILED: IngestionStatus.FAILED,
        FileStatus.CANCELLED: IngestionStatus.CANCELLED,
        FileStatus.DELETED: IngestionStatus.DELETED,
    }
    status = status_mapping.get(file_reg.status, IngestionStatus.PENDING)
    
    # Parse plugin_params if it's a string
    plugin_params = file_reg.plugin_params
    if isinstance(plugin_params, str):
        try:
            plugin_params = json.loads(plugin_params)
        except:
            plugin_params = {}
    
    # Parse processing_stats if it's a string
    processing_stats = None
    if hasattr(file_reg, 'processing_stats') and file_reg.processing_stats:
        stats_data = file_reg.processing_stats
        if isinstance(stats_data, str):
            try:
                stats_data = json.loads(stats_data)
            except:
                stats_data = None
        if stats_data:
            try:
                processing_stats = ProcessingStats(**stats_data)
            except Exception as e:
                # If parsing fails, try to return as dict wrapped in ProcessingStats
                print(f"WARNING: Failed to parse processing_stats: {e}")
                processing_stats = None
    
    return IngestionJobResponse(
        id=file_reg.id,
        job_id=file_reg.id,
        collection_id=file_reg.collection_id,
        collection_name=collection_name,
        original_filename=file_reg.original_filename,
        file_path=file_reg.file_path,
        file_url=file_reg.file_url,
        file_size=file_reg.file_size or 0,
        content_type=file_reg.content_type,
        plugin_name=file_reg.plugin_name,
        plugin_params=plugin_params or {},
        status=status,
        document_count=file_reg.document_count or 0,
        created_at=file_reg.created_at,
        updated_at=file_reg.updated_at,
        processing_started_at=file_reg.processing_started_at,
        processing_completed_at=file_reg.processing_completed_at,
        processing_duration_seconds=duration,
        progress=progress,
        error_message=file_reg.error_message,
        error_details=file_reg.error_details,
        processing_stats=processing_stats,
        owner=file_reg.owner
    )


def _get_collection_or_404(db: Session, collection_id: int) -> Collection:
    """Get collection or raise 404."""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(
            status_code=404,
            detail=f"Collection {collection_id} not found"
        )
    return collection


# ═══════════════════════════════════════════════════════════════════════════════
# LIST INGESTION JOBS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{collection_id}/ingestion-jobs",
    response_model=IngestionJobListResponse,
    summary="List ingestion jobs for a collection",
    description="""
    Get a paginated list of all ingestion jobs for a collection.
    
    Supports filtering by status and sorting by various fields.
    
    **Use Cases:**
    - Display job history in UI
    - Monitor active jobs
    - Find failed jobs for retry
    
    **Example:**
    ```bash
    # List all jobs
    curl 'http://localhost:9090/collections/1/ingestion-jobs' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    
    # List only failed jobs
    curl 'http://localhost:9090/collections/1/ingestion-jobs?status=failed' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    
    # List processing jobs, sorted by creation time
    curl 'http://localhost:9090/collections/1/ingestion-jobs?status=processing&sort_by=created_at&sort_order=asc' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    """,
    responses={
        200: {"description": "List of ingestion jobs"},
        404: {"description": "Collection not found"},
        401: {"description": "Unauthorized"}
    }
)
async def list_ingestion_jobs(
    collection_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(
        None, 
        description="Filter by status (pending, processing, completed, failed, cancelled, deleted)"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    sort_by: str = Query(
        "created_at", 
        description="Field to sort by",
        enum=["created_at", "updated_at", "status", "original_filename", "file_size"]
    ),
    sort_order: str = Query("desc", description="Sort order", enum=["asc", "desc"])
):
    """List all ingestion jobs for a collection with filtering and pagination."""
    
    # Verify collection exists
    collection = _get_collection_or_404(db, collection_id)
    
    # Build query
    query = db.query(FileRegistry).filter(FileRegistry.collection_id == collection_id)
    
    # Apply status filter
    if status:
        try:
            status_enum = FileStatus(status)
            query = query.filter(FileRegistry.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: pending, processing, completed, failed, cancelled, deleted"
            )
    
    # Get total count before pagination
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(FileRegistry, sort_by, FileRegistry.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Apply pagination
    jobs = query.offset(offset).limit(limit).all()
    
    # Convert to response models
    items = [_file_registry_to_job_response(job, collection.name) for job in jobs]
    
    return IngestionJobListResponse(
        total=total,
        items=items,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < total
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET SINGLE JOB STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{collection_id}/ingestion-jobs/{job_id}",
    response_model=IngestionJobResponse,
    summary="Get ingestion job status",
    description="""
    Get detailed status of a specific ingestion job.
    
    Returns comprehensive information including:
    - Current status
    - Progress (for long-running jobs)
    - Timing information
    - Error details (if failed)
    
    **Use Cases:**
    - Poll job status during processing
    - Get error details for failed jobs
    - Display job details in UI
    
    **Example:**
    ```bash
    curl 'http://localhost:9090/collections/1/ingestion-jobs/5' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    
    **Polling Recommendation:**
    - Poll every 1-2 seconds for active jobs
    - Stop polling when status is 'completed', 'failed', or 'cancelled'
    """,
    responses={
        200: {"description": "Job details"},
        404: {"description": "Collection or job not found"},
        401: {"description": "Unauthorized"}
    }
)
async def get_ingestion_job(
    collection_id: int,
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed status of a specific ingestion job."""
    
    # Verify collection exists
    collection = _get_collection_or_404(db, collection_id)
    
    # Get job
    job = db.query(FileRegistry).filter(
        FileRegistry.id == job_id,
        FileRegistry.collection_id == collection_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Ingestion job {job_id} not found in collection {collection_id}"
        )
    
    return _file_registry_to_job_response(job, collection.name)


# ═══════════════════════════════════════════════════════════════════════════════
# GET STATUS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{collection_id}/ingestion-status",
    response_model=IngestionStatusSummary,
    summary="Get ingestion status summary",
    description="""
    Get a summary of ingestion job statuses for a collection.
    
    Provides:
    - Total job count
    - Breakdown by status
    - Currently processing count
    - Recent failures (up to 5)
    - Oldest processing job (useful for detecting stuck jobs)
    
    **Use Cases:**
    - Dashboard overview
    - Collection health monitoring
    - Quick error detection
    
    **Example:**
    ```bash
    curl 'http://localhost:9090/collections/1/ingestion-status' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    """,
    responses={
        200: {"description": "Status summary"},
        404: {"description": "Collection not found"},
        401: {"description": "Unauthorized"}
    }
)
async def get_ingestion_status_summary(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """Get summary of ingestion statuses for a collection."""
    
    # Verify collection exists
    collection = _get_collection_or_404(db, collection_id)
    
    # Get counts by status
    status_counts = db.query(
        FileRegistry.status,
        func.count(FileRegistry.id).label('count')
    ).filter(
        FileRegistry.collection_id == collection_id
    ).group_by(FileRegistry.status).all()
    
    # Build status count object
    by_status = StatusCount()
    total = 0
    for status, count in status_counts:
        total += count
        if status == FileStatus.PENDING:
            by_status.pending = count
        elif status == FileStatus.PROCESSING:
            by_status.processing = count
        elif status == FileStatus.COMPLETED:
            by_status.completed = count
        elif status == FileStatus.FAILED:
            by_status.failed = count
        elif status == FileStatus.CANCELLED:
            by_status.cancelled = count
        elif status == FileStatus.DELETED:
            by_status.deleted = count
    
    # Get recent failures (up to 5)
    recent_failures = db.query(FileRegistry).filter(
        FileRegistry.collection_id == collection_id,
        FileRegistry.status == FileStatus.FAILED
    ).order_by(desc(FileRegistry.updated_at)).limit(5).all()
    
    recent_failure_responses = [
        _file_registry_to_job_response(f, collection.name) 
        for f in recent_failures
    ]
    
    # Get oldest processing job
    oldest_processing = db.query(FileRegistry).filter(
        FileRegistry.collection_id == collection_id,
        FileRegistry.status == FileStatus.PROCESSING
    ).order_by(asc(FileRegistry.processing_started_at)).first()
    
    oldest_processing_response = None
    if oldest_processing:
        oldest_processing_response = _file_registry_to_job_response(
            oldest_processing, collection.name
        )
    
    return IngestionStatusSummary(
        collection_id=collection_id,
        collection_name=collection.name,
        total_jobs=total,
        by_status=by_status,
        currently_processing=by_status.processing,
        recent_failures=recent_failure_responses,
        oldest_processing_job=oldest_processing_response
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY FAILED JOB
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{collection_id}/ingestion-jobs/{job_id}/retry",
    response_model=IngestionJobResponse,
    summary="Retry a failed ingestion job",
    description="""
    Retry a failed ingestion job.
    
    Only jobs with status 'failed' can be retried.
    
    Optionally, you can override the original plugin parameters.
    
    **What happens:**
    1. Job status is reset to 'pending'
    2. Error information is cleared
    3. Job is re-queued for processing
    4. A new background task is started
    
    **Example:**
    ```bash
    # Retry with original parameters
    curl -X POST 'http://localhost:9090/collections/1/ingestion-jobs/5/retry' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    
    # Retry with different chunk size
    curl -X POST 'http://localhost:9090/collections/1/ingestion-jobs/5/retry' \\
      -H 'Authorization: Bearer 0p3n-w3bu!' \\
      -H 'Content-Type: application/json' \\
      -d '{"override_params": {"chunk_size": 500}}'
    ```
    """,
    responses={
        200: {"description": "Job queued for retry"},
        400: {"description": "Job cannot be retried (not in failed state)"},
        404: {"description": "Collection or job not found"},
        401: {"description": "Unauthorized"}
    }
)
async def retry_ingestion_job(
    collection_id: int,
    job_id: int,
    request: Optional[RetryIngestionRequest] = None,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Retry a failed ingestion job."""
    
    # Verify collection exists
    collection = _get_collection_or_404(db, collection_id)
    
    # Get job
    job = db.query(FileRegistry).filter(
        FileRegistry.id == job_id,
        FileRegistry.collection_id == collection_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Ingestion job {job_id} not found in collection {collection_id}"
        )
    
    # Check if job can be retried
    if job.status != FileStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Only failed jobs can be retried. Current status: {job.status.value}"
        )
    
    # Get plugin params (potentially overridden)
    import json
    params = job.plugin_params
    if isinstance(params, str):
        params = json.loads(params)
    params = params or {}
    
    if request and request.override_params:
        params.update(request.override_params)
        job.plugin_params = params
    
    # Reset job state
    job.status = FileStatus.PENDING
    job.error_message = None
    job.error_details = None
    job.progress_current = 0
    job.progress_total = 0
    job.progress_message = "Queued for retry"
    job.processing_started_at = None
    job.processing_completed_at = None
    job.document_count = 0
    job.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(job)
    
    # Schedule background task
    from routers.collections import process_file_in_background_enhanced
    
    background_tasks.add_task(
        process_file_in_background_enhanced,
        job.file_path,
        job.plugin_name,
        params,
        collection_id,
        job.id
    )
    
    return _file_registry_to_job_response(job, collection.name)


# ═══════════════════════════════════════════════════════════════════════════════
# CANCEL PROCESSING JOB
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{collection_id}/ingestion-jobs/{job_id}/cancel",
    response_model=IngestionJobResponse,
    summary="Cancel a processing job",
    description="""
    Cancel an ingestion job that is currently processing or pending.
    
    **Note:** This is a best-effort cancellation:
    - For pending jobs: Job is marked as cancelled and won't start
    - For processing jobs: Job is marked as cancelled, but the current
      processing step may complete before the cancellation takes effect
    
    **What happens:**
    1. Job status is set to 'cancelled'
    2. Progress message is updated
    3. Any partial results may remain in the collection
    
    **Example:**
    ```bash
    curl -X POST 'http://localhost:9090/collections/1/ingestion-jobs/5/cancel' \\
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    """,
    responses={
        200: {"description": "Job cancelled"},
        400: {"description": "Job cannot be cancelled (already completed/failed)"},
        404: {"description": "Collection or job not found"},
        401: {"description": "Unauthorized"}
    }
)
async def cancel_ingestion_job(
    collection_id: int,
    job_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a processing or pending ingestion job."""
    
    # Verify collection exists
    collection = _get_collection_or_404(db, collection_id)
    
    # Get job
    job = db.query(FileRegistry).filter(
        FileRegistry.id == job_id,
        FileRegistry.collection_id == collection_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Ingestion job {job_id} not found in collection {collection_id}"
        )
    
    # Check if job can be cancelled
    if job.status not in [FileStatus.PENDING, FileStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail=f"Only pending or processing jobs can be cancelled. Current status: {job.status.value}"
        )
    
    # Update job state
    job.status = FileStatus.CANCELLED
    job.progress_message = "Cancelled by user"
    job.processing_completed_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(job)
    
    return _file_registry_to_job_response(job, collection.name)

