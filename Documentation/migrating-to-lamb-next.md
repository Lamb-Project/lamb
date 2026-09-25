# Official LAMB 0.6 → 0.7 upgrade: migrate persistent data

**An upgrade requires a stopped-data copy, not just `git pull`.** Version 0.7 uses
named Docker volumes. Starting it without migration can present an empty installation.
Use `scripts/migrate_06_to_07.py` as the standard copy and verification procedure.
This guide also applies to older bind-mounted installations after reviewing their paths.

## 1. Preserve the rollback environment before upgrading

Schedule downtime. Stop native processes, ingestion jobs, scripts and containers that
can write any source store. Keep them stopped throughout migration and verification.
Do not run two installations against the same database.

Before replacing code or configuration, retain:

- The exact old Git revision and any local changes, or a full copy of the old checkout.
- Old Compose files, resolved configuration, `.env`, `backend/.env` and service-specific
  configuration. Protect this backup: resolved Compose configuration contains secrets.
- Exact old container image IDs/digests and an image archive (`docker image save`) if
  the images cannot otherwise be retrieved. A moving `latest` tag is not a rollback pin.
- A stopped backup of **all** persistent stores, including SQLite `-wal`, `-shm` and
  `-journal` files where present. Keep the original stores untouched.
- Baseline application counts and sample IDs for users, organisations, assistants,
  chats, KB collections/files and libraries. Retain a known RAG question and its source.

Use your actual legacy Compose files and project name to stop the old stack:

```bash
docker compose -p OLD_PROJECT -f /path/to/saved-old-compose.yaml stop
```

Do not use `down -v`, delete old files, prune rollback images, or checkpoint SQLite
against the live source to make copying convenient. The script reads sources only.
Native writers cannot be discovered reliably by Docker; stopping them is an operator
precondition. The script checks running Compose projects, overlapping bind mounts and
attached destination volumes, but cannot prevent another operator from starting them.

## 2. Prepare 0.7 code and configuration

Obtain the approved 0.7 revision in a separate checkout, retaining the old rollback
checkout. Copy `.env.next.example` to the new root `.env`, then set your existing URLs,
provider credentials, tokens, signing secrets and administrator settings. Do not replace
existing secrets with example values. The example model is `gpt-5-mini`; this does not
change model settings already stored in organisations.

The base Compose file pins `LAMB_DB_PATH=/data/lamb` and `OWI_PATH=/data/openwebui`.
The development overlay inherits these settings, keeping source bind mounts/hot reload
while persistent data stays on volumes. Open WebUI `DATA_DIR`, Library Manager
`DATA_DIR` and KB configuration are pinned to their mounted stores. KB database and
static paths are derived from its backend directory; nested named volumes cover them.
If your old LAMB tables have no `LAMB_` prefix, explicitly set `LAMB_DB_PREFIX=` in `.env`.

Do not start the new stack or use `up --no-start` before copying: Docker image contents
can populate empty volumes during container creation. The script creates volumes with
`volume-nocopy`, and refuses any destination which already contains entries.

## 3. Copy and verify all stores

Requirements: Python 3 on the host, a local Docker daemon, sufficient storage for the
originals, backups, new volumes and temporary SQLite verification copies. Pull the
helper first if needed: `docker pull python:3.12-slim`. It runs without network access;
SQLite verification uses disposable copies under the helper's `/tmp` tmpfs, so provide
enough Docker memory for the largest database and its sidecars.

Pull the intended Library Manager image and inspect its user with
`docker run --rm --entrypoint id ghcr.io/lamb-project/lamb-library-manager:latest`.
Use the reported numeric UID:GID for `--library-owner` below; do not assume host user
IDs match container IDs. Prefer your approved release image digest over `latest`.
The script assigns that ownership to Library Manager's destination; other services
use their base images' root user. Custom non-root images require an ownership review.

From the new checkout (replace LIBRARY_UID:LIBRARY_GID with those numbers):

```bash
python3 scripts/migrate_06_to_07.py \
  --source-root /absolute/path/to/old-lamb \
  --legacy-project OLD_PROJECT \
  --library-owner LIBRARY_UID:LIBRARY_GID \
  --project-name lamb-next \
  --manifest /absolute/private/backup/migration-0.7.json
```

Default source mapping:

| Source below old checkout | Destination volume suffix |
|---|---|
| `lamb_v4.db`, plus existing WAL/SHM/journal sidecars | `lamb-data` |
| `open-webui/backend/data/` | `openwebui-data` |
| `lamb-kb-server-stable/backend/data/` | `kb-data` |
| `lamb-kb-server-stable/backend/static/` | `kb-static` |
| `library-manager/data/` | `library-manager-data` |
| `backend/static/` (uploads and file RAG) | `lamb-static` |

Actual Docker names are `PROJECT_SUFFIX`, for example `lamb-next_kb-static`.
Use the same project name when starting Compose. Custom/external volume naming needs
separate review; the script targets the standard base Compose layout.

If an installation uses different paths, provide `--sources /private/sources.json`:

```json
{
  "lamb-data": "/srv/legacy/lamb_v4.db",
  "openwebui-data": "/srv/legacy/openwebui-data",
  "library-manager-data": null
}
```

Unspecified stores use defaults. `null` is allowed only for `library-manager-data` and
`lamb-static`, explicitly declaring a store never used in that installation. Never
use it to bypass a missing-path error for real data. Symlinks and special files are
rejected; supply actual regular-file/directory sources and review custom layouts.

All sources are mounted read-only. The script checks every source and every destination
before copying, compares per-file SHA-256/size inventories, and checks SQLite integrity
and table row counts on disposable copies of both sides. WAL and journal files travel
with their database, including committed rows not yet checkpointed into the main file.
SQLite verification never opens the original or destination database for writing.

Success produces `status: verified` in the private manifest and leaves services stopped.
On failure the manifest says `incomplete`; partial volumes are retained for inspection.
Do not start them or rerun into populated volumes. Correct the cause and use a fresh,
reviewed destination project/manifest, or have the administrator archive and recreate
only that failed attempt's volumes. The script never deletes data or volumes.

## 4. Start and validate

Only after the manifest is verified:

```bash
docker compose -p lamb-next -f docker-compose.next.yaml --env-file .env pull
docker compose -p lamb-next -f docker-compose.next.yaml --env-file .env up -d
docker compose -p lamb-next -f docker-compose.next.yaml --env-file .env ps
```

For development, add `-f docker-compose.next.dev.yaml` to the same commands.
Inspect effective mounts with `docker inspect`; databases must remain on named volumes,
even when a legacy `backend/.env` exists in the source bind mount.

Check health, login and the saved baseline counts/IDs for every store. Open a saved chat,
assistant, KB file and library document. Run the known RAG query and check retrieved
content. Restart the stack and repeat these checks. Retain the results alongside the
manifest. Hash equality before startup proves copying, not application compatibility.

## 5. Rollback rehearsal

Stop 0.7 with the same Compose project and files. Preserve its volumes separately for
investigation; do not copy them over the original 0.6 data. Restore the exact old code,
configuration and image pins from step 1. Start the old Compose stack against the
untouched old stores, and repeat baseline checks and the known RAG query.

**Rollback returns to the pre-migration state. Writes made after starting 0.7 are absent
from the original 0.6 files.** Plan how to retain/export those writes before a real
rollback; reverse-copying upgraded databases is not supported by this procedure.

## Release gate

Before publishing 0.7, record both a clean installation and an upgrade from a real 0.6
checkout on a Linux host. Required evidence: store preservation, restart, RAG query,
rollback rehearsal and the development-overlay/legacy-env storage check. A Docker
Desktop rehearsal or unit-test fixture does not satisfy this Linux release gate.
See [0.7 release notes](release-notes-0.7.md).
