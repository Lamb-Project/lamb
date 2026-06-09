"""Edge-case and safety tests."""

import urllib.parse
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests._helpers import _poll_job
from tests.conftest import AUTH_HEADERS

# ---------------------------------------------------------------------------
# Original 5 tests (unchanged)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# New edge-case tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extremely_long_unicode_text(
    client: AsyncClient, collection: dict
) -> None:
    """Ingest a document with mixed-script text (Chinese, Arabic, Cyrillic, emoji).

    The text is kept under MAX_REQUEST_SIZE_BYTES (2 KB in the test
    environment). The job should complete and querying should return valid
    metadata with the correct source_item_id.
    """
    # Build a mixed-script string — keep well under the 2 KB request cap
    chinese = "中文内容测试 "
    arabic = "محتوى عربي "
    cyrillic = "русский текст "
    emoji = "🌍🚀💡🎉 "
    unit = chinese + arabic + cyrillic + emoji
    # Repeat enough to get a substantial body but stay well under 2 KB limit
    # (JSON overhead + other fields; raw text ~400 chars is safe)
    long_text = (unit * 6).strip()

    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "long-unicode-1",
                    "title": "Long Unicode Test",
                    "text": long_text,
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"

    # Query to verify metadata comes back intact
    qr = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "中文内容", "top_k": 1},
        headers=AUTH_HEADERS,
    )
    assert qr.status_code == 200
    results = qr.json()["results"]
    assert len(results) >= 1
    assert results[0]["metadata"]["source_item_id"] == "long-unicode-1"


@pytest.mark.asyncio
async def test_zero_length_text_document(
    client: AsyncClient, collection: dict
) -> None:
    """Ingest a document with an empty string text.

    The simple chunking strategy will produce 0 chunks; the job should
    complete and collection.chunk_count should not be incremented.
    """
    # Get chunk_count before ingestion
    before = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert before.status_code == 200
    chunk_count_before = before.json()["chunk_count"]

    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "empty-text-1",
                    "title": "Empty Document",
                    "text": "",
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"
    # Empty text produces no chunks
    assert job["chunks_created"] == 0

    # Verify collection chunk count was not incremented
    after = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert after.status_code == 200
    assert after.json()["chunk_count"] == chunk_count_before


@pytest.mark.asyncio
async def test_permalink_with_special_url_characters(
    client: AsyncClient, collection: dict
) -> None:
    """Permalink containing query params, percent-encoding, and unicode is preserved."""
    special_permalink = (
        "https://example.com/path?query=hello%20world&special=日本語"
    )

    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "permalink-special-1",
                    "title": "Special Permalink Test",
                    "text": (
                        "This document has a special permalink URL that must be "
                        "preserved verbatim."
                    ),
                    "permalinks": {"original": special_permalink},
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"

    qr = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "special permalink URL", "top_k": 1},
        headers=AUTH_HEADERS,
    )
    assert qr.status_code == 200
    results = qr.json()["results"]
    assert len(results) >= 1
    assert results[0]["metadata"]["permalink_original"] == special_permalink


@pytest.mark.asyncio
async def test_extra_metadata_primitive_values(
    client: AsyncClient, collection: dict
) -> None:
    """extra_metadata with str, int, bool, and float values is stored and retrieved.

    ChromaDB accepts str/int/float/bool primitives but rejects None.
    This test verifies the str/int/bool/float path works end-to-end.
    """
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "extra-meta-primitives-1",
                    "title": "Primitive Metadata Test",
                    "text": "Testing extra metadata with various primitive types.",
                    "extra_metadata": {
                        "foo": "bar",
                        "n": 42,
                        "b": True,
                        "f": 3.14,
                    },
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"

    qr = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "primitive types", "top_k": 1},
        headers=AUTH_HEADERS,
    )
    assert qr.status_code == 200
    results = qr.json()["results"]
    assert len(results) >= 1
    meta = results[0]["metadata"]
    assert meta["foo"] == "bar"
    assert meta["n"] == 42
    assert meta["b"] is True
    assert abs(meta["f"] - 3.14) < 0.001


@pytest.mark.asyncio
async def test_extra_metadata_none_value_rejected_at_schema(
    client: AsyncClient, collection: dict
) -> None:
    """extra_metadata containing a None value is rejected at the request boundary.

    The schema now declares dict[str, str | int | float | bool] and validates
    that no value is None, so the request should be rejected with a 422 before
    a job is ever created.
    """
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "extra-meta-none-1",
                    "title": "None Metadata Test",
                    "text": "Testing that None in extra_metadata is rejected by ChromaDB.",
                    "extra_metadata": {"none_val": None},
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any("none_val" in str(e) for e in detail)


@pytest.mark.asyncio
async def test_extra_metadata_nested_dict_rejected_at_schema(
    client: AsyncClient, collection: dict
) -> None:
    """extra_metadata with a nested dict is rejected at the request boundary.

    The schema now validates that all values are str/int/float/bool primitives,
    so a nested dict is caught immediately and returned as a 422 before a job
    is ever created.
    """
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "extra-meta-nested-1",
                    "title": "Nested Metadata Test",
                    "text": "Testing extra metadata with a nested dictionary value.",
                    "extra_metadata": {"nested": {"key": "value"}},
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any("nested" in str(e) for e in detail)


@pytest.mark.asyncio
async def test_whitespace_only_text(
    client: AsyncClient, collection: dict
) -> None:
    """Whitespace-only document text produces 0 chunks; job completes."""
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "whitespace-only-1",
                    "title": "Whitespace Document",
                    "text": "   \n\n\t  ",
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"
    assert job["chunks_created"] == 0


@pytest.mark.asyncio
async def test_very_long_collection_name(
    client: AsyncClient, org_id: str
) -> None:
    """A 200-character collection name should be accepted (no max_length in schema)."""
    long_name = "a" * 200
    r = await client.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": long_name,
            "chunking_strategy": "simple",
            "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
            "embedding": {"vendor": "fake", "model": "fake-model", "api_endpoint": ""},
            "vector_db_backend": "chromadb",
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 201
    assert r.json()["name"] == long_name

    # Cleanup
    coll_id = r.json()["id"]
    await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)


@pytest.mark.asyncio
async def test_collection_name_with_weird_characters(
    client: AsyncClient, org_id: str
) -> None:
    """Collection names with emoji, slashes, and unicode are stored verbatim.

    The KB server stores collection names in SQLite without sanitization.
    Only the backend_collection_id (prefixed kb_<uuid>) needs to satisfy
    ChromaDB naming rules — the human-readable name is unrestricted.
    """
    weird_name = "test 🚀 /slashes/ 日本語 — weird & chars"
    r = await client.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": weird_name,
            "chunking_strategy": "simple",
            "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
            "embedding": {"vendor": "fake", "model": "fake-model", "api_endpoint": ""},
            "vector_db_backend": "chromadb",
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 201
    assert r.json()["name"] == weird_name

    # Cleanup
    coll_id = r.json()["id"]
    await client.delete(f"/collections/{coll_id}", headers=AUTH_HEADERS)


@pytest.mark.asyncio
async def test_org_id_with_weird_characters(client: AsyncClient) -> None:
    """org_id with slashes, unicode, and special chars is rejected.

    The org_id validation now rejects characters that could enable path
    traversal or other security issues, returning 422.
    """
    weird_org = "org/weird 🌍 ñ chars&test"
    r = await client.post(
        "/collections",
        json={
            "organization_id": weird_org,
            "name": f"test-{uuid4().hex[:6]}",
            "chunking_strategy": "simple",
            "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
            "embedding": {"vendor": "fake", "model": "fake-model", "api_endpoint": ""},
            "vector_db_backend": "chromadb",
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_unicode_source_item_id_preserved_and_deletable(
    client: AsyncClient, collection: dict
) -> None:
    """source_item_id with unicode characters is stored and retrievable.

    After ingestion, querying returns chunks with the original unicode id,
    and DELETE by that id removes them cleanly.
    """
    unicode_id = "doc-日本語-id-🔑"

    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": unicode_id,
                    "title": "Unicode ID Document",
                    "text": "This document has a unicode source item identifier.",
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"

    # Query and verify the source_item_id is preserved
    qr = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "unicode source item identifier", "top_k": 1},
        headers=AUTH_HEADERS,
    )
    assert qr.status_code == 200
    results = qr.json()["results"]
    assert len(results) >= 1
    assert results[0]["metadata"]["source_item_id"] == unicode_id

    # Delete by the unicode source_item_id (URL-encode it for the path)
    encoded_id = urllib.parse.quote(unicode_id, safe="")
    dr = await client.delete(
        f"/collections/{collection['id']}/content/{encoded_id}",
        headers=AUTH_HEADERS,
    )
    assert dr.status_code == 200
    assert dr.json()["deleted_count"] >= 1


@pytest.mark.asyncio
async def test_title_with_newlines_and_tabs(
    client: AsyncClient, collection: dict
) -> None:
    """Document title containing newlines and tabs is propagated to chunk metadata."""
    weird_title = "Title with\nnewline\tand tab"

    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "weird-title-1",
                    "title": weird_title,
                    "text": (
                        "Testing metadata propagation for titles with whitespace "
                        "control chars."
                    ),
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    job = await _poll_job(client, job_id)
    assert job["status"] == "completed", f"Job failed: {job}"

    qr = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "metadata propagation titles", "top_k": 1},
        headers=AUTH_HEADERS,
    )
    assert qr.status_code == 200
    results = qr.json()["results"]
    assert len(results) >= 1
    assert results[0]["metadata"]["source_title"] == weird_title


@pytest.mark.asyncio
async def test_stale_job_at_max_attempts_minus_one_reset_to_pending() -> None:
    """A stale job with attempts == MAX_ATTEMPTS - 1 is reset to pending.

    With one remaining attempt, the job should be retried, not failed.
    Default KB_MAX_JOB_ATTEMPTS = 3, so attempts=2 is one below the limit.
    """
    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import IngestionJob  # noqa: PLC0415
    from tasks.worker import _MAX_ATTEMPTS, recover_stale_jobs  # noqa: PLC0415

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
            attempts=_MAX_ATTEMPTS - 1,  # one attempt still remaining
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
        assert got.status == "pending", (
            f"Expected 'pending' for attempts={_MAX_ATTEMPTS - 1} "
            f"(below max={_MAX_ATTEMPTS}), got '{got.status}'"
        )
    finally:
        db.close()


@pytest.mark.asyncio
async def test_stale_job_at_max_attempts_marked_failed() -> None:
    """A stale job with attempts == MAX_ATTEMPTS is marked failed (no more retries)."""
    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import IngestionJob  # noqa: PLC0415
    from tasks.worker import _MAX_ATTEMPTS, recover_stale_jobs  # noqa: PLC0415

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
            attempts=_MAX_ATTEMPTS,  # at the limit — must fail
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
        assert got.status == "failed", (
            f"Expected 'failed' for attempts={_MAX_ATTEMPTS} "
            f"(at max={_MAX_ATTEMPTS}), got '{got.status}'"
        )
        assert got.error_message is not None
        assert (
            "max attempts" in got.error_message.lower()
            or "exceeded" in got.error_message.lower()
        )
    finally:
        db.close()
