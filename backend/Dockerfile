# syntax=docker/dockerfile:1.7

ARG NODE_IMAGE=node:20-alpine
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${NODE_IMAGE} AS frontend-build
WORKDIR /frontend/svelte-app

# Needed by scripts/generate-version.js during frontend build to capture
# commit hash/branch/date for VERSION_INFO instead of falling back to unknown.
RUN apk add --no-cache git

COPY frontend/svelte-app/package.json ./package.json
RUN npm install

COPY frontend/svelte-app/ ./
RUN test -f static/config.js || cp static/config.js.sample static/config.js
RUN npm run build

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
