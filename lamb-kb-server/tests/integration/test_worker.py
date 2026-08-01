"""Integration tests for tasks/worker.py.

Covers:
- Semaphore concurrency cap (MAX_CONCURRENT_INGESTIONS)
- Duplicate-dispatch dedupe via _dispatched set
- Ingestion timeout (INGESTION_TASK_TIMEOUT_SECONDS)
- Stale recovery — retry path (attempts < _MAX_ATTEMPTS → pending)
- Stale recovery — fail path (attempts >= _MAX_ATTEMPTS → failed)
- Credentials lost — job still succeeds with empty creds dict via FakeEmbedding
- Collection deleted before job runs → failed with descriptive message
- Plugin disabled after collection creation → failed with descriptive error
- Partial progress: batch commit visible even when job fails mid-way
- is_worker_running() lifecycle transitions
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

import tasks.worker as worker_module
from database.connection import get_session_direct
from database.models import Collection, IngestionJob
from plugins.base import Chunk, ChunkingRegistry, ChunkingStrategy, DocumentInput, PluginParameter
from tasks.worker import (
    _MAX_ATTEMPTS,
    is_worker_running,
    recover_stale_jobs,
    start_worker,
    stop_worker,
    store_credentials,
)
from tests._helpers import AUTH_HEADERS, poll_job

# ---------------------------------------------------------------------------
# Helper: base collection creation payload
# ---------------------------------------------------------------------------

_BASE_COLLECTION_PAYLOAD = {
    "description": "Worker test collection",
    "chunking_strategy": "simple",
    "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
    "embedding": {
        "vendor": "fake",
        "model": "fake-model",
        "api_endpoint": "",
    },
    "vector_db_backend": "chromadb",
}


def _collection_payload(**overrides: Any) -> dict:
    p = dict(_BASE_COLLECTION_PAYLOAD)
    p["organization_id"] = f"org-{uuid4().hex[:8]}"
    p["name"] = f"test-kb-{uuid4().hex[:6]}"
    p.update(overrides)
    return p


def _doc_payload(n: int = 1, *, text_prefix: str = "Content") -> dict:
    return {
        "documents": [
            {
                "source_item_id": f"item-{i}",
                "title": f"Document {i}",
                "text": f"{text_prefix} document number {i}. " * 5,
            }
            for i in range(n)
        ],
        "embedding_credentials": {"api_key": "test-key"},
    }


# ---------------------------------------------------------------------------
# Custom chunking plugins used in tests (registered inline, cleaned up)
# ---------------------------------------------------------------------------


# Test stand-ins for `simple` use the same collection payload (chunk_size,
# chunk_overlap). Declaring these params keeps them compatible with the
# unknown-key validation, even though the chunkers ignore the values.
_SIMPLE_PARAM_DECL = [
    PluginParameter(name="chunk_size", type="int"),
    PluginParameter(name="chunk_overlap", type="int"),
]


class _SleepChunker(ChunkingStrategy):
    """Sleeps before returning trivial chunks — simulates slow chunking."""

    name = "sleep_chunker"
    description = "Test-only sleeping chunker"

    _sleep_seconds: float = 0.5
    _invocation_count: int = 0

    def get_parameters(self) -> list[PluginParameter]:
        return list(_SIMPLE_PARAM_DECL)

    def chunk(self, document: DocumentInput, params: dict | None = None) -> list[Chunk]:
        _SleepChunker._invocation_count += 1
        time.sleep(_SleepChunker._sleep_seconds)
        return [Chunk(text=document.text, metadata={"source_item_id": document.source_item_id})]


class _LongSleepChunker(ChunkingStrategy):
    """Sleeps 3 seconds — used to trigger the ingestion timeout."""

    name = "long_sleep_chunker"
    description = "Test-only long sleeping chunker"

    def get_parameters(self) -> list[PluginParameter]:
        return list(_SIMPLE_PARAM_DECL)

    def chunk(self, document: DocumentInput, params: dict | None = None) -> list[Chunk]:
        time.sleep(3)
        return [Chunk(text=document.text, metadata={"source_item_id": document.source_item_id})]


class _FailOnNthChunker(ChunkingStrategy):
    """Raises on the N-th invocation across all documents in one job run."""

    name = "fail_on_nth_chunker"
    description = "Test-only chunker that fails on nth call"

    _call_count: int = 0
    _fail_at: int = 7  # default: fail on 7th call

    def get_parameters(self) -> list[PluginParameter]:
        return list(_SIMPLE_PARAM_DECL)

    def chunk(self, document: DocumentInput, params: dict | None = None) -> list[Chunk]:
        _FailOnNthChunker._call_count += 1
        if _FailOnNthChunker._call_count >= _FailOnNthChunker._fail_at:
            raise RuntimeError(f"Intentional failure on call {_FailOnNthChunker._call_count}")
        return [
            Chunk(
                text=f"chunk {_FailOnNthChunker._call_count}: {document.text[:50]}",
                metadata={"source_item_id": document.source_item_id},
            )
        ]


# ---------------------------------------------------------------------------
# Fixture: collection backed by sleep_chunker
# ---------------------------------------------------------------------------


async def _create_collection(client: AsyncClient, strategy: str, **extra: Any) -> dict:
    payload = _collection_payload(chunking_strategy=strategy, **extra)
    r = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Semaphore enforcement — at most MAX_CONCURRENT_INGESTIONS simultaneously
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.slow
async def test_semaphore_caps_concurrent_ingestions(client: AsyncClient) -> None:
    """Queue 5 sleep-y jobs; at most 2 should ever be processing simultaneously.

    MAX_CONCURRENT_INGESTIONS=2 is set by the root conftest.
    """
    _SleepChunker._invocation_count = 0
    _SleepChunker._sleep_seconds = 0.5

    ChunkingRegistry._plugins["sleep_chunker"] = _SleepChunker
    try:
        col = await _create_collection(client, "sleep_chunker")
        col_id = col["id"]

        # Queue 5 jobs
        job_ids = []
        for _ in range(5):
            r = await client.post(
                f"/collections/{col_id}/add-content",
                json=_doc_payload(1),
                headers=AUTH_HEADERS,
            )
            assert r.status_code == 202, r.text
            job_ids.append(r.json()["job_id"])

        # Poll and record max simultaneous "processing"
        max_concurrent = 0
        deadline = asyncio.get_event_loop().time() + 30  # 30s timeout

        while asyncio.get_event_loop().time() < deadline:
            db = get_session_direct()
            try:
                processing_count = (
                    db.query(IngestionJob)
                    .filter(IngestionJob.status == "processing")
                    .count()
                )
            finally:
                db.close()

            max_concurrent = max(max_concurrent, processing_count)

            # Check if all terminal
            all_done = True
            for jid in job_ids:
                r = await client.get(f"/jobs/{jid}", headers=AUTH_HEADERS)
                if r.json()["status"] not in ("completed", "failed"):
                    all_done = False
                    break
            if all_done:
                break
            await asyncio.sleep(0.1)

        assert max_concurrent <= 2, (
            f"Expected at most 2 concurrent jobs, observed {max_concurrent}"
        )

        # All jobs should complete
        for jid in job_ids:
            final = await poll_job(client, jid, timeout=30)
            assert final["status"] == "completed", final

    finally:
        ChunkingRegistry._plugins.pop("sleep_chunker", None)


# ---------------------------------------------------------------------------
# 2. Duplicate-dispatch dedupe — _dispatched set prevents re-dispatching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.slow
async def test_dispatched_set_prevents_duplicate_dispatch(client: AsyncClient) -> None:
    """A slow job in flight should be dispatched exactly once even across polls."""
    _SleepChunker._invocation_count = 0
    _SleepChunker._sleep_seconds = 1.0  # slow enough to straddle two poll cycles

    ChunkingRegistry._plugins["sleep_chunker"] = _SleepChunker
    try:
        col = await _create_collection(client, "sleep_chunker")
        col_id = col["id"]

        r = await client.post(
            f"/collections/{col_id}/add-content",
            json=_doc_payload(1),
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 202, r.text
        job_id = r.json()["job_id"]

        # Wait for the job to reach processing (it's been dispatched)
        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            r2 = await client.get(f"/jobs/{job_id}", headers=AUTH_HEADERS)
            if r2.json()["status"] in ("processing", "completed"):
                break
            await asyncio.sleep(0.1)

        # Give the poll loop a chance to run again (>2s poll interval)
        await asyncio.sleep(worker_module._POLL_INTERVAL + 0.5)

        # Wait for completion
        final = await poll_job(client, job_id, timeout=20)
        assert final["status"] == "completed", final

        # chunker should have been invoked exactly once
        assert _SleepChunker._invocation_count == 1, (
            f"Expected 1 invocation, got {_SleepChunker._invocation_count}"
        )

    finally:
        ChunkingRegistry._plugins.pop("sleep_chunker", None)


# ---------------------------------------------------------------------------
# 3. Timeout — job times out and is marked failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.slow
async def test_job_times_out_and_is_marked_failed(
    client_no_worker: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Job that sleeps longer than timeout is marked failed with 'timed out' message."""
    # Patch timeout to 1 second so the test runs quickly
    monkeypatch.setattr(worker_module, "INGESTION_TASK_TIMEOUT_SECONDS", 1)

    ChunkingRegistry._plugins["long_sleep_chunker"] = _LongSleepChunker
    try:
        await start_worker()
        try:
            col = await _create_collection(client_no_worker, "long_sleep_chunker")
            col_id = col["id"]

            r = await client_no_worker.post(
                f"/collections/{col_id}/add-content",
                json=_doc_payload(1),
                headers=AUTH_HEADERS,
            )
            assert r.status_code == 202, r.text
            job_id = r.json()["job_id"]

            # Wait up to 15s for the job to fail due to timeout
            final = await poll_job(client_no_worker, job_id, timeout=15)
            assert final["status"] == "failed", final
            assert "timed out" in (final.get("error_message") or "").lower(), final

        finally:
            await stop_worker()

    finally:
        ChunkingRegistry._plugins.pop("long_sleep_chunker", None)


# ---------------------------------------------------------------------------
# 4. Stale recovery — retry path (attempts < _MAX_ATTEMPTS → pending)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stale_jobs_retry_path() -> None:
    """A stale processing job with attempts < MAX should be reset to pending."""
    db = get_session_direct()
    job_id = uuid4().hex
    # Insert collection so the job can eventually run (not required for recovery itself)
    org_id = f"org-{uuid4().hex[:8]}"
    try:
        stale = IngestionJob(
            id=job_id,
            collection_id="some-nonexistent-collection",
            organization_id=org_id,
            documents_json="[]",
            status="processing",
            documents_total=0,
            documents_processed=0,
            chunks_created=0,
            attempts=0,  # below _MAX_ATTEMPTS
        )
        db.add(stale)
        db.commit()
    finally:
        db.close()

    recover_stale_jobs()

    db = get_session_direct()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        assert job is not None
        assert job.status == "pending", f"Expected 'pending', got '{job.status}'"
        # attempts should be unchanged (recovery doesn't increment)
        assert job.attempts == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Stale recovery — fail path (attempts >= _MAX_ATTEMPTS → failed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stale_jobs_fail_path() -> None:
    """A stale processing job with attempts >= MAX should be marked failed."""
    db = get_session_direct()
    job_id = uuid4().hex
    org_id = f"org-{uuid4().hex[:8]}"
    try:
        stale = IngestionJob(
            id=job_id,
            collection_id="some-nonexistent-collection",
            organization_id=org_id,
            documents_json="[]",
            status="processing",
            documents_total=0,
            documents_processed=0,
            chunks_created=0,
            attempts=_MAX_ATTEMPTS,  # at the threshold → should fail
        )
        db.add(stale)
        db.commit()
    finally:
        db.close()

    recover_stale_jobs()

    db = get_session_direct()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        assert job is not None
        assert job.status == "failed", f"Expected 'failed', got '{job.status}'"
        assert job.error_message is not None
        assert "max attempts" in job.error_message.lower(), job.error_message
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5b. Stale recovery — multiple stale jobs, mixed attempts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stale_jobs_mixed() -> None:
    """Multiple stale jobs: some reset, some failed, all committed in one batch."""
    org_id = f"org-{uuid4().hex[:8]}"
    ids: dict[str, str] = {}  # label → job_id

    db = get_session_direct()
    try:
        for label, attempts in [("retry", 0), ("fail", _MAX_ATTEMPTS)]:
            jid = uuid4().hex
            ids[label] = jid
            db.add(
                IngestionJob(
                    id=jid,
                    collection_id="noop",
                    organization_id=org_id,
                    documents_json="[]",
                    status="processing",
                    documents_total=0,
                    documents_processed=0,
                    chunks_created=0,
                    attempts=attempts,
                )
            )
        db.commit()
    finally:
        db.close()

    recover_stale_jobs()

    db = get_session_direct()
    try:
        retry_job = db.query(IngestionJob).filter(IngestionJob.id == ids["retry"]).first()
        fail_job = db.query(IngestionJob).filter(IngestionJob.id == ids["fail"]).first()
        assert retry_job.status == "pending"
        assert fail_job.status == "failed"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5c. Stale recovery — no stale jobs (empty case: no commit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stale_jobs_no_stale() -> None:
    """recover_stale_jobs with no processing jobs does not crash."""
    # Should complete without error
    recover_stale_jobs()


# ---------------------------------------------------------------------------
# 6. Credentials lost — job succeeds with empty credentials dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_runs_with_empty_credentials(client: AsyncClient) -> None:
    """A job with no stored credentials uses empty creds — FakeEmbedding succeeds."""
    col = await _create_collection(client, "simple")
    col_id = col["id"]

    # Manually insert a job bypassing store_credentials
    db = get_session_direct()
    job_id = uuid4().hex
    doc = {
        "source_item_id": "creds-test-item",
        "title": "Credentials test doc",
        "text": "Testing credentials handling. " * 10,
        "permalinks": {},
        "pages": [],
        "extra_metadata": {},
    }
    try:
        job = IngestionJob(
            id=job_id,
            collection_id=col_id,
            organization_id=col["organization_id"],
            documents_json=json.dumps([doc]),
            status="pending",
            documents_total=1,
            documents_processed=0,
            chunks_created=0,
            attempts=0,
        )
        db.add(job)
        db.commit()
    finally:
        db.close()

    # NOTE: we deliberately do NOT call store_credentials — credentials are lost
    # Worker should pop empty dict from store, FakeEmbedding doesn't need keys

    final = await poll_job(client, job_id, timeout=20)
    assert final["status"] == "completed", (
        f"Expected completed (FakeEmbedding needs no creds), got: {final}"
    )
    assert final["documents_processed"] >= 1
    assert final["chunks_created"] >= 1


# ---------------------------------------------------------------------------
# 7. Collection deleted before job runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.slow
async def test_collection_deleted_before_job_runs(client: AsyncClient) -> None:
    """A job whose collection is deleted before it runs should fail gracefully."""
    _SleepChunker._invocation_count = 0
    _SleepChunker._sleep_seconds = 2.0  # block worker slot

    ChunkingRegistry._plugins["sleep_chunker"] = _SleepChunker
    try:
        # Create two collections: first will be blocked, second will be deleted
        blocker_col = await _create_collection(client, "sleep_chunker")
        victim_col = await _create_collection(client, "simple")

        # Queue a slow job on the blocker to occupy the semaphore slot
        r1 = await client.post(
            f"/collections/{blocker_col['id']}/add-content",
            json=_doc_payload(1),
            headers=AUTH_HEADERS,
        )
        assert r1.status_code == 202, r1.text
        blocker_job_id = r1.json()["job_id"]

        # Wait for blocker job to be dispatched (processing state)
        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            r = await client.get(f"/jobs/{blocker_job_id}", headers=AUTH_HEADERS)
            if r.json()["status"] == "processing":
                break
            await asyncio.sleep(0.1)

        # Now queue the victim job (won't run until blocker finishes)
        r2 = await client.post(
            f"/collections/{victim_col['id']}/add-content",
            json=_doc_payload(1),
            headers=AUTH_HEADERS,
        )
        assert r2.status_code == 202, r2.text
        victim_job_id = r2.json()["job_id"]

        # Delete the victim collection
        del_r = await client.delete(
            f"/collections/{victim_col['id']}", headers=AUTH_HEADERS
        )
        assert del_r.status_code in (200, 204), del_r.text

        # Wait for the victim job to be picked up and fail
        final = await poll_job(client, victim_job_id, timeout=30)
        assert final["status"] == "failed", final
        assert "deleted" in (final.get("error_message") or "").lower(), final

        # Blocker job should eventually complete
        blocker_final = await poll_job(client, blocker_job_id, timeout=30)
        assert blocker_final["status"] == "completed", blocker_final

    finally:
        ChunkingRegistry._plugins.pop("sleep_chunker", None)


# ---------------------------------------------------------------------------
# 8. Plugin disabled after collection creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plugin_disabled_after_collection_creation(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Job fails with descriptive error if chunking plugin is removed after collection created."""
    # Create a collection using the standard "simple" strategy
    col = await _create_collection(client, "simple")
    col_id = col["id"]

    # Save the real plugin before removing it
    original_plugin = ChunkingRegistry._plugins.get("simple")
    # Remove "simple" from registry to simulate it being disabled
    ChunkingRegistry._plugins.pop("simple", None)
    try:
        r = await client.post(
            f"/collections/{col_id}/add-content",
            json=_doc_payload(1),
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 202, r.text
        job_id = r.json()["job_id"]

        final = await poll_job(client, job_id, timeout=20)
        assert final["status"] == "failed", final
        error_msg = final.get("error_message") or ""
        assert "simple" in error_msg.lower() or "not available" in error_msg.lower(), (
            f"Expected descriptive error about missing plugin, got: {error_msg}"
        )
    finally:
        # Restore the plugin
        if original_plugin is not None:
            ChunkingRegistry._plugins["simple"] = original_plugin


# ---------------------------------------------------------------------------
# 9. Partial progress — batch commit visible even when chunking fails midway
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.slow
async def test_partial_progress_committed_before_failure(client: AsyncClient) -> None:
    """8-document job fails on 6th doc. Progress from first batch (5) should be committed.

    We insert the job directly into the DB to bypass the 2KB request-size guard
    that the root conftest sets (MAX_REQUEST_SIZE_BYTES=2048).
    """
    _FailOnNthChunker._call_count = 0
    _FailOnNthChunker._fail_at = 6  # raise on the 6th document (after first batch commits)

    ChunkingRegistry._plugins["fail_on_nth_chunker"] = _FailOnNthChunker
    try:
        # Create a collection that uses fail_on_nth_chunker strategy
        col_payload = _collection_payload(chunking_strategy="fail_on_nth_chunker")
        r_col = await client.post("/collections", json=col_payload, headers=AUTH_HEADERS)
        assert r_col.status_code == 201, r_col.text
        col = r_col.json()
        col_id = col["id"]

        # Build 8 minimal docs
        docs = [
            {
                "source_item_id": f"item-{i}",
                "title": f"Doc {i}",
                "text": f"Short text for document {i}.",
                "permalinks": {},
                "pages": [],
                "extra_metadata": {},
            }
            for i in range(8)
        ]

        # Insert job directly — bypasses MAX_REQUEST_SIZE_BYTES
        db = get_session_direct()
        job_id = uuid4().hex
        try:
            job = IngestionJob(
                id=job_id,
                collection_id=col_id,
                organization_id=col["organization_id"],
                documents_json=json.dumps(docs),
                status="pending",
                documents_total=8,
                documents_processed=0,
                chunks_created=0,
                attempts=0,
            )
            db.add(job)
            db.commit()
        finally:
            db.close()

        # Store credentials (FakeEmbedding doesn't need them but worker expects to pop)
        store_credentials(job_id, {"api_key": "test-key"})

        final = await poll_job(client, job_id, timeout=30)

        # Job must fail (chunker raises on doc 6)
        assert final["status"] == "failed", final

        # Partial progress from the first batch (5 docs committed at i=4) must survive
        assert final["documents_processed"] >= 5, (
            f"Expected >= 5 processed (batch commit at 5), got {final['documents_processed']}"
        )
        assert final["chunks_created"] > 0, (
            f"Expected > 0 chunks, got {final['chunks_created']}"
        )

    finally:
        ChunkingRegistry._plugins.pop("fail_on_nth_chunker", None)


# ---------------------------------------------------------------------------
# 10. is_worker_running() lifecycle transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_worker_running_lifecycle(client_no_worker: AsyncClient) -> None:
    """is_worker_running() should reflect start/stop state correctly."""
    # Worker is not running initially (client_no_worker fixture)
    assert is_worker_running() is False

    await start_worker()
    try:
        assert is_worker_running() is True
    finally:
        await stop_worker()

    assert is_worker_running() is False


# ---------------------------------------------------------------------------
# 11. Worker poll loop handles DB error gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_loop_continues_after_db_error(
    client_no_worker: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the DB query in _poll_loop raises once, the worker keeps going."""
    original_get_db = worker_module._get_db
    call_count = 0

    def flaky_get_db():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated DB error on first call")
        return original_get_db()

    await start_worker()
    try:
        monkeypatch.setattr(worker_module, "_get_db", flaky_get_db)

        # Give the poll loop time to encounter the error and recover
        await asyncio.sleep(worker_module._POLL_INTERVAL * 2 + 0.5)

        # Worker must still be running
        assert is_worker_running() is True

    finally:
        monkeypatch.setattr(worker_module, "_get_db", original_get_db)
        await stop_worker()


# ---------------------------------------------------------------------------
# 12. _process_job_sync handles missing job_id gracefully (no-op)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_job_sync_missing_job_id() -> None:
    """_process_job_sync with a non-existent job ID logs error and returns cleanly."""
    from tasks.worker import _process_job_sync  # noqa: PLC0415

    # Should return without raising even if job doesn't exist
    _process_job_sync("nonexistent-job-id-that-does-not-exist")


# ---------------------------------------------------------------------------
# 13. _process_job_sync exception path — job status updated to failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_job_sync_records_exception_as_failed(client: AsyncClient) -> None:
    """If chunking raises an exception, job status → failed with error message."""
    col = await _create_collection(client, "simple")
    col_id = col["id"]

    # Temporarily corrupt the collection's chunking strategy name to force failure
    db = get_session_direct()
    try:
        coll = db.query(Collection).filter(Collection.id == col_id).first()
        coll.chunking_strategy = "nonexistent_strategy_xyz"
        db.commit()
    finally:
        db.close()

    r = await client.post(
        f"/collections/{col_id}/add-content",
        json=_doc_payload(1),
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    final = await poll_job(client, job_id, timeout=20)
    assert final["status"] == "failed", final
    assert final["error_message"] is not None
    assert "nonexistent_strategy_xyz" in final["error_message"] or \
           "not available" in final["error_message"], final["error_message"]


# ---------------------------------------------------------------------------
# 14. store_credentials ignores None / empty dict
# ---------------------------------------------------------------------------


def test_store_credentials_with_none_is_noop() -> None:
    """store_credentials(job_id, None) should not add anything to _job_credentials."""
    jid = uuid4().hex
    original_keys = set(worker_module._job_credentials.keys())

    store_credentials(jid, None)

    # The key should NOT have been added
    assert jid not in worker_module._job_credentials
    # No other keys added either
    assert set(worker_module._job_credentials.keys()) == original_keys


def test_store_credentials_with_empty_dict_is_noop() -> None:
    """store_credentials(job_id, {}) should not add anything to _job_credentials."""
    jid = uuid4().hex
    original_keys = set(worker_module._job_credentials.keys())

    store_credentials(jid, {})

    assert jid not in worker_module._job_credentials
    assert set(worker_module._job_credentials.keys()) == original_keys


def test_store_credentials_stores_nonempty_dict() -> None:
    """store_credentials(job_id, {...}) stores in _job_credentials."""
    jid = uuid4().hex
    creds = {"api_key": "my-key", "api_endpoint": "https://api.example.com"}
    store_credentials(jid, creds)
    try:
        assert jid in worker_module._job_credentials
        assert worker_module._job_credentials[jid] == creds
    finally:
        worker_module._job_credentials.pop(jid, None)


# ---------------------------------------------------------------------------
# 15. stop_worker when _executor is None (should not crash)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_worker_with_no_executor() -> None:
    """stop_worker() is safe to call even if _executor was never set."""
    import tasks.worker as w  # noqa: PLC0415

    original_executor = w._executor
    w._executor = None
    w._running = True

    try:
        await stop_worker()
        assert w._running is False
    finally:
        w._executor = original_executor


# ---------------------------------------------------------------------------
# 16. Error handler: inner except when db.commit() raises (lines 147-148)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_job_sync_inner_except_when_error_recording_fails() -> None:
    """If the error-recording db.commit() also raises, the inner except logs and swallows it."""
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    from tasks.worker import _process_job_sync  # noqa: PLC0415

    # Create a mock session that raises when commit() is called
    mock_session = MagicMock()
    mock_job = MagicMock()
    mock_job.collection_id = "some-collection"
    mock_job.id = "mock-job-id"

    # query().filter().first() returns mock_job on first call (job lookup),
    # then mock_collection=None on second call (collection lookup) — this causes
    # the main try to return early (collection is None, job fails with error set).
    # Actually for this test we want the exception path.
    # Let's make execute_ingestion_job raise so we enter except block.
    # Then inside the except block, db.query returns mock_job, but db.commit raises.

    call_count = {"count": 0}

    def mock_query_result(*args, **kwargs):
        """Return job on first query, None on second (collection), job on third (error handler)."""
        class FakeFilter:
            def filter(self, *a, **kw):
                return self

            def first(self):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return mock_job  # job lookup
                elif call_count["count"] == 2:
                    return None  # collection lookup → job fails with "collection missing"
                # This branch handles re-query in the except clause if it gets there
                return mock_job

        return FakeFilter()

    mock_session.query = mock_query_result

    # On commit, first call succeeds (recording collection missing), second raises
    commit_calls = {"count": 0}

    def raising_commit():
        commit_calls["count"] += 1
        # First commit is for the collection-missing error, second would be in except
        raise RuntimeError("Simulated commit failure")

    mock_session.commit = raising_commit

    with patch("tasks.worker._get_db", return_value=mock_session):
        # Should not raise — inner except swallows the error
        _process_job_sync("test-job-id-for-inner-except")

    # db.close() should still be called via finally
    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# 17. Error handler: job is None in the outer except (lines 142->150 branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_job_sync_job_none_in_error_handler() -> None:
    """When the job disappears between processing and error recording, no crash."""
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    from tasks.worker import _process_job_sync  # noqa: PLC0415

    mock_session = MagicMock()
    mock_job = MagicMock()
    mock_collection = MagicMock()
    mock_collection.chunking_strategy = "nonexistent_xyz"  # will cause failure in execute_ingestion_job
    mock_job.collection_id = "col-1"
    mock_job.id = "job-1"
    mock_job.attempts = 0
    mock_job.documents_json = "[]"

    call_count = {"count": 0}

    def mock_query_side_effect(model):
        class FakeFilter:
            def filter(self, *a, **kw):
                return self

            def first(self):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return mock_job  # job found
                elif call_count["count"] == 2:
                    return mock_collection  # collection found
                else:
                    return None  # job gone in the error handler

        return FakeFilter()

    mock_session.query = mock_query_side_effect

    with patch("tasks.worker._get_db", return_value=mock_session):
        # Should not raise even when job is None during error recording
        _process_job_sync("test-job-for-none-in-error-handler")

    mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# 18. Timeout handler: job is None after timeout (lines 171->177 branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_job_async_timeout_job_already_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When job disappears after timeout, the finally block still closes the DB."""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    from tasks.worker import _process_job_async  # noqa: PLC0415

    # Patch timeout to near-zero
    monkeypatch.setattr(worker_module, "INGESTION_TASK_TIMEOUT_SECONDS", 0.01)

    # Ensure a live executor is available
    test_executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(worker_module, "_executor", test_executor)

    # Patch _process_job_sync to sleep longer than timeout
    def slow_sync(job_id):
        time.sleep(2)

    # Patch _get_db to return a session where job query returns None
    mock_session = MagicMock()

    class FakeFilter:
        def filter(self, *a, **kw):
            return self

        def first(self):
            return None  # job gone

    mock_session.query = MagicMock(return_value=FakeFilter())

    try:
        with patch("tasks.worker._process_job_sync", slow_sync), \
             patch("tasks.worker._get_db", return_value=mock_session):
            # Should complete without raising (timeout caught, job None handled gracefully)
            await _process_job_async("phantom-job-id")

        # DB was closed via finally
        mock_session.close.assert_called_once()
    finally:
        test_executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# 19. _poll_loop dispatch exception path (lines 210-212)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_loop_dispatch_exception_removes_from_dispatched(
    client_no_worker: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If _semaphore.acquire() raises, job_id is removed from _dispatched."""
    import asyncio as _asyncio  # noqa: PLC0415

    await start_worker()
    try:
        # Replace the semaphore with one whose acquire() raises immediately
        original_semaphore = worker_module._semaphore

        class _RaisingSemaphore:
            async def acquire(self):
                raise RuntimeError("Semaphore error for testing")

            def release(self):
                pass  # pragma: no cover

        worker_module._semaphore = _RaisingSemaphore()

        # Create a collection and queue a job so the poll loop has something to dispatch
        col_payload = _collection_payload()
        r_col = await client_no_worker.post("/collections", json=col_payload, headers=AUTH_HEADERS)
        assert r_col.status_code == 201, r_col.text
        col_id = r_col.json()["id"]

        r = await client_no_worker.post(
            f"/collections/{col_id}/add-content",
            json=_doc_payload(1),
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 202, r.text
        job_id = r.json()["job_id"]

        # Give the poll loop time to try (and fail) the dispatch
        await asyncio.sleep(worker_module._POLL_INTERVAL + 1.0)

        # Restore real semaphore
        worker_module._semaphore = original_semaphore

        # The job_id should NOT be stuck in _dispatched (was removed by the except)
        assert job_id not in worker_module._dispatched, (
            f"job_id {job_id} should have been removed from _dispatched after exception"
        )

    finally:
        # Restore semaphore before stopping worker to prevent deadlock
        if not isinstance(worker_module._semaphore, _asyncio.Semaphore):
            # Restore if we still have the fake one
            worker_module._semaphore = _asyncio.Semaphore(2)
        await stop_worker()
