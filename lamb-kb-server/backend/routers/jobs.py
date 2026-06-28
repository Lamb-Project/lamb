"""Ingestion job status routes."""

import logging

from config import MAX_JOB_ATTEMPTS
from database.connection import get_session
from database.models import IngestionJob
from dependencies import verify_token
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.jobs import JobStatusResponse, RetryAvailability
from services.ingestion_service import cancel_job as cancel_job_service
from sqlalchemy.orm import Session
from tasks.worker import retry_available

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


def _load_job(db: Session, job_id: str) -> IngestionJob:
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return job


@router.get("/{job_id}/retry-available", response_model=RetryAvailability)
async def get_retry_available(
    job_id: str,
    db: Session = Depends(get_session),
) -> RetryAvailability:
    """Report whether a failed job can still be retried in place.

    A retry is possible only while the job is ``failed``, has attempts left,
    and its embedding credentials are still cached in memory (within the
    retention window and since the last restart). The UI uses this to decide
    whether to show a Retry affordance.
    """
    job = _load_job(db, job_id)
    available = (
        job.status == "failed"
        and job.attempts < MAX_JOB_ATTEMPTS
        and retry_available(job_id)
    )
    return RetryAvailability(
        available=available,
        attempts=job.attempts,
        max_attempts=MAX_JOB_ATTEMPTS,
    )


@router.post("/{job_id}/retry", response_model=JobStatusResponse)
async def retry_job(
    job_id: str,
    db: Session = Depends(get_session),
) -> JobStatusResponse:
    """Retry a failed ingestion job, reusing its cached credentials.

    The document payload is already persisted in the job row, and the
    embedding credentials are kept in memory across attempts, so a retry does
    not require the client to re-send anything. The job is flipped back to
    ``pending`` and the worker picks it up on the next poll.

    Errors:
        404 — job not found.
        409 — job is not ``failed``, or has exhausted ``MAX_JOB_ATTEMPTS``.
        410 — credentials are no longer cached (retention window elapsed or
              the service restarted); the client must re-submit add-content.
    """
    job = _load_job(db, job_id)

    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only failed jobs can be retried (status='{job.status}').",
        )
    if job.attempts >= MAX_JOB_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job has exhausted its retries ({MAX_JOB_ATTEMPTS} attempts).",
        )
    if not retry_available(job_id):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Retry window expired — credentials are no longer held. "
                "Re-submit the content to index it again."
            ),
        )

    job.status = "pending"
    job.error_message = None
    job.completed_at = None
    db.commit()
    db.refresh(job)
    logger.info("Job %s queued for retry (attempt %d)", job_id, job.attempts + 1)
    return JobStatusResponse.model_validate(job)
