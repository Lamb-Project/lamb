// @ts-check
require('dotenv').config({ quiet: true }) 

const { defineConfig } = require('@playwright/test');

const baseURL = process.env.BASE_URL || 'http://localhost:9099/';

module.exports = defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  // The specs share LAMB DB state (libraries, Knowledge Stores), so running
  // them across multiple workers causes resource-count assertions to flap
  // when one spec's afterAll runs while another spec's beforeAll is still
  // snapshotting counts. Force a single worker so specs run end-to-end
  // serially -- matches CI behavior and is the only safe mode for these
  // integration tests.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [
        ['list'],
        ['junit', { outputFile: 'test-results/junit.xml' }],
        ['html', { open: 'never' }]
      ]
    : [['list'], ['html']],
  use: {
    baseURL,
    headless: !!process.env.CI,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    storageState: '.auth/state.json'
  },
  globalSetup: require.resolve('./global-setup')
});
