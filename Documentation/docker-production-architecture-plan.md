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
| P1 | Dockerfiles | Create `backend/Dockerfile` multi-stage (build frontend + run backend) | DONE | Added `backend/Dockerfile` + root `.dockerignore` |
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

## P1 Validation Notes

`backend/Dockerfile` builds successfully, but the first build surfaced warnings worth tracking:

- The initial P1 build showed `git: not found` in frontend build; this is now fixed by installing `git` in the frontend build stage so version metadata can be captured.
- Svelte/Vite build completes, but emits multiple Svelte warnings (`state_referenced_locally`) in several components.
- Build also reports a config warning during frontend compile (`Cannot find base config file ./.svelte-kit/tsconfig.json` from `jsconfig.json`).

Remaining warnings are non-blocking for P1 because the image is produced successfully, but they should be addressed in later hardening iterations to improve build quality and reproducibility.

## Backend Image Size and Build Time Analysis (P1)

Observed image size for `lamb-backend-p1-test` is approximately 7.27 GB.

Main reason the image is large and slow to build:

- The Python dependency install layer dominates the image: ~7.13 GB in a single layer (`pip install -r requirements.txt`).

Main dependency groups driving size and build time:

- ML/compute stack: `torch`, `xgboost`, `scikit-learn`, `scipy`, `numpy`, `pandas`.
- NLP/LLM stack: `transformers`, `sentence-transformers`, `tokenizers`, `llama-index` and related plugin packages.
- CV and browser tooling: `opencv-python`, `playwright`.
- Observability and platform integrations: `ddtrace`, `chromadb` and OpenTelemetry-related dependencies.

Build-time impact factors:

- Large wheel downloads for scientific/ML packages.
- Dependency resolver backtracking across several loosely constrained transitive dependencies.
- Broad requirements set installed into one runtime image without separation by feature/profile.

Optimization ideas for later phases:

- Split requirements into core vs optional extras (ML/RAG/evaluator/testing).
- Publish slimmer runtime profiles for common production use cases.
- Pin or constrain high-backtracking dependency groups to reduce resolver time.
- Revisit heavy packages that are not required in all production deployments.

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
| 2026-03-01 | LAMB Team | Initial plan draft |
| 2026-03-01 | LAMB Team | Completed P1 with multi-stage `backend/Dockerfile` |
| 2026-03-01 | LAMB Team | Added P1 validation warnings and image size/build-time analysis |
| 2026-03-01 | LAMB Team | Added `git` to frontend build stage and cleared the missing-git warning |
