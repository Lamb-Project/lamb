const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

module.exports = async (config) => {
  const baseURL = config.projects[0]?.use?.baseURL || 'http://localhost:5173/';
  const email = process.env.LOGIN_EMAIL || 'admin@owi.com';
  const password = process.env.LOGIN_PASSWORD || 'admin';

  const authDir = path.join(__dirname, '.auth');
  const statePath = path.join(authDir, 'state.json');

  fs.mkdirSync(authDir, { recursive: true });

  // If a prior state exists, reuse it. This keeps local dev fast.
  if (fs.existsSync(statePath) && !process.env.FORCE_RELOGIN) {
    return;
  }

  const browser = await chromium.launch({ headless: !!process.env.CI });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(baseURL);
  await page.waitForLoadState('domcontentloaded');

  // If already authenticated in some environments, just persist storage.
  const existingToken = await page.evaluate(() => localStorage.getItem('userToken'));
  if (!existingToken) {
    await page.waitForSelector('#email', { timeout: 30_000 });
    await page.fill('#email', email);
    await page.fill('#password', password);

    // Matches your current scripts: login is "form > button".
    await Promise.all([
      page.waitForLoadState('networkidle').catch(() => {}),
      page.click('form > button')
    ]);

    // Give time for localStorage token to be set.
    await page.waitForTimeout(1500);
  }

  const tokenAfter = await page.evaluate(() => localStorage.getItem('userToken'));
  if (!tokenAfter) {
    await browser.close();
    throw new Error(
      'Login did not produce localStorage.userToken. Check UI selectors or credentials (LOGIN_EMAIL/LOGIN_PASSWORD).'
    );
  }

  await context.storageState({ path: statePath });
  await browser.close();
};
