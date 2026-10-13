# LAMB Playwright Tests

Automated browser tests for the LAMB platform.

## Test Suites

### Automated Test Suite (Playwright Test)

| Test File                                        | Description                                                                             |
| ------------------------------------------------ | --------------------------------------------------------------------------------------- |
| `tests/admin_and_sharing_flow.spec.js`           | Combined admin & sharing flow: user/org CRUD + assistant sharing                        |
| `tests/admin_role_lifecycle.spec.js`              | Admin role lifecycle (issue #245): create admin, verify capabilities, disable, cleanup   |
| `tests/creator_flow.spec.js`                      | Creator flow: Create KB → ingest file → query → create assistant                        |
| `tests/moodle_lti.spec.js`                        | Moodle LTI integration: login via Moodle, click LTI activity and verify redirect to OWI |
| `tests/org_no_admin_and_role_promotion.spec.js`  | Org without admin + role promotion (issue #249): create org without admin, promote/demote members |
| `tests/access_control_and_user_dashboard.spec.js` | Access control & admin user dashboard: read-only view, owner full access, profile API validation |
| `tests/workshop_ui.spec.js`                       | **Student workshop UI, route-mocked** — no stack needed (track A)                        |
| `tests/workshop_student_journey.spec.js`          | **Student workshop journey** against a live stack + real model (track B)                 |

### Workshop tests (two tracks)

The workshop has two independent e2e tracks, because a single real-model
journey would be a test nobody runs:

**Track A — the PR gate** (`workshop_ui.spec.js`). Every backend call is
fulfilled with `page.route`, so it needs no model, no KB server and no seeded
activity. It asserts what unit tests cannot see: the workshop shell renders no
Creator navigation, the observation panel is present from step 2 (before any
chat), the language chain (LMS `?lang=` → switcher) works, and the
knowledge-base A/B switch changes what the page shows.

```bash
cd testing/playwright
npm install && npx playwright install chromium
# with the SPA dev server running (cd frontend/svelte-app && npm run dev)
npm run test:workshop:ui
# …or point it at any other SPA URL:
WORKSHOP_UI_BASE_URL=http://127.0.0.1:5173/ npm run test:workshop:ui
```

It runs on every push/PR via `.github/workflows/workshop-ui.yml` (together with
the backend workshop pytest suite and the frontend vitest suite).

**Track B — before a release** (`workshop_student_journey.spec.js`). Walks the
real lesson: launch → consent → assistant → document → retrieval → tools →
chat → reflection → submit → feedback. It needs the full stack *and* a working
LLM, so it is gated behind an env var and only runs on demand
(`.github/workflows/workshop-e2e.yml`).

```bash
# 1. start the stack (any compose file) and seed a workshop activity:
docker compose -f docker-compose.next.yaml exec lamb \
  python tests/mvp_smoke.py --seed-only     # prints the wizard URL

# 2. walk it in a browser:
cd testing/playwright
WORKSHOP_E2E=1 WORKSHOP_URL='http://localhost:9099/m/workshop/12?token=…' \
  npm run test:workshop
```

Without `WORKSHOP_E2E=1` and `WORKSHOP_URL`, the spec skips itself with an
explanatory message instead of failing.

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
