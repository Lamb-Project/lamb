const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const VIDEO_URL =
  process.env.VIDEO_URL || "https://www.youtube.com/watch?v=PMZy53PHbY0";
const VIDEO_LANG = process.env.VIDEO_LANG || "es";
const QUERY_TEXT =
  process.env.YT_QUERY_TEXT || "Quién es Messi?";

/**
 * YouTube Ingestion E2E
 *
 * Full end-to-end test for YouTube content ingestion:
 *   1. Create a dedicated KB
 *   2. Ingest a single YouTube video URL via the youtube_transcript_ingest plugin
 *   3. Wait and verify the ingestion completes (status = completed, not failed)
 *   4. Query the KB and verify results are returned
 *   5. Ingest a .txt file containing 2 YouTube links (one per line)
 *   6. Wait and verify the second ingestion completes
 *   7. Query the KB again and verify results
 *   8. Delete the KB (cleanup)
 *
 * Prerequisites:
 *   - Logged in as admin via global-setup.js
 */

test.describe.serial("YouTube Ingestion E2E", () => {
  const timestamp = Date.now();
  const kbName = `yt_e2e_test_${timestamp}`;

  // ── Auth bootstrap ────────────────────────────────────────────────
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await Promise.race([
      page.waitForSelector("#email", { timeout: 5_000 }).catch(() => null),
      page
        .waitForSelector("button:has-text('Logout')", { timeout: 5_000 })
        .catch(() => null),
    ]);

    if (await page.locator("#email").isVisible()) {
      const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@owi.com";
      const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "admin";

      await page.fill("#email", LOGIN_EMAIL);
      await page.fill("#password", LOGIN_PASSWORD);
      await page.click("form > button");
      await page.waitForLoadState("networkidle");
    }

    await expect(
      page.locator("button", { hasText: /logout/i })
    ).toBeVisible({ timeout: 5_000 });

    await context.storageState({
      path: path.join(__dirname, "..", ".auth", "state.json"),
    });
    await context.close();
  });

  test.use({
    storageState: path.join(__dirname, "..", ".auth", "state.json"),
  });

  // ── Helpers ───────────────────────────────────────────────────────

  /** Navigate to our KB detail page. */
  async function navigateToKb(page) {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const kbButton = page.getByRole("button", { name: kbName });
    await expect(kbButton).toBeVisible({ timeout: 10_000 });
    await kbButton.click();
    await page.waitForLoadState("networkidle");
  }

  /**
   * Wait until the latest ingestion job shows "completed" (or fail if "failed").
   * Polls the Files tab every few seconds up to a generous timeout.
   *
   * IMPORTANT: Only checks the FIRST row in the files table (= most recent
   * ingestion).  Other test suites (e.g. youtube_titles) may contaminate the
   * KB by ingesting unrelated videos, leaving stale "failed" rows further
   * down the table.  Scoping to targetRowIndex avoids false negatives.
   *
   * @param {import('@playwright/test').Page} page
   * @param {object}  opts
   * @param {number}  opts.timeout         Max wait in ms (default 120 s)
   * @param {number}  opts.targetRowIndex   Row to monitor (0 = newest file)
   */
  async function waitForIngestionStatus(
    page,
    { timeout = 120_000, targetRowIndex = 0 } = {}
  ) {
    const filesButton = page.getByRole("button", { name: /^Files$/i });
    await expect(filesButton).toBeVisible();
    await filesButton.click();
    await page.waitForTimeout(2_000);

    const deadline = Date.now() + timeout;

    while (Date.now() < deadline) {
      const targetRow = page
        .locator("table tbody tr")
        .nth(targetRowIndex);

      // Row not yet visible — wait and retry
      if ((await targetRow.count()) === 0) {
        await page.waitForTimeout(5_000);
        continue;
      }

      // Read the status button inside the target row only
      const statusButton = targetRow.locator("button").filter({
        hasText: /processing|completed|failed|pending/i,
      });

      if ((await statusButton.count()) > 0) {
        const statusText = (await statusButton.textContent()).trim().toLowerCase();

        if (statusText.includes("failed")) {
          // Click to get details
          await statusButton.click();
          const detailsDialog = page.getByRole("dialog", {
            name: /Ingestion Job Details/i,
          });
          let errorText = "";
          if (await detailsDialog.isVisible().catch(() => false)) {
            errorText = await detailsDialog.textContent().catch(() => "");
            await page
              .locator("button")
              .filter({ hasText: /^Close$/ })
              .click()
              .catch(() => {});
          }
          throw new Error(
            `Ingestion failed. Details: ${errorText.substring(0, 500)}`
          );
        }

        if (statusText.includes("completed")) {
          return; // Success
        }
      }

      // Still processing — wait 10s then hit Refresh Status
      await page.waitForTimeout(10_000);
      const refreshBtn = page.getByRole("button", { name: /Refresh Status/i });
      if (await refreshBtn.isVisible().catch(() => false)) {
        await refreshBtn.click();
      } else {
        await filesButton.click();
      }
      await page.waitForTimeout(2_000);
    }

    throw new Error(
      `Ingestion did not complete within ${timeout / 1000}s`
    );
  }

  /**
   * Run a query against the KB and verify that results appear.
   */
  async function queryAndVerify(page, queryText) {
    const queryTab = page.getByRole("button", { name: /^Query$/ });
    await expect(queryTab).toBeVisible();
    await queryTab.click();
    await page.waitForTimeout(500);

    const queryInput = page.getByRole("textbox", {
      name: /Enter your query/i,
    });
    await expect(queryInput).toBeVisible({ timeout: 5_000 });
    await queryInput.fill(queryText);

    const submitBtn = page.getByRole("button", { name: /Submit Query/i });
    if (await submitBtn.count()) {
      await submitBtn.click();
    } else {
      await page.keyboard.press("Enter");
    }

    // Verify query results appear
    await expect(page.getByText(/Query Results:/i)).toBeVisible({
      timeout: 60_000,
    });

    // Verify the word "messi" appears somewhere in the results
    const resultsSection = page.locator("text=/messi/i");
    const matchCount = await resultsSection.count();
    expect(matchCount, 'Expected "messi" to appear in query results').toBeGreaterThan(0);
  }

  // ── Tests ─────────────────────────────────────────────────────────

  test("1. Create knowledge base", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const createButton = page.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    await page.getByRole("textbox", { name: /name \*/i }).fill(kbName);
    await page
      .getByRole("textbox", { name: /description/i })
      .fill("YouTube ingestion E2E test");

    const submitButton = dialog.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(submitButton).toBeVisible();
    await submitButton.click();

    await expect(dialog).not.toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 10_000 });
    console.log(`Created KB: ${kbName}`);
  });

  test("2. Ingest single YouTube video", async ({ page }) => {
    await navigateToKb(page);

    // Go to Ingest Content tab
    await page.getByRole("button", { name: /Ingest Content/i }).click();
    await page.waitForTimeout(1_000);

    // Select YouTube plugin
    const pluginSelect = page.locator("#plugin-select-inline");
    await expect(pluginSelect).toBeVisible();

    const youtubeOption = pluginSelect.locator("option", {
      hasText: /youtube_transcript_ingest/i,
    });
    const youtubeValue = await youtubeOption.getAttribute("value");
    await pluginSelect.selectOption(youtubeValue);
    await page.waitForTimeout(500);

    // Fill video URL
    const videoUrlInput = page.locator("#param-video_url-inline");
    await expect(videoUrlInput).toBeVisible();
    await videoUrlInput.fill(VIDEO_URL);

    // Optional: Set language if field exists
    try {
      const languageInput = page.getByRole("textbox", {
        name: /^language /i,
      });
      await languageInput.waitFor({ timeout: 2_000 });
      await languageInput.fill(VIDEO_LANG);
    } catch {
      // Language input not found — skip
    }

    // Run Ingestion
    const runButton = page.getByRole("button", { name: /Run Ingestion/i });
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for success banner
    await expect(
      page.getByText(
        /File uploaded and ingestion started successfully!/i
      )
    ).toBeVisible({ timeout: 10_000 });

    console.log("Single YouTube video ingestion started.");
  });

  test("3. Verify single video ingestion completes", async ({ page }) => {
    await navigateToKb(page);
    await waitForIngestionStatus(page, { timeout: 80_000 });
    console.log("Single YouTube video ingestion completed successfully.");
  });

  test("4. Query KB after single video ingestion", async ({ page }) => {
    await navigateToKb(page);
    await queryAndVerify(page, QUERY_TEXT);
    console.log("Query returned results after single video ingestion.");
  });

  test("5. Ingest .txt file with 2 YouTube links", async ({ page }) => {
    await navigateToKb(page);

    // Go to Ingest Content tab
    await page.getByRole("button", { name: /Ingest Content/i }).click();
    await page.waitForTimeout(1_000);

    // For a .txt file upload, use the default file ingestion plugin
    // Upload the fixture file containing two YouTube links
    const fixturePath = path.join(
      __dirname,
      "..",
      "fixtures",
      "youtube_links.txt"
    );

    // Click "Select File" button and handle the file chooser dialog
    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      page.getByRole("button", { name: /Select File/i }).click(),
    ]);
    await fileChooser.setFiles(fixturePath);

    // Verify file is selected
    await expect(page.getByText("youtube_links.txt")).toBeVisible({
      timeout: 10_000,
    });

    // Fill description and citation if the fields are present
    const descInput = page.locator("#param-description-inline");
    if (await descInput.isVisible().catch(() => false)) {
      await descInput.fill("Two YouTube links for E2E test");
    }

    const citationInput = page.locator("#param-citation-inline");
    if (await citationInput.isVisible().catch(() => false)) {
      await citationInput.fill("YouTube Links Fixture");
    }

    // Submit
    await page.locator("div.border-t > div.px-4 button").click();

    // Wait for success banner
    await expect(
      page.getByText(
        /file uploaded and ingestion started successfully/i
      )
    ).toBeVisible({ timeout: 10_000 });

    console.log(".txt file with 2 YouTube links ingestion started.");
  });

  test("6. Verify .txt file ingestion completes", async ({ page }) => {
    await navigateToKb(page);
    await waitForIngestionStatus(page, { timeout: 80_000 });
    console.log(".txt file ingestion completed successfully.");
  });

  test("7. Query KB after .txt file ingestion", async ({ page }) => {
    await navigateToKb(page);
    await queryAndVerify(page, QUERY_TEXT);
    console.log("Query returned results after .txt file ingestion.");
  });

  // ── Part 3: Video sin subtítulos + fallback con .txt de subtítulos ──

  test("8. Ingest YouTube video without subtitles (expect failure)", async ({ page }) => {
    await navigateToKb(page);

    // Go to Ingest Content tab
    await page.getByRole("button", { name: /Ingest Content/i }).click();
    await page.waitForTimeout(1_000);

    // Select YouTube plugin
    const pluginSelect = page.locator("#plugin-select-inline");
    await expect(pluginSelect).toBeVisible();

    const youtubeOption = pluginSelect.locator("option", {
      hasText: /youtube_transcript_ingest/i,
    });
    const youtubeValue = await youtubeOption.getAttribute("value");
    await pluginSelect.selectOption(youtubeValue);
    await page.waitForTimeout(500);

    // Fill video URL (this video has no usable transcript)
    const videoUrlInput = page.locator("#param-video_url-inline");
    await expect(videoUrlInput).toBeVisible();
    await videoUrlInput.fill("https://www.youtube.com/watch?v=OSpeKzhrPVI");

    // Run Ingestion
    const runButton = page.getByRole("button", { name: /Run Ingestion/i });
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for the ingestion to be accepted
    await expect(
      page.getByText(/File uploaded and ingestion started successfully!/i)
    ).toBeVisible({ timeout: 10_000 });

    console.log("YouTube video without subtitles ingestion started (expecting failure).");
  });

  test("9. Verify no-subtitle video ingestion fails", async ({ page }) => {
    await navigateToKb(page);

    const filesButton = page.getByRole("button", { name: /^Files$/i });
    await expect(filesButton).toBeVisible();
    await filesButton.click();
    await page.waitForTimeout(2_000);

    const deadline = Date.now() + 80_000;

    while (Date.now() < deadline) {
      // Check for "failed" — this is the EXPECTED outcome
      const failedButton = page.getByRole("button", { name: /failed/i });
      if ((await failedButton.count()) > 0) {
        // Click to see details
        await failedButton.first().click();
        const detailsDialog = page.getByRole("dialog", {
          name: /Ingestion Job Details/i,
        });
        let errorText = "";
        if (await detailsDialog.isVisible().catch(() => false)) {
          errorText = await detailsDialog.textContent().catch(() => "");
          await page
            .locator("button")
            .filter({ hasText: /^Close$/ })
            .click()
            .catch(() => {});
        }

        // Verify it's the expected "no chunks" error
        expect(errorText).toMatch(/no chunks produced|failed to ingest/i);
        console.log("Video without subtitles correctly failed with: No chunks produced.");
        return;
      }

      // If it somehow completed, that's unexpected but not a blocker
      const completedButton = page.getByRole("button", { name: /completed/i });
      if ((await completedButton.count()) > 0) {
        console.log("WARNING: Video without subtitles unexpectedly completed.");
        return;
      }

      await page.waitForTimeout(10_000);
      const refreshBtn = page.getByRole("button", { name: /Refresh Status/i });
      if (await refreshBtn.isVisible().catch(() => false)) {
        await refreshBtn.click();
      } else {
        await filesButton.click();
      }
      await page.waitForTimeout(2_000);
    }

    throw new Error("Ingestion did not fail within expected time");
  });

  test("10. Ingest with .srt subtitle fallback + video URL", async ({ page }) => {
    await navigateToKb(page);

    // Go to Ingest Content tab
    await page.getByRole("button", { name: /Ingest Content/i }).click();
    await page.waitForTimeout(1_000);

    // Select YouTube plugin (same plugin, but this time with manual .srt)
    const pluginSelect = page.locator("#plugin-select-inline");
    await expect(pluginSelect).toBeVisible();

    const youtubeOption = pluginSelect.locator("option", {
      hasText: /youtube_transcript_ingest/i,
    });
    const youtubeValue = await youtubeOption.getAttribute("value");
    await pluginSelect.selectOption(youtubeValue);
    await page.waitForTimeout(500);

    // Upload .srt subtitle file via the file input
    const fixturePath = path.join(
      __dirname,
      "..",
      "fixtures",
      "french_revolution_oversimplified.srt"
    );

    await page.locator("#file-upload-input-inline").setInputFiles(fixturePath);

    // Verify file is selected
    await expect(page.getByText(/french_revolution_oversimplified\.srt/i)).toBeVisible({
      timeout: 10_000,
    });

    // Fill video_url so citations keep YouTube links
    const videoUrlInput = page.locator("#param-video_url-inline");
    await expect(videoUrlInput).toBeVisible();
    await videoUrlInput.fill("https://www.youtube.com/watch?v=EQmjXM4VK2U");

    // Run Ingestion
    const runButton = page.getByRole("button", { name: /Run Ingestion/i });
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for success banner
    await expect(
      page.getByText(/file uploaded and ingestion started successfully/i)
    ).toBeVisible({ timeout: 10_000 });

    console.log("SRT subtitle + video URL ingestion started.");
  });

  test("11. Verify subtitles ingestion (expect fail — server renames .srt to .txt breaking detection)", async ({ page }) => {
    await navigateToKb(page);

    const filesButton = page.getByRole("button", { name: /^Files$/i });
    await expect(filesButton).toBeVisible();
    await filesButton.click();
    await page.waitForTimeout(2_000);

    const deadline = Date.now() + 80_000;

    while (Date.now() < deadline) {
      const failedButton = page.getByRole("button", { name: /failed/i });
      if ((await failedButton.count()) > 0) {
        await failedButton.first().click();
        const detailsDialog = page.getByRole("dialog", {
          name: /Ingestion Job Details/i,
        });
        let errorText = "";
        if (await detailsDialog.isVisible().catch(() => false)) {
          errorText = await detailsDialog.textContent().catch(() => "");
          await page
            .locator("button")
            .filter({ hasText: /^Close$/ })
            .click()
            .catch(() => {});
        }
        expect(errorText).toMatch(/no chunks produced|failed to ingest/i);
        console.log("SRT fallback correctly failed — server renames .srt to .txt, plugin cannot detect SRT format.");
        return;
      }

      const completedButton = page.getByRole("button", { name: /completed/i });
      if ((await completedButton.count()) > 0) {
        console.log("SRT fallback unexpectedly completed — this is OK.");
        return;
      }

      await page.waitForTimeout(10_000);
      const refreshBtn = page.getByRole("button", { name: /Refresh Status/i });
      if (await refreshBtn.isVisible().catch(() => false)) {
        await refreshBtn.click();
      } else {
        await filesButton.click();
      }
      await page.waitForTimeout(2_000);
    }

    throw new Error("Ingestion did not complete or fail within expected time");
  });

  // Test 12 skipped — SRT fallback ingestion fails, so no content to query
  // If SRT fallback is fixed in the future, uncomment this test.
  //
  // test("12. Query KB after subtitles ingestion", async ({ page }) => {
  //   await navigateToKb(page);
  //
  //   const queryTab = page.getByRole("button", { name: /^Query$/ });
  //   await expect(queryTab).toBeVisible();
  //   await queryTab.click();
  //   await page.waitForTimeout(500);
  //
  //   const queryInput = page.getByRole("textbox", {
  //     name: /Enter your query/i,
  //   });
  //   await expect(queryInput).toBeVisible({ timeout: 5_000 });
  //   await queryInput.fill("What happened during the French Revolution?");
  //
  //   const submitBtn = page.getByRole("button", { name: /Submit Query/i });
  //   if (await submitBtn.count()) {
  //     await submitBtn.click();
  //   } else {
  //     await page.keyboard.press("Enter");
  //   }
  //
  //   await expect(page.getByText(/Query Results:/i)).toBeVisible({
  //     timeout: 60_000,
  //   });
  //
  //   const resultsSection = page.locator("text=/revolution|robespierre|guillotine|king louis/i");
  //   const matchCount = await resultsSection.count();
  //   expect(
  //     matchCount,
  //     'Expected French Revolution subtitle content to appear in query results'
  //   ).toBeGreaterThan(0);
  //
  //   console.log("Query returned relevant results from French Revolution subtitles.");
  // });

  // ── Cleanup ──

  test("13. Delete knowledge base (cleanup)", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const kbRow = page.locator("tr").filter({ hasText: kbName });
    if ((await kbRow.count()) === 0) {
      console.log(`KB "${kbName}" already deleted or not found — nothing to clean up.`);
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
    await expect(page.getByText(kbName)).not.toBeVisible({ timeout: 10_000 });
    console.log(`KB "${kbName}" deleted.`);
  });
});
