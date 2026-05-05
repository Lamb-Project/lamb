# Merge: dev → feature/issue#277/phase4_lamba_port
> **Date:** 2026-05-05  
> **Branch:** `feature/issue#277/phase4_lamba_port`  
> **Source:** `dev`
---
## Summary
Merge of `dev` into the Phase 4 (file evaluation) branch. This brought in resilience fixes (#352, #353), new services, and bug fixes from the main development line.
---
## Key Decisions
### 1. `svelte-app/` directory removed
The entire `frontend/svelte-app/` directory was deleted during the monorepo migration to `creator-app`. Dev still had this directory with updated files (`authService.js`, `package.json`, `config.js.sample`), but these were **deleted by us** because the equivalent functionality now lives in:
| Old (svelte-app) | New (creator-app / @lamb/ui) |
|------------------|------------------------------|
| `svelte-app/package.json` | `creator-app/package.json` |
| `svelte-app/src/lib/services/authService.js` | `ui/src/lib/services/authService.js` |
| `svelte-app/static/config.js.sample` | `creator-app/src/lib/config.js` + `docker-entrypoint.py` |
### 2. `sanitize.js` placed in `@lamb/ui`
Dev had `sanitize.js` in `creator-app/src/lib/utils/`. We moved it to `ui/src/lib/utils/` because it's a pure utility (marked + DOMPurify) that any module can reuse without app-specific dependencies.
### 3. `apiClient.js` placed in `creator-app` (not `@lamb/ui`)
Dev's `apiClient.js` depends on `$lib/config` (`getApiUrl`) and `$lib/session/sessionManager`, which are app-specific. It was placed in `creator-app/src/lib/services/` to avoid creating a circular dependency. This means **module-chat and module-file-eval cannot use it yet** — they still use raw `fetch()`.
### 4. `authService` kept in `@lamb/ui`
The `authService` object pattern (exporting a single object with all auth methods) was kept from HEAD. Dev used individual function exports. The object pattern is already used by `Login.svelte`, `Signup.svelte`, and `userStore.js`, so changing it would require updating all callers.
### 5. `Nav.svelte` imports kept as relative paths
Dev used `$lib/` imports for `Nav.svelte`, but since it lives inside `@lamb/ui`, the relative paths (`../i18n`, `./LanguageSelector`, `../version`) are correct. Added `getConfig` import that dev had introduced.
### 6. `config.js.sample` deleted
This was a reference template for `window.LAMB_CONFIG`. The actual config is generated dynamically by `backend/docker-entrypoint.py` at container start, and the same information is documented in CLAUDE.md and the entrypoint source. No longer needed as a standalone file.
---
## What from dev did NOT make it (and why)
| Feature | File | Reason |
|---------|------|--------|
| `apiFetch` in `authService.fetchUserProfile()` | `ui/src/lib/services/authService.js` | Circular dependency: `apiClient` is in `creator-app`, `authService` is in `@lamb/ui`. `fetchUserProfile` still uses raw `fetch()` without 401 global handling. |
| `apiClient` in `@lamb/ui` | N/A | Would require decoupling from `$lib/config` and `$lib/session/sessionManager`. Deferred to future refactor. |
| Module-chat/file-eval using `apiFetch` | N/A | These modules don't have `$lib/config.js` and use raw `fetch()` with relative paths. Would need `apiClient` to be generic first. |
| Two `apiClient.js` files coexisting | `utils/apiClient.js` + `services/apiClient.js` | Both exist in creator-app with overlapping responsibilities. `utils/` protects against disabled accounts (`sessionGuard`), `services/` protects against expired tokens (401 → redirect). Not merged yet. |
---
## TODOs for future work
### High Priority
1. **Merge the two `apiClient.js` files into one**
   - `utils/apiClient.js` → `authenticatedFetch` + sessionGuard (disabled account detection)
   - `services/apiClient.js` → `apiFetch` + `apiJson` + `apiAxios` (401 global handling)
   - Create a single unified client that has **both** protections
   - Update all services to use the unified client
   - Delete the duplicate
2. **Move `apiClient.js` to `@lamb/ui`**
   - Replace `getApiUrl()` dependency → read `window.LAMB_CONFIG.api.baseUrl` directly
   - Replace `$lib/session/sessionManager` dependency → make it injectable or use dynamic import
   - This enables **all modules** (creator-app, module-chat, module-file-eval) to use `apiFetch` with global 401 handling
   - Eliminates the circular dependency blocking `authService` improvements
3. **Update `authService.fetchUserProfile()` to use `apiFetch`**
   - Currently uses raw `fetch('/creator/me')` — no 401 global handling
   - Once `apiClient` is in `@lamb/ui`, change to `apiFetch('/me', { token })`
   - This matches what dev's version of `authService` already did
### Medium Priority
4. **Migrate remaining `fetch()` raw calls in creator-app to `apiFetch`**
   - `assistantService.js` — ~10 calls using raw `fetch()`
   - `+page.svelte` (org-admin) — uses `axios` directly instead of `apiAxios`
   - Any other services still using raw `fetch()` or direct `axios` imports
5. **Migrate module-chat and module-file-eval to `apiFetch`**
   - module-chat: 7 calls with raw `fetch()` using `?token=` query params
   - module-file-eval: 4 calls with raw `fetch()` with manual auth headers
   - Requires `apiClient` to be in `@lamb/ui` first (see #2)
### Low Priority
6. **Document `window.LAMB_CONFIG` structure**
   - `config.js.sample` was deleted during this merge
   - Consider adding a proper documentation page or keeping a reference in `docs/`
---
## Files affected by this merge
### Auto-merged (no conflicts)
- `.gitignore`
- `Documentation/352-resilience-fixes-repro.md`
- `Documentation/lamb_architecture_v2.md`
- `backend/.env.example`
- `backend/config.py`
- `backend/creator_interface/library_manager_client.py`
- `backend/docker-entrypoint.py`
- `frontend/packages/creator-app/src/lib/components/AssistantsList.svelte`
- `frontend/packages/creator-app/src/lib/components/KnowledgeBasesList.svelte`
- `frontend/packages/creator-app/src/lib/components/aac/*`
- `frontend/packages/creator-app/src/lib/components/evaluaitor/RubricsList.svelte`
- `frontend/packages/creator-app/src/lib/components/libraries/LibraryDetail.svelte`
- `frontend/packages/creator-app/src/lib/components/modals/*`
- `frontend/packages/creator-app/src/lib/config.js`
- `frontend/packages/creator-app/src/lib/services/aacService.js`
- `frontend/packages/creator-app/src/lib/services/analyticsService.js`
- `frontend/packages/creator-app/src/lib/services/assistantService.js`
- `frontend/packages/creator-app/src/lib/services/knowledgeBaseService.js`
- `frontend/packages/creator-app/src/lib/services/libraryService.js`
- `frontend/packages/creator-app/src/lib/services/organizationService.js`
- `frontend/packages/creator-app/src/lib/services/rubricService.js`
- `frontend/packages/creator-app/src/lib/services/templateService.js`
- `frontend/packages/creator-app/src/lib/services/testService.js`
- `frontend/packages/creator-app/src/lib/session/sessionManager.js`
- `frontend/packages/creator-app/src/lib/stores/aacStore.svelte.js`
- `frontend/packages/creator-app/src/lib/stores/templateStore.js`
- `frontend/packages/creator-app/src/routes/agent/+page.svelte`
- `frontend/packages/creator-app/src/routes/agent/history/[id]/+page.svelte`
- `frontend/packages/creator-app/src/routes/assistants/+page.svelte`
### Resolved conflicts
- `ChatInterface.svelte` — accepted dev (chat history, streaming abort, isMounted)
- `Login.svelte` — merged: `authService.login` + `try/finally` from dev
- `PublishModal.svelte` — merged: `@lamb/ui` imports + `onDestroy` cleanup from dev
- `Signup.svelte` — merged: `authService.signup` + `try/finally` from dev
- `AssistantForm.svelte` — merged: `@lamb/ui` imports + `apiFetch` from dev
- `adminService.js` — accepted dev (uses `apiFetch`)
- `assistantStore.js` — accepted dev (defensive `Array.isArray()`)
- `+layout.js` — accepted dev (`try/catch` around `waitLocale()`)
- `+page.svelte` — merged: `@lamb/ui` imports + `apiFetch`/`sanitize` from dev
- `org-admin/+page.svelte` — merged: `apiAxios` from dev + `@lamb/ui` imports
- `Nav.svelte` — accepted HEAD (relative paths correct for `@lamb/ui`) + added `getConfig`
- `userStore.js` — merged: `authService` from HEAD + validation from dev
### Deleted
- `frontend/svelte-app/package.json`
- `frontend/svelte-app/src/lib/services/authService.js`
- `frontend/svelte-app/static/config.js.sample`
### Added
- `frontend/packages/creator-app/src/lib/services/apiClient.js`
- `frontend/packages/ui/src/lib/utils/sanitize.js`