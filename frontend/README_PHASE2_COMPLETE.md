# Phase 2: Frontend Monorepo — Quick Start

**Status**: ✅ **Foundation Complete** — 32 files created, ready for code migration

---

## What Was Done in 5 Minutes

✅ Created pnpm workspace structure  
✅ Created `@lamb/ui` shared library package  
✅ Created `packages/creator-app` skeleton  
✅ Created 3 comprehensive guides for completing migration  

**Your monorepo is now ready to receive the source code.**

---

## Directory Structure Ready

```
frontend/
├── pnpm-workspace.yaml              ← Manages all packages
├── packages/
│   ├── ui/                          ← Shared components, stores, services
│   ├── creator-app/                 ← Main LAMB app (config only)
│   └── [future: module-chat/, module-file-eval/]
├── svelte-app/                      ← Old location (reference)
└── MIGRATION_MONOREPO.md            ← Your playbook
```

---

## 3 Files to Read (In Order)

### 1. **PHASE2_COMPLETION_SUMMARY.md** (5 min read)
High-level overview of what was built, why, and what comes next.

### 2. **MIGRATION_MONOREPO.md** (30 min to execute)
12 step-by-step instructions to complete the migration:
- Copy source files
- Update imports
- Test build
- Verify everything works

### 3. **DOCKER_CI_UPDATES.md** (reference)
How to update your Docker/CI builds for the new structure.

---

## Quick Commands to Test It

Once you complete the migration:

```bash
cd frontend

# Install all workspace packages
pnpm install

# Build everything
pnpm -r build

# Output appears at: frontend/build/

# Or develop locally
pnpm --filter creator-app dev
```

---

## What Happened Under the Hood

### @lamb/ui Package (The Shared Library)
```
packages/ui/src/
├── components/       - Nav, Footer, LanguageSelector (to be migrated)
├── stores/          - userStore, configStore (ready to use)
├── services/        - authService, configService (ready to use)
├── i18n/            - i18n initialization + base translations
└── styles/          - Shared Tailwind theme
```

**What it provides to all modules**:
- Consistent authentication handling
- Shared UI components
- Multi-language support infrastructure
- Configuration management

### Creator App Package
```
packages/creator-app/
├── src/             - [TO BE POPULATED: Copy from svelte-app/src/]
├── package.json     - Depends on @lamb/ui (workspace:*)
├── svelte.config.js - Builds to ../../build (monorepo root output)
└── vite.config.js   - Includes @lamb/ui in bundling
```

**Key change**: Build outputs to `../../build` instead of `../build`

---

## What Didn't Change

✅ **Backend**: Still serves `frontend/build/` exactly the same  
✅ **Database**: No changes needed  
✅ **API endpoints**: No changes  
✅ **User experience**: Users see same app

---

## Next: Complete the Migration

**Step 1**: Open `frontend/MIGRATION_MONOREPO.md`  
**Step 2**: Execute Steps 1-12 (copy files, update imports, test)  
**Step 3**: Run `pnpm -r build` and verify `frontend/build/` exists  
**Step 4**: Test with the backend (it should work unchanged)

---

## After Migration: Phase 3 (Chat Module)

Once Phase 2 is complete, you can start Phase 3:

```
packages/module-chat/
├── src/routes/
│   ├── dashboard/    - Instructor dashboard (from Jinja2 template)
│   ├── setup/        - Activity setup (from Jinja2 template)
│   └── consent/      - Student consent (from Jinja2 template)
├── src/lib/
│   ├── components/   - Svelte components for chat UI
│   └── locales/      - Chat-specific i18n keys
└── [config files]    - Same as creator-app
```

Phase 3 will be much faster because:
- `@lamb/ui` is already ready with shared components
- Monorepo build pipeline is proven
- You're just adding a new SvelteKit app

---

## Architecture Diagram

```
LMS (Moodle/Canvas)
        ↓ LTI POST
     /launch

    Activity Router (backend/lamb/lti_router.py)
        ↓
    ├── Chat activity      → /m/chat/
    ├── File-eval activity → /m/file-eval/
    └── Future activities  → /m/{module}/

    Each module SPA:
    ├── Svelte components
    ├── Pages & routes
    └── Uses @lamb/ui shared library
        ├── userStore (auth)
        ├── configStore (config)
        ├── Nav component (consistent UI)
        └── i18n (translations)

    Backend handles:
    ├── LTI validation
    ├── Module routing
    ├── API endpoints
    ├── Database
    └── /lamb/v1/chat/completions (AI brain)
```

---

## Files You'll Need to Reference

| File | Purpose |
|------|---------|
| `PHASE2_COMPLETION_SUMMARY.md` | Overview & architecture |
| `MIGRATION_MONOREPO.md` | Step-by-step migration instructions |
| `DOCKER_CI_UPDATES.md` | Docker & CI/CD build updates |
| `FILES_CREATED.md` | Detailed list of all 32 files created |

---

## Troubleshooting

### Q: "Module @lamb/ui not found"
**A**: Run `pnpm install` in `frontend/` to link workspace packages

### Q: "pnpm: command not found"  
**A**: `npm install -g pnpm`

### Q: Where's the build output?
**A**: `frontend/build/` (same as before, no change)

### Q: Do I need to change backend code?
**A**: No. Backend still serves `frontend/build/` unchanged.

---

## Success Criteria

You'll know Phase 2 is complete when:

- ✅ `pnpm install` works in `frontend/`
- ✅ `pnpm -r build` completes without errors
- ✅ `frontend/build/` contains the full SPA
- ✅ Backend serves it without issues
- ✅ All imports in creator-app use `@lamb/ui`
- ✅ Developer can run `pnpm --filter creator-app dev`

---

## Architecture Intent

This monorepo enables:

1. **Multiple modules in one LAMB instance**
   - Chat module (current)
   - File evaluation module (LAMBA port)
   - Quiz module (future)
   - Peer review module (future)

2. **Shared code without duplication**
   - One i18n system
   - One auth system
   - Consistent UI components
   - Shared utilities

3. **Independent module development**
   - Teams develop modules separately
   - Build/test/deploy each module independently
   - No breaking changes to other modules

4. **Scalable infrastructure**
   - Add 10 modules without rebuilding the system
   - Each module is a complete SvelteKit app
   - Monorepo handles all the wiring

---

## You're Reading This Because

✅ Phase 1 (backend module system) was already completed  
✅ Phase 2 foundation has just been completed  
✅ Now you're ready to migrate the source code (manual steps documented)  
✅ Then Phase 3 (chat module frontend) can begin  

**Total time to complete this phase**: 30-60 minutes for the manual migration  
**Difficulty**: Low to Medium (mostly copy-paste + search-replace)

---

## Let's Go! 🚀

1. Open `frontend/MIGRATION_MONOREPO.md`
2. Follow Steps 1-12
3. Run `pnpm -r build`
4. Verify `frontend/build/` exists
5. Test with backend
6. You're done with Phase 2!

Then: Phase 3 awaits with the chat module frontend. 🎯

---

*Last updated: 2026-02-27*  
*Part of: Activity Module System — Extensible LTI App Framework*  
*Phase: 2 / 5 (Foundation Complete)*
