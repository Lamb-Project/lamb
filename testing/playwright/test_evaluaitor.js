const { chromium } = require('playwright');

(async () => {
  console.log('=== Testing Evaluaitor Page ===\n');

  const browser = await chromium.launch({ 
    headless: false,  // Show the browser so we can see what's happening
    slowMo: 500       // Slow down operations for visibility
  });
  
  const context = await browser.newContext();
  const page = await context.newPage();

  // Enable console logging from the page
  page.on('console', msg => console.log('BROWSER:', msg.text()));
  
  // Log all network requests
  page.on('request', request => {
    if (request.url().includes('rubrics') || request.url().includes('creator')) {
      console.log('→ REQUEST:', request.method(), request.url());
      const headers = request.headers();
      if (headers['authorization']) {
        console.log('  Authorization:', headers['authorization'].substring(0, 30) + '...');
      } else {
        console.log('  ⚠️  NO AUTHORIZATION HEADER!');
      }
    }
  });

  // Log all network responses
  page.on('response', response => {
    if (response.url().includes('rubrics') || response.url().includes('creator')) {
      console.log('← RESPONSE:', response.status(), response.url());
    }
  });

  try {
    // Step 1: Go to login page
    console.log('\n1. Navigating to login page...');
    await page.goto('http://localhost:9099/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    // Check if already logged in
    const isLoggedIn = await page.evaluate(() => {
      return !!localStorage.getItem('userToken');
    });

    if (isLoggedIn) {
      console.log('✅ Already logged in!');
      const token = await page.evaluate(() => localStorage.getItem('userToken'));
      console.log('Token:', token.substring(0, 30) + '...');
    } else {
      // Step 2: Login
      console.log('\n2. Logging in as admin@owi.com...');
      await page.fill('input[type="email"], input[name="email"]', 'admin@owi.com');
      await page.fill('input[type="password"], input[name="password"]', 'admin');
      await page.click('button[type="submit"]');
      
      // Wait for navigation after login
      await page.waitForTimeout(2000);
      
      // Verify login
      const token = await page.evaluate(() => localStorage.getItem('userToken'));
      if (token) {
        console.log('✅ Login successful!');
        console.log('Token:', token.substring(0, 30) + '...');
      } else {
        console.log('❌ Login failed - no token in localStorage');
        throw new Error('Login failed');
      }
    }

    // Step 3: Navigate to Evaluaitor
    console.log('\n3. Navigating to Evaluaitor page...');
    await page.goto('http://localhost:9099/evaluaitor?view=create', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // Check the page content
    const pageTitle = await page.title();
    console.log('Page title:', pageTitle);

    // Check if we're on the evaluaitor page
    const url = page.url();
    console.log('Current URL:', url);

    // Check for error messages in the page
    const errorMessages = await page.evaluate(() => {
      const errors = [];
      // Check for visible error text
      const elements = document.querySelectorAll('*');
      elements.forEach(el => {
        const text = el.textContent || '';
        if (text.includes('401') || text.includes('Authorization') || text.includes('error')) {
          errors.push(text.trim().substring(0, 100));
        }
      });
      return [...new Set(errors)];
    });

    if (errorMessages.length > 0) {
      console.log('\n⚠️  Found error messages on page:');
      errorMessages.forEach(msg => console.log('  -', msg));
    }

    // Check localStorage token
    const currentToken = await page.evaluate(() => localStorage.getItem('userToken'));
    console.log('\n4. Token in localStorage:', currentToken ? (currentToken.substring(0, 30) + '...') : 'NULL');

    // Check the userStore state
    const userState = await page.evaluate(() => {
      return {
        hasUserStore: !!window.userStore,
        isLoggedIn: window.userStore?.isLoggedIn || false,
        userData: window.userStore?.user || null
      };
    });
    console.log('\n5. User store state:', JSON.stringify(userState, null, 2));

    // Wait a bit to see the page
    console.log('\n6. Waiting 5 seconds to observe the page...');
    await page.waitForTimeout(5000);

    // Take a screenshot
    await page.screenshot({ path: '/opt/lamb/testing/playwright/evaluaitor-test-screenshot.png' });
    console.log('Screenshot saved to: testing/playwright/evaluaitor-test-screenshot.png');

    console.log('\n✅ Test completed successfully');

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    await page.screenshot({ path: '/opt/lamb/testing/playwright/evaluaitor-test-error.png' });
    console.log('Error screenshot saved to: testing/playwright/evaluaitor-test-error.png');
  } finally {
    await browser.close();
  }
})();


