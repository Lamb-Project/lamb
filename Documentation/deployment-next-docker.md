# Docker Next Deployment Guide

This guide explains how to deploy the new production-first Docker stack using:

- `docker-compose.next.yaml` (base stack)
- `docker-compose.next.prod.yaml` (optional Caddy/TLS overlay)
- `docker-compose.next.build.yaml` (optional local Open WebUI source build overlay)

## Goals

- Deploy with prebuilt images by default.
- Keep deployment simple with one root `.env` file.
- Avoid backend code changes in this phase.

## Important Temporary Decision

To avoid modifying `backend/` runtime code in this phase, some environment variables are intentionally required in `docker-compose.next.yaml`.

- Compose fails fast if these required variables are missing.
- This is a temporary compatibility decision.
- Future target: make these variables optional through image-backed/runtime defaults.

## Quick Start

Base stack (no TLS):

```bash
docker compose -f docker-compose.next.yaml up -d
```

Base + TLS reverse proxy:

```bash
docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml up -d
```

Base + local Open WebUI build:

```bash
docker compose -f docker-compose.next.yaml -f docker-compose.next.build.yaml up -d
```

With custom env overrides file:

```bash
docker compose -f docker-compose.next.yaml --env-file .env up -d
```

## Services and Volumes

Core services:

- `lamb` (`ghcr.io/lamb-project/lamb:latest`)
- `kb` (`ghcr.io/lamb-project/lamb-kb:latest`)
- `openwebui` (`ghcr.io/lamb-project/openwebui:latest`)

Optional service:

- `caddy` (`caddy:2.8`) via `docker-compose.next.prod.yaml`

Persistent volumes:

- `lamb-data` (LAMB SQLite and local app data)
- `kb-data` (KB storage)
- `kb-static` (KB static files)
- `openwebui-data` (Open WebUI DB + vector/cache)
- `caddy-data`, `caddy-config` (only with TLS overlay)

## Configurable Environment Variables

All variables below are configurable via shell env or a root `.env` file.

### LAMB and KB Variables (Complete)

| Variable | Scope | Default | Required | Description |
|---|---|---|---|---|
| `LAMB_PORT` | `lamb` | `9099` | No | Container port exposed by LAMB backend service. |
| `LAMB_WEB_HOST` | `lamb` | none | **Yes** | Public base URL used for browser-facing LAMB links. |
| `LAMB_BACKEND_HOST` | `lamb` | none | **Yes** | Internal backend URL for server-to-server requests. |
| `LAMB_DB_PATH` | `lamb` | none | **Yes** | Path inside container where LAMB DB is stored. |
| `LAMB_BEARER_TOKEN` | `lamb` | none | **Yes** | Main API bearer token for LAMB backend auth. |
| `LAMB_KB_SERVER` | `lamb` | `http://kb:9090` | No | Internal URL for KB service integration. |
| `LAMB_KB_SERVER_TOKEN` | `lamb` | `0p3n-w3bu!` | No (should override in prod) | Token used by LAMB to call KB service. |
| `OWI_BASE_URL` | `lamb` | none | **Yes** | Internal Open WebUI API base URL. |
| `OWI_PUBLIC_BASE_URL` | `lamb` | `http://localhost:8080` | No | Public Open WebUI URL for redirects/browser flows. |
| `OWI_PATH` | `lamb` | none | **Yes** | Mounted Open WebUI data path visible from LAMB container. |
| `OPENAI_API_KEY` | `lamb` | empty | No | API key for OpenAI provider calls. |
| `OPENAI_BASE_URL` | `lamb` | none | **Yes** | OpenAI-compatible API endpoint. |
| `OPENAI_MODEL` | `lamb` | none | **Yes** | Default main OpenAI model. |
| `OPENAI_MODELS` | `lamb` | `gpt-4o-mini,gpt-4o` | No | Comma-separated model list exposed by backend. |
| `OLLAMA_BASE_URL` | `lamb` | `http://host.docker.internal:11434` | No | Ollama endpoint for embedding/completion integrations. |
| `OLLAMA_MODEL` | `lamb` | `nomic-embed-text` | No | Default Ollama embedding model name. |
| `SIGNUP_ENABLED` | `lamb` | `true` | No | Enables/disables signup flow. |
| `SIGNUP_SECRET_KEY` | `lamb` | none | **Yes** | Secret used for signup token handling. |
| `LTI_SECRET` | `lamb` | `lamb-lti-secret-key-2024` | No (should override in prod) | Shared secret used by LTI integration. |
| `DEV_MODE` | `lamb` | `false` | No | Enables development-oriented backend behavior. |
| `GLOBAL_LOG_LEVEL` | `lamb` | `WARNING` | No | Base log level (`CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`). |
| `OWI_ADMIN_NAME` | `lamb` | none | **Yes** | Open WebUI bootstrap admin name required by backend config. |
| `OWI_ADMIN_EMAIL` | `lamb` | none | **Yes** | Open WebUI bootstrap admin email required by backend config. |
| `OWI_ADMIN_PASSWORD` | `lamb` | none | **Yes** | Open WebUI bootstrap admin password required by backend config. |
| `KB_PORT` | `kb` | `9090` | No | Port exposed by KB service. |
| `KB_HOME_URL` | `kb` | `http://localhost:9090` | No | Base URL used by KB for generated links. |
| `LAMB_API_KEY` | `kb` | `0p3n-w3bu!` | No (should override in prod) | KB API auth key. |
| `EMBEDDINGS_MODEL` | `kb` | `nomic-embed-text` | No | Default embeddings model for KB collections. |
| `EMBEDDINGS_VENDOR` | `kb` | `ollama` | No | Embedding provider (`ollama`, `local`, `openai`). |
| `EMBEDDINGS_ENDPOINT` | `kb` | `http://host.docker.internal:11434/api/embeddings` | No | Embeddings API endpoint used by KB. |
| `EMBEDDINGS_APIKEY` | `kb` | empty | No | Optional API key for embedding provider. |
| `FIRECRAWL_API_URL` | `kb` | `http://host.docker.internal:3002` | No | Firecrawl API endpoint for URL ingestion plugin. |
| `FIRECRAWL_API_KEY` | `kb` | empty | No | Optional Firecrawl API key. |

### OpenWebUI and Caddy Variables (Common)

This table lists the most common variables for OpenWebUI/Caddy. Advanced OpenWebUI knobs can be added later if needed.

| Variable | Scope | Default | Required | Description |
|---|---|---|---|---|
| `OPENWEBUI_PORT` | `openwebui` | `8080` | No | Port exposed by Open WebUI service. |
| `WEBUI_SECRET_KEY` | `openwebui` | empty | No (recommended in prod) | Open WebUI session/security secret. |
| `CADDY_EMAIL` | `caddy` (prod overlay) | `admin@yourdomain.com` | No | Email used by Caddy for ACME/TLS registration. |
| `LAMB_PUBLIC_HOST` | `caddy` (prod overlay) | `lamb.yourdomain.com` | No | Main public hostname routed to LAMB/KB endpoints. |
| `OWI_PUBLIC_HOST` | `caddy` (prod overlay) | `owi.lamb.yourdomain.com` | No | Public hostname routed to Open WebUI. |

## Recommended Production Overrides

At minimum, override these in production:

- `LAMB_BEARER_TOKEN`
- `LAMB_KB_SERVER_TOKEN`
- `LAMB_API_KEY`
- `SIGNUP_SECRET_KEY`
- `LTI_SECRET`
- `WEBUI_SECRET_KEY`
- `OPENAI_API_KEY` (if OpenAI is used)
- `LAMB_WEB_HOST`, `OWI_PUBLIC_BASE_URL`, `LAMB_PUBLIC_HOST`, `OWI_PUBLIC_HOST`

Also ensure these are explicitly set (required variables):

- `LAMB_BACKEND_HOST`
- `LAMB_DB_PATH`
- `OWI_BASE_URL`
- `OWI_PATH`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OWI_ADMIN_NAME`
- `OWI_ADMIN_EMAIL`
- `OWI_ADMIN_PASSWORD`

## Migration Notes (Legacy -> Next)

For existing installations, migrate data by mapping/copying current data into new named volumes:

- LAMB DB (`lamb_v4.db`) -> `lamb-data`
- Open WebUI data (`webui.db`, vector/cache) -> `openwebui-data`
- KB DB/vector data -> `kb-data`

No service-name aliasing is required in the new stack.
