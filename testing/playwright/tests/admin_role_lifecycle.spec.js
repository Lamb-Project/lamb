const { test, expect } = require("@playwright/test");

/**
 * Admin Role Lifecycle Tests (Issue #245 regression)
 *
 * Verifies that non-initial admin users have full admin capabilities,
 * covering the fix for the broken is_admin_user() dict path.
 *
 * Flow:
 *   1. Login as base admin → create a new user with role=admin
 *   2. Logout → login as the new admin → verify admin capabilities
 *      (dashboard, user management, organizations all load)
 *   3. Logout → login as base admin → verify "self-disable" is blocked,
 *      then disable the new admin
 *   4. Verify the disabled admin can no longer log in
 *   5. Cleanup: re-enable + delete the test user
 *
 * Prerequisites:
 *   - Logged in as base admin via global-setup.js
 */

test.describe.serial("Admin Role Lifecycle (issue #245)", () => {
  const timestamp = Date.now();
  const testAdminEmail = `sysadmin_${timestamp}@test.com`;
  const testAdminName = `SysAdmin ${timestamp}`;
  const testAdminPassword = "TestAdmin_245!";

  const baseAdminEmail = process.env.LOGIN_EMAIL || "admin@owi.com";
  const baseAdminPassword = process.env.LOGIN_PASSWORD || "admin";

  // ────────────────────────────────────────────
  // Helper: logout then login as a given user
  // ────────────────────────────────────────────
  async function logoutAndLoginAs(page, email, password) {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // Click Logout if present
    const logoutBtn = page.getByRole("button", { name: "Logout" });
    if (await logoutBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await logoutBtn.click();
    }
    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", email);
    await page.fill("#password", password);
    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button'),
    ]);
    await page.waitForTimeout(2000);
  }

  // ──────────────────────────────────────────────────────────────────
  // 1. As base admin, create a new user with role = admin
  // ──────────────────────────────────────────────────────────────────
  test("1. Create user with admin role", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Open the Create User dialog
    const createButton = page
      .getByRole("button", { name: /create user/i })
      .first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for dialog
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    const emailInput = modal.locator('input[name="email"]');
    await expect(emailInput).toBeVisible({ timeout: 5_000 });

    // Wait for org dropdown to finish loading
    const orgSelect = modal.locator("select#organization");
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText(/loading organizations/i)
    ).not.toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(500);

    // Fill fields
    await modal.locator('input[name="email"]').fill(testAdminEmail);
    await modal.locator('input[name="name"]').fill(testAdminName);
    await modal.locator('input[name="password"]').fill(testAdminPassword);

    // Set Role → Admin
    await modal.locator('select[name="role"]').selectOption("admin");

    // Submit
    const submitButton = modal.getByRole("button", {
      name: /^create user$/i,
    });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for the success message
    await expect(
      page.getByText(/user created successfully/i)
    ).toBeVisible({ timeout: 15_000 });

    // Verify user appears in the list
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(testAdminEmail);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(testAdminEmail)).toBeVisible({
      timeout: 10_000,
    });
    console.log(`[admin_role_lifecycle] Created admin user: ${testAdminEmail}`);
  });

  // ──────────────────────────────────────────────────────────────────
  // 2. Login as the new admin — verify admin capabilities
  // ──────────────────────────────────────────────────────────────────
  test("2. New admin can access admin dashboard", async ({ page }) => {
    await logoutAndLoginAs(page, testAdminEmail, testAdminPassword);

    // Admin link should be visible in the nav
    await expect(page.getByRole("link", { name: "Admin" })).toBeVisible({
      timeout: 10_000,
    });

    // Navigate to admin dashboard
    await page.goto("admin");
    await page.waitForLoadState("networkidle");

    // Dashboard tab and stats should render (not a 403)
    await expect(
      page.getByRole("button", { name: "Dashboard" })
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByRole("button", { name: "Users", exact: true })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Organizations", exact: true })
    ).toBeVisible();

    // Quick-action buttons prove the stats API responded
    await expect(
      page.getByRole("button", { name: /refresh stats/i })
    ).toBeVisible({ timeout: 10_000 });

    console.log("[admin_role_lifecycle] Dashboard loads for new admin.");
  });

  test("3. New admin can access user management", async ({ page }) => {
    await logoutAndLoginAs(page, testAdminEmail, testAdminPassword);

    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // The user list should load (search box appears only after data arrives)
    await expect(
      page.locator('input[placeholder*="Search" i]')
    ).toBeVisible({ timeout: 15_000 });

    // Create User button proves full admin access
    await expect(
      page.getByRole("button", { name: /create user/i }).first()
    ).toBeVisible();

    console.log("[admin_role_lifecycle] User Management loads for new admin.");
  });

  test("4. New admin can access organizations", async ({ page }) => {
    await logoutAndLoginAs(page, testAdminEmail, testAdminPassword);

    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Organization list should load
    await expect(
      page.getByRole("button", { name: /create organization/i }).first()
    ).toBeVisible({ timeout: 15_000 });

    console.log("[admin_role_lifecycle] Organizations loads for new admin.");
  });

  // ──────────────────────────────────────────────────────────────────
  // 3. As base admin: verify self-disable is blocked, then disable new admin
  // ──────────────────────────────────────────────────────────────────
  test("5. Base admin cannot disable own account", async ({ page }) => {
    await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Wait for user list
    await expect(
      page.locator('input[placeholder*="Search" i]')
    ).toBeVisible({ timeout: 15_000 });

    // Search for the base admin email
    const searchBox = page.locator('input[placeholder*="Search" i]');
    await searchBox.fill(baseAdminEmail);
    await page.waitForTimeout(1000);

    // The base admin's row should be visible
    const selfRow = page.locator(`tr:has-text("${baseAdminEmail}")`);
    await expect(selfRow).toBeVisible({ timeout: 10_000 });

    // The UI hides the Disable/Enable button for the current user (self-disable prevention).
    // Verify the Disable button is NOT present in the current user's row.
    const disableBtn = selfRow.getByRole("button", {
      name: /disable/i,
    });
    await expect(disableBtn).not.toBeVisible({ timeout: 3_000 });

    // Also verify the checkbox for self-selection is disabled
    const selfCheckbox = selfRow.locator('input[type="checkbox"]');
    if (await selfCheckbox.count()) {
      await expect(selfCheckbox).toBeDisabled();
    }

    console.log(
      "[admin_role_lifecycle] Self-disable is correctly blocked."
    );
  });

  test("6. Base admin disables the new admin", async ({ page }) => {
    // Already logged in as base admin from prior test's storageState
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Wait for user list
    await expect(
      page.locator('input[placeholder*="Search" i]')
    ).toBeVisible({ timeout: 15_000 });

    // Search for new admin
    const searchBox = page.locator('input[placeholder*="Search" i]');
    await searchBox.fill(testAdminEmail);
    await page.waitForTimeout(1000);

    const userRow = page.locator(`tr:has-text("${testAdminEmail}")`);
    await expect(userRow).toBeVisible({ timeout: 10_000 });

    // Should show "Active" status
    await expect(userRow.getByText("Active")).toBeVisible();

    // Click disable
    const disableButton = userRow
      .getByRole("button", { name: /disable/i })
      .first();
    await expect(disableButton).toBeVisible({ timeout: 5_000 });
    await disableButton.click();

    // Confirm in modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await expect(
      modal.getByText(/disable user account/i)
    ).toBeVisible({ timeout: 5_000 });

    const confirmButton = modal.getByRole("button", {
      name: /^disable$/i,
    });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to close and status to change
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(userRow.getByText("Disabled")).toBeVisible({
      timeout: 10_000,
    });

    console.log(
      `[admin_role_lifecycle] ${testAdminEmail} disabled.`
    );
  });

  // ──────────────────────────────────────────────────────────────────
  // 4. Disabled admin cannot log in
  // ──────────────────────────────────────────────────────────────────
  test("7. Disabled admin cannot log in", async ({ page }) => {
    // Logout from base admin
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const logoutBtn = page.getByRole("button", { name: "Logout" });
    if (await logoutBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await logoutBtn.click();
    }
    await page.waitForSelector("#email", { timeout: 30_000 });

    // Attempt login as disabled admin
    await page.fill("#email", testAdminEmail);
    await page.fill("#password", testAdminPassword);
    await page.click('button[type="submit"], form button');

    // Should see an error (invalid credentials or account disabled)
    await expect(
      page.getByText(/invalid|disabled|error|denied/i).first()
    ).toBeVisible({ timeout: 10_000 });

    // Admin link should NOT be visible (user is not logged in)
    await expect(
      page.getByRole("link", { name: "Admin" })
    ).not.toBeVisible({ timeout: 3_000 });

    console.log(
      "[admin_role_lifecycle] Disabled admin correctly rejected."
    );
  });

  // ──────────────────────────────────────────────────────────────────
  // 5. Cleanup: re-enable and delete the test user
  // ──────────────────────────────────────────────────────────────────
  test("8. Cleanup: delete test admin user", async ({ page }) => {
    // Login as base admin
    await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator('input[placeholder*="Search" i]')
    ).toBeVisible({ timeout: 15_000 });

    // Search for test admin
    const searchBox = page.locator('input[placeholder*="Search" i]');
    await searchBox.fill(testAdminEmail);
    await page.waitForTimeout(1000);

    const userRow = page.locator(`tr:has-text("${testAdminEmail}")`);
    await expect(userRow).toBeVisible({ timeout: 10_000 });

    // Click Delete User
    const deleteButton = userRow
      .getByRole("button", { name: /delete user/i })
      .first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Wait for the delete confirmation (may be a dialog or a plain div)
    const confirmButton = page
      .getByRole("button", { name: /^delete$/i })
      .last();
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for user to disappear from the list
    await expect(userRow).not.toBeVisible({ timeout: 10_000 });

    console.log(
      `[admin_role_lifecycle] ${testAdminEmail} deleted.`
    );
  });
});
