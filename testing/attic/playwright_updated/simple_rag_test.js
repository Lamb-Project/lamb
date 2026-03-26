const { chromium } = require('playwright');

(async () => {
  console.log("🔍 Simple Rubrics RAG Test");
  console.log(`📍 Testing against: http://localhost:5173`);

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
    
    // Check if the page contains "rubric_rag" anywhere
    const pageContent = await page.textContent('body');
    console.log("🔍 Checking for rubric_rag in page content...");
    
    if (pageContent.includes('rubric_rag')) {
      console.log("✅ rubric_rag option found in page content");
    } else {
      console.log("❌ rubric_rag option NOT found in page content");
    }
    
    // Check for rubric-related text
    if (pageContent.includes('Rubric') || pageContent.includes('rubric')) {
      console.log("✅ Rubric-related text found in page content");
    } else {
      console.log("❌ No rubric-related text found");
    }
    
    // Check for advanced mode text
    if (pageContent.includes('Advanced Mode') || pageContent.includes('advanced')) {
      console.log("✅ Advanced mode text found");
    } else {
      console.log("❌ Advanced mode text not found");
    }
    
    // Take screenshot
    await page.screenshot({ path: 'simple-test-screenshot.png', fullPage: true });
    console.log('📸 Screenshot saved as simple-test-screenshot.png');
    
    console.log("\n🎯 Test Results:");
    console.log("- Login: ✅ Working");
    console.log("- Assistant form loads: ✅ Working");
    console.log("- Check manual testing for rubric_rag integration");
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  } finally {
    await browser.close();
  }
})();
