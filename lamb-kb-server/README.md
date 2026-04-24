# LAMB KB Server

The **LAMB Knowledge Base Server** is a microservice that chunks, embeds, and stores vectors for the LAMB learning-assistant platform. It runs on port **9092** alongside the existing `lamb-kb-server-stable/` (port 9090) so both can coexist without migration pressure.

**Terminology.** Libraries **IMPORT** content. Knowledge Bases **INGEST** content. This service is the ingestion side: it receives already-imported text + permalinks from LAMB, chunks it, embeds the chunks, and serves similarity queries back.

## What it does

- Creates collections (knowledge bases) with locked store setup: chunking strategy + embedding vendor/model + vector DB backend.
- Accepts `add-content` requests from LAMB containing document text, permalink metadata, and embedding credentials. Processes them asynchronously via a persistent SQLite-backed job queue.
- Attaches permalink metadata to every chunk so query results can cite back to the exact source page.
- Exposes similarity search with permalink-enriched results.
- Isolates storage per organization at the filesystem level (`data/storage/{org_id}/{collection_id}/`).

## What it does NOT do

- **No user-level authentication or ACL.** LAMB owns access control; this service trusts the bearer token and processes whatever LAMB sends (ADR-6).
- **No calls to the Library Manager.** LAMB reads content from the Library Manager and delivers it to the KB server in a single request — the KB server never talks to the Library Manager directly (ADR-1).
- **No mutation of store setup after creation.** Chunking strategy, embedding model, and vector DB backend are immutable — changing them after vectors exist would make the collection inconsistent (ADR-3). Users who want different settings create a new KB.
- **No cross-collection query merging.** Multi-KB query merging happens in LAMB's RAG pipeline, not here.
- **No query rewriting.** The `context_aware_rag` processor in LAMB rewrites queries before sending them; the KB server embeds the query as-is (ADR-11).

## Architecture

```
┌──────────────┐   bearer token   ┌────────────────┐
│ LAMB backend │────────────────▶ │ LAMB KB Server │
│   (9099)     │   content + URL  │     (9092)     │
└──────────────┘                  └────────┬───────┘
                                           │
                                           ▼
                        ┌──────────────────────────────┐
                        │   Vector DB (Chroma|Qdrant)  │
                        │   data/storage/{org}/{kb}/   │
                        └──────────────────────────────┘
```

Only LAMB calls the KB server. Requests carry `Authorization: Bearer $LAMB_API_TOKEN`. The KB server refuses to start if the token is empty.

### Async processing

1. LAMB calls `POST /collections/{id}/add-content` with a list of documents and embedding credentials.
2. The server writes an ingestion job to SQLite (credentials are held in memory only) and returns a job ID.
3. A background worker pulls pending jobs, chunks each document using the collection's strategy, embeds the chunks with the provided credentials, and stores them in the collection's vector DB.
4. Credentials are discarded after the job completes.
5. LAMB polls `GET /jobs/{job_id}` for status.

On a crash, `processing` jobs are reset to `pending` at startup — unless they have exceeded the retry threshold, in which case they are marked `failed`.

### Plugin architecture

Three plugin families, each gated by simple `{CATEGORY}_{NAME}=ENABLE|DISABLE` env vars.

| Category | Plugins | Notes |
|----------|---------|-------|
| Vector DB | `chromadb` (default), `qdrant` (optional) | `qdrant` requires the `qdrant` extra |
| Chunking  | `simple`, `hierarchical`, `by_page`, `by_section` | All bundled by default |
| Embedding | `openai`, `ollama`, `local` (optional) | `local` requires the `local` extra (sentence-transformers) |

Optional plugins are skipped gracefully if their dependencies are missing — startup does not fail.

### Citations via permalink propagation

Every chunk's metadata carries the permalink URLs delivered by LAMB:

- `source_item_id` — the Library item the chunk came from
- `source_title` — display name for citations
- `permalink_original`, `permalink_markdown`, `permalink_page` — LAMB-scoped URLs

Query responses include these keys so the LAMB frontend can render clickable citation links.

## Development

### Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # minimal
pip install -e ".[all,dev]"        # with qdrant, local embeddings, openai SDK
```

### Running locally

```bash
cd backend
cp .env.example .env                # set LAMB_API_TOKEN
PORT=9092 uvicorn main:app --host 0.0.0.0 --port 9092 --reload
```

### Running tests

```bash
pytest tests/ -v
pytest tests/ --cov=backend --cov-report=term-missing
ruff check backend/ tests/
```

Tests use an in-process ASGI client (`httpx.AsyncClient(transport=ASGITransport(app))`) so no external server is required. ChromaDB runs in-process with a temporary storage directory per test session.

### Docker

```bash
docker build -t lamb-kb-server .
docker run -p 9092:9092 \
    -e LAMB_API_TOKEN=your-token \
    -v $(pwd)/data:/app/data \
    lamb-kb-server
```

## API overview

All endpoints except `GET /health` require `Authorization: Bearer $LAMB_API_TOKEN`.

| Group | Endpoints |
|-------|-----------|
| System | `GET /health`, `GET /backends`, `GET /chunking-strategies`, `GET /embedding-vendors` |
| Collections | `POST /collections`, `GET /collections`, `GET /collections/{id}`, `PUT /collections/{id}`, `DELETE /collections/{id}` |
| Content | `POST /collections/{id}/add-content`, `DELETE /collections/{id}/content/{source_item_id}` |
| Query | `POST /collections/{id}/query` |
| Jobs | `GET /jobs/{job_id}` |

OpenAPI docs at `/docs` are served only when `LOG_LEVEL=DEBUG`.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOST` | `0.0.0.0` | Uvicorn bind host |
| `PORT` | `9092` | Uvicorn bind port |
| `LOG_LEVEL` | `INFO` | Python logging level; `DEBUG` also enables `/docs` |
| `LAMB_API_TOKEN` | *(required)* | Bearer token LAMB sends |
| `DATA_DIR` | `data` | Root directory for SQLite DB + vector storage |
| `MAX_CONCURRENT_INGESTIONS` | `3` | Semaphore width for the worker |
| `INGESTION_TASK_TIMEOUT_SECONDS` | `1800` | Per-job timeout (30 min) |
| `MAX_REQUEST_SIZE_BYTES` | `209715200` | 200 MB cap on `add-content` bodies |
| `QDRANT_URL` | *(empty)* | Optional Qdrant endpoint (if using qdrant backend) |
| `QDRANT_API_KEY` | *(empty)* | Qdrant API key |
| `VECTOR_DB_*`, `CHUNKING_*`, `EMBEDDING_*` | `ENABLE` | Per-plugin kill-switches |

## Database

SQLite at `$DATA_DIR/kb-server.db`, WAL mode enabled at connection time. Two tables:

- `collections` — one row per KB (immutable store setup).
- `ingestion_jobs` — persistent queue (document text lives here until processed; credentials do not).

Schema is managed with `Base.metadata.create_all` (no Alembic migrations).

Per-org vector storage lives under `$DATA_DIR/storage/{organization_id}/{collection_id}/`.

## Security

- Service-level bearer token only; compared with `hmac.compare_digest`.
- No CORS middleware (not a browser-facing service).
- Runs as `appuser` (non-root) in the Docker image.
- Single-instance file lock prevents two server processes from sharing a data directory.
- Embedding credentials live in memory only; losing them on restart is intentional — the failed job is marked accordingly.
- Request-body size cap on `add-content` (returns 413 on overflow).

## ADRs (see issue #334)

- ADR-1: LAMB delivers content; KB server never calls Library Manager.
- ADR-2: Distinct port (9092) for coexistence with the stable server.
- ADR-3: `store_setup` is immutable — no content updates.
- ADR-4: Per-request embedding credentials, in-memory only.
- ADR-5: Query strategy is tied to chunking strategy.
- ADR-6: All ACL lives in LAMB.
- ADR-7: Polling for async processing (webhooks are a future improvement).
- ADR-8: Raw-score merging for multi-KB queries happens in LAMB.
- ADR-9: Per-org filesystem isolation.
- ADR-10: No artificial storage limits.
- ADR-11: Query rewriting stays in LAMB.
