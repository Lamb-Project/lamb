# AI Workshop — operation and maintenance

The AI Workshop is an LTI activity type (`activity_type = "workshop"`) in which
students build a small AI assistant: they write instructions, attach a document,
verify retrieval, pick a tool, test the assistant and reflect on the design.
Teachers see a dashboard with per-student progress and rubric-based formative
feedback.

This page covers the operational side: configuration, data lifecycle, deletion,
the pilot gate and how to test the whole thing. The design rationale lives with
the code (see the module docstrings in `backend/lamb/modules/workshop/`).

---

## 1. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `WORKSHOP_TOKEN_TTL_SECONDS` | `1800` | Lifetime of a student's workshop token. The wizard renews it in the background while the token is still valid; an expired token can never be renewed. |
| `WORKSHOP_RETENTION_ENABLED` | off | Enables the daily retention sweep. Retention is **opt-in**: off unless this is truthy *and* a window is set. |
| `WORKSHOP_RETENTION_DAYS` | unset (no deletion) | Retention window in days. Unset means "keep forever". |
| `WORKSHOP_RETENTION_HOUR` / `WORKSHOP_RETENTION_MINUTE` | `4` / `0` | When the daily sweep runs (server local time). |

Per-organization overrides live in the organization config
(`organizations.config.features`), not in the environment:

| Feature key | Type | Purpose |
|---|---|---|
| `workshop_teacher_pilot` | bool | Teacher must complete the workshop before students can launch (see §4). |
| `workshop_retention_days` | int | Overrides `WORKSHOP_RETENTION_DAYS` for this organization. |
| `require_reconsent_on_version_change` | bool (default **true**) | Re-ask students to accept the notice when its version changes. |

Legacy/optional: `WORKSHOP_TOKEN_TTL` remains as a module constant alias, but
`WORKSHOP_TOKEN_TTL_SECONDS` is what the token issuer reads.

---

## 2. Data lifecycle (retention)

Three data categories age differently, and only one of them is deleted
automatically:

| Category | Retention behaviour | Where it lives |
|---|---|---|
| **Uploaded document + KB collection** | **Deleted** by the sweep once the session is older than the window | KB server (`collections`, Chroma, files) |
| **Conversation, reflection, build state, evaluation** | **Only reported** (`expiring_soon` on the teacher dashboard). Never deleted silently — this is the assessed work | `lti_workshop_sessions`, `workshop_evaluations` |
| **Assistant built by the student** | **Never** deleted automatically — the work product survives (portfolio/export depends on it) | `assistants` |

The sweep also clears the session's KB binding so a deleted collection is not
retried forever. If the KB server is unavailable, the failure is logged and
**nothing on the LAMB side is touched**; the next sweep retries (deletions are
idempotent).

Ordering note: remote deletion happens **before** local erasure, deliberately.
The plan's failure-mode table asks for "no half-delete", which is only true if a
KB outage aborts the operation before anything local is removed.

The teacher dashboard shows a permanent warning when student work goes to an
**external** model provider but no retention window is configured.

---

## 3. Deleting a student's data (two levels)

Both actions are on the teacher dashboard, per student row.

| Action | Endpoint | What it removes | What it keeps |
|---|---|---|---|
| **Erase** (default) | `POST /lamb/v1/lti/workshop/dashboard/sessions/{sid}/data/erase` | Conversation, reflection, build state, evaluation, the uploaded document and its KB collection, the assistant's RAG binding | The assistant itself, the roster row, the session row |
| **Delete all** (purge) | `DELETE /lamb/v1/lti/workshop/dashboard/sessions/{sid}/data?confirm=<name>` | Everything above **plus the assistant row** | The session row, with `assistant_id` set to `NULL` |

`purge` is irreversible and requires the teacher to type the student's name (or
email) as `confirm`; without it the API answers `400`. Both routes require a
valid dashboard token bound to the activity.

---

## 4. Teacher-first pilot gate

When `features.workshop_teacher_pilot` is on for the organization:

* **students** who launch before the teacher has run the workshop see a waiting
  page (`workshop_pilot_required.html`, four languages) — not an error;
* the **teacher** who has not yet run it is redirected into the wizard as a
  pilot (their roster row and session are flagged `is_pilot`, and the consent
  page is skipped because they configured the disclosure themselves);
* submitting the pilot sets `lti_activities.pilot_completed_at` and opens the
  activity for students.

Three deliberate limits:

1. **Per teacher.** The gate asks *this* owner to pilot; a colleague's pilot
   does not unblock them.
2. **Never hijacks a running class.** If the activity already has submitted
   sessions, the gate does not engage at all.
3. **Escape hatch.** The owner can add `?skip_pilot=1` to the launch URL; the
   bypass is written to the audit log (`workshop.pilot_skip`).

Pilot runs are excluded from `total_students`, the student list and the session
statistics — a teacher must never appear as their own student. `is_pilot` is
stored on **both** `lti_activity_users` (the roster row, which is what the count
reads) and `lti_workshop_sessions`.

---

## 5. Consent notice and versions

The consent page is server-rendered (`workshop/templates/consent.html`) with
copy from `workshop/i18n.py` (`CONSENT_STRINGS`, en/es/ca/eu). It discloses the
three purposes (build, test-chat, model-based evaluation), the retention
behaviour, and **which model class actually sees the work** — resolved at
request time from the same configuration the completion pipeline uses
(`GET /lamb/v1/workshop/consent/info`), never hard-coded, so the page cannot
describe a setup the deployment does not have.

`CONSENT_VERSION` (in `workshop/i18n.py`) is stored per student in
`lti_activity_users.consent_version`. Bump it whenever the disclosure changes
materially: with `require_reconsent_on_version_change` on (the default),
returning students are asked again, and the dashboard shows how many
(`pending_reconsent`) so the teacher can warn the class in advance.

---

## 6. Migration notes

Schema version **31** adds:

* `lti_activity_users.consent_version` (TEXT)
* `lti_activity_users.is_pilot` (INTEGER, default 0)
* `lti_workshop_sessions.is_pilot` (INTEGER, default 0)
* `lti_activities.pilot_completed_at` (INTEGER)
* index `idx_*lti_activities_workshop_pilot(organization_id, activity_type)`

Migrations run automatically at startup (`MigrationRunner.apply_all`), are
idempotent, and existing rows keep their behaviour (all new columns default to
"off"/NULL).

### One-off: repairing pre-S1 assistant KB bindings

Before the S1 fix, a crafted request could persist another session's collection
id on a workshop assistant, which every later RAG turn would query. New writes
are rejected (403) and the retrieval paths strip foreign ids defensively, but
rows written **before** the fix need cleaning:

```bash
# dry run — prints what it would change
docker compose exec backend python tests/workshop_repair_kb_bindings.py

# apply
docker compose exec backend python tests/workshop_repair_kb_bindings.py --apply
```

Only assistants owned by the synthetic student domain (`@lamb-lti.local`) with a
workshop session are touched; the script is idempotent.

---

## 7. Testing

| Layer | Command |
|---|---|
| Backend (container) | `docker compose exec backend python -m pytest tests/ -q -k workshop` |
| Frontend unit | `docker compose exec frontend npx vitest run` (or `npm run test:unit` on the host after `npm install`) |
| e2e track A (route-mocked, no model) | `cd testing/playwright && npm run test:workshop:ui` |
| e2e track B (real model journey) | `WORKSHOP_E2E=1 WORKSHOP_URL='…' npm run test:workshop` |
| Manual smoke (whole loop) | `docker compose exec backend python tests/mvp_smoke.py` |

Track A is the per-PR gate (`.github/workflows/workshop-ui.yml`); track B runs
on `workflow_dispatch` or before a release
(`.github/workflows/workshop-e2e.yml`). See `testing/playwright/README.md`.

---

## 7.1 Formative evaluation and small-context models

The rubric evaluation sends a **large** prompt: the rubric instructions alone are
~4 900 characters (≈1 250 tokens), and the student transcript is added on top. A
small local model shares one window between prompt and answer, and Ollama's
default window is 2 048 tokens — so the *answer* is what gets cut off, mid-JSON,
and the evaluation used to be reported as "feedback could not be generated" even
though the model had produced every criterion.

Measured on this deployment (`llama3.2:latest` via Ollama, 3-criterion rubric):

| | prompt | answer | outcome |
|---|---|---|---|
| Before (verbose feedback) | ~6 130 chars ≈ 1 533 tokens | 1 189 chars, **never closed** | parse error, evaluation discarded |
| After (concise feedback) | ~6 130 chars ≈ 1 533 tokens | 788 chars, closed | `completed`, 12/12 |

Three layers now protect this:

1. **The parser salvages a cut-off response.** `parse_evaluation_json_detailed`
   closes an unterminated string/bracket structure and tolerates trailing
   commas, so the recovered criteria and score are kept. The clipped sentence
   gets an ellipsis, and the evaluation is stored as `completed` with a note in
   `error_message`; the student's feedback panel shows a short "the model stopped
   before finishing" hint instead of an empty result.
2. **The answer is asked to be short.** The JSON directive caps each criterion's
   `feedback` at two short sentences, which is what created the headroom above.
3. **The prompt transcript is bounded** (`MAX_EVALUATION_TRANSCRIPT_CHARS`,
   4 000 chars) with an explicit `[... conversation shortened for length ...]`
   marker. Only the model's copy is trimmed: the teacher dashboard still shows
   the full transcript, and the graded parts (build decisions, reflection,
   observation snapshots) are kept at both ends.

**Deployment-level remedy**, if you have the VRAM: raise the model's context so
nothing has to be trimmed — e.g. an Ollama Modelfile with `PARAMETER num_ctx
4096`, or a larger small-fast-model. The connector forwards only
`temperature`/`top_p`/`top_k` from the request, so `num_ctx` is a model-side
setting today, not a per-request one.

When feedback does fail, the raw model output and the error are stored on the row
(`workshop_evaluations.raw_response` / `error_message`) and shown in the
teacher's session detail — start there rather than re-running blind.

### 7.2 The rubric decides which criteria exist

A model filling in a rubric will happily rename criteria, invent them, drop some
and repeat others. Observed in the wild: a 3-criterion rubric came back with
**20 rows** — the model turned the transcript's section headings into four
"criteria" and repeated that set five times — and the student's panel showed the
same four headings over and over with no relation to what the teacher had
defined.

`normalize_evaluation` now aligns the model's answer with the rubric:

* each returned entry is matched to a rubric criterion by name, id, or a
  decorated/partial form of the name ("criterion: instruction clarity (30%)");
* entries that match nothing are **dropped** (counted and logged — a mismatch
  never becomes rows on a student's screen);
* repeats collapse to one row (first entry wins) and the output is re-ordered to
  the rubric;
* the **rubric's** label, weight and criterion id are what get stored and shown;
* rows with no level, score or feedback are not rendered.

If *nothing* matches while the model did return criteria, the run is reported as
`failed` with an explicit message rather than showing invented criteria as if
they were the rubric. If only some rubric criteria were scored, the evaluation
is kept and the gap is recorded in `error_message`; the student sees a short
"some of this feedback may be incomplete" note (four languages).

The prompt also spells the criteria out (`build_evaluation_directive`) and tells
the model to use those names verbatim and not to add, rename, split, merge or
repeat them — prevention first, validation second.

---

## 8. Known limitation: KB server credentials

The KB server authenticates with a single global API key that carries no
identity, so "who may read which collection" has no tenant boundary on the KB
side. S1 closed the **student** path (a client-supplied `kb_id` is now an
assertion, not a choice, and the retrieval paths restrict workshop assistants to
their own session collection), but any component holding that token can still
read any collection whose id it knows.

The risk is **accepted** for now and tracked outside the codebase (see the
`Workshop-后续跟进` note, entry F1). Multi-org isolation via per-org KB
instances or identity-bearing tokens is the medium-term fix.

---

## Related documentation

* `Documentation/deployLocal.md` — running the stack locally
* `testing/playwright/README.md` — the two workshop e2e tracks
* `backend/lamb/modules/workshop/` — module docstrings: routers, KB wiring,
  retention, i18n, evaluation
