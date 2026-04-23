# LAMB Library Manager

Document repository microservice for the [LAMB](https://github.com/Lamb-Project) platform. Imports documents into a structured, permalinkable markdown format that can later be consumed by the KB Server for chunking and embedding.

**Terminology:** The Library Manager **imports** content (converts documents into a structured repository). The KB Server **ingests** content (chunks, embeds, and stores vectors). These are distinct operations — this service only handles the first.

## What it does

- **Imports documents** from files (PDF, DOCX, PPTX, XLSX, HTML, TXT, MD, etc.), URLs (via Firecrawl), and YouTube videos (via yt-dlp)
- **Converts to a common format:** every imported document produces `metadata.json` + `source_ref.json` + original file + extracted markdown (`full.md`) + per-page breakdown + extracted images
- **Serves content** via API — full markdown, individual pages, images, original files, metadata
- **Generates stable permalinks** for every piece, used for citation in RAG results
- **Manages libraries** — multiple named libraries per organization, each containing imported items
- **Exports/imports** libraries as ZIP files for portability

## What it does NOT do

- Chunk, embed, or store vectors (KB Server's responsibility)
- Enforce user-level access control (LAMB handles ACL and sends pre-authorized requests)
- Manage organizations, users, or assistants (LAMB's responsibility)

## Architecture

The Library Manager is one of three services in the LAMB platform:

```
LAMB Backend (orchestrator, ACL, RAG) ──► Library Manager (this service)
                                      ──► KB Server (chunking, embedding, vector search)
```

LAMB initiates all requests. The Library Manager trusts requests authenticated with the service bearer token (`LAMB_API_TOKEN`). It runs on an isolated Docker network with no published ports.

### Async processing

File imports are processed asynchronously:

1. The API accepts an upload and returns immediately with `{ item_id, job_id, status: "processing" }`.
2. Jobs are persisted to SQLite (`import_jobs` table) so they survive service restarts.
3. An async worker loop polls for pending jobs and processes them in a thread pool.
4. Concurrency is controlled by a semaphore (`MAX_CONCURRENT_IMPORTS`, default: 3).
5. API keys received in the request are held in memory for the job duration and then discarded — never persisted to disk.

### Plugin system

Each source type (file, URL, YouTube) is handled by a pluggable import plugin. Plugins receive a source and produce an `ImportResult` containing full markdown text, optional per-page breakdown, optional extracted images, and metadata. All plugins converge to the same structured disk format regardless of source type.

| Plugin | Sources | Notes |
|--------|---------|-------|
| `simple_import` | .txt, .md, .html | Direct text read, no conversion |
| `markitdown_import` | .pdf, .docx, .pptx, .xlsx, + more | MarkItDown conversion to markdown |
| `markitdown_plus_import` | Same as above | Enhanced: image extraction + optional LLM descriptions via OpenAI Vision |
| `url_import` | URLs | Web crawling via Firecrawl |
| `youtube_transcript_import` | YouTube URLs | Transcript download via yt-dlp |

Plugins can be disabled or put in simplified mode via environment variables: `PLUGIN_<NAME>=DISABLE|SIMPLIFIED|ADVANCED`.

### Structured content format

Every imported document is stored on disk as:

```
data/content/{org_id}/{library_id}/{item_id}/
├── metadata.json           # Title, source, permalinks, import plugin, etc.
├── source_ref.json         # Original source reference (file/url/youtube)
├── original/               # Original document (hosted copy)
│   └── document.pdf
└── content/
    ├── full.md             # Full extracted markdown
    ├── pages/              # Per-page breakdown (if applicable)
    │   ├── page_001.md
    │   └── page_002.md
    └── images/             # Extracted images
        └── img_001.png
```

Permalink URLs follow the pattern `/docs/{org}/{lib}/{item}/content/full.md` and are served through LAMB's reverse proxy with ACL enforcement.

## Development

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
```

### Running locally

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set LAMB_API_TOKEN at minimum

cd backend
LAMB_API_TOKEN=your-token uvicorn main:app --host 0.0.0.0 --port 9091 --reload
```

### Running tests

```bash
pytest tests/ -v
```

Tests use an in-process ASGI client (httpx + FastAPI) with a temporary SQLite database. No external services are required — the YouTube test uses a live video with reliable subtitles, and the URL import test verifies the error path since Firecrawl is not available in the test environment.

### Docker

```bash
docker build -t lamb-library-manager .
docker run -p 9091:9091 -e LAMB_API_TOKEN=your-token lamb-library-manager
```

## API overview

All endpoints except `/health` require `Authorization: Bearer {LAMB_API_TOKEN}`.

| Group | Endpoints |
|-------|-----------|
| System | `GET /health`, `GET /plugins` |
| Libraries | `POST /libraries`, `GET /libraries/{id}`, `DELETE /libraries/{id}`, `GET /libraries?organization_id=`, `GET/PUT /libraries/{id}/import-config` |
| Importing | `POST /libraries/{id}/import/file`, `POST /libraries/{id}/import/url`, `POST /libraries/{id}/import/youtube` |
| Content | `GET /libraries/{id}/items`, `GET /libraries/{id}/items/{item_id}`, `GET .../content`, `GET .../content/pages/{page}`, `GET .../content/images/{img}`, `GET .../original/{filename}`, `GET .../metadata`, `GET .../source_ref`, `GET .../status`, `DELETE .../items/{item_id}` |
| Export/Import | `GET /libraries/{id}/export`, `POST /libraries/import?organization_id=` |

Full OpenAPI spec available at `http://localhost:9091/docs` when the service is running.

## Configuration

All configuration is via environment variables (see `backend/.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LAMB_API_TOKEN` | *(required)* | Bearer token for authenticating requests from LAMB |
| `PORT` | `9091` | Server port |
| `DATA_DIR` | `data` | Base directory for SQLite DB and content files |
| `MAX_CONCURRENT_IMPORTS` | `3` | Max parallel import jobs |
| `IMPORT_TASK_TIMEOUT_SECONDS` | `600` | Timeout per import job |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PERMALINK_PREFIX` | `/docs` | URL prefix for permalinks in metadata.json |
| `PLUGIN_<NAME>` | `ADVANCED` | Per-plugin governance: `DISABLE`, `SIMPLIFIED`, or `ADVANCED` |

## Database

SQLite with WAL mode (`data/library-manager.db`). Tables:

| Table | Purpose |
|-------|---------|
| `organizations` | Lightweight org records (LAMB is source of truth) |
| `libraries` | Named document repositories within organizations |
| `content_items` | Imported documents with status, metadata, permalinks |
| `content_images` | Extracted images linked to content items |
| `import_jobs` | Persistent job queue for async processing |

Tables are created automatically on first startup via SQLAlchemy `create_all`.
