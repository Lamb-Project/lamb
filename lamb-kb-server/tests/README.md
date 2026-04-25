# Test suite

Three tiers, each with its own scope, fixtures, and runtime profile. The combined run hits **99% line + branch coverage** on `backend/`.

| Tier | Where | Tests | Runtime | What it proves |
|---|---|---|---|---|
| Unit | `tests/unit/` | ~330 | ~16s | Every module's pure logic — chunking, embedding URL normalization, plugin registry, schemas, services driven directly with no FastAPI app and no HTTP layer. |
| Integration | `tests/integration/` | ~178 | ~110s | Routers, async worker concurrency / timeout / recovery, request-logging middleware, lifespan startup/shutdown — exercised via in-process ASGI (`httpx.AsyncClient(transport=ASGITransport(app))`) with the real worker, real SQLite, real ChromaDB. |
| E2E | `tests/e2e/` | ~61 | ~150s | Full stack via real HTTP (loopback TCP to a uvicorn subprocess) + real Ollama embeddings + real Qdrant + real ChromaDB. Tests crash recovery (SIGKILL+restart), graceful shutdown, multi-tenant isolation, concurrency back-pressure, and the entire HTTP error-code matrix. |

## Running

```bash
./scripts/run_tests.sh                # all three tiers + combined ≥95% gate
pytest tests/unit/        -q
pytest tests/integration/ -q
pytest tests/e2e/         -q
pytest -m "not slow" tests/           # skip the sentence-transformers download + heavy e2e
```

## Fixture map

### Root `tests/conftest.py`
Session-wide setup that runs before any tier loads:
- Creates a tempdir for `DATA_DIR`.
- Sets `LAMB_API_TOKEN=test-token`, restricts `MAX_REQUEST_SIZE_BYTES=2048` (so 413 is reachable cheaply), `MAX_CONCURRENT_INGESTIONS=2`, disables optional plugins (`EMBEDDING_LOCAL`, `VECTOR_DB_QDRANT`).
- Force-registers `FakeEmbedding` (deterministic SHA-256-based 16-D vector — identical text → identical vector → cosine 1.0). Lives in `tests/_fakes.py`.
- Auto-tags every test with its tier marker via `pytest_collection_modifyitems` so `pytest -m unit` works without manual decoration.

### `tests/_helpers.py`
- `AUTH_HEADERS` — `{"Authorization": "Bearer test-token"}`.
- `poll_job(client, job_id, timeout=20.0, interval=0.2)` — async polling helper.

### `tests/unit/conftest.py`
- `tmp_storage` — per-test tempdir for vector DB persistence.
- `fake_embedding` — shared `FakeEmbedding` instance.
- `db_session` — direct SQLAlchemy session (no HTTP layer).

### `tests/integration/conftest.py`
- `client` — ASGI `AsyncClient` with worker started/stopped per test.
- `client_no_worker` — ASGI client without auto-starting the worker (for tests that drive it manually).
- `org_id` — unique per-test org id.
- `collection` — pre-created chromadb+fake collection.

### `tests/e2e/conftest.py`
- `docker_stack` (session) — brings up Qdrant + Ollama via `docker-compose.test.yml` (or auto-discovers a pre-started stack if `QDRANT_TEST_PORT` and `OLLAMA_TEST_PORT` are exported).
- `kb_server_process` (session) — launches `uvicorn` in a subprocess on a free port with `LOG_LEVEL=DEBUG` (exposes `/docs` and `/openapi.json`).
- `http` — `httpx.Client` against the running server with auth headers.

## Design rules

- **Tests hit real systems.** No mocking of the system under test. ChromaDB runs in-process with a tempdir; Qdrant local-mode runs on disk; Ollama runs in a real container; SQLite is real with WAL mode. The only mocks are at boundaries: external embedding APIs are mocked at the wrapper class boundary so the URL-normalization code path is still exercised.
- **No reliance on test ordering.** Each test generates a unique `org_id` (UUID hex) and uses its own `data_dir` where applicable. Force-registered plugins are popped in `try/finally`.
- **Asynchronous code is exercised end-to-end.** The async ingestion worker really runs in tests — `start_worker()` per test, real polling loop, real semaphore, real timeout handling. Tests for stale-job recovery directly insert `processing` rows and call `recover_stale_jobs()`.

## Real bugs the suite caught

The new test tier surfaced several latent issues in the source as it was written:

1. **`qdrant_backend.py` used `client.search()`** — a method removed in `qdrant-client>=1.12`. The unit tier's roundtrip test failed against `qdrant-client==1.17`, leading to a one-line patch to use `client.query_points()`.
2. **Latin-1 decoded tokens crash with 500 instead of 401.** Sending `Authorization: Bearer test-tok\xe9n` raw bytes is decoded as Latin-1 by Starlette; `hmac.compare_digest` then raises `TypeError` on non-ASCII strings. Documented as a regression guard in `tests/e2e/test_auth_boundary.py::test_token_with_multibyte_utf8_difference`.
3. **`extra_metadata` with `None` or nested dicts silently passes schema validation but crashes at the ChromaDB layer.** The schema `dict[str, Any]` is too permissive; Pydantic accepts but the storage layer rejects with a `TypeError`. Documented in `tests/integration/test_edge_cases.py::test_extra_metadata_none_value_causes_job_failure` and `..._nested_dict_causes_job_failure`.
4. **`collection.chunk_count` is a read-modify-write counter** with no row-level locking. Under 20 concurrent ingestion jobs it underreports. Vector data itself is correct. Documented in `tests/e2e/test_concurrency.py`.
5. **Server stdout pipe deadlock.** With `LOG_LEVEL=DEBUG` and active ingestion, a parent process that captures stdout via `subprocess.PIPE` without draining will fill the 64KB Linux pipe buffer and block the asyncio loop. The e2e fixture works around this with a daemon stdout-drain thread.

## CI / coverage

`scripts/run_tests.sh` runs each tier separately (passing tests required), then a final combined run with `--cov-fail-under=95`. Subprocess-side coverage instrumentation for the e2e tier is not enabled — measure-by-tier on e2e isn't reliable with the current `pytest-cov` plumbing. The combined coverage gate is the meaningful number; per-tier passing is the meaningful per-tier signal.

## Following up

- Add a regression-guard test for the silent `chunking_params` key-typo issue (`{"overlap": 10}` is silently ignored; the correct key is `chunk_overlap`).
- Mutation testing: `mutmut` is wired up in `pyproject.toml` but its auto test-discovery in `mutmut>=3` doesn't match the tiered class-based test layout; running it productively requires a different approach.
- Pin `ollama/ollama:latest` in `docker-compose.test.yml` to a specific tag for reproducibility.
