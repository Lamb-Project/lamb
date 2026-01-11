# LAMB Playwright Tests

Automated browser tests for the LAMB platform.

## Test Suites

### Automated Test Suite (Playwright Test)

| Test File                              | Description                                                                             |
| -------------------------------------- | --------------------------------------------------------------------------------------- |
| `tests/admin_and_sharing_flow.spec.js` | Combined admin & sharing flow: user/org CRUD + assistant sharing                        |
| `tests/creator_flow.spec.js`           | Creator flow: Create KB → ingest file → query → create assistant                        |
| `tests/moodle_lti.spec.js`             | Moodle LTI integration: login via Moodle, click LTI activity and verify redirect to OWI |

### Moodle LTI test

The `tests/moodle_lti.spec.js` file checks the LTI activity flow by pre-authenticating a Moodle user (saved to `.auth/moodle-state.json`), visiting the course/activity and ensuring the LTI launch redirects to the expected OWI host and shows the assistant text.

Required environment variables in `tests/.env`:

- `MOODLE_URL` (e.g. `https://moodle.ikasten.io/`)
- `MOODLE_LOGIN` and `MOODLE_PASSWORD`
- `LTI_ACTIVITY_ID` (e.g. `15`)
- `COURSE_ID` (optional, used to find the activity on the course page)

Run the test directly:

```bash
# from repository root
cd testing/playwright
npx playwright test tests/moodle_lti.spec.js -g "Clicking LTI activity redirects to OWI and shows assistant"
```

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
