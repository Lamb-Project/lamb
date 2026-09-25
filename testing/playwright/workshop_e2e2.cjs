// Focused re-check: correct step-button count + user bubble, then screenshot post-chat.
const { chromium } = require('playwright');

(async () => {
  const URL = process.argv[2];
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));
  let pass = 0, fail = 0;
  const check = (l, c, d = '') => { const ok = !!c; ok ? pass++ : fail++; console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${l}${d ? ' :: ' + d : ''}`); };

  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);

  console.log('\n== wizard step buttons (scoped) ==');
  const stepBtns = await page.locator('nav.flex.gap-2 button').count();
  check('exactly 5 wizard steps', stepBtns === 5, `count=${stepBtns}`);

  console.log('\n== build assistant via step 1, then chat ==');
  await page.fill('#ws-instructions', 'You are a helpful tutor that explains fractions step by step.');
  await page.click('nav.flex.gap-2 button:has-text("Next")');
  await page.waitForTimeout(3000);
  const active = await page.locator('nav.flex.gap-2 button.bg-blue-600').textContent().catch(() => '');
  check('step advanced to 2', String(active).includes('2'), `active="${active}"`);
  check('no backend error', !(await page.textContent('body')).includes('check the backend is running'));

  await page.click('nav.flex.gap-2 button:has-text("5.")');
  await page.waitForTimeout(500);
  await page.fill('input[placeholder*="Ask your assistant"]', 'What is 1/2 + 1/4? Use the calculator.');
  await page.click('button:has-text("Send")');
  await page.waitForTimeout(12000);

  console.log('\n== after chat ==');
  const userBubbles = await page.locator('div.bg-blue-600').count();
  check('user bubble rendered', userBubbles >= 1, `count=${userBubbles}`);
  const assistantBubbles = await page.locator('div.bg-gray-100').count();
  check('assistant reply bubble rendered', assistantBubbles >= 1, `count=${assistantBubbles}`);
  const obsPanels = await page.locator('h4:has-text("System instructions")').count();
  check('observability system-instructions shown', obsPanels >= 1, `count=${obsPanels}`);
  const toolTimeline = await page.locator('h4:has-text("Tool calls")').count();
  check('tool timeline header shown', toolTimeline >= 1, `count=${toolTimeline}`);
  // Capture the reply text
  const reply = await page.locator('div.bg-gray-100').first().textContent().catch(() => '');
  console.log('   reply text:', (reply || '').slice(0, 140));

  const notable = consoleErrors.filter((e) => !/favicon|LAMB_CONFIG|i18n|Net::ERR|Download the React|DevTools|Source map/.test(e));
  console.log('\n== console errors ==', notable.length ? '\n' + notable.join('\n') : 'none');

  await page.screenshot({ path: process.argv[3] || 'workshop_after_chat.png', fullPage: false });
  await browser.close();
  console.log(`\n==== RESULT: ${pass} passed, ${fail} failed ====`);
  process.exit(fail > 0 ? 1 : 0);
})().catch((e) => { console.error('FATAL', e); process.exit(2); });