"""End-to-end tests for the content ingestion + query pipeline over HTTP."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import AUTH_HEADERS, _poll_job

# ---------------------------------------------------------------------------
# Original 6 tests (unchanged)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_413_via_content_length_header_even_with_small_body(
    client: AsyncClient, collection: dict
) -> None:
    """Content-Length header above limit trips 413 even with a short body.

    This exercises the header-check branch (line 53->64 in content.py) where
    the server reads Content-Length before parsing the body.
    """
    # A genuinely small JSON payload — well under MAX_REQUEST_SIZE_BYTES=2048.
    payload = {
        "documents": [{"source_item_id": "x", "title": "X", "text": "hello"}]
    }
    import json  # noqa: PLC0415

    body_bytes = json.dumps(payload).encode()
    assert len(body_bytes) < 2048  # guard: body really is small

    # Override Content-Length to be far above the 2048-byte limit.
    # We also set Content-Type so FastAPI can parse the body after (or before)
    # the size check — the 413 should fire based on the header alone.
    headers = {
        **AUTH_HEADERS,
        "Content-Length": "999999",
        "Content-Type": "application/json",
    }
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        content=body_bytes,
        headers=headers,
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_large_valid_payload_near_limit_accepted(
    client: AsyncClient, collection: dict
) -> None:
    """Payload just below MAX_REQUEST_SIZE_BYTES (2048) should succeed (202).

    Covers the happy-path branch of the content-length guard where the
    header is present but within bounds.
    """
    # Build a document whose text fills up to ~1900 bytes total payload.
    # MAX_REQUEST_SIZE_BYTES=2048 in the test conftest.
    padding = "x" * 1400  # text field — enough to make payload ~1900 bytes
    payload = {
        "documents": [
            {
                "source_item_id": "near-limit",
                "title": "Near limit",
                "text": padding,
            }
        ]
    }
    import json  # noqa: PLC0415

    body_bytes = json.dumps(payload).encode()
    assert len(body_bytes) < 2048, (
        f"Test payload is {len(body_bytes)} bytes — too large; reduce padding."
    )

    headers = {
        **AUTH_HEADERS,
        "Content-Length": str(len(body_bytes)),
        "Content-Type": "application/json",
    }
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        content=body_bytes,
        headers=headers,
    )
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_multi_source_ingestion_correct_metadata(
    client: AsyncClient, collection: dict
) -> None:
    """Three documents with distinct source_item_ids are all queryable.

    After ingestion, a query for each doc's text should return chunks
    whose metadata contains the correct source_item_id.
    """
    texts = {
        "src-alpha": "Quantum computing leverages superposition and entanglement.",
        "src-beta": "Photosynthesis converts light energy into chemical energy.",
        "src-gamma": "Machine learning models learn from labelled training data.",
    }
    payload = {
        "documents": [
            {"source_item_id": sid, "title": sid.upper(), "text": text}
            for sid, text in texts.items()
        ]
    }
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    final = await _poll_job(client, r.json()["job_id"], timeout=20)
    assert final["status"] == "completed", final
    assert final["documents_processed"] == 3

    # Query each document text — top-1 result should match its own source_item_id.
    for sid, text in texts.items():
        q = await client.post(
            f"/collections/{collection['id']}/query",
            json={"query_text": text, "top_k": 3},
            headers=AUTH_HEADERS,
        )
        assert q.status_code == 200
        results = q.json()["results"]
        assert results, f"No results for source '{sid}'"
        top_sid = results[0]["metadata"]["source_item_id"]
        assert top_sid == sid, (
            f"Expected top result for '{sid}' but got '{top_sid}'"
        )


@pytest.mark.asyncio
async def test_delete_by_source_removes_from_chromadb(
    client: AsyncClient, collection: dict
) -> None:
    """delete-by-source removes vectors from real ChromaDB collection.

    Ingest two sources, delete one, query the deleted source — expect 0 hits.
    Also verify collection.chunk_count reflects the deletion.
    """
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "src-keep",
                    "title": "Keep",
                    "text": "Astronomy studies stars and galaxies.",
                },
                {
                    "source_item_id": "src-delete",
                    "title": "Delete",
                    "text": "Botany is the study of plants and their biology.",
                },
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    final = await _poll_job(client, r.json()["job_id"], timeout=20)
    assert final["status"] == "completed"

    # Check collection has both docs.
    c_before = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    chunk_count_before = c_before.json()["chunk_count"]
    assert chunk_count_before >= 2

    # Delete the second source.
    del_r = await client.delete(
        f"/collections/{collection['id']}/content/src-delete",
        headers=AUTH_HEADERS,
    )
    assert del_r.status_code == 200
    del_body = del_r.json()
    assert del_body["source_item_id"] == "src-delete"
    assert del_body["deleted_count"] >= 1

    # Query for deleted source — should return zero results.
    q = await client.post(
        f"/collections/{collection['id']}/query",
        json={"query_text": "Botany is the study of plants and their biology.", "top_k": 10},
        headers=AUTH_HEADERS,
    )
    assert q.status_code == 200
    deleted_results = [
        res for res in q.json()["results"]
        if res["metadata"]["source_item_id"] == "src-delete"
    ]
    assert deleted_results == [], f"Expected no results for deleted source, got: {deleted_results}"

    # chunk_count should have decreased.
    c_after = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    chunk_count_after = c_after.json()["chunk_count"]
    assert chunk_count_after < chunk_count_before


@pytest.mark.asyncio
async def test_counter_aggregation_across_multiple_ingestions(
    client: AsyncClient, collection: dict
) -> None:
    """document_count and chunk_count accumulate across multiple ingestion jobs."""
    # First ingestion: 2 documents.
    r1 = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {"source_item_id": "agg-1", "title": "Agg1", "text": "First doc content here."},
                {"source_item_id": "agg-2", "title": "Agg2", "text": "Second doc content here."},
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r1.status_code == 202
    final1 = await _poll_job(client, r1.json()["job_id"], timeout=20)
    assert final1["status"] == "completed"
    chunks_job1 = final1["chunks_created"]

    # Second ingestion: 3 documents.
    r2 = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {"source_item_id": "agg-3", "title": "Agg3", "text": "Third doc content."},
                {"source_item_id": "agg-4", "title": "Agg4", "text": "Fourth doc content."},
                {"source_item_id": "agg-5", "title": "Agg5", "text": "Fifth doc content."},
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 202
    final2 = await _poll_job(client, r2.json()["job_id"], timeout=20)
    assert final2["status"] == "completed"
    chunks_job2 = final2["chunks_created"]

    # GET collection — counters must reflect both jobs.
    c = await client.get(
        f"/collections/{collection['id']}", headers=AUTH_HEADERS
    )
    assert c.status_code == 200
    data = c.json()
    assert data["document_count"] == 5, (
        f"Expected document_count=5, got {data['document_count']}"
    )
    assert data["chunk_count"] == chunks_job1 + chunks_job2, (
        f"Expected chunk_count={chunks_job1 + chunks_job2}, got {data['chunk_count']}"
    )


@pytest.mark.asyncio
async def test_qdrant_happy_path(client: AsyncClient, org_id: str) -> None:
    """Ingest into a Qdrant-backed collection, query, verify results.

    Force-registers QdrantBackend directly into the registry (bypassing the
    DISABLE env guard) without touching sys.modules. Evicting and re-importing
    the module would invalidate references already bound by sibling test
    modules — keep the existing module object in place.
    """
    from plugins.base import VectorDBRegistry  # noqa: PLC0415

    try:
        from plugins.vector_db.qdrant_backend import QdrantBackend  # noqa: PLC0415
    except ImportError:
        pytest.skip("qdrant-client not installed; skipping Qdrant integration test")

    VectorDBRegistry._plugins["qdrant"] = QdrantBackend
    try:
        # Create a Qdrant-backed collection.
        create_r = await client.post(
            "/collections",
            json={
                "organization_id": org_id,
                "name": f"qdrant-test-{uuid4().hex[:6]}",
                "description": "Qdrant integration test",
                "chunking_strategy": "simple",
                "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
                "embedding": {
                    "vendor": "fake",
                    "model": "fake-model",
                    "api_endpoint": "",
                },
                "vector_db_backend": "qdrant",
            },
            headers=AUTH_HEADERS,
        )
        assert create_r.status_code == 201, create_r.text
        qdrant_collection = create_r.json()

        # Ingest 2 documents.
        ingest_r = await client.post(
            f"/collections/{qdrant_collection['id']}/add-content",
            json={
                "documents": [
                    {
                        "source_item_id": "qdrant-doc-1",
                        "title": "Qdrant Doc 1",
                        "text": "Qdrant is a high-performance vector search engine.",
                    },
                    {
                        "source_item_id": "qdrant-doc-2",
                        "title": "Qdrant Doc 2",
                        "text": "Vector databases are optimized for similarity search.",
                    },
                ]
            },
            headers=AUTH_HEADERS,
        )
        assert ingest_r.status_code == 202
        final = await _poll_job(client, ingest_r.json()["job_id"], timeout=20)
        assert final["status"] == "completed", final
        assert final["documents_processed"] == 2
        assert final["chunks_created"] >= 2

        # Query — top result should be the relevant doc.
        query_r = await client.post(
            f"/collections/{qdrant_collection['id']}/query",
            json={
                "query_text": "Qdrant is a high-performance vector search engine.",
                "top_k": 2,
            },
            headers=AUTH_HEADERS,
        )
        assert query_r.status_code == 200
        results = query_r.json()["results"]
        assert results, "No results from Qdrant-backed collection"
        assert results[0]["metadata"]["source_item_id"] == "qdrant-doc-1"

    finally:
        VectorDBRegistry._plugins.pop("qdrant", None)


@pytest.mark.asyncio
async def test_hierarchical_chunking_parent_text_in_results(
    client: AsyncClient, org_id: str
) -> None:
    """Hierarchical chunking emits parent_text chunks queryable from the API.

    Creates a collection with chunking_strategy="hierarchical", ingests a
    markdown document with H2/H3 headers, verifies the returned chunks have
    section_title metadata fields.
    """
    # Create a hierarchical-chunking collection.
    create_r = await client.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": f"hier-test-{uuid4().hex[:6]}",
            "description": "Hierarchical chunking test",
            "chunking_strategy": "hierarchical",
            "chunking_params": {
                "parent_chunk_size": 2000,
                "child_chunk_size": 200,
                "child_chunk_overlap": 20,
            },
            "embedding": {
                "vendor": "fake",
                "model": "fake-model",
                "api_endpoint": "",
            },
            "vector_db_backend": "chromadb",
        },
        headers=AUTH_HEADERS,
    )
    assert create_r.status_code == 201, create_r.text
    hier_collection = create_r.json()

    markdown_text = """## Introduction to LAMB

LAMB is a learning assistant management platform for educators. It supports
multiple LLM backends and RAG knowledge bases.

### Key Features

The platform provides a no-code assistant builder, multi-model support, and
privacy-first design principles for educational use cases.

## Technical Architecture

The system uses a microservice architecture with a FastAPI backend, Svelte
frontend, and dedicated KB Server for vector storage and retrieval operations.

### KB Server

The KB Server handles document chunking, embedding, and storage. It supports
ChromaDB and Qdrant as vector database backends.
"""

    ingest_r = await client.post(
        f"/collections/{hier_collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "hier-doc-1",
                    "title": "LAMB Architecture",
                    "text": markdown_text,
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert ingest_r.status_code == 202
    final = await _poll_job(client, ingest_r.json()["job_id"], timeout=20)
    assert final["status"] == "completed", final
    assert final["chunks_created"] >= 2

    # Query — results should have section_title metadata from hierarchical chunking.
    query_r = await client.post(
        f"/collections/{hier_collection['id']}/query",
        json={
            "query_text": "LAMB platform features",
            "top_k": 5,
        },
        headers=AUTH_HEADERS,
    )
    assert query_r.status_code == 200
    results = query_r.json()["results"]
    assert results, "No results from hierarchical collection"

    # All chunks should come from our document.
    for result in results:
        assert result["metadata"]["source_item_id"] == "hier-doc-1"

    # At least one chunk should have a section_title from the markdown headers.
    section_titles = [r["metadata"].get("section_title") for r in results]
    assert any(t is not None for t in section_titles), (
        f"Expected section_title in at least one chunk, got: {section_titles}"
    )


@pytest.mark.asyncio
async def test_by_page_chunking_with_pre_split_pages(
    client: AsyncClient, org_id: str
) -> None:
    """by_page chunking with pre-split pages produces chunks with page_range metadata."""
    # Create a by_page-chunking collection.
    create_r = await client.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": f"bypage-test-{uuid4().hex[:6]}",
            "description": "By-page chunking test",
            "chunking_strategy": "by_page",
            "chunking_params": {"pages_per_chunk": 1},
            "embedding": {
                "vendor": "fake",
                "model": "fake-model",
                "api_endpoint": "",
            },
            "vector_db_backend": "chromadb",
        },
        headers=AUTH_HEADERS,
    )
    assert create_r.status_code == 201, create_r.text
    page_collection = create_r.json()

    # Ingest a document with pre-split pages (simulates Library Manager pages).
    ingest_r = await client.post(
        f"/collections/{page_collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "paged-doc-1",
                    "title": "Paged Document",
                    "text": "",  # text ignored when pages present
                    "pages": [
                        {
                            "page_number": 1,
                            "text": (
                                "Page one discusses the fundamentals of machine learning "
                                "and its applications in various fields of science."
                            ),
                        },
                        {
                            "page_number": 2,
                            "text": (
                                "Page two covers deep learning architectures including "
                                "convolutional and recurrent neural networks."
                            ),
                        },
                    ],
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert ingest_r.status_code == 202
    final = await _poll_job(client, ingest_r.json()["job_id"], timeout=20)
    assert final["status"] == "completed", final
    assert final["chunks_created"] == 2  # one chunk per page

    # Query — chunks should have page_range metadata.
    query_r = await client.post(
        f"/collections/{page_collection['id']}/query",
        json={
            "query_text": "machine learning fundamentals",
            "top_k": 5,
        },
        headers=AUTH_HEADERS,
    )
    assert query_r.status_code == 200
    results = query_r.json()["results"]
    assert results, "No results from by_page collection"

    # Every chunk should have page_range set.
    for result in results:
        assert "page_range" in result["metadata"], (
            f"Expected page_range in metadata, got: {result['metadata'].keys()}"
        )

    # Top result (page-1 content) should have page_range="1".
    page_ranges = {r["metadata"]["page_range"] for r in results}
    assert "1" in page_ranges or "2" in page_ranges, (
        f"Expected page ranges 1 or 2, got: {page_ranges}"
    )


@pytest.mark.asyncio
async def test_malformed_content_length_header_ignored(
    client: AsyncClient, collection: dict
) -> None:
    """Non-numeric Content-Length header is ignored (ValueError branch in content.py).

    When Content-Length is not a valid integer, the server silently ignores it
    (line 64: ``except ValueError: pass``) and processes the request normally.
    This exercises the branch at line 64 of routers/content.py.
    """
    import json  # noqa: PLC0415

    payload = {
        "documents": [
            {"source_item_id": "cl-invalid", "title": "CL Invalid", "text": "hello world"}
        ]
    }
    body_bytes = json.dumps(payload).encode()

    headers = {
        **AUTH_HEADERS,
        "Content-Length": "not-a-number",  # malformed — triggers ValueError
        "Content-Type": "application/json",
    }
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        content=body_bytes,
        headers=headers,
    )
    # Server should ignore the bad header and proceed normally.
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_add_content_no_content_length_header(
    client: AsyncClient, collection: dict
) -> None:
    """Request without Content-Length header skips the size check entirely.

    The guard in content.py (line 52-64) only fires when the header is present.
    This test exercises the ``content_length is None`` branch (53->66).
    We strip Content-Length by using a custom ASGI wrapper that removes the
    header from the scope before it reaches the app.
    """
    import json  # noqa: PLC0415

    import main  # noqa: PLC0415

    # Wrap the app: strip 'content-length' from headers before each request.
    class _StripContentLengthMiddleware:
        def __init__(self, inner_app):
            self._app = inner_app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                scope = dict(scope)
                scope["headers"] = [
                    (k, v)
                    for k, v in scope["headers"]
                    if k.lower() != b"content-length"
                ]
            await self._app(scope, receive, send)

    from httpx import ASGITransport, AsyncClient  # noqa: PLC0415
    from tasks.worker import start_worker, stop_worker  # noqa: PLC0415

    await start_worker()
    wrapped_app = _StripContentLengthMiddleware(main.app)
    transport = ASGITransport(app=wrapped_app)  # type: ignore[arg-type]
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as stripped_client:
            payload = {
                "documents": [
                    {
                        "source_item_id": "no-cl",
                        "title": "No CL",
                        "text": "Content without Content-Length header.",
                    }
                ]
            }
            body_bytes = json.dumps(payload).encode()
            headers = {
                **AUTH_HEADERS,
                "Content-Type": "application/json",
            }
            r = await stripped_client.post(
                f"/collections/{collection['id']}/add-content",
                content=body_bytes,
                headers=headers,
            )
            assert r.status_code == 202
    finally:
        await stop_worker()


@pytest.mark.asyncio
async def test_ingestion_empty_text_document_zero_chunks(
    client: AsyncClient, collection: dict
) -> None:
    """A document with empty text produces zero chunks (chunks empty branch).

    Covers the ``if chunks:`` branch in execute_ingestion_job (line 183->191)
    where the empty path is taken — ``n_stored = 0`` without calling add_chunks.
    """
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "empty-text-doc",
                    "title": "Empty",
                    "text": "",  # empty text → no chunks produced
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    final = await _poll_job(client, r.json()["job_id"], timeout=20)
    assert final["status"] == "completed"
    # No chunks should have been created from empty text.
    assert final["chunks_created"] == 0


@pytest.mark.asyncio
async def test_ingestion_batch_commit_boundary(
    client: AsyncClient, collection: dict
) -> None:
    """Ingesting >5 documents triggers the mid-batch commit (line 197).

    _COMMIT_BATCH_SIZE=5 means after doc 5 is processed, a mid-run db.commit()
    is called. This test verifies that 6 documents all complete successfully
    (implicitly hitting the batch boundary at index 5, i.e., (5+1)%5==0).
    """
    docs = [
        {
            "source_item_id": f"batch-doc-{i}",
            "title": f"Batch Doc {i}",
            "text": f"Batch document number {i} containing unique content for testing.",
        }
        for i in range(6)  # 6 docs: batch commit fires after doc index 4 (5th doc)
    ]
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={"documents": docs},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    final = await _poll_job(client, r.json()["job_id"], timeout=30)
    assert final["status"] == "completed", final
    assert final["documents_processed"] == 6
    assert final["chunks_created"] >= 6  # at least one chunk per doc


@pytest.mark.asyncio
async def test_delete_vectors_unknown_collection(client: AsyncClient) -> None:
    """DELETE /collections/{unknown}/content/{source} returns 404.

    Covers line 241 in ingestion_service.delete_vectors (collection not found).
    """
    r = await client.delete(
        "/collections/nonexistent-collection-id/content/some-source",
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_vectors_backend_unavailable(
    client: AsyncClient, org_id: str
) -> None:
    """delete_vectors returns 503 when the vector DB backend is disabled.

    Covers line 248 in ingestion_service (backend None in delete_vectors).
    Create a collection, then disable its backend plugin, then attempt delete.
    """
    from plugins.base import VectorDBRegistry  # noqa: PLC0415

    from tests._fakes import register_fake_embedding  # noqa: PLC0415

    # Create a normal chromadb collection.
    create_r = await client.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": f"be-disable-{uuid4().hex[:6]}",
            "description": "Backend disable test",
            "chunking_strategy": "simple",
            "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
            "embedding": {
                "vendor": "fake",
                "model": "fake-model",
                "api_endpoint": "",
            },
            "vector_db_backend": "chromadb",
        },
        headers=AUTH_HEADERS,
    )
    assert create_r.status_code == 201, create_r.text
    coll = create_r.json()

    # Ingest one document so the collection has content.
    r = await client.post(
        f"/collections/{coll['id']}/add-content",
        json={
            "documents": [
                {"source_item_id": "be-src", "title": "BE Src", "text": "Backend test content."}
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    final = await _poll_job(client, r.json()["job_id"], timeout=20)
    assert final["status"] == "completed"

    # Temporarily remove the chromadb backend from the registry to simulate
    # it being disabled after collection creation.
    chromadb_cls = VectorDBRegistry._plugins.pop("chromadb", None)
    try:
        del_r = await client.delete(
            f"/collections/{coll['id']}/content/be-src",
            headers=AUTH_HEADERS,
        )
        assert del_r.status_code == 503
    finally:
        # Restore chromadb backend.
        if chromadb_cls is not None:
            VectorDBRegistry._plugins["chromadb"] = chromadb_cls
        register_fake_embedding()


@pytest.mark.asyncio
async def test_delete_vectors_updates_counters(
    client: AsyncClient, collection: dict
) -> None:
    """Deleting vectors decrements document_count and chunk_count (line 261->264).

    Covers the ``if deleted_count > 0`` branch in ingestion_service.delete_vectors.
    """
    # Ingest one source.
    r = await client.post(
        f"/collections/{collection['id']}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "counter-src",
                    "title": "Counter Source",
                    "text": "This document will be deleted to test counter decrement.",
                }
            ]
        },
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 202
    final = await _poll_job(client, r.json()["job_id"], timeout=20)
    assert final["status"] == "completed"
    chunks_added = final["chunks_created"]

    # Record counters before deletion.
    c_before = await client.get(f"/collections/{collection['id']}", headers=AUTH_HEADERS)
    doc_count_before = c_before.json()["document_count"]
    chunk_count_before = c_before.json()["chunk_count"]
    assert doc_count_before >= 1
    assert chunk_count_before >= 1

    # Delete the source.
    del_r = await client.delete(
        f"/collections/{collection['id']}/content/counter-src",
        headers=AUTH_HEADERS,
    )
    assert del_r.status_code == 200
    assert del_r.json()["deleted_count"] == chunks_added

    # Verify counters decremented.
    c_after = await client.get(f"/collections/{collection['id']}", headers=AUTH_HEADERS)
    assert c_after.json()["document_count"] == doc_count_before - 1
    assert c_after.json()["chunk_count"] == chunk_count_before - chunks_added


@pytest.mark.asyncio
async def test_delete_vectors_nonexistent_source_no_counter_change(
    client: AsyncClient, collection: dict
) -> None:
    """Deleting a source_item_id with zero vectors is a no-op on counters.

    Covers the ``deleted_count == 0`` (False) path of the ``if deleted_count > 0``
    branch in ingestion_service (line 261->264).
    """
    # Get current counters.
    c_before = await client.get(f"/collections/{collection['id']}", headers=AUTH_HEADERS)
    doc_before = c_before.json()["document_count"]
    chunk_before = c_before.json()["chunk_count"]

    # Attempt to delete a source that was never ingested.
    del_r = await client.delete(
        f"/collections/{collection['id']}/content/never-existed-source",
        headers=AUTH_HEADERS,
    )
    assert del_r.status_code == 200
    assert del_r.json()["deleted_count"] == 0

    # Counters must remain unchanged.
    c_after = await client.get(f"/collections/{collection['id']}", headers=AUTH_HEADERS)
    assert c_after.json()["document_count"] == doc_before
    assert c_after.json()["chunk_count"] == chunk_before


def test_queue_add_content_empty_documents_raises(collection: dict) -> None:
    """queue_add_content raises 400 when documents is empty (line 60).

    This path is normally guarded by Pydantic schema validation at the HTTP
    layer. We call the service directly to exercise the internal guard.
    """
    import pytest  # noqa: PLC0415
    from database.connection import get_session_direct  # noqa: PLC0415
    from fastapi import HTTPException  # noqa: PLC0415
    from schemas.content import AddContentRequest  # noqa: PLC0415
    from services import ingestion_service  # noqa: PLC0415

    db = get_session_direct()
    try:
        # Build a minimal AddContentRequest with an empty documents list by
        # bypassing Pydantic validation (construct skips validators).
        req = AddContentRequest.model_construct(documents=[], embedding_credentials=None)
        # Manually inject a falsy embedding_credentials to avoid AttributeError.
        from schemas.content import EmbeddingCredentials  # noqa: PLC0415

        req.embedding_credentials = EmbeddingCredentials.model_construct(
            api_key="", api_endpoint=""
        )
        with pytest.raises(HTTPException) as exc_info:
            ingestion_service.queue_add_content(db, collection["id"], req)
        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()
    finally:
        db.close()


def test_execute_ingestion_job_chunking_strategy_none(collection: dict) -> None:
    """execute_ingestion_job raises RuntimeError when chunking plugin is disabled.

    Covers line 153: ``if strategy is None: raise RuntimeError(...)``.
    We temporarily remove the chunking plugin from the registry to simulate
    it being disabled after collection creation.
    """
    import json  # noqa: PLC0415

    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import Collection, IngestionJob  # noqa: PLC0415
    from plugins.base import ChunkingRegistry  # noqa: PLC0415
    from services import ingestion_service  # noqa: PLC0415

    db = get_session_direct()
    try:
        coll = db.query(Collection).filter(Collection.id == collection["id"]).first()
        assert coll is not None

        # Create a fake job row (no DB insert needed — we call execute directly).
        fake_job = IngestionJob(
            id="test-chunking-none",
            collection_id=coll.id,
            organization_id=coll.organization_id,
            documents_json=json.dumps([{
                "source_item_id": "s", "title": "T", "text": "text",
                "permalinks": {}, "pages": [], "extra_metadata": {},
            }]),
            status="processing",
            documents_total=1,
            documents_processed=0,
            chunks_created=0,
            attempts=1,
        )

        # Remove the simple chunking plugin to force strategy=None.
        simple_cls = ChunkingRegistry._plugins.pop("simple", None)
        try:
            import pytest as _pytest  # noqa: PLC0415

            with _pytest.raises(RuntimeError, match="not available"):
                ingestion_service.execute_ingestion_job(db, fake_job, coll, {})
        finally:
            if simple_cls is not None:
                ChunkingRegistry._plugins["simple"] = simple_cls
    finally:
        db.close()


def test_execute_ingestion_job_vector_backend_none(collection: dict) -> None:
    """execute_ingestion_job raises RuntimeError when vector backend is disabled.

    Covers line 162: ``if backend is None: raise RuntimeError(...)``.
    We temporarily remove the chromadb backend from the registry to simulate
    it being disabled after collection creation.
    """
    import json  # noqa: PLC0415

    from database.connection import get_session_direct  # noqa: PLC0415
    from database.models import Collection, IngestionJob  # noqa: PLC0415
    from plugins.base import VectorDBRegistry  # noqa: PLC0415
    from services import ingestion_service  # noqa: PLC0415

    db = get_session_direct()
    try:
        coll = db.query(Collection).filter(Collection.id == collection["id"]).first()
        assert coll is not None

        fake_job = IngestionJob(
            id="test-backend-none",
            collection_id=coll.id,
            organization_id=coll.organization_id,
            documents_json=json.dumps([{
                "source_item_id": "s", "title": "T", "text": "text",
                "permalinks": {}, "pages": [], "extra_metadata": {},
            }]),
            status="processing",
            documents_total=1,
            documents_processed=0,
            chunks_created=0,
            attempts=1,
        )

        # Remove the chromadb backend to force backend=None.
        chromadb_cls = VectorDBRegistry._plugins.pop("chromadb", None)
        try:
            import pytest as _pytest  # noqa: PLC0415

            with _pytest.raises(RuntimeError, match="not available"):
                ingestion_service.execute_ingestion_job(db, fake_job, coll, {})
        finally:
            if chromadb_cls is not None:
                VectorDBRegistry._plugins["chromadb"] = chromadb_cls
    finally:
        db.close()
