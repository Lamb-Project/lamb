# syntax=docker/dockerfile:1.7

ARG NODE_IMAGE=node:20-alpine
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${NODE_IMAGE} AS frontend-build
WORKDIR /frontend

# Needed by scripts/generate-version.js during frontend build to capture
# commit hash/branch/date for VERSION_INFO instead of falling back to unknown.
RUN apk add --no-cache git
RUN corepack enable && corepack prepare pnpm@latest --activate

COPY frontend/package.json frontend/pnpm-workspace.yaml ./
COPY frontend/packages/ui/package.json ./packages/ui/package.json
COPY frontend/packages/creator-app/package.json ./packages/creator-app/package.json
COPY frontend/packages/module-chat/package.json ./packages/module-chat/package.json
COPY frontend/packages/module-file-eval/package.json ./packages/module-file-eval/package.json

RUN pnpm install --no-frozen-lockfile

COPY frontend/ ./
RUN pnpm --filter creator-app build \
 && pnpm --filter module-chat build \
 && pnpm --filter module-file-eval build

FROM ${PYTHON_IMAGE} AS runtime
WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=9099

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /frontend/build /app/frontend/build
RUN chmod +x /app/backend/docker-entrypoint.py

EXPOSE 9099

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 CMD curl --fail http://127.0.0.1:${PORT}/status || exit 1

ENTRYPOINT ["python", "/app/backend/docker-entrypoint.py"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9099", "--forwarded-allow-ips", "*"]
