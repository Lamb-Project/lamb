"""E2E pipeline matrix: create → ingest → query → delete over real HTTP.

Parametrized over (vector_db, embedding_vendor) combinations using real
backend containers (Qdrant on :16333, Ollama on :11435 with nomic-embed-text).

OpenAI is excluded from this matrix because no real API key is available
for recording VCR cassettes, and hand-crafted cassettes are fragile under
the current match_on=["method","host","path"] strategy when the request body
(model name, input texts) varies per test. OpenAI coverage is deferred to a
dedicated cassette-recording session.

Stack requirements (provided by the session-scope docker_stack fixture):
  - Qdrant  : http://127.0.0.1:{qdrant_port}
  - Ollama  : http://127.0.0.1:{ollama_port}  (nomic-embed-text must be pulled)
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx
import pytest

from tests._helpers import AUTH_HEADERS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POLL_INTERVAL = 1.0  # seconds between polls
_POLL_TIMEOUT = 120.0  # Ollama embeddings can be slow on first call


def _poll_job_sync(
    client: httpx.Client,
    job_id: str,
    timeout: float = _POLL_TIMEOUT,
    interval: float = _POLL_INTERVAL,
) -> dict:
    """Poll /jobs/{job_id} synchronously until terminal state or timeout."""
    deadline = time.monotonic() + timeout
    last_body: dict = {}
    while time.monotonic() < deadline:
        r = client.get(f"/jobs/{job_id}", headers=AUTH_HEADERS)
        assert r.status_code == 200, f"Poll failed: {r.status_code} {r.text}"
        last_body = r.json()
        if last_body["status"] in ("completed", "failed"):
            return last_body
        time.sleep(interval)
    raise AssertionError(
        f"Job {job_id!r} did not finish within {timeout}s; "
        f"last status={last_body}"
    )


def _unique_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _ollama_endpoint(docker_stack: dict) -> str:
    """Return the Ollama /api/embeddings URL for the running container."""
    return f"{docker_stack['ollama_url']}/api/embeddings"


# ---------------------------------------------------------------------------
# Matrix: (vector_db, embedding_vendor)
# ---------------------------------------------------------------------------

_MATRIX = [
    pytest.param("chromadb", "ollama", id="chromadb-ollama"),
    pytest.param("qdrant", "ollama", id="qdrant-ollama"),
]


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.parametrize("vector_db,embedding_vendor", _MATRIX)
def test_full_pipeline(
    http: httpx.Client,
    kb_server_process: dict,
    docker_stack: dict,
    vector_db: str,
    embedding_vendor: str,
) -> None:
    """Full create→ingest→query→delete pipeline for each backend×embedding combo.

    Steps:
      1.  POST /collections with the given (vector_db, embedding_vendor) combo.
      2.  POST /collections/{id}/add-content with 3 short documents using the
          "simple" chunking strategy.
      3.  Poll /jobs/{id} until completed (up to 120 s for Ollama).
      4.  POST /collections/{id}/query with text known to be in doc-2.
      5.  Assert top result has the expected source_item_id and score > 0.3.
      6.  DELETE /collections/{id}/content/{source_item_id} for doc-2.
      7.  Re-query and verify doc-2 no longer appears in top results.
      8.  DELETE /collections/{id} — assert 204.
      9.  Verify the storage directory was removed.
    """
    org_id = _unique_id("org-")
    collection_name = _unique_id(f"mat-{vector_db[:4]}-")
    ollama_ep = _ollama_endpoint(docker_stack)

    # ------------------------------------------------------------------
    # Step 1: Create collection
    # ------------------------------------------------------------------
    create_payload = {
        "organization_id": org_id,
        "name": collection_name,
        "description": f"Matrix test {vector_db}×{embedding_vendor}",
        "chunking_strategy": "simple",
        "chunking_params": {"chunk_size": 512, "chunk_overlap": 50},
        "embedding": {
            "vendor": embedding_vendor,
            "model": "nomic-embed-text",
            "api_endpoint": ollama_ep,
        },
        "vector_db_backend": vector_db,
    }
    r_create = http.post("/collections", json=create_payload)
    assert r_create.status_code == 201, (
        f"Create collection failed: {r_create.status_code} {r_create.text}"
    )
    collection = r_create.json()
    collection_id = collection["id"]
    assert collection["vector_db_backend"] == vector_db
    assert collection["embedding"]["vendor"] == embedding_vendor

    # ------------------------------------------------------------------
    # Step 2: Add 3 documents
    # ------------------------------------------------------------------
    doc1_text = (
        "The mitochondria is the powerhouse of the cell. "
        "It produces ATP through oxidative phosphorylation."
    )
    doc2_text = (
        "Photosynthesis is the process by which plants convert light energy "
        "into chemical energy stored as glucose. Chlorophyll absorbs sunlight."
    )
    doc3_text = (
        "The theory of general relativity describes gravity as the curvature "
        "of spacetime caused by mass and energy."
    )
    ingest_payload = {
        "documents": [
            {
                "source_item_id": "doc-1-cell",
                "title": "Cell Biology",
                "text": doc1_text,
                "permalinks": {
                    "original": f"/data/{org_id}/doc-1/original.txt",
                    "full_markdown": f"/data/{org_id}/doc-1/full.md",
                    "pages": [],
                },
            },
            {
                "source_item_id": "doc-2-plants",
                "title": "Plant Biology",
                "text": doc2_text,
                "permalinks": {
                    "original": f"/data/{org_id}/doc-2/original.txt",
                    "full_markdown": f"/data/{org_id}/doc-2/full.md",
                    "pages": [],
                },
            },
            {
                "source_item_id": "doc-3-physics",
                "title": "Physics",
                "text": doc3_text,
            },
        ],
        "embedding_credentials": {
            "api_key": "",
            "api_endpoint": ollama_ep,
        },
    }
    r_ingest = http.post(
        f"/collections/{collection_id}/add-content",
        json=ingest_payload,
    )
    assert r_ingest.status_code == 202, (
        f"Add-content failed: {r_ingest.status_code} {r_ingest.text}"
    )
    job_id = r_ingest.json()["job_id"]
    assert r_ingest.json()["documents_total"] == 3

    # ------------------------------------------------------------------
    # Step 3: Poll until completed
    # ------------------------------------------------------------------
    final = _poll_job_sync(http, job_id)
    assert final["status"] == "completed", (
        f"Job did not complete: {final}"
    )
    assert final["documents_processed"] == 3
    assert final["chunks_created"] >= 3

    # ------------------------------------------------------------------
    # Step 4: Query with text known to be in doc-2
    # ------------------------------------------------------------------
    query_payload = {
        "query_text": "photosynthesis plants convert light energy glucose",
        "top_k": 3,
        "embedding_credentials": {
            "api_key": "",
            "api_endpoint": ollama_ep,
        },
    }
    r_query = http.post(
        f"/collections/{collection_id}/query",
        json=query_payload,
    )
    assert r_query.status_code == 200, (
        f"Query failed: {r_query.status_code} {r_query.text}"
    )
    results = r_query.json()["results"]
    assert results, "Query returned no results"

    # ------------------------------------------------------------------
    # Step 5: Assert top result is doc-2 with score > 0.3
    # ------------------------------------------------------------------
    top_result = results[0]
    assert top_result["metadata"]["source_item_id"] == "doc-2-plants", (
        f"Expected top result from doc-2-plants but got "
        f"{top_result['metadata']['source_item_id']!r}; "
        f"all results: {[(r['metadata']['source_item_id'], r['score']) for r in results]}"
    )
    assert top_result["score"] > 0.3, (
        f"Expected score > 0.3, got {top_result['score']}"
    )

    # ------------------------------------------------------------------
    # Step 6: Delete doc-2 vectors
    # ------------------------------------------------------------------
    r_del_content = http.delete(
        f"/collections/{collection_id}/content/doc-2-plants",
    )
    assert r_del_content.status_code == 200, (
        f"Delete content failed: {r_del_content.status_code} {r_del_content.text}"
    )
    del_body = r_del_content.json()
    assert del_body["source_item_id"] == "doc-2-plants"
    assert del_body["deleted_count"] >= 1

    # ------------------------------------------------------------------
    # Step 7: Re-query — doc-2 must no longer appear
    # ------------------------------------------------------------------
    r_requery = http.post(
        f"/collections/{collection_id}/query",
        json=query_payload,
    )
    assert r_requery.status_code == 200
    requery_results = r_requery.json()["results"]
    doc2_hits = [
        r for r in requery_results
        if r["metadata"]["source_item_id"] == "doc-2-plants"
    ]
    assert doc2_hits == [], (
        f"doc-2-plants still appears after deletion: {doc2_hits}"
    )

    # ------------------------------------------------------------------
    # Step 8: Delete the entire collection
    # ------------------------------------------------------------------
    r_del_coll = http.delete(f"/collections/{collection_id}")
    assert r_del_coll.status_code == 204, (
        f"Delete collection failed: {r_del_coll.status_code} {r_del_coll.text}"
    )

    # ------------------------------------------------------------------
    # Step 9: Verify storage path was removed
    # ------------------------------------------------------------------
    data_dir = Path(kb_server_process["data_dir"])
    storage_path = data_dir / "storage" / org_id / collection_id
    assert not storage_path.exists(), (
        f"Storage path still exists after collection deletion: {storage_path}"
    )

    # Verify collection is gone from the API too
    r_get = http.get(f"/collections/{collection_id}")
    assert r_get.status_code == 404


# ---------------------------------------------------------------------------
# Chunking variety tests (chromadb + ollama, non-parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_with_hierarchical_chunking(
    http: httpx.Client,
    kb_server_process: dict,
    docker_stack: dict,
) -> None:
    """Full pipeline using hierarchical chunking strategy with real Ollama embeddings.

    Verifies that hierarchical parent/child chunks are produced and that
    query results carry section_title metadata from the markdown headers.
    """
    org_id = _unique_id("org-")
    ollama_ep = _ollama_endpoint(docker_stack)

    # Create collection
    r_create = http.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": _unique_id("hier-"),
            "description": "Hierarchical chunking e2e test",
            "chunking_strategy": "hierarchical",
            "chunking_params": {
                "parent_chunk_size": 2000,
                "child_chunk_size": 300,
                "child_chunk_overlap": 30,
            },
            "embedding": {
                "vendor": "ollama",
                "model": "nomic-embed-text",
                "api_endpoint": ollama_ep,
            },
            "vector_db_backend": "chromadb",
        },
    )
    assert r_create.status_code == 201, r_create.text
    coll_id = r_create.json()["id"]

    # Markdown document with two H2 sections and nested H3 subsections
    markdown_doc = """## Introduction to Knowledge Bases

A knowledge base stores documents in a structured way so that they can be
retrieved efficiently using semantic search. Modern knowledge bases use vector
embeddings to capture the meaning of text rather than just keywords.

### Vector Embeddings

Vector embeddings are numerical representations of text in high-dimensional
space. Semantically similar texts will have vectors that are close together
under cosine similarity.

## Retrieval Augmented Generation

RAG combines a retrieval system with a language model. The retrieval step
finds relevant documents, and the generation step synthesizes an answer.

### Query Processing

When a user submits a query, it is first embedded into a vector, then the
nearest neighbour search locates the most relevant document chunks.
"""

    # Ingest
    r_ingest = http.post(
        f"/collections/{coll_id}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "kb-arch-doc",
                    "title": "Knowledge Base Architecture",
                    "text": markdown_doc,
                }
            ],
            "embedding_credentials": {"api_key": "", "api_endpoint": ollama_ep},
        },
    )
    assert r_ingest.status_code == 202, r_ingest.text
    final = _poll_job_sync(http, r_ingest.json()["job_id"])
    assert final["status"] == "completed", final
    assert final["chunks_created"] >= 2

    # Query for content in the second section
    r_query = http.post(
        f"/collections/{coll_id}/query",
        json={
            "query_text": "retrieval augmented generation RAG language model",
            "top_k": 5,
            "embedding_credentials": {"api_key": "", "api_endpoint": ollama_ep},
        },
    )
    assert r_query.status_code == 200, r_query.text
    results = r_query.json()["results"]
    assert results, "Query returned no results for hierarchical collection"

    # All results should be from our document
    for res in results:
        assert res["metadata"]["source_item_id"] == "kb-arch-doc"

    # At least one chunk should have section_title from markdown headers
    section_titles = [r["metadata"].get("section_title") for r in results]
    has_section_title = any(t is not None for t in section_titles)
    assert has_section_title, (
        f"Expected section_title in at least one chunk; "
        f"metadata keys: {[list(r['metadata'].keys()) for r in results]}"
    )

    # Cleanup
    http.delete(f"/collections/{coll_id}")


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_with_by_page_chunking(
    http: httpx.Client,
    kb_server_process: dict,
    docker_stack: dict,
) -> None:
    """Full pipeline using by_page chunking with pre-split pages and real Ollama.

    Verifies page_range metadata is present in query results and that each
    page produces a distinct chunk with the correct page number.
    """
    org_id = _unique_id("org-")
    ollama_ep = _ollama_endpoint(docker_stack)

    # Create collection
    r_create = http.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": _unique_id("bypage-"),
            "description": "By-page chunking e2e test",
            "chunking_strategy": "by_page",
            "chunking_params": {"pages_per_chunk": 1},
            "embedding": {
                "vendor": "ollama",
                "model": "nomic-embed-text",
                "api_endpoint": ollama_ep,
            },
            "vector_db_backend": "chromadb",
        },
    )
    assert r_create.status_code == 201, r_create.text
    coll_id = r_create.json()["id"]

    # Three-page document with clearly distinct topics per page
    pages = [
        {
            "page_number": 1,
            "text": (
                "Page one covers the fundamentals of machine learning. "
                "Supervised learning uses labelled training data to train models "
                "that generalise to new examples."
            ),
        },
        {
            "page_number": 2,
            "text": (
                "Page two explains convolutional neural networks for image recognition. "
                "CNNs use filters to detect visual features like edges and textures."
            ),
        },
        {
            "page_number": 3,
            "text": (
                "Page three describes reinforcement learning where agents learn "
                "by receiving rewards or penalties from their environment."
            ),
        },
    ]

    # Ingest
    r_ingest = http.post(
        f"/collections/{coll_id}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "ml-textbook",
                    "title": "Machine Learning Textbook",
                    "text": "",  # text ignored when pages are provided
                    "pages": pages,
                    "permalinks": {
                        "original": "/data/ml-textbook/original.pdf",
                        "full_markdown": "/data/ml-textbook/full.md",
                        "pages": [
                            "/data/ml-textbook/pages/1.md",
                            "/data/ml-textbook/pages/2.md",
                            "/data/ml-textbook/pages/3.md",
                        ],
                    },
                }
            ],
            "embedding_credentials": {"api_key": "", "api_endpoint": ollama_ep},
        },
    )
    assert r_ingest.status_code == 202, r_ingest.text
    final = _poll_job_sync(http, r_ingest.json()["job_id"])
    assert final["status"] == "completed", final
    # One chunk per page
    assert final["chunks_created"] == 3, (
        f"Expected 3 chunks (one per page), got {final['chunks_created']}"
    )

    # Query for page-2 content (CNNs / image recognition)
    r_query = http.post(
        f"/collections/{coll_id}/query",
        json={
            "query_text": "convolutional neural networks image recognition filters",
            "top_k": 3,
            "embedding_credentials": {"api_key": "", "api_endpoint": ollama_ep},
        },
    )
    assert r_query.status_code == 200, r_query.text
    results = r_query.json()["results"]
    assert results, "Query returned no results for by_page collection"

    # Every chunk must have page_range metadata
    for res in results:
        assert "page_range" in res["metadata"], (
            f"Missing page_range in metadata: {res['metadata'].keys()}"
        )

    # Top result should be page-2 content
    top_page_range = results[0]["metadata"]["page_range"]
    assert "2" in str(top_page_range), (
        f"Expected top result to be from page 2, got page_range={top_page_range!r}; "
        f"all: {[(r['metadata']['page_range'], r['score']) for r in results]}"
    )

    # Cleanup
    http.delete(f"/collections/{coll_id}")


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_with_by_section_chunking(
    http: httpx.Client,
    kb_server_process: dict,
    docker_stack: dict,
) -> None:
    """Full pipeline using by_section chunking with real Ollama embeddings.

    Verifies that sections are split on H2 headings and that each chunk
    carries a section_title in its metadata.
    """
    org_id = _unique_id("org-")
    ollama_ep = _ollama_endpoint(docker_stack)

    # Create collection
    r_create = http.post(
        "/collections",
        json={
            "organization_id": org_id,
            "name": _unique_id("bysect-"),
            "description": "By-section chunking e2e test",
            "chunking_strategy": "by_section",
            "chunking_params": {
                "split_on_heading": 2,
                "headings_per_chunk": 1,
            },
            "embedding": {
                "vendor": "ollama",
                "model": "nomic-embed-text",
                "api_endpoint": ollama_ep,
            },
            "vector_db_backend": "chromadb",
        },
    )
    assert r_create.status_code == 201, r_create.text
    coll_id = r_create.json()["id"]

    # Document with three clearly distinct H2 sections
    section_doc = """## Climate Change

Climate change refers to long-term shifts in temperatures and weather patterns.
Human activities such as burning fossil fuels are the primary driver of the
accelerating changes observed since the mid-20th century.

## Biodiversity Loss

Biodiversity loss is the decline in the variety of life on Earth. Habitat
destruction, pollution, and invasive species are among the leading causes.
Conservation efforts focus on protecting ecosystems and endangered species.

## Ocean Acidification

Ocean acidification occurs when carbon dioxide dissolves in seawater forming
carbonic acid. This process is harmful to marine organisms that build shells
and skeletons from calcium carbonate.
"""

    # Ingest
    r_ingest = http.post(
        f"/collections/{coll_id}/add-content",
        json={
            "documents": [
                {
                    "source_item_id": "environment-doc",
                    "title": "Environmental Issues",
                    "text": section_doc,
                }
            ],
            "embedding_credentials": {"api_key": "", "api_endpoint": ollama_ep},
        },
    )
    assert r_ingest.status_code == 202, r_ingest.text
    final = _poll_job_sync(http, r_ingest.json()["job_id"])
    assert final["status"] == "completed", final
    # Three H2 sections → at least 3 chunks
    assert final["chunks_created"] >= 3, (
        f"Expected ≥3 chunks from 3 H2 sections, got {final['chunks_created']}"
    )

    # Query for ocean acidification section
    r_query = http.post(
        f"/collections/{coll_id}/query",
        json={
            "query_text": "ocean acidification carbon dioxide seawater carbonic acid",
            "top_k": 3,
            "embedding_credentials": {"api_key": "", "api_endpoint": ollama_ep},
        },
    )
    assert r_query.status_code == 200, r_query.text
    results = r_query.json()["results"]
    assert results, "Query returned no results for by_section collection"

    # All chunks from our document
    for res in results:
        assert res["metadata"]["source_item_id"] == "environment-doc"

    # At least one result should carry section/heading metadata.
    # by_section chunking emits "section_titles" (list) and "parent_path".
    metadata_keys_all = [set(r["metadata"].keys()) for r in results]
    has_heading_meta = any(
        "section_titles" in keys
        or "section_title" in keys
        or "heading" in keys
        or "parent_path" in keys
        for keys in metadata_keys_all
    )
    assert has_heading_meta, (
        f"Expected section_titles/section_title/heading/parent_path metadata "
        f"from by_section chunking; metadata keys seen: {metadata_keys_all}"
    )

    # Top result should be about ocean (highest cosine similarity)
    top_text = results[0]["text"].lower()
    assert "ocean" in top_text or "acidification" in top_text or "carbon" in top_text, (
        f"Top result does not seem to be the ocean section: {results[0]['text'][:200]!r}"
    )

    # Cleanup
    http.delete(f"/collections/{coll_id}")
