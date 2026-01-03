const { chromium } = require('playwright');

(async () => {
  console.log("🔍 Debugging Assistant Form...");
  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto('http://localhost:5173');
    
    // Login
    await page.fill('input[name="email"], input[type="email"]', 'admin@owi.com');
    await page.fill('input[name="password"], input[type="password"]', 'admin');
    await page.click('button:has-text("Login")');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Go to assistant creation
    await page.goto('http://localhost:5173/assistants?view=create');
    await page.waitForTimeout(2000);
    
    console.log("📸 Taking screenshot...");
    await page.screenshot({ path: 'assistant-form-debug.png', fullPage: true });
    console.log('✅ Screenshot saved as assistant-form-debug.png');
    
    // Check for checkboxes
    const checkboxes = await page.locator('input[type="checkbox"]').all();
    console.log('📋 Found', checkboxes.length, 'checkboxes');
    
    for (let i = 0; i < checkboxes.length; i++) {
      try {
        const checkbox = checkboxes[i];
        const label = await checkbox.locator('xpath=ancestor::label | xpath=following-sibling::*[1]').first().textContent();
        console.log('  Checkbox', i, ':', (label || '').trim().substring(0, 50));
      } catch (e) {
        console.log('  Checkbox', i, ': unable to get label');
      }
    }
    
    // Check for selects
    const selects = await page.locator('select').all();
    console.log('📋 Found', selects.length, 'select elements');
    
    for (let i = 0; i < selects.length; i++) {
      try {
        const select = selects[i];
        const name = await select.getAttribute('name') || '';
        const id = await select.getAttribute('id') || '';
        console.log('  Select', i, ': name="' + name + '" id="' + id + '"');
      } catch (e) {
        console.log('  Select', i, ': error getting attributes');
      }
    }
    
    // Check for any text containing "RAG" or "rubric"
    const ragElements = await page.locator('*:has-text("RAG"), *:has-text("rubric")').all();
    console.log('📋 Found', ragElements.length, 'elements mentioning RAG or rubric');
    
    for (let i = 0; i < Math.min(ragElements.length, 5); i++) {
      try {
        const element = ragElements[i];
        const text = await element.textContent();
        const tagName = await element.evaluate(el => el.tagName);
        console.log('  Element', i, ':', tagName, '-', (text || '').trim().substring(0, 100));
      } catch (e) {
        console.log('  Element', i, ': error getting info');
      }
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  } finally {
    await browser.close();
  }
})();
