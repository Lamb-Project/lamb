# Post-Merge Consolidation Changes

## Date: 2026-04-23

## Summary

Merge of `dev` into HEAD (feature/modules branch), followed by consolidation
of the `svelte-app` into `creator-app` and backend cleanup.

---

## Backend Changes

### lti_router.py

- **Removed dead in-memory token functions** (`_create_token`, `_validate_token`,
  `_consume_token`, `_create_setup_token`, `_validate_setup_token`) that referenced
  an undefined `LTI_TOKEN_SCOPE` constant -- would crash at runtime
- **Removed dead TTL constants** (`SETUP_TOKEN_TTL`, `DASHBOARD_TOKEN_TTL`) that
  were only used by the deleted token functions
- **Removed duplicate import** `from lamb import auth as lamb_auth` (was on both line 20 and 23)
- **Removed unused** `import json` (no references in the file)
- **Removed redundant inner imports** of `from lamb.modules.base import LTIContext`
  inside `lti_launch()` (already imported at module level)
- **Removed unused** `_format_timestamp` function (defined but never called)
- **Removed unused** `import datetime` (only `timedelta` is needed)
- **Fixed link-account redirect**: changed from `/lamb/v1/lti/setup?token=...`
  (backend API path) to `/m/chat/setup?token=...` (correct SPA path)
- **Updated module docstring**: removed mentions of "anonymized chat transcripts"
  and "in-memory tokens (one-shot flow)"
- **Updated `lti_launch` docstring**: decision tree now says "direct launch" for
  students instead of "consent check -> consent page"
- **Updated dashboard endpoint docstrings**: removed "anonymized" qualifier
- **Kept** HEAD's module architecture: `LTIContext`, `module.on_student_launch()`,
  `module.on_instructor_launch()`, LAMB JWTs for instructor sessions
- **Kept** HEAD's file_evaluation support, grade passback, dynamic owner check

### lti_activity_manager.py

- **Removed dead** `get_owi_redirect_url` static method (HEAD uses
  `module.launch_user()` / `ChatModule._get_owi_redirect_url()` instead)
- **Kept** HEAD's `determine_is_owner()` (dynamic LMS->Creator resolution)
- **Kept** HEAD's `reconfigure_activity()` returning `Tuple[List[int], List[int]]`
  (added_ids, removed_ids)

### modules/chat/service.py

- **De-anonymized dashboard**: renamed `_build_anonymization_map` to `_build_name_map`
- Dashboard now shows **real LMS names** (from `user_display_name` / `user_name`)
  instead of "Student 1", "Student 2"
- **Renamed all references**: `anon_map` -> `name_map`, `anon_name` -> `student_name`
- **Updated JSON response keys**: `"anonymous_student"` -> `"student_name"` in both
  `_query_activity_chats` and `_query_chat_detail`
- **Updated docstrings**: "anonymized" -> "with real names from LMS"

### modules/chat/__init__.py

- **Updated SetupField label**: changed from "Allow instructors to review anonymized
  chat transcripts" to "Allow instructors to review chat transcripts"

---

## Frontend Changes

### svelte-app -> creator-app Migration

The `svelte-app` folder arrived from the `dev` branch with new AAC agent and
library features. These have been migrated into `creator-app` (the monorepo
SPA package) using `@lamb/ui` shared components.

**Components migrated** (from `svelte-app/src/lib/components/` to
`creator-app/src/lib/components/`):

- `aac/AgentLaunchCard.svelte` -- agent launch card for dashboard
- `aac/AacTerminal.svelte` -- chat terminal for AAC sessions
- `aac/GlobalAacTabBar.svelte` -- global tab bar for open AAC sessions
- `aac/AacTabBar.svelte` -- local tab bar within agent view
- `aac/AacSkillButton.svelte` -- skill launcher button
- `aac/AssistantTests.svelte` -- assistant testing interface
- `libraries/LibrariesList.svelte` -- document library list view
- `libraries/LibraryDetail.svelte` -- library detail with items

**Routes migrated** (from `svelte-app/src/routes/` to `creator-app/src/routes/`):

- `/agent` -- LAMB Agent main page
- `/agent/history` -- agent conversation history
- `/agent/history/[id]` -- individual history entry
- `/libraries` -- document libraries list/detail

**Import updates applied to all migrated files:**

- `import { _ } from '$lib/i18n'` -> `import { _ } from '@lamb/ui'`
- `import { _ } from 'svelte-i18n'` -> `import { _ } from '@lamb/ui'`
- `import { _, locale } from '$lib/i18n'` -> `import { _, locale } from '@lamb/ui'`
- `import { user } from '$lib/stores/userStore'` -> `import { user } from '@lamb/ui'`

Local imports (`$lib/services/*`, `$lib/stores/*`) were left unchanged as they
point to creator-app local modules.

### creator-app Layout Changes

- **Added GlobalAacTabBar** to the layout (renders between Nav and main content)
- **Added token-based session bootstrap**: handles `?token=` URL parameters from
  LTI flows, calling `replaceSessionWithToken()` to establish sessions
- **Created `sessionManager.js`**: copied from svelte-app, updated `user` import
  to use `@lamb/ui` instead of local store

### i18n

- **Added `home.dashboard.agent` keys** to all 4 locale files (en, es, ca, eu)
  with full translations -- used by `AgentLaunchCard.svelte`
- **Added `libraries` top-level section** to all 4 locale files with full
  translations -- used by `LibrariesList.svelte` and `LibraryDetail.svelte`
- **Deleted `ui/src/lib/i18n/base/en.json`** -- legacy file not loaded at
  runtime (not registered in `i18n/index.js`); all unique keys have been
  merged into the active locale files

### module-chat

- **Deleted orphaned `/consent` SPA page** (`src/routes/consent/+page.svelte`) --
  backend consent endpoints no longer exist

### Dockerfile

- **Updated frontend build stage** from `svelte-app` (npm) to monorepo workspace
  (pnpm) -- now builds `creator-app`, `module-chat`, and `module-file-eval` using
  `pnpm --filter` commands

---

## Merge Decisions (for reference)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Consent flow | **REMOVED** | Per issue #332; LMS privacy settings control identity |
| Token system | **HEAD's LAMB JWTs** | Already stateless and multi-worker safe |
| Architecture | **HEAD's module system** | LTIContext, on_student_launch, on_instructor_launch |
| Dashboard names | **Real LMS names** | Per issue #332; de-anonymized |
| Activity reconfigure | **Tuple return** | HEAD's `(added_ids, removed_ids)` more useful than bool |
| Frontend structure | **Monorepo packages** | SPA via creator-app, not standalone svelte-app |

---

## Files Modified

### Backend
- `backend/lamb/lti_router.py`
- `backend/lamb/lti_activity_manager.py`
- `backend/lamb/modules/chat/service.py`
- `backend/lamb/modules/chat/__init__.py`
- `backend/Dockerfile`

### Frontend -- Created
- `frontend/packages/creator-app/src/lib/components/aac/AgentLaunchCard.svelte`
- `frontend/packages/creator-app/src/lib/components/aac/AacTerminal.svelte`
- `frontend/packages/creator-app/src/lib/components/aac/GlobalAacTabBar.svelte`
- `frontend/packages/creator-app/src/lib/components/aac/AacTabBar.svelte`
- `frontend/packages/creator-app/src/lib/components/aac/AacSkillButton.svelte`
- `frontend/packages/creator-app/src/lib/components/aac/AssistantTests.svelte`
- `frontend/packages/creator-app/src/lib/components/libraries/LibrariesList.svelte`
- `frontend/packages/creator-app/src/lib/components/libraries/LibraryDetail.svelte`
- `frontend/packages/creator-app/src/lib/session/sessionManager.js`
- `frontend/packages/creator-app/src/routes/agent/+page.svelte`
- `frontend/packages/creator-app/src/routes/agent/history/+page.svelte`
- `frontend/packages/creator-app/src/routes/agent/history/[id]/+page.svelte`
- `frontend/packages/creator-app/src/routes/libraries/+page.svelte`

### Frontend -- Modified
- `frontend/packages/creator-app/src/routes/+layout.svelte`
- `frontend/packages/ui/src/lib/locales/en.json`
- `frontend/packages/ui/src/lib/locales/es.json`
- `frontend/packages/ui/src/lib/locales/ca.json`
- `frontend/packages/ui/src/lib/locales/eu.json`

### Frontend -- Deleted
- `frontend/packages/module-chat/src/routes/consent/+page.svelte`
- `frontend/packages/ui/src/lib/i18n/base/en.json`
