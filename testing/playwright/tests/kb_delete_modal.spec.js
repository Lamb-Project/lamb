const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@owi.com";
const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "admin";

test.describe.serial("Knowledge Base Delete Modal", () => {
  const kbName = `pw_kb_delete_test_${Date.now()}`;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    
    // Navigate to the app - this will redirect to login if not authenticated
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    
    // Wait for either login form OR logout button (already logged in via stored state)
    await Promise.race([
      page.waitForSelector("#email", { timeout: 5_000 }).catch(() => null),
      page.waitForSelector("button:has-text('Logout')", { timeout: 5_000 }).catch(() => null),
    ]);
    
    // If login form is visible, log in
    if (await page.locator("#email").isVisible()) {
      await page.fill("#email", LOGIN_EMAIL);
      await page.fill("#password", LOGIN_PASSWORD);
      await page.click("form > button");
      await page.waitForLoadState("networkidle");
    }
    
    // Verify logged in
    await expect(page.locator("button", { hasText: /logout/i })).toBeVisible({ timeout: 5_000 });
    
    // Save storage state for subsequent tests
    await context.storageState({ path: path.join(__dirname, "..", ".auth", "state.json") });
    await context.close();
  });

  test("Create a test KB for deletion tests", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const createButton = page.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(createButton).toBeVisible({ timeout: 3_000 });
    await createButton.click();

    // Wait for the create dialog
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 2_000 });

    await page.getByLabel(/name\s*\*/i).fill(kbName);
    await page.getByLabel(/description/i).fill("Test KB for delete modal");

    const submitButton = dialog.getByRole("button", {
      name: /create knowledge base/i,
    });
    await submitButton.click();

    // Wait for dialog to close and KB to appear
    await expect(dialog).not.toBeVisible({ timeout: 3_000 });
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 5_000 });
  });

  test("Delete modal shows when clicking Delete button", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find the row with our test KB and click its Delete button
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: 3_000 });

    // Find the Delete button - use text selector for reliability
    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: 2_000 });
    await deleteButton.click();

    // The confirmation modal should appear (using ConfirmationModal component)
    // It should have a dialog role and contain "Delete" in the title/text
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });

    // Check modal contains expected elements - use specific selectors
    await expect(modal.locator("h3")).toContainText(/delete/i);
    await expect(modal.locator("p")).toContainText(kbName);

    // Check for Cancel and Confirm/Delete buttons
    const cancelButton = modal.locator("button", { hasText: /cancel/i });
    const confirmButton = modal.locator("button", { hasText: /delete/i });
    await expect(cancelButton).toBeVisible({ timeout: 2_000 });
    await expect(confirmButton).toBeVisible({ timeout: 2_000 });
  });

  test("Cancel button closes modal without deleting", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and click Delete on our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: 3_000 });

    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: 2_000 });
    await deleteButton.click();

    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });

    // Click Cancel
    const cancelButton = modal.locator("button", { hasText: /cancel/i });
    await expect(cancelButton).toBeVisible({ timeout: 2_000 });
    await cancelButton.click();

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 2_000 });

    // KB should still be in the list
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 2_000 });
  });

  test("Clicking outside modal closes it (optional behavior)", async ({
    page,
  }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and click Delete
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: 3_000 });
    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: 2_000 });
    await deleteButton.click();

    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });

    // Press Escape to close (standard modal behavior)
    await page.keyboard.press("Escape");

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 2_000 });

    // KB should still exist
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 2_000 });
  });

  test("Confirm button deletes the KB", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and click Delete on our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: 3_000 });

    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: 2_000 });
    await deleteButton.click();

    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });

    // Click the Delete/Confirm button in the modal
    const confirmButton = modal.locator("button", { hasText: /delete/i });
    await expect(confirmButton).toBeVisible({ timeout: 2_000 });
    await confirmButton.click();

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 3_000 });

    // KB should be removed from the list
    await expect(page.getByText(kbName)).not.toBeVisible({ timeout: 3_000 });
  });
});
