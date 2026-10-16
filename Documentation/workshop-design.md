# AI Workshop — design and decision record

This page records **how the AI Workshop fits into LAMB, and why it was built
this way**. It is the companion to
[workshop-operations.md](./workshop-operations.md), which covers configuration,
retention, deletion and testing.

It also defines the **decision IDs** that appear in code comments and tests
(`S1`, `W1`–`W3`, `D1`–`D7`, `C1`–`C22`). If a comment says "decision C13" or
"the S1 fix", §4 is where that ID is defined.

> State described: branch `AI-workshop`, schema v31, as of 2026-10-16.
> Upstream facts in §3 were checked on GitHub on 2026-10-15. Check them again
> before you rely on them.

---

## 1. What the workshop is for

Students build a small AI assistant step by step: they write instructions,
attach one document, check that retrieval finds it, pick a tool, chat with
the assistant and reflect on their design. Alongside the wizard, an
**observability panel** shows exactly what the assistant received before it
answered: system prompt, retrieved excerpts with similarity, the request body,
and when tools were called.

The learning goal is that an assistant is not a black box: it only knows what
it is given on each turn. The panel is the core feature. Without it the
workshop is just another chatbot builder, so design choices that make the panel
earlier, more honest or more visible take priority.

Scope is a deliberately lean MVP: one document, one knowledge base, one tool,
one conversation, one reflection and one piece of formative feedback per
student. The intended audience runs from secondary school to teacher training,
and the rollout strategy is **teacher first**: a teacher runs the workshop
before their students do (enforced by the pilot gate, C13).

---

## 2. Architecture

### 2.1 Component map

```
Moodle ── LTI launch ──▶ lti_router.py  (/lamb/v1/lti)
                           │ activity_type == "workshop"
              ┌────────────┴─────────────┐
           student                    instructor
              ▼                           ▼
  modules/workshop/service.py     modules/workshop/dashboard.py
  virtual principal + token        Jinja dashboard (workshop_dashboard.html)
              │                    /lamb/v1/lti/workshop/dashboard*
              ▼ redirect
  /m/workshop/{activityId}?token=…   (SvelteKit route inside the main SPA)
              │ REST + SSE
              ▼
  /lamb/v1/workshop/sessions/{sid}/…   modules/workshop/routers.py
     ├─ doc / kb ──────▶ modules/workshop/kb.py ──▶ KB server (as the activity owner)
     ├─ chat ──────────▶ completions/main.py: run_lamb_assistant
     │                     ├─ simple_rag ─────────▶ KB server
     │                     ├─ ToolLoop: calculator · kb_query · sandbox_exec (stub)
     │                     └─ SSE: content · observability · tool_event · tool_messages · error
     └─ submit/evaluate ▶ modules/workshop/evaluation.py ──▶ rubric engine + small-fast model
```

### 2.2 Where the workshop plugs into existing layers

| Layer | What the workshop adds | Note |
|---|---|---|
| LTI (`lamb/lti_router.py`) | `activity_type` dispatch on both the student and the instructor branch; setup form gains a type selector and an optional rubric; pilot gate | Chat activities are unchanged (`activity_type` defaults to `'chat'`) |
| Module package (`lamb/modules/`) | `discover_modules()` registry; `WorkshopModule` exposes `get_routers()`, mounted by `lamb/main.py` under `/lamb/v1` → `/lamb/v1/workshop/*` | Its own registry, not the #277 framework (§3) |
| **API layer** | Student routes live on **LAMB Core** (`/lamb/v1/workshop`), not on the Creator Interface | Deliberate exception to "frontend → `/creator` → `/lamb/v1`": students have no `Creator_users` row, so they cannot use `/creator/*`. The module exposes its own restricted subset instead |
| Completion pipeline (`lamb/completions/`) | Observability frames, tool pass-through in connectors, `ToolLoop`, per-request RAG switch, error frames | Generic: any assistant can use them, but nothing changes unless the request asks for it |
| KB server | Per-session collection, created and queried server-side under the activity owner's identity | KB server is vendored; it is only called over HTTP |
| Rubric engine (`lamb/evaluaitor/rubric_service.py`) | Reused to build evaluation instructions; workshop adds transcript serialisation, the LLM call and persistence | |
| Database (`lamb/migrations.py`) | Migrations 26–31 (§2.9) | Central migrations file, not module-owned |
| Frontend (`frontend/svelte-app`) | Route `routes/m/workshop/[activityId]/`, components in `lib/components/workshop/` | Part of the main SPA build, not a separate module app |

### 2.3 Student identity: a virtual principal

On launch, `service.initialize_workshop_workspace` reuses the chat activity's
identity steps (OWI user, group, `lti_activity_users` row) but does **not**
send the student to Open WebUI. It creates or loads an `lti_workshop_sessions`
row and signs a short-lived token:

```
{ type: "workshop_student", scope: "workshop_student",
  activity_id, activity_user_id, owi_user_id, email, organization_id, session_id }
```

* No `Creator_users` row is created. The rejected alternative, real rows with
  `user_type='end_user'`, would add students to the organization's membership
  and spread "is this a workshop student?" checks across every Creator
  authorization path.
* Every workshop route checks that the token's `session_id` matches the URL
  and that the assistant belongs to that session. Students cannot publish,
  share or reach other tenants. Quotas per session: one assistant, one
  document (max 10 MB), one KB.
* The token travels in the URL (`?token=`). TTL is 1800 s with proactive
  renewal (C4, C5).
* Student-owned assistants have the synthetic owner domain `@lamb-lti.local`.
  That domain is the cheap marker the retrieval guard uses (C2).

**Consequence: no organization resolves for a student-owned assistant.**
`OrganizationConfigResolver(assistant.owner)` raises for these assistants, so:

* the chat completion uses the connector and model **pinned in the assistant's
  metadata**. The wizard sets them from the runtime config
  `LAMB_CONFIG.workshop` (`static/config.js`; fallback `ollama` / `qwen3.5:9b`
  in `lib/config.js`). `resolve_completion_config` honours pinned values when
  resolution fails;
* retrieval (`simple_rag`, `kb_query`) falls back to the environment KB config
  (`LAMB_KB_SERVER`, `LAMB_KB_SERVER_TOKEN`);
* work that needs a real identity runs as the **activity owner**: KB
  ingestion and queries from the workshop routes, formative evaluation (the
  owner's small-fast model) and the consent disclosure.

§6 lists the limits this creates.

### 2.4 Knowledge base wiring

* The KB is created **server-side under the activity owner's creator
  identity** through `KBServerManager`, so it is registered in LAMB and the
  teacher can see it. If the owner's creator row is missing (historical data),
  `kb.py` calls the KB server directly with owner `workshop:{activity_id}` and
  logs a warning.
* Collection name: `ws-{activity_id}-{activity_user_id}`. The resulting
  `kb_id` is stored on the session row, and **the session is the only source
  of truth for it**. A client-supplied id is treated as a claim to check, never
  as a choice (S1, C1).
* All four readers of `assistant.RAG_collections` (`simple_rag`,
  `context_aware_rag`, `hierarchical_rag` and the `kb_query` tool) call
  `kb.restrict_collections_for_assistant`. For a workshop assistant this keeps
  only the session's own collection (C2).

### 2.5 Completion pipeline additions (SSE dialect)

The workshop chat (`POST /sessions/{sid}/assistant/{aid}/chat`) calls
`run_lamb_assistant` and streams the normal OpenAI-style deltas plus these
frames:

| Frame | When | Content |
|---|---|---|
| `{"type":"observability","data":{…,"phase":"request"}}` | Tool path: **first frame**, before the first LLM call (D1, C11) | `system_instructions`, `user_input`, `rag_context`, `retrieved_sources[]` (similarity, content clipped to 500 chars), `final_llm_messages`, `tools`, `request_body {model, tools, messages}`, `rag_mode` |
| `{"type":"observability","data":{…,"phase":"result"}}` | Just before `[DONE]` | Same fields, with the messages the model finally saw after any tool rounds |
| `{"type":"tool_event","data":{"type":"thinking"\|"tool"\|"tool_done",…}}` | During `ToolLoop` rounds | Same event shape as the AAC agent loop, so one telemetry contract serves both |
| `{"type":"tool_messages","data":{"messages":[…]}}` | After the tool rounds | Assistant `tool_calls` + `role:"tool"` results, for the client to resend on later turns |
| `{"type":"error","data":{"message","type"}}` | A failure inside the generator (`with_error_frame`) | Once headers are sent, an HTTP status is no longer available |

* **Opt-in per request**: frames are only emitted when the body contains
  `observability: true`; the workshop route sets it by default. There is no
  organization-level gate (§6).
* **Tools**: connectors accept `tools` / `tool_choice`. `ToolLoop`
  (`completions/tools/loop.py`) runs non-streaming function-call rounds
  (max 5), then streams the final text reply. Tool schemas are in
  `completions/tools/definitions.py`. The calculator evaluates an AST
  whitelist and never calls `eval`.
* **A/B switch**: the chat accepts `rag_mode ∈ {on, off}`. `off` sets the
  namespaced private key `_workshop_disable_rag` and removes `kb_query` from
  the tools (C10).

### 2.6 Formative evaluation

`evaluation.py` serialises the whole build into a transcript: build decisions,
the conversation including the tool trace, the three reflection answers, and
observation snapshots (`=== DESIGN QUESTIONS ===`,
`=== OBSERVABILITY SNAPSHOTS ===`). It builds the instructions with the rubric
engine and calls the activity owner's small-fast model asynchronously. Results
are stored in `workshop_evaluations`, a separate table:
`assistant_test_evaluations` is keyed by test run and does not fit.

* The rubric is attached per activity (`lti_activities.rubric_id`). Without a
  rubric, no feedback is generated.
* The score is a **suggestion**. Nothing is written to a gradebook, and the
  teacher always decides the grade.
* The rubric, not the model, decides which criteria exist. The parser can
  also recover a truncated answer. Both are described with measurements in
  [workshop-operations.md](./workshop-operations.md) §7.1–§7.2.

### 2.7 Teacher side

* The dashboard is a **server-rendered Jinja page**
  (`backend/lamb/templates/workshop_dashboard.html`). A Svelte teacher route
  was considered: Jinja needs no extra build and matches the existing chat
  dashboard. Access uses a dashboard token bound to the activity.
* Tool-usage statistics come from the persisted chat trace (`saved_chat`), not
  from a separate telemetry table.
* Pilot runs (C13) never count as students.

### 2.8 Frontend

* `routes/m/workshop/[activityId]/+page.svelte` is rendered client-side
  (adapter-static) and served by the backend SPA catch-all.
* `+layout.svelte` drops `Nav`, `Footer` and `AacSidebar` on workshop paths
  (`lib/workshop/workshopRoute.js`, C7). The creator session bootstrap is
  skipped there too, because the URL token is the only credential.
* `lib/services/workshopApi.js` (`wsFetch`) handles `token_expired`, renews
  the token and rewrites it into the URL with `history.replaceState`.
  `workshopChatService.js` parses the SSE dialect from §2.5.
* State lives in plain JS hooks so it can be unit-tested:
  `logic/workshopFormState.svelte.js` (wizard, reflection, A/B history) and
  `logic/workshopObservations.svelte.js` (per-step snapshots, D2).
* Strings use the flat `workshop.*` keys in `lib/locales/{en,es,ca,eu}.json`.
  The locale chain is in `lib/workshop/workshopLocale.js` (C6). The consent and
  pilot-wait pages are server-rendered, with their copy in
  `modules/workshop/i18n.py`.

### 2.9 Data model (schema v26–v31)

| Version | Change |
|---|---|
| 26 | `lti_activities.activity_type TEXT NOT NULL DEFAULT 'chat'` |
| 27 | Table `lti_workshop_sessions` (build state, saved chat, reflection, status) |
| 28 | KB and document binding columns on `lti_workshop_sessions` |
| 29 | `lti_activities.rubric_id` |
| 30 | Table `workshop_evaluations` |
| 31 | `consent_version`, `is_pilot` (roster and session), `lti_activities.pilot_completed_at`, pilot index |

All migrations are guarded (`_column_exists` / `_table_exists`) and
idempotent. These numbers collide with upstream `dev` (§3.3).

---

## 3. Relationship to the Activity Module System (#277)

### 3.1 Decision: an independent module, aligned with the contract ("route A")

Issue #277 proposes a generic framework for new LTI activity types
(`ActivityModule`, `LTIContext`, `SetupField`, automatic discovery). The
workshop is exactly such an activity type. When the workshop was designed,
the framework existed only on a feature branch with no date for merging. So
the workshop:

* ships its **own minimal `activity_type` column and launch dispatch**, and
  does not depend on #277 being merged;
* uses **method names from the `ActivityModule` contract**
  (`get_routers`, `get_migrations`, `on_student_launch`,
  `on_instructor_launch`, `get_dashboard_stats`, …) so a later move is smaller.

Rejected alternatives: building directly on the #277 branch (fast, but tied to
a moving, unmerged design), and skipping LTI to reuse the chat path (no module
boundary, and students would land in Open WebUI rather than a build wizard).

### 3.2 What "aligned" does and does not mean

Only the method names match. A later move into the framework is **not**
mechanical:

| Framework (`lamb-1.0-alpha`, `modules/base.py`) | Workshop today |
|---|---|
| Subclass of the `ActivityModule` ABC | Plain class `WorkshopModule`; the ABC does not exist in this tree |
| `name`, `display_name`, `description` | No `description` |
| `get_migrations()` returns the module's migrations | Returns `[]`; migrations live in the central `migrations.py` |
| Routers mounted at `/lamb/v1/modules/{name}/` | Mounted at `/lamb/v1/workshop/`; every frontend API path would change |
| `get_setup_fields() -> List[SetupField]` | Returns `[]`; type and rubric selectors are in `lti_router.py` / `lti_activity_setup.html` |
| `on_student_launch(ctx: LTIContext) -> RedirectResponse` (and the instructor equivalent, `launch_user`, `on_activity_(re)configured`) | Take a `dict`, return dicts; `on_activity_*` are empty |
| `get_dashboard_chats` / `get_dashboard_chat_detail` | Missing; the workshop dashboard has its own routes |
| `get_frontend_build_path()`: a separately built SPA at `/m/{name}/` | Returns the prefix `"/m/workshop/"`; the UI is a route in the main SPA |
| `LTIContext` carries `lis_result_sourcedid` (grade passback) | Not used; the workshop never writes grades |

### 3.3 Upstream state (checked 2026-10-15) — open

* The framework is **not** on upstream `main` or `dev`. It is on
  `lamb-1.0-alpha` (`backend/lamb/modules/{base.py,chat,file_evaluation}`),
  which has diverged from `dev`. The migration target for the workshop is that
  line, not a future merge of #277 into `main`.
* **Migration numbers collide.** Upstream `dev` is at `LATEST_VERSION = 32`:
  26 = `api_keys`, 27–31 reserved for the alpha line (alpha's 28 also adds
  `activity_type`), 32 taken; the next free number is 33. Upstream's
  `test_migration_runner.py::test_numbering_guard` rejects 27–31, and the
  runner refuses to start when a recorded version maps to a different
  migration. Before syncing with `dev`, renumber workshop migrations 26–31 to
  33+ and reconcile `activity_type` with alpha's 28. The upgrade path for an
  existing v31 database has not been tested yet.
* Still to decide: keep route A, or subclass alpha's `ActivityModule` and move
  to `/lamb/v1/modules/workshop/` (§3.2 lists what changes).

---

## 4. Decision record

### 4.1 Foundational decisions (design phase)

| Decision | Choice | Why |
|---|---|---|
| Scope | Full build flow: each student builds from scratch in a sandboxed workspace | The learning goal needs students to make the design choices themselves |
| Observability transport | Extra frames on the existing chat SSE stream | Smallest change; one socket. A separate debug endpoint was rejected |
| Tools | `calculator` + `kb_query`; `sandbox_exec` stays a stub (D7) | Students can watch the model decide to retrieve or compute; real code execution is the one high-risk item |
| Rollout | Teacher first | Train teachers before students |
| MVP | One document, one KB, one tool, one chat, one reflection, one feedback | Smallest complete loop |
| Module strategy | Route A (§3.1) | #277 was unmerged and still under discussion |
| Student identity | Virtual principal (§2.3) | Keeps students out of `Creator_users` and keeps authorization in one module |
| KB ownership | Activity owner's creator identity (§2.4) | Reuses tested `KBServerManager` code; the teacher sees the KB. Rejected: a service account (new configuration and operations work), direct calls only (no LAMB-side registration) |
| Teacher view | Jinja dashboard (§2.7) | No new frontend build |
| Grades | Formative only; never written to a gradebook | The teacher decides the grade |

### 4.2 Review findings (S / W / D)

A conformance and security review of the branch, against the original
proposal, produced these items. Severity: **S** = security blocker,
**W** = must fix before a pilot, **D** = needed for the learning goal.

| ID | Finding | Resolution |
|---|---|---|
| **S1** | A student could read another student's KB. The four entry points (create/patch assistant, connect/query KB) accepted a client-supplied `kb_id` / `rag_collections`. Collection ids are sequential and the KB server does not check ownership | C1–C3; regression tests in `test_workshop_kb_ownership.py` |
| W1 | The 30-minute token expired with no renewal, and a page reload could not recover | C4, C5 |
| W2 | Student-facing text was hard-coded English, and students saw the Creator navigation | C6, C7, C19 |
| W3 | Consent did not mention model-based evaluation; there was no retention or deletion path | C8, C9, C17, C18, C20 |
| D1 | The panel updated only after the answer had streamed | C11 (`phase: "request"` frame) |
| D2 | The panel appeared only in step 5 | Per-step snapshots (`workshopObservations.svelte.js`) and C16 |
| D3 | No way to compare answers with and without the knowledge base | C10 + `RagComparison.svelte` |
| D4 | "Teacher first" was only a dashboard label | C13 + migration 31 |
| D5 | Reflection was an unguided text box | C12 + transcript sections |
| D6 | Scores dominated the formative feedback | C14 |
| D7 | `sandbox_exec` is a stub | **Not done** (§5) |

### 4.3 Implementation decisions (C1–C22)

| ID | Decision | Why / rejected alternative | Code |
|---|---|---|---|
| C1 | `kb_id` is a claim to verify. The server always uses the session's id. A different client value → **403** + warning log. A client value when the session has no KB → **400** (a state error, not an attack) | 403 makes attack attempts visible. The separate 400 tier keeps a legitimate recovery after an erase from being logged as an attack | `routers._resolve_session_kb_id`, `_assert_rag_collections_allowed` |
| C2 | Retrieval also enforces it: `restrict_collections_for_assistant` keeps only the session collection for workshop assistants. It returns early unless the owner ends in `@lamb-lti.local` | Route checks alone are a single point of failure. The domain check avoids a DB query on every non-workshop completion | `workshop/kb.py`; called from the four `RAG_collections` readers |
| C3 | One-off repair script for rows written before the fix | A poisoned `RAG_collections` leaks on every later turn, so blocking new writes is not enough | `backend/tests/workshop_repair_kb_bindings.py` (dry run by default) |
| C4 | Token TTL stays **1800 s**. Renewal is proactive (`POST /sessions/{sid}/refresh`, requires a still-valid token); an expired token is never renewed | Rejected: a 4 h TTL. The token is in the URL and ends up in browser history | `service.workshop_token_ttl`, `WORKSHOP_TOKEN_TTL_SECONDS` |
| C5 | Expiry returns 401 with `detail: "token_expired"`, a plain string | The frontend can tell expiry from forgery, and existing `err.detail` rendering is unchanged. `decode_token` keeps its behaviour; `decode_token_ex` adds the reason | `auth.decode_token_ex` |
| C6 | Locale chain, on workshop routes only: `?lang=` (from LTI `launch_presentation_locale`) → `localStorage.lang` → browser → `en`. Server pages: `?lang=` → activity locale (reserved) → `Accept-Language` → `en` | Creator users' default language is not affected. Many Moodle sites do not send the locale | `workshopLocale.js`, `i18n.resolve_locale` |
| C7 | The student shell is the main layout without `Nav` / `Footer` / `AacSidebar` | Rejected: a separate layout file, which conflicts more with SvelteKit's layout tree | `+layout.svelte`, `workshopRoute.js` |
| C8 | Consent is versioned (`CONSENT_VERSION` → `lti_activity_users.consent_version`) | A student has to have agreed to the notice as it reads now | `workshop/i18n.py` |
| C9 | Retention differs per data category, and automatic deletion is off by default: KB material is deleted; conversations and reflections are only reported; assistants are never deleted; external provider + no retention window → warning | Assessed work and the future portfolio feature keep working. No "delete on archive", because LAMB has no activity archive path | `workshop/retention.py` |
| C10 | KB-off is per request: `rag_mode` → `_workshop_disable_rag`, stripped by `learning_assistant_proxy` and popped in `run_lamb_assistant`; `kb_query` is removed as well | The shared proxy forwards the raw body, so a plain key would let any caller turn RAG off. Leaving `kb_query` in would still give the model the course material. Never change `RAG_collections` to run an experiment | `completions/main.py: workshop_rag_mode` |
| C11 | On the tool path, the `request` observability frame is the first frame; the old eager connector call (its result was thrown away) is removed; the generator is wrapped in `with_error_frame`; the configuration pre-check stays outside the generator | Otherwise the panel waits a whole model turn, and a failure mid-stream leaves the UI stuck on "streaming…" | `completions/main.py` |
| C12 | Reflection = three fixed questions stored in `build_state.reflectionAnswers`. `composeReflection()` still produces the legacy `reflection` string | No migration needed; `avg_reflection_length` and older sessions keep working | `workshopFormState.svelte.js` |
| C13 | Pilot gate: **per owner**; skipped when the activity already has submitted sessions; `?skip_pilot=1` only for the owner and audited (`workshop.pilot_skip`); `is_pilot` on both the roster row and the session; `get_activity_students(include_pilot=True)` keeps its default | A running class is never hijacked. The teacher never counts as their own student (`total_students` counts roster rows) | `dashboard.is_teacher_pilot_blocking`, `lti_router._pilot_skip_granted` |
| C14 | Scores sit in one collapsed `<details>`. The backend and the prompt are unchanged | Rejected: removing scores from the prompt (less structured feedback, and teachers need them) | `FormativeFeedback.svelte` |
| C15 | KB deletion depends on the collection owner: a creator id → `KBServerManager.delete_knowledge_base`; `workshop:{activity_id}` → `DELETE /collections/{id}` directly | `delete_knowledge_base` checks ownership and would return 403 for the fallback owner | `kb.delete_session_kb` |
| C16 | "How was my document chunked" comes from the KB **files registry** (chunk count, chunk size/overlap, size, status) through a read-only proxy. A probe query only shows hits | Rejected: inferring chunks from a probe, which returns only `top_k` hits and depends on indexing timing | `GET /sessions/{sid}/doc/files` |
| C17 | The consent page's model disclosure is resolved when the page is requested (`GET /workshop/consent/info` → `model_class: local\|external\|unknown`), never hard-coded | A server-side page cannot see `config.js`, assistant metadata or org overrides. Misleading consent is worse than none. See §6 for the remaining gap | `routers.resolve_consent_model_info`, `classify_model_class` |
| C18 | Two deletion levels: `erase` (default; keeps the assistant) and `purge` (also deletes the assistant, needs the student's name typed to confirm, sets `assistant_id` to NULL) | Erase alone cannot honour "delete everything" (the system prompt is the student's own text). Purge alone turns a wrong upload into losing the whole piece of work | `retention.erase_session_content`, `purge_session` |
| C19 | 4-language switcher in the student shell, writing `localStorage.lang` | Without `Nav` there is no other way to switch, and a teacher must be able to correct the class language | `LocaleSwitcher.svelte` |
| C20 | Re-consent on by default (`require_reconsent_on_version_change`); the dashboard shows `pending_reconsent` | The new copy widened what student work is used for. The count lets the teacher warn the class beforehand | `dashboard.py` |
| C21 | Two e2e tracks: route-mocked UI tests + pytest are the PR gate; the real-model journey runs only before a release. The KB credential risk is accepted (§6) | Rejected: a real-model journey as the regression gate; in practice it would never run | `testing/playwright/tests/workshop_*.spec.js`, `.github/workflows/workshop-*.yml` |
| C22 | Removing the attached document is a server call (`DELETE /sessions/{sid}/assistant/{aid}/doc`): the KB goes first, then the session's document binding and the assistant's RAG wiring are cleared. Chat, reflection and wizard state are kept (the `erase` level of C18, narrowed to the document). The browser clears its own state only after the server confirmed. Idempotent | Rejected: clearing only the browser. The session keeps the one-document quota (§2.3), so the next upload answered 429 while the UI looked empty | `routers.remove_workshop_document`, `LambDatabaseManager.clear_workshop_session_document` |

---

## 5. Deliberately not done

These items are left out on purpose. If you pick one up, revisit the reason
first.

| Item | Decision and reason |
|---|---|
| Real `sandbox_exec`, or a zero-risk replacement tool (D7) | Neither for now. The tool always refuses; **no flag enables it**. Its definition stays so step 4 can show it disabled. If pilots say the tools feel thin, update `WORKSHOP_TOOLS` (`completions/tools/definitions.py`) and the step-4 UI together |
| 4-hour token TTL | Rejected (C4) |
| Deleting KB material when an activity is archived | LAMB has no archive path; deletion follows the session lifetime (C9) |
| Hard-coded model description on the consent page | Rejected (C17) |
| Single-level deletion | Rejected (C18) |
| Real-model e2e as the regression gate | Rejected (C21) |
| Linking each reflection answer to an observation snapshot (`build_state.observationLinks`) | Dropped. The three questions + transcript sections already meet the goal; a selector per question costs UI weight with unproven value. Revisit after a pilot |
| Long-term ideas | Portfolio / PDF export, a student-facing consent switch, reusable activity templates, longitudinal analytics, mobile and accessibility work, provider switching and prompt-version comparison, showing model reasoning ("thinking"), multimodal assistants, publishing student assistants, a tool-telemetry table, chat history with stored observation snapshots |

---

## 6. Known limitations and open items

| # | Item | Status |
|---|---|---|
| 1 | **KB server credentials carry no identity.** One global API key; the KB server only checks that a collection exists. S1 closed the student path, but any component holding the key can read any collection whose id it knows. Non-workshop assistants get no ownership check at retrieval | Accepted risk. Options, cheapest first: assert ownership on every LAMB→KB call; identity-bearing KB tokens (changes the vendored KB server, so upstream); a KB instance per organization. See [workshop-operations.md](./workshop-operations.md) §8 |
| 2 | **The consent disclosure and the chat model can differ.** `consent/info` reports the activity owner's default org model. The student's chat uses the model pinned from `LAMB_CONFIG.workshop` (§2.3). Evaluation uses the owner's small-fast model | Keep `LAMB_CONFIG.workshop` in the same model class (local/external) as the org default. Fix: derive the pinned model from org config, or make `consent/info` report the pinned one |
| 3 | **Split KB configuration in multi-org deployments.** Ingestion runs as the activity owner (org KB config); retrieval runs for the student-owned assistant (environment fallback). If an organization overrides the KB server, the two can point at different servers | Single-org deployments are unaffected. Not tested on a multi-org setup |
| 4 | **Observability has no org-level gate.** Any caller allowed to chat with an assistant can send `observability: true` and receive its system prompt and retrieved context (an "anyone with access can see the internals" model, accepted for the workshop) | An org feature flag inside `observability_enabled()` was planned but never added |
| 5 | **Reconfiguring after submissions.** "Manage activity" on the dashboard can change the rubric after students have submitted; re-evaluation then uses the new rubric, without warning | Known. Options: lock Manage once submissions exist, warn, or remove it from the workshop dashboard |
| 6 | **Small-fast model providers.** `small_fast_model_helper` imports `anthropic` / `google` connectors that do not exist, so an org configured with those providers breaks formative evaluation | Pre-existing debt outside the workshop |
| 7 | **Upstream alignment.** Migration numbering and the #277 target (§3.3) | Open; decide before syncing with `dev` |
| 8 | **Translations.** The `eu` and `ca` copy (`workshop/i18n.py`, frontend locales) was written by the implementer | Needs a native-speaker review |
| 9 | **Frontend gates.** `svelte-check` has a large pre-existing error baseline, and prettier fails on `.svelte` files in the dev container, so the workshop uses vitest + eslint + `vite build` | Tooling issue, not specific to the workshop |
| 10 | **Track B** (real-model e2e) has not been run against a release yet | Run it before the first release that includes the workshop |
