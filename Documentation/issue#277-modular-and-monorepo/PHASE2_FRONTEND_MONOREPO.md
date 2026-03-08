# Phase 2: Frontend Monorepo Migration

> **Status**: ✅ Complete  
> **Date**: 2026-03-08  
> **Issue**: #277 — Architecture: Activity Module System  
> **Consolidates**: MIGRATION_MONOREPO.md, PHASE2_EXECUTION_PLAN.md, PHASE2_COMPLETION_SUMMARY.md, DOCKER_CHANGES.md, DOCKER_CI_UPDATES.md, FILES_CREATED.md, PHASE2_BUGS.md, PHASE2_COMMIT_GUIDE.md, README_PHASE2_COMPLETE.md (all in `frontend/`)

---

## 1. Objective

Restructure the LAMB frontend from a monolithic `svelte-app/` SPA into a **pnpm monorepo** with:

- **`@lamb/ui`** — Shared library (components, stores, services, i18n)
- **`creator-app`** — The LAMB creator SPA (migrated from `svelte-app/`)
- **Future module packages** — `module-chat`, `module-file-eval`, etc.

This enables multiple independent SvelteKit apps (one per LTI activity module) sharing the same UI components and authentication, without code duplication.

---

## 2. Architecture

```
frontend/
├── pnpm-workspace.yaml              ← Workspace config: packages/*
├── pnpm-lock.yaml                   ← Lockfile (committed)
│
├── packages/
│   ├── ui/                          ← @lamb/ui shared library
│   │   ├── package.json             ← name: @lamb/ui, exports map
│   │   └── src/lib/
│   │       ├── index.js             ← Main re-export point
│   │       ├── components/          ← Nav, Footer, LanguageSelector,
│   │       │                          ConfirmationModal, Pagination
│   │       ├── stores/              ← userStore, configStore
│   │       ├── services/            ← authService, configService
│   │       ├── i18n/                ← setupI18n, locale, _, waitLocale
│   │       │                          (wraps svelte-i18n internally)
│   │       ├── locales/             ← en.json, es.json, ca.json, eu.json
│   │       └── styles/              ← theme.css (Tailwind utilities)
│   │
│   └── creator-app/                 ← Main LAMB creator application
│       ├── package.json             ← depends on "@lamb/ui": "workspace:*"
│       ├── svelte.config.js         ← adapter-static → output: ../../build
│       ├── vite.config.js           ← proxy to backend:9099, optimizeDeps
│       └── src/
│           ├── routes/              ← SvelteKit pages
│           ├── lib/
│           │   ├── components/      ← App-specific (assistants, admin,
│           │   │                      evaluaitor, knowledgebases...)
│           │   ├── services/        ← App-specific API services
│           │   ├── stores/          ← App-specific stores
│           │   └── utils/           ← apiClient, sessionGuard, etc.
│           ├── app.html, app.css
│           └── hooks.server.js
│
├── build/                           ← Build output (SAME PATH as before)
│   ├── index.html
│   └── app/immutable/              ← chunks/, assets/, entry/, nodes/
│                                     (normal SvelteKit build artifacts)
│
└── svelte-app/                      ← ⚠️ OLD remnant — safe to delete
```

### Build Output

The build output path is **unchanged**: `frontend/build/`. This means:

- **Backend** (`main.py`): No changes — still serves `../frontend/build`
- **Caddy** (prod): No changes — still mounts `frontend/build:/var/www/frontend:ro`
- **Docker**: Updated commands only (see Section 6)

---

## 3. What `@lamb/ui` Provides

All consuming apps import shared functionality via `from '@lamb/ui'`:

```javascript
// Components
import { Nav, Footer, LanguageSelector, ConfirmationModal } from '@lamb/ui';

// Stores (authentication state, config)
import { userStore, user, configStore } from '@lamb/ui';

// Services (auth tokens, config reading)
import { authService, configService } from '@lamb/ui';

// i18n (internationalization — multi-language support)
import { _, locale, setupI18n, initI18n, setLocale, waitLocale,
         supportedLocales, fallbackLocale } from '@lamb/ui';

// Version info
import { VERSION_INFO } from '@lamb/ui';
```

### What is `i18n` / `svelte-i18n`?

**i18n = internationalization** (i + 18 letters + n). It is **NOT a UI library** — it is a **translation library**.

`svelte-i18n` enables translating the interface to multiple languages:

```javascript
// Instead of hardcoded text:
<h1>Assistants</h1>

// Use the translation function:
<h1>{$_('nav.assistants')}</h1>

// And define translations in JSON files:
// en.json: { "nav": { "assistants": "Assistants" } }
// es.json: { "nav": { "assistants": "Asistentes" } }
```

`svelte-i18n` is **encapsulated inside `@lamb/ui`**. Consumer apps must import `_`, `locale`, etc. from `@lamb/ui`, NOT directly from `svelte-i18n`.

### Supported Locales

| Code | Language | File |
|------|----------|------|
| `en` | English | `locales/en.json` (~29KB) |
| `es` | Spanish | `locales/es.json` (~29KB) |
| `ca` | Catalan | `locales/ca.json` (~29KB) |
| `eu` | Basque | `locales/eu.json` (~29KB) |

---

## 4. What Was Done (Migration Steps Completed)

### 4.1 — Scaffold Creation

Created the monorepo skeleton:
- `pnpm-workspace.yaml` defining `packages/*`
- `@lamb/ui` package with stores, services, i18n setup, and component stubs
- `creator-app` package with SvelteKit configs adapted for monorepo paths

### 4.2 — Source Code Migration

Copied from `svelte-app/` to `packages/creator-app/`:
- `src/*` (routes, lib, app.html, app.css, hooks.server.js)
- `static/*` (favicon, config.js, images)
- `scripts/generate-version.js`
- `eslint.config.js`, `vitest-setup-client.js`

### 4.3 — Shared Component Extraction

Moved shared components from `creator-app` to `@lamb/ui`:
- `Nav.svelte`, `Footer.svelte`, `LanguageSelector.svelte`
- `ConfirmationModal.svelte`, `Pagination.svelte`
- `userStore.js`, `configStore.js`
- `authService.js`, `configService.js`
- Full i18n setup with 4 locale files

### 4.4 — Import Migration

Updated **50+ files** in `creator-app` to import from `@lamb/ui` instead of local `$lib/` paths:

```javascript
// BEFORE (old SPA):
import { userStore } from '$lib/stores/userStore.js';
import Nav from '$lib/components/Nav.svelte';
import { _ } from 'svelte-i18n';

// AFTER (monorepo):
import { userStore } from '@lamb/ui';
import { Nav } from '@lamb/ui';
import { _ } from '@lamb/ui';
```

### 4.5 — Docker/Build Updates

Updated `docker-compose-example.yaml` services for pnpm:
- `frontend-build`: `corepack enable && pnpm install && pnpm --filter creator-app build`
- `frontend` (dev): `pnpm install && pnpm --filter creator-app dev -- --host 0.0.0.0`

---

## 5. Bugs Found and Fixed

### Scaffold Bugs (fixed by teammate during initial migration)

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-F1 | `@lamb/ui` services + i18n | Used `$app/environment` (SvelteKit-only) | → `const browser = typeof window !== 'undefined'` |
| BUG-F2 | `@lamb/ui` package.json | `svelte-i18n: ^3.7.4` (conflicts with v4 in creator-app) | → `^4.0.1` |
| BUG-F3 | `@lamb/ui` package.json | Export `./styles` → `index.css` (doesn't exist) | → `theme.css` |
| BUG-F4 | `@lamb/ui` i18n/base/en.json | Not valid JSON | → Valid JSON object |
| BUG-F5 | `@lamb/ui` package.json | `build: "svelte-package && tsc"` (no TS source) | → `"svelte-package"` |
| BUG-F6 | `creator-app` .prettierrc | Extends non-existent root config | → Inline config |
| BUG-F7 | `creator-app` .npmrc | Wrong content (looked like .gitignore) | → `engine-strict=true` |

### Post-Merge Bugs (found and fixed 2026-03-08)

| File | Issue | Fix |
|------|-------|-----|
| `@lamb/ui/components/Footer.svelte` | Used `$lib/i18n` instead of relative path — **caused Docker build failure** | → `../i18n/index.js` |
| `creator-app/hooks.server.js` | Direct `from 'svelte-i18n'` import | → `from '@lamb/ui'` |
| `creator-app/routes/+layout.js` | Mixed `svelte-i18n` + `@lamb/ui` imports | → Single `@lamb/ui` import |
| `creator-app/components/AssistantSharingModal.svelte` | Direct `from 'svelte-i18n'` import | → `from '@lamb/ui'` |

> **Root cause of Docker build failure**: `$lib` is a SvelteKit alias that resolves to `src/lib/` of the **compiling app**. When `@lamb/ui`'s `Footer.svelte` used `from '$lib/i18n'`, it resolved to `creator-app/src/lib/i18n` (doesn't exist) instead of `ui/src/lib/i18n`. Fix: use relative imports in library code.

---

## 6. Docker Configuration

### docker-compose-example.yaml — Key Services

**`frontend-build`** (compiles the SPA):
```yaml
frontend-build:
  image: node:20-alpine
  working_dir: ${LAMB_PROJECT_PATH}/frontend     # ← was: frontend/svelte-app
  command: >
    sh -lc "apk add --no-cache git &&
    git config --global --add safe.directory ${LAMB_PROJECT_PATH} &&
    corepack enable &&
    corepack prepare pnpm@latest --activate &&
    pnpm install &&
    pnpm --filter creator-app build"              # ← was: npm install && npm run build
```

**`frontend`** (dev server):
```yaml
frontend:
  image: node:20-alpine
  working_dir: ${LAMB_PROJECT_PATH}/frontend
  command: >
    sh -lc "... corepack enable && pnpm install &&
    pnpm --filter creator-app dev -- --host 0.0.0.0"
```

**`docker-compose.prod.yaml`**: No changes — mounts `frontend/build:/var/www/frontend:ro`

### What Does NOT Change

| Component | Path/Config | Changed? |
|-----------|------------|----------|
| Build output | `frontend/build/` | ❌ Same |
| Backend serving | `../frontend/build` in `main.py` | ❌ Same |
| Caddy | `/var/www/frontend` | ❌ Same |
| API proxy (dev) | `http://backend:9099` for `/creator`, `/lamb`, `/static` | ❌ Same |
| Dev server port | `5173` | ❌ Same |

---

## 7. Development Commands

### Local Development (without Docker)

```bash
cd frontend

# Install all workspace packages (requires pnpm)
pnpm install

# Run dev server with hot reload
pnpm --filter creator-app dev

# Build for production
pnpm --filter creator-app build

# Output: frontend/build/
```

### Installing pnpm

```bash
# Option 1: corepack (comes with Node 16+)
corepack enable && corepack prepare pnpm@latest --activate

# Option 2: npx (no global install)
npx pnpm install
npx pnpm --filter creator-app build

# Option 3: npm global
npm install -g pnpm
```

### With Docker

```bash
# Full stack
docker compose -f docker-compose-example.yaml up

# Just frontend build
docker compose -f docker-compose-example.yaml up frontend-build
```

---

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| `Module @lamb/ui not found` | Run `pnpm install` from `frontend/` |
| `pnpm: command not found` | `corepack enable` or `npm install -g pnpm` |
| `Cannot find native binding` (Tailwind) | `rm -rf node_modules && pnpm install --force` |
| `EACCES: permission denied` | Never use `sudo` with npm/pnpm. Fix: `sudo rm -rf node_modules && pnpm install` |
| TS errors `Cannot find module '@lamb/ui'` in IDE | IDE-only issue — resolved after `pnpm install`. Build works fine. |
| Build output not in `frontend/build/` | Check `svelte.config.js` has `pages: '../build'` |

---

## 9. Cleanup Recommendations

| Item | Status | Action |
|------|--------|--------|
| `frontend/svelte-app/` | ⚠️ Old remnant | Safe to delete — all code migrated to `packages/creator-app/` |
| `frontend/packages/ui/src/lib/i18n/base/` | ⚠️ Unused (only has placeholder en.json) | Safe to delete — real locales are in `locales/` |
| `.pnpm-store/` inside project | ⚠️ pnpm cache (can be huge) | Safe to delete — pnpm re-downloads as needed. Add to `.gitignore` |
| 9 Phase 2 docs in `frontend/` | ⚠️ Superseded by this document | Can be deleted once this doc is reviewed |

---

## 10. Verification Checklist

- [x] `pnpm install` from `frontend/` succeeds
- [x] `pnpm --filter creator-app build` completes without errors
- [x] `frontend/build/` contains complete SPA (index.html, app/)
- [x] All imports in `creator-app` use `@lamb/ui` (no direct `svelte-i18n`)
- [x] All imports in `@lamb/ui` use relative paths (no `$lib/`)
- [x] Docker `frontend-build` service uses pnpm
- [x] Docker `frontend` dev service uses pnpm
- [x] `docker-compose.prod.yaml` mounts `frontend/build` correctly
- [x] Backend serves `frontend/build/` unchanged

---

## 11. Related Documentation

- [PHASE1_MODULE_SYSTEM.md](./PHASE1_MODULE_SYSTEM.md) — Backend module system (ActivityModule, ChatModule, JWT sessions)
- [Phase 3](../PHASE1_MODULE_SYSTEM.md#phase-3) — Chat module frontend (next phase: port Jinja2 templates to SvelteKit at `packages/module-chat/`)

---

## 12. Architecture Intent

This monorepo enables:

1. **Multiple LTI activity modules** — Chat, file-evaluation, quiz, peer-review
2. **Shared code without duplication** — One auth system, one i18n, consistent UI
3. **Independent module development** — Teams develop/build/test modules separately
4. **Scalable infrastructure** — Add new modules without rebuilding existing ones

```
LMS (Moodle/Canvas)
    ↓ LTI POST /launch
Activity Router (backend/lamb/lti_router.py)
    ↓
    ├── Chat activity      → /m/chat/       (Phase 3: packages/module-chat/)
    ├── File-eval activity → /m/file-eval/  (Phase 4: packages/module-file-eval/)
    └── Creator (current)  → /              (packages/creator-app/)

All modules share:
    @lamb/ui → Nav, Footer, userStore, authService, i18n, theme.css
```
