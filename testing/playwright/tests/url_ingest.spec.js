const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const TEST_URL =
  process.env.TEST_URL ||
  "https://www.cervantesvirtual.com/obra-visor/the-political-constitution-of-the-spanish-monarchy-promulgated-in-cadiz-the-nineteenth-day-of-march--0/html/ffd04084-82b1-11df-acc7-002185ce6064_1.html";
const TEST_KB_BASE_NAME = process.env.KB_NAME || "url_test";
const TEST_QUERY =
  process.env.TEST_QUERY ||
  "What did the article number 14 in the Spanish Constitution of 1812 say?";
const INGESTION_WAIT_TIME = process.env.INGESTION_WAIT_TIME
  ? parseInt(process.env.INGESTION_WAIT_TIME, 10)
  : 2000;
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || "";
const FIRECRAWL_API_URL = process.env.FIRECRAWL_API_URL || "";
const FIRECRAWL_QUERY = process.env.FIRECRAWL_QUERY || "false";

test.describe.serial("URL ingestion and query verification", () => {
  let createdKbName;
  let createdKbId = null;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    // Navigate to the app - this will redirect to login if not authenticated
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait for either login form OR logout button (already logged in via stored state)
    await Promise.race([
      page.waitForSelector("#email", { timeout: 5_000 }).catch(() => null),
      page
        .waitForSelector("button:has-text('Logout')", { timeout: 5_000 })
        .catch(() => null),
    ]);

    // If login form is visible, log in
    if (await page.locator("#email").isVisible()) {
      const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@owi.com";
      const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "admin";

      await page.fill("#email", LOGIN_EMAIL);
      await page.fill("#password", LOGIN_PASSWORD);
      await page.click("form > button");
      await page.waitForLoadState("networkidle");
    }

    // Verify logged in
    await expect(page.locator("button", { hasText: /logout/i })).toBeVisible({
      timeout: 5_000,
    });

    // Save storage state for subsequent tests
    await context.storageState({
      path: path.join(__dirname, "..", ".auth", "state.json"),
    });
    await context.close();
  });

  test.use({ storageState: path.join(__dirname, "..", ".auth", "state.json") });

  test("Create knowledge base for URL ingestion", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle", { timeout: 30_000 });

    // Find available KB name (url_test, url_test_1, url_test_2, etc.)
    let counter = 0;
    let kbNameAvailable = false;

    while (!kbNameAvailable) {
      const testName =
        counter === 0 ? TEST_KB_BASE_NAME : `${TEST_KB_BASE_NAME}_${counter}`;
      const existingKb = page.getByRole("button", { name: testName });
      const exists = (await existingKb.count()) > 0;

      if (!exists) {
        createdKbName = testName;
        kbNameAvailable = true;
      } else {
        counter++;
      }

      if (counter > 100) {
        throw new Error("Could not find available KB name after 100 attempts");
      }
    }

    // Click "Create Knowledge Base" button
    const createKbButton = page
      .getByRole("button", {
        name: /Crear Base de Conocimiento|Create Knowledge Base/i,
      })
      .first();
    await expect(createKbButton).toBeVisible({ timeout: 5_000 });
    await createKbButton.click();

    // Fill in KB name
    const kbNameInput = page.locator("#kb-name");
    await expect(kbNameInput).toBeVisible();
    await kbNameInput.fill(createdKbName);

    // Submit KB creation
    const submitButton = page.locator("div.fixed button.border-transparent", {
      hasText: /Crear Base de Conocimiento|Create Knowledge Base/i,
    });
    await expect(submitButton).toBeVisible();
    await submitButton.click();

    // Wait for KB to be created and visible in the list
    await page.waitForTimeout(2000);

    // Click on the newly created KB to open it
    const kbLink = page.getByRole("button", { name: createdKbName });
    await expect(kbLink).toBeVisible({ timeout: 5_000 });
    await kbLink.click();
    await page.waitForLoadState("networkidle");

    // Extract KB ID from URL
    const currentUrl = page.url();
    const kbIdMatch = currentUrl.match(/[?&]id=(\d+)/);
    if (kbIdMatch) {
      createdKbId = kbIdMatch[1];
    }

    // Verify we're on the KB detail page
    await expect(
      page.getByRole("button", { name: /Ingest Content/i }),
    ).toBeVisible();
  });

  test("Ingest URL content", async ({ page }) => {
    // Assume KB is already created from previous test, navigate to it
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const kbLink = page.getByRole("button", { name: createdKbName });
    await expect(kbLink).toBeVisible({ timeout: 5_000 });
    await kbLink.click();
    await page.waitForLoadState("networkidle");

    // Click "Ingest Content" tab
    const ingestButton = page.getByRole("button", { name: /Ingest Content/i });
    await expect(ingestButton).toBeVisible();
    await ingestButton.click();
    await page.waitForTimeout(1000);

    // Select URL ingestion plugin
    const pluginSelect = page.locator("#plugin-select-inline");
    await expect(pluginSelect).toBeVisible();

    // Select by text content instead of value for better reliability
    const urlIngestOption = pluginSelect.locator("option", { hasText: /url/i });
    const urlIngestValue = await urlIngestOption.getAttribute("value");
    await pluginSelect.selectOption(urlIngestValue);
    await page.waitForTimeout(500);

    // Fill URL
    const urlInput = page.locator("#param-url-inline");
    await expect(urlInput).toBeVisible();
    await urlInput.fill(TEST_URL);

    // Fill Firecrawl API key if provided
    if (FIRECRAWL_API_KEY) {
      const apiKeyInput = page.locator("#param-api_key-inline");
      try {
        await apiKeyInput.waitFor({ timeout: 2000 });
        await apiKeyInput.fill(FIRECRAWL_API_KEY);
      } catch (e) {
        // API key input not found, might be optional
      }
    }

    // Click "Run Ingestion"
    const runButton = page.locator("div.border-t > div.px-4 button", {
      hasText: /Run Ingestion/i,
    });
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for success message
    await expect(
      page.getByText(
        /File uploaded and ingestion started successfully!|Ingestion started/i,
      ),
    ).toBeVisible({ timeout: 10_000 });

    // Navigate to Files tab to verify ingestion started
    const filesButton = page.getByRole("button", { name: /^Files$/i });
    await expect(filesButton).toBeVisible();
    await filesButton.click();
    await page.waitForTimeout(2000);

    // Verify at least one file is listed
    const fileRows = page.locator("table tbody tr");
    const rowCount = await fileRows.count();
    expect(rowCount).toBeGreaterThan(0);
  });

  if (FIRECRAWL_QUERY === "true") {
    test("Wait for ingestion to complete", async ({ page }) => {
      // This test just waits for the ingestion process to complete
      // In a real scenario, you might want to poll for completion status
      test.info().annotations.push({
        type: "info",
        description: `Waiting ${INGESTION_WAIT_TIME / 1000} seconds for ingestion to complete`,
      });

      await page.waitForTimeout(INGESTION_WAIT_TIME);
    });

    test("Verify JSON response status is success", async ({ page }) => {
      // Navigate to the KB
      await page.goto("knowledgebases");
      await page.waitForLoadState("networkidle");

      const kbLink = page.getByRole("button", { name: createdKbName });
      await expect(kbLink).toBeVisible({ timeout: 5_000 });
      await kbLink.click();
      await page.waitForLoadState("networkidle");

      // Click "Show Raw JSON Response" button
      const jsonButton = page.getByRole("button", {
        name: /Show Raw JSON Response/i,
      });
      await expect(jsonButton).toBeVisible();
      await jsonButton.click();
      await page.waitForTimeout(1000);

      // Check if JSON response is visible
      const jsonContainer = page.locator("pre");
      await expect(jsonContainer).toBeVisible({ timeout: 10_000 });

      // Get the JSON text content
      const jsonText = await jsonContainer.textContent();

      // Verify that the JSON contains "status": "success"
      expect(jsonText).toContain('"status": "success"');

      // Also verify it contains the expected URL
      expect(jsonText).toContain(TEST_URL);
    });
  }

  test("Delete knowledge base", async ({ page }) => {
    // Navigate to knowledge bases list
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Find the KB we created
    const kbLink = page.getByRole("button", { name: createdKbName });
    await expect(kbLink).toBeVisible({ timeout: 5_000 });

    // Find the delete button in the same row as the KB
    // Use .filter() to narrow to the specific row containing our KB
    const tableRows = page.locator("table tbody tr");
    const kbRow = tableRows.filter({ hasText: createdKbName });
    const deleteButton = kbRow.getByRole("button", { name: "Delete" });

    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Confirm deletion in the dialog
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    const confirmDeleteButton = dialog.getByRole("button", { name: "Delete" });
    await expect(confirmDeleteButton).toBeVisible();
    await confirmDeleteButton.click();

    // Wait for success message
    await expect(page.getByText("Knowledge base deleted")).toBeVisible({
      timeout: 10_000,
    });

    // Verify the KB is no longer in the list
    await expect(kbLink).not.toBeVisible({ timeout: 5_000 });
  });
});
