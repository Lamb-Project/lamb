FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY backend/ backend/

# Pre-build wheels for the default install + all optional extras so the
# runtime image does not need any build toolchain.
RUN pip wheel --no-cache-dir --wheel-dir=/wheels ".[all]"

# ---------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY backend/ .

RUN useradd -r -s /bin/false appuser && \
    mkdir -p /app/data/storage && \
    chown -R appuser:appuser /app/data

USER appuser

EXPOSE 9092

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://127.0.0.1:9092/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9092"]
