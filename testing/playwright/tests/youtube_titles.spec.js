const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const VIDEO_URL = process.env.VIDEO_URL || "https://www.youtube.com/watch?v=YA9FlHLE9ts";
const VIDEO_LANG = process.env.VIDEO_LANG || "es";

test.describe.serial("YouTube video titles are descriptive", () => {
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

  test("Ingest YouTube video and verify descriptive title", async ({ page }) => {
    // Step 1: Navigate to knowledge bases
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Step 2: Click Edit button for the KB
    const editButton = page.getByRole("button", { name: /Editar|Edit/i }).first();
    await expect(editButton).toBeVisible({ timeout: 5_000 });
    await editButton.click();
    await page.waitForLoadState("networkidle");

    // Step 3: Click "Ingest Content" tab
    const ingestButton = page.getByRole("button", { name: /Ingest Content/i });
    await expect(ingestButton).toBeVisible();
    await ingestButton.click();
    await page.waitForTimeout(1000);

    // Step 4: Select YouTube plugin
    const pluginSelect = page.locator("#plugin-select-inline");
    await expect(pluginSelect).toBeVisible();
    
    const youtubeOption = pluginSelect.locator("option", { hasText: /youtube_transcript_ingest/i });
    const youtubeValue = await youtubeOption.getAttribute("value");
    await pluginSelect.selectOption(youtubeValue);
    await page.waitForTimeout(500);

    // Step 5: Fill video URL
    const videoUrlInput = page.locator("#param-video_url-inline");
    await expect(videoUrlInput).toBeVisible();
    await videoUrlInput.fill(VIDEO_URL);

    // Optional: Set language if field exists
    try {
      const languageInput = page.getByRole("textbox", { name: /^language /i });
      await languageInput.waitFor({ timeout: 2000 });
      await languageInput.fill(VIDEO_LANG);
    } catch (e) {
      // Language input not found, skip
    }

    // Step 6: Click "Run Ingestion"
    const runButton = page.locator("div.border-t > div.px-4 button", { hasText: /Run Ingestion/i });
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for success message
    await expect(
      page.getByText(/File uploaded and ingestion started successfully!/i)
    ).toBeVisible({ timeout: 10_000 });

    // Wait for ingestion to process
    await page.waitForTimeout(3000);

    // Step 7: Click "Files" tab to view ingested files
    const filesButton = page.getByRole("button", { name: /^Files$/i });
    await expect(filesButton).toBeVisible();
    await filesButton.click();
    await page.waitForTimeout(2000);

    // Step 8: Verify YouTube video has descriptive title
    const videoIdMatch = VIDEO_URL.match(/[?&]v=([^&]+)/);
    const videoId = videoIdMatch ? videoIdMatch[1] : null;

    const fileRows = page.locator("table tbody tr");
    const rowCount = await fileRows.count();

    expect(rowCount).toBeGreaterThan(0);

    let foundYoutubeFile = false;
    let hasDescriptiveTitle = false;

    for (let i = 0; i < rowCount; i++) {
      const row = fileRows.nth(i);
      const fileName = await row.locator("td").first().textContent();

      if (!foundYoutubeFile && (fileName.includes(videoId) || fileName.includes("youtube") || fileName.includes(".txt"))) {
        foundYoutubeFile = true;
        
        const trimmedName = fileName.trim();
        const isJustVideoId = trimmedName === videoId || trimmedName === `${videoId}.txt`;
        const hasSpacesOrDashes = /[\s\-_]{2,}|[A-Z][a-z]/.test(trimmedName);
        const hasMultipleWords = trimmedName.split(/[\s\-_]+/).filter(w => w.length > 2).length > 1;
        
        if (!isJustVideoId && (hasSpacesOrDashes || hasMultipleWords)) {
          hasDescriptiveTitle = true;
        }
        break;
      }
    }

    expect(foundYoutubeFile, "YouTube video file should be found in the list").toBe(true);
    expect(hasDescriptiveTitle, "File name should be descriptive, not just video ID").toBe(true);
  });
});
