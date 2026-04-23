"""Async worker loop that processes import jobs from the SQLite-backed queue.

Design:
    - Jobs are persisted to the ``import_jobs`` table so they survive restarts.
    - An ``asyncio.Semaphore`` caps concurrent processing to
      ``MAX_CONCURRENT_IMPORTS``.
    - The worker loop polls for pending jobs every few seconds.
    - Each job is executed in a thread pool (``run_in_executor``) because
      import plugins are synchronous (file I/O, network calls, LLM APIs).
    - On completion the job row is updated; on failure the error is recorded.
    - API keys are cleared from the job row as soon as processing starts.
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from config import IMPORT_TASK_TIMEOUT_SECONDS, MAX_CONCURRENT_IMPORTS
from database.connection import get_session_direct
from database.models import ContentItem, ImportJob
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
_executor: ThreadPoolExecutor | None = None
_running = False

# In-memory store for API keys — never written to disk.
# Maps job_id → api_keys dict. Entries are removed once the worker picks them up.
_job_api_keys: dict[str, dict[str, str]] = {}

# How often (seconds) the worker checks for new pending jobs.
_POLL_INTERVAL = 2.0


def store_api_keys(job_id: str, api_keys: dict[str, str] | None) -> None:
    """Hold API keys in memory for a job until the worker picks it up.

    Called by import_service after committing the job to SQLite. The keys
    live only in this dict and are popped by the worker when processing
    starts. If the service restarts before the worker picks up the job,
    the keys are lost and the import will run without them (plugins that
    need keys will fail and the job will be marked failed).

    Args:
        job_id: The import job ID.
        api_keys: API keys dict, or None.
    """
    if api_keys:
        _job_api_keys[job_id] = api_keys


def is_worker_running() -> bool:
    """Check if the worker loop is active."""
    return _running


def _get_db() -> Session:
    """Obtain a database session outside of the FastAPI request cycle."""
    return get_session_direct()


def _process_job_sync(job_id: str) -> None:
    """Run the import plugin for a single job (synchronous, in thread pool).

    This function:
      1. Loads the job from the database.
      2. Pops API keys from the in-memory store.
      3. Runs the appropriate import plugin.
      4. Writes structured content to disk.
      5. Updates the ``content_items`` and ``import_jobs`` rows.

    Args:
        job_id: Primary key of the ``import_jobs`` row.
    """
    # Import here to avoid circular imports at module load time.
    from services.import_service import execute_import_job  # noqa: PLC0415

    db = _get_db()
    try:
        job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if job is None:
            logger.error("Job %s not found in database", job_id)
            return

        api_keys = _job_api_keys.pop(job_id, {})

        job.status = "processing"
        job.started_at = datetime.now(UTC)
        job.attempts += 1
        db.commit()

        logger.info(
            "Processing job %s (item=%s, plugin=%s, attempt=%d)",
            job_id,
            job.content_item_id,
            job.plugin_name,
            job.attempts,
        )

        execute_import_job(db, job, api_keys)

        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        db.commit()

        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        try:
            # Store sanitized message for API consumers; full trace goes to logs only.
            error_msg = f"Import failed: {type(exc).__name__}: {str(exc)[:500]}"
            job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = error_msg
                job.completed_at = datetime.now(UTC)
                db.commit()

                item = (
                    db.query(ContentItem)
                    .filter(ContentItem.id == job.content_item_id)
                    .first()
                )
                if item:
                    item.status = "failed"
                    item.error_message = error_msg
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
            timeout=IMPORT_TASK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.error("Job %s timed out after %ds", job_id, IMPORT_TASK_TIMEOUT_SECONDS)
        timeout_msg = f"Import timed out after {IMPORT_TASK_TIMEOUT_SECONDS} seconds."
        db = _get_db()
        try:
            job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = timeout_msg
                job.completed_at = datetime.now(UTC)
                db.commit()

                item = (
                    db.query(ContentItem)
                    .filter(ContentItem.id == job.content_item_id)
                    .first()
                )
                if item:
                    item.status = "failed"
                    item.error_message = timeout_msg
                db.commit()
        finally:
            db.close()


_dispatched: set[str] = set()


async def _poll_loop() -> None:
    """Continuously poll for pending jobs and dispatch them.

    Each pending job is dispatched as an ``asyncio.Task`` guarded by
    the semaphore, so at most ``MAX_CONCURRENT_IMPORTS`` jobs run
    concurrently. The ``_dispatched`` set prevents the same job from
    being dispatched twice between poll cycles.
    """
    while _running:
        db = _get_db()
        try:
            pending_jobs = (
                db.query(ImportJob)
                .filter(ImportJob.status == "pending")
                .order_by(ImportJob.created_at.asc())
                .limit(MAX_CONCURRENT_IMPORTS)
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

    _semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMPORTS)
    _executor = ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_IMPORTS,
        thread_name_prefix="import-worker",
    )
    _running = True

    logger.info(
        "Import worker started (max_concurrent=%d, timeout=%ds)",
        MAX_CONCURRENT_IMPORTS,
        IMPORT_TASK_TIMEOUT_SECONDS,
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
    logger.info("Import worker stopped")


_MAX_ATTEMPTS = int(os.getenv("LM_MAX_JOB_ATTEMPTS", "3"))


def recover_stale_jobs() -> None:
    """Reset stale jobs that were left in 'processing' state after a crash.

    Called once at startup. Jobs exceeding ``_MAX_ATTEMPTS`` are marked as
    failed instead of being retried.
    """
    db = _get_db()
    try:
        stale = (
            db.query(ImportJob)
            .filter(ImportJob.status == "processing")
            .all()
        )
        for job in stale:
            if job.attempts >= _MAX_ATTEMPTS:
                error_msg = (
                    f"Exceeded max attempts ({_MAX_ATTEMPTS}) — "
                    f"last seen processing when service restarted."
                )
                job.status = "failed"
                job.error_message = error_msg

                item = (
                    db.query(ContentItem)
                    .filter(ContentItem.id == job.content_item_id)
                    .first()
                )
                if item:
                    item.status = "failed"
                    item.error_message = error_msg

                logger.warning("Job %s exceeded max attempts, marked failed", job.id)
            else:
                job.status = "pending"
                logger.info("Job %s reset to pending (attempt %d)", job.id, job.attempts)
        if stale:
            db.commit()
            logger.info("Recovered %d stale jobs", len(stale))
    finally:
        db.close()
