"""Tests for the jobs router: GET /jobs/{id}."""

import pytest
from httpx import AsyncClient

from tests.conftest import AUTH_HEADERS, _poll_job

# A minimal single-document payload for seeding a collection with one job.
_SINGLE_DOC_PAYLOAD = {
    "documents": [
        {
            "source_item_id": "item-job-test",
            "title": "Job test document",
            "text": "LAMB is an open-source platform for educators using LTI.",
        }
    ],
    "embedding_credentials": {"api_key": "test-key"},
}


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_job_requires_auth(client: AsyncClient) -> None:
    """GET /jobs/{id} without a bearer token must return 401 or 403."""
    response = await client.get("/jobs/some-id")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_job_rejects_wrong_token(client: AsyncClient) -> None:
    """GET /jobs/{id} with an invalid bearer token must return 401."""
    response = await client.get(
        "/jobs/some-id",
        headers={"Authorization": "Bearer totally-wrong"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 404 for unknown ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_job_unknown_id_returns_404(client: AsyncClient) -> None:
    """GET /jobs/{id} for a non-existent job ID must return 404."""
    response = await client.get(
        "/jobs/00000000-0000-0000-0000-000000000000",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Full field presence after queuing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_job_all_fields_present(
    client: AsyncClient, collection: dict
) -> None:
    """GET /jobs/{id} must return all fields defined in JobStatusResponse."""
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json=_SINGLE_DOC_PAYLOAD,
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    response = await client.get(f"/jobs/{job_id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()

    required_fields = {
        "id",
        "collection_id",
        "status",
        "documents_total",
        "documents_processed",
        "chunks_created",
        "attempts",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "error_message",
    }
    missing = required_fields - body.keys()
    assert not missing, f"Missing fields in job response: {missing}"

    assert body["id"] == job_id
    assert body["collection_id"] == collection["id"]
    assert body["documents_total"] == 1


# ---------------------------------------------------------------------------
# Status-transition visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_status_transitions_to_completed(
    client: AsyncClient, collection: dict
) -> None:
    """Queue a job and observe it transition through to 'completed'."""
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json=_SINGLE_DOC_PAYLOAD,
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202, r.text
    initial_body = r.json()
    assert initial_body["status"] == "pending"

    job_id = initial_body["job_id"]

    # Poll until terminal state.
    final = await _poll_job(client, job_id, timeout=20)
    assert final["status"] == "completed", final
    assert final["documents_processed"] >= 1
    assert final["chunks_created"] >= 1
    # completed_at must be set.
    assert final["completed_at"] is not None


@pytest.mark.asyncio
async def test_job_initial_status_is_pending(
    client: AsyncClient, collection: dict
) -> None:
    """Immediately after queuing the job status should be 'pending'."""
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json=_SINGLE_DOC_PAYLOAD,
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    response = await client.get(f"/jobs/{job_id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    # The job may have advanced to 'processing' or 'completed' very quickly,
    # but it must not start in an unknown state.
    assert response.json()["status"] in ("pending", "processing", "completed")


@pytest.mark.asyncio
async def test_job_collection_id_matches(
    client: AsyncClient, collection: dict
) -> None:
    """The job's collection_id field must match the collection used to create it."""
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json=_SINGLE_DOC_PAYLOAD,
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    final = await _poll_job(client, job_id, timeout=20)
    assert final["collection_id"] == collection["id"]
