# Load Test for /v1/chat/completions

Concurrent load test script for the LAMB completion endpoint. Sends multiple simultaneous requests to measure throughput, success rate, and response time distribution against real LLM providers.

## Requirements

- Python 3.8+
- `aiohttp` (`pip install aiohttp`)

## Usage

```bash
python3 testing/load_test_completions.py [options]
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--url` | LAMB backend URL | `http://localhost:9099` |
| `--api-key` | Bearer token | `0p3n-w3bu!` |
| `--model` | Model/assistant ID (e.g. `lamb_assistant.58`) | `lamb_assistant.58` |
| `--users` | Number of concurrent users | `30` |
| `--timeout` | Per-request timeout in seconds | `180` |
| `--prompt` | Custom prompt (overrides default short prompt) | Short "say hello" prompt |

### Examples

Basic test with 30 concurrent users:
```bash
python3 testing/load_test_completions.py --users 30
```

50 users against a specific assistant:
```bash
python3 testing/load_test_completions.py --users 50 --model lamb_assistant.32
```

Long responses (stress test token generation throughput):
```bash
python3 testing/load_test_completions.py --users 50 \
  --prompt "Write a 20-line poem about the ocean, with vivid imagery and metaphors."
```

Custom backend URL and timeout:
```bash
python3 testing/load_test_completions.py --users 30 \
  --url https://lamb.yourdomain.com --timeout 300
```

## How It Works

1. **Pre-flight check**: Sends a single request to verify the endpoint is reachable and authentication works. Aborts if this fails.
2. **Concurrent burst**: Fires all N requests simultaneously using `asyncio.gather`.
3. **Results**: Prints per-request status as they complete, then a summary with success rate, min/max/mean/median/P90 response times, and standard deviation.

## Output

```
=================================================================
  LAMB Load Test - /v1/chat/completions
=================================================================
  URL:              http://localhost:9099
  Model:            lamb_assistant.58
  Concurrent users: 50
  Request timeout:  180s
=================================================================

Pre-flight check: single request...
  User   0  OK  200    4.75s

Pre-flight OK (4.75s). Starting load test...

  User  39  OK  200    3.46s
  User  40  OK  200    3.57s
  ...
  User  20  OK  200    6.83s

=================================================================
  RESULTS
=================================================================
  Total time:       6.83s
  Requests sent:    50
  Successful:       50
  Failed:           0
  Success rate:     100.0%

  Response times (all):
    Min:              3.46s
    Max:              6.83s
    Mean:             4.76s
    Median:           4.69s
    Std dev:          0.67s
    P90:              5.59s
=================================================================

LOAD TEST PASSED
```

## Exit Codes

- `0` -- 90% or more requests succeeded (PASSED)
- `1` -- Less than 90% succeeded (FAILED)

## Finding Available Models

List published assistants to find valid model IDs:

```bash
curl http://localhost:9099/v1/models -H "Authorization: Bearer 0p3n-w3bu!"
```

## Related Configuration

The completion pipeline uses shared HTTP client pools configured via environment variables in `backend/.env`:

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_REQUEST_TIMEOUT` | Total request timeout for OpenAI calls (seconds) | `120` |
| `LLM_CONNECT_TIMEOUT` | TCP connection timeout (seconds) | `10` |
| `LLM_MAX_CONNECTIONS` | Max concurrent connections per pool | `50` |
| `OLLAMA_REQUEST_TIMEOUT` | Total request timeout for Ollama calls (seconds) | `120` |

See [GitHub Issue #255](https://github.com/Lamb-Project/lamb/issues/255) for background on the connection pooling implementation.
