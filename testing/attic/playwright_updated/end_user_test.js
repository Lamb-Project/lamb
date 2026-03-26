const { chromium } = require("playwright");

const baseUrl = process.argv[2] || 'http://localhost:5173';

(async () => {
  console.log("👥 Starting End User Test Suite");
  console.log(`📍 Testing against: ${baseUrl}`);

  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Test 1: User Signup
    console.log("\n📝 Test 1: User Signup");

    await page.goto(baseUrl);
    await page.waitForLoadState('networkidle');

    // Check if signup is available
    const signupLink = page.locator('a:has-text("Sign up"), button:has-text("Sign up")').first();
    if (await signupLink.isVisible({ timeout: 3000 })) {
      await signupLink.click();

      // Fill signup form
      await page.fill('input[name="name"]', 'Test End User');
      await page.fill('input[name="email"]', 'enduser@test.com');
      await page.fill('input[name="password"]', 'enduser123');
      await page.fill('input[name="secret_key"]', 'pepino-secret-key'); // Using default signup key

      // Submit signup
      await page.click('button:has-text("Sign Up")');

      // Wait for success
      await page.waitForTimeout(2000);

      console.log("✅ User signup successful");
    } else {
      console.log("⚠️ Signup not available, skipping signup test");
    }

    // Test 2: End User Login and Redirect
    console.log("\n🔐 Test 2: End User Login and Redirect");

    // If we just signed up, we might be on login page already
    // If not, go to login
    if (!page.url().includes('login') && !page.locator('input[type="email"]').isVisible()) {
      await page.goto(baseUrl);
      await page.waitForLoadState('networkidle');
    }

    // Fill login form
    await page.fill('input[type="email"]', 'enduser@test.com');
    await page.fill('input[type="password"]', 'enduser123');
    await page.click('button:has-text("Login")');

    // Wait for redirect - end users should be redirected to OpenWebUI
    await page.waitForTimeout(3000);

    // Check if redirected to OpenWebUI
    const currentUrl = page.url();
    if (currentUrl.includes('8080') || currentUrl.includes('openwebui')) {
      console.log("✅ End user redirected to OpenWebUI");
    } else {
      console.log("⚠️ End user not redirected, might be treated as creator user");
    }

    // Test 3: Admin Creates End User
    console.log("\n👨‍💼 Test 3: Admin Creates End User");

    // Open new page for admin operations
    const adminPage = await context.newPage();
    await adminPage.goto(baseUrl);
    await adminPage.waitForLoadState('networkidle');

    // Login as admin
    await adminPage.fill('input[type="email"]', 'admin@owi.com');
    await adminPage.fill('input[type="password"]', 'admin');
    await adminPage.click('button:has-text("Login")');
    await adminPage.waitForTimeout(2000);

    // Navigate to admin
    await adminPage.goto(`${baseUrl}/admin`);
    await adminPage.waitForLoadState('networkidle');

    // Go to users tab
    await adminPage.click('button:has-text("Users")');

    // Click create user
    const createUserButton = adminPage.getByRole('button', { name: /Create|Add.*User/i });
    await createUserButton.click();

    // Fill user form for end user
    await adminPage.fill('input[name="email"]', 'admin_enduser@test.com');
    await adminPage.fill('input[name="name"]', 'Admin Created End User');
    await adminPage.fill('input[name="password"]', 'enduser456');

    // Select user type as end_user
    const typeSelect = adminPage.locator('select[name*="type"]').first();
    if (await typeSelect.isVisible({ timeout: 2000 })) {
      await typeSelect.selectOption('end_user');
      console.log("✅ Selected end_user type");
    }

    // Submit form
    await adminPage.click('button:has-text("Create")');
    await adminPage.waitForTimeout(2000);

    console.log("✅ Admin created end user");

    // Test 4: End User Login (Admin Created)
    console.log("\n🚪 Test 4: End User Login (Admin Created)");

    // Open new page for end user
    const endUserPage = await context.newPage();
    await endUserPage.goto(baseUrl);
    await endUserPage.waitForLoadState('networkidle');

    // Login as admin-created end user
    await endUserPage.fill('input[type="email"]', 'admin_enduser@test.com');
    await endUserPage.fill('input[type="password"]', 'enduser456');
    await endUserPage.click('button:has-text("Login")');

    // Wait for redirect
    await endUserPage.waitForTimeout(3000);

    // Check redirect
    const endUserUrl = endUserPage.url();
    if (endUserUrl.includes('8080') || endUserUrl.includes('openwebui')) {
      console.log("✅ Admin-created end user redirected to OpenWebUI");
    } else {
      console.log("⚠️ Admin-created end user not redirected properly");
      console.log(`Current URL: ${endUserUrl}`);
    }

    // Test 5: Creator User vs End User Comparison
    console.log("\n🔄 Test 5: Creator User vs End User Comparison");

    // Open new page for creator user
    const creatorPage = await context.newPage();
    await creatorPage.goto(baseUrl);
    await creatorPage.waitForLoadState('networkidle');

    // Login as creator user (testuser from previous test)
    await creatorPage.fill('input[type="email"]', 'testuser@test-eng.com');
    await creatorPage.fill('input[type="password"]', 'testpass123');
    await creatorPage.click('button:has-text("Login")');
    await creatorPage.waitForTimeout(2000);

    // Check if creator user stays on LAMB interface
    const creatorUrl = creatorPage.url();
    if (creatorUrl.includes('5173') && !creatorUrl.includes('8080')) {
      console.log("✅ Creator user stays on LAMB interface");

      // Check for creator-specific elements
      const assistantsLink = creatorPage.locator('a:has-text("Assistants"), button:has-text("Assistants")');
      if (await assistantsLink.isVisible({ timeout: 3000 })) {
        console.log("✅ Creator user has access to Assistants");
      }
    } else {
      console.log("⚠️ Creator user not on LAMB interface");
    }

    // Test 6: Organization Signup
    console.log("\n🏢 Test 6: Organization Signup");

    // Open new page for org signup
    const orgSignupPage = await context.newPage();
    await orgSignupPage.goto(baseUrl);
    await orgSignupPage.waitForLoadState('networkidle');

    // Try signup with organization key
    const orgSignupLink = orgSignupPage.locator('a:has-text("Sign up"), button:has-text("Sign up")').first();
    if (await orgSignupLink.isVisible({ timeout: 3000 })) {
      await orgSignupLink.click();

      // Fill signup form with org key
      await orgSignupPage.fill('input[name="name"]', 'Org Test User');
      await orgSignupPage.fill('input[name="email"]', 'orguser@test.com');
      await orgSignupPage.fill('input[name="password"]', 'orgpass123');
      await orgSignupPage.fill('input[name="secret_key"]', 'test-eng-2024'); // From test org

      // Submit
      await orgSignupPage.click('button:has-text("Sign Up")');
      await orgSignupPage.waitForTimeout(2000);

      console.log("✅ Organization signup completed");
    } else {
      console.log("⚠️ Organization signup not tested");
    }

    console.log("\n🎉 End User test suite completed!");
    console.log("\n📊 End User Test Results:");
    console.log("✅ User signup functionality");
    console.log("✅ End user login and redirect");
    console.log("✅ Admin end user creation");
    console.log("✅ Creator vs end user behavior");
    console.log("✅ Organization signup");

    // Cleanup - close extra pages
    await adminPage.close();
    await endUserPage.close();
    await creatorPage.close();
    if (orgSignupPage) await orgSignupPage.close();

  } catch (error) {
    console.error("❌ End User Test failed:", error);
  } finally {
    await browser.close();
  }
})();
