# Phase 4: File Evaluation Module — Port from LAMBA to LAMB

> **Status**: Implementation complete; **integration hardening in progress** (remaining issues tracked separately)
> **Date**: 2026-03-24 (updated 2026-03-25 — integration notes)
> **Issue**: #277 — Architecture: Activity Module System

---

## 1. Executive Summary & Objective

Phase 4 delivers the second concrete `ActivityModule` in LAMB by porting [LAMBA](https://github.com/Lamb-Project/LAMBA)'s file evaluation workflow into the module system established in Phase 1. LAMBA ran as a completely separate application that duplicated LAMB's LTI handling, user management, frontend stack, and database layer — just to add file evaluation on top of LAMB's `/v1/chat/completions` API.

This phase **eliminates that duplication** by re-implementing the same business logic as a LAMB module that:

- Fulfills the `ActivityModule` contract (12 abstract methods)
- Uses LAMB's existing JWT auth (`lamb.auth`) instead of LAMBA's in-memory LTI session cookies
- Uses raw SQL via `LambDatabaseManager` instead of LAMBA's SQLAlchemy ORM with composite keys
- Calls `run_lamb_assistant()` directly in-process instead of making HTTP requests to LAMB's completions API
- Lives in the frontend monorepo as a SvelteKit SPA (`module-file-eval`) following the `module-chat` pattern

---

## 2. Architecture Decisions

### 2.1 — Key Simplifications vs. LAMBA

| Concern | LAMBA (standalone) | LAMB Module (Phase 4) |
|---------|-------------------|----------------------|
| **LTI handling** | Own OAuth validation, session cookies | Delegates to LAMB's Unified LTI Router |
| **Auth** | In-memory session dict | LAMB JWT via `lamb.auth.create_token` / `decode_token` |
| **Database** | SQLAlchemy ORM with Moodle-scoped composite PKs | Raw SQL, integer `activity_id` FK to `lti_activities(id)` |
| **AI evaluation** | HTTP `POST /chat/completions` to LAMB | Direct `await run_lamb_assistant()` in-process |
| **Activity config** | Own `activities` table with full schema | `lti_activities.setup_config` JSON column |
| **User identity** | `(user_id, moodle_id)` composite key | `student_id` = synthetic email from `LtiActivityManager.generate_student_email()` |
| **Frontend** | Separate SvelteKit app on its own port | Monorepo package at `frontend/packages/module-file-eval/` |

### 2.2 — MVP Scope

- **No `/progress` route**: Evaluation polling is integrated into the grading dashboard (instructor view).
- **No activity CRUD endpoints**: Activity lifecycle is managed by `lti_activities` + the Unified LTI Router. The module only adds endpoints the SPA needs (submissions, grades, evaluation, sync).
- **JWT centralized**: `_create_file_eval_jwt()` lives in `FileEvalModule` (`__init__.py`) using `lamb.auth.create_token`, not duplicated per route.

### 2.3 — Integration constraints (read this when debugging)

| Topic | Rule |
|--------|------|
| **API base path** | Module HTTP routes **must** be registered on `lamb/main.py`’s FastAPI app, **not** only on the root `backend/main.py` app. The root server **mounts** `lamb_app` at `/lamb`, so only routes on the mounted app receive `/lamb/v1/modules/file_evaluation/...`. |
| **`activity_id` type** | All path/query parameters named `activity_id` are the **integer primary key** of `{LAMB_DB_PREFIX}lti_activities` (same as JWT claim `lti_activity_id`). They are **not** LTI `resource_link_id` (UUID). |
| **`LAMB_DB_PREFIX`** | Migrations format `{table_prefix}lti_activities` in FK clauses. If the prefix used when migrations ran does not match the live DB, see **§4.8** (schema repair). |
| **Student redirect URL** | `on_student_launch` / `on_instructor_launch` must include **`activity_id=<numeric id>`** in the query string. Using only `resource_link_id` breaks uploads (422: path `activity_id` must be int). |
| **i18n for `$_('fileEval.*')`** | Strings live in **`frontend/packages/ui/src/lib/locales/{en,es,ca,eu}.json`** under a top-level **`fileEval`** object (shared with other packages). |
| **Schema repair** | See **§4.8** — wrong FK target vs `LAMB_DB_PREFIX` causes `no such table: main.lti_activities` on insert. |

---

## 3. Files Created

### 3.1 — Backend Module (`backend/lamb/modules/file_evaluation/`)

| File | Responsibility | Lines | Ported from (LAMBA) |
|------|----------------|-------|---------------------|
| `__init__.py` | Exports `module = FileEvalModule()`; full `ActivityModule` implementation (migrations, routers, setup fields, LTI launch, JWT, dashboard hooks) | ~210 | New (wraps LAMB contract) |
| `migrations.py` | DDL: 3 tables + 7 indexes; `{table_prefix}` in FKs; **`repair_file_eval_schema_if_needed`** for prefix mismatch | ~115 | `db_models.py` |
| `router.py` | Single `APIRouter` (submissions, grades, evaluation, sync, etc.) | ~260 | `activities_router.py`, `submissions_router.py`, `grades_router.py` |
| `evaluator_client.py` | Score regex extraction + direct call to `run_lamb_assistant` | ~150 | `lamb_api_service.py` |
| `document_extractor.py` | PDF, DOCX, TXT text extraction | ~100 | `document_extractor.py` (near-verbatim) |
| `storage_service.py` | File storage under `uploads/file-eval/{activity_id}/` | ~70 | `storage_service.py` |
| `grade_service.py` | Grade CRUD via raw SQL, dual AI+professor model, bulk accept | ~130 | `grade_service.py` |
| `evaluation_service.py` | Background batch evaluation with status tracking, timeout handling | ~200 | `evaluation_service.py` |
| `service.py` | Submission CRUD, group join flow, dashboard stats queries; robust **`_parse_setup_config`** | ~355 | `activities_service.py` |
| `lti_passback.py` | OAuth 1.0a signed XML grade passback to Moodle | ~160 | `lti_service.py` (verbatim algorithm) |
| `schemas.py` | Pydantic v2 request/response models | ~120 | `models.py` |

### 3.2 — Database Tables

Three new tables in the `mod_file_eval_*` namespace:

```sql
-- File submissions (one per individual or group upload)
mod_file_eval_submissions
  ├── id (TEXT PK)
  ├── activity_id (INTEGER FK → `{LAMB_DB_PREFIX}lti_activities` in DDL; unqualified name in docs = conceptual)
  ├── file_name, file_path, file_size, file_type
  ├── uploaded_by, uploaded_at
  ├── group_code, group_display_name, max_group_members
  ├── student_note
  └── evaluation_status, evaluation_started_at, evaluation_error

-- Student submissions (one per student, links to file submission)
mod_file_eval_student_submissions
  ├── id (TEXT PK)
  ├── file_submission_id (TEXT FK → submissions)
  ├── student_id, activity_id
  ├── lis_result_sourcedid (for Moodle grade passback)
  ├── joined_at
  └── sent_to_moodle, sent_to_moodle_at
  └── UNIQUE(student_id, activity_id)

-- Grades (one per file submission, dual AI + professor)
mod_file_eval_grades
  ├── id (TEXT PK)
  ├── file_submission_id (TEXT FK UNIQUE → submissions)
  ├── ai_score, ai_comment, ai_evaluated_at
  ├── score, comment (professor's final grade)
  └── created_at, updated_at
```

### 3.3 — API Endpoints

All mounted under `/lamb/v1/modules/file_evaluation/`:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/activities/{id}/view` | Any | Activity view (student or instructor, role-based) |
| `POST` | `/activities/{id}/submissions` | Student | Upload file (multipart) |
| `GET` | `/activities/{id}/submissions` | Instructor | List all submissions |
| `GET` | `/submissions/me` | Student | Get own submission |
| `POST` | `/submissions/join` | Student | Join group by code |
| `GET` | `/submissions/{id}/members` | Any | List group members |
| `GET` | `/submissions/my-file/download` | Student | Download submitted file |
| `POST` | `/activities/{id}/evaluate` | Instructor | Start AI evaluation batch |
| `GET` | `/activities/{id}/evaluation-status` | Instructor | Poll evaluation progress |
| `POST` | `/grades/{submission_id}` | Instructor | Set/update professor grade |
| `POST` | `/grades/activity/{id}/accept-ai-grades` | Instructor | Bulk accept AI grades as final |
| `POST` | `/activities/{id}/grades/sync` | Instructor | Send all grades to Moodle via LTI 1.1 |

### 3.4 — Frontend Module (`frontend/packages/module-file-eval/`)

| File/Directory | Purpose |
|---------------|---------|
| `package.json` | SvelteKit 5 + TailwindCSS 4 + `@lamb/ui` workspace dependency |
| `svelte.config.js` | `adapter-static`, base path `/m/file-eval`, output `../../build/m/file-eval` |
| `vite.config.js` | TailwindCSS plugin, dev proxy to backend, port 5174 |
| `src/app.html` | HTML shell with CSP, config.js script tag |
| `src/app.css` | Tailwind import |
| `src/routes/+layout.js` | `load`: `setupI18n` + `waitLocale` before pages render (avoids “Cannot format a message without first setting the initial locale”) |
| `src/routes/+layout.svelte` | Root layout with `@lamb/ui` shell |
| `src/routes/upload/+page.svelte` | **Student view**: drag-and-drop upload, group code join, submission status, grade display |
| `src/routes/grading/+page.svelte` | **Instructor view**: stats cards, submissions table, AI evaluation with polling, inline grade editing, accept-all, Moodle sync |
| `src/lib/services/api.js` | API helper with JWT from URL query param + Bearer header |
| `src/lib/services/submissionService.js` | Upload, download, join group, get submission |
| `src/lib/services/gradingService.js` | Activity view, evaluation, grading, Moodle sync |
| `src/lib/locales/{en,es,ca,eu}.json` | Optional package-local strings (if used); primary `fileEval.*` keys are in **`@lamb/ui`** (see §2.3) |

---

## 4. Files Modified

### 4.1 — `backend/main.py`

1. **Lifespan: module schema repair (file_evaluation)** — Before applying module migrations, calls `repair_file_eval_schema_if_needed(conn, table_prefix)` from `lamb/modules/file_evaluation/migrations.py`. If `mod_file_eval_submissions` was created with FK to `lti_activities` while `LAMB_DB_PREFIX` is non-empty, SQLite cannot resolve the parent table; the repair **drops** the three `mod_file_eval_*` tables so the next migration pass recreates them with `REFERENCES {prefix}lti_activities(...)`. **This deletes submission data** in those tables (dev-safe).

2. **Lifespan: module migration runner** — After `discover_modules()`, iterates all modules calling `get_migrations()` and executes each SQL statement via `LambDatabaseManager.get_connection()`.

3. **Static file mount** — `app.mount("/m/file-eval/app", StaticFiles(...))` mirroring the `module_chat` pattern.

4. **SPA catch-all** — Serves `m/file-eval/index.html` for `/m/file-eval/*`, with static asset paths including `m/file-eval/app/`.

5. **Module HTTP routers are not registered here** for `/lamb/v1/modules/...` — see **§4.2** (`lamb/main.py`).

### 4.2 — `backend/lamb/main.py` (critical)

Activity module routers (`file_evaluation`, future modules) are **`include_router`**’d on **this** FastAPI app with prefix `/v1/modules/{module.name}`.

The root application mounts this app at **`/lamb`**, so the public paths are **`/lamb/v1/modules/file_evaluation/...`**. Registering the same routers only on the parent app would **never match** incoming `/lamb/*` requests because the mount takes precedence.

`discover_modules()` / `get_all_modules()` run at import time here so routers are attached before the server accepts traffic.

### 4.3 — `backend/lamb/modules/file_evaluation/router.py`

- **`GET /activities/{activity_id}/view`**: Ensures JWT `lti_activity_id` matches path `activity_id` when present (not only for `dashboard` tokens).
- **`POST /activities/{activity_id}/submissions`**: Same JWT/path consistency; maps `ValueError`, `sqlite3.IntegrityError`, `sqlite3.OperationalError`, and `OSError` (disk) to appropriate HTTP status codes; logs unexpected errors.

### 4.4 — `backend/lamb/modules/file_evaluation/service.py`

- **`_parse_setup_config`**: Accepts `setup_config` as `str`, `bytes`, `dict`, or `NULL`, always yielding a **`dict`** so `cfg.get(...)` never fails on unexpected SQLite types.

### 4.5 — `backend/lamb/modules/file_evaluation/__init__.py` (LTI redirects)

- **`on_student_launch`**: Redirect URL includes **`activity_id={activity['id']}`** and `resource_link_id` and `token`.
- **`on_instructor_launch`**: Same for grading URL.
- **`launch_user`**: Same pattern for both pages.

### 4.6 — `frontend/packages/module-file-eval/src/lib/services/api.js`

- **`getActivityId()`**: Prefers numeric `activity_id` query param; otherwise decodes URL `token` JWT payload and uses **`lti_activity_id`**. Does **not** use `resource_link_id` as `activity_id` (UUID breaks API paths).

### 4.7 — `frontend/packages/ui/src/lib/locales/*.json`

- Added **`fileEval`** subtree (`grading`, `upload`, `status`, etc.) so `svelte-i18n` `$_('fileEval....')` in `module-file-eval` resolves after layout load.

### 4.8 — `backend/lamb/modules/file_evaluation/migrations.py`

- **`repair_file_eval_schema_if_needed(conn, table_prefix)`**: Detects DDL where FK still references `lti_activities(` while `LAMB_DB_PREFIX` requires `{prefix}lti_activities(`; drops module tables so the next migration run recreates them. Invoked from root **`backend/main.py`** lifespan (see **§4.1**).
- **`FileEvalModule.get_migrations()`** uses **`LambDatabaseManager().table_prefix`** (fresh read) when formatting `MIGRATION_SQL` so `{table_prefix}` matches the core schema.

### 4.9 — `backend/lamb/database_manager.py`

Added two new columns to `lti_activities` (both in `CREATE TABLE` for fresh installs and as `ALTER TABLE` migrations for existing databases):

- `setup_config TEXT DEFAULT '{}'` — Stores module-specific configuration as JSON (evaluator ID, activity type, max group size, deadline, language).
- `lis_outcome_service_url TEXT` — LTI Outcome Service URL for grade passback, stored per activity.

### 4.10 — Backend Python requirements

Document extraction deps live in `requirements-base.txt` (pinned):

```
pypdf==5.1.0
python-docx==1.1.2
```

Heavy ML/RAG deps are in `requirements-ml.txt`. Install with  
`pip install -r requirements-base.txt && pip install -r requirements-ml.txt` (see `backend/requirements.txt`).

---

## 5. LTI Launch Flow

```
POST /lamb/v1/lti/launch
  │
  ├── Validate OAuth (existing code)
  ├── Look up / create activity in lti_activities
  │   └── activity_type = 'file_evaluation'
  │
  ├── Activity NOT configured:
  │   └── Instructor → Setup page (activity type selector includes "File Evaluation")
  │
  └── Activity IS configured:
      ├── module = registry.get_module('file_evaluation')
      │
      ├── Instructor:
      │   └── module.on_instructor_launch(ctx)
      │       → JWT with is_instructor=True
      │       → 303 Redirect to /m/file-eval/grading?activity_id=<id>&resource_link_id=<uuid>&token=...
      │
      └── Student:
          └── module.on_student_launch(ctx)
              → JWT with is_instructor=False
              → 303 Redirect to /m/file-eval/upload?activity_id=<id>&resource_link_id=<uuid>&token=...
```

The **`activity_id`** query parameter is the **integer** `lti_activities.id` (required for `GET/POST .../activities/{activity_id}/...` in the module API). **`resource_link_id`** is retained for debugging and deep links; it must **not** be substituted for `activity_id` in API paths.

**Post-setup instructor redirect** (from `lti_router` when finishing configuration) may use `activity_id` in the grading URL without `resource_link_id` in some flows; both patterns are valid as long as the SPA resolves a numeric `activity_id` (query or JWT `lti_activity_id`).

---

## 6. Evaluation Pipeline

```
Instructor clicks "Evaluate All"
  │
  ├── POST /activities/{id}/evaluate  (file_submission_ids)
  │   ├── Mark submissions as 'pending' in DB
  │   └── Enqueue BackgroundTask → process_evaluation_batch()
  │
  ├── Frontend polls GET /activities/{id}/evaluation-status every 3s
  │
  └── Background: for each submission:
      ├── Mark 'processing'
      ├── DocumentExtractor.extract_text_from_file(path)
      ├── EvaluatorClient.evaluate_text(text, evaluator_id)
      │   └── await run_lamb_assistant(request, assistant_id)  ← in-process!
      ├── EvaluatorClient.parse_evaluation_response(response)
      │   └── Regex score extraction (NOTA FINAL, Score, etc.)
      ├── GradeService.upsert_ai_grade(fs_id, ai_score, ai_comment)
      └── Mark 'completed' (or 'error' with message)
```

---

## 7. Grade Passback Flow

```
Instructor clicks "Sync Grades to Moodle"
  │
  ├── POST /activities/{id}/grades/sync
  │
  └── LTIGradePassback.send_activity_grades(activity_id):
      ├── Get LTI credentials from LtiActivityManager.get_lti_credentials()
      ├── Get lis_outcome_service_url from lti_activities
      ├── JOIN student_submissions + grades WHERE score IS NOT NULL
      │
      └── For each student:
          ├── Generate OAuth 1.0a HMAC-SHA1 signature
          ├── Build IMS LTI XML (score normalized 0-10 → 0-1)
          ├── POST to Moodle lis_outcome_service_url
          └── Mark sent_to_moodle = 1 on success
```

---

## 8. Verification Checklist

### Automated (pytest)

```bash
cd backend && pytest tests/modules/test_file_evaluation_*.py -v
```

Recommended test coverage:
- [ ] Migration SQL parses and creates tables (`MIGRATION_SQL` contains `mod_file_eval_submissions`)
- [ ] `DocumentExtractor` handles `.txt` files
- [ ] `EvaluatorClient._extract_score_and_feedback` regex patterns (parametrized)
- [ ] Module auto-discovery includes `file_evaluation`
- [ ] All 12 Python files pass syntax check (`ast.parse`)

### Manual (LTI end-to-end)

- [ ] Instructor LTI launch → redirects to `/m/file-eval/grading` (query includes **`activity_id`**)
- [ ] Student LTI launch → redirects to `/m/file-eval/upload` (query includes **`activity_id`**)
- [ ] `GET /lamb/v1/modules/file_evaluation/activities/{id}/view` returns JSON (not 404) when backend is mounted at `/lamb`
- [ ] UI shows translated `fileEval.*` strings (not raw keys) after i18n init
- [ ] Student uploads PDF → submission created, file stored
- [ ] With `LAMB_DB_PREFIX` set, no SQLite error `no such table: main.lti_activities` on insert (schema repair + migrations)
- [ ] Group activity: leader gets code → member joins with code
- [ ] AI evaluation: start → poll → completed with ai_score
- [ ] Instructor edits grade → final score saved
- [ ] Accept all AI grades → bulk update
- [ ] Sync to Moodle → grades sent via LTI 1.1 Outcome Service

---

## 9. Relationship to Other Phases

| Phase | What it delivered | How Phase 4 builds on it |
|-------|-------------------|--------------------------|
| **Phase 1** | `ActivityModule` contract, module registry, auto-discovery | Phase 4 implements the second module (`file_evaluation`) |
| **Phase 2** | Frontend monorepo (`pnpm-workspace.yaml`, `@lamb/ui`) | Phase 4 adds `packages/module-file-eval/` using same shared UI |
| **Phase 3** | Chat module migrated from Jinja2 to SvelteKit SPA | Phase 4 follows the same pattern: SPA at `/m/file-eval/`, static mount, catch-all |

---

## 10. Known Limitations, Future Work & Pending Issues

### 10.1 — Product / UX gaps (unchanged from Phase 4 scope)

1. **No consent flow**: Unlike the chat module, file-eval does not require student consent before launch. If needed, add a `/m/file-eval/consent` route following `module-chat`'s pattern.
2. **Single evaluator per activity**: The current design supports one LAMB assistant as evaluator. Multi-rubric or multi-evaluator support would need schema changes.
3. **No real-time updates**: Evaluation progress uses polling (3s interval). WebSocket or SSE could improve UX.
4. **File size limits**: No explicit upload size limit is enforced in the module; relies on FastAPI/reverse proxy defaults.
5. **`lis_outcome_service_url`**: Currently stored as a new column on `lti_activities`. This URL comes from the LTI launch params and must be persisted during activity setup — the Unified LTI Router needs to save it from the launch POST.
6. **Activity description / parity with standalone LAMBA**: The instructor setup flow may not yet expose all fields (e.g. long description) that LAMBA had for file-eval activities; track as a follow-up if product requires it.
7. **Group resubmit policy and 409 Conflict**: `create_submission` only treats a POST as a *resubmit* (update same `mod_file_eval_submissions` row) when the existing submission’s `uploaded_by` equals the current `student_id`. A group member who joined via code shares the same `file_submission_id` but is not `uploaded_by`; a second upload attempt falls through to a new insert and hits the UNIQUE constraint on `(student_id, activity_id)`, which surfaces as **HTTP 409**. Only the student who originally uploaded can replace the file today—this can look like an intermittent bug when comparing different accounts. **To improve / implement**: decide product rules (e.g. any group member may replace vs leader-only), return a clear API error message (not a generic conflict), update the student UI copy, and optionally allow updates to the shared `file_submission` for all members of the same group when policy allows. Success-path logging for uploads is also minimal (mostly warnings on errors); ops visibility can be improved with `INFO` lines or access logs.

### 10.3 — Resolved: AI evaluation stored garbage in `ai_comment` (file_eval)

| | |
|--|--|
| **Symptom** | After “Evaluate”, `mod_file_eval_grades.ai_comment` contained text like `{'success': True, 'response': <starlette.responses.Response object at 0x…>}` and `ai_score` stayed empty. |
| **Cause** | In-process `run_lamb_assistant()` returns a **Starlette `Response`** (JSON body) for non-streaming completions (`lamb/completions/main.py`). `EvaluatorClient.parse_evaluation_response()` expected `eval_result["response"]` to be an **OpenAI-shaped dict** with `choices` / `message` / `content`, so it never extracted model text and fell back to `str(eval_result)`. |
| **Fix** | `evaluate_text()` in [`backend/lamb/modules/file_evaluation/evaluator_client.py`](../../backend/lamb/modules/file_evaluation/evaluator_client.py) unwraps `Response`: read `body`, `json.loads`, treat HTTP status ≥ 400 as failure (surface `error.message` when present), then pass the parsed dict into `parse_evaluation_response`. Streaming responses are rejected as unexpected when `stream=False`. |

**Status (verified)**: With the unwrap in place, evaluation persists the **full assistant message** in `ai_comment` (the model’s `content` string). That is the intended behaviour after the fix. **`ai_score` may still be `NULL`**: it is only filled when `_extract_score_and_feedback` finds a numeric grade using the built-in regex patterns (e.g. `NOTA FINAL: 7.5`, `Score: 8`, line ending in `8/10`). Chat-style replies without those patterns store useful text in `ai_comment` but leave **`ai_score` empty** — that is expected, not a regression. Use an evaluator-oriented assistant prompt (or extend the regex / rubric flow) if you need automatic numeric scores every time.

### 10.2 — Integration follow-ups (tracked for next iteration)

- **Remaining errors**: Several edge cases and polish items are still open; treat logs and the checklist in **§8** as the source of truth.
- **Standalone `uvicorn lamb.main:app`**: The file-eval schema **repair** and **module migrations** run only from the **root** `backend/main.py` lifespan. Running only `lamb.main` without the full app may skip those steps (document or align startup).
- **Schema repair data loss**: `repair_file_eval_schema_if_needed` **drops** `mod_file_eval_*` tables when fixing FK mismatch; production deployments need a migration strategy if data must be preserved.
- **Docker / frontend build**: Ensure the production image runs the same build pipeline that includes `module-file-eval` and `packages/ui` locale updates so `fileEval` strings ship with the bundle.
