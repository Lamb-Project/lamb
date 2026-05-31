# Pre-existing tech debt — handoff for a fresh Claude

This file documents real defects discovered during the Knowledge-Store lifecycle verification run on **2026-05-03** (`test-results/lifecycle-20260503T181108Z/`) that were **deferred** because they predate the run and are unrelated to the new Knowledge Store stack. The user has explicitly authorized handing them off to a separate Claude session.

The rest of this document is written to be picked up cold by another Claude. Treat each section as an independent work package; you can attack them in any order, but the order below is roughly increasing-blast-radius. Every issue includes a reproduction, the exact files, and the fix shape.

If you are starting a session on this:

1. Read `CLAUDE.md` at the repo root first. It states the architecture and which directories are vendored / do-not-modify.
2. Verify the bug still exists before fixing — months may have passed; some of these may already be fixed by a coworker.
3. After each fix, re-run the suite that surfaced it and only commit the fix once that suite is green and unrelated suites still pass.
4. Don't bundle unrelated fixes into one commit. One subject = one commit.

---

## 1. Backend dependency CVEs in `backend/requirements.txt` (deferred — security)

`pip-audit` against `backend/requirements.txt` flagged **3 CRITICAL + 22 HIGH** CVEs in pinned versions. Full machine-readable report: `test-results/lifecycle-20260503T181108Z/01_lints/pip_audit_backend.json`.

### Critical
| Package | Pinned | Fix | CVE |
|---|---|---|---|
| `torch` | `2.3.1` | `>=2.6.0` | GHSA-53q9-r3pm-6pq6 — `torch.load` RCE |
| `nltk` | `3.8.1` | `>=3.9.3` | GHSA-7p94-766c-hgjp — Zip Slip |
| `llama-index` | `0.10.56` | `>=0.12.28` | GHSA-v3c8-3pr6-gr7p — SQL injection |

### High (selected — full list in JSON)
- `python-multipart@0.0.9` → `>=0.0.22` (DoS + arbitrary-file-write)
- `aiohttp@3.9.5` → `>=3.13.4` (zip-bomb + 24 lower bugs)
- `mcp@1.14.0` → `>=1.23.0` (DNS rebinding default-off)
- `transformers@4.42.3` → `>=4.48.0` (3 deserialization HIGHs)
- `pillow@10.3.0` → `>=12.2.0` (PSD OOB write, FITS gzip bomb)
- `protobuf@4.25.9` → `>=5.29.6` (JSON recursion DoS)
- `starlette@0.37.2` → `>=0.40.0` (multipart DoS)
- `google-cloud-aiplatform@1.60.0` → `>=1.133.0` (predictable bucket naming)
- `llama-index-cli@0.1.13` → `>=0.4.1` (OS command injection)

### Why this is risky to fix in one go
- `torch` and `transformers` major-version bumps will cascade through every model loader in `backend/lamb/completions/connectors/` and any embedding code paths.
- `llama-index@0.10.x → 0.12.x` was a major API rewrite; chunkers and retrievers in `backend/lamb/completions/rag/` will likely need migration.
- `python-multipart` and `starlette` are FastAPI's transitive deps — bump them and you may need to bump `fastapi` too.

### Recommended approach
1. Phase A — low-blast bumps in one commit: `python-multipart`, `pillow`, `protobuf`, `aiohttp`, `nltk`, `requests` (if pinned). Re-run `backend` pytest + a smoke chat. Should be safe.
2. Phase B — `starlette` + verify `fastapi` compatibility. Re-run.
3. Phase C — `transformers` + `mcp`. Re-run.
4. Phase D (own PR) — `torch` bump. Test every connector that loads a model.
5. Phase E (own PR) — `llama-index` bump. Test every RAG processor in `backend/lamb/completions/rag/`.

Each phase its own commit, its own test pass.

---

## 2. Legacy stable KB-server cannot reach Ollama from inside its container

### Repro
```bash
cd /home/novelia/Documents/lamb/lamb-kb-server-stable/backend/tests
source .venv/bin/activate
pytest -m "not slow" -v
# Expect: 4 failed + 43 errored + 19 passed
```

All non-passing cases share one root cause: `POST /collections` returns 400:
```
Failed to validate ollama embeddings (custom configuration).
Endpoint: http://localhost:11434/api/embeddings
Error: ConnectionError: Failed to connect to Ollama
```

### Why it fails
The legacy stable KB Server runs in the `kb` Docker service (`docker-compose-example.yaml`). Inside that container `localhost` is the container itself, not the host. Ollama runs on the host. The new `kb-server` (port 9092) gets it right via `http://172.18.0.1:11434` (the docker0 bridge gateway). The legacy one was never updated.

### Fix
Edit `lamb-kb-server-stable/backend/.env`:

```diff
- EMBEDDINGS_ENDPOINT=http://localhost:11434/api/embeddings
+ EMBEDDINGS_ENDPOINT=http://172.18.0.1:11434/api/embeddings
```

Or, more robustly (works on macOS where the bridge IP differs), add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `kb` service in `docker-compose-example.yaml` and use `http://host.docker.internal:11434/api/embeddings`.

After the fix, re-run the test command above; expected ≥ 60/66 passing (some integration tests may still be slow-skipped).

### Constraint
The `lamb-kb-server-stable/` source tree is a vendored snapshot per `CLAUDE.md` — do not modify code inside it. The `.env` file and the compose entry are project-local and ARE editable.

---

## 3. Frontend ESLint — 369 pre-existing errors

### Repro
```bash
cd /home/novelia/Documents/lamb/frontend/svelte-app
npx eslint .
# Expect: 369 problems (369 errors, 0 warnings)
```

Full output: `test-results/lifecycle-20260503T181108Z/01_frontend/eslint_full.log`.

These errors were hidden until this run because the previous prettier (`prettier@3.8.x` resolved from `^3.4.2`) crashed on every `.svelte` file, causing the npm `lint` script (`prettier --check . && eslint .`) to short-circuit before ESLint ran. We pinned prettier to `3.5.3` (commit on `frontend/svelte-app/package.json`) which made prettier work and unmasked these.

### Rule breakdown
| Count | Rule | Nature |
|---|---|---|
| 163 | `no-unused-vars` | unused `error` in catch blocks, unused imports, unused props |
| 84 | `svelte/require-each-key` | `{#each items as item}` missing `(item.id)` keying |
| 83 | `svelte/no-navigation-without-resolve` | `goto('...')` should use `resolve()` for type-safe routes |
| 20 | `svelte/no-at-html-tags` | `{@html ...}` flagged as XSS risk; needs review case-by-case |
| 9 | `svelte/no-unused-svelte-ignore` | dead `<!-- svelte-ignore ... -->` comments |
| 8 | `svelte/prefer-svelte-reactivity` | use `$state.raw()` / `$derived()` correctly |
| 1 | `svelte/prefer-writable-derived` | use `$state` instead of writable `$derived` |
| 1 | `no-useless-catch` | `catch (e) { throw e; }` |

### Fix shape per rule
- `no-unused-vars`: rename `error` → `_error` (lint config typically allows underscore-prefix). For unused imports, delete. For unused props on a Svelte 5 component, delete from `let { ... } = $props()`.
- `svelte/require-each-key`: every `{#each items as item}` should be `{#each items as item (item.id || item.uuid || item)}`. Pick the stable identifier; `(item)` itself is OK if the value is a primitive.
- `svelte/no-navigation-without-resolve`: import `{ resolve }` from `$app/paths` and call `goto(resolve('/some/route'))`. SvelteKit's docs explain.
- `svelte/no-at-html-tags`: each instance is its own decision. If the content is markdown, prefer `marked(...)` already in deps; if it's trusted server output, document with a `// eslint-disable-next-line svelte/no-at-html-tags -- reason` comment.
- The remaining low-count rules are point fixes in 1–2 files each.

### Suggested attack plan
1. Run `npx eslint . --rule '{"no-unused-vars":"off"}' --rule '{"svelte/no-navigation-without-resolve":"off"}'` and confirm only the genuinely meaningful rules fire — that gives you a smaller starting set.
2. Tackle `no-unused-vars` first (mechanical, low risk).
3. Tackle `svelte/require-each-key` next (mechanical, but each fix needs the right key chosen).
4. Tackle `svelte/no-navigation-without-resolve` last (minor refactor, every call site changes).
5. Re-test each component after change with `npm run dev` — keying changes especially can affect render behaviour.

---

## 4. Frontend `svelte-check` — 776 errors / 40 warnings on 61 files

### Repro
```bash
cd /home/novelia/Documents/lamb/frontend/svelte-app
docker stop lamb-frontend-1   # the dev container fights for .svelte-kit/ ownership
npm run check
# Expect: 776 errors, 40 warnings, 61 files with problems
```

Full output: `test-results/lifecycle-20260503T181108Z/01_frontend/svelte_check_full.log`.

Per `CLAUDE.md`, the frontend is intentionally JavaScript with JSDoc, not TypeScript. But `svelte-check` runs against `jsconfig.json` and reports type issues anyway. The errors are real type-safety issues that JSDoc could fix; they are not test failures.

### Top patterns
- 79× `Parameter 'event' implicitly has an 'any' type` — add `/** @param {Event} event */` JSDoc.
- 22× `Property 'criteria' does not exist on type 'never'` — generic-narrowing failures in arrays initialized as `[]`. Fix with `/** @type {SomeType[]} */ let arr = []` JSDoc.
- The remaining ~675 fall into similar JSDoc-typing buckets.

### Files most affected (top 10 by error count)
- `RubricTable.svelte` (48), `RubricEditor.svelte` (37), `KnowledgeStoreDetail.svelte` (33), `LibraryDetail.svelte` (31), `PromptTemplatesContent.svelte` (28), `Service.svelte` (26), `AacTerminal.svelte` (26), `RubricsList.svelte` (22), `RubricForm.svelte` (~20), `assistantService.js` (~20).

### Suggested attack plan
A full JSDoc pass is the right long-term fix but is multi-day work. As an interim:
- Either lower the strictness of `jsconfig.json` (set `"checkJs": false` or `"strict": false`) so `npm run check` becomes useful as a smoke test instead of a strict gate, with a TODO to re-enable per directory as files are migrated;
- Or drop `--tsconfig ./jsconfig.json` from the `check` script so svelte-check only validates Svelte template syntax, not JS types.

The user should make this call. If they want full strictness, plan ~2 person-days.

---

## 5. Frontend `vitest` — 1 pre-existing failure

### Repro
```bash
cd /home/novelia/Documents/lamb/frontend/svelte-app
npm run test:unit -- --run
# 1 failed: src/routes/page.svelte.test.js > "/+page.svelte" > "should render h1"
```

### Why
`src/routes/+page.svelte` renders an `<h1>` only inside an auth-gated branch (line 219). The test renders the component without setting up auth state, so the h1 isn't in the tree. `getByRole('heading', { level: 1 })` therefore throws.

### Fix shape
Either (a) mock the auth store before render, or (b) replace the assertion with one that targets the always-rendered shell (`screen.getByRole('main')` or similar). Option (b) is one line.

### File
`/home/novelia/Documents/lamb/frontend/svelte-app/src/routes/page.svelte.test.js`

```diff
-		expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
+		// h1 only renders for authenticated users; assert the page mounts.
+		expect(screen.getByRole('main')).toBeInTheDocument();
```

(verify the page actually has a `<main>` element first; if not, adjust the selector).

---

## 6. Library-manager streaming-write SIM115 — already fixed in this run

Already addressed inline by adding `# noqa: SIM115` with a one-line explanation at `library-manager/backend/routers/content.py:448`. No follow-up needed.

If a future cleanup wants to remove the suppression: Python 3.12 added `delete_on_close=False` to `tempfile.NamedTemporaryFile`, which lets you use the context manager and still keep the file after close. Migrate to that and drop the `noqa` once Python ≥ 3.12 is the minimum.

---

## 7. Lamb-cli pre-existing test bugs — already fixed in this run

`tests/test_commands/test_assistant.py::TestAssistantUpdate::test_update_metadata_merge` and `::test_update_vision_flag` were registering 2 mock responses for what is actually 3 HTTP calls (GET-for-metadata-merge → GET-for-name-backfill → PUT). pytest-httpx 0.36 enforces strict per-response consumption; the previous, looser version masked the bug. Already fixed inline by adding the third mock response. No follow-up needed.

---

## 8. Frontend Docker dev container fights for `.svelte-kit/` ownership

### Repro
After `docker compose up`, the `lamb-frontend-1` container (running as root) creates `frontend/svelte-app/.svelte-kit/` and `node_modules/.vite-temp/` as `root:root`. Host-side `npm run check` and `npm run test:unit` then fail with `EACCES`.

### Workaround used in this run
Stop the container before host-side tests, then chown the tree:
```bash
docker stop lamb-frontend-1
docker run --rm -v /home/novelia/Documents/lamb/frontend/svelte-app:/app -w /app node:20-alpine sh -c 'rm -rf .svelte-kit node_modules/.vite-temp && chown -R 1000:1000 .'
```

### Real fix
Edit the `frontend` service in `docker-compose-example.yaml` to add `user: "${UID:-1000}:${GID:-1000}"` so the dev server runs as the host user. May need to chown on first up. The `frontend-build` one-shot service should probably do the same.

### File
`/home/novelia/Documents/lamb/docker-compose-example.yaml` — `frontend` and `frontend-build` services.

---

## How to verify you're done

After tackling any subset of the above, re-run the corresponding suite from the repo root:

```bash
# Backend deps
cd backend && pytest                                  # should still be 39/39

# Legacy stable
cd lamb-kb-server-stable/backend/tests && pytest -m "not slow" -v

# Frontend
cd frontend/svelte-app
docker stop lamb-frontend-1 || true
npm run lint                                          # target: 0 errors
npm run check                                         # target: 0 errors
npm run test:unit -- --run                            # target: all pass
```

For each fix, also update this file: strike out the section (or move to a "Done" section at the bottom) once verified, with the commit hash.

---

## 9. AssistantForm "Advanced Mode" hides Connector / LLM in create flow (UX call)

### Repro
1. Open `/assistants` → click + Create.
2. Notice that **Connector**, **LLM**, and **Prompt Processor** dropdowns are not visible in basic mode.
3. Save the assistant. The new row uses the org default (here: `openai` / `gpt-4o-mini` from `setups.default.providers.openai.default_model`).
4. If the org's `openai.api_key` is the placeholder `your-openai-api-key-here` (default for fresh installs), the user only finds out at first chat: HTTP 401 from OpenAI.

### Source
`frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte` — search for `isAdvancedMode`. Lines 2263 and 2286 are `{#if isAdvancedMode || formState === 'edit'}` blocks that hide the selects in create mode.

### Why this is a real defect
The basic-mode default is silent — no banner, no warning, no "this connector has no valid credentials" feedback. New deployments that haven't configured a real OpenAI key will trip every basic-mode user.

### Fix shape — pick one
A. **Always show Connector + LLM** in create mode (drop the `isAdvancedMode` guard for those two; keep `prompt_processor` advanced-only). 1-line change. Slight UX-overload risk for novices, mitigated by sensible defaults already populating the fields.
B. **Validate the default connector at form-mount time.** If the org's default connector has a placeholder key (regex match on the key value), surface a warning banner. Higher-effort but more graceful.
C. **Backend-side:** the `/creator/assistant/defaults` endpoint should return a connector whose credentials are actually present. If the placeholder is detected, return a different default. Cleanest if combined with (B).

The Phase 7 continuation walkthrough worked around this by toggling Advanced Mode manually. Acceptable workaround for power users; not for end users.

---

## 10. FR-10 conflict modal UX polish — DONE in this run

`LibraryDetail.svelte::handleDeleteItemConfirm` used to leave the confirmation modal open on a 409 conflict and only show a generic "Request failed with status code 409". Fixed in the run dated 2026-05-04: the modal now closes on error and the error banner shows `detail.message` plus the names of the conflicting Knowledge Stores parsed out of `detail.knowledge_stores[]`. Verified by re-running `testing/playwright/tests/fr10_ui.spec.js` (still GREEN).

---

## Done in the original run (2026-05-03 / 2026-05-04)

- ✅ Section 6 — library-manager SIM115 noqa applied.
- ✅ Section 7 — lamb-cli pytest-httpx-0.36 mock count.
- ✅ Section 10 — FR-10 conflict modal closes on error + names KS.
- ✅ Phase 7 i18n locale gap — `knowledge.wizard.step9.heading` added to en/es/ca/eu.
- ✅ Prettier pinned to 3.5.3 + 116 files reformatted (including 4 locales after the new key landed).
- ✅ Phase 0–9 of the Knowledge-Store lifecycle verification + Phase 7 continuation (see `test-results/lifecycle-20260503T181108Z/SUMMARY.md`).
