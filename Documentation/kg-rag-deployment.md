# KG-RAG / Semantic-Graph Deployment Guide

This guide explains how to bring up the LAMB stack with the **KG-RAG (Knowledge-Graph RAG)** feature enabled — the Neo4j-backed semantic-graph layer that augments vector retrieval in the new KB server.

KG-RAG is **optional and off by default**. With `KG_RAG_ENABLED=false` the graph endpoints are never mounted and every existing RAG flow (simple, hierarchical, single-file, context-aware) behaves exactly as before. You only get the extra services and behaviour when you explicitly opt in as described below.

> Scope: this targets the development `docker-compose.yaml` at the repository root, which is the compose file that wires the new KB server (`kb-v2`, port 9092) and Neo4j. It bind-mounts the checkout into every container and installs dependencies on first start.

---

## What KG-RAG adds to the stack

| Service | Port | Role with KG-RAG | Started by |
|---|---|---|---|
| `kb-v2` (new KB server) | 9092 | Concept extraction, graph write, graph-augmented query | always (base stack) |
| `neo4j` | 7474 (HTTP), 7687 (Bolt) | Semantic graph + curation audit log | **only `--profile kg-rag`** |

`kb-v2` always runs, but it only mounts the `/graph` + `/benchmarks` routers and talks to Neo4j when `KG_RAG_ENABLED=true`. Neo4j itself sits behind the `kg-rag` Compose profile, so the base `docker compose up` never starts it.

---

## Prerequisites

- Docker Engine 24+ and the Docker Compose v2 plugin (`docker compose version`).
- This repository checked out on the **`feat/kg-rag-new-kbserver-arch`** branch.
- An OpenAI-compatible API key if you want concept extraction to actually run (extraction is an LLM call). Without a key the stack still starts; ingestion just skips graph writes / logs an extraction error.
- ~2 GB free RAM for Neo4j (default heap 1 GB + page cache).

---

## Step 1 — Create the root `.env`

From the repository root:

```bash
cp .env.example .env
```

Edit `.env` and set, at minimum:

```bash
# REQUIRED — absolute path to THIS checkout on the host
LAMB_PROJECT_PATH=/absolute/path/to/lamb

# Turn the feature on
KG_RAG_ENABLED=true

# Pick a Neo4j password (this initialises the database on first boot)
KG_RAG_NEO4J_PASSWORD=lamb-kg-rag-password

# Key used for concept extraction at ingest time (optional but recommended)
KG_RAG_OPENAI_API_KEY=sk-...
```

Everything else has working defaults (see the comments in `.env.example`). The KG-RAG block controls graph behaviour:

| Variable | Default | Meaning |
|---|---|---|
| `KG_RAG_ENABLED` | `false` | Master switch. Must be `true` for any graph behaviour. |
| `KG_RAG_INDEX_ON_INGEST` | `false` | If `true`, run extraction + graph write on every ingestion job (slower). If `false`, ingest fast and back-populate later via the migrate API. |
| `KG_RAG_OPENAI_API_KEY` | empty | Fallback key for extraction (per-request keys from LAMB are preferred). |
| `KG_RAG_CHAT_MODEL` | `gpt-4o-mini` | Model for graph reasoning. |
| `KG_RAG_EXTRACTION_MODEL` | empty → chat model | Model for concept/entity extraction. |
| `KG_RAG_NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt URI (service name inside the compose network). |
| `KG_RAG_NEO4J_USER` / `KG_RAG_NEO4J_PASSWORD` | `neo4j` / `lamb-kg-rag-password` | Neo4j credentials; the DB is initialised with these. |
| `KG_RAG_GRAPH_DEPTH` | `2` | Graph traversal depth (clamped 1–4). `.env.example` ships `2`; note the kb-v2 service's bare compose fallback is `1`, so keep this line set rather than deleting it. |
| `KG_RAG_LIMIT_FACTOR` | `4` | Candidate-expansion factor (clamped 1–20). |

The same file also sets `LAMB_KB_SERVER_V2_TOKEN` and `LIBRARY_MANAGER_TOKEN`; leave the defaults unless you change them on the services too.

## Step 2 — Create `backend/.env`

The backend container loads `backend/.env` directly (`env_file:`), so it must exist. From the **repository root**:

```bash
cp backend/.env.example backend/.env
```

Set a real `OPENAI_API_KEY` (and any other provider keys) inside `backend/.env`. No KG-RAG-specific edits are needed here — the backend learns the new KB server address from `LAMB_KB_SERVER_V2` / `LAMB_KB_SERVER_V2_TOKEN`, which the compose file injects from the root `.env`.

> You do **not** need to create a `.env` for the KB servers by hand. `kb-v2` (the KG-RAG server) takes all of its config from the compose `environment:` block — it never reads a `.env` file. The legacy `kb` service auto-creates `lamb-kb-server-stable/backend/.env` from its `.env.example` on first start. Either way, the KG-RAG settings come from compose environment variables sourced from the root `.env`.

## Step 3 — Start the stack with the `kg-rag` profile

```bash
docker compose --profile kg-rag up -d
```

The `--profile kg-rag` flag is what adds the `neo4j` service. Without it, `kb-v2` starts but has no graph database to talk to.

> This assumes a clean host: ports 9099, 9092, 9090, 9091, 8080, 5173, 7474 and 7687 must be free. If a LAMB stack is already running, `up` will fail on a port conflict — bring the existing one down first (`docker compose --profile kg-rag down`) or start the new one with a distinct `COMPOSE_PROJECT_NAME` and remapped ports.

First boot is slow: the containers `pip install` / `npm build` against the bind-mounted source. Watch progress with:

```bash
docker compose --profile kg-rag ps
docker compose logs -f kb-v2
```

You can also bring up just the feature-critical services to validate KG-RAG quickly without building the frontend/OpenWebUI:

```bash
docker compose --profile kg-rag up -d neo4j kb-v2
```

## Step 4 — Verify KG-RAG is live

1. **Neo4j is healthy:**
   ```bash
   docker compose ps neo4j     # STATUS shows "healthy" (ps lists running containers; no profile flag needed)
   ```
   The Neo4j browser is at <http://localhost:7474> (log in with `KG_RAG_NEO4J_USER` / `KG_RAG_NEO4J_PASSWORD`).

2. **kb-v2 mounted the graph routers** — the startup log prints this line only when the feature is on:
   ```bash
   docker compose logs kb-v2 | grep "KG-RAG enabled"
   # → KG-RAG enabled: mounted /graph and /benchmarks routers
   ```

3. **kb-v2 is healthy and the graph surface exists:**
   ```bash
   curl -s http://localhost:9092/health        # {"status":"ok",...}
   curl -s http://localhost:9092/openapi.json | grep -o '"/graph[^"]*"' | head
   # → graph paths appear ONLY when KG_RAG_ENABLED=true
   ```
   With the feature off, `/graph` paths are absent from the OpenAPI spec (callers get a clean 404).

## Step 5 — Use it from LAMB

1. Open the frontend at <http://localhost:9099> (or the Svelte dev server at <http://localhost:5173>).
2. Create a **Knowledge Store** via the "Create Knowledge" wizard. In the Setup step, enable the **graph / `graph_enabled`** toggle and pick the extraction vendor/model. This per-store opt-in is required *in addition* to `KG_RAG_ENABLED` — the flag enables the capability, the toggle enables it for that store. Store setup is locked after creation.
3. Link Library items into the store to ingest them. If `KG_RAG_INDEX_ON_INGEST=true`, concepts are extracted and written to Neo4j during ingestion; otherwise run the migrate/back-populate action from the store's graph view.
4. Inspect and curate the graph in the store's **Graph** view (Sigma.js): approve/reject/rename/merge concepts; every edit is recorded as an audit `ChangeEvent`.
5. Attach the store to an assistant whose RAG processor is `knowledge_store_rag` to use graph-augmented retrieval at query time.

## Turning KG-RAG off again

```bash
docker compose --profile kg-rag down       # stop everything incl. Neo4j
```

Set `KG_RAG_ENABLED=false` in `.env` and start normally (`docker compose up -d`, no profile). The graph routers disappear, Neo4j is not started, and all vector RAG flows continue unchanged. Neo4j data persists in the `neo4j-data` volume for next time.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `kb-v2` log has no "KG-RAG enabled" line | `KG_RAG_ENABLED` not `true` in `.env`, or container not recreated — run `docker compose up -d --force-recreate kb-v2`. |
| `/graph` calls return 404 | Feature flag off, or you hit the legacy `kb` (9090) instead of `kb-v2` (9092). |
| kb-v2 logs Neo4j connection errors | Neo4j not started (missing `--profile kg-rag`), wrong `KG_RAG_NEO4J_URI`, or password mismatch. Confirm `docker compose ps neo4j` is healthy. |
| Ingestion is suddenly slow | `KG_RAG_INDEX_ON_INGEST=true` runs an LLM call per parent text. Set it `false` and back-populate via the migrate API. |
| Extraction silently does nothing | No OpenAI key reached the server — set `KG_RAG_OPENAI_API_KEY` or thread a per-request key from the LAMB org config. |
| `.env` changes not picked up | Compose only re-reads env on container (re)create: `docker compose up -d --force-recreate <service>` (a plain `restart` is not enough). |

See `lamb-kb-server/Documentation/` for the architecture decision records (ADR-KS-1…17) behind this design.
