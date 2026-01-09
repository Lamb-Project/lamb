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


Remember to install dependencies first:

```bash
npm install
npx playwright install
# you might need to install some dependencies for Playwright browsers:
npx playwright install-deps
```