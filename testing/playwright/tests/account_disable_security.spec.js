const { test, expect, chromium } = require("@playwright/test");
const fs = require("fs");

/**
 * Account Disable Security Tests (Dual Browser Strategy)
 *
 * Tests the AuthContext disabled account detection across multiple security layers:
 *   - Backend: AuthContext._build_auth_context() checks enabled field
 *   - Frontend: beforeNavigate + authenticatedFetch + polling
 *
 * Flow:
 *   1. Admin1 creates Admin2
 *   2. Admin2 logs in (separate browser context - simulates different device)
 *   3. Admin1 disables Admin2 (while Admin2 is still logged in)
 *   4. Admin2 tries API call (disable Admin1) → 401/403 + forced logout
 *   5. Admin2 tries navigation → Blocked by beforeNavigate
 *   6. Admin2 idle (AFK) → Polling detects within 60s
 *   7. Direct URL access blocked
 *   8. Cleanup
 */

test.describe.serial("Account Disable Security (Dual Browser)", () => {
  const timestamp = Date.now();
  const admin2Email = `admin2_sec_${timestamp}@test.com`;
  const admin2Name = `Admin2Sec${timestamp}`;
  const admin2Password = "TestSecure_456!";

  const baseAdminEmail = process.env.LOGIN_EMAIL || "admin@owi.com";
  const baseURL = process.env.BASE_URL || "http://localhost:5173";

  let browser;
  let admin1Context;
  let admin1Page;
  let admin2Context;
  let admin2Page;

  test.beforeAll(async () => {
    console.log(`[security] Starting dual browser setup...`);
    
    // Launch browser
    browser = await chromium.launch();
    
    // Context 1: Admin1 - try to use auth state, but login if needed
    const authFile = ".auth/state.json";
    if (fs.existsSync(authFile)) {
      admin1Context = await browser.newContext({
        storageState: authFile
      });
      console.log(`[security] Admin1 context created with auth state`);
    } else {
      admin1Context = await browser.newContext();
      console.log(`[security] ⚠️  No auth file found, Admin1 will login fresh`);
    }
    
    admin1Page = await admin1Context.newPage();
    admin1Page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`[admin1-console] ERROR: ${msg.text()}`);
      }
    });
    
    // Verify admin1 is authenticated, login if not
    await admin1Page.goto(baseURL);
    await admin1Page.waitForLoadState("domcontentloaded");
    await admin1Page.waitForTimeout(2000);
    
    // Check if there's an "Invalid or expired authentication token" message
    const hasTokenError = await admin1Page.getByText(/invalid or expired authentication token/i).isVisible().catch(() => false);
    
    if (hasTokenError) {
      console.log(`[security] Token expired - logging out and re-authenticating...`);
      
      // Click logout button
      const logoutBtn = admin1Page.getByRole('button', { name: /logout/i });
      if (await logoutBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await logoutBtn.click();
        await admin1Page.waitForTimeout(1000);
      } else {
        // Alternative: clear token from localStorage and reload
        await admin1Page.evaluate(() => {
          localStorage.removeItem('userToken');
          localStorage.removeItem('user');
        });
        await admin1Page.reload();
      }
    }
    
    // Check if we're on login page
    const emailInput = await admin1Page.locator('#email').isVisible({ timeout: 3000 }).catch(() => false);
    
    if (emailInput) {
      console.log(`[security] Admin1 logging in...`);
      
      await admin1Page.fill('#email', baseAdminEmail);
      await admin1Page.fill('#password', process.env.LOGIN_PASSWORD || 'admin');
      
      await Promise.all([
        admin1Page.waitForLoadState("networkidle").catch(() => {}),
        admin1Page.click('button[type="submit"]')
      ]);
      
      await admin1Page.waitForTimeout(2000);
      console.log(`[security] Admin1 logged in successfully`);
    } else {
      console.log(`[security] Admin1 already authenticated ✅`);
    }
    
    // Context 2: Admin2 (fresh, independent)
    admin2Context = await browser.newContext({
      storageState: undefined // No shared state
    });
    admin2Page = await admin2Context.newPage();
    admin2Page.on('console', msg => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        console.log(`[admin2-console] ${msg.type()}: ${msg.text()}`);
      }
    });
    
    console.log(`[security] Base URL: ${baseURL}`);
    console.log(`[security] Dual browser setup complete ✅`);
  });

  test.afterAll(async () => {
    console.log(`[security] Closing browser contexts...`);
    await admin1Context?.close();
    await admin2Context?.close();
    await browser?.close();
    console.log(`[security] Cleanup complete ✅`);
  });

  test("1. Admin1 creates Admin2", async () => {
    console.log(`[security-test-1] Starting: Admin1 creates Admin2`);
    
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("networkidle");

    const createButton = admin1Page.getByRole("button", { name: /create user/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const modal = admin1Page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await admin1Page.waitForTimeout(500);

    await modal.getByRole("textbox", { name: "Email *" }).fill(admin2Email);
    await modal.getByRole("textbox", { name: "Name *" }).fill(admin2Name);
    await modal.getByRole("textbox", { name: "Password *" }).fill(admin2Password);
    await modal.getByLabel("Role").selectOption("admin");

    const submit = modal.getByRole("button", { name: "Create User" });
    await submit.click();
    await admin1Page.waitForTimeout(2000);

    // Verify user created
    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    await expect(admin1Page.getByText(admin2Email)).toBeVisible({ timeout: 10_000 });
    console.log(`[security-test-1] ✅ Admin1 created ${admin2Email}`);
  });

  test("2. Admin2 logs in (separate browser context)", async () => {
    console.log(`[security-test-2] Starting: Admin2 login`);
    
    await admin2Page.goto(baseURL);
    await admin2Page.waitForLoadState("domcontentloaded");
    
    await admin2Page.waitForSelector("#email", { timeout: 10_000 });
    await admin2Page.getByRole("textbox", { name: "Email" }).fill(admin2Email);
    await admin2Page.getByRole("textbox", { name: "Password" }).fill(admin2Password);
    
    await Promise.all([
      admin2Page.waitForNavigation({ timeout: 10_000 }).catch(() => {}),
      admin2Page.getByRole("button", { name: "Login" }).click()
    ]);
    
    await admin2Page.waitForTimeout(2000);

    // Verify logged in
    await expect(admin2Page.getByRole("link", { name: "Admin" })).toBeVisible({ timeout: 10_000 });
    
    // Verify token stored
    const token = await admin2Page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).not.toBeNull();
    
    console.log(`[security-test-2] ✅ Admin2 logged in successfully`);
  });

  test("3. Admin2 navigates to users page", async () => {
    console.log(`[security-test-3] Starting: Admin2 navigates to users`);
    
    await admin2Page.goto("/admin?view=users");
    await admin2Page.waitForLoadState("networkidle");

    await expect(
      admin2Page.getByRole("button", { name: "Users", exact: true })
    ).toBeVisible({ timeout: 10_000 });

    console.log(`[security-test-3] ✅ Admin2 on users page`);
  });

  test("4. Admin1 disables Admin2 (while Admin2 is still logged in)", async () => {
    console.log(`[security-test-4] Starting: Admin1 disables Admin2`);
    
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("networkidle");

    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const userRow = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    await expect(userRow).toBeVisible({ timeout: 5_000 });

    const disableButton = userRow.getByLabel("Disable User");
    await disableButton.click();

    const confirmButton = admin1Page.getByRole("button", { name: "Disable", exact: true });
    await confirmButton.click();
    await admin1Page.waitForTimeout(2000);

    // Verify disabled
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const disabledRow = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    await expect(disabledRow.getByLabel("Enable User")).toBeVisible({ timeout: 5_000 });

    console.log(`[security-test-4] ✅ Admin1 disabled ${admin2Email} (Admin2 still has valid token)`);
  });

  test("5. Admin2 tries API call (disable Admin1) → 401 + forced logout", async () => {
    console.log(`[security-test-5] Starting: Admin2 tries to disable Admin1 (should fail)`);
    
    // Set up network listener BEFORE action
    let got401or403 = false;
    admin2Page.on('response', (response) => {
      if (response.status() === 401 || response.status() === 403) {
        console.log(`[security-test-5] ⚠️  Detected ${response.status()} from ${response.url()}`);
        got401or403 = true;
      }
    });

    // Set up console listener for frontend logout
    let frontendLoggedOut = false;
    admin2Page.on('console', (msg) => {
      if (msg.text().includes('Force logout') || msg.text().includes('Invalid or expired token')) {
        console.log(`[security-test-5] ⚠️  Frontend logout triggered: ${msg.text()}`);
        frontendLoggedOut = true;
      }
    });

    // Search for Admin1
    const searchBox = admin2Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(baseAdminEmail);
    await admin2Page.waitForTimeout(500);

    const admin1Row = admin2Page.getByRole("row", { name: new RegExp(baseAdminEmail, "i") });
    await expect(admin1Row).toBeVisible({ timeout: 5_000 });

    // Try to disable Admin1 (should trigger 401)
    const disableBtn = admin1Row.getByLabel("Disable User");
    await disableBtn.click();

    const confirmBtn = admin2Page.getByRole("button", { name: "Disable", exact: true });
    await confirmBtn.click();

    // Wait for backend response
    await admin2Page.waitForTimeout(2000);

    // Verify either got 401/403 OR was redirected to login
    const currentURL = admin2Page.url();
    const onLoginPage = currentURL.endsWith('/') && !currentURL.includes('/admin');
    
    if (onLoginPage) {
      console.log(`[security-test-5] ✅ Redirected to login page`);
      await expect(admin2Page.getByRole("textbox", { name: "Email" })).toBeVisible({ timeout: 3_000 });
    } else {
      // Still on admin page but should have gotten error
      expect(got401or403).toBe(true);
      console.log(`[security-test-5] ✅ Got 401/403 error`);
    }

    // Verify token cleared
    const token = await admin2Page.evaluate(() => localStorage.getItem("userToken"));
    if (onLoginPage) {
      expect(token).toBeNull();
      console.log(`[security-test-5] ✅ Token cleared from localStorage`);
    }
  });

  test("6. Admin2 tries navigation → Blocked by beforeNavigate", async () => {
    console.log(`[security-test-6] Starting: Admin2 tries to navigate (should be blocked)`);
    
    // If already logged out from test 5, skip
    const currentURL = admin2Page.url();
    if (currentURL.endsWith('/') && !currentURL.includes('/admin')) {
      console.log(`[security-test-6] Admin2 already logged out, skipping navigation test`);
      return;
    }

    // Listen for 401 responses
    let got401 = false;
    admin2Page.on('response', (response) => {
      if (response.status() === 401) {
        console.log(`[security-test-6] ⚠️  401 from ${response.url()}`);
        got401 = true;
      }
    });

    // Navigate internally by clicking on Organizations button (triggers beforeNavigate)
    // First make sure we're on the admin page
    if (!admin2Page.url().includes('/admin')) {
      await admin2Page.goto("/admin");
      await admin2Page.waitForLoadState("domcontentloaded");
    }

    // Try to click the Organizations button/link (internal navigation via SvelteKit)
    const orgButton = admin2Page.getByRole("button", { name: /organizations/i });
    
    if (await orgButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await orgButton.click();
    } else {
      // Alternative: try clicking a navigation link
      const orgLink = admin2Page.getByRole("link", { name: /organizations/i });
      if (await orgLink.isVisible({ timeout: 2000 }).catch(() => false)) {
        await orgLink.click();
      } else {
        console.log(`[security-test-6] ⚠️  Organizations button not found, test may be invalid`);
      }
    }
    
    // Should be redirected to login after beforeNavigate intercepts
    await admin2Page.waitForURL(/\/$/, { timeout: 10_000 });
    await expect(admin2Page.getByRole("textbox", { name: "Email" })).toBeVisible({ timeout: 5_000 });

    // Token should be cleared
    const token = await admin2Page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeNull();

    console.log(`[security-test-6] ✅ Navigation blocked by beforeNavigate, forced logout`);
  });

  test("7. Verify disabled account cannot re-login", async () => {
    console.log(`[security-test-7] Starting: Disabled account re-login attempt`);
    
    // Admin2 can't login anymore (disabled), so this test verifies the account is truly disabled
    await admin2Page.goto(baseURL);
    await admin2Page.waitForLoadState("domcontentloaded");
    
    await admin2Page.getByRole("textbox", { name: "Email" }).fill(admin2Email);
    await admin2Page.getByRole("textbox", { name: "Password" }).fill(admin2Password);
    await admin2Page.getByRole("button", { name: "Login" }).click();
    
    await admin2Page.waitForTimeout(2000);
    
    // Should fail to login (account disabled message or stay on login page)
    const stillOnLoginPage = admin2Page.url().endsWith('/');
    expect(stillOnLoginPage).toBe(true);
    
    console.log(`[security-test-7] ✅ Disabled account cannot re-login`);
  });

  test("8. Polling detects disabled account (AFK scenario)", async () => {
    // This test needs more time - polling runs every 60s
    test.setTimeout(120_000); // 2 minutes timeout
    
    console.log(`[security-test-8] Starting: Polling detection test (60s max)`);
    
    // First, Admin1 re-enables Admin2 so they can login
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("domcontentloaded");

    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const admin2Row = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    await expect(admin2Row).toBeVisible({ timeout: 5_000 });

    const enableBtn = admin2Row.getByLabel("Enable User");
    if (await enableBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await enableBtn.click();
      
      // Confirm enable in modal
      const confirmEnableBtn = admin1Page.getByRole("button", { name: "Enable", exact: true });
      await expect(confirmEnableBtn).toBeVisible({ timeout: 3_000 });
      await confirmEnableBtn.click();
      await admin1Page.waitForTimeout(1500);
      
      console.log(`[security-test-8] Admin2 re-enabled`);
    }

    // Admin2 logs back in
    console.log(`[security-test-8] Navigating Admin2 to login...`);
    await admin2Page.goto(baseURL);
    await admin2Page.waitForLoadState("domcontentloaded");
    await admin2Page.waitForTimeout(1000);
    
    // Check if already on login page or need to navigate
    const emailField = admin2Page.getByRole("textbox", { name: "Email" });
    await expect(emailField).toBeVisible({ timeout: 10_000 });
    
    console.log(`[security-test-8] Filling Admin2 login credentials...`);
    await emailField.fill(admin2Email);
    await admin2Page.getByRole("textbox", { name: "Password" }).fill(admin2Password);
    
    console.log(`[security-test-8] Clicking login button...`);
    await Promise.all([
      admin2Page.waitForNavigation({ timeout: 15_000 }).catch(() => {}),
      admin2Page.getByRole("button", { name: "Login" }).click()
    ]);
    await admin2Page.waitForTimeout(2000);

    // Verify login succeeded (look for Admin link like test 2 does)
    await expect(admin2Page.getByRole("link", { name: "Admin" })).toBeVisible({ timeout: 10_000 });
    console.log(`[security-test-8] ✅ Admin2 logged back in`);

    // Navigate explicitly to admin page
    await admin2Page.goto("/admin?view=users");
    await admin2Page.waitForLoadState("networkidle");

    // Admin1 disables Admin2 again
    console.log(`[security-test-8] Admin1 navigating to users page...`);
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("domcontentloaded");
    await admin1Page.waitForTimeout(1000);
    
    console.log(`[security-test-8] Searching for Admin2...`);
    // Search for Admin2 again (fresh query)
    const searchBox2 = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox2.fill(admin2Email);
    await admin1Page.waitForTimeout(1000);

    console.log(`[security-test-8] Looking for Admin2 row...`);
    // Find Admin2 row again (fresh query)
    const admin2RowAgain = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    await expect(admin2RowAgain).toBeVisible({ timeout: 10_000 });

    console.log(`[security-test-8] Finding Disable button...`);
    const disableBtn = admin2RowAgain.getByLabel("Disable User");
    await expect(disableBtn).toBeVisible({ timeout: 5_000 });
    await disableBtn.click();

    console.log(`[security-test-8] Confirming disable...`);
    const confirmBtn = admin1Page.getByRole("button", { name: "Disable", exact: true });
    await expect(confirmBtn).toBeVisible({ timeout: 5_000 });
    await confirmBtn.click();
    await admin1Page.waitForTimeout(2000);

    console.log(`[security-test-8] Admin2 disabled again, Admin2 now AFK (polling will detect within 60s)...`);

    // Admin2 stays idle, polling should detect within 60s
    // sessionGuard.js polls every 60s, wait up to 75s for detection
    let loggedOut = false;
    const startTime = Date.now();
    
    while (Date.now() - startTime < 75_000 && !loggedOut) {
      await admin2Page.waitForTimeout(3000); // Check every 3s
      const currentURL = admin2Page.url();
      if (currentURL.endsWith('/') && !currentURL.includes('/admin')) {
        loggedOut = true;
        const timeElapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        console.log(`[security-test-8] ✅ Polling detected disabled account after ${timeElapsed}s`);
      }
    }

    if (!loggedOut) {
      console.log(`[security-test-8] ⚠️  Polling did not detect disabled account within 75s`);
    }

    expect(loggedOut).toBe(true);
    
    // Verify on login page
    await expect(admin2Page.getByRole("textbox", { name: "Email" })).toBeVisible({ timeout: 3_000 });
    const token = await admin2Page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeNull();
    
    console.log(`[security-test-8] ✅ AFK user logged out via polling`);
  });

  test("9. Direct URL access blocked", async () => {
    console.log(`[security-test-9] Starting: Direct URL access blocked test`);
    
    const protectedUrls = ["/assistants", "/knowledgebases", "/admin"];

    for (const url of protectedUrls) {
      await admin2Page.goto(url);
      await admin2Page.waitForURL(/\/$/, { timeout: 5_000 });

      const emailInput = admin2Page.getByRole("textbox", { name: "Email" });
      await expect(emailInput).toBeVisible({ timeout: 3_000 });

      console.log(`[security-test-9] ✅ ${url} blocked, redirected to login`);
    }
  });

  test("10. Cleanup", async () => {
    console.log(`[security-test-10] Cleanup: Deleting Admin2`);
    
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("networkidle");

    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const userRow = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    const deleteButton = userRow.getByLabel("Delete User");
    await deleteButton.click();

    const confirmButton = admin1Page.getByRole("button", { name: "Delete", exact: true });
    await confirmButton.click();

    await admin1Page.waitForTimeout(2000);

    console.log(`[security-test-10] ✅ Cleanup done - Admin2 deleted`);
  });
});
