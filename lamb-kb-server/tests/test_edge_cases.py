"""Edge-case and safety tests."""

import pytest
from httpx import AsyncClient

from tests.conftest import AUTH_HEADERS


@pytest.mark.asyncio
async def test_oversized_add_content_rejected(
    client: AsyncClient, collection: dict
) -> None:
    """Send a real body larger than MAX_REQUEST_SIZE_BYTES (2KB in conftest)."""
    big_text = "x" * 4096  # 4 KB — comfortably over the 2 KB cap
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {"source_item_id": "big", "title": "big", "text": big_text}
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_crash_recovery_resets_stale_processing() -> None:
    """A job left in 'processing' should be reset on recover_stale_jobs()."""
    from uuid import uuid4  # noqa: PLC0415

    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import IngestionJob  # noqa: PLC0415
    from tasks.worker import recover_stale_jobs  # noqa: PLC0415

    db = get_session_direct()
    job_id = uuid4().hex
    try:
        stale = IngestionJob(
            id=job_id,
            collection_id="nonexistent",
            organization_id="org-test",
            documents_json="[]",
            status="processing",
            documents_total=0,
            documents_processed=0,
            chunks_created=0,
            attempts=1,
        )
        db.add(stale)
        db.commit()
    finally:
        db.close()

    recover_stale_jobs()

    db = get_session_direct()
    try:
        got = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        assert got is not None
        assert got.status in ("pending", "failed")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_unicode_content(client: AsyncClient, collection: dict) -> None:
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "uni-1",
                    "title": "Unicode — 中文 русский 🌍",
                    "text": "Café español Ωμέγα 日本語 한국어.",
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_delete_vectors_unknown_collection(client: AsyncClient) -> None:
    r = await client.delete(
        "/collections/missing/content/anything",
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_query_unknown_collection(client: AsyncClient) -> None:
    r = await client.post(
        "/collections/missing/query",
        json={"query_text": "hello"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404
