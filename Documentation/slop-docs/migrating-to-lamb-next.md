# Migrating to lamb.next (docker-compose.next.yaml)

The new stack replaces the old build-on-deploy approach with **pre-built container images** and **named Docker volumes**. No more local `npm run build` or `pip install` at startup.

## What changes

| | Old stack (`docker-compose.yaml`) | New stack (`docker-compose.next.yaml`) |
|---|---|---|
| Images | Built at startup from source | Pre-built from GHCR |
| Data storage | Host bind-mounts (`/opt/lamb/...`) | Named Docker volumes |
| Config file | `backend/.env` | `.env` at project root |
| Service name | `backend` | `lamb` |
| Build services | `openwebui-build`, `frontend-build` | Gone |

## Prerequisites

- Docker with Compose v2 (`docker compose` not `docker-compose`)
- Git on the `dev` branch (PR #286 merged)
- Current lamb containers are stopped

---

## Step 1 - Pull the latest dev branch

```bash
cd /opt/lamb
git checkout dev
git pull origin dev
```

## Step 2 - Create your `.env` file

Copy the example and fill in your values:

```bash
cp .env.next.example .env
```

Edit `.env` - the minimum required vars are:

```env
# Data paths (inside containers - leave as-is)
LAMB_DB_PATH=/data/lamb
OWI_PATH=/data/openwebui

# Required if your DB was created with the old stack (prefixed tables LAMB_*)
LAMB_DB_PREFIX=LAMB_

# Internal OWI URL (leave as-is)
OWI_BASE_URL=http://openwebui:8080

# Public URLs (adjust to your hostname/IP if not localhost)
LAMB_WEB_HOST=http://localhost:9099
LAMB_BACKEND_HOST=http://lamb:9099

# Secrets - change these
LAMB_BEARER_TOKEN=change-me
SIGNUP_SECRET_KEY=change-me

# OpenAI (or any OpenAI-compatible endpoint)
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# OWI admin bootstrap
OWI_ADMIN_NAME=Admin User
OWI_ADMIN_EMAIL=admin@example.com
OWI_ADMIN_PASSWORD=change-me
```

> The full list of optional vars (embeddings, Ollama, LTI, ports, log levels, etc.) is in `.env.next.example`.

## Step 3 - Create named volumes and migrate existing data

### 3a. Create the volumes (without starting services)

```bash
docker compose -f docker-compose.next.yaml --env-file .env --project-name lamb-next up --no-start
```

This creates four named volumes: `lamb-next_lamb-data`, `lamb-next_openwebui-data`, `lamb-next_kb-data`, `lamb-next_kb-static`.

### 3b. Copy the LAMB database

```bash
docker run --rm \
  -v /opt/lamb/lamb_v4.db:/src/lamb_v4.db:ro \
  -v lamb-next_lamb-data:/dst \
  alpine cp /src/lamb_v4.db /dst/lamb_v4.db
```

### 3c. Copy the Open WebUI data

```bash
docker run --rm \
  -v /opt/lamb/open-webui/backend/data:/src:ro \
  -v lamb-next_openwebui-data:/dst \
  alpine sh -c "cp -r /src/. /dst/"
```

### 3d. Copy the KB server data

```bash
docker run --rm \
  -v /opt/lamb/lamb-kb-server-stable/backend/data:/src:ro \
  -v lamb-next_kb-data:/dst \
  alpine sh -c "cp -r /src/. /dst/"
```

### 3e. Verify the volumes

```bash
docker run --rm -v lamb-next_lamb-data:/data alpine ls -la /data
docker run --rm -v lamb-next_openwebui-data:/data alpine ls -la /data
docker run --rm -v lamb-next_kb-data:/data alpine ls -la /data
```

Expected: `lamb_v4.db` in `lamb-data`; `webui.db`, `vector_db/`, etc. in `openwebui-data`; `lamb-kb-server.db`, `chromadb/` in `kb-data`.

## Step 4 - Pull images

```bash
docker compose -f docker-compose.next.yaml --env-file .env --project-name lamb-next pull
```

> **Apple Silicon (M1/M2/M3):** Current images are `linux/amd64` only and run under Rosetta emulation. This works but is slower for RAG ingestion. Native `arm64` images are planned.

## Step 5 - Start the stack

```bash
docker compose -f docker-compose.next.yaml --env-file .env --project-name lamb-next up -d
```

The startup order is: `openwebui` first (with healthcheck), then `kb` and `lamb` in parallel once OWI is healthy.

## Step 6 - Verify

```bash
# Container status
docker ps --filter "name=lamb-next"

# Health endpoints
curl http://localhost:9099/status        # {"status": true}
curl http://localhost:9090/health        # {"status": "ok", ...}
curl http://localhost:8080/health        # {"status": true}

# Check logs if something is wrong
docker compose -f docker-compose.next.yaml --project-name lamb-next logs -f
```

Then open `http://localhost:9099` in your browser - the frontend SPA is now served directly by the `lamb` container (no separate dev server).

---

## Day-to-day operations

### Update to latest images

```bash
docker compose -f docker-compose.next.yaml --env-file .env --project-name lamb-next pull
docker compose -f docker-compose.next.yaml --env-file .env --project-name lamb-next up -d
```

No local build step needed - just pull and restart.

### Stop the stack

```bash
docker compose -f docker-compose.next.yaml --project-name lamb-next down
```

### View logs

```bash
# All services
docker compose -f docker-compose.next.yaml --project-name lamb-next logs -f

# Single service
docker logs lamb-next-lamb-1 -f
```

### Optional: local Ollama (for local inference)

```bash
docker compose -f docker-compose.next.yaml --env-file .env --project-name lamb-next --profile ollama up -d
```

### Optional: production TLS with Caddy

```bash
docker compose \
  -f docker-compose.next.yaml \
  -f docker-compose.next.prod.yaml \
  --env-file .env \
  --project-name lamb-next \
  up -d
```

Set `CADDY_EMAIL`, `LAMB_PUBLIC_HOST`, and `OWI_PUBLIC_HOST` in `.env` before using this.

---

## Troubleshooting

**`lamb` fails to start / connection refused to OWI**
The healthcheck on `openwebui` gives it up to 2 minutes to become ready. On first boot with an empty DB it may take longer. Wait and check `docker logs lamb-next-openwebui-1`.

**`LAMB_DB_PREFIX` - which value do I need?**
If your `lamb_v4.db` has tables named `LAMB_Creator_users`, `LAMB_Creator_assistants`, etc., set `LAMB_DB_PREFIX=LAMB_`. If tables are named `Creator_users` etc., leave it empty.

**Platform warning (`linux/amd64` on Apple Silicon)**
This is expected and harmless. The containers run via Rosetta 2.

**Old stack data is untouched**
The migration only *copies* data into the named volumes. Your original files at `/opt/lamb/lamb_v4.db`, `/opt/lamb/open-webui/backend/data/`, and `/opt/lamb/lamb-kb-server-stable/backend/data/` are not modified.
