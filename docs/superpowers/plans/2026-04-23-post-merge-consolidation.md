# Post-Merge Consolidation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the svelte-app into creator-app, fix all post-merge issues in the backend, apply de-anonymization, clean up dead code, and document every change.

**Architecture:** The frontend monorepo has three SPA packages (`creator-app`, `module-chat`, `module-file-eval`) plus a shared `@lamb/ui` package. The `svelte-app` folder arrived from dev with new AAC agent and library features that need to live inside `creator-app` using `@lamb/ui` components. The backend `lti_router.py` and `lti_activity_manager.py` were merged keeping HEAD's module architecture but need cleanup of dead code, stale docs, and the de-anonymization change from issue #332.

**Tech Stack:** SvelteKit 2 + Svelte 5, `@sveltejs/adapter-static`, `svelte-i18n`, Tailwind CSS 4, FastAPI (backend), `@lamb/ui` shared package.

---

## Part A: Backend Post-Merge Fixes

### Task A1: Remove dead token functions from lti_router.py

These functions reference an undefined `LTI_TOKEN_SCOPE` constant and would crash at runtime. They are dead code -- HEAD uses `_create_dashboard_jwt` / `_create_setup_jwt` / `_validate_lti_jwt` instead.

**Files:**
- Modify: `backend/lamb/lti_router.py`

- [ ] **Step 1: Delete dead token functions**

Remove the entire block from `_tokens: dict = {}` through `_validate_setup_token` (roughly lines 53-88 in the current file). This includes:
- `_tokens` dict
- `SETUP_TOKEN_TTL`, `DASHBOARD_TOKEN_TTL`, `CONSENT_TOKEN_TTL` constants
- `LTI_TOKEN_SCOPE` (if present) 
- `_create_token()`, `_validate_token()`, `_consume_token()`
- `_create_setup_token()`, `_validate_setup_token()`

Keep `SESSION_EXPIRED_HTML` and the JWT expiry constants (`LTI_DASHBOARD_JWT_EXPIRY`, `LTI_SETUP_JWT_EXPIRY`).

- [ ] **Step 2: Verify no remaining references**

Search the file for any calls to `_create_token`, `_validate_token`, `_consume_token`, `_create_setup_token`, `_validate_setup_token`. There should be zero.

- [ ] **Step 3: Commit**

```bash
git add backend/lamb/lti_router.py
git commit -m "fix: remove dead in-memory token functions from lti_router (undefined LTI_TOKEN_SCOPE)"
```

---

### Task A2: Clean up imports and dead code in lti_router.py

**Files:**
- Modify: `backend/lamb/lti_router.py`

- [ ] **Step 1: Remove duplicate import**

Line 20 and 23 both have `from lamb import auth as lamb_auth`. Remove one of them.

- [ ] **Step 2: Remove unused `import json`**

The `json` module is not used anywhere in the file. Remove it.

- [ ] **Step 3: Remove redundant inner `from lamb.modules.base import LTIContext`**

`LTIContext` is already imported at the top level (around line 29). Remove the duplicate imports inside `lti_launch()` (around lines 228-229 and 249).

- [ ] **Step 4: Remove unused `_format_timestamp` function**

Defined but never called in this file. Remove it entirely.

- [ ] **Step 5: Verify file still parses**

```bash
python -c "import ast; ast.parse(open('backend/lamb/lti_router.py').read()); print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/lamb/lti_router.py
git commit -m "chore: clean up duplicate imports and dead code in lti_router"
```

---

### Task A3: Fix link-account redirect URL

After successful account linking, the redirect goes to `/lamb/v1/lti/setup?token=...` but the backend only defines `GET /setup/info` (JSON API). The SPA lives at `/m/chat/setup`.

**Files:**
- Modify: `backend/lamb/lti_router.py`

- [ ] **Step 1: Fix the redirect URL**

In `lti_link_account_submit()`, find the line:
```python
url=f"{public_base}/lamb/v1/lti/setup?token={new_token}",
```
Change it to:
```python
url=f"{public_base}/m/chat/setup?token={new_token}",
```

This matches how the initial launch redirect works (the instructor setup goes to the SPA).

- [ ] **Step 2: Commit**

```bash
git add backend/lamb/lti_router.py
git commit -m "fix: link-account redirect to SPA path /m/chat/setup instead of API path"
```

---

### Task A4: Update stale docstrings and comments in lti_router.py

**Files:**
- Modify: `backend/lamb/lti_router.py`

- [ ] **Step 1: Update module docstring**

At the top of the file, the docstring still mentions "Student consent uses short-lived in-memory tokens". Replace the session management section with:
```python
"""
Session management:
- Instructor flows use LAMB JWTs (via lamb.auth) with lti_type claims
- Students launch directly into the activity module (no consent gate)
"""
```

- [ ] **Step 2: Update lti_launch docstring**

The decision tree comment in `lti_launch()` still mentions "consent check -> consent page". Update to:
```python
"""
Decision tree:
1. Validate OAuth signature
2. Is there a configured activity for this resource_link_id?
   YES + instructor -> module.on_instructor_launch() (dashboard)
   YES + student    -> module.on_student_launch() (direct launch)
   NO  + instructor -> identify as Creator user -> setup (LAMB JWT)
   NO  + student    -> "not configured yet" page
"""
```

- [ ] **Step 3: Remove stale consent comment in student branch**

In the student launch path, remove or update the comment "Check if consent is needed" to something like "Student -> module dispatch".

- [ ] **Step 4: Commit**

```bash
git add backend/lamb/lti_router.py
git commit -m "docs: update stale docstrings about removed consent flow in lti_router"
```

---

### Task A5: De-anonymize chat dashboard in modules/chat/service.py

The dashboard still shows "Student 1, Student 2" instead of real LMS names. This was a deliberate product decision in issue #332.

**Files:**
- Modify: `backend/lamb/modules/chat/service.py`
- Modify: `backend/lamb/modules/chat/__init__.py`

- [ ] **Step 1: Rename `_build_anonymization_map` to `_build_name_map`**

In `service.py`, find:
```python
def _build_anonymization_map(self, activity_id: int) -> Dict[str, str]:
    """Build a map from owi_user_id to 'Student N' (ordered by created_at)."""
    all_data = self.db_manager.get_activity_students(activity_id, page=1, per_page=100000)
    anon = {}
    for i, student in enumerate(all_data['students']):
        owi_uid = student.get('owi_user_id')
        if owi_uid:
            anon[owi_uid] = f"Student {i + 1}"
    return anon
```

Replace with:
```python
def _build_name_map(self, activity_id: int) -> Dict[str, str]:
    """Build a map from owi_user_id to student's real name (from LMS)."""
    all_data = self.db_manager.get_activity_students(activity_id, page=1, per_page=100000)
    name_map = {}
    for student in all_data['students']:
        owi_uid = student.get('owi_user_id')
        if owi_uid:
            name_map[owi_uid] = student.get('user_display_name') or student.get('user_name') or '(unknown)'
    return name_map
```

- [ ] **Step 2: Update all references in service.py**

Replace across the entire file:
- `_build_anonymization_map` -> `_build_name_map` (call sites in `get_dashboard_chats` and `get_dashboard_chat_detail`)
- `anon_map` -> `name_map` (parameter names and local vars)
- `anon_name` -> `student_name` (in `_query_activity_chats` and `_query_chat_detail`)
- `"anonymous_student"` -> `"student_name"` (JSON response keys)
- Update docstrings that say "anonymized" to say "with real names from LMS"

- [ ] **Step 3: Update setup field label in `__init__.py`**

In `modules/chat/__init__.py`, find the SetupField that says "Allow instructors to review anonymized chat transcripts" and change to "Allow instructors to review chat transcripts".

- [ ] **Step 4: Verify file parses**

```bash
python -c "import ast; ast.parse(open('backend/lamb/modules/chat/service.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/lamb/modules/chat/service.py backend/lamb/modules/chat/__init__.py
git commit -m "feat: de-anonymize dashboard — show real LMS names instead of Student N (#332)"
```

---

### Task A6: Remove dead `get_owi_redirect_url` from activity manager

**Files:**
- Modify: `backend/lamb/lti_activity_manager.py`

- [ ] **Step 1: Verify it's unused**

Search all Python files in `backend/` for calls to `get_owi_redirect_url`. It should only appear as the method definition in `lti_activity_manager.py` and nowhere else (HEAD uses `module.launch_user()` instead).

- [ ] **Step 2: Remove the method if confirmed dead**

Delete the `get_owi_redirect_url` static method (around lines 322-329).

- [ ] **Step 3: Commit**

```bash
git add backend/lamb/lti_activity_manager.py
git commit -m "chore: remove dead get_owi_redirect_url from activity manager"
```

---

## Part B: svelte-app Migration into creator-app

### Task B1: Move AAC components from svelte-app to creator-app

The AAC components (`AgentLaunchCard`, `AacTerminal`, `GlobalAacTabBar`, `AacTabBar`, `AacSkillButton`, `AssistantTests`) exist in `svelte-app/src/lib/components/aac/` but creator-app already references them via `$lib/components/aac/` (in `UserDashboard.svelte` and `routes/assistants/+page.svelte`). The files are simply missing from creator-app.

**Files:**
- Create: `frontend/packages/creator-app/src/lib/components/aac/AgentLaunchCard.svelte`
- Create: `frontend/packages/creator-app/src/lib/components/aac/AacTerminal.svelte`
- Create: `frontend/packages/creator-app/src/lib/components/aac/GlobalAacTabBar.svelte`
- Create: `frontend/packages/creator-app/src/lib/components/aac/AacTabBar.svelte`
- Create: `frontend/packages/creator-app/src/lib/components/aac/AacSkillButton.svelte`
- Create: `frontend/packages/creator-app/src/lib/components/aac/AssistantTests.svelte`

- [ ] **Step 1: Copy all 6 AAC component files**

Copy from `frontend/svelte-app/src/lib/components/aac/` to `frontend/packages/creator-app/src/lib/components/aac/`.

- [ ] **Step 2: Update imports to use `@lamb/ui`**

In each copied file, replace local imports:
- `import { _ } from '$lib/i18n'` -> `import { _ } from '@lamb/ui'`
- `import { _ } from 'svelte-i18n'` -> `import { _ } from '@lamb/ui'`
- `import { user } from '$lib/stores/userStore'` -> `import { user } from '@lamb/ui'`

Leave `$lib/services/aacService` and `$lib/stores/aacStore.svelte` as-is (these are creator-app local, not shared UI).

- [ ] **Step 3: Verify creator-app already has aacService.js and aacStore.svelte.js**

Confirm these exist at:
- `frontend/packages/creator-app/src/lib/services/aacService.js`
- `frontend/packages/creator-app/src/lib/stores/aacStore.svelte.js`

If not, copy from svelte-app and update their imports similarly.

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/creator-app/src/lib/components/aac/
git commit -m "feat: migrate AAC components from svelte-app to creator-app"
```

---

### Task B2: Move library components from svelte-app to creator-app

**Files:**
- Create: `frontend/packages/creator-app/src/lib/components/libraries/LibrariesList.svelte`
- Create: `frontend/packages/creator-app/src/lib/components/libraries/LibraryDetail.svelte`

- [ ] **Step 1: Copy library components**

Copy from `frontend/svelte-app/src/lib/components/libraries/` to `frontend/packages/creator-app/src/lib/components/libraries/`.

- [ ] **Step 2: Update imports to use `@lamb/ui`**

Replace local imports with `@lamb/ui` equivalents (same pattern as Task B1).

- [ ] **Step 3: Verify libraryService.js exists in creator-app**

Check `frontend/packages/creator-app/src/lib/services/libraryService.js` exists (it does per the exploration).

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/creator-app/src/lib/components/libraries/
git commit -m "feat: migrate library components from svelte-app to creator-app"
```

---

### Task B3: Add agent and library routes to creator-app

**Files:**
- Create: `frontend/packages/creator-app/src/routes/agent/+page.svelte`
- Create: `frontend/packages/creator-app/src/routes/agent/history/+page.svelte`
- Create: `frontend/packages/creator-app/src/routes/agent/history/[id]/+page.svelte`
- Create: `frontend/packages/creator-app/src/routes/libraries/+page.svelte`

- [ ] **Step 1: Copy route files**

Copy from `frontend/svelte-app/src/routes/agent/` and `frontend/svelte-app/src/routes/libraries/` into the corresponding paths under `frontend/packages/creator-app/src/routes/`.

- [ ] **Step 2: Update imports to use `@lamb/ui`**

In each route file, replace:
- `import { _ } from '$lib/i18n'` -> `import { _ } from '@lamb/ui'`
- `import { _, locale } from '$lib/i18n'` -> `import { _, locale } from '@lamb/ui'`
- `import { user } from '$lib/stores/userStore'` -> `import { user } from '@lamb/ui'`

Leave `$lib/services/*` and `$lib/stores/*` as-is (they are creator-app local services/stores).

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/creator-app/src/routes/agent/ frontend/packages/creator-app/src/routes/libraries/
git commit -m "feat: add agent and library routes to creator-app from svelte-app"
```

---

### Task B4: Integrate GlobalAacTabBar into creator-app layout

The svelte-app layout renders `<GlobalAacTabBar />` between Nav and main content. Creator-app's layout does not have this.

**Files:**
- Modify: `frontend/packages/creator-app/src/routes/+layout.svelte`

- [ ] **Step 1: Add GlobalAacTabBar import and render**

In `+layout.svelte`, add the import:
```svelte
import GlobalAacTabBar from '$lib/components/aac/GlobalAacTabBar.svelte';
```

Add `<GlobalAacTabBar />` after the `<Nav />` component and before the main content area.

- [ ] **Step 2: Commit**

```bash
git add frontend/packages/creator-app/src/routes/+layout.svelte
git commit -m "feat: add GlobalAacTabBar to creator-app layout"
```

---

### Task B5: Integrate token-based session bootstrap into creator-app layout

The svelte-app layout handles `?token=` URL params for LTI login flows via `sessionManager.replaceSessionWithToken()`. Creator-app does not have this, which breaks LTI instructor flows that redirect to the creator SPA with a token.

**Files:**
- Modify: `frontend/packages/creator-app/src/routes/+layout.svelte`

- [ ] **Step 1: Check if sessionManager.js already exists in creator-app**

The file `frontend/svelte-app/src/lib/session/sessionManager.js` imports from creator-app stores (`$lib/stores/userStore`, etc.). Check if creator-app already has an equivalent at `src/lib/session/sessionManager.js` or similar.

If not, copy `sessionManager.js` from svelte-app to `frontend/packages/creator-app/src/lib/session/sessionManager.js` and update the `user` import:
- `import { user } from '$lib/stores/userStore'` -> `import { user } from '@lamb/ui'`
- Leave the rest of the `$lib/stores/*` imports as-is (they point to creator-app local stores).

- [ ] **Step 2: Add token handling to +layout.svelte**

Add the `?token=` detection and `replaceSessionWithToken()` logic from svelte-app's layout. Gate child rendering on `sessionReady`. Show error banner if token bootstrap fails.

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/creator-app/src/lib/session/ frontend/packages/creator-app/src/routes/+layout.svelte
git commit -m "feat: add token-based session bootstrap to creator-app layout for LTI flows"
```

---

### Task B6: Verify and fix i18n locale completeness

**Files:**
- Verify: `frontend/packages/ui/src/lib/locales/{en,es,ca,eu}.json`

- [ ] **Step 1: Check that `libraries` keys exist in all 4 locale files**

The `base/en.json` has a `libraries` section that is NOT in the active `locales/en.json`. The new library feature needs i18n keys. Check if `libraries` top-level key exists in all four locale files.

- [ ] **Step 2: Check that AAC/agent keys exist**

The AAC components use keys like `home.dashboard.agent.title`, `agent.tabs.close`, `agent.history.title`. Verify these exist in all four locale files under `@lamb/ui`.

- [ ] **Step 3: Add missing keys**

If any keys are missing, add them to all four locale files. Use the English text as reference and translate to es/ca/eu (or leave English as placeholder with a TODO comment).

- [ ] **Step 4: Delete legacy `ui/src/lib/i18n/base/en.json`**

This file is not loaded at runtime (not registered in `i18n/index.js`). If all its unique keys have been merged into the active locale files, delete it.

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/ui/src/lib/locales/ frontend/packages/ui/src/lib/i18n/
git commit -m "fix: ensure all i18n keys for agent/libraries exist in all 4 locales"
```

---

### Task B7: Update backend Dockerfile for creator-app build

The Dockerfile currently builds from `frontend/svelte-app`. It needs to build from the monorepo packages instead.

**Files:**
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Update the frontend build stage**

Change the Dockerfile frontend build stage from:
```dockerfile
WORKDIR /frontend/svelte-app
```
to the monorepo workspace build pattern used in `docker-compose-example.yaml` (pnpm workspace filters for `creator-app`, `module-chat`, `module-file-eval`).

- [ ] **Step 2: Verify build output path matches `main.py` expectations**

`main.py` expects the build at `../frontend/build`. Verify the adapter-static output from `creator-app` still writes to `frontend/build/` (the `svelte.config.js` sets `pages: '../../build'`).

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile
git commit -m "fix: update Dockerfile to build from monorepo packages instead of svelte-app"
```

---

### Task B8: Delete orphaned consent SPA page

**Files:**
- Delete: `frontend/packages/module-chat/src/routes/consent/+page.svelte`

- [ ] **Step 1: Delete the consent route**

The consent SPA page calls backend endpoints that no longer exist (`/lamb/v1/lti/consent/info`, `POST /lamb/v1/lti/consent`). Nothing redirects to it.

- [ ] **Step 2: Commit**

```bash
git add -A frontend/packages/module-chat/src/routes/consent/
git commit -m "chore: remove orphaned consent SPA page (backend endpoints removed)"
```

---

## Part C: Documentation

### Task C1: Write post-merge changelog document

**Files:**
- Create: `docs/POST_MERGE_CHANGES.md`

- [ ] **Step 1: Create the changelog document**

Write a markdown file documenting ALL changes made during and after the merge. Structure it as:

```markdown
# Post-Merge Consolidation Changes

## Date: 2026-04-23

## Summary
Merge of `dev` into HEAD (feature/modules branch), followed by consolidation
of the `svelte-app` into `creator-app` and backend cleanup.

## Backend Changes

### lti_router.py
- Removed dead in-memory token functions (`_create_token`, `_validate_token`, etc.)
  that referenced undefined `LTI_TOKEN_SCOPE`
- Removed duplicate `from lamb import auth as lamb_auth` import
- Removed unused `import json`
- Removed redundant inner `from lamb.modules.base import LTIContext` imports
- Removed unused `_format_timestamp` function
- Fixed link-account redirect: `/lamb/v1/lti/setup` -> `/m/chat/setup`
- Updated stale docstrings about removed consent flow
- Kept HEAD's module architecture (LTIContext, module dispatch, LAMB JWTs)
- Kept HEAD's file_evaluation support, grade passback, dynamic owner check

### lti_activity_manager.py
- Kept HEAD's `determine_is_owner()` (dynamic LMS->Creator resolution)
- Kept HEAD's `reconfigure_activity()` returning tuple (added_ids, removed_ids)
- Removed consent methods (`check_student_consent`, `record_consent`)
- Adopted real names in `get_dashboard_students()` (was "Student N")
- Removed dead `get_owi_redirect_url` method

### modules/chat/service.py
- De-anonymized dashboard: `_build_anonymization_map` -> `_build_name_map`
- Dashboard shows real LMS names instead of "Student 1, Student 2"
- Updated all JSON response keys: `anonymous_student` -> `student_name`

### modules/chat/__init__.py
- Updated setup field label: removed "anonymized" from chat transcripts description

## Frontend Changes

### svelte-app -> creator-app Migration
- Moved AAC components (AgentLaunchCard, AacTerminal, GlobalAacTabBar,
  AacTabBar, AacSkillButton, AssistantTests) to creator-app
- Moved library components (LibrariesList, LibraryDetail) to creator-app
- Added /agent and /libraries routes to creator-app
- Integrated GlobalAacTabBar into creator-app layout
- Added token-based session bootstrap for LTI flows
- Updated all imports to use @lamb/ui instead of local $lib paths

### i18n
- Verified all 4 locale files (en, es, ca, eu) have agent/library keys
- Removed legacy base/en.json (not loaded at runtime)

### module-chat
- Removed orphaned /consent SPA page (backend endpoints no longer exist)

### Dockerfile
- Updated frontend build stage to use monorepo workspace packages

## Merge Decisions (for reference)
- Consent flow: REMOVED (per issue #332 — LMS privacy settings control identity)
- Token system: HEAD's LAMB JWTs for instructors (already stateless/multi-worker safe)
- Architecture: HEAD's module system (LTIContext, on_student_launch, on_instructor_launch)
- Dashboard names: Real LMS names (per issue #332)
```

- [ ] **Step 2: Commit**

```bash
git add docs/POST_MERGE_CHANGES.md
git commit -m "docs: add post-merge consolidation changelog"
```

---

## Execution Order

Tasks can be parallelized in some cases, but the recommended sequential order is:

1. **A1-A4** (backend fixes in lti_router.py) — no dependencies between them, can be done in any order
2. **A5** (de-anonymize chat service) — independent of A1-A4
3. **A6** (remove dead method from activity manager) — independent
4. **B1-B3** (copy components and routes) — do these first in frontend
5. **B4-B5** (layout integration) — depends on B1 (GlobalAacTabBar must exist)
6. **B6** (i18n) — can be done anytime after B1-B3 to know which keys are needed
7. **B7** (Dockerfile) — do after B1-B5 to verify build works
8. **B8** (delete consent page) — independent
9. **C1** (documentation) — do LAST, after everything else is done
