# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LAMB (Learning Assistants Manager and Builder) is an open-source platform for educators to create AI-based learning assistants integrated with LMS (Moodle) via LTI. It features a no-code assistant builder, multi-model LLM support, RAG knowledge bases, multi-tenant organizations, and privacy-first design.

## Development Commands

### Starting the full stack (Docker Compose)
```bash
# Set LAMB_PROJECT_PATH in your shell or .env first
docker compose up          # all services
docker compose up backend  # just the backend (starts dependencies too)
docker compose up frontend # just the frontend dev server
```

### Running services individually (without Docker)
```bash
# Backend (FastAPI on port 9099)
cd backend && PORT=9099 uvicorn main:app --port 9099 --host 0.0.0.0 --forwarded-allow-ips '*' --reload

# Frontend dev server (Svelte on port 5173)
cd frontend/svelte-app && npm run dev -- --host 0.0.0.0

# KB Server (port 9090)
cd lamb-kb-server-stable/backend && uvicorn main:app --host 0.0.0.0 --port 9090 --reload
```

### Frontend (from `frontend/svelte-app/`)
```bash
npm run build        # production build
npm run check        # svelte-kit sync + svelte-check (type checking)
npm run lint         # prettier --check + eslint
npm run format       # prettier --write
npm run test:unit    # vitest
```

### Playwright E2E tests (from `testing/playwright/`)
```bash
# Copy .env.sample to .env and configure first
npm test                                            # all tests
npx playwright test tests/some_test.spec.js         # single test file
npx playwright test -g "test name"                  # single test by name
npm run test:headed                                 # visible browser
npm run test:ui                                     # interactive UI mode
npm run report                                      # view HTML report
```
Playwright config: 90s timeout per test, 10s assertion timeout, parallel disabled, global-setup handles auth via `.auth/state.json`.

### KB Server tests (from `lamb-kb-server-stable/backend/tests/`)
```bash
pytest                         # runs e2e/ test directory
pytest -m "not slow"           # skip slow tests
```

### Applying backend env changes in Docker
```bash
docker compose up -d backend   # recreate container (restart is NOT sufficient for .env changes)
```

## API Reference

The backend (FastAPI) auto-generates an OpenAPI spec at `http://localhost:9099/openapi.json`. When the server is running, this is the definitive source for all available endpoints, request/response schemas, and auth requirements.

## Architecture

### Dual API Layer
The backend runs a single FastAPI process (port 9099) with two API layers:

- **Creator Interface** (`/creator`) — user-facing API with auth, validation, file uploads. Acts as a proxy/enhancer to LAMB Core. Code in `backend/creator_interface/`.
- **LAMB Core** (`/lamb/v1`) — internal business logic, database ops, OpenAI-compatible completions API. Code in `backend/lamb/`.

Frontend requests hit `/creator`, which delegates to `/lamb/v1` internally.

### Services (ports)
| Service | Port | Purpose |
|---------|------|---------|
| Frontend (Svelte dev) | 5173 | SvelteKit dev server, proxies `/creator` and `/lamb` to backend |
| Backend (FastAPI) | 9099 | Main API server, also serves built frontend SPA in production |
| Open WebUI | 8080 | Chat interface for end-users, user session management |
| KB Server | 9090 | Knowledge base document ingestion, embedding, vector search |

### Completion Pipeline (plugin system)
Completions flow through a plugin pipeline in `backend/lamb/completions/`:
- **Connectors** (`connectors/`) — LLM providers: `openai.py`, `ollama.py`, `bypass.py`
- **RAG processors** (`rag/`) — `simple_rag.py`, `context_aware_rag.py`, `rubric_rag.py`, `single_file_rag.py`, `no_rag.py`
- **Prompt processors** (`pps/`) — message augmentation before LLM call

Plugin hooks: `before_completion` → `run_completion` → `after_completion`

### Multi-Tenancy
Organizations are the tenant boundary. Each org isolates users, assistants, KBs, and config. Roles: `owner`, `admin`, `member`. User types: `creator` (builds assistants) vs `end_user` (chat only, redirected to Open WebUI).

### Database
- **LAMB DB** — SQLite with WAL mode (`lamb_v4.db` at `LAMB_DB_PATH`). Schema managed in `backend/lamb/database_manager.py`.
- **Open WebUI DB** — `open-webui/backend/data/webui.db`. For historical reasons, Open WebUI is still the authentication provider — LAMB delegates user auth and session management to OWI. This is a known coupling targeted for refactoring (see GitHub issues).
- **ChromaDB** — vector store for KB embeddings, collections scoped per org+user.

### Frontend
Svelte 5 + SvelteKit + Vite + TailwindCSS 4. JavaScript with JSDoc (not TypeScript). I18n via `svelte-i18n` with locales in `frontend/svelte-app/src/lib/locales/` (en, es, ca, eu). API services in `frontend/svelte-app/src/lib/services/`. Reactive state in `frontend/svelte-app/src/lib/stores/`.

## Code Style

- **Python**: PEP 8. FastAPI with async/await.
- **Frontend**: JavaScript with JSDoc comments, not TypeScript. Prettier + ESLint + Svelte plugin. TailwindCSS for styling.

## Key Configuration

- Backend env: `backend/.env` (copy from `backend/.env.example`)
- KB Server env: `lamb-kb-server-stable/backend/.env` (copy from `.env.example`)
- Playwright env: `testing/playwright/.env` (copy from `.env.sample`)
- Frontend runtime config: `frontend/svelte-app/static/config.js` (copy from `config.js.sample`)
- Docker orchestration: `docker-compose.yaml` (requires `LAMB_PROJECT_PATH` env var)
- Reverse proxy: `Caddyfile`

## Vendored Dependencies — Do Not Modify

`open-webui/` and `lamb-kb-server-stable/` are separate projects maintained in their own repositories. They are included here only as stable snapshots so Docker Compose can launch them alongside LAMB. **Do not edit code in these directories** — changes belong in their upstream repos. The `frontend/build/` directory is build output. All three are excluded from search via `.cursorignore`.

## Version Bumping

Dev version lives in `frontend/svelte-app/scripts/generate-version.js`. Run `node frontend/svelte-app/scripts/generate-version.js` to regenerate `src/lib/version.js`. Only commit the generator script change, not the generated file.
