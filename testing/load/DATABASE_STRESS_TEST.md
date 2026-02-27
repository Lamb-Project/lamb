# LAMB Database Stress Testing

## Overview

This guide documents the current `stress_test_db.py` workflow. The script now supports:

- Explicit endpoint overrides and optional auth
- Server readiness checks
- CSV summary output and JSONL per-request capture
- Response body capture with truncation controls
- Embeddings model discovery for reporting

## What the Script Does

The `stress_test_db.py` script sends concurrent POST requests to the LAMB assistant chat endpoint. It is designed to expose SQLite write contention and identify capacity/latency limits under load.

Default endpoint:

```
{API_BASE_URL}/creator/assistant/{ASSISTANT_ID}/chat/completions
```

You can override the endpoint path or API base URL via flags.

## Prerequisites

```bash
pip install requests
# Optional (only required for the async runner):
pip install aiohttp
```

## Configuration

### Environment Variables (Required)

- `API_BASE_URL` or `MOCK_OPENAI_BASE_URL`
- `JWT_TOKEN` (unless you pass `--no-auth`)
- `ASSISTANT_ID`

### Optional Environment Variables

- `NO_SERVER_CHECK=true` to disable readiness checks
- `RESPONSE_BODY_MAX_CHARS=10000` to cap stored response text
- Embeddings config discovery (for CSV summary):
  - `EMBEDDINGS_CONFIG_URL` or `KB_EMBEDDINGS_CONFIG_URL`
  - `EMBEDDINGS_CONFIG_TOKEN`, `KB_EMBEDDINGS_CONFIG_TOKEN`, `KB_API_KEY`, `KB_SERVER_API_KEY`

## Quick Start

### Set Environment Variables

```bash
# Windows PowerShell
$env:API_BASE_URL = "http://localhost:9099"
$env:JWT_TOKEN = "your_token_here"
$env:ASSISTANT_ID = "1"

# Linux/macOS
export API_BASE_URL=http://localhost:9099
export JWT_TOKEN=your_token_here
export ASSISTANT_ID=1
```

### Run a Test

```bash
# Basic: 50 concurrent users, 100 requests
python stress_test_db.py --vus 50 --requests 100

# Duration-based (60 seconds)
python stress_test_db.py --vus 50 --duration 60

# Save JSON summary and raw results
python stress_test_db.py --vus 100 --requests 200 --output results.json

# Save per-request responses as JSON Lines
python stress_test_db.py --vus 100 --requests 200 --responses responses.jsonl

# Provide a custom prompt (default is "Hello")
python stress_test_db.py --vus 50 --requests 100 --prompt "Say hello in Basque"

# Async/high-concurrency (connection reuse — default)
python stress_test_db.py --vus 200 --requests 1000 --responses responses.jsonl --csv results.csv

# Legacy threaded runner (opt-out)
python stress_test_db.py --vus 50 --requests 100 --sync --responses responses.jsonl --csv results.csv

# Save a CSV summary row
python stress_test_db.py --vus 100 --requests 200 --csv results.csv

# Override endpoint path and skip auth
python stress_test_db.py --vus 50 --requests 100 --endpoint-path /v1/chat/completions --no-auth
```

## Command-Line Options

```
--vus VUS                   Number of concurrent virtual users (required)
--requests N                Total requests to send (use with --vus or --duration)
--duration SECONDS          Test duration in seconds (use instead of --requests)
--timeout SECONDS           Request timeout in seconds (default 120)
--output FILE               Save JSON summary and raw results
--responses FILE            Append per-request responses as JSON Lines
--csv FILE                  Append a summary row to CSV
--response-max-chars N       Max response body characters to store per request
--env-file FILE             Load env vars from a .env file
--api-base-url URL           Override API base URL
--endpoint-path PATH        Override endpoint path (supports {assistant_id})
--auth-token TOKEN          Override bearer token
--no-auth                   Disable Authorization header
--no-check                  Skip server readiness check
--prompt STRING             Custom prompt/message to send with each request (default: "Hello")
--async                     Use asyncio/aiohttp runner (reuses connections; recommended for high VU) (default)
--sync                      Use legacy sync/threaded runner instead of async
--verbose                   Print detailed progress logs
```

## Output Files

### JSON Summary Output (`--output`)

The JSON output now includes new fields and embeds raw results:

```json
{
  "metadata": {
    "timestamp": "2026-02-12T10:30:45.123456+00:00",
    "api_url": "http://localhost:9099",
    "assistant_id": "1",
    "vus": 50,
    "total_requests": 100,
    "duration": null,
    "timeout": 120
  },
  "statistics": {
    "total_requests": 100,
    "successful": 100,
    "failed": 0,
    "error_rate_percent": 0.0,
    "status_codes": {
      "200": 100
    },
    "errors": {},
    "latency_ms": {
      "min": 245.32,
      "max": 1045.67,
      "mean": 487.25,
      "median": 465.18,
      "p95": 892.45,
      "p99": 956.23,
      "stdev": 198.76
    }
  },
  "raw_results": [
    {
      "status_code": 200,
      "latency_ms": 245.32,
      "success": true,
      "error": null,
      "model": "gpt-4o-mini",
      "response_text": "...",
      "response_truncated": false,
      "timestamp": "2026-02-12T10:30:45.123456+00:00"
    }
  ]
}
```

### JSON Lines Responses (`--responses`)

If you provide `--responses`, each request result is appended as a single JSON line. This is the preferred format for large tests.

### CSV Summary (`--csv`)

The script appends a summary row per run (no per-request rows):

```
index,assistant_id,model,embedding_model,total_requests,vus,max_time,total_time,success_pct,error
```

Notes:

- `model` is the most common response model in this run
- `embedding_model` is discovered from embeddings config endpoints
- `total_requests` is either a number or `duration:<seconds>`
- `max_time` is the timeout value (seconds)
- `error` is a compact summary (e.g., `Timeout(12); 500(3)`)

## Server Readiness Checks

By default, the script probes the API base URL and assistant endpoint before running. It treats any response under 500 as "server is up".

Disable with:

```bash
python stress_test_db.py --vus 50 --requests 100 --no-check
```

## Testing Strategy (Suggested)

### Phase 1: Baseline

```bash
python stress_test_db.py --vus 10 --requests 50 --verbose
```

Record:

- Error rate
- P95 latency
- Status code distribution

### Phase 2: Progressive Load

```bash
python stress_test_db.py --vus 50 --requests 200 --csv step1.csv
python stress_test_db.py --vus 100 --requests 200 --csv step2.csv
python stress_test_db.py --vus 150 --requests 200 --csv step3.csv
python stress_test_db.py --vus 200 --requests 200 --csv step4.csv
```

Stop when:

- Error rate exceeds 5%
- P95 latency spikes significantly
- You see repeated `Timeout` or 5xx errors

### Phase 3: Sustained Load

```bash
# Use --async for high VU / connection-reuse testing
python stress_test_db.py --vus 100 --duration 300 --responses sustained.jsonl --async
```

Monitor for:

- Cumulative error growth
- Latency drift
- Log-level failures

## Troubleshooting

### Missing environment variables

```bash
API_BASE_URL=http://localhost:9099
JWT_TOKEN=your_token
ASSISTANT_ID=1
```

### Connection refused

Backend not running. Start it from [backend/README.md](../backend/README.md).

### 401 Unauthorized

Invalid `JWT_TOKEN`. Generate a new one or use `--no-auth` only for endpoints that permit it.

### High memory usage

Use `--responses` (JSONL) instead of `--output` for long runs, or reduce `--response-max-chars`.