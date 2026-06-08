# LAMB NEXT — Local Deployment Guide

This document is designed to be fed to an AI coding agent (like GitHub Copilot) that will autonomously deploy LAMB NEXT locally for development or testing purposes.

**Assumptions:**
- Docker and Docker Compose (V2) are installed on the local machine.
- Git is installed and the agent has access to the LAMB source repository.
- No DNS, TLS certificates, or cloud infrastructure are needed — everything runs on `localhost`.

---

## Phase 0: Gather Information (via `askQuestions`)

Before touching any files, the agent MUST collect these from the user using the `vscode_askQuestions` tool. Do NOT proceed until all answers are received.

### 0.0 — Pre-Flight: Check for Existing `.env`

> **CRITICAL — Do this FIRST, before asking any questions.**

If the user already has a `.env` file (at `<install-location>/.env` or in the current workspace), the agent MUST read it and extract all values. Use these as **pre-filled defaults** for the questions in sections 0.2–0.5. This dramatically reduces the number of questions — if the `.env` is complete, the user may only need to confirm a handful of values.

**Priority order for defaults:**
1. Existing `.env` at the install location (highest priority)
2. `backend/.env` or `backend/.env.example` in the repo
3. `lamb-kb-server-stable/backend/.env.example` (for embeddings vars)
4. Built-in defaults documented in sections 0.2–0.5 below (lowest priority)

**What to extract from the existing `.env`:**
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_MODELS`
- `EMBEDDINGS_VENDOR`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_APIKEY`, `EMBEDDINGS_ENDPOINT`
- `LAMB_BEARER_TOKEN`, `SIGNUP_SECRET_KEY`, `SIGNUP_ENABLED`, `DEV_MODE`
- `LAMB_WEB_HOST`, `LAMB_PORT`, `KB_PORT`, `OPENWEBUI_PORT`
- `OWI_ADMIN_NAME`, `OWI_ADMIN_EMAIL`, `OWI_ADMIN_PASSWORD`
- `OWI_PUBLIC_BASE_URL`, `LAMB_LIBRARY_TOKEN`
- Any other configured variables

> **Insight:** If a fully pre-filled `.env` already exists (all required vars present), the agent can skip directly to Phase 1 after a quick confirmation with the user. The user can also place a pre-filled `.env` in the clone target directory *before* the agent runs, ensuring a near-silent deployment.


> **🔍 AI Agent Note:** `.env` files (if they exist at all) are **gitignored** — glob-based file search will miss them. Use `list_dir` on the repo root, `backend/`, and `lamb-kb-server-stable/backend/` instead, or use `includeIgnoredFiles: true`. Read any `.env` found (priority: `<root>/.env` > `backend/.env` > `lamb-kb-server-stable/backend/.env` > `.env.example` files). ALWAYS ask for an *initial confirmation* from the user before attempting to read the .env. 

### 0.1 — Operating System & Shell

| Question | Purpose | Options / Notes |
|----------|---------|-----------------|
| Operating system | Determines install path, shell commands, and Docker setup | `Linux` or `Windows` |
| Windows shell | (Only if Windows) Which shell to use for all commands | `PowerShell` (native) or `WSL` (Windows Subsystem for Linux) |

> **Insight:** WSL behaves like Linux for all shell commands (bash, `sudo`, heredocs, etc.). If the user chooses WSL, treat the environment as Linux throughout this guide. PowerShell requires different syntax for many operations (see Phase 1–3 for platform-specific commands).

### 0.2 — Workspace Setup

| Question | Purpose | Options / Notes |
|----------|---------|-----------------|
| Install location | Where to clone the repo | **Linux / WSL:** `/opt/lamb` — **Windows PowerShell:** `C:\lamb` |
| Git branch | Which branch to use | Default: `main` |
| Existing data? | Does the user have data from a previous LAMB installation to migrate? | `yes` or `no`. If yes, the agent must ask for the **old project path** (where the old LAMB install lives — database, OpenWebUI data, KB server data). |

### 0.3 — API Keys & Model Configuration

| Question | Purpose | Default / Fallback |
|----------|---------|---------------------|
| OpenAI API key | `OPENAI_API_KEY` and `EMBEDDINGS_APIKEY` | Required unless using Ollama for everything |
| OpenAI base URL | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| OpenAI model | `OPENAI_MODEL` | `gpt-4o-mini` |
| OpenAI model list | `OPENAI_MODELS` | `gpt-4o-mini,gpt-4o` |
| Embeddings vendor | `EMBEDDINGS_VENDOR` | `openai` or `ollama` (local, no API key needed) |
| Embeddings model | `EMBEDDINGS_MODEL` | `text-embedding-3-large` (OpenAI) or `nomic-embed-text` (Ollama) |
| Embeddings endpoint | `EMBEDDINGS_ENDPOINT` | `https://api.openai.com/v1` (OpenAI) or `http://ollama:11434` (Ollama) |
| Embeddings API key | `EMBEDDINGS_APIKEY` | Same as `OPENAI_API_KEY` for OpenAI; leave empty for Ollama |

> **IMPORTANT:** If the user has an existing `backend/.env` file or `.env.example`, extract keys from those files as defaults to pre-fill the questions.

### 0.4 — Feature Toggles & Secrets

| Question | Purpose | Default |
|----------|---------|---------|
| Enable signup? | `SIGNUP_ENABLED` | `true` |
| Enable dev mode? | `DEV_MODE` | `true` (for local dev) |
| Enable Ollama? | Adds `--profile ollama` to compose | `false` — ask the user if they want local LLM inference via Ollama |
| Signup secret key | `SIGNUP_SECRET_KEY` | Auto-generate a random string |
| LAMB bearer token | `LAMB_BEARER_TOKEN` | Auto-generate a random string |
| OWI admin name/email/password | Bootstrap admin account for OpenWebUI | e.g., `Admin` / `admin@localhost.local` / auto-generated password |

### 0.5 — Port Configuration

| Question | Purpose | Default |
|----------|---------|---------|
| LAMB port | Backend API port | `9099` |
| KB port | Knowledge base server port | `9090` |
| OpenWebUI port | Chat interface port | `8080` |
| Ollama port | Local LLM port (if enabled) | `11434` |

> **Insight:** The defaults work for most users. Only ask about port overrides if the user mentions port conflicts.

---

## Phase 1: Prerequisites Check

The agent MUST verify these before proceeding. Check them on the local machine (no SSH needed).

### 1.1 — Check Docker

```bash
docker --version
docker compose version
```

Expected: Docker 29+ and Docker Compose V2 (the plugin, invoked as `docker compose`).

If Docker is not installed, tell the user to install it:
- **Windows/Mac:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux:** `curl -fsSL https://get.docker.com | sh`

### 1.2 — Check Available Disk Space

```bash
df -h <install-location>
```

The stack's Docker images total ~3-4 GB. With volumes, plan for at least 10 GB free.

### 1.3 — Check Port Availability

```bash
# Check if default ports are already in use
lsof -i :9099 2>/dev/null || netstat -tlnp 2>/dev/null | grep -E '9099|9090|8080|11434'
```

If any ports are in use, ask the user to either free them or choose alternative ports in Phase 0.5.

---

## Phase 2: Clone the Repository

### 2.1 — Create the Install Directory

```bash
sudo mkdir -p <install-location>
sudo chown $(whoami) <install-location>
```

Or on Windows (PowerShell as Administrator):

```powershell
New-Item -ItemType Directory -Path <install-location> -Force
```

### 2.2 — Clone

```bash
git clone https://github.com/Lamb-Project/lamb.git <install-location>
cd <install-location>
```

If the user specified a branch:

```bash
git checkout <branch>
```

---

## Phase 3: Create the `.env` File

The `.env` file lives in the repo root (same directory as `docker-compose.next.yaml`).

### 3.1 — Required Variables (compose fails if missing)

These MUST be set. The compose file uses `${VAR?error message}` syntax.

| Variable | Local Default | Notes |
|----------|--------------|-------|
| `LAMB_WEB_HOST` | `http://localhost:9099` | The URL where the LAMB frontend is accessed |
| `LAMB_BACKEND_HOST` | `http://lamb:9099` | Internal Docker service name — NOT `localhost` |
| `LAMB_BEARER_TOKEN` | Auto-generated | Strong random string |
| `LAMB_DB_PATH` | `/data/lamb` | Path INSIDE the container |
| `OWI_BASE_URL` | `http://openwebui:8080` | Internal Docker service name |
| `OWI_PATH` | `/data/openwebui` | Path INSIDE the container |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Or user's custom endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Or user's custom model |
| `SIGNUP_SECRET_KEY` | Auto-generated | Strong random string |
| `OWI_ADMIN_NAME` | `Admin` | OpenWebUI bootstrap admin |
| `OWI_ADMIN_EMAIL` | `admin@localhost.local` | OpenWebUI bootstrap admin |
| `OWI_ADMIN_PASSWORD` | Auto-generated | Strong password |
| `LAMB_LIBRARY_TOKEN` | Auto-generated | Strong random string for library-manager auth |

### 3.2 — Browser-Facing URLs

| Variable | Local Default | Notes |
|----------|--------------|-------|
| `OWI_PUBLIC_BASE_URL` | `http://localhost:8080` | Browser-facing OpenWebUI URL. REQUIRED — without it, LAMB generates login redirects using the internal Docker hostname (`openwebui:8080`) that browsers cannot resolve. Must be set even for local dev. |

### 3.3 — KB Embeddings Variables

| Variable | Local Default (Ollama) | Local Default (OpenAI) |
|----------|------------------------|-------------------------|
| `EMBEDDINGS_VENDOR` | `ollama` | `openai` |
| `EMBEDDINGS_MODEL` | `nomic-embed-text` | `text-embedding-3-large` |
| `EMBEDDINGS_APIKEY` | (empty) | Same as `OPENAI_API_KEY` |
| `EMBEDDINGS_ENDPOINT` | `http://ollama:11434` | `https://api.openai.com/v1` |

> **Insight:** If the user is NOT running Ollama, they MUST use OpenAI for embeddings. The KB server requires a working embeddings provider.

### 3.4 — Optional Variables

```bash
OPENAI_API_KEY=sk-...               # only if using OpenAI
OPENAI_MODELS=gpt-4o-mini,gpt-4o    # comma-separated list of available models
LAMB_KB_SERVER=http://kb:9090       # default, can omit
LAMB_KB_SERVER_TOKEN=0p3n-w3bu!     # must match KB's LAMB_API_KEY
LTI_SECRET=lamb-lti-secret-key-2024 # override in production-like testing
SIGNUP_ENABLED=true
DEV_MODE=true                       # true for local dev
GLOBAL_LOG_LEVEL=WARNING
WEBUI_SECRET_KEY=                   # optional, auto-generated if empty
LAMB_PORT=9099
KB_PORT=9090
OPENWEBUI_PORT=8080
```

### 3.5 — Key Insights for the Agent

- **`LAMB_BACKEND_HOST`** is an INTERNAL Docker network URL (`http://lamb:9099`), NOT `localhost`. The `lamb` part is the Docker Compose service name.
- **`OWI_BASE_URL`** likewise uses the Docker service name: `http://openwebui:8080`.
- **`LAMB_DB_PATH`** and **`OWI_PATH`** are paths INSIDE the container, not on the host. The defaults use Docker named volumes.
- **`LAMB_WEB_HOST`** IS `http://localhost:9099` — this is the URL the browser uses, so it must point to the host.
- **`OWI_PUBLIC_BASE_URL`** is the browser-facing OpenWebUI URL. Without it, the code falls back to `OWI_BASE_URL` (`http://openwebui:8080`), which browsers can't resolve. For local dev, set it to `http://localhost:8080`.
- **`LAMB_LIBRARY_TOKEN`** is required by `docker-compose.next.yaml` (the `library-manager` service uses `?Set` syntax). Auto-generate a random string.
- **API key reuse** — The user may want the same key for both `OPENAI_API_KEY` (lamb service) and `EMBEDDINGS_APIKEY` (kb service), or different keys. Ask explicitly.

### 3.6 — Write the File

The agent should construct the `.env` from the collected answers and write it:

```bash
cat > <install-location>/.env << 'ENVEOF'
# ============================================================================
# LAMB NEXT — Local Development .env
# ============================================================================

# --- Required ---
LAMB_WEB_HOST=http://localhost:9099
LAMB_BACKEND_HOST=http://lamb:9099
LAMB_BEARER_TOKEN=<auto-generated>
LAMB_DB_PATH=/data/lamb
OWI_BASE_URL=http://openwebui:8080
OWI_PUBLIC_BASE_URL=http://localhost:8080
OWI_PATH=/data/openwebui
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
SIGNUP_SECRET_KEY=<auto-generated>
OWI_ADMIN_NAME=Admin
OWI_ADMIN_EMAIL=admin@localhost.local
OWI_ADMIN_PASSWORD=<auto-generated>
LAMB_LIBRARY_TOKEN=<auto-generated>

# --- KB Embeddings  ---
EMBEDDINGS_VENDOR=openai
EMBEDDINGS_MODEL=text-embedding-3-large
EMBEDDINGS_APIKEY=sk-...
EMBEDDINGS_ENDPOINT=https://api.openai.com/v1

# --- Optional ---
OPENAI_API_KEY=sk-...
OPENAI_MODELS=gpt-4o-mini,gpt-4o
SIGNUP_ENABLED=true
DEV_MODE=true
GLOBAL_LOG_LEVEL=WARNING
ENVEOF
```

> **Insight:** Use single-quoted `'ENVEOF'` (heredoc delimiter) to prevent shell variable expansion. Auto-generate passwords using: `openssl rand -hex 32`.

---

## Phase 3.5: Migrate Existing Data (GATE — Conditional)

> **Only execute this phase if the user answered `yes` to "Existing data?" in Phase 0.2. If this is a fresh install with no prior data, skip to Phase 4.**

The old LAMB stack stored data in host directories. The new stack uses **named Docker volumes**. This phase copies existing data into the new volumes so the user doesn't lose their database, OpenWebUI accounts, or KB server collections.

### 3.5.1 — What the agent needs

From Phase 0.2, the agent should have:
- **`<old-project-path>`** — the directory where the old LAMB installation lives (e.g., `/opt/lamb-old` or `C:\lamb-old`)
- **`<install-location>`** — the new install directory (from Phase 0.2)

The expected data locations inside the old project:

| Data | Old location (relative to old project path) | New volume |
|------|---------------------------------------------|------------|
| LAMB database | `<old-project-path>/lamb_v4.db` | `lamb-data` (file: `lamb_v4.db`) |
| OpenWebUI data | `<old-project-path>/open-webui/backend/data/` | `openwebui-data` |
| KB server data | `<old-project-path>/lamb-kb-server-stable/backend/data/` | `kb-data` |

### 3.5.2 — Run the migration

Follow the step-by-step guide in **`Documentation/slop-docs/migrating-to-lamb-next.md`**, using the paths above. The migration document covers:

1. Creating named volumes with `docker compose up --no-start`
2. Copying the LAMB database into `lamb-data`
3. Copying OpenWebUI data into `openwebui-data`
4. Copying KB server data into `kb-data`
5. Verifying the copied data
6. Troubleshooting (schema auto-migration, large KB data, platform warnings)

> **Insight:** The `.env` file must already exist (Phase 3) before running the migration, since `docker compose` reads it. Adapt the migration guide's paths — replace `/opt/lamb` with `<old-project-path>`, and substitute the correct compose project name (defaults to the directory name of `<install-location>`).

### 3.5.3 — Critical gotcha

**Stop the old stack first.** If the old LAMB containers are still running with bind-mounts to these data directories, the copy may produce inconsistent results. Ask the user to run this from the old project directory before migrating:

```bash
docker compose -f docker-compose.yaml down
```

---

## Phase 4: Launch the Stack

### 4.1 — Pull Images and Start (Without Ollama)

```bash
cd <install-location>
docker compose -f docker-compose.next.yaml up -d
```

### 4.2 — With Ollama (Local LLM Inference)

```bash
cd <install-location>
docker compose -f docker-compose.next.yaml --profile ollama up -d
```

> **Note:** The first run downloads ~3-4 GB of Docker images (more with Ollama). This may take several minutes. The agent should run this in async mode with a generous timeout (≥300s).

> **Insight:** When using the Ollama profile, the user will need to pull models inside the Ollama container before they can be used. See Phase 5.5.

### 4.3 — Windows-Specific Notes

On Windows with Docker Desktop:
- Ensure the WSL2 backend is running.
- `host.docker.internal` is available for services that need to reach the host.
- Volume mounts work with WSL2 paths. If the repo is on a Windows drive (e.g., `C:\`), use the Docker Desktop file sharing settings to allow that drive.

---

## Phase 5: Verify the Deployment

### 5.1 — Check Container Status

```bash
cd <install-location>
docker compose -f docker-compose.next.yaml ps
```

All services should show `Up` and `healthy`:

| Container | Expected Status |
|-----------|----------------|
| `lamb-lamb-1` | Up (healthy) |
| `lamb-kb-1` | Up (healthy) |
| `lamb-openwebui-1` | Up (healthy) |
| `lamb-ollama-1` | Up (only if Ollama profile enabled) |

### 5.2 — Check Logs

```bash
docker compose -f docker-compose.next.yaml logs -f --tail=50
```

Look for:
- Lamb: `Uvicorn running on http://0.0.0.0:9099`
- OpenWebUI: `Uvicorn running on http://0.0.0.0:8080`
- KB: `Uvicorn running on http://0.0.0.0:9090`

### 5.3 — Verify Services Are Reachable

Open these URLs in a browser:

| Service | URL | What You Should See |
|---------|-----|---------------------|
| LAMB Creator Interface | `http://localhost:9099` | LAMB sign-in / creator page |
| OpenWebUI Chat | `http://localhost:8080` | OpenWebUI sign-in page |
| KB Server API | `http://localhost:9090/docs` | FastAPI Swagger docs |
| LAMB API Docs | `http://localhost:9099/docs` | FastAPI Swagger docs |

### 5.4 — Verify Health Endpoints

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:9099/health
curl -s http://localhost:9090/health
```

All should return HTTP 200 or similar success response.

### 5.5 — Verify OpenWebUI Redirect URL

After the stack is up, verify the OpenWebUI redirect uses the browser-accessible URL:

```bash
# Test login and check the launch_url field
curl -s -X POST http://localhost:9099/creator/login \
  -d "email=${OWI_ADMIN_EMAIL}&password=${OWI_ADMIN_PASSWORD}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('launch_url','MISSING'))"
```

The `launch_url` should start with `http://localhost:8080/`, NOT `http://openwebui:8080/`. If it shows the internal hostname, `OWI_PUBLIC_BASE_URL` is missing or not being passed to the `lamb` container — add it to both `.env` and `docker-compose.next.yaml` (see Phase 3.2).

### 5.6 — Pull Ollama Models (if using Ollama profile)

If the Ollama profile is enabled, pull the embedding model and optionally a chat model:

```bash
# Pull the embedding model (required for KB)
docker exec lamb-ollama-1 ollama pull nomic-embed-text

# Optional: pull a chat model for local inference
docker exec lamb-ollama-1 ollama pull llama3.2
```

> **Insight:** The `nomic-embed-text` model is required for KB embeddings if `EMBEDDINGS_VENDOR=ollama`. Without it, KB ingestion will fail.

---

## Phase 6: Day-to-Day Operations (Cheatsheet)

### Stop the stack
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml down
```

### Start the stack
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml up -d
```

### Update images and restart
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml pull && docker compose -f docker-compose.next.yaml up -d
```

### View logs for a specific service
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml logs -f lamb
```

### Restart a single service
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml restart lamb
```

### Rebuild after code changes (when using local build)
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml up -d --build
```

### Reset all data (WARNING: deletes all databases and uploaded files)
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml down -v
```

### Access a service shell
```bash
docker exec -it lamb-lamb-1 bash
docker exec -it lamb-kb-1 bash
docker exec -it lamb-openwebui-1 bash
```

---

## Phase 7: Tear Down

### Stop and remove containers, networks
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml down
```

### Also remove volumes (deletes ALL data)
```bash
cd <install-location> && docker compose -f docker-compose.next.yaml down -v
```

### Remove images to free disk space
```bash
docker rmi ghcr.io/lamb-project/lamb:latest
docker rmi ghcr.io/lamb-project/lamb-kb:latest
docker rmi ghcr.io/lamb-project/openwebui:latest
docker rmi ollama/ollama:latest  # if Ollama was used
```

### Remove the repo
```bash
sudo rm -rf <install-location>
```

---

## Appendix A: Complete Local `.env` Template

```bash
# ============================================================================
# LAMB NEXT — Local Development .env
# ============================================================================

# --- Required ---
LAMB_WEB_HOST=http://localhost:9099
LAMB_BACKEND_HOST=http://lamb:9099
LAMB_BEARER_TOKEN=<strong-random-string>
LAMB_DB_PATH=/data/lamb
OWI_BASE_URL=http://openwebui:8080
OWI_PUBLIC_BASE_URL=http://localhost:8080
OWI_PATH=/data/openwebui
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
SIGNUP_SECRET_KEY=<strong-random-string>
OWI_ADMIN_NAME=Admin
OWI_ADMIN_EMAIL=admin@localhost.local
OWI_ADMIN_PASSWORD=<strong-password>
LAMB_LIBRARY_TOKEN=<strong-random-string>

# --- KB Embeddings (Ollama — no API key needed) ---
# EMBEDDINGS_VENDOR=ollama
# EMBEDDINGS_MODEL=nomic-embed-text
# EMBEDDINGS_APIKEY=
# EMBEDDINGS_ENDPOINT=http://ollama:11434

# --- KB Embeddings ---
EMBEDDINGS_VENDOR=openai
EMBEDDINGS_MODEL=text-embedding-3-large
EMBEDDINGS_APIKEY=sk-...
EMBEDDINGS_ENDPOINT=https://api.openai.com/v1

# --- Optional / Tweaks ---
OPENAI_MODELS=gpt-4o-mini,gpt-4o
LAMB_KB_SERVER=http://kb:9090
LAMB_KB_SERVER_TOKEN=0p3n-w3bu!
LTI_SECRET=lamb-lti-secret-key-2024
SIGNUP_ENABLED=true
DEV_MODE=true
GLOBAL_LOG_LEVEL=WARNING
WEBUI_SECRET_KEY=

# --- Ports (only if overriding defaults) ---
# LAMB_PORT=9099
# KB_PORT=9090
# OPENWEBUI_PORT=8080
```

---

## Appendix B: Architecture Reference (Local)

| Service | Internal Port | Local URL | Docker Image |
|---------|--------------|-----------|--------------|
| `lamb` | 9099 | `http://localhost:9099` | `ghcr.io/lamb-project/lamb:latest` |
| `kb` | 9090 | `http://localhost:9090` | `ghcr.io/lamb-project/lamb-kb:latest` |
| `openwebui` | 8080 | `http://localhost:8080` | `ghcr.io/lamb-project/openwebui:latest` |
| `ollama` (optional) | 11434 | `http://localhost:11434` | `ollama/ollama:latest` |

**Service dependencies:**
- `lamb` depends on `kb` (service_started) and `openwebui` (service_healthy)
- `kb` is independent
- `openwebui` is independent
- `ollama` is independent (used by `kb` for embeddings and by `lamb` for chat if configured)

**Docker volumes:**
- `lamb-data` — LAMB database and uploads
- `kb-data` — KB server database and vector store
- `kb-static` — KB server static files
- `openwebui-data` — OpenWebUI database and configuration
- `ollama-data` — Ollama models (only with Ollama profile)

---

## Appendix C: Known Gotchas

1. **Docker Compose version:** The `docker compose` (V2, space, no hyphen) command is required. The old `docker-compose` (V1) won't work with the compose file syntax.

2. **`.env` file location:** Must be in the same directory as `docker-compose.next.yaml` (the repo root). Docker Compose reads it automatically when running from that directory.

3. **Required variable failures:** Missing `?Set VARNAME` variables cause `docker compose` to fail with a clear error message. This is a fast-fail mechanism — the agent should double-check all required vars before running compose.

4. **OpenWebUI startup race:** The `lamb` service has `depends_on: openwebui: condition: service_healthy`. OpenWebUI may take 30-60 seconds on first boot to initialize its database. The healthcheck prevents the race.

5. **Ollama model pull:** When using the Ollama profile, models are NOT included in the image. The user must pull them manually with `docker exec lamb-ollama-1 ollama pull <model>`. The embedding model (`nomic-embed-text`) is required for KB ingestion.

6. **Port conflicts:** If ports 9099, 9090, 8080, or 11434 are already in use, the stack will fail to start. Check with `lsof -i :PORT` before launching.

7. **Memory usage:** Running all services (lamb + kb + openwebui) uses ~2-3 GB RAM. Adding Ollama with models adds 1-4 GB more depending on the models loaded.

8. **`DEV_MODE=true` implications:** When `DEV_MODE=true`, the backend exposes additional debug/admin endpoints and may use development-oriented settings. This is appropriate for local development.

9. **Docker Desktop on Windows/Mac:** If using Docker Desktop, ensure the file sharing settings include the drive where the repo is cloned. WSL2 backend is recommended for Windows.

10. **No TLS locally:** The local deployment uses plain HTTP on localhost. Do not set `LAMB_WEB_HOST` to an `https://` URL — it won't work without Caddy and TLS certificates.

11. **OpenWebUI redirect breaks without `OWI_PUBLIC_BASE_URL`:** If the agent forgets to set `OWI_PUBLIC_BASE_URL=http://localhost:8080`, the LAMB frontend's OpenWebUI menu item will redirect to `http://openwebui:8080/...` — an internal Docker hostname that browsers can't resolve. Always include this variable in the `.env` and verify the login `launch_url` points to `localhost` (see Phase 5.6).

12. **`LAMB_LIBRARY_TOKEN` is required:** The `docker-compose.next.yaml` uses `${LAMB_LIBRARY_TOKEN?Set LAMB_LIBRARY_TOKEN}` for the `library-manager` service. Omitting it causes `docker compose up` to fail. Always auto-generate this token.

13. **Schema migration can fail silently on first boot:** The backend runs database migrations and then immediately tries to use the migrated columns. On the first startup with an existing database, you may see errors like `no such column: password_hash` in the logs. These are one-time — the migration adds the columns, and subsequent restarts are clean. If the error persists across multiple restarts, the migration itself may be failing; check `docker logs lamb-lamb-1` for `Migration error` messages.

---

## Appendix D: Agent Workflow Checklist

The agent should follow this sequence and check off each step:

- [ ] **0.1** — Ask operating system and (if Windows) PowerShell vs WSL
- [ ] **0.2** — Ask install location, branch, existing data (and old project path if applicable)
- [ ] **0.3** — Ask API keys, model configuration, embeddings vendor
- [ ] **0.4** — Ask feature toggles (signup, dev mode, Ollama), generate secrets
- [ ] **0.5** — Confirm port configuration
- [ ] **1.1** — Verify Docker and Docker Compose are installed
- [ ] **1.2** — Check available disk space
- [ ] **1.3** — Check port availability
- [ ] **2.1** — Create install directory
- [ ] **2.2** — Clone repository (and checkout branch if needed)
- [ ] **3** — Create `.env` file with all collected variables
- [ ] **3.5** — (If existing data) Stop old stack, create volumes, copy LAMB DB, OWI data, KB data, verify
- [ ] **4** — Run `docker compose -f docker-compose.next.yaml up -d` (with `--profile ollama` if needed)
- [ ] **5.1** — Verify all containers are Up and healthy
- [ ] **5.2** — Check logs for startup errors
- [ ] **5.3** — Report access URLs to user
- [ ] **5.4** — Verify health endpoints
- [ ] **5.5** — Verify OpenWebUI redirect URL uses `localhost`, not internal Docker hostname
- [ ] **5.6** — Pull Ollama models if using Ollama profile

---

## Appendix E: Quick Start (Minimal Path)

For users who want to skip the interactive questions and go fast, the agent can use these defaults:

```bash
# Clone
git clone https://github.com/Lamb-Project/lamb.git /opt/lamb
cd /opt/lamb

# Generate secrets
LAMB_BEARER_TOKEN=$(openssl rand -hex 32)
SIGNUP_SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -hex 16)

# Write .env
cat > .env << ENVEOF
LAMB_WEB_HOST=http://localhost:9099
LAMB_BACKEND_HOST=http://lamb:9099
LAMB_BEARER_TOKEN=$LAMB_BEARER_TOKEN
LAMB_DB_PATH=/data/lamb
OWI_BASE_URL=http://openwebui:8080
OWI_PATH=/data/openwebui
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-REPLACE_ME
SIGNUP_SECRET_KEY=$SIGNUP_SECRET_KEY
OWI_ADMIN_NAME=Admin
OWI_ADMIN_EMAIL=admin@localhost.local
OWI_ADMIN_PASSWORD=$ADMIN_PASSWORD
EMBEDDINGS_VENDOR=ollama
EMBEDDINGS_MODEL=nomic-embed-text
EMBEDDINGS_APIKEY=
EMBEDDINGS_ENDPOINT=http://ollama:11434
OPENAI_MODELS=gpt-4o-mini,gpt-4o
SIGNUP_ENABLED=true
DEV_MODE=true
ENVEOF

# Launch (with Ollama for embeddings)
docker compose -f docker-compose.next.yaml --profile ollama up -d

# Pull the embedding model
docker exec lamb-ollama-1 ollama pull nomic-embed-text
```

> **Note:** The user MUST replace `sk-REPLACE_ME` with a real OpenAI API key, or configure their preferred LLM provider. If they want to skip Ollama entirely, they must set `EMBEDDINGS_VENDOR=openai` and provide both `EMBEDDINGS_APIKEY` and `EMBEDDINGS_ENDPOINT`.
