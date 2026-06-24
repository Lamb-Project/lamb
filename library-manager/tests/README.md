# Library Manager — Test Suite

A three-tier suite (**unit / integration / e2e**) with an enforced
**95% line + branch** coverage gate. The goal: when this suite is green, a
change to the Library Manager is known-good.

## The tier contract

| Tier | Mechanism | Proves | Speed |
|------|-----------|--------|-------|
| **unit** | Direct module calls. No FastAPI app, no HTTP. | Pure logic: config, auth dependency, DB engine setup, ORM constraints, schemas, every import plugin's internals, the plugin/capability registries, and the service layer. | fast |
| **integration** | In-process ASGI (`httpx.ASGITransport`) against the **real** SQLite DB and the **real** background worker. | Routers, request validation, the async import pipeline end-to-end, worker concurrency/timeout/recovery, lifespan, route ordering. | medium |
| **e2e** | **Real HTTP** to a `uvicorn` subprocess on loopback (+ one Docker smoke test of the shipped image). | The real process boots and serves; crash recovery across restart; the single-instance file lock; graceful shutdown; multi-tenant isolation; the full HTTP error-code matrix. | slow |

### The one rule: mock only at the boundary

Tests run against real systems — real SQLite, the real worker, the real
filesystem, the real plugin code. The **only** things mocked are the
third-party SDKs the plugins call out to (`markitdown`, `firecrawl`, PyMuPDF
`fitz`, `openai`), and they are patched at their exact import boundary
(`tests/_fakes.py`) so the plugin's own logic — SSRF guards, page splitting,
image extraction, error humanisation — still executes. YouTube transcripts
use the offline cassette cache in `tests/.yt_cache/`. Nothing in the unit or
integration tiers touches the network.

## Layout

```
tests/
  conftest.py        # env + sys.path + session DB init + auto-tag by directory
  _helpers.py        # AUTH_HEADERS, poll_until_ready (async+sync), payload factories
  _fakes.py          # boundary doubles: markitdown / firecrawl / fitz / openai
  youtube_cache.py   # offline YouTube transcript cache installer
  .yt_cache/         # cached transcripts
  unit/              # tier 1  (+ conftest: tmp_storage, db_session, registry reset)
  integration/       # tier 2  (+ conftest: client, client_no_worker, library, org_id)
  e2e/               # tier 3  (+ conftest, _server.py, _docker.py)
```

Tier markers are applied **automatically** by directory
(`pytest_collection_modifyitems` in the root `conftest.py`) — no per-test
decoration. `pytest -m unit` just works.

## Running

```bash
# everything, with the 95% combined gate
./scripts/run_tests.sh

# a single tier
pytest tests/unit/ -q
pytest tests/integration/ -q
pytest tests/e2e/ -q              # Docker smoke test skips cleanly if no daemon

# by marker
pytest -m unit -q
pytest -m "not slow" -q           # skip subprocess/Docker tiers

# coverage only (in-process tiers)
pytest tests/unit/ tests/integration/ --cov=backend --cov-branch \
       --cov-report=term-missing --cov-fail-under=95
```

## Coverage scope

The 95% line+branch gate is computed over `unit/` + `integration/` — the
tiers that exercise `backend/` in-process. The e2e tier provides behavioural
assurance (a real process really boots, recovers, and locks), not a coverage
number: a subprocess/container can't be instrumented by the parent
`pytest-cov`. A small, audited set of genuinely unreachable defensive lines
(optional-dependency `ImportError` guards, `if __name__ == "__main__"`) carry
`# pragma: no cover`. `backend/migrations/` is excluded — schema DDL is
covered by the migration round-trip test, not line coverage.
