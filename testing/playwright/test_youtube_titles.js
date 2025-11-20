// Playwright test to verify YouTube videos have descriptive titles (not just video IDs)
// Based on recorded interaction: ingest YouTube video and verify title is descriptive
const { chromium } = require('playwright');
const fs = require('fs');

// Configurable constants
const VIDEO_URL = process.env.VIDEO_URL || 'https://www.youtube.com/watch?v=YA9FlHLE9ts';
const VIDEO_LANG = process.env.VIDEO_LANG || 'es';
const KNOWN_KB_ID = process.env.KB_ID || '1';
const HEADLESS = (process.env.HEADLESS || 'false').toLowerCase() === 'true';
const SLOW_MO = process.env.SLOW_MO ? parseInt(process.env.SLOW_MO, 10) : 500;
const BASE_URL = process.argv[2] || 'http://localhost:5173';

(async () => {
  const browser = await chromium.launch({ headless: HEADLESS, slowMo: SLOW_MO });
  const context = await browser.newContext({ viewport: { width: 1438, height: 1148 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);

  const log = (...args) => console.log('[test_youtube_titles]', ...args);
  const error = (...args) => console.error('[test_youtube_titles]', ...args);

  // Load session data for authentication
  try {
    if (fs.existsSync('session_data.json')) {
      log('Loading session_data.json ...');
      const sessionData = JSON.parse(fs.readFileSync('session_data.json', 'utf-8'));
      await page.goto(BASE_URL + '/');
      await page.evaluate((data) => {
        for (const [k, v] of Object.entries(data.localStorage || {})) localStorage.setItem(k, v);
        for (const [k, v] of Object.entries(data.sessionStorage || {})) sessionStorage.setItem(k, v);
      }, sessionData);
      await page.reload();
      await page.waitForLoadState('networkidle');
      log('Session data applied.');
    } else {
      log('WARNING: No session_data.json found. Run login.js first.');
      await browser.close();
      process.exit(1);
    }
  } catch (e) {
    error('Failed applying session data:', e);
    await browser.close();
    process.exit(1);
  }

  let testsPassed = 0;
  let testsFailed = 0;

  try {
    // Step 1: Navigate to knowledge bases
    log('Step 1: Navigating to knowledge bases...');
    await page.goto(`${BASE_URL}/knowledgebases`);
    await page.waitForLoadState('networkidle');
    log(' Navigated to knowledge bases');

    // Step 2: Click Edit button for the first KB (or specific KB)
    log('Step 2: Opening knowledge base for editing...');
    const editButton = page.getByRole('button', { name: /Editar|Edit/i }).first();
    await editButton.waitFor({ state: 'visible', timeout: 5000 });
    await editButton.click();
    await page.waitForLoadState('networkidle');
    log(' Opened knowledge base');

    // Step 3: Click "Ingest Content" tab
    log('Step 3: Opening Ingest Content tab...');
    const ingestButton = page.getByRole('button', { name: /Ingest Content/i });
    await ingestButton.waitFor({ state: 'visible' });
    await ingestButton.click();
    await page.waitForTimeout(1000);
    log(' Opened Ingest Content');

    // Step 4: Select YouTube plugin
    log('Step 4: Selecting YouTube ingestion plugin...');
    const pluginSelect = page.locator('#plugin-select-inline');
    await pluginSelect.waitFor({ state: 'visible' });
    
    // Find the youtube_transcript_ingest option
    const youtubeOption = pluginSelect.locator('option', { hasText: /youtube_transcript_ingest/i });
    const youtubeValue = await youtubeOption.getAttribute('value');
    await pluginSelect.selectOption(youtubeValue);
    await page.waitForTimeout(500);
    log(' Selected YouTube plugin');

    // Step 5: Fill video URL
    log('Step 5: Filling video URL...');
    const videoUrlInput = page.locator('#param-video_url-inline');
    await videoUrlInput.waitFor({ state: 'visible' });
    await videoUrlInput.fill(VIDEO_URL);
    log(` Filled video URL: ${VIDEO_URL}`);

    // Optional: Set language if field exists
    try {
      const languageInput = page.getByRole('textbox', { name: /^language /i });
      await languageInput.waitFor({ timeout: 2000 });
      await languageInput.fill(VIDEO_LANG);
      log(` Set language to ${VIDEO_LANG}`);
    } catch (e) {
      log('Language input not found, skipping');
    }

    // Step 6: Click "Run Ingestion"
    log('Step 6: Starting ingestion...');
    const runButton = page.locator('div.border-t > div.px-4 button', { hasText: /Run Ingestion/i });
    await runButton.waitFor({ state: 'visible' });
    await runButton.click();
    log(' Clicked Run Ingestion');

    // Wait for success message
    try {
      await page.getByText(/File uploaded and ingestion started successfully!/i).waitFor({ timeout: 10000 });
      log(' Ingestion started successfully');
    } catch (e) {
      log('WARNING: Success message not detected within timeout');
    }

    // Wait a bit for ingestion to process
    await page.waitForTimeout(3000);

    // Step 7: Click "Files" tab to view ingested files
    log('Step 7: Navigating to Files tab...');
    const filesButton = page.getByRole('button', { name: /^Files$/i });
    await filesButton.waitFor({ state: 'visible' });
    await filesButton.click();
    await page.waitForTimeout(2000);
    log(' Opened Files tab');

    // Step 8: VERIFY - Check that YouTube video titles are descriptive
    log('Step 8: Verifying YouTube video titles are descriptive...');
    
    // Extract video ID from URL for comparison
    const videoIdMatch = VIDEO_URL.match(/[?&]v=([^&]+)/);
    const videoId = videoIdMatch ? videoIdMatch[1] : null;
    log(`Video ID extracted: ${videoId}`);

    // Look for file entries in the table
    const fileRows = page.locator('table tbody tr');
    const rowCount = await fileRows.count();
    log(`Found ${rowCount} file rows`);

    if (rowCount === 0) {
      error('✗ TEST FAILED: No files found in knowledge base');
      testsFailed++;
    } else {
      let foundYoutubeFile = false;

      // Look through files to find the most recent YouTube video (only check first occurrence)
      for (let i = 0; i < rowCount; i++) {
        const row = fileRows.nth(i);
        const fileName = await row.locator('td').first().textContent();
        log(`  File ${i + 1}: ${fileName.trim()}`);

        // Check if this is likely our YouTube video file
        // It should contain the video ID OR be a recently added file
        if (!foundYoutubeFile && (fileName.includes(videoId) || fileName.includes('youtube') || fileName.includes('.txt'))) {
          foundYoutubeFile = true;
          
          // TEST: The filename should NOT be just the video ID
          // It should be descriptive (contain spaces or meaningful words)
          const trimmedName = fileName.trim();
          const isJustVideoId = trimmedName === videoId || trimmedName === `${videoId}.txt`;
          const hasSpacesOrDashes = /[\s\-_]{2,}|[A-Z][a-z]/.test(trimmedName);
          const hasMultipleWords = trimmedName.split(/[\s\-_]+/).filter(w => w.length > 2).length > 1;
          
          if (isJustVideoId) {
            error(`✗ TEST FAILED: File name is just video ID: "${trimmedName}"`);
            error('  Expected: Descriptive title from YouTube video');
            testsFailed++;
          } else if (hasSpacesOrDashes || hasMultipleWords) {
            log(`✓ TEST PASSED: File has descriptive title: "${trimmedName}"`);
            testsPassed++;
            break; // Only test the first matching file
          } else {
            error(`✗ TEST FAILED: File name is not descriptive enough: "${trimmedName}"`);
            error('  Expected: Title with multiple words or meaningful description');
            testsFailed++;
          }
        }
      }

      if (!foundYoutubeFile) {
        log('WARNING: Could not identify YouTube video file. Showing all files above.');
        log('This may indicate the ingestion is still processing.');
      }
    }

  } catch (err) {
    error('Test error:', err);
    testsFailed++;
  }

  // Summary
  log('');
  log('='.repeat(60));
  log('TEST SUMMARY');
  log('='.repeat(60));
  log(`Tests Passed: ${testsPassed}`);
  log(`Tests Failed: ${testsFailed}`);
  log('='.repeat(60));

  await browser.close();
  
  if (testsFailed > 0) {
    process.exit(1);
  }
})().catch(err => {
  console.error('[test_youtube_titles] Fatal error:', err);
  process.exit(1);
});
