# Phase 4 — File Evaluation Module: Review & QA Guide

> **Purpose**: Step-by-step checks for reviewers and QA when validating the `file_evaluation` ActivityModule after port from LAMBA.  
> **Companion doc**: [PHASE4_FILE_EVALUATION_MODULE.md](./PHASE4_FILE_EVALUATION_MODULE.md) (architecture, files, API table).  
> **Issue**: #277 — Activity Module System

---

## 1. Audience & scope

Use this guide for:

- Manual LTI end-to-end smoke tests (Moodle or test consumer → LAMB → SPA).
- Spot-checking that **`activity_id` in URLs is the integer `lti_activities.id`**, not `resource_link_id` (UUID).
- Confirming module routes are reachable at **`/lamb/v1/modules/file_evaluation/...`** (mounted app in `lamb/main.py`).

Automated checks: see **§8** in the companion doc (`pytest` + checklist).

---

## 2. Environment

| Item | Typical value / note |
|------|----------------------|
| Backend API | `http://localhost:9099` (or your compose service) |
| OpenAPI | `http://localhost:9099/openapi.json` (when server is up) |
| Student SPA | `/m/file-eval/upload?activity_id=<int>&token=...` |
| Instructor SPA | `/m/file-eval/grading?activity_id=<int>&token=...` |
| Module API prefix | `/lamb/v1/modules/file_evaluation` |

**Docker logs (backend)**:

```bash
docker compose -f docker-compose-example.yaml logs -f backend
```

Successful uploads do not always emit `INFO` lines in module code; you may see little change unless log level is `INFO` or you rely on uvicorn access logs. Errors often surface as `WARNING` in `router.py`.

---

## 3. Critical integration rules (fail fast if wrong)

1. **Routers on `lamb/main.py`**: Module HTTP routes must be registered on the **mounted** FastAPI app so paths are `/lamb/v1/modules/file_evaluation/...`. See companion doc **§2.3** and **§4.2**.
2. **`activity_id` type**: Path/query `activity_id` = **integer PK** of `lti_activities`. A UUID in the path → **422**.
3. **JWT vs path**: For endpoints that carry both JWT and `activity_id`, the claim `lti_activity_id` must match the path parameter when enforced.
4. **`fileEval` i18n**: Strings live under **`frontend/packages/ui`** locales (`fileEval` key), not only in `module-file-eval` (see companion **§2.3**).

---

## 4. Flow A — Instructor: activity setup & launch

| Step | Action | Pass criteria |
|------|--------|----------------|
| A1 | LTI launch as instructor on a **file_evaluation** activity | Redirect or setup flow allows choosing/configuring file eval (evaluator assistant, options). |
| A2 | Complete setup (if applicable) | `lti_activities` row has `activity_type` / `setup_config` populated; no SQLite errors in logs. |
| A3 | Open grading URL | Browser lands on `/m/file-eval/grading` with **`activity_id=<numeric>`** in query (and `token` if used). |
| A4 | `GET .../activities/{id}/view` with instructor JWT | **200**, JSON with instructor-oriented view (submissions list access as designed). |

**Failure hints**: 404 on module routes → router not mounted under `/lamb`. Wrong table errors → migrations / `LAMB_DB_PREFIX` / schema repair (companion **§4.1**, **§4.8**).

---

## 5. Flow B — Student: upload & own submission

| Step | Action | Pass criteria |
|------|--------|----------------|
| B1 | LTI launch as student | Redirect to `/m/file-eval/upload` with **`activity_id=<numeric>`**. |
| B2 | Upload a small **PDF** or **TXT** (and optionally DOCX if supported) | **200** on `POST /activities/{id}/submissions`; file appears under server storage (`uploads/file-eval/{activity_id}/...` per deployment). |
| B3 | `GET /submissions/me` | Returns current student’s submission metadata. |
| B4 | Download | `GET /submissions/my-file/download` returns file (if implemented in UI, same API). |

**Failure hints**: **422** → `activity_id` not int or multipart field names wrong. **401/403** → JWT missing/invalid. Disk errors → **507** mapped from `OSError` in router.

---

## 6. Flow C — Group activities (leader, member, resubmit)

| Step | Action | Pass criteria |
|------|--------|----------------|
| C1 | Configure activity as **group** (max size > 1) | Setup stored in `setup_config`. |
| C2 | Student A uploads first | Group code / display name created; A is **`uploaded_by`** for the shared `mod_file_eval_submissions` row. |
| C3 | Student B joins with code | `POST /submissions/join` succeeds; B has `mod_file_eval_student_submissions` pointing to **same** `file_submission_id`. |
| C4 | Student A uploads **again** (replace file) | **200** — resubmit path: same `student_id` as `uploaded_by`. |
| C5 | Student B uploads **again** (replace file) | **Current backend behavior**: often **409 Conflict** — B is not `uploaded_by`, insert hits UNIQUE `(student_id, activity_id)`. |

**Review note**: Treat C5 as **known product/backend gap** until policy is implemented: only the original uploader can replace the file; other members need a clear UI message and/or backend change (see companion doc **§10.1** item 7). Do not file as “random Docker bug” without checking which account was `uploaded_by`.

---

## 7. Flow D — Instructor: AI evaluation & grades

| Step | Action | Pass criteria |
|------|--------|----------------|
| D1 | `POST /activities/{id}/evaluate` | Batch starts; submissions move through pending/processing/completed (or error) states. |
| D2 | `GET /activities/{id}/evaluation-status` | Poll until batch finished (UI may poll ~3s). |
| D3 | Grades | AI scores visible; instructor can override via `POST /grades/{submission_id}`. |
| D4 | Accept AI | `POST /grades/activity/{id}/accept-ai-grades` updates final scores as designed. |
| D5 | Sync to Moodle | `POST /activities/{id}/grades/sync` — requires valid LTI outcome URL/credentials; verify Moodle side if available. |

**DB check (D3)**: In `mod_file_eval_grades`, `ai_comment` should contain the **full model message text** after the Response-unwrap fix (see **§10.3** in [PHASE4_FILE_EVALUATION_MODULE.md](./PHASE4_FILE_EVALUATION_MODULE.md)). **`ai_score` can be empty** if the reply does not match the score regexes — normal for chat-oriented assistants; configure the evaluator prompt or patterns if you need a number every time.

---

## 8. Quick API spot-checks (optional)

With a valid **Bearer** token from the LTI redirect query:

- `GET /lamb/v1/modules/file_evaluation/activities/{activity_id}/view`
- `GET /lamb/v1/modules/file_evaluation/activities/{activity_id}/submissions` (instructor)

Compare response shapes with **OpenAPI** when the server is running.

---

## 9. Regression checklist (short)

- [ ] New DB / migrations: `mod_file_eval_*` tables exist; no `no such table: main.lti_activities` when `LAMB_DB_PREFIX` is set (see companion **§4.8**).
- [ ] Prefix mismatch repair: understand it **drops** module tables — dev-only implication.
- [ ] Frontend: no raw `fileEval.*` keys after locale load.
- [ ] Group: leader/member join works; **document 409** for non-uploader resubmit until fixed.

---

## 10. Sign-off

| Role | Date | Notes |
|------|------|-------|
| Reviewer | | |
| QA | | |

**References**: [PHASE4_FILE_EVALUATION_MODULE.md](./PHASE4_FILE_EVALUATION_MODULE.md) §8 (full checklist), §10 (limitations & follow-ups).
