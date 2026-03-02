# Frontend Monorepo Migration Guide

## Phase 2 Completion Checklist: Frontend Monorepo

This document outlines the remaining steps to complete Phase 2 of the Activity Module System. The initial structure has been created; now we need to migrate the existing `svelte-app` to the new monorepo structure.

## What's Already Done ✅

- ✅ Created `pnpm-workspace.yaml`
- ✅ Created `packages/ui/` structure with:
  - Core services (`authService`, `configService`)
  - Core stores (`userStore`, `configStore`)
  - i18n setup
  - Placeholder components
  - Tailwind theme
- ✅ Created `packages/creator-app/` skeleton with config files

## Remaining Steps

### Step 1: Copy Source Files to creator-app

Copy the key source directories from `svelte-app/` to `packages/creator-app/src/`:

```bash
cd frontend

# Copy source structure
cp -r svelte-app/src/* packages/creator-app/src/

# Copy static assets
cp -r svelte-app/static packages/creator-app/

# Copy build scripts
cp -r svelte-app/scripts packages/creator-app/

# Copy configuration files (if different)
cp svelte-app/.prettierrc packages/creator-app/
cp svelte-app/tsconfig.json packages/creator-app/  # Override if needed
```

### Step 2: Verify and Update Package Dependencies

In **`packages/creator-app/package.json`**:
- ✅ Already has `@lamb/ui: "workspace:*"`
- Verify all dependencies are correct
- Run `pnpm install` to install/link packages

### Step 3: Update Imports in creator-app

Find all instances in `creator-app/` that import from the old location and update:

**Before:**
```javascript
import { userStore } from '$lib/stores/userStore.js';
import { authService } from '$lib/services/authService.js';
import Nav from '$lib/components/Nav.svelte';
```

**After:**
```javascript
import { userStore, authService } from '@lamb/ui';
import { Nav } from '@lamb/ui';
```

Use these search patterns:

```bash
# Find imports to be migrated
grep -r "from '\$lib/stores/" packages/creator-app/src/
grep -r "from '\$lib/services/auth" packages/creator-app/src/
grep -r "import Nav from" packages/creator-app/src/
grep -r "import Footer from" packages/creator-app/src/
grep -r "import LanguageSelector from" packages/creator-app/src/
```

### Step 4: Extract Shared Components to @lamb/ui

These components should be symlinked or copied to `@lamb/ui/src/components`:

From `creator-app/src/lib/components/`:
- `Nav.svelte` → `@lamb/ui/src/components/Nav.svelte`
- `Footer.svelte` → `@lamb/ui/src/components/Footer.svelte`
- `LanguageSelector.svelte` → `@lamb/ui/src/components/LanguageSelector.svelte`
- `common/` - commonly-used components
- `modals/ConfirmationModal.svelte` → `@lamb/ui/src/components/modals/`

### Step 5: Move App-Specific Code

**Creator-specific code stays in creator-app** (not in @lamb/ui):
- `assistants/` directory
- `admin/` directory
- `promptTemplates/` directory
- `login/signup` flows
- `KnowledgeBasesComponent`

Structure:
```
packages/creator-app/src/lib/
├── components/
│   ├── assistants/          ← Creator-specific
│   ├── admin/               ← Creator-specific
│   ├── promptTemplates/     ← Creator-specific
│   ├── common/              ← Creator utils (not @lamb/ui)
│   └── [shared → @lamb/ui]  ← Nav, Footer, etc.
├── services/
│   ├── assistantService.js  ← Creator-specific
│   ├── adminService.js      ← Creator-specific
│   ├── [shared → @lamb/ui]  ← authService, configService
│   └── ...
└── stores/
    ├── assistantStore.js    ← Creator-specific
    └── [shared → @lamb/ui]  ← userStore, configStore
```

### Step 6: Extract Common Stores to @lamb/ui

From `creator-app/src/lib/stores/`, the following might be useful for other modules:
- `userStore.js` (already done)
- Potential: `organizationStore` (for multi-tenancy)
- App-specific stores stay in creator-app

### Step 7: Extract Common Locales to @lamb/ui

Move common translation keys to `@lamb/ui/src/i18n/base/`:

```bash
# Extract common keys from each locale file
# en.json, es.json, ca.json, eu.json
```

Common keys to extract:
- `common.*` (OK, Cancel, Save, Delete, Loading, etc.)
- `auth.*` (Login, Logout, Sign up, etc.)
- `nav.*` (navigation items that appear everywhere)

Creator-specific keys stay in:
- `packages/creator-app/src/lib/locales/`

### Step 8: Update i18n Setup in creator-app

In `packages/creator-app/src/+layout.svelte` or main app entry:

```javascript
import { initI18n, addMessages } from '@lamb/ui';
import en from './lib/locales/en.json';
import es from './lib/locales/es.json';
import ca from './lib/locales/ca.json';
import eu from './lib/locales/eu.json';

// Initialize shared i18n
initI18n();

// Add creator-specific locales
addMessages('en', en);
addMessages('es', es);
addMessages('ca', ca);
addMessages('eu', eu);
```

### Step 9: Update Build Paths in CI/Docker

**`Dockerfile`** (if building frontend separately):
```dockerfile
# Build @lamb/ui first
RUN cd frontend/packages/ui && npm install && npm run build

# Then build creator-app
RUN cd frontend/packages/creator-app && npm install && npm run build

# Output: frontend/build
COPY frontend/build /app/frontend/build
```

**GitHub Actions / CI scripts**:
```yaml
- name: Install and build frontend
  run: |
    cd frontend
    pnpm install
    pnpm -r build
    # Output goes to frontend/build
```

**`docker-compose.yaml`**:
```yaml
services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - BUILD_CONTEXT=frontend
```

### Step 10: Test the Build

```bash
cd frontend

# Install all workspace packages
pnpm install

# Build everything
pnpm -r build

# Output should be at frontend/build/
ls -la build/

# Serve locally for testing
cd packages/creator-app && npm run preview
```

### Step 11: Update Backend to Serve Correct Paths

In `backend/main.py`:

```python
# Mount creator-app (currently at root)
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")

# For module frontends (Phase 3+):
# app.mount("/m/chat", StaticFiles(directory="frontend/modules/chat/build", html=True))
# app.mount("/m/file-eval", StaticFiles(directory="frontend/modules/file-eval/build", html=True))
```

### Step 12: Cleanup

1. Verify creator-app works in dev mode:
   ```bash
   cd frontend/packages/creator-app
   npm run dev
   ```

2. Test production build:
   ```bash
   npm run build
   npm run preview
   ```

3. Once verified:
   - Keep `svelte-app/` for reference (or remove if confident)
   - Update project docs to reference `packages/creator-app` instead

## Commands Reference

### Development
```bash
# From frontend/ directory
pnpm install                          # Install all workspace packages
pnpm -r dev                          # Run all in dev mode
pnpm --filter creator-app dev        # Run just creator-app
pnpm --filter @lamb/ui build         # Build just @lamb/ui
```

### Building
```bash
# Full build
pnpm -r build                         # Output: frontend/build/

# Specific package
pnpm --filter creator-app build
```

### Integration
```bash
# From project root with docker-compose
docker-compose up frontend
```

## Troubleshooting

### Issue: "@lamb/ui not found"
**Solution**: Run `pnpm install` in frontend/ to link workspace packages

### Issue: Path resolution errors
**Solution**: Check that paths in `vite.config.js` match the new structure (e.g., `pages: '../../build'`)

### Issue: Styles not loading
**Solution**: Ensure `@lamb/ui/src/styles/theme.css` is imported in creator-app's main app.css

### Issue: i18n not working
**Solution**: Verify `initI18n()` is called early in the app lifecycle, before components render

## Next Steps (Phase 3)

Once Phase 2 is complete:
1. Create `packages/module-chat/` as a new SvelteKit app
2. Port Jinja2 templates (dashboard, setup, consent) to Svelte
3. Update LTI launch to redirect to `/m/chat/` endpoints
4. Remove Jinja2 templates from backend

## References

- [pnpm Workspaces](https://pnpm.io/workspaces)
- [SvelteKit Adapter Documentation](https://kit.svelte.dev/docs/adapters)
- [Svelte Component Libraries](https://kit.svelte.dev/docs/packaging)
