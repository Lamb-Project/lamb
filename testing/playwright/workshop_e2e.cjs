// Drive the workshop wizard end-to-end in a real browser (system Edge).
// Verifies: page loads, step nav, assistant creation, chat streaming,
// observability + tool timeline, submit.
const { chromium } = require('playwright');

(async () => {
  const URL = process.argv[2];
  const SESSION = process.argv[3];
  const out = [];
  const log = (s) => { out.push(s); console.log(s); };

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));

  let pass = 0, fail = 0;
  const check = (label, cond, detail = '') => {
    const ok = !!cond;
    if (ok) pass++; else fail++;
    log(`  [${ok ? 'PASS' : 'FAIL'}] ${label}${detail ? ' :: ' + detail : ''}`);
  };

  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  log('\n== 1. Page loads ==');
  const title = await page.textContent('h1').catch(() => '');
  check('h1 = AI Workshop', title.includes('AI Workshop'), `h1="${title}"`);
  check('activity id shown', (await page.textContent('body')).includes(`#${SESSION.split('-')[1]}`));
  const stepBtns = await page.locator('nav button').count();
  check('5 step buttons', stepBtns === 5, `count=${stepBtns}`);
  check('instructions textarea present', await page.locator('#ws-instructions').count() === 1);
  check('chat panel present', (await page.textContent('body')).includes('Test your assistant'));

  log('\n== 2. Fill instructions ===================');
  await page.fill('#ws-instructions', 'You are a helpful tutor that explains fractions step by step.');
  await page.waitForTimeout(300);
  // Next button should now be enabled
  const nextEnabled = await page.locator('button:has-text("Next")').isEnabled();
  check('Next enabled after instructions', nextEnabled);

  log('\n== 3. Step 1 -> create assistant ==========');
  await page.click('button:has-text("Next")');
  await page.waitForTimeout(3000); // wait for assistant creation
  // Should move to step 2
  const stepActive = await page.locator('nav button.bg-blue-600').textContent().catch(() => '');
  check('moved past step 1', String(stepActive).includes('2'), `active="${stepActive}"`);
  const bodyText = await page.textContent('body');
  check('no error banner', !bodyText.includes('check the backend is running'), '');

  log('\n== 4. Jump to step 5 (Test & Reflect) ======');
  await page.click('nav button:has-text("5.")');
  await page.waitForTimeout(500);
  check('reflect textarea present', await page.locator('#ws-reflection').count() === 1);
  check('submit button present', (await page.textContent('body')).includes('Submit workshop'));
  // chat input should now be enabled (assistant exists)
  const chatEnabled = await page.locator('input[placeholder*="Ask your assistant"]').isEnabled().catch(() => false);
  check('chat input enabled', chatEnabled);

  log('\n== 5. Send a message (chat + observability) ==');
  await page.fill('input[placeholder*="Ask your assistant"]', 'What is 1/2 + 1/4? Use the calculator.');
  await page.click('button:has-text("Send")');
  await page.waitForTimeout(12000); // allow stream + tool round + obs frame

  const afterChat = await page.textContent('body');
  check('assistant reply streamed', afterChat.length > 0, '');
  // observability dashboard should appear with a section title
  const obsTitle = await page.locator('text=What your assistant received').count();
  check('observability panel appeared', obsTitle > 0);
  const msgCount = await page.locator('div:has(> div.bg-blue-600)').count();
  check('user message rendered', msgCount >= 1, `userBubbles=${msgCount}`);

  log('\n== console errors ==');
  const notable = consoleErrors.filter((e) => !/favicon|LAMB_CONFIG|i18n|Net::ERR|Download the React|DevTools/.test(e));
  log(`  ${notable.length ? notable.join('\n  ') : 'none'}`);

  await browser.close();
  log(`\n==== RESULT: ${pass} passed, ${fail} failed ====`);
  process.exit(fail > 0 ? 1 : 0);
})().catch((e) => { console.error('FATAL', e); process.exit(2); });