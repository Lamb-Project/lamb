# Docker BuildKit Cache for Pip Downloads

This repository now uses Docker BuildKit's cache mount feature to speed up Docker builds by caching pip downloads across builds.

## What Changed

All Python Dockerfiles now include:
1. `# syntax=docker/dockerfile:1.12` directive at the top
2. `RUN --mount=type=cache,target=/root/.cache/pip` for pip install commands
3. `RUN --mount=type=cache,target=/root/.cache/uv` for uv pip install commands (open-webui only)
4. Removed `--no-cache-dir` flags from pip/uv commands to allow caching

## How to Use

### Automatic (Recommended)
Docker BuildKit is enabled by default in Docker 23.0 and later. The cache will work automatically when building.

### Manual Enablement
If you're using an older version of Docker, you can enable BuildKit by:

**Option 1: Per-build**
```bash
DOCKER_BUILDKIT=1 docker build -t myimage .
```

**Option 2: Permanently**
Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):
```bash
export DOCKER_BUILDKIT=1
```

Or configure in Docker daemon settings (`/etc/docker/daemon.json`):
```json
{
  "features": {
    "buildkit": true
  }
}
```

### Using with Docker Compose
Docker Compose v2.x automatically uses BuildKit. For older versions:
```bash
DOCKER_BUILDKIT=1 docker-compose build
```

Or set in your docker-compose file:
```yaml
services:
  myservice:
    build:
      context: .
      dockerfile: Dockerfile
      cache_from:
        - myimage:latest
```

## Benefits

- **Faster builds**: Pip packages are cached between builds
- **Reduced bandwidth**: Packages are only downloaded once
- **Better for development**: Iterative builds are much faster when dependencies don't change

## Affected Dockerfiles

- `lamb-kb-server-stable/frontend/Dockerfile`
- `lamb-kb-server-stable/Dockerfile.server`
- `lamb-kb-server-stable/Dockerfile.webapp`
- `open-webui/Dockerfile`

## Cache Location

The cache is stored locally on your build machine in Docker's cache storage. You can manage it with:

```bash
# View cache usage
docker buildx du

# Prune build cache (if needed)
docker builder prune
```

## CI/CD Considerations

In CI/CD environments (GitHub Actions, GitLab CI, etc.), you may need to:
1. Enable BuildKit explicitly
2. Configure cache storage backends (e.g., GitHub Actions cache)
3. Use `--cache-from` and `--cache-to` flags for distributed caching

Example for GitHub Actions:
```yaml
- name: Build with cache
  uses: docker/build-push-action@v5
  with:
    context: .
    file: ./Dockerfile
    push: false
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

## Limitations

- Cache is local to the build machine by default
- In some CI environments, cache may not persist between runs without additional configuration
- Non-root users may need different cache target paths

## References

- [Docker BuildKit Documentation](https://docs.docker.com/build/buildkit/)
- [Python Speed Article](https://pythonspeed.com/articles/docker-cache-pip-downloads/)
- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
