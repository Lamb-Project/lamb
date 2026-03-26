# LAMB CLI E2E Tests

End-to-end tests that validate LAMB workflows through the `lamb` CLI tool,
mirroring the Playwright browser tests in `testing/playwright/`.

## Prerequisites

1. LAMB backend running on port 9099
2. `lamb` CLI installed: `pip install -e /path/to/lamb-cli`
3. An admin account on the running instance

## Setup

```bash
cd testing/cli
pip install -r requirements.txt
cp .env.sample .env   # edit with your credentials
```

## Running

```bash
pytest tests/ -v -x              # all tests, stop on first failure
pytest tests/ -v -x -m "not slow"  # skip ingestion-wait tests
pytest tests/test_01_auth.py -v  # single file
pytest tests/ -v -x -k "test_login"  # single test by name
```

## How it works

- Each test invokes the real `lamb` binary via `subprocess.run()`
- Auth is done once per session via HTTP POST, then the JWT is passed
  to every subprocess call through the `LAMB_TOKEN` env var
- All commands use `--output json` for machine-parseable assertions
- Tests run sequentially; `-x` stops on first failure
- Test data is tagged with a session timestamp to avoid collisions
