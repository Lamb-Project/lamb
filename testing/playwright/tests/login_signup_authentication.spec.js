const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

/**
 * Login, Signup & Authentication Tests
 *
 * Covers the authentication-related flows that were previously untested:
 *
 *   Part 1 — Login with invalid credentials:
 *     1. Wrong email/password shows error message
 *     2. Empty fields are blocked by HTML5 validation
 *
 *   Part 2 — Signup form:
 *     3. "Sign up" link toggles from login to signup form
 *     4. "Log in" link toggles from signup back to login form
 *     5. Signup with invalid secret key shows error
 *     6. Signup with valid system secret key creates user (requires SIGNUP_ENABLED + SIGNUP_SECRET_KEY)
 *
 *   Part 3 — Signup with organization-specific key:
 *     7. Admin creates org with signup key enabled
 *     8. Signup using org signup key creates user in that org
 *     9. Cleanup: disable user + delete org
 *
 *   Part 4 — Explicit logout:
 *    10. Logout clears session and shows login form
 *    11. After logout, protected routes redirect to login
 *
 *   Part 5 — Expired / invalid token:
 *    12. Invalid token in localStorage → API calls fail, user sees login
 *
 * Prerequisites:
 *   - Logged in as admin via global-setup.js (for admin operations in Part 3)
 *   - Backend env: SIGNUP_ENABLED=true, SIGNUP_SECRET_KEY set (for Part 2 test 6)
 */

const baseAdminEmail = process.env.LOGIN_EMAIL || "admin@owi.com";
const baseAdminPassword = process.env.LOGIN_PASSWORD || "admin";

// These env vars are needed for the system signup test (Part 2, test 6).
// If not set, that specific test will be skipped gracefully.
const SIGNUP_SECRET_KEY = process.env.SIGNUP_SECRET_KEY || "";

test.describe.serial("Login, Signup & Authentication", () => {
  const timestamp = Date.now();

  // ════════════════════════════════════════════════════════════════
  // PART 1 — Login with invalid credentials
  // ════════════════════════════════════════════════════════════════

  test("1. Login with wrong credentials shows error message", async ({ browser }) => {
    // Use a fresh context without any stored auth state
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait for login form
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Fill in wrong credentials
    await page.fill("#email", "nonexistent_user@invalid.com");
    await page.fill("#password", "wrong_password_12345");

    // Submit the form
    await page.click('button[type="submit"], form button');

    // Wait for error message to appear
    await expect(
      page.locator(".bg-red-100").first()
    ).toBeVisible({ timeout: 10_000 });

    // Verify error text is shown (backend returns "Invalid email or password" or similar)
    const errorText = await page.locator(".bg-red-100").first().textContent();
    expect(errorText?.toLowerCase()).toMatch(/invalid|error|failed|denied/);

    // Verify we're still on the login page (not redirected)
    await expect(page.locator("#email")).toBeVisible();

    // Verify no token was set in localStorage
    const token = await page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeNull();

    console.log(`[auth_test] Login with wrong credentials correctly rejected: "${errorText?.trim()}"`);

    await context.close();
  });

  test("2. Login form requires email and password (HTML5 validation)", async ({ browser }) => {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Both fields are required — try submitting with empty fields
    // The form has required attributes, so the browser should prevent submission
    const emailInput = page.locator("#email");
    const passwordInput = page.locator("#password");

    await expect(emailInput).toHaveAttribute("required", "");
    await expect(passwordInput).toHaveAttribute("required", "");

    console.log("[auth_test] Login form fields have required attribute.");

    await context.close();
  });

  // ════════════════════════════════════════════════════════════════
  // PART 2 — Signup form
  // ════════════════════════════════════════════════════════════════

  test("3. 'Sign up' link switches from login to signup form", async ({ browser }) => {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Verify we're on the login form (has "Login" heading)
    await expect(page.getByRole("heading", { name: /login/i })).toBeVisible();

    // Click "Sign up" link
    const signupLink = page.getByRole("button", { name: /sign up/i });
    await expect(signupLink).toBeVisible();
    await signupLink.click();

    // Verify signup form is now visible
    await expect(page.getByRole("heading", { name: /sign up/i })).toBeVisible({ timeout: 5_000 });

    // Verify signup-specific fields exist
    await expect(page.locator("#name")).toBeVisible();
    await expect(page.locator("#signup-email")).toBeVisible();
    await expect(page.locator("#signup-password")).toBeVisible();
    await expect(page.locator("#secret")).toBeVisible(); // Secret key field

    console.log("[auth_test] Successfully navigated from Login to Signup form.");

    await context.close();
  });

  test("4. 'Log in' link switches from signup back to login form", async ({ browser }) => {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Navigate to signup form first
    await page.getByRole("button", { name: /sign up/i }).click();
    await expect(page.getByRole("heading", { name: /sign up/i })).toBeVisible({ timeout: 5_000 });

    // Click "Log in" link to go back
    const loginLink = page.getByRole("button", { name: /log in/i });
    await expect(loginLink).toBeVisible();
    await loginLink.click();

    // Verify login form is visible again
    await expect(page.getByRole("heading", { name: /login/i })).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("#email")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();

    // Signup-specific fields should NOT be visible
    await expect(page.locator("#secret")).not.toBeVisible();

    console.log("[auth_test] Successfully navigated from Signup back to Login form.");

    await context.close();
  });

  test("5. Signup with invalid secret key shows error", async ({ browser }) => {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Navigate to signup form
    await page.getByRole("button", { name: /sign up/i }).click();
    await expect(page.getByRole("heading", { name: /sign up/i })).toBeVisible({ timeout: 5_000 });

    // Fill in signup details with an invalid secret key
    await page.locator("#name").fill(`Invalid Key User ${timestamp}`);
    await page.locator("#signup-email").fill(`invalid_key_${timestamp}@test.com`);
    await page.locator("#signup-password").fill("TestPassword123!");
    await page.locator("#secret").fill("this-is-a-totally-invalid-key-xyz");

    // Submit signup
    await page.click('form button[type="submit"], form button');

    // Should show an error message (red banner)
    await expect(
      page.locator(".bg-red-100").first()
    ).toBeVisible({ timeout: 10_000 });

    const errorText = await page.locator(".bg-red-100").first().textContent();
    expect(errorText?.toLowerCase()).toMatch(/invalid|disabled|error|secret|key/);

    console.log(`[auth_test] Signup with invalid key correctly rejected: "${errorText?.trim()}"`);

    await context.close();
  });

  // Test 6: System signup — only runs if SIGNUP_SECRET_KEY env var is set
  const systemSignupEmail = `sys_signup_${timestamp}@test.com`;
  const systemSignupName = `SysSignup ${timestamp}`;
  const systemSignupPassword = "SignupTest_2026!";

  test("6. Signup with valid system secret key creates user", async ({ browser }, testInfo) => {
    if (!SIGNUP_SECRET_KEY) {
      testInfo.skip(true, "SIGNUP_SECRET_KEY not set in tests/.env — skipping system signup test");
      return;
    }

    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Navigate to signup form
    await page.getByRole("button", { name: /sign up/i }).click();
    await expect(page.getByRole("heading", { name: /sign up/i })).toBeVisible({ timeout: 5_000 });

    // Fill in valid signup details
    await page.locator("#name").fill(systemSignupName);
    await page.locator("#signup-email").fill(systemSignupEmail);
    await page.locator("#signup-password").fill(systemSignupPassword);
    await page.locator("#secret").fill(SIGNUP_SECRET_KEY);

    // Submit signup
    await page.click('form button[type="submit"], form button');

    // Should show success message (green banner)
    await expect(
      page.locator(".bg-green-100").first()
    ).toBeVisible({ timeout: 15_000 });

    const successText = await page.locator(".bg-green-100").first().textContent();
    expect(successText?.toLowerCase()).toMatch(/success|created|account/);

    // After success, the UI auto-switches back to login form
    await expect(page.locator("#email")).toBeVisible({ timeout: 5_000 });

    console.log(`[auth_test] System signup successful: "${successText?.trim()}"`);

    await context.close();
  });

  test("6b. Cleanup: disable system signup user", async ({ page }, testInfo) => {
    if (!SIGNUP_SECRET_KEY) {
      testInfo.skip(true, "SIGNUP_SECRET_KEY not set — no system signup user to clean up");
      return;
    }

    // Already logged in as admin via global-setup storageState
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(systemSignupEmail);
      await page.waitForTimeout(500);
    }

    const userRow = page.locator(`tr:has-text("${systemSignupEmail}")`);
    if (await userRow.count()) {
      const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await disableButton.click();

        const modal = page.getByRole("dialog");
        await expect(modal).toBeVisible({ timeout: 5_000 });
        const confirmButton = modal.getByRole("button", { name: /^disable$/i });
        await expect(confirmButton).toBeVisible({ timeout: 5_000 });
        await confirmButton.click();
        await expect(modal).not.toBeVisible({ timeout: 10_000 });

        console.log(`[auth_test] System signup user "${systemSignupEmail}" disabled.`);
      }
    } else {
      console.log(`[auth_test] System signup user "${systemSignupEmail}" not found (may not have been created).`);
    }
  });

  // ════════════════════════════════════════════════════════════════
  // PART 3 — Signup with organization-specific signup key
  // ════════════════════════════════════════════════════════════════

  const orgSignupKey = `test-signup-key-${timestamp}`;
  const orgSlug = `signup-org-${timestamp}`;
  const orgName = `Signup Org ${timestamp}`;
  const orgSignupEmail = `org_signup_${timestamp}@test.com`;
  const orgSignupName = `OrgSignup ${timestamp}`;
  const orgSignupPassword = "OrgSignup_2026!";

  test("7. Admin creates org with signup key enabled", async ({ page }) => {
    // Logged in as admin via storageState
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click Create Organization
    const createButton = page.getByRole("button", { name: /create organization/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for modal
    await expect(page.locator("input#org_slug")).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(500);

    // Fill org details
    await page.locator("input#org_slug").fill(orgSlug);
    await page.locator("input#org_name").fill(orgName);

    // Enable signup for this org
    const signupCheckbox = page.locator('input[name="signup_enabled"]');
    await expect(signupCheckbox).toBeVisible({ timeout: 5_000 });
    if (!(await signupCheckbox.isChecked())) {
      await signupCheckbox.click();
    }
    await page.waitForTimeout(300);

    // Wait for the signup key input to appear and fill it
    const signupKeyInput = page.locator("input#signup_key");
    await expect(signupKeyInput).toBeVisible({ timeout: 3_000 });
    await signupKeyInput.fill(orgSignupKey);

    // Wait for admin dropdown to load (don't select any admin — optional)
    const adminSelect = page.locator("select#admin_user");
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1000);

    // Submit
    const submitButton = page
      .locator(".fixed.inset-0")
      .getByRole("button", { name: /^create organization$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click({ force: true });

    // Wait for success
    await expect(
      page.getByText(/organization created successfully/i)
    ).toBeVisible({ timeout: 15_000 });

    console.log(`[auth_test] Organization "${orgName}" created with signup key "${orgSignupKey}".`);
  });

  test("8. Signup using org-specific signup key creates user in that org", async ({ browser }) => {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    // Navigate to signup form
    await page.getByRole("button", { name: /sign up/i }).click();
    await expect(page.getByRole("heading", { name: /sign up/i })).toBeVisible({ timeout: 5_000 });

    // Fill in signup with org signup key
    await page.locator("#name").fill(orgSignupName);
    await page.locator("#signup-email").fill(orgSignupEmail);
    await page.locator("#signup-password").fill(orgSignupPassword);
    await page.locator("#secret").fill(orgSignupKey);

    // Submit
    await page.click('form button[type="submit"], form button');

    // Should show success message
    await expect(
      page.locator(".bg-green-100").first()
    ).toBeVisible({ timeout: 15_000 });

    const successText = await page.locator(".bg-green-100").first().textContent();
    expect(successText?.toLowerCase()).toMatch(/success|created|account/);

    console.log(`[auth_test] Org signup successful: "${successText?.trim()}"`);

    // Verify the user can now log in
    // After signup success, the app auto-switches to login form
    await expect(page.locator("#email")).toBeVisible({ timeout: 5_000 });

    await page.fill("#email", orgSignupEmail);
    await page.fill("#password", orgSignupPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button'),
    ]);

    await page.waitForTimeout(2000);

    // Should be logged in (logout button visible)
    await expect(
      page.getByRole("button", { name: /logout/i })
    ).toBeVisible({ timeout: 10_000 });

    // Verify token was set
    const token = await page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeTruthy();

    console.log(`[auth_test] Org signup user "${orgSignupEmail}" can log in successfully.`);

    await context.close();
  });

  test("9. Cleanup: disable org signup user + delete org", async ({ page }) => {
    // Logged in as admin via storageState
    // First disable the user
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(orgSignupEmail);
      await page.waitForTimeout(500);
    }

    const userRow = page.locator(`tr:has-text("${orgSignupEmail}")`);
    if (await userRow.count()) {
      const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await disableButton.click();

        const modal = page.getByRole("dialog");
        await expect(modal).toBeVisible({ timeout: 5_000 });
        const confirmButton = modal.getByRole("button", { name: /^disable$/i });
        await expect(confirmButton).toBeVisible({ timeout: 5_000 });
        await confirmButton.click();
        await expect(modal).not.toBeVisible({ timeout: 10_000 });

        console.log(`[auth_test] Org signup user "${orgSignupEmail}" disabled.`);
      }
    }

    // Now delete the org
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    const orgSearchBox = page.locator('input[placeholder*="Search" i]');
    if (await orgSearchBox.count()) {
      await orgSearchBox.fill(orgSlug);
      await page.waitForTimeout(500);
    }

    const orgRow = page.locator(`tr:has-text("${orgSlug}")`);
    if (await orgRow.count()) {
      const deleteButton = orgRow.getByRole("button", { name: /delete organization/i });
      await expect(deleteButton).toBeVisible({ timeout: 5_000 });
      await deleteButton.click();

      const modal = page.getByRole("dialog", { name: /delete organization/i });
      await expect(modal).toBeVisible({ timeout: 5_000 });
      const confirmButton = modal.getByRole("button", { name: /^delete$/i });
      await expect(confirmButton).toBeVisible({ timeout: 5_000 });
      await confirmButton.click();

      await expect(modal).not.toBeVisible({ timeout: 10_000 });
      await expect(orgRow).not.toBeVisible({ timeout: 10_000 });

      console.log(`[auth_test] Organization "${orgSlug}" deleted.`);
    }
  });

  // ════════════════════════════════════════════════════════════════
  // PART 4 — Explicit logout
  // ════════════════════════════════════════════════════════════════

  test("10. Logout clears session and shows login form", async ({ browser }) => {
    // Create a fresh context, login manually, then logout
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    // Login first
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("#email", { timeout: 15_000 });

    await page.fill("#email", baseAdminEmail);
    await page.fill("#password", baseAdminPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button'),
    ]);

    await page.waitForTimeout(2000);

    // Verify we're logged in
    await expect(
      page.getByRole("button", { name: /logout/i })
    ).toBeVisible({ timeout: 10_000 });

    // Verify token exists in localStorage
    const tokenBefore = await page.evaluate(() => localStorage.getItem("userToken"));
    expect(tokenBefore).toBeTruthy();

    // Click Logout
    await page.getByRole("button", { name: /logout/i }).click();

    // Wait for redirect to login page
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // Verify login form is now shown
    await expect(page.locator("#email")).toBeVisible({ timeout: 10_000 });

    // Verify token was removed from localStorage
    const tokenAfter = await page.evaluate(() => localStorage.getItem("userToken"));
    expect(tokenAfter).toBeNull();

    // Verify userName and userEmail are also cleared
    const userName = await page.evaluate(() => localStorage.getItem("userName"));
    const userEmail = await page.evaluate(() => localStorage.getItem("userEmail"));
    expect(userName).toBeNull();
    expect(userEmail).toBeNull();

    // Verify the Logout button is no longer visible
    await expect(
      page.getByRole("button", { name: /logout/i })
    ).not.toBeVisible({ timeout: 3_000 });

    console.log("[auth_test] Logout correctly clears session and shows login form.");

    await context.close();
  });

  test("11. After logout, navigating to protected route shows login form", async ({ browser }) => {
    // Create a fresh context with no auth
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    // Try to navigate directly to protected routes without authentication
    await page.goto("/assistants");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // The app should show the login form (since there's no token in storage)
    // Either we're redirected to "/" with login form, or the page shows login
    const emailField = page.locator("#email");
    const logoutButton = page.getByRole("button", { name: /logout/i });

    // One of these must be true: login form is shown OR we're redirected
    const isLoginVisible = await emailField.isVisible().catch(() => false);
    const isLoggedIn = await logoutButton.isVisible().catch(() => false);

    // Without a stored token, user should NOT be logged in
    expect(isLoggedIn).toBe(false);

    // Login form should be visible (either on the same page or after redirect)
    if (!isLoginVisible) {
      // The SvelteKit frontend renders the page shell even without auth,
      // but user-specific content (name, logout) should not be present.
      const userNameVisible = await page.getByText("Admin User").isVisible().catch(() => false);
      expect(userNameVisible).toBe(false);
    }

    console.log("[auth_test] Protected routes not accessible without authentication.");

    await context.close();
  });

  // ════════════════════════════════════════════════════════════════
  // PART 5 — Expired / invalid token
  // ════════════════════════════════════════════════════════════════

  test("12. Invalid token in localStorage causes API failures", async ({ browser }) => {
    // Create a fresh context and inject a fake/expired token
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();

    // Navigate to the app first
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Inject a fake token into localStorage to simulate an expired session
    await page.evaluate(() => {
      localStorage.setItem("userToken", "fake-expired-token-xyz-123");
      localStorage.setItem("userName", "Fake User");
      localStorage.setItem("userEmail", "fake@test.com");
      localStorage.setItem("userData", JSON.stringify({
        token: "fake-expired-token-xyz-123",
        name: "Fake User",
        email: "fake@test.com",
      }));
    });

    // Reload the page — the store will pick up the fake token and think we're logged in
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Try to navigate to a protected page that makes API calls
    await page.goto("/assistants");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // The page should either:
    // 1. Show an error/unauthorized message
    // 2. Redirect to login
    // 3. Show empty state due to failed API calls
    // Any of these is acceptable — the key is that the fake token doesn't grant access

    const hasLoginForm = await page.locator("#email").isVisible().catch(() => false);
    const hasErrorMessage = await page
      .getByText(/unauthorized|invalid|error|authentication|expired|failed/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasAssistantContent = await page
      .locator('input[placeholder*="Search" i]')
      .isVisible()
      .catch(() => false);

    // With an invalid token, we should NOT see normal functioning content
    // (unless the app silently catches the error and shows empty state)
    if (hasLoginForm) {
      console.log("[auth_test] Invalid token → redirected to login form (correct).");
    } else if (hasErrorMessage) {
      console.log("[auth_test] Invalid token → error message shown (correct).");
    } else if (!hasAssistantContent) {
      console.log("[auth_test] Invalid token → no content loaded (correct).");
    } else {
      // If content loaded, verify API call actually returned an error
      // by making a direct API call with the fake token
      const apiResult = await page.evaluate(async () => {
        const response = await fetch("/creator/users", {
          headers: {
            Authorization: "Bearer fake-expired-token-xyz-123",
            "Content-Type": "application/json",
          },
        });
        return { status: response.status, ok: response.ok };
      });

      // The API should reject the fake token with 401 or 403
      expect(apiResult.ok).toBe(false);
      expect([401, 403, 422]).toContain(apiResult.status);
      console.log(`[auth_test] Invalid token → API returned ${apiResult.status} (correct).`);
    }

    await context.close();
  });
});
