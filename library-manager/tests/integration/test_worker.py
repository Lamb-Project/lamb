"""Strengthened background-worker tests.

Goes beyond the old ``tests/test_load.py`` (which only asserted that every
import completed) by measuring *peak* concurrency against
``MAX_CONCURRENT_IMPORTS``, exercising every status transition (completed /
failed / timeout), and driving ``recover_stale_jobs`` directly.

Custom test plugins are registered into ``PluginRegistry._plugins`` and
always removed in a ``finally`` so the shared session registry never leaks.

Source under test: ``tasks/worker.py`` + ``services/import_service.py``.
"""

from __future__ import annotations

import contextlib
import threading
import time
import uuid
from datetime import UTC, datetime

import config
import pytest
from database.connection import get_session_direct
from database.models import ContentItem, ImportJob
from httpx import AsyncClient
from plugins.base import ImportResult, LibraryImportPlugin, PluginRegistry
from tasks import worker


@contextlib.contextmanager
def _registered(plugin_cls: type[LibraryImportPlugin]):
    """Register a plugin for the duration of the block, then restore.

    Snapshots the whole ``_plugins`` dict so a test never leaks a custom
    plugin into the shared session registry.
    """
    snapshot = dict(PluginRegistry._plugins)
    PluginRegistry._plugins[plugin_cls.name] = plugin_cls
    try:
        yield
    finally:
        PluginRegistry._plugins.clear()
        PluginRegistry._plugins.update(snapshot)


def _queue_job_row(plugin_name: str, library_id: str, org_id: str, source_url: str) -> str:
    """Insert a pending ImportJob + ContentItem row directly; return job_id."""
    item_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    session = get_session_direct()
    try:
        from services.library_service import ensure_organization  # noqa: PLC0415

        ensure_organization(session, org_id)
        session.add(
            ContentItem(
                id=item_id,
                library_id=library_id,
                organization_id=org_id,
                title="Worker Test Item",
                source_type="url",
                base_path=f"/tmp/{item_id}",
                permalink_base=f"/docs/{org_id}/{library_id}/{item_id}",
                import_plugin=plugin_name,
                status="pending",
            )
        )
        session.add(
            ImportJob(
                id=job_id,
                content_item_id=item_id,
                library_id=library_id,
                organization_id=org_id,
                source_type="url",
                plugin_name=plugin_name,
                source_url=source_url,
                title="Worker Test Item",
                status="pending",
            )
        )
        session.commit()
    finally:
        session.close()
    return job_id


# ---------------------------------------------------------------------------
# Concurrency cap
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_peak_concurrency_capped_at_max(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """Peak concurrent imports equals MAX_CONCURRENT_IMPORTS, never more."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    max_concurrent = config.MAX_CONCURRENT_IMPORTS
    assert max_concurrent == 3, "test pins the documented default of 3"

    lock = threading.Lock()
    state = {"current": 0, "peak": 0}

    class SlowConcurrencyPlugin(LibraryImportPlugin):
        name = "slow_concurrency_test"
        description = "Sleeps while tracking peak concurrency."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            with lock:
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            try:
                time.sleep(0.6)
            finally:
                with lock:
                    state["current"] -= 1
            return ImportResult(full_text="# done", pages=[], images=[], metadata={}, source_ref={})

        def get_parameters(self):
            return []

    num_jobs = max_concurrent + 3
    with _registered(SlowConcurrencyPlugin):
        job_ids = [
            _queue_job_row("slow_concurrency_test", lib_id, org_id, f"https://x/{i}")
            for i in range(num_jobs)
        ]
        await worker.start_worker()
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                session = get_session_direct()
                try:
                    done = (
                        session.query(ImportJob)
                        .filter(
                            ImportJob.id.in_(job_ids),
                            ImportJob.status.in_(("completed", "failed")),
                        )
                        .count()
                    )
                finally:
                    session.close()
                if done == num_jobs:
                    break
                import asyncio  # noqa: PLC0415

                await asyncio.sleep(0.2)
        finally:
            await worker.stop_worker()

    assert done == num_jobs, f"only {done}/{num_jobs} finished"
    assert state["peak"] == max_concurrent, (
        f"peak concurrency was {state['peak']}, expected {max_concurrent}"
    )


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


async def test_happy_path_status_transition(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """A successful job lands the item+job at completed/ready."""
    lib_id = library["id"]
    org_id = library["organization_id"]

    class OkPlugin(LibraryImportPlugin):
        name = "ok_transition_test"
        description = "Always succeeds."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(
                full_text="# ok", pages=[], images=[], metadata={}, source_ref={"type": "url"}
            )

        def get_parameters(self):
            return []

    with _registered(OkPlugin):
        job_id = _queue_job_row("ok_transition_test", lib_id, org_id, "https://x/ok")
        worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item = (
            session.query(ContentItem)
            .filter(ContentItem.id == job.content_item_id)
            .first()
        )
        assert job.status == "completed"
        assert job.attempts == 1
        assert job.started_at is not None
        assert job.completed_at is not None
        assert item.status == "ready"
    finally:
        session.close()


async def test_failure_records_truncated_error(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """A raising plugin marks job+item failed and truncates the message to 500."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    long_msg = "boom-" * 300  # 1500 chars

    class FailPlugin(LibraryImportPlugin):
        name = "fail_transition_test"
        description = "Always raises."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            raise RuntimeError(long_msg)

        def get_parameters(self):
            return []

    with _registered(FailPlugin):
        job_id = _queue_job_row("fail_transition_test", lib_id, org_id, "https://x/fail")
        worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item = (
            session.query(ContentItem)
            .filter(ContentItem.id == job.content_item_id)
            .first()
        )
        assert job.status == "failed"
        assert item.status == "failed"
        assert len(job.error_message) == 500
        assert job.error_message == long_msg[:500]
        assert item.error_message == long_msg[:500]
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_job_timeout_marks_failed(
    client_no_worker: AsyncClient, library: dict, monkeypatch
) -> None:
    """A job exceeding IMPORT_TASK_TIMEOUT_SECONDS is marked failed with a timeout message."""
    lib_id = library["id"]
    org_id = library["organization_id"]

    # The worker reads IMPORT_TASK_TIMEOUT_SECONDS from its own module-level
    # import, so patch the name on tasks.worker (and config for good measure).
    monkeypatch.setattr(worker, "IMPORT_TASK_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(config, "IMPORT_TASK_TIMEOUT_SECONDS", 1)

    class SleepyPlugin(LibraryImportPlugin):
        name = "timeout_test"
        description = "Sleeps past the timeout."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            time.sleep(5)
            return ImportResult(full_text="late", pages=[], images=[], metadata={}, source_ref={})

        def get_parameters(self):
            return []

    with _registered(SleepyPlugin):
        job_id = _queue_job_row("timeout_test", lib_id, org_id, "https://x/slow")
        await worker._process_job_async(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item = (
            session.query(ContentItem)
            .filter(ContentItem.id == job.content_item_id)
            .first()
        )
        assert job.status == "failed"
        assert "timed out" in job.error_message.lower()
        assert item.status == "failed"
        assert "timed out" in item.error_message.lower()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# recover_stale_jobs
# ---------------------------------------------------------------------------


async def test_recover_stale_job_resets_to_pending(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """A processing job below the attempt cap is reset to pending on recovery."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    job_id = _queue_job_row("simple_import", lib_id, org_id, "https://x/stale")

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        job.status = "processing"
        job.attempts = worker._MAX_ATTEMPTS - 1
        session.commit()
    finally:
        session.close()

    worker.recover_stale_jobs()

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "pending"
    finally:
        session.close()


async def test_recover_stale_job_exceeding_attempts_fails(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """A processing job at/over the attempt cap is marked failed (item too)."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    job_id = _queue_job_row("simple_import", lib_id, org_id, "https://x/dead")

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item_id = job.content_item_id
        job.status = "processing"
        job.attempts = worker._MAX_ATTEMPTS
        session.commit()
    finally:
        session.close()

    worker.recover_stale_jobs()

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item = session.query(ContentItem).filter(ContentItem.id == item_id).first()
        assert job.status == "failed"
        assert "max attempts" in job.error_message.lower()
        assert item.status == "failed"
        assert "max attempts" in item.error_message.lower()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# store_api_keys / _job_api_keys
# ---------------------------------------------------------------------------


def test_store_api_keys_holds_and_pops() -> None:
    """store_api_keys puts keys in memory; the worker pops them exactly once."""
    job_id = f"job-{uuid.uuid4().hex}"
    worker.store_api_keys(job_id, {"openai_vision": "sk-mem"})
    assert worker._job_api_keys[job_id] == {"openai_vision": "sk-mem"}

    popped = worker._job_api_keys.pop(job_id, {})
    assert popped == {"openai_vision": "sk-mem"}
    assert job_id not in worker._job_api_keys


def test_store_api_keys_noop_for_empty() -> None:
    """store_api_keys with None/empty stores nothing (no memory footprint)."""
    job_id = f"job-{uuid.uuid4().hex}"
    worker.store_api_keys(job_id, None)
    assert job_id not in worker._job_api_keys
    worker.store_api_keys(job_id, {})
    assert job_id not in worker._job_api_keys


def test_process_job_sync_missing_job_is_noop() -> None:
    """Processing a non-existent job id returns cleanly without raising."""
    worker._process_job_sync(f"missing-{uuid.uuid4().hex}")


async def test_failure_with_missing_item_still_records_job(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """When a job's item row is gone, the error path still marks the job failed."""
    lib_id = library["id"]
    org_id = library["organization_id"]

    class FailPlugin(LibraryImportPlugin):
        name = "fail_no_item_test"
        description = "Raises."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            raise RuntimeError("kaboom")

        def get_parameters(self):
            return []

    with _registered(FailPlugin):
        job_id = _queue_job_row("fail_no_item_test", lib_id, org_id, "https://x/noitem")
        # Delete the content item so the error-recording branch finds no item.
        session = get_session_direct()
        try:
            job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
            item = (
                session.query(ContentItem)
                .filter(ContentItem.id == job.content_item_id)
                .first()
            )
            session.delete(item)
            session.commit()
        finally:
            session.close()
        worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "failed"
        assert job.error_message == "kaboom"
    finally:
        session.close()


async def test_plugin_not_found_fails_job(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """A job referencing an unregistered plugin fails with a clear message."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    job_id = _queue_job_row("ghost_plugin_xyz", lib_id, org_id, "https://x/ghost")

    worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "failed"
        assert "Plugin not found" in job.error_message
    finally:
        session.close()


async def test_job_with_no_source_fails(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """A job with neither source_path nor source_url fails in execute_import_job."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    job_id = _queue_job_row("simple_import", lib_id, org_id, "https://x/clearme")

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        job.source_url = None
        job.source_path = None
        session.commit()
    finally:
        session.close()

    worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "failed"
        assert "no source_path or source_url" in job.error_message
    finally:
        session.close()


async def test_execute_fails_when_item_row_missing(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """execute_import_job raises (job fails) if the item row vanished post-queue."""
    lib_id = library["id"]
    org_id = library["organization_id"]

    class OkPlugin(LibraryImportPlugin):
        name = "missing_item_ok_test"
        description = "Succeeds at plugin level."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(
                full_text="# ok", pages=[], images=[], metadata={}, source_ref={}
            )

        def get_parameters(self):
            return []

    with _registered(OkPlugin):
        job_id = _queue_job_row("missing_item_ok_test", lib_id, org_id, "https://x/gone")
        session = get_session_direct()
        try:
            job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
            item = (
                session.query(ContentItem)
                .filter(ContentItem.id == job.content_item_id)
                .first()
            )
            session.delete(item)
            session.commit()
        finally:
            session.close()
        worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "failed"
        assert "not found" in job.error_message.lower()
    finally:
        session.close()


async def test_write_failure_cleans_up_item_dir(
    client_no_worker: AsyncClient, library: dict, monkeypatch
) -> None:
    """If content writing fails, the partial item dir is removed and job fails."""
    import services.content_service as content_service  # noqa: PLC0415
    from config import CONTENT_DIR  # noqa: PLC0415

    lib_id = library["id"]
    org_id = library["organization_id"]

    class OkPlugin(LibraryImportPlugin):
        name = "writefail_test"
        description = "Succeeds at plugin level."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(
                full_text="# ok", pages=[], images=[], metadata={}, source_ref={}
            )

        def get_parameters(self):
            return []

    def boom(*args, **kwargs):
        # Create the item dir first so the cleanup branch has something to rmtree.
        item_id = kwargs["item_id"]
        item_dir = CONTENT_DIR / org_id / lib_id / item_id
        item_dir.mkdir(parents=True, exist_ok=True)
        raise RuntimeError("disk write exploded")

    monkeypatch.setattr(content_service, "write_structured_content", boom)

    with _registered(OkPlugin):
        job_id = _queue_job_row("writefail_test", lib_id, org_id, "https://x/wf")
        worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item_id = job.content_item_id
        assert job.status == "failed"
        assert "exploded" in job.error_message
    finally:
        session.close()
    assert not (CONTENT_DIR / org_id / lib_id / item_id).exists()


async def test_recover_stale_job_over_cap_with_missing_item(
    client_no_worker: AsyncClient, library: dict
) -> None:
    """Over-cap recovery still marks the job failed when its item row is gone."""
    lib_id = library["id"]
    org_id = library["organization_id"]
    job_id = _queue_job_row("simple_import", lib_id, org_id, "https://x/orphan")

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        item = (
            session.query(ContentItem)
            .filter(ContentItem.id == job.content_item_id)
            .first()
        )
        job.status = "processing"
        job.attempts = worker._MAX_ATTEMPTS
        session.delete(item)
        session.commit()
    finally:
        session.close()

    worker.recover_stale_jobs()

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "failed"
    finally:
        session.close()


async def test_stop_worker_without_start_is_clean() -> None:
    """stop_worker is safe to call when no executor was created."""
    if worker.is_worker_running():
        await worker.stop_worker()
    # Force the no-executor branch.
    worker._executor = None
    await worker.stop_worker()
    assert not worker.is_worker_running()


async def test_write_failure_without_item_dir(
    client_no_worker: AsyncClient, library: dict, monkeypatch
) -> None:
    """Write failure before any item dir exists still fails the job cleanly."""
    import services.content_service as content_service  # noqa: PLC0415

    lib_id = library["id"]
    org_id = library["organization_id"]

    class OkPlugin(LibraryImportPlugin):
        name = "writefail_nodir_test"
        description = "Succeeds at plugin level."
        supported_source_types = {"url"}

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(
                full_text="# ok", pages=[], images=[], metadata={}, source_ref={}
            )

        def get_parameters(self):
            return []

    def boom(*args, **kwargs):
        # Do NOT create the item dir — exercises the ``if item_dir.exists()`` False branch.
        raise RuntimeError("write failed before any dir")

    monkeypatch.setattr(content_service, "write_structured_content", boom)

    with _registered(OkPlugin):
        job_id = _queue_job_row("writefail_nodir_test", lib_id, org_id, "https://x/nodir")
        worker._process_job_sync(job_id)

    session = get_session_direct()
    try:
        job = session.query(ImportJob).filter(ImportJob.id == job_id).first()
        assert job.status == "failed"
        assert "write failed" in job.error_message
    finally:
        session.close()


def test_recover_stale_jobs_noop_when_none() -> None:
    """recover_stale_jobs is a no-op when no jobs are stuck processing.

    Marks any pre-existing processing rows so this assertion is about the
    'nothing to recover' branch, not other tests' leftovers.
    """
    # Drain any stray processing rows first so the no-op branch is exercised.
    session = get_session_direct()
    try:
        stuck = session.query(ImportJob).filter(ImportJob.status == "processing").all()
        for j in stuck:
            j.status = "completed"
            j.completed_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()
    worker.recover_stale_jobs()  # no exception, no commit
