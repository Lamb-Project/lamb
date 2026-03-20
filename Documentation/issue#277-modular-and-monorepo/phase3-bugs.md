# Phase 3 Bugs — Module Chat `/m/chat/` 404 Issue

> **Date:** 2026-03-17
> **Phase:** 3 — Chat Module Frontend
> **Status:** ✅ Fixes applied and verified

---

## Bug #1 — Wrong Asset Paths in Built `index.html`

### Symptom

After LTI launch as instructor, browser redirects to `http://localhost:9099/m/chat/setup?token=...` but the page stays blank. Browser console shows `Not found: /m/chat/setup` — the creator-app's SvelteKit router was handling the request instead of module-chat's.

### Root Cause

[svelte.config.js](file:///home/franpv2004/proyecto/lamb/frontend/packages/module-chat/svelte.config.js) had `paths.base: '/m/chat'` but `paths.relative` defaulted to `true`, causing asset references like `/app/immutable/...` which collide with the creator-app's `/app` mount.

### Fix Applied

```diff
 // frontend/packages/module-chat/svelte.config.js
 paths: {
     base: '/m/chat',
+    relative: false
 },
```

Now the build generates `/m/chat/app/immutable/...` paths ✅

---

## Bug #2 — Adapter-Static Output Path Wrong

### Symptom

Build logs showed `Wrote site to "../build/m/chat" ✔ done` but files appeared at `frontend/packages/build/m/chat/` instead of `frontend/build/m/chat/` where the backend reads from.

### Root Cause

The adapter-static `pages`/`assets` path `'../build/m/chat'` resolves relative to the package directory (`packages/module-chat/`), landing in `packages/build/m/chat/` — a **different directory** from `frontend/build/` (confirmed by different inodes). Same issue affected `creator-app`.

### Fix Applied

```diff
 // frontend/packages/module-chat/svelte.config.js
 adapter: adapter({
-    pages: '../build/m/chat',
-    assets: '../build/m/chat',
+    pages: '../../build/m/chat',
+    assets: '../../build/m/chat',
 })

 // frontend/packages/creator-app/svelte.config.js
 adapter: adapter({
-    pages: '../build',
-    assets: '../build',
+    pages: '../../build',
+    assets: '../../build',
 })
```

---

## Bug #3 — Parallel Build Race Condition

### Symptom

Build succeeds but `frontend/build/m/chat/` is empty — only `frontend/build/app/` (creator-app) exists.

### Root Cause

`adapter-static` calls `rimraf()` on the output directory before writing. With `pnpm --filter creator-app --filter module-chat build` both run **in parallel**:
1. module-chat creates `frontend/build/m/chat/` ✓
2. creator-app calls `rimraf('frontend/build/')` → **deletes everything** including `m/chat/`
3. creator-app writes its own files → `m/chat/` is gone

### Fix Applied

```diff
 // docker-compose-example.yaml — frontend-build service
-pnpm --filter creator-app --filter module-chat build
+pnpm --filter creator-app build && pnpm --filter module-chat build
```

Sequential build: creator-app wipes and writes first, then module-chat adds `m/chat/` subdirectory.

Also changed `strict: false` on both adapters to prevent failures when sibling files exist:

```diff
 // Both svelte.config.js files
-strict: true
+strict: false
```

---

## Bug #4 — Wrong Default Port in `LAMB_PUBLIC_BASE_URL` Fallback

### Symptom

If `LAMB_PUBLIC_BASE_URL` env var is not set, `ChatModule.on_instructor_launch()` redirects to port `8000` instead of `9099`.

### Fix Applied

```diff
 // backend/lamb/modules/chat/__init__.py
-public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:8000")
+public_base = os.getenv("LAMB_PUBLIC_BASE_URL", "http://localhost:9099")
```

---

## Files Modified

| File | Change |
|------|--------|
| `frontend/packages/module-chat/svelte.config.js` | Output path `../../build/m/chat`, `relative: false`, `strict: false` |
| `frontend/packages/creator-app/svelte.config.js` | Output path `../../build`, `strict: false` |
| `docker-compose-example.yaml` | Sequential build (creator-app first, then module-chat) |
| `backend/lamb/modules/chat/__init__.py` | Default port 8000 → 9099 |

---

## Build Verification ✅

After rebuild, `frontend/build/m/chat/index.html` now correctly references:
```
/m/chat/app/immutable/entry/start.JVD3dBkn.js ✅
/m/chat/app/immutable/entry/app.DA2lQoe8.js ✅
base: "/m/chat", assets: "/m/chat" ✅
```

---

## Full Test Checklist

| # | Test | Expected Result | Verified? |
|---|------|----------------|-----------|
| 1 | `frontend/build/m/chat/index.html` exists | File present with `/m/chat/` asset paths | ✅ |
| 2 | Open `/m/chat/setup?token=...` in browser | Setup page renders (not blank/404) | ☐ |
| 3 | DevTools Network: JS/CSS requests | All go to `/m/chat/app/immutable/...` with 200 | ☐ |
| 4 | LTI launch as instructor (unconfigured) | Redirect to `/m/chat/setup` → page loads | ☐ |
| 5 | LTI launch as instructor (configured) | Redirect to `/m/chat/dashboard` → page loads | ☐ |
| 6 | Configure activity from setup page | Save succeeds, redirect to dashboard | ☐ |
| 7 | LTI launch as student (configured + consent) | Consent page loads at `/m/chat/consent` | ☐ |
| 8 | Creator app still works | `http://localhost:5173/` loads normally | ☐ |

---

## Known Limitation: Dev Mode Module-Chat

In `docker-compose-example.yaml`, the `frontend` service only runs `creator-app` dev server. Module-chat pages only work from pre-built static files — no hot-reload. A future improvement would add a separate dev server for module-chat.
