"""E2E multi-tenancy isolation tests.

Verifies per-org isolation over real HTTP against a real uvicorn subprocess
with a real ChromaDB / Qdrant backend and real Ollama embeddings.

ADR-6: LAMB owns ACL; KB Server does not enforce per-org access on GET by id.
ADR-9: Per-org filesystem isolation at data/storage/{org_id}/{collection_id}/.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from tests._helpers import AUTH_HEADERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org_id() -> str:
    """Generate a short, unique org ID safe to use as a directory name."""
    return f"org-{uuid4().hex[:8]}"


def _create_collection(
    http: httpx.Client,
    org_id: str,
    name: str,
    vendor: str = "ollama",
    api_endpoint: str = "",
) -> dict:
    """POST /collections and return the parsed JSON body.

    Uses Ollama as the embedding vendor so real vectors are produced, which
    makes the cross-org leak test (#5) meaningful.
    """
    payload = {
        "organization_id": org_id,
        "name": name,
        "description": f"e2e multitenancy test for org {org_id}",
        "chunking_strategy": "simple",
        "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
        "embedding": {
            "vendor": vendor,
            "model": "nomic-embed-text",
            "api_endpoint": api_endpoint,
        },
        "vector_db_backend": "chromadb",
    }
    r = http.post("/collections", json=payload)
    assert r.status_code == 201, f"create_collection failed: {r.text}"
    return r.json()


def _ingest(
    http: httpx.Client,
    collection_id: str,
    source_item_id: str,
    text: str,
    api_endpoint: str = "",
) -> str:
    """POST add-content and return the job_id."""
    payload = {
        "documents": [
            {
                "source_item_id": source_item_id,
                "title": source_item_id,
                "text": text,
            }
        ],
        "embedding_credentials": {
            "api_key": "",
            "api_endpoint": api_endpoint,
        },
    }
    r = http.post(f"/collections/{collection_id}/add-content", json=payload)
    assert r.status_code == 202, f"add-content failed: {r.text}"
    return r.json()["job_id"]


def _poll_job(
    http: httpx.Client,
    job_id: str,
    timeout: float = 60.0,
    interval: float = 0.5,
) -> dict:
    """Synchronous poll for /jobs/{id} until terminal state or timeout."""
    deadline = time.monotonic() + timeout
    body: dict = {}
    while time.monotonic() < deadline:
        r = http.get(f"/jobs/{job_id}")
        assert r.status_code == 200, r.text
        body = r.json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(interval)
    raise AssertionError(
        f"Job {job_id} did not finish within {timeout}s; last body={body}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_two_orgs_same_collection_name(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """Two orgs can each create a collection named 'kb1' — both return 201.

    Name uniqueness is scoped per (organization_id, name) — the same name in
    different orgs must succeed.
    """
    ollama_url = docker_stack["ollama_url"]
    org_a = _org_id()
    org_b = _org_id()

    col_a = _create_collection(http, org_a, "kb1", api_endpoint=ollama_url)
    col_b = _create_collection(http, org_b, "kb1", api_endpoint=ollama_url)

    assert col_a["organization_id"] == org_a
    assert col_b["organization_id"] == org_b
    assert col_a["name"] == "kb1"
    assert col_b["name"] == "kb1"
    # Each collection gets its own unique ID despite the same name.
    assert col_a["id"] != col_b["id"]


@pytest.mark.e2e
def test_filesystem_isolation_per_org(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """Each org has its own directory tree under data/storage/{org_id}/.

    After creating and ingesting into collections for org-A and org-B, each
    org's storage directory must exist and be completely separate.
    """
    ollama_url = docker_stack["ollama_url"]
    data_dir = Path(kb_server_process["data_dir"])
    org_a = _org_id()
    org_b = _org_id()

    col_a = _create_collection(http, org_a, "fs-test", api_endpoint=ollama_url)
    col_b = _create_collection(http, org_b, "fs-test", api_endpoint=ollama_url)

    # Ingest something to ensure the storage directories are populated.
    job_a = _ingest(
        http,
        col_a["id"],
        "doc-a",
        "Filesystem isolation test content for org A.",
        api_endpoint=ollama_url,
    )
    job_b = _ingest(
        http,
        col_b["id"],
        "doc-b",
        "Filesystem isolation test content for org B.",
        api_endpoint=ollama_url,
    )
    result_a = _poll_job(http, job_a)
    result_b = _poll_job(http, job_b)
    assert result_a["status"] == "completed", result_a
    assert result_b["status"] == "completed", result_b

    # Assert each org has its own directory under storage/.
    dir_a = data_dir / "storage" / org_a / col_a["id"]
    dir_b = data_dir / "storage" / org_b / col_b["id"]

    assert dir_a.exists(), f"Expected org-A storage dir at {dir_a}"
    assert dir_b.exists(), f"Expected org-B storage dir at {dir_b}"

    # The two paths are entirely separate — org-A's dir has nothing from org-B.
    assert dir_a != dir_b
    assert not dir_a.is_relative_to(dir_b)
    assert not dir_b.is_relative_to(dir_a)

    # Org-A's root only contains org-A's collection; org-B's is isolated.
    org_a_root = data_dir / "storage" / org_a
    org_b_root = data_dir / "storage" / org_b
    a_children = {p.name for p in org_a_root.iterdir() if p.is_dir()}
    b_children = {p.name for p in org_b_root.iterdir() if p.is_dir()}
    assert col_a["id"] in a_children
    assert col_b["id"] not in a_children  # org-A dir has no org-B collections
    assert col_b["id"] in b_children
    assert col_a["id"] not in b_children  # org-B dir has no org-A collections


@pytest.mark.e2e
def test_cross_org_collection_access_via_id(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """GET /collections/{id} (no org filter) returns the collection regardless of org.

    ADR-6: The KB Server does NOT enforce per-org access control on GET by id.
    LAMB owns ACL. Any valid collection_id is retrievable by any authenticated
    caller — the KB Server is a trusted internal service.

    This documents the actual behavior: the collection is returned with a 200.
    """
    ollama_url = docker_stack["ollama_url"]
    org_a = _org_id()

    col_a = _create_collection(http, org_a, "acl-test", api_endpoint=ollama_url)
    collection_id = col_a["id"]

    # Retrieve the collection by ID — no org filter is required or checked.
    r = http.get(f"/collections/{collection_id}")
    assert r.status_code == 200, (
        f"Expected 200 for GET /collections/{collection_id} (ADR-6: KB Server "
        f"does not enforce per-org ACL on GET; got {r.status_code}: {r.text})"
    )
    body = r.json()
    assert body["id"] == collection_id
    assert body["organization_id"] == org_a


@pytest.mark.e2e
def test_list_with_org_filter_excludes_other_orgs(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """GET /collections?organization_id=A returns only A's collections.

    Create kb-1 in org-A and kb-2 in org-B. Listing with org-A's filter must
    contain kb-1 but not kb-2, and vice versa.
    """
    ollama_url = docker_stack["ollama_url"]
    org_a = _org_id()
    org_b = _org_id()

    col_a = _create_collection(http, org_a, "kb-1", api_endpoint=ollama_url)
    col_b = _create_collection(http, org_b, "kb-2", api_endpoint=ollama_url)

    # List org-A.
    r_a = http.get(f"/collections?organization_id={org_a}")
    assert r_a.status_code == 200
    body_a = r_a.json()
    ids_a = {c["id"] for c in body_a["collections"]}
    assert col_a["id"] in ids_a, "org-A's collection missing from org-A filter"
    assert col_b["id"] not in ids_a, "org-B's collection leaked into org-A filter"
    for c in body_a["collections"]:
        assert c["organization_id"] == org_a, (
            f"Unexpected org in org-A listing: {c['organization_id']}"
        )

    # List org-B.
    r_b = http.get(f"/collections?organization_id={org_b}")
    assert r_b.status_code == 200
    body_b = r_b.json()
    ids_b = {c["id"] for c in body_b["collections"]}
    assert col_b["id"] in ids_b, "org-B's collection missing from org-B filter"
    assert col_a["id"] not in ids_b, "org-A's collection leaked into org-B filter"
    for c in body_b["collections"]:
        assert c["organization_id"] == org_b, (
            f"Unexpected org in org-B listing: {c['organization_id']}"
        )


@pytest.mark.e2e
@pytest.mark.slow
def test_query_isolation_between_orgs(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """Querying org-A's collection must not surface org-B's chunks.

    Uses real Ollama embeddings so each phrase produces a real semantic vector.
    Ingest "secret-org-A-data" into org-A's collection and "secret-org-B-data"
    into org-B's collection. Query org-A's collection for "secret-org-B-data"
    — no result with source_item_id from org-B must appear.
    """
    ollama_url = docker_stack["ollama_url"]
    org_a = _org_id()
    org_b = _org_id()

    col_a = _create_collection(http, org_a, "query-iso-a", api_endpoint=ollama_url)
    col_b = _create_collection(http, org_b, "query-iso-b", api_endpoint=ollama_url)

    # Ingest into org-A.
    job_a = _ingest(
        http,
        col_a["id"],
        "src-a",
        "secret-org-A-data: confidential information belonging to organization A.",
        api_endpoint=ollama_url,
    )
    # Ingest into org-B.
    job_b = _ingest(
        http,
        col_b["id"],
        "src-b",
        "secret-org-B-data: confidential information belonging to organization B.",
        api_endpoint=ollama_url,
    )

    result_a = _poll_job(http, job_a)
    result_b = _poll_job(http, job_b)
    assert result_a["status"] == "completed", result_a
    assert result_b["status"] == "completed", result_b

    # Query org-A's collection for org-B's secret phrase.
    q = http.post(
        f"/collections/{col_a['id']}/query",
        json={
            "query_text": "secret-org-B-data",
            "top_k": 10,
            "embedding_credentials": {
                "api_key": "",
                "api_endpoint": ollama_url,
            },
        },
    )
    assert q.status_code == 200, q.text
    results = q.json()["results"]

    # No result from org-B's source must appear.
    org_b_hits = [r for r in results if r["metadata"].get("source_item_id") == "src-b"]
    assert org_b_hits == [], (
        f"Cross-org data leak detected: org-B chunks appeared in org-A query: {org_b_hits}"
    )


@pytest.mark.e2e
def test_delete_one_orgs_collection_doesnt_affect_other(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """Deleting org-A's collection leaves org-B's collection intact.

    After DELETE kb-1 (org-A):
    - GET kb-1 → 404
    - GET kb-2 → 200
    - org-A's storage dir is gone
    - org-B's storage dir still exists
    """
    ollama_url = docker_stack["ollama_url"]
    data_dir = Path(kb_server_process["data_dir"])
    org_a = _org_id()
    org_b = _org_id()

    col_a = _create_collection(http, org_a, "del-test-a", api_endpoint=ollama_url)
    col_b = _create_collection(http, org_b, "del-test-b", api_endpoint=ollama_url)

    # Ingest into both so storage directories are created.
    job_a = _ingest(
        http,
        col_a["id"],
        "doc-del-a",
        "Org A content for deletion test.",
        api_endpoint=ollama_url,
    )
    job_b = _ingest(
        http,
        col_b["id"],
        "doc-del-b",
        "Org B content for deletion test.",
        api_endpoint=ollama_url,
    )
    assert _poll_job(http, job_a)["status"] == "completed"
    assert _poll_job(http, job_b)["status"] == "completed"

    # Verify both storage dirs exist before deletion.
    dir_a = data_dir / "storage" / org_a / col_a["id"]
    dir_b = data_dir / "storage" / org_b / col_b["id"]
    assert dir_a.exists(), f"org-A storage dir should exist before delete: {dir_a}"
    assert dir_b.exists(), f"org-B storage dir should exist before delete: {dir_b}"

    # Delete org-A's collection.
    r_del = http.delete(f"/collections/{col_a['id']}")
    assert r_del.status_code == 204, f"DELETE failed: {r_del.text}"

    # GET kb-1 → 404.
    r_get_a = http.get(f"/collections/{col_a['id']}")
    assert r_get_a.status_code == 404, (
        f"Expected 404 for deleted org-A collection, got {r_get_a.status_code}"
    )

    # GET kb-2 → 200 (org-B unaffected).
    r_get_b = http.get(f"/collections/{col_b['id']}")
    assert r_get_b.status_code == 200, (
        f"org-B collection should still exist, got {r_get_b.status_code}"
    )
    assert r_get_b.json()["id"] == col_b["id"]

    # org-A's storage dir must be gone.
    assert not dir_a.exists(), (
        f"org-A storage dir should be deleted but still exists: {dir_a}"
    )

    # org-B's storage dir must still exist.
    assert dir_b.exists(), (
        f"org-B storage dir should still exist but is gone: {dir_b}"
    )


@pytest.mark.e2e
def test_concurrent_orgs_no_id_collision(
    http: httpx.Client, docker_stack: dict, kb_server_process: dict
) -> None:
    """Five orgs each creating a collection named 'shared-name' all succeed.

    Each collection must receive a unique server-generated ID. Uses a
    ThreadPoolExecutor to issue creates concurrently, verifying that the
    server's ID-generation has no collision under concurrent load.
    """
    ollama_url = docker_stack["ollama_url"]
    orgs = [_org_id() for _ in range(5)]

    def _create(org_id: str) -> dict:
        return _create_collection(
            http, org_id, "shared-name", api_endpoint=ollama_url
        )

    # ThreadPoolExecutor for concurrent HTTP requests.
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_create, org): org for org in orgs}
        for future in as_completed(futures):
            results.append(future.result())

    assert len(results) == 5, f"Expected 5 created collections, got {len(results)}"

    # All collections must have unique IDs.
    ids = [r["id"] for r in results]
    assert len(set(ids)) == 5, f"ID collision detected: {ids}"

    # Each collection must have the correct name.
    for r in results:
        assert r["name"] == "shared-name"

    # Each org appears exactly once.
    org_ids_returned = {r["organization_id"] for r in results}
    assert org_ids_returned == set(orgs), (
        f"Org IDs mismatch: expected {set(orgs)}, got {org_ids_returned}"
    )
