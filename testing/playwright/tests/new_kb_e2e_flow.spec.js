const { test, expect } = require("@playwright/test");
const path = require("path");
// Load .env explicitly and silence tips/logging via quiet: true
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

test.describe.serial("New Knowledge Base E2E Flow", () => {
    const timestamp = Date.now();
    const kbName = `kb_e2e_test_${timestamp}`;
    const kbDescription = `Description for E2E test ${timestamp}`;

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

        // If login form is visible, log in with env vars or defaults
        if (await page.locator("#email").isVisible()) {
            const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@owi.com";
            const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "admin";

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

    test.use({ storageState: path.join(__dirname, "..", ".auth", "state.json") });

    test("Create a new Knowledge Base with dynamic name", async ({ page }) => {
        await page.goto("/");
        await page.waitForLoadState("networkidle");

        // Navigate to Knowledge Bases (if not already there, but usually we start from home)
        // Assuming there is a nav link or we just go to /knowledgebases directly like other tests
        await page.goto("knowledgebases");

        // Click Create button
        const createButton = page.getByRole("button", { name: /create knowledge base/i });
        await expect(createButton).toBeVisible({ timeout: 5000 });
        await createButton.click();

        // Wait for modal
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();

        // Fill form with dynamic data
        await page.getByRole("textbox", { name: /name \*/i }).fill(kbName);
        await page.getByRole("textbox", { name: /description/i }).fill(kbDescription);

        // Submit
        const submitButton = dialog.getByRole("button", { name: /create knowledge base/i });
        await submitButton.click();

        // Verify Creation
        // 1. Modal should close
        await expect(dialog).not.toBeVisible();

        // 2. KB should appear in the list with the dynamic name
        await expect(page.getByText(kbName)).toBeVisible({ timeout: 10000 });

        console.log(`Created KB: ${kbName}`);
    });

    test("Ingest content using Firecrawl (if key provided) or expect failure", async ({ page }) => {
        // 1. Navigate to the KB
        await page.goto("knowledgebases");
        await page.waitForLoadState("networkidle");

        const kbRow = page.locator("tr").filter({ hasText: kbName }).first();
        await expect(kbRow).toBeVisible();
        await kbRow.getByRole("button", { name: kbName }).click();

        // 2. Go to Ingest Content
        await page.getByRole("button", { name: /ingest content/i }).click();

        // 3. Select Firecrawl Plugin (Generic logic from url_ingest.spec.js)
        // We try to find a plugin that looks like Firecrawl or URL ingest
        const pluginSelect = page.locator("#plugin-select-inline");

        // Try to select Firecrawl specifically if possible, otherwise generic URL
        let firecrawlOption = pluginSelect.locator("option", { hasText: /firecrawl/i });
        if (await firecrawlOption.count() === 0) {
            // Fallback to generic URL if Firecrawl specific one isn't found
            firecrawlOption = pluginSelect.locator("option", { hasText: /url/i });
        }

        const optionValue = await firecrawlOption.first().getAttribute("value");
        await pluginSelect.selectOption(optionValue);

        // 4. Fill URL
        // We use the specific ID #param-url-inline because getByRole is ambiguous (matches multiple inputs)
        const urlInput = page.locator("#param-url-inline");
        await expect(urlInput).toBeVisible();
        await urlInput.fill("https://es.wikipedia.org/wiki/Lionel_Messi");

        // 5. Fill Firecrawl API Key (Logic copied from url_ingest.spec.js)
        // It checks environment variables. If key is missing, it skips filling it.
        const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || "";
        if (FIRECRAWL_API_KEY) {
            const apiKeyInput = page.locator("#param-api_key-inline");
            try {
                await apiKeyInput.waitFor({ timeout: 2000 });
                await apiKeyInput.fill(FIRECRAWL_API_KEY);
            } catch (e) {
                console.log("API Key input not found or optional");
            }
        }

        // 6. Run Ingestion
        await page.getByRole("button", { name: /run ingestion/i }).click();

        // 7. Verify Result based on whether we had a key
        if (FIRECRAWL_API_KEY) {
            // Happy Path: Key exists, should succeed
            await expect(page.getByText(/ingestion started/i)).toBeVisible({ timeout: 10000 });
            console.log("Firecrawl ingestion started (API Key was provided)");
        } else {
            // Sad Path: No Key, expecting failure
            // Navigate to Files to check status
            await page.getByRole("button", { name: /files/i }).click();

            const failedTag = page.getByRole("button", { name: /failed/i });
            // We expect it to fail within a reasonable time
            await expect(failedTag).toBeVisible({ timeout: 15000 });
            await failedTag.click();

            await expect(page.getByLabel("Ingestion Job Details")).toContainText(/no api key provided|failed to initialize/i);
            console.log("Firecrawl ingestion failed as expected (No API Key provided)");
        }
    });

    test("Ingest Invalid URL using Firecrawl (Expect 'No Content' Error)", async ({ page }) => {
        // Only run this test if we have an API Key, otherwise it's redundant with the previous test
        const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;

        if (!FIRECRAWL_API_KEY) {
            console.log("Skipping Invalid URL test because no API Key is provided");
            return;
        }

        // 1. Navigate to the KB
        await page.goto("knowledgebases");
        await page.waitForLoadState("networkidle");
        const kbRow = page.locator("tr").filter({ hasText: kbName }).first();
        await expect(kbRow).toBeVisible();
        await kbRow.getByRole("button", { name: kbName }).click();

        // 2. Go to Ingest Content
        await page.getByRole("button", { name: /ingest content/i }).click();

        // 3. Select Firecrawl Plugin
        const pluginSelect = page.locator("#plugin-select-inline");

        // Logic to select Firecrawl option specifically
        let firecrawlOption = pluginSelect.locator("option", { hasText: /firecrawl/i });
        if (await firecrawlOption.count() === 0) {
            firecrawlOption = pluginSelect.locator("option", { hasText: /url/i });
        }
        const optionValue = await firecrawlOption.first().getAttribute("value");
        await pluginSelect.selectOption(optionValue);

        // 4. Fill API Key from ENV
        const apiKeyInput = page.locator("#param-api_key-inline");
        try {
            await expect(apiKeyInput).toBeVisible({ timeout: 2000 });
            await apiKeyInput.fill(FIRECRAWL_API_KEY);
        } catch (e) {
            console.log("API Key input not visible, skipping fill");
        }

        // 5. Fill INVALID URL using the Specific ID selector
        const urlInput = page.locator("#param-url-inline");
        await urlInput.fill("https://ca.wiiipedia.org/wiki/Lionel_Andr%C3%A9s_Messi");

        // 6. Run Ingestion
        await page.getByRole("button", { name: /run ingestion/i }).click();

        // 7. Verify Failure Message
        await page.getByRole("button", { name: /files/i }).click();

        // Wait for failure
        const failedTag = page.getByRole("button", { name: /failed/i }).first();
        await expect(failedTag).toBeVisible({ timeout: 20000 });
        await failedTag.click();

        // Assert specific error message for invalid URL
        await expect(page.getByLabel("Ingestion Job Details")).toContainText(/no content could be extracted|400|failed to ingest file/i);

        console.log("Verified Firecrawl correctly handles Invalid URLs");
    });

    test("Query KB after Firecrawl ingestion to verify content", async ({ page }, testInfo) => {
        const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;
        if (!FIRECRAWL_API_KEY) {
            testInfo.skip(true, "Skipping query test — no FIRECRAWL_API_KEY provided");
            return;
        }

        // 1. Navigate to the KB detail
        await page.goto("knowledgebases");
        await page.waitForLoadState("networkidle");

        const kbRow = page.locator("tr").filter({ hasText: kbName }).first();
        await expect(kbRow).toBeVisible({ timeout: 5_000 });
        await kbRow.getByRole("button", { name: kbName }).click();

        // 2. Wait for async ingestion to complete before querying.
        // Instead of checking Files tab status, we go straight to Query
        // and retry with a generous timeout — if results come back,
        // ingestion worked.
        // Give Firecrawl ingestion some time to finish processing
        await page.waitForTimeout(15_000);

        // 3. Go to Query tab
        await page.getByRole("button", { name: "Query" }).click();

        // 4. Query for "messi" — the Wikipedia page we ingested is about Lionel Messi
        const queryInput = page.locator("#query-text");
        const queryInputAlt = page.getByRole("textbox", { name: /enter your query/i });

        // Use whichever query input is available
        if (await queryInput.isVisible().catch(() => false)) {
            await queryInput.fill("messi");
        } else {
            await queryInputAlt.fill("messi");
        }

        const submitBtn = page.getByRole("button", { name: /^Submit Query$/i });
        if (await submitBtn.count()) {
            await submitBtn.click();
        } else {
            await page.keyboard.press("Enter");
        }

        // 5. Verify that query results appear (embedding similarity search, no LLM)
        await expect(page.getByText(/Query Results:/i)).toBeVisible({ timeout: 60_000 });

        console.log("Query returned results for 'messi' — ingestion verified");
    });

    test("Ingest malformed URL (invalid protocol htps://)", async ({ page }, testInfo) => {
        const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;
        if (!FIRECRAWL_API_KEY) {
            testInfo.skip(true, "Skipping malformed URL test — no FIRECRAWL_API_KEY provided");
            return;
        }

        // 1. Navigate to the KB
        await page.goto("knowledgebases");
        await page.waitForLoadState("networkidle");

        const kbRow = page.locator("tr").filter({ hasText: kbName }).first();
        await expect(kbRow).toBeVisible({ timeout: 5_000 });
        await kbRow.getByRole("button", { name: kbName }).click();

        // 2. Go to Ingest Content
        await page.getByRole("button", { name: /ingest content/i }).click();

        // 3. Select Firecrawl Plugin
        const pluginSelect = page.locator("#plugin-select-inline");
        let firecrawlOption = pluginSelect.locator("option", { hasText: /firecrawl/i });
        if (await firecrawlOption.count() === 0) {
            firecrawlOption = pluginSelect.locator("option", { hasText: /url/i });
        }
        const optionValue = await firecrawlOption.first().getAttribute("value");
        await pluginSelect.selectOption(optionValue);

        // 4. Fill API Key
        const apiKeyInput = page.locator("#param-api_key-inline");
        try {
            await expect(apiKeyInput).toBeVisible({ timeout: 2_000 });
            await apiKeyInput.fill(FIRECRAWL_API_KEY);
        } catch (e) {
            console.log("API Key input not visible, skipping fill");
        }

        // 5. Fill MALFORMED URL — typo in protocol: htps instead of https
        const urlInput = page.locator("#param-url-inline");
        await urlInput.fill("htps://es.wikipedia.org/wiki/Lionel_Messi");

        // 6. Run Ingestion
        await page.getByRole("button", { name: /run ingestion/i }).click();

        // 7. Expect failure — either immediate UI validation error or async ingestion failure
        // Check for inline error first (some UIs validate URL format)
        const inlineError = page.getByText(/invalid url|invalid protocol|url must start with/i);
        const hasInlineError = await inlineError.isVisible({ timeout: 3_000 }).catch(() => false);

        if (hasInlineError) {
            console.log("UI correctly rejected malformed URL with validation error");
        } else {
            // If no inline error, check Files tab for ingestion failure
            await page.getByRole("button", { name: /files/i }).click();

            const failedTag = page.getByRole("button", { name: /failed/i }).first();
            await expect(failedTag).toBeVisible({ timeout: 20_000 });
            await failedTag.click();

            await expect(page.getByLabel("Ingestion Job Details")).toContainText(
                /invalid url|invalid protocol|failed|error/i
            );
            console.log("Firecrawl correctly rejected malformed URL (htps://)");
        }
    });

    test("Ingest unreachable URL (localhost that never responds)", async ({ page }, testInfo) => {
        const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;
        if (!FIRECRAWL_API_KEY) {
            testInfo.skip(true, "Skipping unreachable URL test — no FIRECRAWL_API_KEY provided");
            return;
        }

        // 1. Navigate to the KB
        await page.goto("knowledgebases");
        await page.waitForLoadState("networkidle");

        const kbRow = page.locator("tr").filter({ hasText: kbName }).first();
        await expect(kbRow).toBeVisible({ timeout: 5_000 });
        await kbRow.getByRole("button", { name: kbName }).click();

        // 2. Go to Ingest Content
        await page.getByRole("button", { name: /ingest content/i }).click();

        // 3. Select Firecrawl Plugin
        const pluginSelect = page.locator("#plugin-select-inline");
        let firecrawlOption = pluginSelect.locator("option", { hasText: /firecrawl/i });
        if (await firecrawlOption.count() === 0) {
            firecrawlOption = pluginSelect.locator("option", { hasText: /url/i });
        }
        const optionValue = await firecrawlOption.first().getAttribute("value");
        await pluginSelect.selectOption(optionValue);

        // 4. Fill API Key
        const apiKeyInput = page.locator("#param-api_key-inline");
        try {
            await expect(apiKeyInput).toBeVisible({ timeout: 2_000 });
            await apiKeyInput.fill(FIRECRAWL_API_KEY);
        } catch (e) {
            console.log("API Key input not visible, skipping fill");
        }

        // 5. Fill unreachable URL — localhost on a port that nothing listens on
        const urlInput = page.locator("#param-url-inline");
        await urlInput.fill("http://localhost:19999/this-page-does-not-exist");

        // 6. Run Ingestion
        await page.getByRole("button", { name: /run ingestion/i }).click();

        // 7. Expect failure — the URL is valid but unreachable
        await page.getByRole("button", { name: /files/i }).click();

        const failedTag = page.getByRole("button", { name: /failed/i }).first();
        await expect(failedTag).toBeVisible({ timeout: 30_000 });
        await failedTag.click();

        await expect(page.getByLabel("Ingestion Job Details")).toContainText(
            /no content could be extracted|connection refused|timeout|failed|error|unreachable/i
        );

        console.log("Firecrawl correctly failed on unreachable localhost URL");
    });

    test("Cleanup — delete test KB", async ({ page }) => {
        await page.goto("knowledgebases");
        await page.waitForLoadState("networkidle");

        const kbRow = page.locator("tr").filter({ hasText: kbName });
        if ((await kbRow.count()) === 0) {
            console.log("Test KB already deleted or not found — nothing to clean up");
            return;
        }

        const deleteButton = kbRow.getByRole("button", { name: "Delete" });
        await expect(deleteButton).toBeVisible({ timeout: 5_000 });
        await deleteButton.click();

        const modal = page.getByRole("dialog");
        await expect(modal).toBeVisible({ timeout: 3_000 });

        const confirmButton = modal.getByRole("button", { name: "Delete" });
        await expect(confirmButton).toBeVisible({ timeout: 2_000 });
        await confirmButton.click();

        await expect(modal).not.toBeVisible({ timeout: 5_000 });
        await expect(page.getByText(kbName)).not.toBeVisible({ timeout: 5_000 });

        console.log(`Cleanup: KB "${kbName}" deleted`);
    });
});
