// Robust interactive E2E: selectors based on visible text (not fragile class chaining).
const { chromium } = require('playwright');

(async () => {
  const URL = process.argv[2];
  const snapshot = process.argv[3];
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));
  let pass = 0, fail = 0;
  const check = (l, c, d = '') => { const ok = !!c; ok ? pass++ : fail++; console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${l}${d ? ' :: ' + d : ''}`); };

  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);

  console.log('\n== wizard step buttons (by text) ==');
  const stepBtns = await page.getByRole('button', { name: /^\d\.\s/ }).count();
  check('exactly 5 wizard steps', stepBtns === 5, `count=${stepBtns}`);

  console.log('\n== build assistant via step 1, then chat ==');
  await page.fill('#ws-instructions', 'You are a helpful tutor that explains fractions step by step.');
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: /^Next/ }).click();
  await page.waitForTimeout(3500);
  check('no backend error', !(await page.textContent('body')).includes('check the backend is running'));
  const active2 = await page.locator('nav button[class*="bg-blue-600"]').textContent().catch(() => '');
  check('step advanced to 2', String(active2).includes('2'), `active="${active2}"`);

  await page.getByRole('button', { name: /^5\./ }).click();
  await page.waitForTimeout(500);
  await page.fill('input[placeholder*="Ask your assistant"]', 'What is 1/2 + 1/4? Use the calculator.');
  await page.getByRole('button', { name: /^Send/ }).click();
  await page.waitForTimeout(13000);

  console.log('\n== after chat ==');
  check('user bubble rendered', (await page.locator('div.bg-blue-600').count()) >= 1);
  const asstBubbles = await page.locator('div.bg-gray-100').count();
  check('assistant reply bubble rendered', asstBubbles >= 1, `count=${asstBubbles}`);
  check('observability system-instructions shown', (await page.locator('h4:has-text("System instructions")').count()) >= 1);
  check('tool timeline header shown', (await page.locator('h4:has-text("Tool calls")').count()) >= 1);
  const reply = await page.locator('div.bg-gray-100').first().textContent().catch(() => '');
  console.log('   reply text:', (reply || '').slice(0, 160));

  const notable = consoleErrors.filter((e) => !/favicon|LAMB_CONFIG|i18n|Net::ERR|Download the React|DevTools|Source map/.test(e));
  console.log('\n== console errors ==', notable.length ? '\n' + notable.join('\n') : 'none');

  if (snapshot) await page.screenshot({ path: snapshot, fullPage: false });
  await browser.close();
  console.log(`\n==== RESULT: ${pass} passed, ${fail} failed ====`);
  process.exit(fail > 0 ? 1 : 0);
})().catch((e) => { console.error('FATAL', e); process.exit(2); });