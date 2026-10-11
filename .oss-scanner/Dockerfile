# syntax=docker/dockerfile:1.7
# Audit environment only. Build from the LAMB repository root.
FROM node:20-bookworm-slim AS node
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git ripgrep sqlite3 pkg-config \
    ffmpeg libmagic1 libgl1 libglib2.0-0 libgomp1 poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Keep the complete checkout, including tests and all service source, at /src.
# Dockerfile.dockerignore overrides the application's narrower root exclusions.
WORKDIR /src
COPY backend/requirements.txt /src/backend/requirements.txt
COPY lamb-cli/ /src/lamb-cli/

# Services intentionally use separate environments: their dependency constraints differ.
RUN python -m venv /opt/venvs/backend \
    && /opt/venvs/backend/bin/pip install --no-cache-dir --upgrade pip \
    && if [ "$(uname -m)" = x86_64 ]; then \
         /opt/venvs/backend/bin/pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu; \
       fi \
    && /opt/venvs/backend/bin/pip install --no-cache-dir -r backend/requirements.txt \
    && /opt/venvs/backend/bin/pip install --no-cache-dir \
         'pytest==8.3.5' 'pytest-asyncio==0.25.3' 'pytest-httpx==0.35.0' \
         'pytest-cov==6.1.1' 'pytest-subtests==0.14.2' -e ./lamb-cli \
    && /opt/venvs/backend/bin/pip check

COPY frontend/svelte-app/package.json /src/frontend/svelte-app/
# dev does not track a package-lock.json. Preserve the resolved lock in the image.
RUN --mount=type=cache,target=/root/.npm \
    cd frontend/svelte-app \
    && npm install --ignore-scripts --no-audit --no-fund --loglevel=info \
         --fetch-retries=1 --fetch-timeout=60000 \
    && npx playwright install --with-deps chromium

COPY library-manager/ /src/library-manager/
RUN python -m venv /opt/venvs/library \
    && /opt/venvs/library/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venvs/library/bin/pip install --no-cache-dir -e './library-manager[all,dev]' \
    && /opt/venvs/library/bin/pip check

COPY lamb-kb-server-stable/backend/requirements.txt /src/lamb-kb-server-stable/backend/requirements.txt
RUN python -m venv /opt/venvs/kb \
    && /opt/venvs/kb/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venvs/kb/bin/pip install --no-cache-dir 'torch==2.9.1' --index-url https://download.pytorch.org/whl/cpu \
    && /opt/venvs/kb/bin/pip install --no-cache-dir -r lamb-kb-server-stable/backend/requirements.txt \
         'pytest==8.3.5' 'pytest-asyncio==0.25.3' \
    && /opt/venvs/kb/bin/pip check

COPY . /src
RUN cd frontend/svelte-app \
    && npm rebuild \
    && cp static/config.js.sample static/config.js \
    && npm run build

# All credentials below are disposable test values, never production secrets.
ENV PATH="/opt/venvs/backend/bin:${PATH}" \
    LAMB_WEB_HOST=http://127.0.0.1:9099 \
    LAMB_BACKEND_HOST=http://127.0.0.1:9099 \
    LAMB_BEARER_TOKEN=scanner-test-bearer \
    LAMB_JWT_SECRET=scanner-test-jwt-secret-at-least-32-bytes \
    SESSION_SECRET=scanner-test-session-secret-at-least-32-bytes \
    LAMB_KB_SERVER=http://127.0.0.1:9090 \
    LAMB_KB_SERVER_TOKEN=scanner-test-service \
    LAMB_API_KEY=scanner-test-service \
    SIGNUP_SECRET_KEY=scanner-test-signup \
    OPENAI_API_KEY=scanner-test-key \
    OPENAI_BASE_URL=http://127.0.0.1:18080/v1 \
    OPENAI_MODEL=scanner-test-model \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OWI_PATH=/tmp/lamb-scanner/owi \
    OWI_BASE_URL=http://127.0.0.1:8080 \
    OWI_ADMIN_NAME=Scanner \
    OWI_ADMIN_EMAIL=scanner@example.test \
    OWI_ADMIN_PASSWORD=scanner-test-password \
    LAMB_DB_PATH=/tmp/lamb-scanner/lamb \
    LAMB_MOODLE_ENCRYPTION_KEY=MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA= \
    LAMB_API_TOKEN=scanner-test-service \
    DATA_DIR=/tmp/lamb-scanner/library \
    TOKENIZERS_PARALLELISM=false

RUN /opt/venvs/backend/bin/pip install --no-cache-dir 'respx==0.22.0' \
    && /opt/venvs/backend/bin/pip check

# QR shell regression tests deliberately use only /usr/bin:/bin.
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /src/lamb-kb-server-stable/backend/static /src/lamb-kb-server-stable/backend/data

# Minimal synthetic compatibility schema, matching OwiDatabaseManager's row order.
# It is not an Open WebUI deployment or a copy of any user's database.
RUN python - <<'PY'
import os
import sqlite3
from pathlib import Path
for name in ('owi', 'lamb', 'library'):
    Path('/tmp/lamb-scanner', name).mkdir(parents=True, exist_ok=True)
with sqlite3.connect(Path(os.environ['OWI_PATH']) / 'webui.db') as db:
    db.executescript('''
        CREATE TABLE user (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL, profile_image_url TEXT NOT NULL, api_key TEXT,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
            last_active_at INTEGER NOT NULL, settings TEXT, info TEXT, oauth_sub TEXT
        );
        CREATE TABLE auth (
            id TEXT PRIMARY KEY, email TEXT NOT NULL, password TEXT NOT NULL,
            active INTEGER NOT NULL
        );
    ''')
PY
RUN /opt/venvs/backend/bin/pip freeze > /opt/venvs/backend/installed.txt \
    && /opt/venvs/library/bin/pip freeze > /opt/venvs/library/installed.txt \
    && /opt/venvs/kb/bin/pip freeze > /opt/venvs/kb/installed.txt

# No server is launched automatically; the auditor chooses tests or local services.
WORKDIR /src
CMD ["/bin/bash"]
