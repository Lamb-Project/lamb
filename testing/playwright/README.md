# LAMB Playwright Tests

Automated browser tests for the LAMB platform.

## Test Suites

### Automated Test Suite (Playwright Test)

| Test File | Description |
|-----------|-------------|
| `tests/admin_flow.spec.js` | Admin operations: Create user, create org, disable user, delete org |
| `tests/creator_flow.spec.js` | Creator flow: Create KB → ingest file → query → create assistant |
| `tests/assistant_sharing_flow.spec.js` | **NEW** Assistant sharing: Create users/org → share assistant → verify access |

See `tests/ASSISTANT_SHARING_FLOW.md` for detailed test documentation.

Run with:

```bash
npm test          # Run all tests
npm run test:ui   # Interactive mode
npm run report    # View HTML report
```


Remember to install dependencies first:

```bash
npm install
npx playwright install
# you might need to install some dependencies for Playwright browsers:
npx playwright install-deps
```