const { test, expect } = require('@playwright/test');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env'), quiet: true });
const { ensureMoodleAuth } = require('./utils/moodle_pre_auth');

const MOODLE_URL = process.env.MOODLE_URL;
const COURSE_ID = process.env.COURSE_ID || '';
const LTI_ACTIVITY_ID = process.env.LTI_ACTIVITY_ID || '';
const EXPECTED_REDIRECT_HOST = 'owi-dev.lamb-project.org';
const EXPECTED_TEXT = 'LAMB:1_nuevo_asistente';

test.describe.serial('Moodle LTI integration', () => {
  test.beforeAll(async () => {
    await ensureMoodleAuth();
  });

  test('Clicking LTI activity redirects to OWI and shows assistant', async ({ browser }) => {
    if (!MOODLE_URL || !LTI_ACTIVITY_ID) {
      throw new Error('MOODLE_URL and LTI_ACTIVITY_ID must be set in tests/.env');
    }

    const context = await browser.newContext({ storageState: path.join(__dirname, '.auth', 'moodle-state.json') });
    const page = await context.newPage();

    // Visit the course page and find the activity link
    const courseUrl = COURSE_ID ? `${MOODLE_URL}course/view.php?id=${COURSE_ID}` : `${MOODLE_URL}`;
    await page.goto(courseUrl);
    await page.waitForLoadState('networkidle');

    const activitySelector = `a[href*="mod/lti/view.php?id=${LTI_ACTIVITY_ID}"]`;
    await page.waitForSelector(activitySelector, { timeout: 30_000 });

    // Click the activity link and handle possible popup or navigation
    let newPage = null;
    const [popup] = await Promise.all([
      context.waitForEvent('page').catch(() => null),
      page.click(activitySelector)
    ]);

    if (popup) {
      newPage = popup;
      await newPage.waitForLoadState('networkidle');
    } else {
      // Link navigated in same tab
      await page.waitForLoadState('networkidle');
      newPage = page;
    }

    // Wait for redirect to OWI host
    await newPage.waitForFunction((host) => window.location.hostname.includes(host), EXPECTED_REDIRECT_HOST, { timeout: 30_000 }).catch(() => {});

    const url = newPage.url();
    expect(url).toContain(EXPECTED_REDIRECT_HOST);

    // Check for the assistant div text
    const assistantLocator = newPage.locator(`div:has-text("${EXPECTED_TEXT}")`).first();
    await expect(assistantLocator).toBeVisible({ timeout: 30_000 });

    await context.close();
  });
});
