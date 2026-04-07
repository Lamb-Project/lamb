# #277 File evaluation (phase 4): LTI passback, i18n, activity API, and integration fixes

## Summary

Follow-up work on porting the file-evaluation flow from LAMBA into LAMB as an `ActivityModule`, aligned with the modular monorepo and unified LTI router (#277).

## Changes (recent commits on this branch)

### `5cd27f7f` — File evaluation: AI grade unwrap, LTI outcome URL, SPA config, activity API

- **EvaluatorClient:** unwrap Starlette `JSONResponse` so model text is stored correctly in `ai_comment`.
- **LTI:** persist `lis_outcome_service_url` on launch; allow the field in `update_lti_activity`.
- **Static SPA config:** serve `/m/chat/config.js` and `/m/file-eval/config.js` for module SPAs (avoid catch-all 404).
- **File-eval API:** `activity_info` on activity view, `PUT` setup-config merge, instructor download with service helpers.
- **Docs:** PHASE4 updates (§10.3 verification, review guide, group resubmit 409 note).

### `d8a1fb9c` / `ee4833be` — Merges

- Merge `upstream/feature/issue#277/phase4_lamba_port` into this branch; intermediate merge commit.

### `88fda13f` — Frontend bugs and Docker-related issues

- **`get_activity_info`:** query matches real `lti_activities` columns (fixes 500 on `/view`).
- **i18n:** full `fileEval` strings merged into `@lamb/ui` locales (en/es/ca/eu); `initI18n` in `module-file-eval` root layout.
- **Upload / grading:** deadline parsing (ISO vs Unix timestamps), clearer sync error handling, small UI/a11y fixes.
- **`backend/file_eval_snapshot.txt`:** was updated for local debugging; **no longer tracked** (see Repository hygiene below).
- Generated **`version.js`** bumps in frontend packages.

### `5aafbae3` — Moodle grade sync and operational hardening

- **LTI 1.1 passback:** propagate `lis_result_sourcedid` from launch POST into `LTIContext`, consent token, and student `file_eval` JWT; extend `launch_user` on the module base contract, chat module, and file-eval module.
- **`lti_passback`:** richer error payloads (including Moodle response snippets), ignore empty `sourcedid`, per-student failure summary, hint when `lis_outcome_service_url` uses `localhost` unreachable from the backend process.

### Repository hygiene — do not commit local / runtime artifacts

The following paths are **gitignored** and **removed from the index** (files may still exist locally for development):

| Path | Reason |
|------|--------|
| `backend/uploads/file-eval/` | Student submission files (entire tree, recursive) |
| `lamb_v4_dump.sql` | Local SQLite dump |
| `backend/file_eval_snapshot.txt` | Local module snapshot for debugging |

Older commits on the branch may still contain blobs for some of these; the **current tree** excludes them. Use history rewrite (e.g. `git filter-repo`) only if the team requires purging blobs from history.

### Optional docs (add if desired)

- [`BACKEND_DOCKER_VS_LOCAL_LTI.md`](./BACKEND_DOCKER_VS_LOCAL_LTI.md) — backend in Docker vs on host for LTI / passback and permissions.

## Checklist before merge

- [ ] Add and commit `BACKEND_DOCKER_VS_LOCAL_LTI.md` (and this `PR_DESCRIPTION_EN.md`) if they should ship with the PR.
- [x] `backend/uploads/file-eval/`, `lamb_v4_dump.sql`, and `backend/file_eval_snapshot.txt` excluded via `.gitignore` and untracked from index.
- [ ] Smoke test: LTI launch → student submission → instructor grade → sync to LMS (plus chat/consent regression if touched).

## How to test

1. Configure LTI tool pointing at this LAMB instance; launch file-eval activity as student and instructor.
2. Submit a file, set a final grade (or accept AI grade), run **Sync grades to Moodle** (or equivalent LMS).
3. With backend in Docker against an LMS on the host, ensure `lis_outcome_service_url` is reachable from the container (see `BACKEND_DOCKER_VS_LOCAL_LTI.md`).
