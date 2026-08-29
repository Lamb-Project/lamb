const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

/**
 * Cache-Aware Single File RAG Tests
 *
 * Validates the cache-aware single_file_rag feature that emits RAG context
 * as a separate user message BEFORE conversation history, enabling LLM
 * providers to cache the stable prefix and reduce token costs.
 *
 * Test flow:
 *   1. Create an assistant configured with single_file_rag and a fixture file
 *   2. Chat: send two messages in the same session — both use file content
 *   3. Cleanup: delete the assistant
 *
 * Prerequisites:
 *   - Logged in as admin via global-setup.js
 *   - Backend has single_file_rag plugin enabled (PLUGIN_SINGLE_FILE_RAG=ENABLE)
 */

test.describe.serial("Cache-Aware Single File RAG", () => {
  const timestamp = Date.now();
  const assistantName = `pw_sfrag_${timestamp}`;
  const fixtureFileName = "single_file_rag_fixture.txt";

  // ─────────────────────────────────────────────────────────────────────
  // 1. Create assistant with single_file_rag + fixture file
  // ─────────────────────────────────────────────────────────────────────
  test("1. Create assistant with single_file_rag and upload fixture file", async ({
    page,
  }) => {
    await page.goto("assistants?view=create");
    await page.waitForLoadState("networkidle");

    const createButton = page
      .getByRole("button", { name: /create assistant/i })
      .first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Fill basic fields
    await page.fill("#assistant-name", assistantName);
    await page.fill(
      "#assistant-description",
      "Playwright test for cache-aware single_file_rag",
    );
    await page.fill(
      "#system-prompt",
      "You are a helpful assistant. Answer questions based on the provided document.",
    );

    // Select single_file_rag from the RAG processor dropdown
    const ragSelect = page.locator("#rag-processor");
    await expect(ragSelect).toBeVisible({ timeout: 15_000 });
    await ragSelect.selectOption("single_file_rag");

    // Wait for the file selector to appear (SingleFileSelector component)
    // The file upload input has id="file-upload"
    const fileUploadInput = page.locator("#file-upload");
    await expect(fileUploadInput).toBeVisible({ timeout: 10_000 });

    // Upload the fixture file
    const fixturePath = path.join(
      __dirname,
      "..",
      "fixtures",
      fixtureFileName,
    );
    await fileUploadInput.setInputFiles(fixturePath);

    // Wait for the async upload to complete (the "Uploading..." text disappears)
    const uploadingIndicator = page.getByText(/uploading/i);
    await uploadingIndicator.waitFor({ state: "hidden", timeout: 15_000 }).catch(() => {
      // May disappear quickly or never appear — continue either way
    });

    // Wait for the uploaded file to appear as a radio option and select it
    const fileRadio = page.getByRole("radio", { name: fixtureFileName });
    await expect(fileRadio).toBeVisible({ timeout: 15_000 });
    await fileRadio.check();

    // Wait for the create_assistant API response
    const createRequest = page.waitForResponse((response) => {
      if (response.request().method() !== "POST") return false;
      try {
        const url = new URL(response.url());
        return (
          url.pathname.endsWith("/assistant/create_assistant") &&
          response.status() >= 200 &&
          response.status() < 300
        );
      } catch {
        return false;
      }
    });

    // Wait for Save button to be enabled
    const saveButton = page.locator(
      'button[type="submit"][form="assistant-form-main"]',
    );
    await expect(saveButton).toBeEnabled({ timeout: 60_000 });

    // Submit the form
    await Promise.all([createRequest, form.evaluate((f) => f.requestSubmit())]);

    // Verify we land back on the assistants list
    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

    // Search for the newly created assistant
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    await expect(page.getByText(assistantName).first()).toBeVisible({
      timeout: 30_000,
    });
  });

  // ─────────────────────────────────────────────────────────────────────
  // 2. Chat — two messages in the same session (validates cache-aware pipeline)
  // ─────────────────────────────────────────────────────────────────────
  test("2. Chat: two messages in same session both use file content", async ({
    page,
  }) => {
    // Navigate to assistants list and find our assistant
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    // Click the assistant name to open detail view
    const assistantRow = page.locator(`tr:has-text("${assistantName}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });

    const nameButton = assistantRow
      .getByRole("button", { name: new RegExp(assistantName, "i") })
      .first();
    if (await nameButton.count()) {
      await nameButton.click();
    } else {
      await assistantRow.click();
    }

    await page.waitForLoadState("networkidle");

    // Click the Chat tab
    const chatTab = page.getByRole("button", { name: /chat with/i });
    await expect(chatTab).toBeVisible({ timeout: 10_000 });
    await chatTab.click();

    // Wait for chat input to appear
    const chatInput = page.getByPlaceholder(/type your message/i);
    await expect(chatInput).toBeVisible({ timeout: 15_000 });

    // ── Message 1 ──────────────────────────────────────────────────
    await chatInput.fill("What is the name of the platform mascot?");
    const sendButton = page.getByRole("button", { name: /^send$/i });
    await expect(sendButton).toBeVisible({ timeout: 5_000 });
    await sendButton.click();

    // Wait for completed assistant response (prose div = streaming done)
    const assistantProse = page.locator(".bg-gray-200 .prose");
    await expect(assistantProse.first()).toBeVisible({ timeout: 120_000 });

    const response1 = await assistantProse.last().textContent();
    console.log(`[single_file_rag] Msg 1: ${response1?.substring(0, 300)}`);
    expect(response1.toLowerCase()).toMatch(/lambda|llama|mascot|graduation/);

    // ── Message 2 (same session — cache-aware prefix reused) ───────
    await chatInput.fill(
      "How many registered users does the platform have as of June 2026?",
    );
    await expect(sendButton).toBeVisible({ timeout: 5_000 });
    await sendButton.click();

    // Wait for a NEW prose element to appear (second response).
    // We can't just check .first() — it still matches the first response.
    const proseElements = page.locator(".bg-gray-200 .prose");
    await expect(proseElements).toHaveCount(2, { timeout: 120_000 });

    const response2 = await proseElements.last().textContent();
    console.log(`[single_file_rag] Msg 2: ${response2?.substring(0, 300)}`);
    expect(response2).toMatch(/12,?847|12847|twelve thousand/);
  });

  // ─────────────────────────────────────────────────────────────────────
  // 3. Cleanup: delete the assistant
  // ─────────────────────────────────────────────────────────────────────
  test("3. Delete the test assistant", async ({ page }) => {
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    const assistantRow = page.locator(`tr:has-text("${assistantName}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });

    // Click the delete button
    const deleteButton = assistantRow
      .getByRole("button", { name: /delete/i })
      .first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Wait for the confirmation modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await expect(modal.getByText(/delete assistant/i)).toBeVisible();

    // Confirm deletion
    const confirmDeleteButton = modal.getByRole("button", {
      name: /^delete$/i,
    });
    await expect(confirmDeleteButton).toBeVisible({ timeout: 5_000 });
    await confirmDeleteButton.click();

    // Wait for modal to close and assistant to be removed
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(assistantRow).not.toBeVisible({ timeout: 10_000 });

    console.log(`Assistant "${assistantName}" successfully deleted.`);
  });
});
