# LAMB Playwright Tests

Automated browser tests for the LAMB platform.

## Test Suites

### Automated Test Suite (Playwright Test)

| Test File | Description |
|-----------|-------------|
| `tests/admin_and_sharing_flow.spec.js` | Combined admin & sharing flow: user/org CRUD + assistant sharing |
| `tests/creator_flow.spec.js` | Creator flow: Create KB → ingest file → query → create assistant |

The `admin_and_sharing_flow.spec.js` includes 14 tests covering:
- **Part 1 (Admin)**: Create user, create org, disable user, delete org
- **Part 2 (Sharing)**: Create users/org, create assistant, share, verify access, cleanup

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