const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@owi.com";
const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "admin";

test.describe.serial("Knowledge Base Detail Modals", () => {
  const kbName = `pw_kb_detail_modals_${Date.now()}`;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    
    await Promise.race([
      page.waitForSelector("#email", { timeout: 5_000 }).catch(() => null),
      page.waitForSelector("button:has-text('Logout')", { timeout: 5_000 }).catch(() => null),
    ]);
    
    if (await page.locator("#email").isVisible()) {
      await page.fill("#email", LOGIN_EMAIL);
      await page.fill("#password", LOGIN_PASSWORD);
      await page.click("form > button");
      await page.waitForLoadState("networkidle");
    }
    
    await expect(page.locator("button", { hasText: /logout/i })).toBeVisible({ timeout: 5_000 });
    await context.storageState({ path: path.join(__dirname, "..", ".auth", "state.json") });
    await context.close();
  });

  test("Create a test KB with a file for modal tests", async ({ page }) => {
    // Create KB
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const createButton = page.getByRole("button", { name: /create knowledge base/i });
    await expect(createButton).toBeVisible({ timeout: 3_000 });
    await createButton.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 2_000 });

    await page.getByLabel(/name\s*\*/i).fill(kbName);
    await page.getByLabel(/description/i).fill("Test KB for detail modals");

    const submitButton = dialog.getByRole("button", { name: /create knowledge base/i });
    await submitButton.click();

    await expect(dialog).not.toBeVisible({ timeout: 3_000 });
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 5_000 });

    // Navigate to KB detail
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await kbRow.locator("button", { hasText: kbName }).click();
    
    // Wait for detail view
    await expect(page.getByRole("heading", { name: /knowledge base details/i })).toBeVisible({ timeout: 5_000 });

    // Go to Ingest tab and upload a file
    await page.getByRole("button", { name: /ingest content/i }).click();
    
    // Upload fixture file
    const fixturePath = path.join(__dirname, "..", "fixtures", "ikasiker_fixture.txt");
    await page.locator("#file-upload-input-inline").setInputFiles(fixturePath);
    
    // Wait for file to be selected
    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({ timeout: 5_000 });

    // Plugin parameters have sensible defaults — just click Upload
    await page.getByRole("button", { name: /upload file/i }).click();
    
    // Wait for success
    await expect(page.getByText(/file uploaded and ingestion started successfully/i)).toBeVisible({ timeout: 60_000 });
  });

  test("Delete file modal shows when clicking Delete button", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Navigate to our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: 3_000 });
    await kbRow.locator("button", { hasText: kbName }).click();
    
    // Wait for detail view
    await expect(page.getByRole("heading", { name: /knowledge base details/i })).toBeVisible({ timeout: 5_000 });
    
    // Go to Files tab
    await page.getByRole("button", { name: /^Files$/i }).click();
    
    // Wait for files to load - look for the file we uploaded
    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({ timeout: 10_000 });
    
    // Click delete on the file
    const deleteButton = page.locator("button", { hasText: /delete/i }).first();
    await expect(deleteButton).toBeVisible({ timeout: 3_000 });
    await deleteButton.click();
    
    // Confirmation modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });
    
    // Modal should contain delete-related text
    await expect(modal.locator("h3")).toContainText(/delete/i);
    
    // Check for Cancel and Delete/Confirm buttons
    const cancelButton = modal.locator("button", { hasText: /cancel/i });
    const confirmButton = modal.locator("button", { hasText: /delete/i });
    await expect(cancelButton).toBeVisible({ timeout: 2_000 });
    await expect(confirmButton).toBeVisible({ timeout: 2_000 });
  });

  test("Cancel button closes delete file modal without deleting", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Navigate to our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await kbRow.locator("button", { hasText: kbName }).click();
    
    await expect(page.getByRole("heading", { name: /knowledge base details/i })).toBeVisible({ timeout: 5_000 });
    
    // Go to Files tab
    await page.getByRole("button", { name: /^Files$/i }).click();
    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({ timeout: 10_000 });
    
    // Click delete
    const deleteButton = page.locator("button", { hasText: /delete/i }).first();
    await deleteButton.click();
    
    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });
    
    // Click Cancel
    const cancelButton = modal.locator("button", { hasText: /cancel/i });
    await cancelButton.click();
    
    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 2_000 });
    
    // File should still be there
    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({ timeout: 2_000 });
  });

  test("Confirm button deletes the file", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Navigate to our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    await kbRow.locator("button", { hasText: kbName }).click();
    
    await expect(page.getByRole("heading", { name: /knowledge base details/i })).toBeVisible({ timeout: 5_000 });
    
    // Go to Files tab
    await page.getByRole("button", { name: /^Files$/i }).click();
    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({ timeout: 10_000 });
    
    // Click delete
    const deleteButton = page.locator("button", { hasText: /delete/i }).first();
    await deleteButton.click();
    
    // Modal should appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 2_000 });
    
    // Click Delete/Confirm
    const confirmButton = modal.locator("button", { hasText: /delete/i });
    await confirmButton.click();
    
    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 3_000 });
    
    // File should be gone (or show "no files" message)
    await expect(page.getByText("ikasiker_fixture.txt")).not.toBeVisible({ timeout: 5_000 });
  });

  test("Cleanup - delete test KB", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find and delete our test KB
    const kbRow = page.locator("tr").filter({ hasText: kbName });
    if (await kbRow.count() > 0) {
      const deleteButton = kbRow.locator("button.text-red-600", { hasText: /delete/i });
      await deleteButton.click();
      
      const modal = page.getByRole("dialog");
      await expect(modal).toBeVisible({ timeout: 2_000 });
      
      const confirmButton = modal.locator("button", { hasText: /delete/i });
      await confirmButton.click();
      
      await expect(modal).not.toBeVisible({ timeout: 3_000 });
      await expect(page.getByText(kbName)).not.toBeVisible({ timeout: 3_000 });
    }
  });
});
