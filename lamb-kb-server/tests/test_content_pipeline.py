"""End-to-end tests for the content ingestion + query pipeline over HTTP."""

import pytest
from httpx import AsyncClient

from tests.conftest import AUTH_HEADERS, _poll_job


@pytest.mark.asyncio
async def test_add_content_and_query(
    client: AsyncClient, collection: dict
) -> None:
    # Use short, single-chunk documents so the hash-based test embedding
    # produces one vector per doc. Querying with the exact text of alpha's
    # chunk guarantees alpha ranks first under cosine similarity.
    alpha_text = "LAMB is an open-source platform for educators."
    beta_text = "Completely unrelated content about gardening tomatoes."
    payload = {
        "documents": [
            {
                "source_item_id": "item-alpha",
                "title": "Alpha document",
                "text": alpha_text,
                "permalinks": {
                    "original": "/docs/org-x/lib-y/item-alpha/original/file.txt",
                    "full_markdown": "/docs/org-x/lib-y/item-alpha/content/full.md",
                    "pages": [],
                },
            },
            {
                "source_item_id": "item-beta",
                "title": "Beta document",
                "text": beta_text,
            },
        ],
        "embedding_credentials": {"api_key": "test-key"},
    }
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["documents_total"] == 2

    # Poll until complete.
    final = await _poll_job(client, body["job_id"], timeout=15)
    assert final["status"] == "completed", final
    assert final["documents_processed"] == 2
    assert final["chunks_created"] >= 2

    # Query with the exact alpha text → identical embedding → score ≈ 1.0.
    q = await client.post(
        f"/collections/{collection['id']}/query",
        json={
            "query_text": alpha_text,
            "top_k": 3,
            "embedding_credentials": {"api_key": "test-key"},
        },
        headers=AUTH_HEADERS,
    )
    assert q.status_code == 200
    results = q.json()["results"]
    assert results
    # First hit should be alpha (most similar under the fake embedding).
    assert results[0]["metadata"]["source_item_id"] == "item-alpha"
    # Permalinks present in metadata.
    assert results[0]["metadata"]["permalink_original"].endswith("file.txt")

    # Collection counters should reflect the ingest.
    c = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert c.status_code == 200
    assert c.json()["document_count"] == 2
    assert c.json()["chunk_count"] >= 2


@pytest.mark.asyncio
async def test_delete_vectors_by_source(
    client: AsyncClient, collection: dict
) -> None:
    # Seed two documents.
    await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {"source_item_id": "keep", "title": "Keep", "text": "alpha"},
                {"source_item_id": "drop", "title": "Drop", "text": "beta"},
            ],
            "embedding_credentials": {"api_key": ""},
        },
        headers=AUTH_HEADERS,
    )
    # Wait for any one job to complete.
    # For simplicity, poll one job at a time via collection.chunk_count.
    import asyncio  # noqa: PLC0415

    for _ in range(40):
        c = await client.get(
            f"/collections/{collection['id']}", headers=AUTH_HEADERS
        )
        if c.json()["chunk_count"] >= 2:
            break
        await asyncio.sleep(0.2)

    r = await client.delete(
        f"/collections/{collection['id']}/content/drop",
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source_item_id"] == "drop"
    assert body["deleted_count"] >= 1

    # Remaining chunks only from 'keep'.
    q = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "anything", "top_k": 10},
        headers=AUTH_HEADERS,
    )
    assert q.status_code == 200
    for res in q.json()["results"]:
        assert res["metadata"]["source_item_id"] == "keep"


@pytest.mark.asyncio
async def test_add_content_unknown_collection(client: AsyncClient) -> None:
    r = await client.post(
        "/collections/not-a-collection/add-content",
        json={
            "documents": [
                {"source_item_id": "x", "title": "X", "text": "foo"}
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_query_empty_collection_returns_empty(
    client: AsyncClient, collection: dict
) -> None:
    r = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "anything"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["results"] == []


@pytest.mark.asyncio
async def test_add_content_empty_documents_rejected(
    client: AsyncClient, collection: dict
) -> None:
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={"documents": []},
        headers=AUTH_HEADERS,
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_job_status_not_found(client: AsyncClient) -> None:
    r = await client.get("/jobs/nonexistent", headers=AUTH_HEADERS)
    assert r.status_code == 404
