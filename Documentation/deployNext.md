# LAMB NEXT — Autonomous Deployment Guide

This document is designed to be fed to an AI coding agent (like GitHub Copilot) that will autonomously deploy LAMB NEXT to a Hetzner Cloud server in production.

**Assumptions:**
- DNS is already configured (the agent should ask for domain/subdomain names, not set them up).
- Hetzner `hcloud` CLI is installed and authenticated on the local machine.
- An SSH public key is registered in Hetzner (the agent can check and add one if needed).
- The agent has access to the LAMB source repository.

---

## Phase 0: Gather Information (via `askQuestions`)

Before touching any infrastructure, the agent MUST collect these from the user using the `vscode_askQuestions` tool. Do NOT proceed until all answers are received.

### 0.1 — Server Configuration

| Question | Purpose | Options / Notes |
|----------|---------|-----------------|
| Server type | vCPU/RAM/disk sizing | `cpx22` (2 vCPU, 4 GB, 80 GB) for tests without Ollama; `cpx32` (4 vCPU, 8 GB, 160 GB) for small production; `cpx62` (16 vCPU, 32 GB, 640 GB) for production with Ollama |
| Server location | Datacenter | `hel1` (Helsinki), `nbg1` (Nuremberg), `ash` (Ashburn US) |
| SSH keys | Which hcloud SSH keys to add | e.g., `my-macbook`, `teammate-key` (can select multiple) |
| Server name | Label for the instance | e.g., `lamb-prod-01` |

### 0.2 — Domain Configuration

| Question | Purpose | Example |
|----------|---------|---------|
| Main LAMB domain | `LAMB_PUBLIC_HOST` / `LAMB_WEB_HOST` | `lamb.example.com` |
| OpenWebUI domain | `OWI_PUBLIC_HOST` | `owi.lamb.example.com` |
| ACME email | `CADDY_EMAIL` for Let's Encrypt | `admin@example.com` |

### 0.3 — API Keys & Secrets

| Question | Purpose | Default / Fallback |
|----------|---------|---------------------|
| OpenAI API key | `OPENAI_API_KEY` and `EMBEDDINGS_APIKEY` | Required unless using Ollama |
| OpenAI base URL | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| OpenAI model | `OPENAI_MODEL` | `gpt-4o-mini` (the user may have a custom model name) |
| OpenAI model list | `OPENAI_MODELS` | Comma-separated, e.g., `gpt-4o-mini,gpt-4o` |
| Embeddings vendor | `EMBEDDINGS_VENDOR` | `openai` or `ollama` |
| Embeddings model | `EMBEDDINGS_MODEL` | `text-embedding-3-large` (OpenAI) or `nomic-embed-text` (Ollama) |
| Embeddings endpoint | `EMBEDDINGS_ENDPOINT` | `https://api.openai.com/v1` or `http://ollama:11434` |
| LAMB bearer token | `LAMB_BEARER_TOKEN` | Should be a strong random string in production |
| Signup secret key | `SIGNUP_SECRET_KEY` | Strong random string in production |
| LTI secret | `LTI_SECRET` | Override in production |
| WebUI secret key | `WEBUI_SECRET_KEY` | Override in production |
| OWI admin name/email/password | Bootstrap admin account for OpenWebUI | e.g., `Admin User` / `admin@example.com` / strong password |

> **IMPORTANT:** If the user provides an existing `backend/.env` file or KB server `.env` file, extract keys from those files as defaults, but always confirm via `askQuestions`. API keys found in existing `.env` files should be offered as pre-filled defaults in the questions.

### 0.4 — Feature Toggles

| Question | Purpose | Default |
|----------|---------|---------|
| Enable signup? | `SIGNUP_ENABLED` | `true` |
| Enable dev mode? | `DEV_MODE` | `true` for test, `false` for production |
| Enable Ollama? | Adds `--profile ollama` to compose | `false` |
| Existing data? | Is this server replacing an old LAMB installation with data to migrate? | `yes` or `no`. If yes, see Phase 4.6. |

---

## Phase 1: Create the Hetzner Server

### 1.1 — Check SSH Keys

```bash
hcloud ssh-key list
```

If no key matches the local machine, add it:

```bash
# List local public keys
ls ~/.ssh/*.pub

# Add to Hetzner
hcloud ssh-key create --name "my-key-name" --public-key-from-file ~/.ssh/id_ed25519.pub
```

> **Insight:** Use MD5 fingerprints to match local keys to hcloud keys: `ssh-keygen -lf ~/.ssh/id_ed25519.pub -E md5`

### 1.2 — Check Available Server Types

```bash
hcloud server-type list
```

### 1.3 — Create the Server

```bash
hcloud server create \
  --name <server-name> \
  --type <server-type> \
  --image ubuntu-24.04 \
  --location <location> \
  --ssh-key <ssh-key-name-1> \
  --ssh-key <ssh-key-name-2> \
  --label project=lamb \
  --label environment=production
```

> **Insight:** Use `--ssh-key` multiple times to add more than one SSH key (e.g., the agent's own key + a teammate's key). All specified keys will be added to `/root/.ssh/authorized_keys` on the server. When the `lamb` user is created in Phase 2.2, those same keys are copied to the `lamb` user's authorized_keys.

Note the IPv4 address from the output. The agent should report it to the user.

---

## Phase 2: Install Dependencies on the Server

SSH as root:

```bash
ssh root@<server-ip>
```

### 2.1 — Install Docker + Docker Compose

```bash
apt-get update -qq && \
apt-get install -y -qq curl && \
curl -fsSL https://get.docker.com | sh
```

Verify:

```bash
docker --version
docker compose version
```

Expected: Docker 29+ and Docker Compose v5+.

### 2.2 — Create `lamb` User

Create a non-root user with Docker access and passwordless sudo:

```bash
useradd -m -s /bin/bash lamb && \
usermod -aG docker,sudo lamb && \
mkdir -p /home/lamb/.ssh && \
cp /root/.ssh/authorized_keys /home/lamb/.ssh/ && \
chown -R lamb:lamb /home/lamb/.ssh && \
echo "lamb ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/lamb
```

Verify:

```bash
id lamb           # should show uid, gid, groups=lamb,sudo,docker
groups lamb       # should include docker and sudo
```

Test Docker access as `lamb`:

```bash
su - lamb -c "docker ps"
```

> **Insight:** All subsequent steps (clone, env setup, compose) should be done as the `lamb` user, NOT root. 

---

## Phase 3: Clone the Repository

SSH as `lamb`:

```bash
ssh lamb@<server-ip>
```

Clone into `/opt/lamb`:

```bash
sudo mkdir -p /opt/lamb
sudo chown lamb:lamb /opt/lamb
git clone https://github.com/Lamb-Project/lamb.git /opt/lamb
```

> **Insight:** If the repo is private or the user wants a specific branch, ask. Default is `main` from the public repo.

---

## Phase 4: Create the `.env` File

The `.env` file lives at `/opt/lamb/.env` (same directory as `docker-compose.next.yaml`).

### 4.1 — Required Variables (compose fails if missing)

These MUST be set. The compose file uses `${VAR?error message}` syntax, so missing vars cause immediate failure.

| Variable | Affected Service | Example Value |
|----------|-----------------|---------------|
| `LAMB_WEB_HOST` | lamb | `https://lamb.example.com` |
| `LAMB_BACKEND_HOST` | lamb | `http://lamb:9099` (Docker service name, not domain) |
| `LAMB_BEARER_TOKEN` | lamb | Strong random string |
| `LAMB_DB_PATH` | lamb | `/data/lamb` (path INSIDE container) |
| `OWI_BASE_URL` | lamb | `http://openwebui:8080` (Docker service name) |
| `OWI_PATH` | lamb | `/data/openwebui` (path INSIDE container) |
| `OPENAI_BASE_URL` | lamb | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | lamb | `gpt-4o-mini` (or user's custom model) |
| `SIGNUP_SECRET_KEY` | lamb | Strong random string |
| `OWI_ADMIN_NAME` | lamb | `Admin User` |
| `OWI_ADMIN_EMAIL` | lamb | `admin@example.com` |
| `OWI_ADMIN_PASSWORD` | lamb | Strong password |

### 4.2 — Caddy/TLS Variables (required for production overlay)

| Variable | Affected Service | Example Value |
|----------|-----------------|---------------|
| `CADDY_EMAIL` | caddy | `admin@example.com` |
| `LAMB_PUBLIC_HOST` | caddy | `lamb.example.com` |
| `OWI_PUBLIC_HOST` | caddy | `owi.lamb.example.com` |

> **Insight:** `LAMB_PUBLIC_HOST` and `LAMB_WEB_HOST` are often the same hostname, but the former is used by Caddy for TLS routing and the latter by LAMB backend for redirect/callback URLs. The agent should ask for them separately but note they're typically the same value (one with `https://`, one without).

### 4.3 — KB Embeddings Variables

| Variable | Affected Service | Example (OpenAI) | Example (Ollama) |
|----------|-----------------|-------------------|-------------------|
| `EMBEDDINGS_VENDOR` | kb | `openai` | `ollama` |
| `EMBEDDINGS_MODEL` | kb | `text-embedding-3-large` | `nomic-embed-text` |
| `EMBEDDINGS_APIKEY` | kb | Same as `OPENAI_API_KEY` | (empty or Ollama key) |
| `EMBEDDINGS_ENDPOINT` | kb | `https://api.openai.com/v1` | `http://ollama:11434` |

### 4.4 — Optional but Recommended

```bash
OPENAI_API_KEY=sk-...           # if using OpenAI
OPENAI_MODELS=gpt-4o-mini,gpt-4o
LAMB_KB_SERVER=http://kb:9090   # default, can omit
LAMB_KB_SERVER_TOKEN=change-me  # should match KB's LAMB_API_KEY
LTI_SECRET=change-me
SIGNUP_ENABLED=true
DEV_MODE=false                  # false for production
GLOBAL_LOG_LEVEL=WARNING
WEBUI_SECRET_KEY=change-me      # important for production sessions
```

### 4.5 — Write the File

The agent should construct the `.env` from the collected answers and write it to the server:

```bash
cat > /opt/lamb/.env << 'ENVEOF'
# ... all variables ...
ENVEOF
```

> **Insight:** Use single-quoted `'ENVEOF'` (heredoc delimiter) to prevent shell variable expansion inside the file content. This is critical when the values contain `$` signs or backticks.

### 4.6 — Key Insights for the Agent

- **`LAMB_BACKEND_HOST`** is an INTERNAL Docker network URL (`http://lamb:9099`), NOT the public domain. The `lamb` part is the Docker Compose service name.
- **`OWI_BASE_URL`** likewise uses the Docker service name: `http://openwebui:8080`.
- **`LAMB_DB_PATH`** and **`OWI_PATH`** are paths INSIDE the container, not on the host. The defaults (`/data/lamb`, `/data/openwebui`) map to Docker named volumes.
- **`OPENAI_MODEL`** — if the user's existing `.env` has a non-standard model name (e.g., `gpt-5-mini`), use it. Don't second-guess; the user may have a custom endpoint.
- **API key reuse** — The user may want the same key for both `OPENAI_API_KEY` (lamb service) and `EMBEDDINGS_APIKEY` (kb service), or different keys. Ask explicitly.
- **`DEV_MODE`** — Set to `false` for real production, `true` for test/staging instances.

---

## Phase 4.5: Verify DNS Resolution (GATE — DO NOT SKIP)

> **CRITICAL:** This is a hard gate. If DNS does not resolve correctly, the stack WILL fail to obtain TLS certificates and the deployment will be broken. Do NOT proceed to Phase 5 until DNS checks pass.

### 4.5.1 — What the agent knows by now

At this point the agent has:
- The server's **IPv4 address** (from Phase 1.3)
- The **`LAMB_PUBLIC_HOST`** (e.g., `lamb.example.com`) — from Phase 0.2 / `.env`
- The **`OWI_PUBLIC_HOST`** (e.g., `owi.lamb.example.com`) — from Phase 0.2 / `.env`

### 4.5.2 — Check DNS resolution

Run from the agent's local machine (not the server):

```bash
dig +short <LAMB_PUBLIC_HOST>
dig +short <OWI_PUBLIC_HOST>
```

Or equivalently:

```bash
host <LAMB_PUBLIC_HOST>
host <OWI_PUBLIC_HOST>
```

### 4.5.3 — Evaluate results

| DNS result | Action |
|------------|--------|
| Both domains resolve to the server's IPv4 | ✅ Proceed to Phase 5 |
| One or both domains resolve to a **different IP** | 🛑 **STOP.** Tell the user: *"The domain(s) `<list>` currently resolve to `<old-ip>`, but the server is at `<new-ip>`. Please update the DNS A records for these domains before I can continue."* Offer to update DNS if the Namecheap skill or equivalent is available and the user has credentials. |
| One or both domains return **NXDOMAIN** (no records) | 🛑 **STOP.** Tell the user: *"The subdomain(s) `<list>` don't exist in DNS yet. Please create A records pointing to `<new-ip>` before I can continue."* Offer to help if tools are available. |
| DNS returns **multiple A records** (load balancing / round-robin) | ⚠️ Warn the user. Multiple A records mean Caddy's TLS challenge may hit a different server. Proceed only if the user confirms all IPs point to the same server. |

### 4.5.4 — If DNS is correct, double-check TTL

If the user just updated DNS, check if the old records might still be cached:

```bash
dig +short <domain> @8.8.8.8
```

If Google's resolver (8.8.8.8) returns the new IP, propagation is complete. If it returns the old IP, wait and retry (TTL is typically 1800s — check with `dig <domain>` for the exact TTL value).

### 4.5.5 — DNS check example

```bash
# Server IP (from Phase 1)
SERVER_IP="178.104.231.37"

# Check both domains
LAMB_IP=$(dig +short lamb.example.com)
OWI_IP=$(dig +short owi.lamb.example.com)

if [ "$LAMB_IP" != "$SERVER_IP" ]; then
  echo "FAIL: lamb.example.com → $LAMB_IP (expected $SERVER_IP)"
  exit 1
fi
if [ "$OWI_IP" != "$SERVER_IP" ]; then
  echo "FAIL: owi.lamb.example.com → $OWI_IP (expected $SERVER_IP)"
  exit 1
fi
echo "OK: Both domains resolve to $SERVER_IP"
```

> **Insight:** The agent MUST NOT proceed to Phase 5 until both domains resolve correctly. TLS certificates (Let's Encrypt via Caddy) require DNS to point to the server — without correct DNS, Caddy will fail the ACME challenge and the deployment will be unreachable over HTTPS (and may not start cleanly).

---

## Phase 4.6: Migrate Existing Data (GATE — Conditional)

> **Only execute this phase if the user answered `yes` to "Existing data?" in Phase 0.4. If this is a fresh server with no prior data, skip to Phase 5.**

If the server previously ran LAMB (old `docker-compose.yaml` stack), the old data lives at `/opt/lamb/lamb_v4.db`, `/opt/lamb/open-webui/backend/data/`, and `/opt/lamb/lamb-kb-server-stable/backend/data/`. The new stack uses named Docker volumes instead — the data must be copied across before launch.

Follow the step-by-step guide in **`Documentation/slop-docs/migrating-to-lamb-next.md`**. The migration covers:

1. Stopping the old stack
2. Creating named volumes with `docker compose up --no-start`
3. Copying the LAMB database into `lamb-data`
4. Copying OpenWebUI data into `openwebui-data`
5. Copying KB server data into `kb-data`
6. Verifying the copied data

> **Insight:** The `.env` file must already exist (Phase 4) before running the migration. The old project path is the same `/opt/lamb` — the migration copies data from the host filesystem into the new named volumes. Original files are not modified.

---

## Phase 5: Launch the Stack

### 5.1 — Pull Images and Start (Production with TLS)

```bash
cd /opt/lamb
docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml up -d
```

> **Note:** The first run downloads ~3-4 GB of Docker images. This may take several minutes. The agent should run this in async mode with a generous timeout (≥300s).

### 5.2 — Without TLS (Test/Dev, port-based access)

```bash
docker compose -f docker-compose.next.yaml up -d
```

### 5.3 — With Ollama (local LLM inference)

```bash
docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml --profile ollama up -d
```

---

## Phase 6: Verify the Deployment

### 6.1 — Check Container Status

```bash
cd /opt/lamb
docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml ps
```

All services should show `Up` and `healthy`:

| Container | Expected Status |
|-----------|----------------|
| `lamb-caddy-1` | Up (if using prod overlay) |
| `lamb-lamb-1` | Up (healthy) |
| `lamb-kb-1` | Up (healthy) |
| `lamb-openwebui-1` | Up (healthy) |

### 6.2 — Check Logs

```bash
docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml logs -f --tail=50
```

Look for:
- Caddy: `serving initial configuration` (TLS certs obtained automatically on first HTTPS request)
- Lamb: `Uvicorn running on http://0.0.0.0:9099`
- OpenWebUI: `Uvicorn running on http://0.0.0.0:8080`
- KB: `Uvicorn running on http://0.0.0.0:9090`

### 6.3 — Verify HTTPS

Caddy obtains Let's Encrypt certificates on the first HTTPS request. Until DNS propagates and a request hits the server, certificates won't be issued. This is normal.

Once DNS resolves, visit:
- `https://lamb.example.com` — should show the LAMB creator interface
- `https://owi.lamb.example.com` — should show the OpenWebUI chat interface

---

## Phase 7: Day-to-Day Operations (Cheatsheet)

### Stop the stack
```bash
cd /opt/lamb && docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml down
```

### Update images and restart
```bash
cd /opt/lamb && docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml pull && docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml up -d
```

### View logs
```bash
cd /opt/lamb && docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml logs -f lamb
```

### Restart a single service
```bash
cd /opt/lamb && docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml restart lamb
```

---

## Phase 8: Tear Down

### Delete the server
```bash
hcloud server delete <server-name>
```

### Delete by label (bulk cleanup)
```bash
hcloud server delete --selector project=lamb
hcloud server delete --selector temporary=true
```

---

## Appendix A: Complete `.env` Template

```bash
# ============================================================================
# LAMB NEXT — Production .env
# ============================================================================

# --- Required ---
LAMB_WEB_HOST=https://lamb.example.com
LAMB_BACKEND_HOST=http://lamb:9099
LAMB_BEARER_TOKEN=<strong-random-string>
LAMB_DB_PATH=/data/lamb
OWI_BASE_URL=http://openwebui:8080
OWI_PATH=/data/openwebui
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
SIGNUP_SECRET_KEY=<strong-random-string>
OWI_ADMIN_NAME=Admin User
OWI_ADMIN_EMAIL=admin@example.com
OWI_ADMIN_PASSWORD=<strong-password>

# --- Caddy / TLS (production overlay) ---
CADDY_EMAIL=admin@example.com
LAMB_PUBLIC_HOST=lamb.example.com
OWI_PUBLIC_HOST=owi.lamb.example.com

# --- KB Embeddings ---
EMBEDDINGS_VENDOR=openai
EMBEDDINGS_MODEL=text-embedding-3-large
EMBEDDINGS_APIKEY=sk-...
EMBEDDINGS_ENDPOINT=https://api.openai.com/v1

# --- Optional / Tweaks ---
OPENAI_MODELS=gpt-4o-mini,gpt-4o
LAMB_KB_SERVER=http://kb:9090
LAMB_KB_SERVER_TOKEN=change-me
LTI_SECRET=change-me
SIGNUP_ENABLED=true
DEV_MODE=false
GLOBAL_LOG_LEVEL=WARNING
WEBUI_SECRET_KEY=change-me
```

## Appendix B: Architecture Reference

| Service | Internal Port | Public URL (via Caddy) | Docker Image |
|---------|--------------|------------------------|--------------|
| `lamb` | 9099 | `https://lamb.example.com` | `ghcr.io/lamb-project/lamb:latest` |
| `kb` | 9090 | `https://lamb.example.com/kb/*` (proxied by Caddy) | `ghcr.io/lamb-project/lamb-kb:latest` |
| `openwebui` | 8080 | `https://owi.lamb.example.com` | `ghcr.io/lamb-project/openwebui:latest` |
| `caddy` | 80, 443 | Routes all traffic | `caddy:2.8` |

**Caddy routing (from `Caddyfile.next`):**
- `lamb.example.com/creator/*` → `lamb:9099`
- `lamb.example.com/api/*` → `lamb:9099`
- `lamb.example.com/lamb/*` → `lamb:9099` (strip prefix)
- `lamb.example.com/kb/*` → `kb:9090` (strip prefix)
- `lamb.example.com/*` (everything else) → `lamb:9099` (SPA frontend)
- `owi.lamb.example.com` → `openwebui:8080`
- Old `/openwebui/*` paths on main domain → 301 redirect to OWI subdomain

## Appendix C: Known Gotchas

1. **Docker Compose version:** The `docker compose` (V2, no hyphen) command is required. The old `docker-compose` (V1) won't work. The Docker install script installs the Compose plugin by default.

2. **`.env` file location:** Must be in the same directory as `docker-compose.next.yaml` (`/opt/lamb/.env`). Docker Compose reads it automatically when running from that directory.

3. **Required variable failures:** Missing `?Set VARNAME` variables cause `docker compose` to fail with a clear error message. This is a fast-fail mechanism — the agent should double-check all required vars before running compose.

4. **TLS certificate timing:** Caddy obtains Let's Encrypt certificates on the first HTTPS request, not at startup. Until DNS propagates and port 443 is reachable from the internet, certificates won't be issued. The agent should NOT panic if certificates aren't present immediately.

5. **OpenWebUI startup race:** The `lamb` service has `depends_on: openwebui: condition: service_healthy`. OpenWebUI may take 30-60 seconds on first boot to initialize its database. The healthcheck prevents the race.

6. **Memory constraints:** With 4 GB RAM (cpx22), running all 4 containers (lamb + kb + openwebui + caddy) leaves little headroom. If the user reports crashes, upgrade to cpx32 (8 GB) or disable unused services.

7. **`DEV_MODE=true` implications:** When `DEV_MODE=true`, the backend exposes additional debug/admin endpoints. Set to `false` for any internet-facing production deployment.

8. **SSH into the server as `lamb`:** The `lamb` user has passwordless sudo and Docker access. For security, the agent should prefer using the `lamb` user for all operations after initial setup, avoiding root where possible.

9. **DNS is a hard prerequisite for TLS:** Caddy requires DNS to be correctly pointed at the server before it can obtain Let's Encrypt certificates. Launching the stack with incorrect DNS will result in TLS failures. Always verify DNS resolution (Phase 4.5) before starting the stack. If using the production overlay (`docker-compose.next.prod.yaml`), missing or incorrect DNS will cause Caddy to fail the ACME challenge and the site will be unreachable over HTTPS.

## Appendix D: Agent Workflow Checklist

The agent should follow this sequence and check off each step:

- [ ] **0.1** — Ask server type, location, name
- [ ] **0.2** — Ask main domain, OWI domain, ACME email
- [ ] **0.3** — Ask API keys, secrets, model names
- [ ] **0.4** — Ask feature toggles (signup, dev mode, Ollama), existing data
- [ ] **1.1** — Check/register SSH key in Hetzner
- [ ] **1.3** — Create server, capture IPv4
- [ ] **2.1** — SSH as root, install Docker + Compose
- [ ] **2.2** — Create `lamb` user with Docker + sudo access
- [ ] **3** — SSH as `lamb`, clone repo to `/opt/lamb`
- [ ] **4** — Create `/opt/lamb/.env` with all collected variables
- [ ] **4.5** — Verify DNS: both LAMB_PUBLIC_HOST and OWI_PUBLIC_HOST resolve to server IP (GATE — STOP if incorrect)
- [ ] **4.6** — (If existing data) Migrate old data to named volumes following migration doc
- [ ] **5** — Run `docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml up -d`
- [ ] **6.1** — Verify all containers are Up and healthy
- [ ] **6.2** — Check logs for startup errors
- [ ] **6.3** — Report access URLs to user
