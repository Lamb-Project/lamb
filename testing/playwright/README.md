# LAMB Playwright Tests

Automated browser tests for the LAMB platform.

## Test Suites

### Automated Test Suite (Playwright Test)

**Main flow:** `tests/creator_flow.spec.js` - Creates KB → ingests file → queries → creates assistant

Run with:

```bash
npm test          # Run all tests
npm run test:ui   # Interactive mode
npm run report    # View HTML report
```

### End User Feature Tests

Complete test suite for the end_user feature (users who are automatically redirected to Open WebUI).

**Location:** `end_user_tests/`

**Quick Start:**

```bash
cd end_user_tests
./run_end_user_tests.sh
```

See [end_user_tests/README_END_USER_TESTS.md](end_user_tests/README_END_USER_TESTS.md) for detailed documentation.

### Manual Test Scripts

Scripts not yet automated (run individually as needed):

| Test File                | Purpose                        |
| ------------------------ | ------------------------------ |
| `create_org.js`          | Organization creation          |
| `create_user.js`         | User creation                  |
| `config_owui.js`         | Configure OpenWebUI connection |
| `remove_kb.js`           | Test knowledge base deletion   |
| `ingest_video.js`        | Video ingestion testing        |
| `test_url_ingest.js`     | URL ingestion testing          |
| `test_youtube_titles.js` | YouTube title extraction       |
| `test_evaluaitor.js`     | Evaluator/rubric testing       |

## Installation

```bash
npm install
```

## Running Tests

### CI-friendly (Playwright Test runner)

This repo now supports the standard Playwright Test runner with HTML + JUnit reporting.

```bash
cd testing/playwright
npm install

# Uses BASE_URL=http://localhost:5173/ by default
npm test

# View the HTML report locally
npm run report
```

Environment variables:

- `BASE_URL` (default: `http://localhost:5173/`)
- `LOGIN_EMAIL` (default: `admin@owi.com`)
- `LOGIN_PASSWORD` (default: `admin`)
- `FORCE_RELOGIN=1` to regenerate auth state

### Individual Tests

Manual scripts (not yet automated):

```bash
node create_org.js http://localhost:5173
node create_user.js http://localhost:5173
node config_owui.js http://localhost:5173
node remove_kb.js http://localhost:5173
node ingest_video.js http://localhost:5173
node test_url_ingest.js http://localhost:5173
node test_youtube_titles.js http://localhost:5173
node test_evaluaitor.js http://localhost:5173
```

## Requirements

- Node.js
- Playwright
- LAMB backend running (port 9099)
- LAMB frontend running (port 5173)
- Open WebUI running (port 8080)

## Test Data

Admin credentials:

- **Email:** `admin@owi.com`
- **Password:** `admin`

## Documentation

- [End User Tests](end_user_tests/README_END_USER_TESTS.md) - Complete end_user feature testing
- [Main LAMB Docs](../../Documentation/) - Full platform documentation
