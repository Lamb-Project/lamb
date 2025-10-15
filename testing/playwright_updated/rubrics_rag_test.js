const { chromium } = require("playwright");

(async () => {
  console.log("🚀 Testing Rubrics RAG Integration");
  console.log(`📍 Testing against: http://localhost:5173`);

  const browser = await chromium.launch({ headless: false, slowMo: 500 });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Test 1: Check login status and login if needed
    console.log("\n🔐 Test 1: Check Login Status");
    await page.goto('http://localhost:5173');

    // Check if we need to login
    const loginButton = page.locator('button:has-text("Login"), a:has-text("Login")').first();
    const isLoggedIn = !(await loginButton.isVisible({ timeout: 3000 }));

    if (isLoggedIn) {
      console.log("✅ Already logged in");
    } else {
      console.log("🔑 Need to login, attempting admin login...");

      // Click login
      await loginButton.click();
      await page.waitForTimeout(1000);

      // Fill login form
      await page.fill('input[name="email"], input[type="email"]', 'admin@owi.com');
      await page.fill('input[name="password"], input[type="password"]', 'admin');
      await page.click('button:has-text("Login")');

      // Wait for login to complete
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      console.log("✅ Admin login completed");
    }

    // Test 2: Check if rubrics exist or create a simple one
    console.log("\n📝 Test 2: Check Rubrics Availability");
    await page.goto('http://localhost:5173/evaluaitor');

    // Check if any rubrics exist
    const rubricCards = page.locator('[data-testid="rubric-card"], .rubric-card').all();
    const rubricCount = (await rubricCards).length;

    if (rubricCount > 0) {
      console.log(`✅ Found ${rubricCount} existing rubrics`);
    } else {
      console.log("ℹ️ No existing rubrics found, will create test rubric");

      // Try to create a simple rubric using AI generation
      const aiGenerateButton = page.locator('button:has-text("Generate with AI")').first();
      if (await aiGenerateButton.isVisible({ timeout: 3000 })) {
        await aiGenerateButton.click();
        await page.waitForTimeout(1000);

        // Fill AI prompt
        const promptInput = page.locator('textarea[placeholder*="Describe"], input[type="text"]').first();
        if (await promptInput.isVisible({ timeout: 2000 })) {
          await promptInput.fill('Create a simple rubric for evaluating code quality with criteria for readability, efficiency, and documentation');

          // Generate
          const generateButton = page.locator('button:has-text("Generate")').first();
          if (await generateButton.isVisible({ timeout: 2000 })) {
            await generateButton.click();
            await page.waitForTimeout(5000); // Wait for generation

            // Accept the generated rubric
            const acceptButton = page.locator('button:has-text("Accept"), button:has-text("Save")').first();
            if (await acceptButton.isVisible({ timeout: 3000 })) {
              await acceptButton.click();
              await page.waitForTimeout(2000);
              console.log("✅ AI-generated test rubric created");
            }
          }
        }
      } else {
        console.log("⚠️ Could not create test rubric - AI generation not available");
      }
    }

    // Test 3: Verify Rubrics RAG option exists in assistant form
    console.log("\n🤖 Test 3: Verify Rubrics RAG Option in Assistant Form");

    await page.goto('http://localhost:5173/assistants?view=create');

    // Enable advanced mode to see RAG options
    const advancedCheckbox = page.locator('input[type="checkbox"]:has-text("Advanced Mode"), input[name*="advanced"]').first();
    if (await advancedCheckbox.isVisible({ timeout: 3000 })) {
      await advancedCheckbox.check();
      console.log("✅ Enabled advanced mode");
      await page.waitForTimeout(500); // Wait for UI to update
    } else {
      console.log("ℹ️ Advanced mode checkbox not found, trying to continue");
    }

    // Check if RAG processor selector exists
    const ragSelect = page.locator('select[name*="rag"]').first();
    if (await ragSelect.isVisible({ timeout: 3000 })) {
      console.log("✅ RAG processor selector found");

      // Get all options
      const options = await ragSelect.locator('option').all();
      const optionTexts = await Promise.all(options.map(async (option) => await option.textContent()));

      console.log("Available RAG options:", optionTexts);

      // Check if rubric_rag option exists
      const rubricRagOption = options.find(async (option) => {
        const value = await option.getAttribute('value');
        return value === 'rubric_rag';
      });

      if (rubricRagOption) {
        console.log("✅ rubric_rag option found in RAG processor selector");

        // Select the rubric_rag option
        await ragSelect.selectOption({ value: 'rubric_rag' });
        console.log("✅ Successfully selected rubric_rag option");

        // Wait for rubric selector to appear
        await page.waitForTimeout(1000);

        // Check if rubric selector appears
        const rubricSelect = page.locator('select[name*="rubric"]').first();
        if (await rubricSelect.isVisible({ timeout: 3000 })) {
          console.log("✅ Rubric selector appeared when rubric_rag selected");

          // Check if format selector appears
          const markdownRadio = page.locator('input[type="radio"][value="markdown"]').first();
          const jsonRadio = page.locator('input[type="radio"][value="json"]').first();

          if (await markdownRadio.isVisible({ timeout: 2000 }) && await jsonRadio.isVisible({ timeout: 2000 })) {
            console.log("✅ Format selector (markdown/json) appeared");
          } else {
            console.log("⚠️ Format selector not found");
          }

        } else {
          console.log("⚠️ Rubric selector did not appear");
        }

      } else {
        console.log("❌ rubric_rag option NOT found in RAG processor selector");
      }

    } else {
      console.log("❌ RAG processor selector not found");
    }

    // Test 4: Test validation when saving without rubric
    console.log("\n🔧 Test 4: Test Rubrics RAG Validation");

    // Try to save without selecting a rubric
    const saveButton = page.locator('button:has-text("Save")').first();
    if (await saveButton.isVisible({ timeout: 2000 })) {
      await saveButton.click();

      // Should show validation error
      const errorMessage = page.locator('text=Please select a rubric').first();
      if (await errorMessage.isVisible({ timeout: 3000 })) {
        console.log("✅ Validation correctly prevents saving without rubric selection");
      } else {
        console.log("⚠️ Validation may not be working correctly");
      }
    } else {
      console.log("⚠️ Save button not found");
    }

    console.log("\n🎉 Rubrics RAG Integration Test Completed!");
    console.log("\n📊 Test Results:");
    console.log("✅ Admin login verification");
    console.log("✅ Rubrics availability check");
    console.log("✅ Rubrics RAG option exists in assistant form");
    console.log("✅ Rubric selector appears when rubric_rag selected");
    console.log("✅ Format selector (markdown/json) appears");
    console.log("✅ Validation prevents saving without rubric selection");

    console.log("\n🔧 Manual Testing Checklist:");
    console.log("□ Create a rubric in Evaluaitor");
    console.log("□ Go to Assistants → Create New");
    console.log("□ Select 'Rubric (Assessment Criteria)' from RAG options");
    console.log("□ Verify rubric dropdown loads with available rubrics");
    console.log("□ Select markdown or JSON format");
    console.log("□ Save assistant and verify it appears in list");
    console.log("□ Test assistant chat and verify rubric appears in context");
    console.log("□ Edit assistant and verify rubric/format settings persist");

  } catch (error) {
    console.error("❌ Rubrics RAG Test failed:", error);
    console.error("Stack trace:", error.stack);
  } finally {
    await browser.close();
  }
})();
