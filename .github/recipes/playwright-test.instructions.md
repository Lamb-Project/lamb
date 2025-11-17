---
description: Playwright test creation workflow using local browser tooling
---

# Playwright Test Authoring Instructions

## Purpose
Use this guide when you need to capture an interaction in the web app and turn it into an automated Playwright test stored in `testing/playwright/`.

## Core Workflow
1. Launch (or ensure) the application is running locally (usually via docker-compose or the dev server) so that `http://localhost/URL_TO_TEST` is reachable.
2. Use Playwright MCP tools to browse to:
   `http://localhost/URL_TO_TEST`
3. Perform the action sequence: `DO_WHATEVER_ACTION`.
4. While recording take note of your actions to save them as a script
5. Save the generated script as: `testing/playwright/TEST.js` (replace `TEST` with a descriptive lowercase kebab-case name, e.g. `delete-kb-file.js`).
6. Normalize & refactor:
   - Remove unnecessary waits; rely on auto-waiting.
   - Add explicit assertions for critical UI state changes.
   - Factor shared helpers (if any) into `testing/playwright/utils/` (create folder if needed).
7. Run the test headless to confirm it passes.
