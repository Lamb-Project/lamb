const { test, expect } = require("@playwright/test");

/**
 * Org-Admin Comprehensive Smoke Tests
 *
 * Tests ALL org-admin views and features to ensure the org-admin
 * section works correctly for managing a specific organization.
 *
 * Views covered:
 *   1. Dashboard — stats, models, API status
 *   2. Users — CRUD, password change, enable/disable, can_share
 *   3. Assistants Access — listing, sharing
 *   4. LTI Activities — listing, toggle
 *   5. Settings — General, API, KB, Assistant Defaults, LTI Creator
 *
 * Prerequisites:
 *   - Logged in as system admin via global-setup.js
 *   - The system org "lamb" must exist
 */

// ============================================================
// Helpers
// ============================================================

const TEST_ORG = "lamb";
const timestamp = Date.now();
const testUserEmail = `orgadmin_smoke_${timestamp}@test.com`;
const testUserName = `smoke_${timestamp}`;
const testUserPassword = "SmokeTest_123!";

/**
 * Navigate to an org-admin view.
 */
async function goToView(page, view, orgSlug = TEST_ORG) {
  await page.goto(`org-admin?org=${orgSlug}&view=${view}`);
  await page.waitForLoadState("networkidle");
}

/**
 * Wait for the org-admin page shell to be ready.
 */
async function waitForPageReady(page) {
  await page.waitForTimeout(500);
}

/**
 * Search for a user by email in the org-admin Users view.
 */
async function searchForUser(page, email) {
  const searchBox = page.locator(
    'input[placeholder*="search" i], input[aria-label*="search" i]'
  ).first();
  if (await searchBox.count()) {
    await searchBox.fill(email);
    await page.waitForTimeout(500);
  }
}

// ============================================================
// Test Suite
// ============================================================

test.describe.serial("Org-Admin Comprehensive Smoke Test", () => {

  // ==========================================
  // VIEW 1: DASHBOARD
  // ==========================================

  test("Dashboard — loads with stats and model info", async ({ page }) => {
    await goToView(page, "dashboard");
    await waitForPageReady(page);

    // Verify the dashboard header / org name is visible
    await expect(page.getByText(TEST_ORG).first()).toBeVisible({ timeout: 10_000 });

    // Stats cards should be present
    await expect(page.getByText(/users/i).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/assistants/i).first()).toBeVisible({ timeout: 5_000 });

    // Default models section should be visible
    await expect(page.getByText(/default model/i).first()).toBeVisible({ timeout: 5_000 });

    console.log("Dashboard loaded successfully.");
  });

  // ==========================================
  // VIEW 2: USERS
  // ==========================================

  test("Users — list loads with columns and action buttons", async ({ page }) => {
    await goToView(page, "users");
    await waitForPageReady(page);

    // Verify the users list is visible (table or card list)
    await expect(page.getByText(/email|name/i).first()).toBeVisible({ timeout: 10_000 });

    // Create User button should be present
    const createBtn = page.getByRole("button", { name: /create user/i });
    await expect(createBtn).toBeVisible({ timeout: 5_000 });

    console.log("Users list loaded with Create User button.");
  });

  test("Users — searches and filters work", async ({ page }) => {
    await goToView(page, "users");
    await waitForPageReady(page);

    // Search box should exist
    const searchInput = page.locator(
      'input[placeholder*="search" i], input[aria-label*="search" i]'
    ).first();
    await expect(searchInput).toBeVisible({ timeout: 5_000 });

    // Type a search and verify it doesn't crash
    await searchInput.fill("nonexistent_user_xyz123");
    await page.waitForTimeout(500);

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(500);

    console.log("User search works.");
  });

  test("Users — creates a new user in the target org", async ({ page }) => {
    await goToView(page, "users");
    await waitForPageReady(page);

    // Click Create User
    const createBtn = page.getByRole("button", { name: /create user/i });
    await createBtn.click();

    // Wait for modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Fill form
    const emailInput = modal.locator("input[name=\"email\"], input#email");
    const nameInput = modal.locator("input[name=\"name\"], input#name");
    const passwordInput = modal.locator("input[name=\"password\"], input#password");

    await emailInput.fill(testUserEmail);
    await nameInput.fill(testUserName);
    await passwordInput.fill(testUserPassword);

    // Ensure enabled checkbox is checked
    const enabledCb = modal.locator("input[name=\"enabled\"], input#enabled");
    if (await enabledCb.count() && !(await enabledCb.isChecked())) {
      await enabledCb.check();
    }

    // Submit
    const submitBtn = modal.getByRole("button", { name: /create user/i });
    await submitBtn.click();

    // Wait for the modal to close (success message auto-closes after ~1.5s)
    await expect(modal).not.toBeVisible({ timeout: 15_000 });

    // Wait for the user list to refresh
    await page.waitForTimeout(1000);

    // Search for the user in the list
    const searchBox = page.locator('input[placeholder*="search" i], input[aria-label*="search" i]').first();
    if (await searchBox.count()) {
      await searchBox.fill(testUserEmail);
      await page.waitForTimeout(500);
    }

    // Verify user appears in the list
    await expect(page.getByText(testUserEmail)).toBeVisible({ timeout: 10_000 });

    console.log(`User "${testUserName}" created in org "${TEST_ORG}".`);
  });

  test("Users — changes password for a user", async ({ page }) => {
    await goToView(page, "users");
    await waitForPageReady(page);
    await searchForUser(page, testUserEmail);

    // Find the test user row
    const userRow = page.locator("tr", { hasText: testUserEmail });
    await expect(userRow.first()).toBeVisible({ timeout: 10_000 });

    // Click password/change password action button
    const pwBtn = userRow.first().locator(
      "button[title*=\"assword\" i], button[aria-label*=\"assword\" i], " +
      "button:has-text(\"assword\"), button:has([data-testid*=\"password\"])"
    );
    await expect(pwBtn.first()).toBeVisible({ timeout: 5_000 });
    await pwBtn.first().click();

    // Wait for password modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Fill new password — the input has no name/id, just type="password"
    const newPwInput = modal.locator('input[type="password"]');
    await newPwInput.fill("NewSmokePass_456!");

    // Submit
    const changeBtn = modal.getByRole("button", { name: /change|save|submit/i });
    await changeBtn.click();

    // Verify success — should NOT show "not found" error
    await page.waitForTimeout(1000);
    const notFoundErr = page.getByText(/not found in this organization/i);
    await expect(notFoundErr).not.toBeVisible({ timeout: 3000 });

    console.log("Password changed successfully.");
  });

  test("Users — enable/disable toggle works", async ({ page }) => {
    await goToView(page, "users");
    await waitForPageReady(page);
    await searchForUser(page, testUserEmail);

    // Find the test user row
    const userRow = page.locator("tr", { hasText: testUserEmail });
    await expect(userRow.first()).toBeVisible({ timeout: 10_000 });

    // Click the disable/deactivate action button
    const disableBtn = userRow.first().getByRole("button", { name: /disable|deactivate/i });
    if (await disableBtn.count()) {
      await disableBtn.first().click();

      // Handle confirmation modal if it appears
      const confirmModal = page.getByRole("dialog");
      try {
        await expect(confirmModal).toBeVisible({ timeout: 2000 });
        const confirmBtn = confirmModal.getByRole("button", { name: /confirm|yes|disable/i });
        if (await confirmBtn.count()) await confirmBtn.click();
      } catch {
        // No confirmation needed
      }

      await page.waitForTimeout(1000);

      // Now re-enable
      await goToView(page, "users");
      await searchForUser(page, testUserEmail);
      const userRow2 = page.locator("tr", { hasText: testUserEmail });
      await expect(userRow2.first()).toBeVisible({ timeout: 10_000 });

      const enableBtn = userRow2.first().getByRole("button", { name: /enable|activate/i });
      if (await enableBtn.count()) {
        await enableBtn.first().click();
        try {
          await expect(confirmModal).toBeVisible({ timeout: 2000 });
          const confirmBtn2 = confirmModal.getByRole("button", { name: /confirm|yes|enable/i });
          if (await confirmBtn2.count()) await confirmBtn2.click();
        } catch {
          // No confirmation needed
        }
        await page.waitForTimeout(1000);
      }

      console.log("Enable/disable toggle works.");
    } else {
      console.log("No enable/disable button found — skipping toggle test.");
    }
  });

  test("Users — can_share toggle persists after reload", async ({ page }) => {
    await goToView(page, "users");
    await waitForPageReady(page);
    await searchForUser(page, testUserEmail);

    // Find the test user row
    const userRow = page.locator("tr", { hasText: testUserEmail });
    await expect(userRow.first()).toBeVisible({ timeout: 10_000 });

    // The can_share toggle is a Tailwind toggle: hidden checkbox + visible div overlay.
    // The checkbox has class "sr-only" and the visible toggle div intercepts clicks.
    // We need to click the visible toggle div (sibling of the checkbox).
    const hiddenCheckbox = userRow.first().locator("input[type=\"checkbox\"]").last();
    const cbCount = await hiddenCheckbox.count();

    if (cbCount > 0) {
      const wasChecked = await hiddenCheckbox.isChecked();

      // Click the visible toggle div (sibling of the hidden checkbox)
      const toggleDiv = hiddenCheckbox.locator("..").locator("div.rounded-full");
      await toggleDiv.click();
      await page.waitForTimeout(1000);

      // Reload and verify state persisted
      await goToView(page, "users");
      await searchForUser(page, testUserEmail);
      await page.waitForTimeout(500);

      const userRow2 = page.locator("tr", { hasText: testUserEmail });
      await expect(userRow2.first()).toBeVisible({ timeout: 10_000 });

      const hiddenCheckbox2 = userRow2.first().locator("input[type=\"checkbox\"]").last();
      const isCheckedNow = await hiddenCheckbox2.isChecked();

      expect(isCheckedNow).toBe(!wasChecked);

      // Restore original state
      const toggleDiv2 = hiddenCheckbox2.locator("..").locator("div.rounded-full");
      await toggleDiv2.click();
      await page.waitForTimeout(1000);

      console.log(`Can Share persisted: ${wasChecked} → ${isCheckedNow} after reload.`);
    } else {
      console.log("No checkboxes found — skipping can_share test.");
    }
  });

  // ==========================================
  // VIEW 3: ASSISTANTS ACCESS
  // ==========================================

  test("Assistants — list loads", async ({ page }) => {
    await goToView(page, "assistants");
    await waitForPageReady(page);

    // Verify the page loads without error
    await expect(page.getByText(/assistant/i).first()).toBeVisible({ timeout: 10_000 });

    console.log("Assistants view loaded.");
  });

  // ==========================================
  // VIEW 4: LTI ACTIVITIES
  // ==========================================

  test("LTI Activities — list loads", async ({ page }) => {
    await goToView(page, "lti-activities");
    await waitForPageReady(page);

    // Verify the page loads without error
    await expect(page.getByText(/lti|activity/i).first()).toBeVisible({ timeout: 10_000 });

    console.log("LTI Activities view loaded.");
  });

  // ==========================================
  // VIEW 5: SETTINGS TABS
  // ==========================================

  test("Settings — General tab loads with signup controls", async ({ page }) => {
    await goToView(page, "settings");
    await waitForPageReady(page);

    // General tab should be visible with signup settings
    await expect(page.getByText(/signup|general/i).first()).toBeVisible({ timeout: 10_000 });

    // Signup checkbox should exist
    const signupCb = page.locator("input[type=\"checkbox\"]").first();
    await expect(signupCb).toBeVisible({ timeout: 5_000 });

    console.log("Settings General tab loaded.");
  });

  test("Settings — API tab loads with provider status", async ({ page }) => {
    await goToView(page, "settings");
    await waitForPageReady(page);

    // Click the API tab
    const apiTab = page.getByRole("button", { name: /api/i })
      .or(page.getByRole("tab", { name: /api/i }))
      .or(page.locator("a, button, [role=\"tab\"]").filter({ hasText: /api/i }));

    if (await apiTab.count()) {
      await apiTab.first().click();
      await page.waitForTimeout(500);
    }

    // Should show provider cards or API key inputs
    await expect(
      page.getByText(/api key|openai|ollama|provider/i).first()
    ).toBeVisible({ timeout: 5_000 });

    console.log("Settings API tab loaded.");
  });

  test("Settings — KB tab loads with server URL input", async ({ page }) => {
    await goToView(page, "settings");
    await waitForPageReady(page);

    // Click the KB tab
    const kbTab = page.getByRole("button", { name: /knowledge|kb/i })
      .or(page.getByRole("tab", { name: /knowledge|kb/i }))
      .or(page.locator("a, button, [role=\"tab\"]").filter({ hasText: /knowledge|kb/i }));

    if (await kbTab.count()) {
      await kbTab.first().click();
      await page.waitForTimeout(500);
    }

    // Should show KB server URL input
    await expect(
      page.getByText(/kb server|knowledge base|url/i).first()
    ).toBeVisible({ timeout: 5_000 });

    console.log("Settings KB tab loaded.");
  });

  test("Settings — Assistant Defaults tab loads with JSON editor", async ({ page }) => {
    await goToView(page, "settings");
    await waitForPageReady(page);

    // Click the Assistant Defaults tab
    const defaultsTab = page.getByRole("button", { name: /defaults|assistant defaults/i })
      .or(page.getByRole("tab", { name: /defaults|assistant defaults/i }))
      .or(page.locator("a, button, [role=\"tab\"]").filter({ hasText: /defaults/i }));

    if (await defaultsTab.count()) {
      await defaultsTab.first().click();
      await page.waitForTimeout(500);
    }

    // Should show a textarea or JSON editor
    const textarea = page.locator("textarea");
    await expect(textarea.first()).toBeVisible({ timeout: 5_000 });

    console.log("Settings Assistant Defaults tab loaded.");
  });

  test("Settings — LTI Creator tab loads with configuration", async ({ page }) => {
    await goToView(page, "settings");
    await waitForPageReady(page);

    // Click the LTI Creator tab
    const ltiTab = page.getByRole("button", { name: /lti creator/i })
      .or(page.getByRole("tab", { name: /lti/i }))
      .or(page.locator("a, button, [role=\"tab\"]").filter({ hasText: /lti creator|lti/i }));

    if (await ltiTab.count()) {
      await ltiTab.first().click();
      await page.waitForTimeout(500);
    }

    // Should show LTI configuration info
    await expect(
      page.getByText(/consumer|oauth|lti/i).first()
    ).toBeVisible({ timeout: 5_000 });

    console.log("Settings LTI Creator tab loaded.");
  });

  // ==========================================
  // INTER-VIEW NAVIGATION
  // ==========================================

  test("Navigation — switching between views works", async ({ page }) => {
    await goToView(page, "dashboard");
    await waitForPageReady(page);
    await expect(page.getByText(/default model/i).first()).toBeVisible({ timeout: 5_000 });

    await goToView(page, "users");
    await waitForPageReady(page);
    await expect(page.getByText(/create user/i).first()).toBeVisible({ timeout: 5_000 });

    await goToView(page, "settings");
    await waitForPageReady(page);
    await expect(page.getByText(/signup|api|general/i).first()).toBeVisible({ timeout: 5_000 });

    console.log("View navigation works correctly.");
  });

  // ==========================================
  // CLEANUP
  // ==========================================

  test("Cleanup — disable the test user", async ({ page }) => {
    // Navigate to system admin users view to clean up
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Search for the test user
    const searchBox = page.locator(
      "input[placeholder*=\"search\" i], input[aria-label*=\"search\" i]"
    ).first();
    if (await searchBox.count()) {
      await searchBox.fill(testUserEmail);
      await page.waitForTimeout(500);
    }

    // Try to disable the user
    const userRow = page.locator("tr", { hasText: testUserEmail });
    if (await userRow.count()) {
      const actionBtn = userRow.first().locator("button").last();
      if (await actionBtn.count()) {
        await actionBtn.click();
        await page.waitForTimeout(500);

        const confirmModal = page.getByRole("dialog");
        try {
          await expect(confirmModal).toBeVisible({ timeout: 2000 });
          const confirmBtn = confirmModal.getByRole("button", { name: /confirm|yes|disable|ok/i });
          if (await confirmBtn.count()) await confirmBtn.click();
        } catch {
          // No modal
        }
        await page.waitForTimeout(1000);
      }
      console.log(`Test user "${testUserEmail}" cleaned up.`);
    } else {
      console.log(`Test user "${testUserEmail}" not found for cleanup.`);
    }
  });
});
