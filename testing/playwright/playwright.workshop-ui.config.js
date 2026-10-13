// @ts-check
/**
 * Track A config — the route-mocked student workshop UI spec (decision C21).
 *
 * Deliberately standalone: no `globalSetup`, no stored auth state and no
 * backend. The spec fulfils every workshop API call itself, so this runs on any
 * pull request (and locally against the Vite dev server on :5173).
 *
 * Point it somewhere else with `WORKSHOP_UI_BASE_URL`.
 */
const { defineConfig } = require('@playwright/test');

const baseURL = process.env.WORKSHOP_UI_BASE_URL || 'http://localhost:5173/';

module.exports = defineConfig({
  testDir: './tests',
  testMatch: /workshop_ui\.spec\.js/,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI
    ? [['list'], ['junit', { outputFile: 'test-results/workshop-ui.xml' }]]
    : [['list']],
  use: {
    baseURL,
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  }
});
