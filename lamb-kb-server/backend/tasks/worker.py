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
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from config import (
    INGESTION_TASK_TIMEOUT_SECONDS,
    MAX_CONCURRENT_INGESTIONS,
    MAX_JOB_ATTEMPTS,
    RETRY_CACHE_TTL_MINUTES,
)
from database.connection import get_session_direct
from database.models import Collection, IngestionJob
from sqlalchemy.orm import Session

_MAX_ATTEMPTS = MAX_JOB_ATTEMPTS

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
_executor: ThreadPoolExecutor | None = None
_running = False

# In-memory store for embedding credentials — never written to disk (ADR-4).
# Maps job_id → credentials dict. The document payload itself is persisted in
# the ``ingestion_jobs`` row, so only the credentials need to survive in
# memory. Unlike the original design (which popped credentials on first
# pickup), entries are RETAINED across attempts so a failed job can be retried
# without the client re-sending credentials. They are discarded when the job
# succeeds, exhausts its attempts, or ages past ``RETRY_CACHE_TTL_MINUTES``
# (see ``_purge_expired_credentials``). A restart still loses them, in which
# case a retry requires a fresh add-content request.
_job_credentials: dict[str, dict[str, str]] = {}
# Parallel map of job_id → when the credentials were stored, for TTL expiry.
_job_cred_stored_at: dict[str, datetime] = {}

# How often (seconds) the worker checks for new pending jobs.
_POLL_INTERVAL = 2.0
# How often (seconds) expired credentials are purged from the retry cache.
_CLEANUP_INTERVAL = 600.0


def store_credentials(job_id: str, credentials: dict[str, str] | None) -> None:
    """Hold embedding credentials in memory for a job and its retries.

    Called by ``ingestion_service`` immediately after committing the job row
    to SQLite. Credentials live only in the module-level dict and are retained
    until the job reaches a terminal state, exhausts its attempts, or the
    retention window elapses.

    Args:
        job_id: The ingestion job ID.
        credentials: Credentials dict (api_key, api_endpoint, ...), or None.
    """
    if credentials:
        _job_credentials[job_id] = credentials
        _job_cred_stored_at[job_id] = datetime.now(UTC)


def _discard_credentials(job_id: str) -> None:
    """Forget a job's cached credentials (terminal state or exhausted retries)."""
    _job_credentials.pop(job_id, None)
    _job_cred_stored_at.pop(job_id, None)


def retry_available(job_id: str) -> bool:
    """Whether a failed job can still be retried with its cached credentials.

    True only while the credentials remain in memory (i.e. within the
    retention window and before a restart). The HTTP layer combines this with
    the job's status and attempt count to decide whether to offer a retry.
    """
    return job_id in _job_credentials


def _purge_expired_credentials() -> None:
    """Drop cached credentials older than ``RETRY_CACHE_TTL_MINUTES``.

    Bounds the in-memory footprint and enforces the retention window: once a
    failed job's credentials age out, a retry must re-send them. Called
    periodically by the cleanup loop and once during stale-job recovery.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=RETRY_CACHE_TTL_MINUTES)
    expired = [jid for jid, ts in _job_cred_stored_at.items() if ts < cutoff]
    for jid in expired:
        _discard_credentials(jid)
    if expired:
        logger.info(
            "Purged credentials for %d job(s) past the retry window", len(expired)
        )


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
        5. Update job + collection counters on success/failure/cancellation.

    A cooperative cancellation (``POST /jobs/{id}/cancel`` followed by the
    ingestion loop's per-document status check raising ``JobCancelledError``)
    is treated as a clean exit: the row stays in ``cancelled`` rather than
    being flipped to ``failed``.

    Args:
        job_id: Primary key of the ``ingestion_jobs`` row.
    """
    # Local import to avoid a circular dependency at module load time.
    from services.ingestion_service import (  # noqa: PLC0415
        JobCancelledError,
        execute_ingestion_job,
    )

    db = _get_db()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job is None:
            logger.error("Job %s not found in database", job_id)
            return

        # The job may have been cancelled before the worker picked it up;
        # respect that and return without flipping back to processing.
        if job.status == "cancelled":
            logger.info("Job %s was cancelled before pickup — skipping", job_id)
            _discard_credentials(job_id)
            return

        # Read (do not pop) so the credentials survive for a possible retry.
        credentials = _job_credentials.get(job_id, {})

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
            # The collection is gone — retrying cannot help, so free creds.
            _discard_credentials(job_id)
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

        try:
            execute_ingestion_job(db, job, collection, credentials)
        except JobCancelledError as exc:
            # Status was already set to 'cancelled' by the canceller; the loop
            # noticed and bailed out. Leave the row alone so the cancellation
            # timestamp / status survive.
            logger.info("Job %s cancelled cooperatively: %s", job_id, exc)
            _discard_credentials(job_id)
            return

        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        db.commit()
        _discard_credentials(job_id)

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
            # Never override a cancellation with a generic failure — the user
            # explicitly stopped this job and we should not surface a false
            # error in its place.
            if job and job.status != "cancelled":
                job.status = "failed"
                job.error_message = error_msg
                job.completed_at = datetime.now(UTC)
                db.commit()
                # Keep the credentials so the user can retry, unless the job
                # has exhausted its attempts — then a retry is not allowed.
                if job.attempts >= _MAX_ATTEMPTS:
                    _discard_credentials(job_id)
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
                if job.attempts >= _MAX_ATTEMPTS:
                    _discard_credentials(job_id)
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
    asyncio.create_task(_cleanup_loop())


async def _cleanup_loop() -> None:
    """Periodically purge credentials of jobs past the retry window."""
    while _running:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        try:
            _purge_expired_credentials()
        except Exception:  # noqa: BLE001 — never let cleanup kill the loop
            logger.exception("Credential purge failed")


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
    _purge_expired_credentials()
    db = _get_db()
    try:
        stale = (
            db.query(IngestionJob)
            .filter(IngestionJob.status == "processing")
            .all()
        )
        for job in stale:
            if job.attempts >= MAX_JOB_ATTEMPTS:
                error_msg = (
                    f"Exceeded max attempts ({MAX_JOB_ATTEMPTS}) — "
                    "last seen processing when service restarted."
                )
                job.status = "failed"
                job.error_message = error_msg
                _discard_credentials(job.id)
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
