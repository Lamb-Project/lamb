// Playwright test to verify URL ingestion plugin functionality
// This test combines two recorded interactions:
// 1. Create a KB, ingest URL content from Spanish Constitution
// 2. Wait for ingestion to complete, then query the KB to verify content retrieval
const { chromium } = require('playwright');
const fs = require('fs');

// Configurable constants
const TEST_URL = process.env.TEST_URL || 'https://www.cervantesvirtual.com/obra-visor/the-political-constitution-of-the-spanish-monarchy-promulgated-in-cadiz-the-nineteenth-day-of-march--0/html/ffd04084-82b1-11df-acc7-002185ce6064_1.html';
const TEST_KB_BASE_NAME = process.env.KB_NAME || 'url_test';
const TEST_QUERY = process.env.TEST_QUERY || 'What did the article number 14 in the Spanish Constitution of 1812 say?';
const HEADLESS = (process.env.HEADLESS || 'false').toLowerCase() === 'true';
const SLOW_MO = process.env.SLOW_MO ? parseInt(process.env.SLOW_MO, 10) : 500;
const BASE_URL = process.argv[2] || 'http://localhost:5173';
const INGESTION_WAIT_TIME = process.env.INGESTION_WAIT_TIME ? parseInt(process.env.INGESTION_WAIT_TIME, 10) : 60000; // 60 seconds default

(async () => {
  const browser = await chromium.launch({ headless: HEADLESS, slowMo: SLOW_MO });
  const context = await browser.newContext({ viewport: { width: 890, height: 729 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);

  const log = (...args) => console.log('[test_url_ingest]', ...args);
  const error = (...args) => console.error('[test_url_ingest]', ...args);

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
  let createdKbId = null;
  let TEST_KB_NAME = TEST_KB_BASE_NAME;

  try {
    // ========================================================================
    // PART 1: CREATE KB AND INGEST URL (Video 1)
    // ========================================================================
    log('');
    log('='.repeat(60));
    log('PART 1: CREATE KNOWLEDGE BASE AND INGEST URL');
    log('='.repeat(60));

    // Step 1: Navigate to knowledge bases
    log('Step 1: Navigating to knowledge bases...');
    await page.goto(`${BASE_URL}/knowledgebases`);
    await page.waitForLoadState('networkidle', { timeout: 30000 });
    log(' Navigated to knowledge bases');

    // Step 2: Find available KB name (url_test, url_test_1, url_test_2, etc.)
    log('Step 2: Finding available knowledge base name...');
    let counter = 0;
    let kbNameAvailable = false;
    
    while (!kbNameAvailable) {
      const testName = counter === 0 ? TEST_KB_BASE_NAME : `${TEST_KB_BASE_NAME}_${counter}`;
      const existingKb = page.getByRole('button', { name: testName });
      const exists = await existingKb.count() > 0;
      
      if (!exists) {
        TEST_KB_NAME = testName;
        kbNameAvailable = true;
        log(` Available KB name found: ${TEST_KB_NAME}`);
      } else {
        counter++;
      }
      
      // Safety limit to avoid infinite loop
      if (counter > 100) {
        throw new Error('Could not find available KB name after 100 attempts');
      }
    }

    // Step 3: Click "Create Knowledge Base" button
    log('Step 3: Creating new knowledge base...');
    const createKbButton = page.getByRole('button', { name: /Crear Base de Conocimiento|Create Knowledge Base/i }).first();
    await createKbButton.waitFor({ state: 'visible', timeout: 5000 });
    await createKbButton.click();
    await page.waitForTimeout(500);
    log(' Clicked Create KB button');

    // Step 4: Fill in KB name
    log('Step 4: Filling knowledge base details...');
    const kbNameInput = page.locator('#kb-name');
    await kbNameInput.waitFor({ state: 'visible' });
    await kbNameInput.fill(TEST_KB_NAME);
    log(` Filled KB name: ${TEST_KB_NAME}`);

    // Step 5: Submit KB creation
    log('Step 5: Submitting knowledge base creation...');
    const submitButton = page.locator('div.fixed button.border-transparent', { hasText: /Crear Base de Conocimiento|Create Knowledge Base/i });
    await submitButton.waitFor({ state: 'visible' });
    await submitButton.click();
    log(' Submitted KB creation');

    // Wait for KB to be created and visible in the list
    await page.waitForTimeout(2000);
    
    // Step 6: Click on the newly created KB to open it
    log('Step 6: Opening the created knowledge base...');
    const kbLink = page.getByRole('button', { name: TEST_KB_NAME });
    await kbLink.waitFor({ state: 'visible', timeout: 5000 });
    await kbLink.click();
    await page.waitForLoadState('networkidle');
    log(' Opened knowledge base');

    // Extract KB ID from URL
    const currentUrl = page.url();
    const kbIdMatch = currentUrl.match(/[?&]id=(\d+)/);
    if (kbIdMatch) {
      createdKbId = kbIdMatch[1];
      log(` KB ID extracted: ${createdKbId}`);
    }

    // Step 7: Click "Ingest Content" tab
    log('Step 7: Opening Ingest Content tab...');
    const ingestButton = page.getByRole('button', { name: /Ingest Content/i });
    await ingestButton.waitFor({ state: 'visible' });
    await ingestButton.click();
    await page.waitForTimeout(1000);
    log(' Opened Ingest Content');

    // Step 8: Select URL ingestion plugin
    log('Step 8: Selecting URL ingestion plugin...');
    const pluginSelect = page.locator('#plugin-select-inline');
    await pluginSelect.waitFor({ state: 'visible' });
    
    // Select the url_ingest option (value="3" based on video)
    await pluginSelect.selectOption('3');
    await page.waitForTimeout(500);
    log(' Selected URL ingestion plugin');

    // Step 9: Fill URL
    log('Step 9: Filling URL parameter...');
    const urlInput = page.locator('#param-url-inline');
    await urlInput.waitFor({ state: 'visible' });
    await urlInput.fill(TEST_URL);
    log(` Filled URL: ${TEST_URL}`);

    // Step 10: Click "Run Ingestion"
    log('Step 10: Starting ingestion...');
    const runButton = page.locator('div.border-t > div.px-4 button', { hasText: /Run Ingestion/i });
    await runButton.waitFor({ state: 'visible' });
    await runButton.click();
    log(' Clicked Run Ingestion');

    // Wait for success message
    try {
      await page.getByText(/File uploaded and ingestion started successfully!|Ingestion started/i).waitFor({ timeout: 10000 });
      log(' Ingestion started successfully');
      testsPassed++;
    } catch (e) {
      error(' TEST FAILED: Success message not detected within timeout');
      testsFailed++;
    }

    // Step 11: Navigate to Files tab to verify ingestion started
    log('Step 11: Checking Files tab...');
    const filesButton = page.getByRole('button', { name: /^Files$/i });
    await filesButton.waitFor({ state: 'visible' });
    await filesButton.click();
    await page.waitForTimeout(2000);
    log(' Opened Files tab');

    // ========================================================================
    // WAITING PERIOD: Allow ingestion to complete (approx 1 minute)
    // ========================================================================
    log('');
    log('='.repeat(60));
    log(`WAITING ${INGESTION_WAIT_TIME / 1000} SECONDS FOR INGESTION TO COMPLETE...`);
    log('='.repeat(60));
    await page.waitForTimeout(INGESTION_WAIT_TIME);
    log('Wait complete. Proceeding to query test...');

    // ========================================================================
    // PART 2: QUERY THE KNOWLEDGE BASE (Video 2)
    // ========================================================================
    log('');
    log('='.repeat(60));
    log('PART 2: QUERY KNOWLEDGE BASE TO VERIFY CONTENT');
    log('='.repeat(60));

    // Step 12: Navigate to Query tab
    log('Step 12: Opening Query tab...');
    const queryButton = page.getByRole('button', { name: /Query/i });
    await queryButton.waitFor({ state: 'visible' });
    await queryButton.click();
    await page.waitForTimeout(1000);
    log(' Opened Query tab');

    // Step 13: Fill query text
    log('Step 13: Entering query...');
    const queryTextArea = page.locator('#query-text');
    await queryTextArea.waitFor({ state: 'visible' });
    await queryTextArea.fill(TEST_QUERY);
    log(` Query: ${TEST_QUERY}`);
    
    // Wait a few seconds for user to read the query
    log(' Waiting 3 seconds to review the query...');
    await page.waitForTimeout(3000);

    // Step 14: Submit query
    log('Step 14: Submitting query...');
    const submitQueryButton = page.locator('div.border-t > div.px-4 button', { hasText: /Submit Query/i });
    await submitQueryButton.waitFor({ state: 'visible' });
    await submitQueryButton.click();
    log(' Submitted query');

    // Step 15: Wait for results and verify content
    log('Step 15: Waiting for query results...');
    await page.waitForTimeout(5000); // Wait for results to load

    // Check if results are displayed
    const resultsContainer = page.locator('div.text-sm > div');
    try {
      await resultsContainer.first().waitFor({ state: 'visible', timeout: 10000 });
      
      // Get the second result (index 1) as it contains the exact answer
      const resultCount = await resultsContainer.count();
      log(` Found ${resultCount} results`);
      
      if (resultCount > 1) {
        const secondResult = resultsContainer.nth(1);
        await secondResult.scrollIntoViewIfNeeded();
        await page.waitForTimeout(1000); // Brief pause before highlighting
        
        // Highlight the second result for visibility
        await secondResult.evaluate(el => {
          el.style.border = '3px solid #00ff00';
          el.style.backgroundColor = '#ffffcc';
        });
        
        const secondResultText = await secondResult.textContent();
        log(' Highlighting second result (contains exact answer)...');
        log(` Second result preview: ${secondResultText.substring(0, 300)}...`);
        
        // Wait 5 seconds to view the highlighted result
        await page.waitForTimeout(5000);
        
        // Verify that the second result contains relevant information about Article 14
        if (secondResultText && (secondResultText.toLowerCase().includes('article') || secondResultText.toLowerCase().includes('14'))) {
          log(' TEST PASSED: Second result contains relevant information');
          testsPassed++;
        } else {
          error(' TEST FAILED: Second result does not contain expected content');
          error(` Result: ${secondResultText ? secondResultText.substring(0, 200) : 'No content'}`);
          testsFailed++;
        }
      } else {
        // Fallback to first result if only one result exists
        const firstResultText = await resultsContainer.first().textContent();
        log(' Only one result found, checking first result...');
        
        if (firstResultText && (firstResultText.toLowerCase().includes('article') || firstResultText.toLowerCase().includes('14'))) {
          log(' TEST PASSED: Query returned relevant results');
          log(` Result preview: ${firstResultText.substring(0, 200)}...`);
          testsPassed++;
        } else {
          error(' TEST FAILED: Query results do not contain expected content');
          error(` Result: ${firstResultText ? firstResultText.substring(0, 200) : 'No content'}`);
          testsFailed++;
        }
        
        // Wait to view the result
        await page.waitForTimeout(3000);
      }
    } catch (e) {
      error(' TEST FAILED: No query results found within timeout');
      error(` Error: ${e.message}`);
      testsFailed++;
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
  if (createdKbId) {
    log(`Created KB ID: ${createdKbId}`);
    log(`KB Name: ${TEST_KB_NAME}`);
  }
  log('='.repeat(60));

  await browser.close();
  
  if (testsFailed > 0) {
    process.exit(1);
  }
})().catch(err => {
  console.error('[test_url_ingest] Fatal error:', err);
  process.exit(1);
});
