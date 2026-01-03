const { test, expect } = require("@playwright/test");
const path = require("path");
// Load .env explicitly and silence tips/logging via quiet: true
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

test.describe.serial("Creator flow (KB + ingest + query + assistant)", () => {
  const kbName = `pw_kb_${Date.now()}`;
  const assistantName = `pw_asst_${Date.now()}`;

  test("Create knowledge base", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const createButton = page.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the dialog to appear
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    await page.getByLabel(/name\s*\*/i).fill(kbName);
    await page.getByLabel(/description/i).fill("Playwright CI knowledge base");

    const submitButton = dialog.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for dialog to close and KB to appear in list
    await expect(dialog).not.toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 30_000 });
  });

  test("Open KB detail", async ({ page }) => {
    await page.goto("knowledgebases");

    // Click the KB row/card by its unique name.
    await page.getByText(kbName, { exact: false }).first().click();

    // The page should show some detail UI; keep it generic.
    await expect(
      page.getByRole("button", { name: /ingest content/i })
    ).toBeVisible();
  });

  test("Ingest fixture file", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.getByText(kbName, { exact: false }).first().click();

    await page.getByRole("button", { name: /ingest content/i }).click();

    const fixturePath = path.join(
      __dirname,
      "..",
      "fixtures",
      "ikasiker_fixture.txt"
    );
    await page.locator("#file-upload-input-inline").setInputFiles(fixturePath);

    // The UI should show the selected filename.
    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({
      timeout: 10_000,
    });

    await page
      .locator("#param-description-inline")
      .fill("Fixture file for CI ingestion");
    await page.locator("#param-citation-inline").fill("Ikasiker Fixture");

    await page.locator("div.border-t > div.px-4 button").click();

    // After clicking Upload, the UI shows a success banner.
    await expect(
      page.getByText(/file uploaded and ingestion started successfully/i)
    ).toBeVisible({ timeout: 60_000 });
  });

  test("Query KB (smoke)", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.getByText(kbName, { exact: false }).first().click();

    await page.getByRole("button", { name: /^Query$/ }).click();
    await page
      .locator("#query-text")
      .fill("¿Cuántas becas Ikasiker se convocan?");

    // Prefer the explicit button if present.
    const submit = page.getByRole("button", { name: /^Submit Query$/ });
    if (await submit.count()) {
      await submit.click();
    } else {
      await page.keyboard.press("Enter");
    }

    await expect(page.getByText(/Query Results:/i)).toBeVisible({
      timeout: 60_000,
    });
  });

  test("Create assistant (smoke)", async ({ page }) => {
    await page.goto("assistants?view=create");

    await page.getByRole("button", { name: "Create Assistant" }).click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Fill only required fields to avoid scroll loop issues with optional RAG/KB configuration
    await page.fill("#assistant-name", assistantName);
    await page.fill("#assistant-description", "Playwright CI assistant");
    await page.fill("#system-prompt", "You are a helpful assistant.");

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

    // Wait for Save button to be enabled (system capabilities loaded)
    const saveButton = page.locator(
      'button[type="submit"][form="assistant-form-main"]'
    );
    await expect(saveButton).toBeEnabled({ timeout: 60_000 });

    // Submit the form and wait for API response
    await Promise.all([createRequest, form.evaluate((f) => f.requestSubmit())]);

    // The app navigates back to the assistants list after creation
    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

    // Search for the newly created assistant to confirm it exists
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500); // Brief wait for search filter to apply
    }

    await expect(page.getByText(assistantName).first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("Delete assistant", async ({ page }) => {
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    // Search for the assistant to ensure it's visible
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    // Find and click the delete button for the assistant
    // The delete button should be in the actions column for the assistant row
    const assistantRow = page.locator(`text=${assistantName}`).first();
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });

    // Click the delete button (trash icon)
    const deleteButton = page
      .locator(`tr:has-text("${assistantName}")`)
      .getByRole("button", { name: /delete/i })
      .first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Wait for the custom delete confirmation modal to appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await expect(modal.getByText(/delete assistant/i)).toBeVisible();

    // Click the "Delete" button in the modal
    const confirmDeleteButton = modal.getByRole("button", {
      name: /^delete$/i,
    });
    await expect(confirmDeleteButton).toBeVisible({ timeout: 5_000 });
    await confirmDeleteButton.click();

    // Wait for the modal to close and assistant to be removed from the list
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(assistantRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Assistant "${assistantName}" successfully deleted.`);
  });

  test("Delete knowledge base", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Search for the KB to ensure it's visible
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(kbName);
      await page.waitForTimeout(500);
    }

    // Find the KB row
    const kbRow = page.locator(`text=${kbName}`).first();
    await expect(kbRow).toBeVisible({ timeout: 10_000 });

    // Click the delete button
    const deleteButton = page
      .locator(`tr:has-text("${kbName}")`)
      .getByRole("button", { name: /delete/i })
      .first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });

    // Set up dialog handler BEFORE clicking delete
    page.once("dialog", async (dialog) => {
      console.log("Confirm dialog:", dialog.message());
      await dialog.accept();
    });

    await deleteButton.click();

    // Wait for the KB to be removed from the list
    await expect(kbRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Knowledge base "${kbName}" successfully deleted.`);
  });

  test("Assistant chat responds with expected answer", async ({ page }) => {
    // Read assistant id from environment (must be set in tests/.env)
    const ASSISTANT_ID = process.env.ASSISTANT_ID || "";
    if (!ASSISTANT_ID) {
      throw new Error("ASSISTANT_ID must be set in the tests/.env file.");
    }
    const targetUrl = `assistants?view=detail&id=${ASSISTANT_ID}`;

    await page.goto(targetUrl);
    await page.waitForLoadState("networkidle");

    // Click the Chat tab (fuzzy match)
    const chatTab = page.getByText(/Chat with/i).first();
    await expect(chatTab).toBeVisible({ timeout: 10_000 });
    await chatTab.click();

    // Wait for chat input
    const input = page.getByPlaceholder(/Type your message/i);
    await expect(input).toBeVisible({ timeout: 10_000 });

    // Type the question and send
    await input.fill("Cuántas becas se convocan?");
    const send = page.getByRole("button", { name: /^Send$/ });
    await expect(send).toBeVisible({ timeout: 5_000 });
    await send.click();

    // Wait for answer to appear (short wait then longer timeout check)
    await page.waitForTimeout(5_000);
    await expect(page.getByText(/190/)).toBeVisible({ timeout: 60_000 });
  });
});
