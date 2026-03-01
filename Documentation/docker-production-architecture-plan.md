# Docker Production Architecture Plan (V2)

## Objective

Define and implement a production-first Docker architecture for LAMB that is fast to deploy, easy to upgrade, and clearly separated from development workflows.

This plan is tracked as the implementation roadmap for issue #275.

## Why We Are Changing It

Current root `docker-compose.yaml` is development-oriented and introduces production friction:

- Runtime installs/builds (`pip install`, `npm install`, frontend build)
- Long first startup and inconsistent restarts
- Dependence on source bind mounts and `LAMB_PROJECT_PATH`
- Complicated upgrade path (git pull + rebuild) instead of image pull + restart

## Target Architecture

### Core Services (default)

- `lamb` (FastAPI backend + bundled Svelte frontend)
- `kb` (LAMB knowledge base service)
- `openwebui` (Open WebUI, upstream image)
- Optional: `caddy` (TLS reverse proxy, production overlay)

### Key Principles

- Production uses prebuilt images
- No source code bind mounts in production
- Named Docker volumes for persistent data
- Simple upgrade flow:
  - `docker compose pull`
  - `docker compose up -d`

## File Strategy (Non-Disruptive Rollout)

To avoid breaking existing users, we will not replace current compose immediately.

### New/Updated Files

- `backend/Dockerfile` (new): multi-stage build, bundles Svelte frontend into backend image
- `lamb-kb-server-stable/Dockerfile` (new or hardened): production KB image
- `docker-compose.next.yaml` (new): new production-first architecture
- `docker-compose.next.prod.yaml` (new, optional): Caddy/TLS overlay
- `.github/workflows/build-images.yml` (new): build/publish images to GHCR
- `.env.next.example` (new): simplified container-oriented env template
- Documentation updates (new docs and migration notes)

### Existing Files (kept for now)

- Current `docker-compose.yaml` remains unchanged during rollout
- Current deployment docs remain valid until cutover decision

## Image and Service Model

### Image Publishing

- `ghcr.io/lamb-project/lamb` (backend + frontend bundled)
- `ghcr.io/lamb-project/lamb-kb` (KB server)
- Open WebUI from upstream:
  - `ghcr.io/open-webui/open-webui:<pinned-tag-or-digest>`

### Service Naming

- Use `lamb` as primary app service name (instead of `backend`)
- Optional temporary compatibility alias: `backend` (one release cycle)

## Data Persistence Model

Named volumes:

- `lamb-data`: LAMB SQLite data (`lamb_v4.db`)
- `kb-data`: KB database and vector index
- `openwebui-data`: Open WebUI DB and vector/cache data

Access rules:

- `openwebui` mounts `openwebui-data` read-write
- `lamb` mounts same volume read-only where needed for user sync

## Environment Model

- Remove deployment dependency on `LAMB_PROJECT_PATH`
- Use in-container paths and service DNS names
- Keep env explicit and minimal for production
- Preserve backward-compatible env behavior where possible during transition

## Implementation Phases and Task Status

Status legend:

- `TODO`
- `IN_PROGRESS`
- `BLOCKED`
- `DONE`

| ID | Phase | Task | Status | Notes |
|---|---|---|---|---|
| P1 | Dockerfiles | Create `backend/Dockerfile` multi-stage (build frontend + run backend) | TODO | Production runtime, no hot reload |
| P2 | Dockerfiles | Create/harden KB production Dockerfile | TODO | Deterministic deps |
| P3 | Compose | Add `docker-compose.next.yaml` with `lamb`, `kb`, `openwebui` | TODO | Image-based only |
| P4 | Compose | Add named volumes and healthchecks | TODO | No source mounts |
| P5 | Compose | Add optional compatibility alias (`backend`) to `lamb` | TODO | Temporary migration aid |
| P6 | Compose | Add `docker-compose.next.prod.yaml` for Caddy/TLS (optional) | TODO | Production overlay |
| P7 | Backend | Support stable frontend path inside container | TODO | Decouple from `../frontend/build` assumptions |
| P8 | Backend | Validate env defaults/requirements for container mode | TODO | `OWI_PATH`, `LAMB_DB_PATH`, host URLs |
| P9 | CI/CD | Add GHCR workflow for `lamb` and `lamb-kb` images | TODO | Buildx + cache + tags |
| P10 | CI/CD | Define release tagging policy (`edge`, semver, `latest`) | TODO | Document in workflow/docs |
| P11 | Docs | Create deployment guide for new compose stack | TODO | Install/upgrade/migrate |
| P12 | Docs | Add migration notes from current compose | TODO | Volumes, env vars, service rename |
| P13 | Validation | Cold-start benchmark and restart behavior validation | TODO | No runtime builds |
| P14 | Validation | Upgrade validation (`pull && up -d`) | TODO | Confirm no rebuild required |
| P15 | Cutover | Decide if/when root `docker-compose.yaml` is replaced | OPTIONAL | Final phase only |

## Acceptance Criteria

The new architecture is considered ready when:

- New stack starts without runtime dependency installs/builds
- Upgrade works via image pull + restart
- Data persists through recreate/update
- Service healthchecks reflect real readiness
- Existing users are not broken (parallel rollout maintained)
- Documentation is complete for install, upgrade, and migration

## Risks and Mitigations

- Drift between old/new compose:
  - Mitigation: keep explicit migration docs and compatibility window
- Open WebUI integration path assumptions:
  - Mitigation: validate shared volume mount and DB access paths early
- Env complexity:
  - Mitigation: provide minimal `.env.next.example` and clear defaults

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-03-01 | OpenCode | Initial plan draft |
