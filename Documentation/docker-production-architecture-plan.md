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
- `openwebui` (LAMB-managed Open WebUI image)
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
- `docker-compose.next.build.yaml` (new, optional): source-build overlay (currently used for local Open WebUI builds)
- `docker-compose.next.prod.yaml` (new, optional): Caddy/TLS overlay
- `.github/workflows/build-images.yml` (new): build/publish images to GHCR
- `.env.next.example` (new): documented unified root env template for compose-only deployments
- Documentation updates (new docs and migration notes)

### Existing Files (kept for now)

- Current `docker-compose.yaml` remains unchanged during rollout
- Current deployment docs remain valid until cutover decision

## Image and Service Model

### Image Publishing

- `ghcr.io/lamb-project/lamb` (backend + frontend bundled)
- `ghcr.io/lamb-project/lamb-kb` (KB server)
- `ghcr.io/lamb-project/openwebui` (LAMB-managed Open WebUI image)

Optional local source-build path for Open WebUI:

- Use `docker-compose.next.build.yaml` overlay to build from `./open-webui/Dockerfile` during local development/contributor workflows.

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

### Deployment Requirement: Optional `.env`

For `docker-compose.next.yaml`, `.env` must be optional.

- Users should be able to deploy with only the compose file(s) and no `.env` file.
- Images must include safe runtime defaults so services start without extra configuration.
- `.env` should be used only to override defaults (tokens, domains, provider keys, ports, feature toggles).
- Compose defaults are acceptable during migration, but target state is image-backed defaults (app config and/or entrypoint) to reduce compose coupling.

### Frontend Runtime Config Strategy

To preserve current deployment flexibility (`frontend/svelte-app/static/config.js` customization),
the new production image will generate `config.js` at container startup from environment variables.

- Implement a startup entrypoint script in the `lamb` container that writes runtime `config.js`.
- Do not patch compiled JS bundles; only generate/overwrite `config.js`.
- Keep defaults so local development still works when env vars are not set.
- Keep current file-based customization available as a fallback during migration.

Planned frontend runtime env vars:

- `LAMB_FRONTEND_BASE_URL` (example: `/creator` or `https://lamb.example.com/creator`)
- `LAMB_FRONTEND_LAMB_SERVER` (example: `https://lamb.example.com`)
- `LAMB_FRONTEND_OPENWEBUI_SERVER` (example: `https://owi.example.com`)
- `LAMB_ENABLE_OPENWEBUI` (default: `true`)
- `LAMB_ENABLE_DEBUG` (default: `false` in production)

## Implementation Phases and Task Status

Status legend:

- `TODO`
- `IN_PROGRESS`
- `BLOCKED`
- `DONE`
- `CANCELLED`

| ID | Phase | Task | Status | Notes |
|---|---|---|---|---|
| P1 | Dockerfiles | Create `backend/Dockerfile` multi-stage (build frontend + run backend) | DONE | Added `backend/Dockerfile` + root `.dockerignore` |
| P2 | Dockerfiles | Create/harden KB production Dockerfile | DONE | Hardened `lamb-kb-server-stable/Dockerfile` + KB `.dockerignore` |
| P3 | Compose | Add `docker-compose.next.yaml` with `lamb`, `kb`, `openwebui` | DONE | Added image-only compose with single root `.env` model |
| P4 | Compose | Add named volumes and healthchecks | DONE | Named volumes added; healthchecks pending per-image (partially covered in Dockerfiles) |
| P5 | Compose | Add optional compatibility alias (`backend`) to `lamb` | CANCELLED | Not needed for new deployment path |
| P6 | Compose | Add `docker-compose.next.prod.yaml` for Caddy/TLS (optional) | DONE | Added `docker-compose.next.prod.yaml` + `Caddyfile.next` |
| P7 | Backend | Support stable frontend path inside container | TODO | Decouple from `../frontend/build` assumptions |
| P8 | Backend | Validate env defaults/requirements for container mode | TODO | `OWI_PATH`, `LAMB_DB_PATH`, host URLs |
| P8a | Backend/Frontend | Add entrypoint to generate frontend `config.js` from env vars | TODO | Runtime config without image rebuild |
| P8b | Backend/Frontend | Define and document frontend runtime env vars | TODO | `LAMB_FRONTEND_*` + feature flags |
| P8c | Runtime Config | Move critical defaults from compose to image runtime defaults | TODO | `.env` optional, compose used for overrides only |
| P9 | CI/CD | Add GHCR workflow for `lamb` and `lamb-kb` images | TODO | Buildx + cache + tags |
| P10 | CI/CD | Define release tagging policy (`edge`, semver, `latest`) | TODO | Document in workflow/docs |
| P11 | Docs | Create deployment guide for new compose stack | TODO | Install/upgrade/migrate + runtime frontend env config |
| P12 | Docs | Add migration notes from current compose | TODO | Volumes, env vars, service rename |
| P13 | Validation | Cold-start benchmark and restart behavior validation | TODO | No runtime builds |
| P14 | Validation | Upgrade validation (`pull && up -d`) | TODO | Confirm no rebuild required |
| P15 | Cutover | Decide if/when root `docker-compose.yaml` is replaced | OPTIONAL | Final phase only |

## Unified `.env` Documentation Notes

To keep deployment simple, `.env.next.example` now documents a unified root `.env` model for `docker-compose.next.yaml`.

- Variable descriptions are aligned with existing `backend/.env.example` and `lamb-kb-server-stable/backend/.env.example` semantics.
- `docker-compose.next.yaml` maps key backend and KB runtime variables explicitly via `${VAR:-default}` so users can deploy with a single `.env` file.
- Goal: users only need the compose file(s) to deploy; `.env` is optional and used to override defaults.
- Current state: most defaults are expressed in compose interpolation.
- Target state: defaults move into image runtime config (entrypoint/app defaults), with compose primarily passing overrides.

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

## P2 Validation Notes

`lamb-kb-server-stable/Dockerfile` builds successfully after hardening and rename from `Dockerfile.server`.

- Rename note: `Dockerfile.server` did not appear to be used in the main root deployment path (`docker-compose.yaml`), so we renamed it to the canonical `Dockerfile` to make the production image path explicit and reduce ambiguity.
- Runtime now starts with `uvicorn` (no `reload=True`) and includes container healthcheck (`/health`).
- Build is deterministic through wheel building/install flow, but still very heavy.
- No blocking build errors were found during P2 validation.

## KB Image Size and Build Time Analysis (P2)

Observed image size for `lamb-kb-p2-test` is approximately 12.82 GB.

Main reasons this image is large and slow to build:

- Heavy ML stack from KB requirements, especially `sentence-transformers` and transitive `torch` dependencies.
- CUDA-enabled Torch dependency chain pulls many large `nvidia-*` wheels (`nvidia-cudnn-cu12`, `nvidia-cublas-cu12`, `nvidia-cusparse-cu12`, `nvidia-nccl-cu12`, etc.).
- Additional large packages (`onnxruntime`, `chromadb`, `transformers`, `scipy`, `scikit-learn`, `pandas`, `numpy`) increase wheel download/install time.

Important layer-level observation from image history:

- The runtime contains a large `COPY /wheels` layer (~4.38 GB) plus the installed Python packages layer (~8.3 GB), which makes total image size significantly larger.

Optimization ideas for later phases:

- Prefer CPU-only `torch` builds for default deployments unless GPU support is explicitly required.
- Split KB requirements into minimal/core vs optional extras (GPU, advanced document parsing, cloud integrations).
- Rework wheel install flow to avoid persisting a large intermediate wheels layer in runtime image.
- Pin heavy dependency families and evaluate alternatives for large optional integrations.

## P3/P4 Compose Design Notes

`docker-compose.next.yaml` is now aligned to compose-only deployment with a single root `.env` file.

- Removed per-service `env_file` references to avoid requiring repository-specific `.env` files.
- Runtime configuration is centralized in `environment:` using `${VAR:-default}` interpolation.
- Default deployment path uses prebuilt images for all services (`lamb`, `kb`, `openwebui`).
- Added `docker-compose.next.build.yaml` as an optional source-build overlay for Open WebUI (for contributors or custom image builds).

Resulting deployment modes:

- Binary/compose-only: `docker compose -f docker-compose.next.yaml --env-file .env up -d`
- Source-build overlay (optional): `docker compose -f docker-compose.next.yaml -f docker-compose.next.build.yaml --env-file .env up -d`

## P6 Production Overlay Notes

Optional production overlay has been added:

- `docker-compose.next.prod.yaml` provides a Caddy TLS/reverse-proxy service.
- `Caddyfile.next` routes to new service names (`lamb`, `kb`, `openwebui`) and supports env-based host/domain configuration.
- Overlay uses these env vars from root `.env`: `CADDY_EMAIL`, `LAMB_PUBLIC_HOST`, `OWI_PUBLIC_HOST`.

Production run command:

- `docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml --env-file .env up -d`

## Migration Strategy for Existing Deployments

Backward compatibility for old compose service names is no longer planned in the new stack.

- No `backend` alias is required in `docker-compose.next.yaml`.
- Migration focus is data continuity: map existing SQLite and service data into the new named volumes.
- Key migration paths:
  - LAMB DB (`lamb_v4.db`) -> `lamb-data`
  - Open WebUI data directory (`webui.db` and vector/cache data) -> `openwebui-data`
  - KB database/vector data -> `kb-data`
- P12 documentation must include explicit copy/mount instructions for these paths.

## Acceptance Criteria

The new architecture is considered ready when:

- New stack starts without runtime dependency installs/builds
- Upgrade works via image pull + restart
- Data persists through recreate/update
- Service healthchecks reflect real readiness
- Existing users are not broken (parallel rollout maintained)
- Documentation is complete for install, upgrade, and migration
- `docker-compose.next.yaml` works without `.env` file (optional overrides only)

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
| 2026-03-01 | LAMB Team | Completed P2 with hardened KB production Dockerfile |
| 2026-03-01 | LAMB Team | Completed P3 with new `docker-compose.next.yaml` and `.env.next.example` |
| 2026-03-01 | LAMB Team | Completed P4 base volume model in `docker-compose.next.yaml` |
| 2026-03-01 | LAMB Team | Switched `docker-compose.next.yaml` to single root `.env` pattern (no per-service `env_file`) |
| 2026-03-01 | LAMB Team | Added `docker-compose.next.build.yaml` optional overlay for local Open WebUI source builds |
| 2026-03-01 | LAMB Team | Completed P6 with `docker-compose.next.prod.yaml` and `Caddyfile.next` |
| 2026-03-01 | LAMB Team | Expanded `.env.next.example` to a documented unified root env file aligned with backend/KB examples |
| 2026-03-01 | LAMB Team | Added explicit requirement that `.env` must be optional and defaults should be image-backed |
| 2026-03-01 | LAMB Team | Cancelled P5 alias task and defined migration-by-volume strategy for legacy deployments |
| 2026-03-01 | LAMB Team | Renamed KB `Dockerfile.server` to `Dockerfile` to remove deployment ambiguity |
| 2026-03-01 | LAMB Team | Added P1 validation warnings and image size/build-time analysis |
| 2026-03-01 | LAMB Team | Added P2 validation notes and KB image size/build-time analysis |
| 2026-03-01 | LAMB Team | Added `git` to frontend build stage and cleared the missing-git warning |
| 2026-03-01 | LAMB Team | Added runtime frontend `config.js` strategy via entrypoint and env vars |
