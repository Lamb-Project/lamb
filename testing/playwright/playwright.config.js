// @ts-check
require('dotenv').config({ quiet: true }) 

const { defineConfig } = require('@playwright/test');

const baseURL = process.env.BASE_URL || 'http://localhost:9099/';

module.exports = defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: process.env.CI ? 1 : undefined,
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
