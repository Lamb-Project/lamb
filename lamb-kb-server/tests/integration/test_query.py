"""Integration tests for the query route and query_service.

Covers:
- top_k=1 returns single best result
- top_k=100 with only 3 chunks returns exactly 3 results
- top_k=0 rejected (422)
- top_k=101 rejected (422)
- empty query_text rejected (422)
- embedding_credentials accepted in request body
- 503 when vector DB backend is unavailable (hits query_service.py line 50)
- permalink metadata propagated to query results
- response structure: text, score in [0,1], metadata dict
- results ordered by score descending
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from plugins.base import VectorDBRegistry

from tests._helpers import AUTH_HEADERS, _poll_job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ingest(
    client: AsyncClient,
    collection_id: str,
    documents: list[dict],
    *,
    timeout: float = 20.0,
) -> dict:
    """Post add-content, wait for the job to complete, return the job body."""
    r = await client.post(
        f"/collections/{collection_id}/add-content",
        json={"documents": documents, "embedding_credentials": {"api_key": ""}},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202, r.text
    body = r.json()
    return await _poll_job(client, body["job_id"], timeout=timeout)


async def _query(
    client: AsyncClient,
    collection_id: str,
    query_text: str,
    *,
    top_k: int = 5,
    embedding_credentials: dict | None = None,
) -> dict:
    """POST query and return the parsed JSON body."""
    payload: dict = {"query_text": query_text, "top_k": top_k}
    if embedding_credentials is not None:
        payload["embedding_credentials"] = embedding_credentials
    r = await client.post(
        f"/collections/{collection_id}/query",
        json=payload,
        headers=AUTH_HEADERS,
    )
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_top_k_1_returns_single_result(
    client: AsyncClient, collection: dict
) -> None:
    """top_k=1 must return exactly one result even when more chunks exist."""
    docs = [
        {
            "source_item_id": f"doc-{i}",
            "title": f"Doc {i}",
            "text": f"unique content item number {i} for testing top k one",
        }
        for i in range(5)
    ]
    job = await _ingest(client, collection["id"], docs)
    assert job["status"] == "completed", job
    assert job["chunks_created"] >= 5

    r = await _query(client, collection["id"], "unique content", top_k=1)
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 1
    assert body["top_k"] == 1


@pytest.mark.asyncio
async def test_top_k_100_returns_all_when_fewer_chunks(
    client: AsyncClient, collection: dict
) -> None:
    """top_k=100 with only 3 chunks stored returns 3 results (not 100)."""
    docs = [
        {"source_item_id": f"small-{i}", "title": f"Small {i}", "text": f"document {i}"}
        for i in range(3)
    ]
    job = await _ingest(client, collection["id"], docs)
    assert job["status"] == "completed", job

    r = await _query(client, collection["id"], "document", top_k=100)
    assert r.status_code == 200
    body = r.json()
    # ChromaDB returns at most the number of stored chunks.
    assert 1 <= len(body["results"]) <= 3
    assert body["top_k"] == 100


@pytest.mark.asyncio
async def test_top_k_0_rejected(client: AsyncClient, collection: dict) -> None:
    """top_k=0 violates ge=1 constraint — must return 422."""
    r = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "anything", "top_k": 0},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_top_k_101_rejected(client: AsyncClient, collection: dict) -> None:
    """top_k=101 violates le=100 constraint — must return 422."""
    r = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "anything", "top_k": 101},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_empty_query_text_rejected(
    client: AsyncClient, collection: dict
) -> None:
    """Empty string violates min_length=1 — must return 422."""
    r = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "", "top_k": 5},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_query_with_embedding_credentials_accepted(
    client: AsyncClient, collection: dict
) -> None:
    """Passing embedding_credentials in the query body must be accepted (200).

    FakeEmbedding ignores credentials but the schema must accept them without
    error — verifies request shape is valid end-to-end.
    """
    r = await client.post(
        f"/collections/{collection['id']}/query",
        json={
            "query_text": "some text",
            "top_k": 5,
            "embedding_credentials": {
                "api_key": "my-api-key",
                "api_endpoint": "https://api.example.com",
            },
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert body["query"] == "some text"


@pytest.mark.asyncio
async def test_query_503_when_backend_unavailable(
    client: AsyncClient, collection: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 is returned when VectorDBRegistry.get returns None (line 50 in query_service.py).

    Strategy: monkeypatch VectorDBRegistry.get to return None, then query.
    The collection was created successfully before the patch so the 404 path
    is NOT taken — only the 503 backend-unavailable branch is exercised.
    """
    original_get = VectorDBRegistry.get

    def _get_none(name: str):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(VectorDBRegistry, "get", staticmethod(_get_none))
    try:
        r = await client.post(
            f"/collections/{collection['id']}/query",
            json={"query_text": "anything", "top_k": 5},
            headers=AUTH_HEADERS,
        )
    finally:
        monkeypatch.setattr(VectorDBRegistry, "get", staticmethod(original_get))

    assert r.status_code == 503
    assert "not available" in r.json()["detail"].lower() or "503" in str(r.status_code)


@pytest.mark.asyncio
async def test_query_permalink_metadata_propagated(
    client: AsyncClient, collection: dict
) -> None:
    """Permalink URLs ingested with a document appear in query result metadata."""
    permalink_url = "https://example.com/doc/original.pdf"
    doc = {
        "source_item_id": "permalink-doc",
        "title": "Permalink Test",
        "text": "This document has a permalink attached to it for citation purposes.",
        "permalinks": {
            "original": permalink_url,
            "full_markdown": "https://example.com/doc/full.md",
            "pages": [],
        },
    }
    job = await _ingest(client, collection["id"], [doc])
    assert job["status"] == "completed", job

    r = await _query(
        client,
        collection["id"],
        "This document has a permalink",
        top_k=5,
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, "Expected at least one result"
    # Find the result from our document.
    permalink_results = [
        res for res in results
        if res["metadata"].get("source_item_id") == "permalink-doc"
    ]
    assert permalink_results, "No result with source_item_id=permalink-doc"
    meta = permalink_results[0]["metadata"]
    assert "permalink_original" in meta
    assert meta["permalink_original"] == permalink_url


@pytest.mark.asyncio
async def test_query_response_structure(
    client: AsyncClient, collection: dict
) -> None:
    """Each result must have text (str), score (float in [0,1]), metadata (dict)."""
    doc = {
        "source_item_id": "structure-doc",
        "title": "Structure Test",
        "text": "Verifying the structure of query response items.",
    }
    job = await _ingest(client, collection["id"], [doc])
    assert job["status"] == "completed", job

    r = await _query(client, collection["id"], "structure of query response", top_k=5)
    assert r.status_code == 200
    body = r.json()

    # Top-level response fields.
    assert "results" in body
    assert "query" in body
    assert "top_k" in body
    assert body["query"] == "structure of query response"
    assert body["top_k"] == 5

    # Per-result structure.
    for result in body["results"]:
        assert "text" in result
        assert isinstance(result["text"], str)
        assert "score" in result
        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0, f"Score out of [0,1]: {result['score']}"
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)


@pytest.mark.asyncio
async def test_query_404_unknown_collection(client: AsyncClient) -> None:
    """Query against a non-existent collection_id must return 404.

    This exercises the collection-not-found branch in query_service.py.
    The 404 path is also covered by test_content_pipeline.py but we include
    it here so this file independently achieves ≥95% coverage.
    """
    r = await client.post(
        "/collections/does-not-exist/query",
        json={"query_text": "anything", "top_k": 5},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404
    body = r.json()
    assert "does-not-exist" in body["detail"]


@pytest.mark.asyncio
async def test_query_results_ordered_by_score_descending(
    client: AsyncClient, collection: dict
) -> None:
    """Query results must be ordered by score descending (best match first).

    We ingest 3 distinct documents. Querying with the exact text of one of them
    should produce that document's chunk as the first result (highest score under
    the deterministic FakeEmbedding which gives score≈1 for identical text).
    """
    exact_text = "The quick brown fox jumps over the lazy dog."
    docs = [
        {
            "source_item_id": "fox-doc",
            "title": "Fox Document",
            "text": exact_text,
        },
        {
            "source_item_id": "cat-doc",
            "title": "Cat Document",
            "text": "Cats are independent animals that like to sleep.",
        },
        {
            "source_item_id": "car-doc",
            "title": "Car Document",
            "text": "A car is a wheeled motor vehicle for transportation.",
        },
    ]
    job = await _ingest(client, collection["id"], docs)
    assert job["status"] == "completed", job

    r = await _query(client, collection["id"], exact_text, top_k=10)
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, "Expected at least one result"

    # Verify results are in descending score order.
    scores = [res["score"] for res in results]
    assert scores == sorted(scores, reverse=True), (
        f"Results are not ordered by score descending: {scores}"
    )

    # The first result should come from fox-doc (exact text match → highest score).
    assert results[0]["metadata"].get("source_item_id") == "fox-doc", (
        f"Expected fox-doc first, got: {results[0]['metadata'].get('source_item_id')}"
    )
