const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@owi.com";
const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "admin";
const UI_SHORT = 5_000;
const UI_MEDIUM = 10_000;
const UI_LONG = 30_000;

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
      page.waitForSelector("#email", { timeout: UI_SHORT }).catch(() => null),
      page.waitForSelector("button:has-text('Logout')", { timeout: UI_SHORT }).catch(() => null),
    ]);
    
    // If login form is visible, log in
    if (await page.locator("#email").isVisible()) {
      await page.fill("#email", LOGIN_EMAIL);
      await page.fill("#password", LOGIN_PASSWORD);
      await page.click("form > button");
      await page.waitForLoadState("networkidle");
    }
    
    // Verify logged in
    await expect(page.locator("button", { hasText: /logout/i })).toBeVisible({
      timeout: UI_SHORT,
    });
    
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
    await expect(createButton).toBeVisible({ timeout: UI_MEDIUM });
    await createButton.click();

    // Wait for the create dialog
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: UI_SHORT });

    await page.getByLabel(/name\s*\*/i).fill(kbName);
    await page.getByLabel(/description/i).fill("Test KB for delete modal");

    const submitButton = dialog.getByRole("button", {
      name: /create knowledge base/i,
    });
    await submitButton.click();

    // First confirm the KB appears in the table, then the modal closes.
    // This ordering is more resilient when backend/API is slower.
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: UI_LONG });
    await expect(dialog).not.toBeVisible({ timeout: UI_MEDIUM });
  });

  test("Delete modal shows when clicking Delete button", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find the row with our test KB and click its Delete button
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: UI_MEDIUM });

    // Find the Delete button - use text selector for reliability
    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: UI_SHORT });
    await deleteButton.click();

    // The confirmation modal should appear (using ConfirmationModal component)
    // It should have a dialog role and contain "Delete" in the title/text
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: UI_SHORT });

    // Check modal contains expected elements - use specific selectors
    await expect(modal.locator("h3")).toContainText(/delete/i);
    await expect(modal.locator("p")).toContainText(kbName);

    // Check for Cancel and Confirm/Delete buttons
    const cancelButton = modal.locator("button", { hasText: /cancel/i });
    const confirmButton = modal.locator("button", { hasText: /delete/i });
    await expect(cancelButton).toBeVisible({ timeout: UI_SHORT });
    await expect(confirmButton).toBeVisible({ timeout: UI_SHORT });
  });

  test("Cancel button closes modal without deleting", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and click Delete on our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: UI_MEDIUM });

    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: UI_SHORT });
    await deleteButton.click();

    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: UI_SHORT });

    // Click Cancel
    const cancelButton = modal.locator("button", { hasText: /cancel/i });
    await expect(cancelButton).toBeVisible({ timeout: UI_SHORT });
    await cancelButton.click();

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: UI_SHORT });

    // KB should still be in the list
    await expect(page.getByText(kbName)).toBeVisible({ timeout: UI_SHORT });
  });

  test("Clicking outside modal closes it (optional behavior)", async ({
    page,
  }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and click Delete
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: UI_MEDIUM });
    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: UI_SHORT });
    await deleteButton.click();

    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: UI_SHORT });

    // Press Escape to close (standard modal behavior)
    await page.keyboard.press("Escape");

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: UI_SHORT });

    // KB should still exist
    await expect(page.getByText(kbName)).toBeVisible({ timeout: UI_SHORT });
  });

  test("Confirm button deletes the KB", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and click Delete on our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: UI_MEDIUM });

    const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
    await expect(deleteButton).toBeVisible({ timeout: UI_SHORT });
    await deleteButton.click();

    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: UI_SHORT });

    // Click the Delete/Confirm button in the modal
    const confirmButton = modal.locator("button", { hasText: /delete/i });
    await expect(confirmButton).toBeVisible({ timeout: UI_SHORT });
    await confirmButton.click();

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: UI_MEDIUM });

    // KB should be removed from the list
    await expect(page.locator("tr").filter({ hasText: kbName })).not.toBeVisible({
      timeout: UI_MEDIUM,
    });
  });
});
