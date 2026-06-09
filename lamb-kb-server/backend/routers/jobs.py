"""Ingestion job status routes."""

import logging

from database.connection import get_session
from database.models import IngestionJob
from dependencies import verify_token
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.jobs import JobStatusResponse
from services.ingestion_service import cancel_job as cancel_job_service
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    dependencies=[Depends(verify_token)],
)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_session),
) -> JobStatusResponse:
    """Get the status of an ingestion job.

    Poll this endpoint after calling ``POST /collections/{id}/add-content``
    to track ingestion progress.

    Args:
        job_id: Ingestion job UUID (returned by add-content).
        db: Database session.

    Returns:
        Full job status including progress counters and timestamps.
    """
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return JobStatusResponse.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobStatusResponse)
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_session),
) -> JobStatusResponse:
    """Cancel a pending or in-flight ingestion job.

    Flips the job's status to ``cancelled``. The worker checks this between
    documents and bails out cleanly. Chunks already written for earlier
    documents in the job are NOT rolled back — callers should follow up with
    ``DELETE /collections/{id}/content/{source_item_id}`` to remove them.

    Idempotent: cancelling a job that is already in a terminal state
    (``completed`` / ``failed`` / ``cancelled``) is a no-op and the current
    row is returned unchanged.
    """
    job = cancel_job_service(db, job_id)
    return JobStatusResponse.model_validate(job)
