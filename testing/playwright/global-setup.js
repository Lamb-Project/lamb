const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

module.exports = async (config) => {
  const baseURL = config.projects[0]?.use?.baseURL || 'http://localhost:9099/';
  const email = process.env.LOGIN_EMAIL || 'admin@owi.com';
  const password = process.env.LOGIN_PASSWORD || 'admin';

  const authDir = path.join(__dirname, '.auth');
  const statePath = path.join(authDir, 'state.json');

  fs.mkdirSync(authDir, { recursive: true });

  const browser = await chromium.launch({ headless: !!process.env.CI });
  const canReuseState = fs.existsSync(statePath) && !process.env.FORCE_RELOGIN;
  const context = await browser.newContext(
    canReuseState ? { storageState: statePath } : {}
  );
  const page = await context.newPage();

  await page.goto(baseURL);
  await page.waitForLoadState('domcontentloaded');

  // If already authenticated in some environments, just persist storage.
  let existingToken = await page.evaluate(() => localStorage.getItem('userToken'));

  // A stored token can outlive the server-side session or signing key. Verify
  // it before reusing the state so tests do not silently land on the login page.
  if (existingToken) {
    const meUrl = new URL('/creator/me', baseURL).toString();
    const validationResponse = await page.request.get(meUrl, {
      headers: { Authorization: `Bearer ${existingToken}` }
    });

    if (!validationResponse.ok()) {
      await page.evaluate(() => localStorage.removeItem('userToken'));
      existingToken = null;
    }
  }

  if (!existingToken) {
    // Wait for the email input to exist in the DOM.
    await page.waitForSelector('#email', { timeout: 30_000 });

    // Wait for full load + network idle so Vite has finished streaming all JS
    // chunks and SvelteKit hydration has wired up the form's onsubmit handler.
    // Without this, clicking on slower machines fires a native form submission
    // (URL becomes /?email=…&password=…) instead of the XHR handler.
    await page.waitForLoadState('load');
    await page.waitForLoadState('networkidle');

    // Double-check that SvelteKit has hydrated by polling for its runtime
    // marker. This is a zero-cost guard on fast machines (already true by the
    // time networkidle resolves) and a reliable gate on slow ones.
    // NOTE: the marker name differs by build mode — dev exposes
    // `__sveltekit_dev`, SvelteKit 2 production builds expose a hashed name
    // like `__sveltekit_1u9jzfb` (no stable global), and older versions used
    // plain `__sveltekit`. Match any property whose name starts with the prefix
    // so the gate works against both dev and production-served pages.
    await page.waitForFunction(
      () => Object.keys(window).some((k) => k.startsWith('__sveltekit')),
      { timeout: 30_000 }
    );

    await page.fill('#email', email);
    await page.fill('#password', password);

    // Click the submit button (selector is intentionally narrow) and
    // concurrently wait for the POST /creator/login XHR response.  This is
    // deterministic: we know auth succeeded the moment the server replies,
    // with no blind sleep required.
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/creator/login') && r.request().method() === 'POST',
        { timeout: 30_000 }
      ),
      page.click('form > button')
    ]);

    // Poll until the SPA has stored the token in localStorage.  waitForFunction
    // resolves as soon as the predicate returns truthy — no fixed wait.
    await page.waitForFunction(() => !!localStorage.getItem('userToken'), { timeout: 15_000 });
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
