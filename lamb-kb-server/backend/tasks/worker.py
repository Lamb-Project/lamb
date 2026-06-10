"""Async worker loop that processes ingestion jobs from the SQLite queue.

Design:
    - Jobs are persisted to the ``ingestion_jobs`` table so they survive
      restarts.
    - An ``asyncio.Semaphore`` caps concurrent processing at
      ``MAX_CONCURRENT_INGESTIONS``.
    - The worker polls for pending jobs every few seconds.
    - Each job runs in a thread pool (``run_in_executor``) because chunking
      and embedding are synchronous CPU/IO bound operations that would
      otherwise block the event loop.
    - Embedding credentials are held in an in-memory dict keyed by job id
      and are popped (never persisted) when the worker picks a job up.
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from config import INGESTION_TASK_TIMEOUT_SECONDS, MAX_CONCURRENT_INGESTIONS
from database.connection import get_session_direct
from database.models import Collection, IngestionJob
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
_executor: ThreadPoolExecutor | None = None
_running = False

# In-memory store for embedding credentials — never written to disk (ADR-4).
# Maps job_id → credentials dict. Entries are removed once the worker picks
# them up. If the service restarts before the worker picks up a job, the
# credentials are lost and the job fails cleanly — exactly the behavior the
# Library Manager uses for its own API keys.
_job_credentials: dict[str, dict[str, str]] = {}

# How often (seconds) the worker checks for new pending jobs.
_POLL_INTERVAL = 2.0

# Maximum number of retry attempts before a stale job is marked failed.
_MAX_ATTEMPTS = int(os.getenv("KB_MAX_JOB_ATTEMPTS", "3"))


def store_credentials(job_id: str, credentials: dict[str, str] | None) -> None:
    """Hold embedding credentials in memory for a job until the worker runs it.

    Called by ``ingestion_service`` immediately after committing the job row
    to SQLite. Credentials live only in the module-level dict and are popped
    by the worker when processing starts.

    Args:
        job_id: The ingestion job ID.
        credentials: Credentials dict (api_key, api_endpoint, ...), or None.
    """
    if credentials:
        _job_credentials[job_id] = credentials


def is_worker_running() -> bool:
    """Check if the worker loop is active."""
    return _running


def _get_db() -> Session:
    """Obtain a database session outside of the FastAPI request cycle."""
    return get_session_direct()


def _process_job_sync(job_id: str) -> None:
    """Run a single ingestion job (synchronous, executed in thread pool).

    Steps:
        1. Load the job from the database.
        2. Pop credentials from the in-memory store.
        3. Load the owning collection record.
        4. Delegate to ``ingestion_service.execute_ingestion_job``.
        5. Update job + collection counters on success/failure.

    Args:
        job_id: Primary key of the ``ingestion_jobs`` row.
    """
    # Local import to avoid a circular dependency at module load time.
    from services.ingestion_service import execute_ingestion_job  # noqa: PLC0415

    db = _get_db()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job is None:
            logger.error("Job %s not found in database", job_id)
            return

        credentials = _job_credentials.pop(job_id, {})

        collection = (
            db.query(Collection).filter(Collection.id == job.collection_id).first()
        )
        if collection is None:
            error_msg = (
                f"Collection {job.collection_id} was deleted before "
                "this ingestion job ran."
            )
            job.status = "failed"
            job.error_message = error_msg
            job.completed_at = datetime.now(UTC)
            db.commit()
            logger.error("Job %s aborted — collection missing", job_id)
            return

        job.status = "processing"
        job.started_at = datetime.now(UTC)
        job.attempts += 1
        db.commit()

        logger.info(
            "Processing ingestion job %s (collection=%s, attempt=%d)",
            job_id,
            job.collection_id,
            job.attempts,
        )

        execute_ingestion_job(db, job, collection, credentials)

        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        db.commit()

        logger.info(
            "Job %s completed — %d documents, %d chunks",
            job_id,
            job.documents_processed,
            job.chunks_created,
        )

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        try:
            error_msg = f"Ingestion failed: {type(exc).__name__}: {str(exc)[:500]}"
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = error_msg
                job.completed_at = datetime.now(UTC)
                db.commit()
        except Exception:
            logger.exception("Failed to record error for job %s", job_id)
    finally:
        db.close()


async def _process_job_async(job_id: str) -> None:
    """Wrap the synchronous job processor in the thread pool with a timeout."""
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(_executor, _process_job_sync, job_id),
            timeout=INGESTION_TASK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.error(
            "Job %s timed out after %ds", job_id, INGESTION_TASK_TIMEOUT_SECONDS
        )
        timeout_msg = (
            f"Ingestion timed out after {INGESTION_TASK_TIMEOUT_SECONDS} seconds."
        )
        db = _get_db()
        try:
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = timeout_msg
                job.completed_at = datetime.now(UTC)
                db.commit()
        finally:
            db.close()


_dispatched: set[str] = set()


async def _poll_loop() -> None:
    """Continuously poll for pending jobs and dispatch them.

    Each pending job is dispatched as an ``asyncio.Task`` guarded by the
    semaphore, so at most ``MAX_CONCURRENT_INGESTIONS`` jobs run
    concurrently. The ``_dispatched`` set prevents the same job from being
    dispatched twice between poll cycles.
    """
    while _running:
        db = _get_db()
        try:
            pending_jobs = (
                db.query(IngestionJob)
                .filter(IngestionJob.status == "pending")
                .order_by(IngestionJob.created_at.asc())
                .limit(MAX_CONCURRENT_INGESTIONS)
                .all()
            )
            job_ids = [j.id for j in pending_jobs if j.id not in _dispatched]
        finally:
            db.close()

        for job_id in job_ids:
            _dispatched.add(job_id)
            try:
                await _semaphore.acquire()
                asyncio.create_task(_run_with_semaphore(job_id))
            except (asyncio.CancelledError, Exception):
                _dispatched.discard(job_id)
                raise

        await asyncio.sleep(_POLL_INTERVAL)


async def _run_with_semaphore(job_id: str) -> None:
    """Run a single job and release the semaphore when done."""
    try:
        await _process_job_async(job_id)
    finally:
        _dispatched.discard(job_id)
        _semaphore.release()


async def start_worker() -> None:
    """Start the background worker loop.

    Called once during FastAPI ``lifespan`` startup.
    """
    global _semaphore, _executor, _running

    _semaphore = asyncio.Semaphore(MAX_CONCURRENT_INGESTIONS)
    _executor = ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_INGESTIONS,
        thread_name_prefix="ingestion-worker",
    )
    _running = True

    logger.info(
        "Ingestion worker started (max_concurrent=%d, timeout=%ds)",
        MAX_CONCURRENT_INGESTIONS,
        INGESTION_TASK_TIMEOUT_SECONDS,
    )

    asyncio.create_task(_poll_loop())


async def stop_worker() -> None:
    """Signal the worker loop to stop and shut down the thread pool.

    Called during FastAPI ``lifespan`` shutdown.
    """
    global _running
    _running = False

    if _executor:
        _executor.shutdown(wait=False)

    _dispatched.clear()
    logger.info("Ingestion worker stopped")


def recover_stale_jobs() -> None:
    """Reset stale jobs left in 'processing' after a crash.

    Jobs exceeding ``_MAX_ATTEMPTS`` are marked failed instead of being
    retried. Called once at startup, before the worker begins polling.
    """
    db = _get_db()
    try:
        stale = (
            db.query(IngestionJob)
            .filter(IngestionJob.status == "processing")
            .all()
        )
        for job in stale:
            if job.attempts >= _MAX_ATTEMPTS:
                error_msg = (
                    f"Exceeded max attempts ({_MAX_ATTEMPTS}) — "
                    "last seen processing when service restarted."
                )
                job.status = "failed"
                job.error_message = error_msg
                logger.warning(
                    "Job %s exceeded max attempts, marked failed", job.id
                )
            else:
                job.status = "pending"
                logger.info(
                    "Job %s reset to pending (attempt %d)", job.id, job.attempts
                )
        if stale:
            db.commit()
            logger.info("Recovered %d stale jobs", len(stale))
    finally:
        db.close()
