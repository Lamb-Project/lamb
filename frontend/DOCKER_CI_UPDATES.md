# Docker & CI/CD Updates for Frontend Monorepo

## Summary

After Phase 2 of the Activity Module System (Frontend Monorepo migration), the build process for the frontend changes from:

```
svelte-app/ → build/
```

To:

```
packages/creator-app/ → build/
packages/ui/ → packages/ui/dist/
```

The final output directory **remains at `frontend/build/`** (no change for backend integration).

## Docker Compose Updates

### Before (Current)
```yaml
# docker-compose.yaml
services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - LAMB_PROJECT_PATH=${LAMB_PROJECT_PATH}
    # OR: simple npm build in production
```

### After (Phase 2)
```yaml
# docker-compose.yaml
services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
      args:
        - LAMB_PROJECT_PATH=${LAMB_PROJECT_PATH}
    # Build context references these lines:
    # RUN cd frontend && pnpm install && pnpm -r build
    # Result: frontend/build/
```

## Dockerfile Updates

Create a new `Dockerfile.frontend` (or update existing if present):

```dockerfile
# Dockerfile.frontend
FROM node:18-slim as builder

ARG LAMB_PROJECT_PATH=/lamb

WORKDIR ${LAMB_PROJECT_PATH}

# Install pnpm
RUN npm install -g pnpm

# Copy only package files first (for better caching)
COPY frontend/pnpm-workspace.yaml frontend/
COPY frontend/package.json frontend/
COPY frontend/package-lock.json frontend/ 2>/dev/null || true
COPY frontend/packages/ui/package.json frontend/packages/ui/
COPY frontend/packages/creator-app/package.json frontend/packages/creator-app/

# Install dependencies
RUN cd frontend && pnpm install --frozen-lockfile

# Copy source code
COPY frontend/ frontend/

# Build all packages
RUN cd frontend && pnpm -r build

# Output is at: frontend/build/

FROM node:18-slim
RUN mkdir -p /app
COPY --from=builder /lamb/frontend/build /app/static
EXPOSE 5173
CMD ["npm", "run", "preview"]
```

## Local Development Build

### Before
```bash
cd frontend/svelte-app
npm run build
# Output: frontend/build/
```

### After
```bash
cd frontend
pnpm install          # Install all workspace packages
pnpm -r build         # Build all packages (ui + creator-app)
# Output: frontend/build/

# Or build just creator-app:
pnpm --filter creator-app build
```

## CI/CD Pipeline (GitHub Actions)

### Before
```yaml
# .github/workflows/build.yml
- name: Build frontend
  run: |
    cd frontend/svelte-app
    npm install
    npm run build
```

### After
```yaml
# .github/workflows/build.yml
- name: Build frontend
  run: |
    cd frontend
    npm install -g pnpm
    pnpm install
    pnpm -r build
    # Output: frontend/build/
```

## Backend Integration (No Changes Needed)

The backend already mounts the frontend correctly:

```python
# backend/main.py
from fastapi.staticfiles import StaticFiles

# Mount frontend SPA
app.mount(
    "/",
    StaticFiles(directory=os.path.join(base_dir, "../frontend/build"), html=True),
    name="static"
)
```

**All frontend build output is still at `frontend/build/`**, so no backend changes are required.

## Environment Variables

| Variable | Before | After | Changes |
|----------|--------|-------|---------|
| `PROXY_TARGET` | ✅ Works | ✅ Works | None — used in both vite configs |
| `LAMB_PROJECT_PATH` | ✅ Works | ✅ Works | None — Docker build path reference |
| `NODE_ENV` | ✅ Works | ✅ Works | None |

## Verification Checklist

- [ ] `pnpm install` works from `frontend/` (installs all packages)
- [ ] `pnpm -r build` completes without errors
- [ ] `frontend/build/` contains the final SPA
- [ ] Backend can serve `frontend/build/` (existing code works)
- [ ] Docker build succeeds with new Dockerfile.frontend
- [ ] Docker image runs with `npm run preview` (or custom CMD)
- [ ] CI/CD pipeline builds successfully

## Rollout Instructions

1. **Update local development**:
   - Dev team switches from `cd frontend/svelte-app` to `cd frontend`
   - Use `pnpm -r dev` for local development

2. **Update CI/CD**:
   - Update GitHub Actions (or other CI tool) build steps
   - Test build locally with new commands

3. **Update Docker deployment**:
   - Add or update `Dockerfile.frontend`
   - Test with `docker build -f Dockerfile.frontend .`

4. **No backend changes required**:
   - Backend already serves `frontend/build/`
   - Existing deployment configs work as-is

## Troubleshooting

### "pnpm: command not found"
```bash
npm install -g pnpm
```

### "Module not found: @lamb/ui"
```bash
cd frontend
pnpm install  # Re-link workspace packages
```

### Build output not in `frontend/build/`
- Check that `creator-app/svelte.config.js` has correct paths: `pages: '../../build'`
- Check that both packages build successfully: `pnpm -r build --reporter=verbose`

### Docker image won't start
- Verify `Dockerfile.frontend` has correct COPY paths
- Test locally: `docker build -f Dockerfile.frontend -t lamb-frontend . && docker run lamb-frontend`

## References

- [pnpm Install & Build Docs](https://pnpm.io/cli/install)
- [pnpm Filtering](https://pnpm.io/filtering)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
