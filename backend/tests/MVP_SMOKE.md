# AI Workshop — Lean MVP one-shot smoke test

> Script: `backend/tests/mvp_smoke.py`
> One run verifies the whole Lean MVP loop: **instructions → attach document → connect KB / retrieve → tools → chat + observability → reflection/submit → formative feedback → teacher dashboard**.

---

## 1. What it tests (mapped to the MVP elements)

| MVP element | Checks run by the script (highlights) |
|---|---|
| 1 Instructions | Creates an assistant, `system_prompt` is written |
| 2 Attach document | `POST /doc` multipart → real KB ingest → polled to `completed` |
| 3 Connect KB | `POST /kb` probe query, hits carry `similarity` + text |
| 4 Tools | Tool definitions accepted in chat; `tool_event` emitted |
| 5 Chat + observability | SSE `observability` frame with `system_instructions` / `user_input` / `final_llm_messages` / `retrieved_sources` |
| 6 Reflection | `POST /submit`, reads back `reflection` and `status=submitted` |
| 7 Formative | `POST /evaluate` → `configured` / `status` / criteria; `GET /evaluation` restores |
| Teacher dashboard | `/lti/workshop/dashboard/{stats,students,sessions/{id}}` + 401/403 boundaries |

The script seeds its own activity/student/session and mints both a `workshop_student` token and a dashboard token. It needs **no Moodle, OWI or browser**, and the document upload and KB retrieval hit the **real KB server**.

---

## 2. Prerequisites

1. The stack is running (at least backend + kb):

   ```powershell
   $env:LAMB_PROJECT_PATH = "C:\Users\Usuario\lamb"
   docker compose up -d backend kb
   docker compose ps
   ```

2. (Optional — decides the "success" vs "degraded" path) The organization has a small-fast model / chat model configured.
   - Configured → chat and formative report `PASS`.
   - Not configured → those two steps report `WARN` (not a failure by default); submission still succeeds.
   - To require a model strictly, add `--require-llm`, which turns missing-model cases into `FAIL`.

---

## 3. Run it

From the repository root:

```powershell
# Default: run everything; LLM-dependent steps report WARN if no model is reachable
docker compose exec backend python tests/mvp_smoke.py

# Require a real LLM (for CI / acceptance)
docker compose exec backend python tests/mvp_smoke.py --require-llm

# Delete the activity seeded by this run when done (cascades to session/user/evaluation)
docker compose exec backend python tests/mvp_smoke.py --cleanup

# Point at a different backend
docker compose exec backend python tests/mvp_smoke.py --base http://localhost:9099
```

> The container bind-mounts the repository, so script edits need no container rebuild.

---

## 4. Reading the output

Each check prints `[PASS] / [WARN] / [FAIL]`, followed by a summary line:

```
 RESULT: 40 passed, 0 failed, 0 warnings  (40 checks)
```

Exit code: `1` if there is any `FAIL`, otherwise `0` (suitable for CI).

- `PASS` = that MVP element genuinely works.
- `WARN` = depends on an external model/environment and cannot be judged right now; not a failure (tighten with `--require-llm`).
- `FAIL` = a real defect or environment error that must be handled.

At the end the script prints two ready-to-open URLs:

```
 Student wizard : http://localhost:9099/m/workshop/<id>?token=<student_token>
 Teacher board  : http://localhost:9099/lamb/v1/lti/workshop/dashboard?resource_link_id=...&token=...
```

Use them for a manual UI review (the 5-step wizard, the feedback card, the teacher dashboard).

---

## 5. A defect that used to exist (now fixed)

> History: `build_state` (the wizard's 5-step decisions: instructions/document/KB/tools) was never persisted. `POST /submit` wrote only `saved_chat` + `reflection`, the frontend sent only those two fields, yet `build_transcript` (formative) and the teacher dashboard read `build_state`, so a real student's "build decisions" were empty on the read side. The Phase 5/6 manual tests missed it because their seed scripts wrote `build_state` straight into the DB with SQL.

**Fix (option 1: persist on submit):**

- Backend `submit_workshop_session(...)` gained a `build_state` parameter accepting a JSON string or a serializable object (`database_manager.py`).
- Route `POST /workshop/sessions/{id}/submit` forwards `body["build_state"]` (`routers.py`).
- Frontend `handleSubmit` sends `build_state: JSON.stringify(formStore.serialize())` (`+page.svelte`).
- Regression test: `test_workshop_auth.py::TestSubmitPersistsBuildState`.

Now the teacher dashboard's session detail `build_state` and the formative transcript's `=== BUILD DECISIONS ===` section carry real data.

---

## 6. Manual UI review (after the script passes)

1. Open the printed **Student wizard** URL.
2. Walk steps 1→5: write instructions → upload the file (watch the progress until it becomes knowledge) → run a retrieval in step 3 and inspect the similarity → pick a tool in step 4 → chat in step 5 and watch the observability panel on the right (system instructions / retrieved excerpts / final messages / tool timeline).
3. Write a reflection → Submit → review the formative feedback card (without a rubric it shows the "No rubric..." text).
4. Open the **Teacher board** URL: the four stat cards, tool usage, the student progress table, and View to expand the transcript and feedback.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `POST /doc` 502 / KB error | KB server down or embeddings not configured | `docker compose up -d kb`, check `docker compose logs kb` |
| Ingestion `failed` | Ingest plugin / embedding model issue | Check the KB logs; the `DISABLE/SIMPLIFIED/ADVANCED` plugin flags |
| Chat / evaluation `WARN` | Organization has no model configured | Set `SMALL_FAST_MODEL_*` / `OLLAMA_MODEL`, then `docker compose up -d backend` |
| Seed reports `no such table` | Migrations have not finished | Wait for `docker compose logs backend` to show startup complete, then retry |
| Want to clean data | — | Add `--cleanup`, or delete rows matching `resource_link_id LIKE 'mvp-smoke-%'` |

---

## 8. Relationship to the automated unit tests

This script is an **end-to-end smoke test** (real HTTP + real KB), complementary to the mock unit tests in `backend/tests/test_workshop_*.py`:

```powershell
# Unit-test regression
docker compose exec backend python -m pytest tests/test_workshop_kb.py tests/test_workshop_evaluation.py `
  tests/test_workshop_dashboard.py tests/test_workshop_migrations.py -q
```

> Note: the repository currently has 4 known failing tests unrelated to this smoke test (`test_observability_payload_has_all_fields`, `ObservabilityPanel` C4/C5, `page.svelte.test.js` h1).
