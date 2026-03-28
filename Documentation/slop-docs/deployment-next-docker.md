# Docker Next Deployment Guide

This guide explains how to deploy the new production-first Docker stack using:

- `docker-compose.next.yaml` (base stack)
- `docker-compose.next.prod.yaml` (optional Caddy/TLS overlay)
- Local source builds are supported directly from `docker-compose.next.yaml` via per-service `build` definitions.

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

Build images from local source:

```bash
docker compose -f docker-compose.next.yaml build
```

Base + local inference with optional Ollama profile:

```bash
docker compose -f docker-compose.next.yaml --profile ollama up -d
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
- `ollama` (`ollama/ollama:latest`) via `--profile ollama`

Startup readiness note:

- `openwebui` includes a healthcheck (`/health`), and `lamb` waits for `openwebui` to become healthy before starting.
- On first boot, this avoids most early login race errors while OpenWebUI initializes.

Persistent volumes:

- `lamb-data` (LAMB SQLite and local app data)
- `kb-data` (KB storage)
- `kb-static` (KB static files)
- `openwebui-data` (Open WebUI DB + vector/cache)
- `ollama-data` (Ollama models cache)
- `caddy-data`, `caddy-config` (only with TLS overlay)

## Configurable Environment Variables

All variables below can be set via shell env or root `.env` file.

Conventions:
- Envars in **bold** are currently required because there is no effective fallback default at runtime.
- "Where default is set" can be `docker-compose.next.yaml`, `backend/docker-entrypoint.py`, `backend/config.py`, or `.env.next.example` (example override only).

### `lamb` service

| Envar | Default value | Where default value is set | Description / Notes |
|---|---|---|---|
| `LAMB_PORT` | `9099` | `docker-compose.next.yaml` | Container port for lamb service. |
| **`LAMB_WEB_HOST`** | none | required in `docker-compose.next.yaml` | Public LAMB URL for browser flows. Also used by frontend runtime fallback (`LAMB_FRONTEND_LAMB_SERVER`). |
| **`LAMB_BACKEND_HOST`** | none | required in `docker-compose.next.yaml` | Internal backend URL for server-side requests. |
| **`LAMB_BEARER_TOKEN`** | none | required in `docker-compose.next.yaml` | Main backend bearer token (security-sensitive). |
| **`LAMB_DB_PATH`** | none | required in `docker-compose.next.yaml` | Filesystem path containing `lamb_v4.db`. |
| `LAMB_DB_PREFIX` | `LAMB_` | `backend/config.py` (consumed by `backend/lamb/database_manager.py`) | Optional override. Set empty (`""`) for unprefixed schemas (`Creator_*`); keep `LAMB_` for legacy prefixed schemas (`LAMB_*`). |
| `LAMB_KB_SERVER` | `http://kb:9090` | `docker-compose.next.yaml` | KB service URL consumed by lamb. Shared with `kb` service connectivity. |
| `LAMB_KB_SERVER_TOKEN` | `0p3n-w3bu!` | `docker-compose.next.yaml` | Token lamb uses to call KB. Must match `kb` `LAMB_API_KEY` when org config does not override token. |
| **`OWI_BASE_URL`** | none | required in `docker-compose.next.yaml` | Internal OpenWebUI API URL used by lamb bridge/auth flows. |
| `OWI_PUBLIC_BASE_URL` | `http://localhost:8080` | `docker-compose.next.yaml`; fallback behavior in `backend/config.py` | Browser-facing OpenWebUI URL. Used by frontend runtime fallback (`LAMB_FRONTEND_OPENWEBUI_SERVER`). |
| **`OWI_PATH`** | none | required in `docker-compose.next.yaml` | OpenWebUI data mount path visible from lamb (`/data/openwebui`). |
| `OPENAI_API_KEY` | empty | `docker-compose.next.yaml` | Optional unless OpenAI provider is used. |
| **`OPENAI_BASE_URL`** | none | required in `docker-compose.next.yaml` | OpenAI-compatible API base URL. |
| **`OPENAI_MODEL`** | none | required in `docker-compose.next.yaml` | Default OpenAI model. |
| `OPENAI_MODELS` | `gpt-4o-mini,gpt-4o` | `docker-compose.next.yaml` | Exposed/allowed OpenAI model list. |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | `docker-compose.next.yaml` (`backend/config.py` has older fallback) | Ollama base URL for lamb inference paths. Shared concept with `kb` `EMBEDDINGS_ENDPOINT`. |
| `OLLAMA_MODEL` | `nomic-embed-text` | `docker-compose.next.yaml` + `backend/config.py` fallback | Default Ollama model reference in lamb. |
| `SIGNUP_ENABLED` | `true` | `docker-compose.next.yaml` | Signup feature toggle. |
| **`SIGNUP_SECRET_KEY`** | none | required in `docker-compose.next.yaml` | Signup token secret (security-sensitive). |
| `LTI_SECRET` | `lamb-lti-secret-key-2024` | `docker-compose.next.yaml` | LTI shared secret; should be overridden in production. |
| `DEV_MODE` | `false` | `docker-compose.next.yaml` + `backend/config.py` | Runtime mode flag. |
| `GLOBAL_LOG_LEVEL` | `WARNING` | `docker-compose.next.yaml` + `backend/config.py` | Base log level for backend modules. |
| **`OWI_ADMIN_NAME`** | none | required in `docker-compose.next.yaml` | OpenWebUI admin bootstrap name used by lamb bridge. |
| **`OWI_ADMIN_EMAIL`** | none | required in `docker-compose.next.yaml` | OpenWebUI admin bootstrap email. |
| **`OWI_ADMIN_PASSWORD`** | none | required in `docker-compose.next.yaml` | OpenWebUI admin bootstrap password (security-sensitive). |
| `LAMB_FRONTEND_BUILD_PATH` | `/app/frontend/build` | `backend/docker-entrypoint.py` | Path used by entrypoint to patch/generate frontend runtime `config.js`. |
| `LAMB_FRONTEND_BASE_URL` | `/creator` | `backend/docker-entrypoint.py` | Frontend runtime `api.baseUrl`. |
| `LAMB_FRONTEND_LAMB_SERVER` | fallback to `LAMB_WEB_HOST` | `backend/docker-entrypoint.py` | Frontend runtime `api.lambServer`; depends on `LAMB_WEB_HOST`. |
| `LAMB_FRONTEND_OPENWEBUI_SERVER` | fallback to `OWI_PUBLIC_BASE_URL` | `backend/docker-entrypoint.py` | Frontend runtime `api.openWebUiServer`; depends on `OWI_PUBLIC_BASE_URL`. |
| `LAMB_ENABLE_OPENWEBUI` | `true` | `backend/docker-entrypoint.py` | Frontend feature toggle. |
| `LAMB_ENABLE_DEBUG` | `false` | `backend/docker-entrypoint.py` | Frontend debug feature toggle. |

### `kb` service

| Envar | Default value | Where default value is set | Description / Notes |
|---|---|---|---|
| `KB_PORT` (`PORT`) | `9090` | `docker-compose.next.yaml` (KB app also has fallback) | KB API port. |
| `KB_HOME_URL` (`HOME_URL`) | `http://localhost:9090` | `docker-compose.next.yaml` | Base URL used by KB metadata/routes. |
| `LAMB_API_KEY` | `0p3n-w3bu!` | `docker-compose.next.yaml` + KB app fallback | KB bearer token expected by API. Should match lamb-side token usage (`LAMB_KB_SERVER_TOKEN` or org-specific `api_token`). |
| `EMBEDDINGS_MODEL` | `nomic-embed-text` | `docker-compose.next.yaml` + KB app fallback | Default embedding model for new collections. |
| `EMBEDDINGS_VENDOR` | `ollama` | `docker-compose.next.yaml` + KB app fallback | Embedding provider (`ollama`, `local`, `openai`). |
| `EMBEDDINGS_ENDPOINT` | `http://ollama:11434` | `docker-compose.next.yaml` | For current Ollama integration in KB, base URL is expected (not `/api/embeddings`). Related to `lamb` `OLLAMA_BASE_URL`. |
| `EMBEDDINGS_APIKEY` | empty | `docker-compose.next.yaml` | Optional API key for embedding provider. |
| `FIRECRAWL_API_URL` | `http://host.docker.internal:3002` | `docker-compose.next.yaml` | Optional URL ingestion integration endpoint. |
| `FIRECRAWL_API_KEY` | empty | `docker-compose.next.yaml` | Optional Firecrawl API key. |

### `openwebui` service

| Envar | Default value | Where default value is set | Description / Notes |
|---|---|---|---|
| `OPENWEBUI_PORT` (`PORT`) | `8080` | `docker-compose.next.yaml` | OpenWebUI service port. |
| `WEBUI_AUTH_TRUSTED_EMAIL_HEADER` | `X-User-Email` | `docker-compose.next.yaml` | Trusted email header for bridge/SSO flows. |
| `WEBUI_AUTH_TRUSTED_NAME_HEADER` | `X-User-Name` | `docker-compose.next.yaml` | Trusted name header for bridge/SSO flows. |
| `DEFAULT_USER_ROLE` | `user` | `docker-compose.next.yaml` | Default role for new users. |
| `WEBUI_SECRET_KEY` | empty | `docker-compose.next.yaml` | Session/signing secret; should be set in production. |

### `ollama` service (`--profile ollama`)

| Envar | Default value | Where default value is set | Description / Notes |
|---|---|---|---|
| _(none currently mapped)_ | n/a | n/a | `ollama` is optional via profile. Behavior is controlled indirectly by `lamb` (`OLLAMA_BASE_URL`) and `kb` (`EMBEDDINGS_ENDPOINT`). |

### `caddy` service (`docker-compose.next.prod.yaml`)

| Envar | Default value | Where default value is set | Description / Notes |
|---|---|---|---|
| `CADDY_EMAIL` | `admin@yourdomain.com` | `docker-compose.next.prod.yaml` | ACME/TLS registration email. |
| `LAMB_PUBLIC_HOST` | `lamb.yourdomain.com` | `docker-compose.next.prod.yaml` | Public host for main LAMB routes. |
| `OWI_PUBLIC_HOST` | `owi.lamb.yourdomain.com` | `docker-compose.next.prod.yaml` | Public host for OpenWebUI routes. |

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

| Legacy path (host bind-mount) | New named volume | Used by |
|---|---|---|
| `/opt/lamb/lamb_v4.db` | `lamb-next_lamb-data` | `lamb` container (`/data/lamb`) |
| `/opt/lamb/open-webui/backend/data/` | `lamb-next_openwebui-data` | `openwebui` (`/app/backend/data`), `lamb` (`/data/openwebui`) |
| `/opt/lamb/lamb-kb-server-stable/backend/data/` | `lamb-next_kb-data` | `kb` container (`/app/backend/data`) |

Set the following `.env` values to match the new mount paths:

```
LAMB_DB_PATH=/data/lamb
OWI_PATH=/data/openwebui
```

The `lamb-next_` prefix comes from Docker Compose using the project directory name as the project name. Adjust if you run Compose with a different `--project-name`.

### Step-by-step migration

**1. Stop the legacy stack**

```bash
cd /opt/lamb
docker compose -f docker-compose-workers.yaml down
```

**2. Create the named volumes** (without starting any services yet)

```bash
cd /opt/lamb-next
docker compose -f docker-compose.next.yaml up --no-start
```

**3. Copy the LAMB database**

```bash
docker run --rm \
  -v /opt/lamb/lamb_v4.db:/src/lamb_v4.db:ro \
  -v lamb-next_lamb-data:/dst \
  alpine cp /src/lamb_v4.db /dst/lamb_v4.db
```

**4. Copy the Open WebUI data** (`webui.db`, `vector_db/`, `cache/`, `uploads/`)

```bash
docker run --rm \
  -v /opt/lamb/open-webui/backend/data:/src:ro \
  -v lamb-next_openwebui-data:/dst \
  alpine sh -c "cp -r /src/. /dst/"
```

**5. Copy the KB server data** (`lamb-kb-server.db`, `chromadb/`, `audit_logs/`, `config.json`)

```bash
docker run --rm \
  -v /opt/lamb/lamb-kb-server-stable/backend/data:/src:ro \
  -v lamb-next_kb-data:/dst \
  alpine sh -c "cp -r /src/. /dst/"
```

**6. Verify the volumes look correct**

```bash
docker run --rm -v lamb-next_lamb-data:/data alpine ls -la /data
docker run --rm -v lamb-next_openwebui-data:/data alpine ls -la /data
docker run --rm -v lamb-next_kb-data:/data alpine ls -la /data
```

**7. Start the new stack**

```bash
cd /opt/lamb-next
docker compose -f docker-compose.next.yaml up -d
```

### Notes

- The `kb-static` volume (`lamb-next_kb-static`) does not need migration — the KB service regenerates static files at startup.
- Stop the legacy stack cleanly before copying databases. SQLite WAL files (`-shm`, `-wal`) are present in the KB data directory; copying them alongside the main `.db` file is safe, but a clean shutdown ensures no in-flight writes are lost.
- No service-name aliasing is required in the new stack.

If your legacy `lamb_v4.db` uses prefixed tables (for example `LAMB_Creator_users`), no override is required because the default is `LAMB_`.

Only set an override when your DB is unprefixed:

```env
LAMB_DB_PREFIX=
```

Then recreate the `lamb` service so the backend queries the correct table names.
