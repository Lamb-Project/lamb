# LAMB security audit guidance

Target: `https://github.com/Lamb-Project/lamb`, branch `dev`.

LAMB (Learning Assistants Manager and Builder) is a GPL-3.0 web application for creating educational AI assistants and exposing learning activities through an LMS. The application includes a FastAPI backend, a Svelte Creator interface, a CLI, document services and integrations with LTI, Moodle and model providers. This guide describes the intended security boundaries; it does not assert that the implementation satisfies them.

## Threat actors and data

Consider unauthenticated internet clients, authenticated learners, creators in another organization, creators with fewer privileges, and malicious content supplied through uploads, remote URLs, LMS resources, chat messages or model/tool output. Attacker-controlled IDs, paths, filenames, MIME types, redirects, pagination cursors, serialized state and role claims must not become authority.

Protect user and organization records, student conversations and evaluations, private course materials, model-provider and LMS credentials, creator API keys, signing/encryption keys, and server files. A creator may manage their authorized resources; organization administrators have a wider organization-local scope; system administrators have intentional cross-organization powers. Reproduce privilege violations with accounts from two synthetic organizations and explain the attacker's actual privileges.

## Priority surfaces and source map

- **Authentication and authorization:** `backend/lamb/auth.py`, `auth_context.py`, `services/takeover.py`, `backend/creator_interface/`, and the OpenAI-compatible endpoints in `backend/main.py`. Check token validation, revocation, impersonation lifetime, API-key scope, disabled accounts, and object ownership on reads and writes.
- **LTI and LMS boundaries:** `backend/lamb/lti_oauth.py`, `lti_router.py`, `lti_creator_router.py`, `lti_activity_manager.py`, and `backend/lamb/moodle/`. Check signatures, role/course binding, replay handling, connection-owner binding, imported-resource access, credential storage, redirects and outgoing requests. LAMB integrates using LTI and standard Moodle web services; the Moodle server is a separate system.
- **Files and documents:** `backend/lamb/uploaded_files.py`, `private_storage.py`, `backend/lamb/aac/files.py`, `library-manager/backend/`, and `lamb-kb-server-stable/backend/`. Check traversal, symlinks, archive extraction, stored active content, parser abuse, SSRF and private/public storage separation. Trace requests through the public LAMB layer and its downstream service.
- **Agent-assisted authoring (AAC):** `backend/lamb/aac/authorization.py`, `liteshell/`, `router.py`, sessions, pending actions and result storage. Model-generated commands are untrusted. Liteshell is an application-command dispatcher, not a general operating-system shell. Check whether malicious content or forged tool output can bypass authorization, required confirmation or session ownership. Distinguish a concrete unauthorized effect from an undesirable generated answer.
- **Browser boundaries:** `frontend/svelte-app/src/`, rendered Markdown/HTML, resource URLs, charts, downloads and authentication handling. Report executable content in a realistic victim context and identify the source and sink.
- **Persistence:** database queries and migrations, export/import, session and document caches. Check SQL injection, tenant separation, stale authorization, credential leakage and unsafe deserialization.

Library Manager uses a service bearer token and trusts its authenticated caller. The public LAMB layer is responsible for user and organization authorization. Do not treat possession of a deliberately trusted service credential as an unauthenticated attack; do investigate ways an untrusted client can obtain it or cause an authorized service to act across a boundary. Likewise, intentional actions by a fully privileged server operator are not privilege escalation.

## Offline audit environment

Build from the repository root:

```sh
docker build -f .oss-scanner/Dockerfile -t lamb-oss-scanner .
docker run --rm --network none lamb-oss-scanner bash /src/.oss-scanner/offline-tests.sh
```

The complete source is at `/src`. The Dockerfile-specific ignore file keeps service source and tests that the normal deployment build excludes. Build-time networking installs dependencies and Chromium; audit-time networking is unnecessary for the regression commands below. Installed Python package versions are recorded in `/opt/venvs/*/installed.txt`.

Separate environments avoid incompatible service dependency constraints:

| Component | Working directory | Environment / command |
| --- | --- | --- |
| LAMB backend and AAC | `/src/backend` | `/opt/venvs/backend/bin/python -m pytest tests -q` |
| LAMB CLI | `/src/lamb-cli` | `/opt/venvs/backend/bin/python -m pytest tests -q` |
| Creator frontend | `/src/frontend/svelte-app` | `npm run test:unit -- --run` |
| Library Manager | `/src/library-manager` | `/opt/venvs/library/bin/python -m pytest tests -q` |
| Legacy KB unit tests | `/src/lamb-kb-server-stable/backend` | `/opt/venvs/kb/bin/python -m pytest tests/test_*.py -q` |

The image contains synthetic test credentials and writable temporary storage. It seeds an empty Open WebUI compatibility database with `user` and `auth` tables matching `backend/lamb/owi_bridge/owi_database.py` and `owi_users.py`; this avoids an indefinite import-time wait for `webui.db`. These values and tables are test fixtures, not deployment defaults or exposed production secrets. No real LMS, student data, model API account or production database is supplied. Provider/embedding/LMS behavior should use in-process mocks or a local HTTP fixture. No model weights are downloaded; tests requiring actual generation or embeddings need a deterministic substitute. The existing backend tests demonstrate ASGI transports, temporary SQLite databases and mocked external clients.

To start the backend for a local reproduction, use `cd /src/backend && python -m uvicorn main:app --host 127.0.0.1 --port 9099`. Startup alone does not provision an LMS, an Open WebUI instance, model providers or a complete multi-service deployment. The `testing/` integration suites and KB `tests/e2e/` require explicitly provisioned services and synthetic fixtures; they are not part of the offline unit-test command.

The vendored `open-webui/` source is available for tracing LAMB's integration boundary, but its independent application environment is not installed. Prioritize LAMB-specific code and integration flaws. For an upstream dependency issue, show reachable impact through LAMB and identify the upstream component; dependency version matches alone are not proof of exploitability. Features absent from the checked-out `dev` branch are outside this scan.

Expected offline skips: the five Windows QR-command cases require PowerShell, which this Linux image does not install. The Library Manager YouTube-import case can skip when the external transcript service is unavailable. These skips do not establish that those integrations work.

## Reproducers, severity and reports

Use only disposable local data. For each finding give the scanned revision, affected route/function and lines, attacker's starting privileges, prerequisites, a minimal executable reproducer, expected versus observed behavior, and confidentiality/integrity/availability impact. Preserve the authorization boundary in tests; mocking it away does not demonstrate a bypass. Separate demonstrated behavior from inferred impact.

Suggested severity: critical for broadly exploitable server code execution or unrestricted compromise of multiple organizations; high for practical account takeover, substantial cross-organization data access/modification, credential theft, or stored script execution with material victim privileges; medium for narrower data exposure or reproducible service disruption with meaningful prerequisites; low for limited hardening issues. Adjust to demonstrated reach and explain the rating. Resource exhaustion should include bounded measurements rather than unbounded stress.

Group instances sharing one root cause and repair. Keep distinct authorization boundaries separate when their fixes differ. Prefer a minimal regression test and focused patch, with any compatibility assumptions stated. Send findings privately through the configured contact; do not create public vulnerability issues or contact deployed institutions from this audit.
