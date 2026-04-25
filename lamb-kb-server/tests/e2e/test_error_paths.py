"""E2E error-path tests — table-driven over real HTTP.

Each test hits a real uvicorn subprocess (the session-scoped ``kb_server_process``
fixture from conftest.py) and asserts the correct HTTP status code plus that the
response body matches the ``ErrorResponse`` shape from ``schemas/common.py``
(i.e., ``{"detail": "<message>"}``) or FastAPI's 422 validation error shape
(``{"detail": [...]}``) where applicable.

**Embedding vendor in helpers:** The e2e subprocess does NOT register the
``FakeEmbedding`` test double — that is only available in unit/integration tiers.
We use ``ollama`` with a dummy endpoint for error-path tests that only need a
collection to *exist* (they fail before any embedding is invoked).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

_KB_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_org() -> str:
    return f"org-{uuid4().hex[:8]}"


def _minimal_collection_payload(
    org_id: str | None = None,
    name: str | None = None,
    *,
    chunking_strategy: str = "simple",
    embedding_vendor: str = "ollama",
    embedding_model: str = "nomic-embed-text",
    embedding_endpoint: str = "http://127.0.0.1:19999",  # unreachable — not called
    vector_db_backend: str = "chromadb",
) -> dict:
    """Build a minimal CreateCollectionRequest payload.

    Defaults use ``ollama`` with an intentionally unreachable endpoint because
    error-path tests that only create/list/delete collections never actually
    invoke the embedding backend.  The endpoint will not be contacted.
    """
    return {
        "organization_id": org_id or _unique_org(),
        "name": name or f"test-{uuid4().hex[:8]}",
        "chunking_strategy": chunking_strategy,
        "embedding": {
            "vendor": embedding_vendor,
            "model": embedding_model,
            "api_endpoint": embedding_endpoint,
        },
        "vector_db_backend": vector_db_backend,
    }


def _create_collection(http: httpx.Client, **kwargs) -> dict:
    """POST /collections with a minimal payload; assert 201 and return body."""
    payload = _minimal_collection_payload(**kwargs)
    r = http.post("/collections", json=payload)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    return r.json()


def _assert_error_response(body: dict) -> None:
    """Assert the body conforms to ErrorResponse: ``{"detail": <str or list>}``.

    FastAPI uses ``{"detail": "..."}`` for HTTPExceptions and
    ``{"detail": [...]}`` for Pydantic 422 validation errors.  Both are valid
    ``ErrorResponse``-compatible shapes — the outer key must be ``"detail"``.
    """
    assert "detail" in body, f"Missing 'detail' key in error body: {body}"


# ---------------------------------------------------------------------------
# 400 — Bad request (unknown plugin names)
# ---------------------------------------------------------------------------


def test_400_unknown_chunking_strategy(http: httpx.Client) -> None:
    """POST /collections with an unregistered chunking_strategy returns 400."""
    payload = _minimal_collection_payload(chunking_strategy="bogus_strategy")
    r = http.post("/collections", json=payload)

    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)
    assert "bogus_strategy" in body["detail"].lower() or "chunking" in body["detail"].lower(), (
        f"Error detail should mention the bad strategy name: {body['detail']}"
    )


def test_400_unknown_embedding_vendor(http: httpx.Client) -> None:
    """POST /collections with an unregistered embedding vendor returns 400."""
    payload = _minimal_collection_payload(embedding_vendor="definitely_fake_vendor_xyz")
    r = http.post("/collections", json=payload)

    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)
    assert (
        "definitely_fake_vendor_xyz" in body["detail"].lower()
        or "embedding" in body["detail"].lower()
    ), f"Error detail should mention the bad vendor: {body['detail']}"


def test_400_unknown_vector_db_backend(http: httpx.Client) -> None:
    """POST /collections with an unregistered vector_db_backend returns 400."""
    payload = _minimal_collection_payload(vector_db_backend="nonexistent_backend")
    r = http.post("/collections", json=payload)

    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)
    assert (
        "nonexistent_backend" in body["detail"].lower()
        or "vector" in body["detail"].lower()
        or "backend" in body["detail"].lower()
    ), f"Error detail should mention the bad backend: {body['detail']}"


# ---------------------------------------------------------------------------
# 400 / 422 — empty documents list in add-content
# ---------------------------------------------------------------------------


def test_400_or_422_empty_documents_in_add_content(http: httpx.Client) -> None:
    """POST /collections/{id}/add-content with documents=[] returns 400 or 422.

    ``AddContentRequest`` declares ``min_length=1`` on the ``documents`` field
    and a ``@model_validator`` that also rejects empty lists.  Pydantic raises
    the error before the route handler runs, so FastAPI converts it to 422.
    Both 400 and 422 are acceptable outcomes for this validation guard.
    """
    coll = _create_collection(http)
    coll_id = coll["id"]

    r = http.post(f"/collections/{coll_id}/add-content", json={"documents": []})

    assert r.status_code in (400, 422), (
        f"Expected 400 or 422 for empty documents, got {r.status_code}: {r.text}"
    )
    body = r.json()
    _assert_error_response(body)


# ---------------------------------------------------------------------------
# 401 — Authentication failures
# ---------------------------------------------------------------------------


def test_401_missing_auth(kb_server_process: dict) -> None:
    """GET /collections with no Authorization header returns 401 or 403.

    FastAPI's ``HTTPBearer`` returns 403 when the scheme is absent because it
    treats a missing Authorization header as a forbidden request (auto_error
    behavior).  Both codes correctly indicate unauthenticated access.
    """
    with httpx.Client(base_url=kb_server_process["base_url"], timeout=10.0) as client:
        r = client.get("/collections")

    assert r.status_code in (401, 403), (
        f"Expected 401 or 403 without auth, got {r.status_code}: {r.text}"
    )
    body = r.json()
    _assert_error_response(body)


def test_401_invalid_token(kb_server_process: dict) -> None:
    """GET /collections with a wrong bearer token returns 401."""
    bad_headers = {"Authorization": "Bearer this-is-totally-wrong"}
    with httpx.Client(
        base_url=kb_server_process["base_url"],
        headers=bad_headers,
        timeout=10.0,
    ) as client:
        r = client.get("/collections")

    assert r.status_code == 401, (
        f"Expected 401 for invalid token, got {r.status_code}: {r.text}"
    )
    body = r.json()
    _assert_error_response(body)


# ---------------------------------------------------------------------------
# 404 — Resource not found
# ---------------------------------------------------------------------------


def test_404_collection_not_found_get(http: httpx.Client) -> None:
    """GET /collections/{nonexistent-id} returns 404."""
    r = http.get("/collections/nonexistent-collection-uuid")

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_404_collection_not_found_put(http: httpx.Client) -> None:
    """PUT /collections/{nonexistent-id} returns 404."""
    r = http.put("/collections/nonexistent-collection-uuid", json={"name": "new-name"})

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_404_collection_not_found_delete(http: httpx.Client) -> None:
    """DELETE /collections/{nonexistent-id} returns 404."""
    r = http.delete("/collections/nonexistent-collection-uuid")

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_404_collection_not_found_add_content(http: httpx.Client) -> None:
    """POST /collections/{nonexistent-id}/add-content returns 404."""
    payload = {
        "documents": [
            {
                "source_item_id": "src-1",
                "title": "Test doc",
                "text": "Hello world",
            }
        ]
    }
    r = http.post("/collections/nonexistent-collection-uuid/add-content", json=payload)

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_404_collection_not_found_query(http: httpx.Client) -> None:
    """POST /collections/{nonexistent-id}/query returns 404."""
    payload = {"query_text": "some query", "top_k": 3}
    r = http.post("/collections/nonexistent-collection-uuid/query", json=payload)

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_404_collection_not_found_delete_source(http: httpx.Client) -> None:
    """DELETE /collections/{nonexistent-id}/content/{source-id} returns 404."""
    r = http.delete("/collections/nonexistent-collection-uuid/content/source-item-abc")

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_404_job_not_found(http: httpx.Client) -> None:
    """GET /jobs/{nonexistent-id} returns 404."""
    r = http.get("/jobs/nonexistent-job-id-xyz")

    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


# ---------------------------------------------------------------------------
# 409 — Conflict (duplicate collection name)
# ---------------------------------------------------------------------------


def test_409_duplicate_collection_name(http: httpx.Client) -> None:
    """Creating two collections with the same name in the same org returns 409."""
    org_id = _unique_org()
    name = f"duplicate-test-{uuid4().hex[:6]}"

    # First creation must succeed.
    first = _create_collection(http, org_id=org_id, name=name)
    assert first["name"] == name

    # Second creation with same (org_id, name) must conflict.
    payload = _minimal_collection_payload(org_id=org_id, name=name)
    r = http.post("/collections", json=payload)

    assert r.status_code == 409, f"Expected 409 for duplicate name, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)
    assert name in body["detail"] or "already exists" in body["detail"].lower(), (
        f"Error detail should mention the duplicate name: {body['detail']}"
    )


# ---------------------------------------------------------------------------
# 413 — Payload too large
#
# The default MAX_REQUEST_SIZE_BYTES is 200 MB — far too large to test by
# actually sending an oversized body.  Instead, we spin up a fresh short-lived
# KB server subprocess with MAX_REQUEST_SIZE_BYTES=2048 (2 KB) and send a
# request whose Content-Length header exceeds that limit.  The server checks
# the header before parsing the body, so we only need to supply a small body
# and set an inflated Content-Length.
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(base_url: str, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def small_limit_server():
    """Spin up a KB server with MAX_REQUEST_SIZE_BYTES=2048 for 413 tests.

    This fixture is module-scoped so the subprocess is created once per module
    run and torn down when the module finishes.
    """
    port = _free_port()
    data_dir = tempfile.mkdtemp(prefix="kbs-413-")
    env = os.environ.copy()
    env.update(
        {
            "LAMB_API_TOKEN": "test-token",
            "DATA_DIR": data_dir,
            "PORT": str(port),
            "LOG_LEVEL": "INFO",
            "MAX_REQUEST_SIZE_BYTES": "2048",  # 2 KB — tiny, for 413 testing
            "MAX_CONCURRENT_INGESTIONS": "1",
            "INGESTION_TASK_TIMEOUT_SECONDS": "30",
            "VECTOR_DB_QDRANT": "ENABLE",
            "EMBEDDING_LOCAL": "DISABLE",
            "QDRANT_URL": "",
        }
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--app-dir",
            str(_KB_ROOT / "backend"),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(_KB_ROOT),
    )

    base_url = f"http://127.0.0.1:{port}"
    if not _wait_for_health(base_url, timeout=30):
        proc.terminate()
        out = proc.stdout.read().decode() if proc.stdout else ""
        pytest.fail(f"Small-limit KB server failed to start:\n{out[-2000:]}")

    info = {
        "base_url": base_url,
        "port": port,
        "data_dir": data_dir,
        "process": proc,
    }

    yield info

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    shutil.rmtree(data_dir, ignore_errors=True)


def test_413_payload_exceeds_limit(small_limit_server: dict) -> None:
    """POST /collections/{id}/add-content with a body > 2048 bytes returns 413.

    We spin up a KB server with MAX_REQUEST_SIZE_BYTES=2048 (via the
    ``small_limit_server`` fixture).  We then construct a real JSON payload
    that exceeds 2048 bytes by padding the document text with spaces.  The
    server reads the ``Content-Length`` header before parsing the body and
    returns 413 when it is exceeded.

    httpx / h11 enforce that the actual body matches the declared
    Content-Length, so we must send a real over-limit payload rather than
    just spoofing the header.
    """
    auth_headers = {"Authorization": "Bearer test-token"}
    base_url = small_limit_server["base_url"]

    # Create a collection — the create payload is tiny and well under 2 KB.
    create_payload = _minimal_collection_payload()
    with httpx.Client(base_url=base_url, headers=auth_headers, timeout=15.0) as client:
        r = client.post("/collections", json=create_payload)
        assert r.status_code == 201, f"Collection creation failed: {r.status_code} {r.text}"
        coll_id = r.json()["id"]

        # Build an add-content payload whose body is deliberately > 2048 bytes.
        # We pad the document text with enough spaces to push the JSON over the limit.
        padding = " " * 3000  # 3000 extra bytes in the text field
        oversized_payload = {
            "documents": [
                {
                    "source_item_id": "src-big",
                    "title": "Big doc",
                    "text": f"Hello world{padding}",
                }
            ]
        }

        r413 = client.post(
            f"/collections/{coll_id}/add-content",
            json=oversized_payload,
        )

    assert r413.status_code == 413, (
        f"Expected 413 for oversized payload, got {r413.status_code}: {r413.text}"
    )
    body = r413.json()
    _assert_error_response(body)


# ---------------------------------------------------------------------------
# 422 — Pydantic validation failures
# ---------------------------------------------------------------------------


def test_422_invalid_request_body_type_top_k_negative(http: httpx.Client) -> None:
    """POST /collections/{id}/query with top_k=-1 returns 422 (ge=1 violated)."""
    coll = _create_collection(http)
    coll_id = coll["id"]

    r = http.post(
        f"/collections/{coll_id}/query",
        json={"query_text": "hello", "top_k": -1},
    )

    assert r.status_code == 422, f"Expected 422 for top_k=-1, got {r.status_code}: {r.text}"
    body = r.json()
    _assert_error_response(body)


def test_422_invalid_top_k_too_large(http: httpx.Client) -> None:
    """POST /collections/{id}/query with top_k=1000 returns 422 (le=100 violated)."""
    coll = _create_collection(http)
    coll_id = coll["id"]

    r = http.post(
        f"/collections/{coll_id}/query",
        json={"query_text": "hello", "top_k": 1000},
    )

    assert r.status_code == 422, (
        f"Expected 422 for top_k=1000 (exceeds max=100), got {r.status_code}: {r.text}"
    )
    body = r.json()
    _assert_error_response(body)


def test_422_missing_required_field_name(http: httpx.Client) -> None:
    """POST /collections without ``name`` (required field) returns 422."""
    org_id = _unique_org()
    # Deliberately omit the required ``name`` field.
    payload = {
        "organization_id": org_id,
        "chunking_strategy": "simple",
        "embedding": {
            "vendor": "ollama",
            "model": "nomic-embed-text",
        },
        "vector_db_backend": "chromadb",
    }
    r = http.post("/collections", json=payload)

    assert r.status_code == 422, (
        f"Expected 422 for missing 'name' field, got {r.status_code}: {r.text}"
    )
    body = r.json()
    _assert_error_response(body)


# ---------------------------------------------------------------------------
# 503 — Backend unavailable
#
# Testing 503 in the e2e tier is hard without modifying live server state
# because it requires the vector DB registry to return None at *query time*,
# which would require restarting the session-scoped server with a different
# env var.  The 503 path is covered exhaustively in the integration tier
# (test_query.py) where monkeypatching the registry is straightforward via
# ASGI in-process transport.
#
# We mark this test as skipped with a clear explanation rather than omitting
# it, so the intent is documented and the skip appears in the test report.
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "503 (backend unavailable) cannot be triggered in the e2e tier without "
        "restarting the session-scoped server with VECTOR_DB_CHROMADB=DISABLE, "
        "which would break all other e2e tests sharing that server.  "
        "This path is covered in tests/integration/test_query.py via "
        "monkeypatching the VectorDBRegistry after collection creation."
    )
)
def test_503_backend_unavailable(http: httpx.Client) -> None:
    """503 is an integration-tier-only test — see skip reason above."""
    pass  # pragma: no cover
