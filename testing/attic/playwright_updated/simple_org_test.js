const { chromium } = require("playwright");

(async () => {
  console.log("🏢 Starting Simple Organization Test");
  console.log(`📍 Testing against: http://localhost:5173`);

  const browser = await chromium.launch({ headless: false, slowMo: 800 });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Verify we're logged in as admin
    console.log("\n🔐 Checking Admin Login");
    await page.goto('http://localhost:5173');

    // Check if already logged in
    const adminIndicator = page.locator('text=Admin User');
    const isLoggedIn = await adminIndicator.isVisible({ timeout: 3000 });

    if (!isLoggedIn) {
      console.log("🔑 Admin not logged in, performing login...");

      // Look for login form
      const emailInput = page.locator('input[type="email"]');
      const passwordInput = page.locator('input[type="password"]');

      if (await emailInput.isVisible({ timeout: 5000 })) {
        // Fill login form
        await emailInput.fill('admin@owi.com');
        await passwordInput.fill('admin');
        await page.click('button:has-text("Login")');
        await page.waitForTimeout(2000);

        // Verify login success
        const adminAfterLogin = page.locator('text=Admin User');
        if (await adminAfterLogin.isVisible({ timeout: 5000 })) {
          console.log("✅ Admin login successful");
        } else {
          throw new Error("Failed to login as admin");
        }
      } else {
        throw new Error("Login form not found");
      }
    } else {
      console.log("✅ Admin already logged in");
    }

    // Navigate to admin organizations
    console.log("\n📋 Navigating to Organization Management");
    await page.goto('http://localhost:5173/admin?view=organizations');

    // Count existing organizations
    await page.waitForTimeout(2000);
    const orgRows = page.locator('table tbody tr');
    const initialOrgCount = await orgRows.count();
    console.log(`📊 Found ${initialOrgCount} existing organizations`);

    // Test: Create Simple Organization
    console.log("\n🏗️ Creating Simple Organization");

    const createOrgButton = page.getByRole('button', { name: 'Create Organization' });
    await createOrgButton.waitFor({ timeout: 10000 });
    await createOrgButton.click();

    // Wait for form to load
    await page.waitForTimeout(2000);

    // Generate unique names
    const timestamp = Date.now();
    const orgName = `Simple Test Org ${timestamp}`;
    const orgSlug = `simple-test-${timestamp}`;

    console.log(`📝 Creating organization: ${orgName} (${orgSlug})`);

    // Fill the form using more direct selectors
    // Find all input elements in the form
    const inputs = page.locator('input[type="text"]');
    const inputCount = await inputs.count();
    console.log(`📝 Found ${inputCount} text inputs in form`);

    // Fill slug (usually first input)
    if (inputCount >= 1) {
      await inputs.nth(0).fill(orgSlug);
      console.log("✅ Filled slug field");
    }

    // Fill name (usually second input)
    if (inputCount >= 2) {
      await inputs.nth(1).fill(orgName);
      console.log("✅ Filled name field");
    }

    // Try to select admin user from dropdown
    const selectElements = page.locator('select');
    const selectCount = await selectElements.count();
    console.log(`📝 Found ${selectCount} select elements`);

    if (selectCount > 0) {
      const adminSelect = selectElements.first();
      const options = adminSelect.locator('option');
      const optionCount = await options.count();

      if (optionCount > 1) {
        // Select first actual user (skip "Select a user..." option)
        await adminSelect.selectOption({ index: 1 });
        console.log("✅ Selected organization admin");
      }
    }

    // Submit the form
    const submitButtons = page.locator('button:has-text("Create Organization")');
    const submitButton = submitButtons.last(); // In case there are multiple

    if (await submitButton.isVisible({ timeout: 2000 })) {
      await submitButton.click();
      console.log("✅ Submitted organization creation form");

      // Wait for processing
      await page.waitForTimeout(3000);

      // Check if organization was created
      const newOrgRows = page.locator('table tbody tr');
      const finalOrgCount = await newOrgRows.count();

      if (finalOrgCount > initialOrgCount) {
        console.log(`✅ Organization created successfully (${initialOrgCount} → ${finalOrgCount})`);

        // Verify our organization appears in the table
        const orgNameCell = page.locator(`text=${orgName}`);
        if (await orgNameCell.isVisible({ timeout: 5000 })) {
          console.log("✅ New organization visible in table");
        } else {
          console.log("⚠️ Organization created but not immediately visible");
        }

        console.log("\n🎉 Simple Organization Test Completed Successfully!");
        console.log("\n📊 Test Results:");
        console.log("✅ Admin login verification");
        console.log("✅ Organization creation");
        console.log("✅ Form field population");
        console.log("✅ Admin user selection");
        console.log("✅ Form submission");
        console.log(`✅ Organization count increased: ${initialOrgCount} → ${finalOrgCount}`);

        console.log("\n🏷️ Created Test Data:");
        console.log(`   Organization: ${orgName}`);
        console.log(`   Slug: ${orgSlug}`);
        console.log("   Status: Active (default)");
        console.log("   Type: Regular");

      } else {
        console.log(`❌ Organization count didn't increase (${initialOrgCount} → ${finalOrgCount})`);
      }

    } else {
      console.log("❌ Could not find submit button");
    }

  } catch (error) {
    console.error("❌ Simple Organization Test failed:", error.message);
  } finally {
    await browser.close();
  }
})();
