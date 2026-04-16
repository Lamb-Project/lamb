# Phase 4: File Evaluation Module — Port from LAMBA to LAMB

> **Status**: Implementation complete; **integration hardening in progress** (remaining issues tracked separately)
> **Date**: 2026-03-24 (updated 2026-04-10 — instructor grading UX / AI feedback / download; student upload: **group leader vs member** views; **join group error handling**)
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
| `__init__.py` | Exports `module = FileEvalModule()`; full `ActivityModule` implementation (migrations, routers, setup fields, LTI launch, JWT, dashboard hooks) | ~250 | New (wraps LAMB contract) |
| `migrations.py` | DDL: 3 tables + 7 indexes; `{table_prefix}` in FKs; **`repair_file_eval_schema_if_needed`** for prefix mismatch | ~115 | `db_models.py` |
| `router.py` | Single `APIRouter` (submissions, grades, evaluation, sync, etc.) | ~260 | `activities_router.py`, `submissions_router.py`, `grades_router.py` |
| `evaluator_client.py` | Score regex extraction + direct call to `run_lamb_assistant` | ~150 | `lamb_api_service.py` |
| `document_extractor.py` | PDF, DOCX, TXT text extraction | ~100 | `document_extractor.py` (near-verbatim) |
| `storage_service.py` | File storage under `uploads/file-eval/{activity_id}/` | ~70 | `storage_service.py` |
| `grade_service.py` | Grade CRUD via raw SQL, dual AI+professor model, bulk accept | ~130 | `grade_service.py` |
| `evaluation_service.py` | Background batch evaluation with status tracking, timeout handling | ~200 | `evaluation_service.py` |
| `service.py` | Submission CRUD, group join flow, dashboard stats queries; robust **`_parse_setup_config`** | ~355 | `activities_service.py` |
| `lti_passback.py` | OAuth 1.0a signed XML grade passback to Moodle | ~160 | `lti_service.py` (verbatim algorithm) |
| `schemas.py` | Pydantic v2 request/response models; `FileEvalSetupConfig` includes `title` + validators for group `max_group_size` | ~150 | `models.py` |

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
| `POST` | `/submissions/join` | Student | Join group by code (404 invalid code; 409 group full / already member / already submitted) |
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
| `src/app.css` | Tailwind import; `@plugin '@tailwindcss/typography'` for Markdown prose in AI feedback |
| `src/routes/+layout.js` | `load`: `setupI18n` + `waitLocale` before pages render (avoids “Cannot format a message without first setting the initial locale”) |
| `src/routes/+layout.svelte` | Root layout with `@lamb/ui` shell |
| `src/routes/upload/+page.svelte` | **Student view** (LAMBA-aligned layout): activity header + group-size banner; four branches: **(1) group, no submission** - two columns (upload to create group / join with code); **(2) group member** (`is_group_leader` false) - "Joined the group" status card, file meta, group code, download, member list with leader badge (`fileEval.grading.leaderBadge`), **no** replace upload; **(3) group leader** - "Document submitted (group leader)" card, highlighted group code with copy button, optional `group_display_name`, members list, then replace-submission block; **(4) individual** - summary + upload/replace. Members loaded via `getGroupMembers(file_submission_id)` (GET `/submissions/{id}/members`) after view load and refreshed on upload/join. Backend flag `is_group_leader` comes from `service.py` `_build_submission_view`. i18n keys under `fileEval.upload` (e.g. `statusJoinedGroup`, `copyGroupCode`, `groupMembersTitle`). |
| `src/routes/grading/+page.svelte` | **Instructor view**: header card (activity title, course/context, owner, created date), editable activity settings (description, deadline), stats cards, **card-based** submission list (not a wide table), per-submission checkboxes + **select all**, bulk actions (**AI Evaluation**, accept AI, Moodle sync) only when there are submissions, evaluator warning if no `evaluator_id`, inline grading (AI score, collapsible **AI feedback** rendered as **Markdown** via `marked` + `@tailwindcss/typography`), final score/comment, filename as download link; polling for batch evaluation; deadline display parses Unix **or** ISO/`datetime-local` from `setup_config` |
| `src/lib/services/api.js` | API helper with JWT from URL query param + Bearer header |
| `src/lib/services/submissionService.js` | Upload, download, join group, get submission, **`getGroupMembers`** (student upload page) |
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

- `setup_config TEXT DEFAULT '{}'` — Stores module-specific configuration as JSON (evaluator ID, **`title`** (redundant copy; display name uses `activity_name`), submission type, max group size, deadline, language).
- `lis_outcome_service_url TEXT` — LTI Outcome Service URL for grade passback, stored per activity.

### 4.10 — Backend Python requirements

Document extraction deps live in `requirements-base.txt` (pinned):

```
pypdf==5.1.0
python-docx==1.1.2
```

Heavy ML/RAG deps are in `requirements-ml.txt`. Install with  
`pip install -r requirements-base.txt && pip install -r requirements-ml.txt` (see `backend/requirements.txt`).

### 4.11 — LTI instructor setup & configure (file_evaluation, 2026-04)

The **unified LTI setup UI** lives in **`frontend/packages/module-chat`** (`/m/chat/setup`), not in `module-file-eval`. The backend drives dynamic fields via `GET /lamb/v1/lti/setup/info` → `modules_fields.file_evaluation` from `FileEvalModule.get_setup_fields()`.

| Area | Change |
|------|--------|
| **`backend/lamb/modules/file_evaluation/__init__.py`** | Setup field order and types: **`title`** (required text, first), **`description`**, **`submission_type`** as **`radio`** (Individual / Group), **`max_group_size`** (conditional in UI), **`deadline`** (required `datetime-local`), **`language`**. **`evaluator_id`** is **not** a setup form field — it is auto-assigned from the first selected assistant in `on_activity_configured()` and persisted into `setup_config` JSON. |
| **`backend/lamb/lti_router.py`** | `_field_to_json()` exposes **`options`** for **`radio`** as well as `select`. **`POST /lamb/v1/lti/configure`**: for `activity_type == file_evaluation`, validates non-empty **title** and **deadline**; if **group**, **`max_group_size`** must be integer **2–20**. **`activity_name`** on `lti_activities` uses instructor **title** (trimmed) with fallback to LMS context title / `resource_link_id`. |
| **`backend/lamb/modules/file_evaluation/schemas.py`** | `FileEvalSetupConfig` adds optional **`title`**; **`@model_validator`** enforces **2–20** for `max_group_size` when `submission_type == group` and clears it for individual. |
| **`frontend/packages/module-chat/src/routes/setup/+page.svelte`** | Renders **`radio`** fields; shows **`max_group_size`** only for **Group**; client-side validation for deadline and group size; hint **Min 2, Max 20** under group size. Generic text field rendering (no `evaluator_id` special-casing). |

**Rebuild** `module-chat` (and optionally `module-file-eval` after grading fixes) so static assets under `/m/chat/app` and `/m/file-eval/app` match source.

### 4.12 — Instructor grading SPA (`grading/+page.svelte`)

Fixes for the instructor dashboard after setup changes:

| Issue | Fix |
|-------|-----|
| **Infinite spinner** | Template called **`isDeadlinePast()`** without defining it → runtime error once `deadline` exists. Added **`isDeadlinePast`** using existing **`parseDeadline()`**. |
| **`Invalid Date`** | **`formatDate()`** assumed Unix seconds; **`setup_config.deadline`** is often a **`datetime-local` string** (e.g. `2026-04-09T20:36`). Added **`formatDeadlineDisplay()`** that uses **`parseDeadline()`** for the activity info card. |

### 4.13 — Instructor grading dashboard UX, data, and download (2026-04)

Follow-up work to align the post-setup **instructor grading** experience with the chat module’s dashboard style and LAMBA-era expectations, plus polish for AI output display.

| Area | Change |
|------|--------|
| **`backend/.../service.py` — `get_activity_info()`** | Enriches `activity_info` for the grading header: `owner_display` (from `owner_name` / `owner_email`), `org_name` (via `get_organization_by_id`), `context_title`, plus existing description/deadline/title/`created_at`. |
| **`backend/.../router.py` — `GET .../submissions/{id}/download`** | Queries table **`mod_file_eval_submissions`** by name (migration creates this table **without** duplicating `table_prefix` in the identifier used historically in SQL). Avoids `no such table` / 500 when prefix is empty or mismatched. Logs and maps missing files to **404**; unexpected errors return a clear **500** message. |
| **Grading SPA layout** | Header card (icon + title + course/org line + owner + created). Activity settings card with edit/save for description and deadline. Stats metrics. Submissions section title switches **Group** vs **Individual**. Bulk toolbar (**AI Evaluation**, accept AI, sync to LMS) only renders when `submissions.length > 0`. |
| **Submissions list** | Card per submission: checkbox (with **select all** above the list), status badge, download button, clickable filename, file meta, always-visible student-note block (placeholder if empty), members + leader badge for groups, grading row with AI score / final score. |
| **Batch evaluation** | `POST /activities/{id}/evaluate` receives **only selected** submission IDs from the UI (not necessarily all rows). Primary action label uses i18n key **`fileEval.grading.aiEvaluation`** (not a literal “Evaluate All”). |
| **AI feedback in UI** | When **`ai_score`** is present, show label **AI feedback** (`aiComment`) with **Show** / **Hide** toggles; expanded body renders **`ai_comment`** as HTML from **`marked`** (GFM + line breaks) inside a `prose` container — not raw Markdown/plain text. Requires **`marked`** dependency and **`@tailwindcss/typography`** in `module-file-eval` `app.css`. |
| **i18n** | New and updated keys under **`fileEval.grading`** in **`frontend/packages/ui/src/lib/locales/{en,es,ca,eu}.json`** and mirrored in **`module-file-eval/src/lib/locales/`** (e.g. `aiEvaluation`, `selectAll`, `submissionsFound`, `aiComment`, `showAiComment`, `hideAiComment`, header/settings copy). |

**Security note:** `{@html}` after `marked.parse()` follows the same pattern as other apps in the monorepo (e.g. creator news). For untrusted content, consider sanitization (e.g. DOMPurify) in a future hardening pass.

### 4.14 — Student upload (`upload/+page.svelte`): group leader vs member (2026-04)

When the activity is **group** submission type and the student already has a row in `submission`, the SPA branches on **`submission.is_group_leader`** (computed in `backend/lamb/modules/file_evaluation/service.py`, `_build_submission_view`: leader = same `student_id` as `file_submission.uploaded_by` and a non-null `group_code`).

| Role | UI |
|------|-----|
| **Member** (joined with code) | Status card “Joined the group”, file name/size/submitted-at, group code, download; list of members with **Leader** badge on the uploader; **no** replace-submission dropzone. |
| **Leader** (first uploader) | Status card “Document submitted (group leader)”, download, **copy group code** (`navigator.clipboard`), optional group display name, member list, then **replace submission** (deadline + dropzone + note). |

**Data:** Member rows are not embedded in `GET .../activities/{id}/view`; the page calls **`getGroupMembers(file_submission_id)`** → existing **`GET /submissions/{id}/members`**. Leader detection in the list matches **`m.student_id === file_submission.uploaded_by`** (same idea as the instructor grading cards).

**i18n:** New keys under **`fileEval.upload`** in **`frontend/packages/ui`** and **`module-file-eval`** locales (`en`, `es`, `ca`, `eu`): e.g. `statusJoinedGroup`, `statusDocumentSentLeader`, `submissionFileLabel`, `submissionSizeLabel`, `submissionSentLabel`, `copyGroupCode`, `codeCopied`, `groupMembersTitle`, `groupLabel`. Reuses **`fileEval.grading.leaderBadge`** for the badge text.

### 4.15 — Group join error handling (`router.py`, `api.js`, i18n) (2026-04)

`POST /submissions/join` previously returned **500** when `FileEvalService.join_group()` raised `ValueError` (group full, invalid code, already member, already submitted). The router now wraps the call in `try/except ValueError` and maps each known message to a proper HTTP status and structured `detail`:

| Service `ValueError` message | HTTP | `detail.code` |
|------------------------------|------|----------------|
| `Invalid group code` | 404 | `invalid_group_code` |
| `Group is full` | 409 | `group_full` |
| `Already a member of this group` | 409 | `already_in_group` |
| `Already submitted to this activity` | 409 | `already_submitted_activity` |

**Frontend:** `apiFetch` (and `apiUpload`) in [`api.js`](frontend/packages/module-file-eval/src/lib/services/api.js) now parse JSON error bodies and expose `error.code` on the thrown Error. `handleJoinGroup` in [`upload/+page.svelte`](frontend/packages/module-file-eval/src/routes/upload/+page.svelte) maps `error.code` to i18n keys (`groupJoinFull`, `groupJoinInvalidCode`, `groupJoinAlreadyMember`, `groupJoinAlreadySubmitted`) under `fileEval.upload`, falling back to the raw message for unknown codes. Keys added in all 8 locale files (en, es, ca, eu).

### 4.16 — Rubric filter for file_evaluation assistant selection (2026-04)

When an instructor configures an LTI activity and selects **File Evaluation**, the assistant list now only shows assistants that are ready for rubric-based evaluation. Assistants shared with the instructor are included if they also meet the rubric criterion. Chat activities continue to show all published assistants without filtering.

| Area | Change |
|------|--------|
| **`backend/lamb/database_manager.py`** | New static method **`assistant_has_rubric_for_eval(api_callback)`**: parses the `api_callback` JSON and returns `True` only when `rubric_id` is non-empty **and** `rag_processor == "rubric_rag"` (strict criterion — the completions pipeline must actually load the rubric). **`get_published_assistants_for_org_user()`**: both `SELECT` queries now include `a.api_callback`; the dedup loop computes **`rubric_eval_ready: bool`** per assistant and strips the raw `api_callback` from the returned dict (never sent to the client). |
| **`backend/lamb/lti_router.py` — `POST /lti/configure`** | When `activity_type == "file_evaluation"`, the endpoint now validates that **every** selected assistant has `rubric_eval_ready == True`. If any assistant lacks a rubric, it returns **HTTP 400** with the assistant name in the error detail. |
| **`backend/lamb/modules/file_evaluation/__init__.py`** | Removed **`evaluator_id`** from `get_setup_fields()`. The field is no longer exposed in the setup form; the backend auto-assigns it from the first selected assistant in `on_activity_configured()`. |
| **`frontend/packages/module-chat/src/routes/setup/+page.svelte`** | New `$derived` **`assistantsForCurrentActivity`**: filters `availableAssistants` by `rubric_eval_ready` when `selectedActivity === 'file_evaluation'`; passes through the full list for chat. The assistant list and `canSubmit` use this filtered list. When the filtered list is empty for file-eval, an amber info box shows *"No assistants with a rubric found"* with the static reference path `/lamb/v1/lti_creator/launch` (plain text, not a link — the administrator provides access context). Changing the activity type clears the assistant selection. Removed all `evaluator_id` special-casing from the text input rendering. |
| **`backend/tests/test_rubric_eval_helper.py`** | 10 parametrized unit tests for `assistant_has_rubric_for_eval`: valid rubric+rag, wrong rag_processor, empty/missing rubric_id, None, empty string, invalid JSON, whitespace, numeric rubric_id. |

**Behaviour note — rubric without evaluator system prompt:** The file-eval pipeline (`EvaluatorClient.evaluate_text`) sends the student document to `run_lamb_assistant`, which applies the assistant's system prompt and RAG context (rubric). If the system prompt is not written for evaluation, the LLM will still produce a response stored in `ai_comment`, but `ai_score` may be `NULL` because `_extract_score_and_feedback` relies on regex patterns (`NOTA FINAL`, `Score`, `x/10`) that a chat-style reply won't contain. The rubric filter ensures the rubric *data* is injected; the quality of the evaluation depends on the assistant's system prompt.

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
Instructor selects submissions and clicks "AI Evaluation" (i18n)
  │
  ├── POST /activities/{id}/evaluate  (file_submission_ids; may be subset)
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
- [ ] First-time **file_evaluation** setup: **title**, **deadline**, **submission type** (individual/group); group requires **max 2–20**; **evaluator** field disabled when assistants are checked; save → **`activity_name`** in DB matches title; grading page loads (no spinner / **Invalid Date** on deadline)
- [ ] Student LTI launch → redirects to `/m/file-eval/upload` (query includes **`activity_id`**)
- [ ] `GET /lamb/v1/modules/file_evaluation/activities/{id}/view` returns JSON (not 404) when backend is mounted at `/lamb`
- [ ] UI shows translated `fileEval.*` strings (not raw keys) after i18n init
- [ ] Student uploads PDF → submission created, file stored
- [ ] With `LAMB_DB_PREFIX` set, no SQLite error `no such table: main.lti_activities` on insert (schema repair + migrations)
- [ ] Group activity: leader uploads first → sees leader view (copy code, members, replace submission); second student joins with code → sees member view (no replace, leader badge on uploader)
- [ ] AI evaluation: select one or more submissions → **AI Evaluation** → poll → completed with `ai_score` / `ai_comment` as applicable
- [ ] Instructor grading UI: header shows owner/org/created; settings edit works; **AI feedback** expands and renders Markdown (not raw `**` lines)
- [ ] Instructor download: `GET .../submissions/{uuid}/download` returns file (no 500 from wrong table name)
- [ ] Instructor edits grade → final score saved
- [ ] Accept all AI grades → bulk update
- [ ] Sync to Moodle → grades sent via LTI 1.1 Outcome Service
- [ ] Join full group → student sees translated "group full" message (not 500 Internal Server Error)

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
6. **Activity description / parity with standalone LAMBA**: The setup form now includes **title**, **description**, **submission type** (radio), **conditional max group size**, **deadline**, and **language**. Remaining gaps vs. old LAMBA (if any) are cosmetic/i18n rather than missing core fields.
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
