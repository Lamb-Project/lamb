# Frontend Resilience Phase 1 — Repro + Verification

Companion document to issue **#352** ("Frontend resilience audit") and the architecture-doc section §9.6 ("Frontend Resilience Patterns").

This doc documents the **5 bugs fixed in Phase 1** on branch `fix/352-frontend-resilience-phase1`. For each bug it gives:
1. **Files changed** — exact lines
2. **Repro before fix** — concrete steps that demonstrate the broken behavior on the original code
3. **Verify after fix** — same steps, with the expected fixed behavior

All repros assume:
- Docker compose stack running (`docker compose up`)
- Frontend dev server on `http://localhost:5173`
- A browser with DevTools open (Network + Console tabs)
- A working test account with creator role

## Switching between fixed and broken code for repro

```bash
# To see the BROKEN behavior, check out the parent commit:
git stash                                   # if you have local changes
git checkout 4b38f05d -- <file>             # restore one file at a time
# …reproduce…
git checkout fix/352-frontend-resilience-phase1 -- <file>   # restore fix
```

Or, simpler, run repros on `dev` (origin tip) and verifications on `fix/352-frontend-resilience-phase1`.

---

## Bug H1 — `+layout.js` blanks the entire app on locale load failure

**File:** `frontend/svelte-app/src/routes/+layout.js:28-33`
**Pattern:** F (top-level `await` with no fallback)

### Repro before fix (broken)

Simulate locale JSON load failure, e.g. by intercepting `/locales/en.json` with the browser DevTools "Network conditions" → block-request feature, or by temporarily renaming the file:

```bash
# Method 1 — rename one of the locale JSON files to force a 404
mv /opt/lamb/frontend/svelte-app/src/lib/locales/en.json \
   /opt/lamb/frontend/svelte-app/src/lib/locales/en.json.bak
```

1. Reload `http://localhost:5173/`.
2. **Expected broken behavior:** the page renders blank/white. The browser console shows an unhandled rejection from `waitLocale()`. SvelteKit's `load()` has rejected, so the entire layout failed to render.
3. Restore: `mv …en.json.bak …en.json`.

### Verify after fix

With the fix in place, repeat the same steps:

```bash
mv /opt/lamb/frontend/svelte-app/src/lib/locales/en.json \
   /opt/lamb/frontend/svelte-app/src/lib/locales/en.json.bak
```

1. Reload `http://localhost:5173/`.
2. **Expected fixed behavior:** the page renders. The console logs `waitLocale failed, continuing with fallback`. Some labels may show their i18n key (`auth.email`) instead of translated text, but the app is usable. The user can navigate, log in, etc.
3. Restore the locale file.

---

## Bug H2 — `Login.svelte` login button stuck spinning on unexpected throw

**File:** `frontend/svelte-app/src/lib/components/Login.svelte:27-83`
**Pattern:** A (loading flag without `try/finally`)

The `login()` service has its own `try/catch` returning `{success:false}`, so this only triggers if a downstream call (e.g. `replaceSessionWithLoginData()`) throws unexpectedly. The fix is defense-in-depth: wrap the entire submit handler in `try/finally`.

### Repro before fix (broken)

Easiest synthetic repro: temporarily make `replaceSessionWithLoginData` throw.

```javascript
// Edit frontend/svelte-app/src/lib/session/sessionManager.js
// Inside replaceSessionWithLoginData, before clearCurrentSession():
if (browser) throw new Error('Synthetic failure for repro');
```

1. Open `http://localhost:5173/`, click login, enter valid creator credentials, click Submit.
2. **Expected broken behavior:** spinner spins forever. Submit button stays disabled. Console shows the synthetic error. User must reload the page.
3. Revert the synthetic throw.

### Verify after fix

Apply the same synthetic throw with the fix in place.

1. Submit the login form with valid credentials.
2. **Expected fixed behavior:** spinner stops, button is re-enabled, an error message is shown ("Synthetic failure for repro"). User can correct and try again — no reload required.
3. Revert the synthetic throw.

---

## Bug H3 — AAC stream keeps running after navigation away

**File:** `frontend/svelte-app/src/lib/services/aacService.js:111-180`
**Companion:** `frontend/svelte-app/src/lib/components/aac/AacTerminal.svelte` (AbortController wiring + `onDestroy`)
**Pattern:** E (timer/stream not cleaned up)

### Repro before fix (broken)

1. Log in. Navigate to `/agent`. Start a new AAC session with a slow-responding skill (or just any conversation that streams for several seconds).
2. Send a message that will produce a long answer (e.g. "Explain assistant authoring step by step in detail").
3. While the response is streaming, immediately click another nav link (e.g. `/assistants`).
4. Open DevTools → Network → filter by `/aac/sessions/.../message/stream`.
5. **Expected broken behavior:** the request is still pending (status: pending). Open DevTools → Performance Memory; the fetch reader keeps decoding chunks in the background. If you watch long enough, the stream eventually completes server-side and chunks keep arriving, attempting to update component state on a destroyed component (Svelte 5 may swallow these silently, but the network traffic and CPU are real).

### Verify after fix

Repeat the same steps.

1. Send a long-streaming message.
2. Navigate away mid-stream.
3. **Expected fixed behavior:** the `/aac/sessions/.../message/stream` request shows status `(canceled)` in DevTools Network within ~1 frame after navigation. No further chunks arrive. No errors in console. Memory does not grow.

Additional check — abort on rapid same-page resend:
4. Stay on `/agent`. Send message A (streaming). Before A completes, send message B.
5. **Expected fixed behavior:** request A is canceled, request B starts cleanly. (Without the fix, both run concurrently and chunks interleave into the wrong message slot.)

---

## Bug AacTerminal defensive try/finally on `loading`

**File:** `frontend/svelte-app/src/lib/components/aac/AacTerminal.svelte` — `handleSend()` and `triggerSkillStartup()`
**Pattern:** A (defense-in-depth)

Note: the original code already reset `loading = false` after the `try/catch` block, so this is not a real bug today. The fix adds `try/finally` so any future code path that throws between `loading = true` and the reset cannot leak the flag. The mounted-check (`if (isMounted)`) prevents stale-state writes after `onDestroy`.

### Verify after fix (sanity check)

1. Send a message in AAC.
2. While streaming, navigate away.
3. Navigate back to the same session.
4. **Expected fixed behavior:** session loads cleanly, send button is enabled, no stale "loading" state from the prior stream. (Without the mount-check, `loading = false` could fire on an unmounted instance, causing Svelte 5 dev warnings.)

---

## Bug H8 — `AssistantsList` retry recursion runs after unmount

**File:** `frontend/svelte-app/src/lib/components/AssistantsList.svelte:138-167`
**Pattern:** B (`await` in lifecycle without mounted-check)

### Repro before fix (broken)

The retry path triggers when the first `getAssistants()` call throws, then waits 1 second, then retries. To repro:

1. In DevTools, set Network throttling to "Offline".
2. Navigate to `/assistants`. The fetch fails. Component logs "Will retry loading assistants in 1 second...".
3. **Within that 1-second window**, click another nav link (e.g. `/knowledge-bases`).
4. Set Network throttling back to "No throttling".
5. **Expected broken behavior:** in the console, see Svelte warnings about state updates on destroyed components, OR the next time you visit `/assistants`, briefly see the previous fetch's stale data flash before the new fetch runs. The retry call recurses on a destroyed component.

### Verify after fix

Repeat the same steps.

1. Trigger the retry path (offline → navigate to `/assistants` → wait for fail).
2. Navigate away within the 1-second retry window.
3. Restore network.
4. **Expected fixed behavior:** the retry's `setTimeout` resolves but the function bails out at the `if (!isMounted) return;` guard. No state writes on the destroyed component. No console warnings. Re-navigating to `/assistants` triggers a fresh load cleanly.

---

## Smoke test — full Phase 1 verification in one pass

Run this end-to-end flow to confirm all five fixes are in place:

```
Step 1.  Stop docker compose.
Step 2.  Move /opt/lamb/frontend/svelte-app/src/lib/locales/en.json to en.json.bak
Step 3.  Start docker compose, open http://localhost:5173/
         ✓ EXPECT: page loads (not blank). Some text in i18n keys is OK.
Step 4.  Restore en.json.
Step 5.  Reload. Login with valid credentials.
         ✓ EXPECT: clean login, redirect to /assistants.
Step 6.  In DevTools, throttle to Offline.
Step 7.  Click /assistants in nav.
         ✓ EXPECT: error state shown OR retry message in console.
Step 8.  Within 1 second, click /knowledge-bases.
Step 9.  Restore network throttling.
         ✓ EXPECT: no Svelte warnings about destroyed-component updates.
Step 10. Navigate to /agent. Start a new conversation.
Step 11. Send a long-form message ("Explain in detail…").
Step 12. While streaming, click /assistants.
         ✓ EXPECT: in Network tab, the /aac/sessions/.../message/stream request
                   shows (canceled) within a frame.
Step 13. Navigate back to /agent. Resume the session.
         ✓ EXPECT: send button is enabled. Conversation history is shown.
                   No "loading" stuck state.
```

---

## Phase 2 fixes

Phase 2 added five more fixes on top of Phase 1.

### Bug M1/M2/M3 — Mid-session token expiry leaves UI broken

**File:** new `frontend/svelte-app/src/lib/services/apiClient.js`
**Pattern:** D (no global 401 handler)

Migrated services: `aacService.js` (incl. streaming), `authService.js` (`fetchUserProfile`, `getHelp`), `adminService.js` (all 8 functions), `AssistantForm.svelte` file upload.

#### Repro before fix (broken)

1. Log in normally.
2. Open DevTools → Application → Local Storage → set `userToken` to `"invalid-token-xxx"` (or wait long enough for the OWI session to expire naturally).
3. Click around — try /assistants, /agent, /knowledgebases.
4. **Expected broken behavior:** APIs all return 401. Each component shows its own generic error (e.g. "HTTP 401" in AAC, "Failed to fetch" in admin, blank lists elsewhere). The user remains on the same page, sees errors, and has to **manually reload** to recover. *This is the original symptom you reported.*

#### Verify after fix

Repeat the same steps.

1. Log in, then corrupt the token in localStorage.
2. Click any nav link.
3. **Expected fixed behavior:** the first 401 immediately clears the session and redirects to the login screen at `/`. The user logs in again and proceeds. No reload needed.

Mid-stream test (covers M1):
4. Log in, navigate to `/agent`, start a conversation.
5. Open DevTools console and run: `localStorage.setItem('userToken', 'invalid-xxx')`
6. Send a message.
7. **Expected fixed behavior:** the stream returns 401, `apiFetch` triggers session reset and redirect. The terminal does NOT paint "HTTP 401" (the error path detects "Session expired" and exits quietly).

### Bug H10 — `KnowledgeBasesList` silent empty on dual failure

**File:** `frontend/svelte-app/src/lib/components/KnowledgeBasesList.svelte:93-118`

#### Repro before fix (broken)

1. Stop the KB Server: `docker compose stop kb`
2. Log in. Navigate to `/knowledgebases`.
3. **Expected broken behavior:** page shows empty list with no error indicator. User has no way to know why their KBs aren't showing.

#### Verify after fix

1. Stop the KB Server.
2. Navigate to `/knowledgebases`.
3. **Expected fixed behavior:** error banner shown (e.g. "Failed to load knowledge bases" or "server offline"). User knows to retry / contact admin.
4. Restart KB Server: `docker compose start kb`. Reload — list populates.

Partial-failure variant: if `getUserKnowledgeBases()` succeeds but `getSharedKnowledgeBases()` fails, the user sees their owned KBs (no banner; the partial result is more useful than an error).

### Bug H11 — `AssistantForm` file upload — token-expiry mid-upload

**File:** `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte:760-820`

#### Repro before fix (broken)

1. Open assistant edit form. Open the file panel.
2. In DevTools, corrupt `localStorage.userToken`.
3. Click "Upload file" and select a file.
4. **Expected broken behavior:** spinner spins, eventually shows "API error: 401 - …" but the user is still logged in (token in localStorage is now bogus). Every other action will also fail.

#### Verify after fix

Repeat steps.

1. Corrupt token, click upload.
2. **Expected fixed behavior:** session is cleared immediately on 401 and the user is redirected to login. No misleading "API error" banner persists in the form.

### Bug H12 — `assistantStore` blank list on unexpected response shape

**File:** `frontend/svelte-app/src/lib/stores/assistantStore.js:80-110`

#### Repro before fix (broken)

This is an edge case triggered when the backend returns something other than `{ assistants: [...] }`. Synthetic repro:

```javascript
// Edit frontend/svelte-app/src/lib/services/assistantService.js
// Inside getAssistants(), before return:
return { /* missing assistants key */ total_count: 0 };
```

1. Reload `/assistants`.
2. **Expected broken behavior:** Svelte iterates `state.items` — which is now `undefined` — and the page throws or renders blank. Console shows "Cannot read property of undefined".

#### Verify after fix

Apply the same synthetic shape change.

1. Reload `/assistants`.
2. **Expected fixed behavior:** list shows "No assistants" cleanly. Store error stays `null`. Defensive `Array.isArray()` coerced the bad shape to `[]`.

### Bug H6 — `GlobalAacTabBar` 500ms polling

**Files:** `frontend/svelte-app/src/lib/stores/aacStore.svelte.js`, `GlobalAacTabBar.svelte`, `AacTabBar.svelte`, `agent/+page.svelte`, `assistants/+page.svelte`

The store was migrated from Svelte 5 `$state` runes to `writable()` so cross-module reactivity works without polling.

#### Repro before fix (high CPU, hard to user-perceive)

1. Open `/agent`, open DevTools → Performance.
2. Start a recording with no user interaction.
3. **Expected broken behavior:** Performance trace shows `setInterval` callback firing every 500ms, each running a Svelte component reconciliation pass even though nothing changed. CPU non-zero at idle.

#### Verify after fix

1. Same recording.
2. **Expected fixed behavior:** no periodic activity. Timer is gone from the trace. Tab bar still updates instantly when you open/close tabs from any other component (subscribe-based reactivity instead of polling).

Function-level smoke test:
3. Open assistant A, launch an AAC skill (creates a tab). Switch to a different page. Open assistant B, launch another skill (second tab).
4. **Expected fixed behavior:** both tabs visible in the global tab bar without delay. Closing a tab from anywhere updates the bar instantly.

---

## Phase 3 fixes

Phase 3 broadened the 401 coverage to all axios- and fetch-based services, and addressed Library Manager polling/abort + remaining mounted-checks.

### Axios-based services — global 401 via shared instance

**Files changed:**
- `apiClient.js` — exports new `apiAxios` instance with request/response interceptors
- `knowledgeBaseService.js`, `assistantService.js`, `analyticsService.js`, `libraryService.js`, `templateService.js` — all swapped `import axios from 'axios'` for the shared instance

**Why this matters:** before Phase 3, every KB/assistant/analytics/library/template call still went through plain axios with no 401 handling. Token expiry while browsing any of those screens left the user with raw error banners. Now every axios call goes through the shared instance — same global session-recovery semantics as `apiFetch`.

#### Repro before fix

1. Log in. Navigate to `/knowledgebases`.
2. In DevTools: `localStorage.setItem('userToken', 'invalid')`.
3. Click any KB.
4. **Expected broken behavior:** axios 401 surfaces as a "Failed to fetch" or "Request failed with status 401" error in the panel. User stays on the page; every subsequent action also 401s.

#### Verify after fix

Repeat steps. **Expected fixed behavior:** the first 401 redirects to login. No "Failed to fetch" banner persists. Same applies for `/assistants` (assistantService), `/libraries` (libraryService), the analytics dashboard, and prompt-template management.

### `testService.js`, `rubricService.js`, `organizationService.js` — fetch-based migration

Migrated to `apiFetch` / `apiJson` from `apiClient`. Same effect — 401 redirects to login.

### Bug M4 — Library Manager rapid-switching shows stale data

**File:** `frontend/svelte-app/src/lib/components/libraries/LibraryDetail.svelte:60-90`

#### Repro before fix

1. Open `/libraries`. Have 2+ libraries.
2. Click library A. While it's loading (slow connection helps), click library B.
3. **Expected broken behavior:** library A's data may briefly show after B's selection. Items list flickers. Polling may target the wrong library ID.

#### Verify after fix

Same steps. **Expected fixed behavior:** only B's data is shown. The earlier A fetch completes silently with no state writes (dropped via `currentLoadId` sequence check).

### Bug M5 — Library item poll silently swallows errors

**File:** `LibraryDetail.svelte` — `pollPendingItems()`

#### Repro before fix

1. Open a library with a "processing" item. Polling starts.
2. Stop the Library Manager: `docker compose stop library-manager`.
3. **Expected broken behavior:** poll keeps firing every 3s. Items remain "processing" forever. Console shows network errors. User has no indication anything is wrong.

#### Verify after fix

Same steps. **Expected fixed behavior:** after 5 consecutive failed polls (~15 seconds), polling stops and an error banner says "Lost connection while checking item status. Reload to retry."

### Bug M6 — Library success-message timeout leaks on unmount

**File:** `LibraryDetail.svelte` — `showSuccess()` + `onDestroy`

#### Repro before fix

Hard to user-perceive. Synthetic check:

1. In LibraryDetail, trigger a success (e.g. upload a file). Within 4 seconds, navigate away.
2. **Expected broken behavior (Svelte dev mode):** console warning about state update on destroyed component when the timeout fires.

#### Verify after fix

Same steps. **Expected fixed behavior:** no warning. Timeout is cleared in `onDestroy`. `if (isMounted)` guards the assignment.

### Bug M7 — Library polling continues across `libraryId` changes

**File:** `LibraryDetail.svelte` — covered together with M4 above. The `currentLoadId` sequence check + `if (!isMounted) return` in the poll loop handle both rapid switching and unmount.

### Bug M12 — Assistants page overlapping detail fetches

**File:** `routes/assistants/+page.svelte:277-310`

#### Repro before fix

1. From assistants list, click assistant A. While loading, click B. While that loads, click C.
2. **Expected broken behavior:** the detail panel may show A's fields after C is selected. URL shows C but content is stale.

#### Verify after fix

Same steps. **Expected fixed behavior:** only C's data shown. Stale fetches dropped via `detailFetchSeq` sequence check.

### Bug M13 — AssistantForm fetchKnowledgeBases mounted-check

**File:** `AssistantForm.svelte` — added `isMounted` flag, mounted-checks in `fetchKnowledgeBases()`.

### Bug L1 — `agent/history/[id]` mounted-check

**File:** `routes/agent/history/[id]/+page.svelte` — added `isMounted` flag and `onDestroy`.

---

## What is NOT covered by Phase 1–3

These remain open in #352:

- **`ChatInterface.svelte`** — 6 raw `fetch()` calls, not migrated. Lower priority because the chat UI lives in a separate flow most creators don't touch frequently.
- **L2-L8 low-severity items** — context-refresh timing asymmetry, `canvasData.content` null check, file-input DOM clear, fire-and-forget `loadSharedUsers()`, partial profile data handling.
- **ESLint guardrail rule** for the resilience patterns (mentioned in §9.6) — manual code review for now.
- **E2E Playwright tests** for these resilience scenarios — should be a follow-up.
