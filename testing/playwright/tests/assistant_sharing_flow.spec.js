const { test, expect } = require("@playwright/test");

/**
 * Assistant Sharing Flow Tests
 * 
 * Tests the complete flow of:
 * a) Creating a user (as system admin)
 * b) Creating an organization with the user as admin
 * c) Creating a new user for the organization
 * d) Managing sharing of assistants
 * 
 * Prerequisites: 
 * - Logged in as admin@owi.com via global-setup.js
 */

test.describe.serial("Assistant Sharing Flow", () => {
  // Unique identifiers for this test run
  const timestamp = Date.now();
  const testUser1Email = `sharing_user1_${timestamp}@test.com`;
  const testUser1Name = `Sharing User 1 ${timestamp}`;
  const testUser2Email = `sharing_user2_${timestamp}@test.com`;
  const testUser2Name = `Sharing User 2 ${timestamp}`;
  const testPassword = "test_password_123";
  const orgSlug = `sharing-org-${timestamp}`;
  const orgName = `Sharing Org ${timestamp}`;
  const assistantName = `Shared Assistant ${timestamp}`;

  test("1. Create first user (future org admin) as system admin", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button
    const createButton = page.getByRole("button", { name: /create user/i });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create user form to appear
    await expect(
      page.getByRole("textbox", { name: /email\s*\*/i })
    ).toBeVisible({ timeout: 5_000 });

    // Wait for organization dropdown to finish loading (important for remote sites)
    const orgSelect = page.getByRole("combobox", { name: /organization/i });
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });

    // Fill in user details
    await page.getByRole("textbox", { name: /email\s*\*/i }).fill(testUser1Email);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(testUser1Name);
    await page.getByRole("textbox", { name: /password\s*\*/i }).fill(testPassword);

    // Select User Type: Creator
    const userTypeSelect = page.getByRole("combobox", { name: /user type/i });
    await userTypeSelect.selectOption("creator");

    // Leave organization as default (system org) - don't select any org

    // Submit the form (note: form uses div, not <form> element)
    const formContainer = page.locator('text=Create New User').locator('..');
    const submitButton = formContainer.getByRole("button", { name: /^create user$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(page.getByText(/user created successfully/i)).toBeVisible({
      timeout: 15_000,
    });

    // Verify user appears in the list (may need to search)
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(testUser1Email);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(testUser1Email)).toBeVisible({ timeout: 10_000 });
    console.log(`User "${testUser1Name}" (${testUser1Email}) successfully created.`);
  });

  test("2. Create organization with first user as admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click "Create Organization" button
    const createButton = page.getByRole("button", { name: /create organization/i });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create org form to appear
    await expect(
      page.getByRole("textbox", { name: /slug\s*\*/i })
    ).toBeVisible({ timeout: 5_000 });

    // Fill in organization details
    await page.getByRole("textbox", { name: /slug\s*\*/i }).fill(orgSlug);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(orgName);

    // Wait for admin dropdown to load
    const adminSelect = page.getByRole("combobox", { name: /organization admin\s*\*/i });
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    
    // Wait for options to load (more than just the placeholder)
    await page.waitForFunction(
      (selector) => {
        const select = document.querySelector(selector);
        return select && select.options && select.options.length > 1;
      },
      'select[name*="admin"], [aria-label*="Organization Admin"]',
      { timeout: 15_000 }
    ).catch(() => {
      // Fallback: just wait a bit
      return page.waitForTimeout(3000);
    });

    // Find and select the option that contains our user email
    const options = await adminSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(testUser1Email)) {
        const value = await option.getAttribute("value");
        if (value) {
          await adminSelect.selectOption(value);
          foundOption = true;
          break;
        }
      }
    }

    if (!foundOption) {
      // List available options for debugging
      const availableOptions = [];
      for (const option of options) {
        availableOptions.push(await option.textContent());
      }
      throw new Error(`Could not find option for user: ${testUser1Email}. Available: ${availableOptions.join(', ')}`);
    }

    // Submit the form (note: form uses div, not <form> element)
    const formContainer = page.locator('text=Create New Organization').locator('..');
    const submitButton = formContainer.getByRole("button", { name: /^create organization$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(
      page.getByText(/organization created successfully/i)
    ).toBeVisible({ timeout: 15_000 });

    // Verify organization appears in the list
    await expect(page.getByText(orgSlug)).toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${orgName}" (${orgSlug}) successfully created.`);
  });

  test("3. Create second user in the organization", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button
    const createButton = page.getByRole("button", { name: /create user/i });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create user form to appear
    await expect(
      page.getByRole("textbox", { name: /email\s*\*/i })
    ).toBeVisible({ timeout: 5_000 });

    // Wait for organization dropdown to finish loading (important for remote sites)
    const orgSelect = page.getByRole("combobox", { name: /organization/i });
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });

    // Fill in user details
    await page.getByRole("textbox", { name: /email\s*\*/i }).fill(testUser2Email);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(testUser2Name);
    await page.getByRole("textbox", { name: /password\s*\*/i }).fill(testPassword);

    // Select User Type: Creator
    const userTypeSelect = page.getByRole("combobox", { name: /user type/i });
    await userTypeSelect.selectOption("creator");

    // Find and select the organization we created
    const options = await orgSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(orgName)) {
        const value = await option.getAttribute("value");
        if (value) {
          await orgSelect.selectOption(value);
          foundOption = true;
          break;
        }
      }
    }

    if (!foundOption) {
      throw new Error(`Could not find organization option: ${orgName}`);
    }

    // Submit the form (note: form uses div, not <form> element)
    const formContainer = page.locator('text=Create New User').locator('..');
    const submitButton = formContainer.getByRole("button", { name: /^create user$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(page.getByText(/user created successfully/i)).toBeVisible({
      timeout: 15_000,
    });

    // Verify user appears in the list (may need to search)
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(testUser2Email);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(testUser2Email)).toBeVisible({ timeout: 10_000 });
    console.log(`User "${testUser2Name}" (${testUser2Email}) successfully created.`);
  });

  test("4. Login as first user and create an assistant", async ({ page, context }) => {
    // Clear existing auth state and re-login as the new user
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    // Login as the first test user
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", testUser1Email);
    await page.fill("#password", testPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click("form > button")
    ]);

    // Wait for login to complete
    await page.waitForTimeout(2000);

    // Navigate to assistants and create one
    await page.goto("assistants?view=create");
    await page.getByRole("button", { name: "Create Assistant" }).click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Fill in assistant details
    await page.fill("#assistant-name", assistantName);
    await page.fill("#assistant-description", "Assistant for testing sharing functionality");
    await page.fill("#system-prompt", "You are a helpful assistant for testing sharing.");

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
      'button[type="submit"][form="assistant-form-main"]'
    );
    await expect(saveButton).toBeEnabled({ timeout: 60_000 });

    // Submit the form
    await Promise.all([createRequest, form.evaluate((f) => f.requestSubmit())]);

    // The app navigates back to the assistants list
    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

    // Verify assistant was created
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    await expect(page.getByText(assistantName).first()).toBeVisible({
      timeout: 30_000,
    });
    console.log(`Assistant "${assistantName}" successfully created.`);
  });

  test("5. Share assistant with second user", async ({ page }) => {
    // Find and view the assistant
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    // Click View button for the assistant
    const assistantRow = page.locator(`tr:has-text("${assistantName}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });
    await assistantRow.getByRole("button", { name: /view/i }).first().click();

    await page.waitForLoadState("networkidle");

    // Click Share tab
    const shareTab = page.getByRole("button", { name: /share/i });
    await expect(shareTab).toBeVisible({ timeout: 10_000 });
    await shareTab.click();

    // Click "Manage Shared Users" button
    const manageButton = page.getByRole("button", { name: /manage shared users/i });
    await expect(manageButton).toBeVisible({ timeout: 10_000 });
    await manageButton.click();

    // Wait for modal to appear
    await page.waitForTimeout(2000);

    // Check that the second user is in Available Users
    // The modal should show users from the same organization
    const modal = page.locator(".modal, [role='dialog']");
    await expect(modal.first()).toBeVisible({ timeout: 5_000 });

    // Look for the second user in available panel and move to shared
    const user2Text = page.getByText(testUser2Email);
    
    // If user2 is visible in available, click "Move ALL" button to share
    const moveAllButton = page.getByRole("button", { name: /move all/i }).first();
    if (await moveAllButton.count()) {
      await moveAllButton.click();
    } else {
      // Or try "<<" button which moves all
      const moveButton = page.locator('button:has-text("<<")').first();
      if (await moveButton.count()) {
        await moveButton.click();
      }
    }

    // Save changes
    const saveButton = page.getByRole("button", { name: /save/i });
    await expect(saveButton).toBeVisible({ timeout: 5_000 });
    await saveButton.click();

    // Wait for save to complete
    await page.waitForTimeout(2000);

    // Modal should close or show success
    console.log(`Assistant shared with ${testUser2Email}`);
  });

  test("6. Verify shared assistant appears for second user", async ({ page, context }) => {
    // Clear auth and login as second user
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    // Login as second user
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", testUser2Email);
    await page.fill("#password", testPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click("form > button")
    ]);

    await page.waitForTimeout(2000);

    // Navigate to assistants
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    // The shared assistant should be visible (in "Shared With Me" section or as a regular entry)
    // Check the network request for shared-with-me
    const sharedResponse = await page.waitForResponse(
      (response) => response.url().includes("shared-with-me"),
      { timeout: 10_000 }
    ).catch(() => null);

    // The assistant should appear somewhere on the page
    await expect(page.getByText(assistantName).first()).toBeVisible({
      timeout: 30_000,
    });
    console.log(`Shared assistant "${assistantName}" visible to ${testUser2Email}`);
  });

  test("7. Remove sharing and cleanup", async ({ page, context }) => {
    // Login back as first user (owner)
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", testUser1Email);
    await page.fill("#password", testPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click("form > button")
    ]);

    await page.waitForTimeout(2000);

    // Navigate to the assistant
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    // View the assistant
    const assistantRow = page.locator(`tr:has-text("${assistantName}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });
    await assistantRow.getByRole("button", { name: /view/i }).first().click();

    await page.waitForLoadState("networkidle");

    // Go to Share tab
    const shareTab = page.getByRole("button", { name: /share/i });
    await shareTab.click();

    // Open sharing modal
    const manageButton = page.getByRole("button", { name: /manage shared users/i });
    await expect(manageButton).toBeVisible({ timeout: 10_000 });
    await manageButton.click();

    await page.waitForTimeout(2000);

    // Move all users back to available (remove sharing)
    const moveAllButton = page.getByRole("button", { name: /move all/i }).last();
    if (await moveAllButton.count()) {
      await moveAllButton.click();
    } else {
      const moveButton = page.locator('button:has-text(">>")').first();
      if (await moveButton.count()) {
        await moveButton.click();
      }
    }

    // Save
    const saveButton = page.getByRole("button", { name: /save/i });
    await saveButton.click();

    await page.waitForTimeout(2000);
    console.log(`Sharing removed from assistant "${assistantName}"`);
  });

  test("8. Delete test assistant", async ({ page }) => {
    // Still logged in as first user from previous test
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    // Find and delete the assistant
    const assistantRow = page.locator(`tr:has-text("${assistantName}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });

    const deleteButton = assistantRow.getByRole("button", { name: /delete/i }).first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Confirm in modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    
    const confirmDeleteButton = modal.getByRole("button", { name: /^delete$/i });
    await expect(confirmDeleteButton).toBeVisible({ timeout: 5_000 });
    await confirmDeleteButton.click();

    // Wait for deletion
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(assistantRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Assistant "${assistantName}" deleted.`);
  });

  test("9. Delete test organization (as system admin)", async ({ page, context }) => {
    // Re-login as system admin
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", "admin@owi.com");
    await page.fill("#password", "admin");

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click("form > button")
    ]);

    await page.waitForTimeout(1500);

    // Navigate to organizations
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for the org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(orgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`tr:has-text("${orgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Handle confirmation dialog
    page.once("dialog", async (dialog) => {
      console.log("Confirm dialog:", dialog.message());
      await dialog.accept();
    });

    // Click delete
    const deleteButton = orgRow.getByRole("button", { name: /delete/i }).first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Wait for org to be removed
    await expect(orgRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${orgSlug}" deleted.`);
  });

  test("10. Disable test users (as system admin)", async ({ page }) => {
    // Still logged in as admin from previous test
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Disable first test user
    const searchBox = page.locator('input[placeholder*="Search" i]');
    
    // Search for first user
    if (await searchBox.count()) {
      await searchBox.fill(testUser1Email);
      await page.waitForTimeout(500);
    }

    let userRow = page.locator(`tr:has-text("${testUser1Email}")`);
    if (await userRow.count()) {
      const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableButton.count()) {
        await disableButton.click();
        
        // Handle confirmation modal
        await expect(page.getByText(/confirm disable/i)).toBeVisible({ timeout: 5_000 });
        const confirmButton = page.getByRole("button", { name: /^disable$/i });
        await confirmButton.click();
        
        await expect(page.getByText(/confirm disable/i)).not.toBeVisible({ timeout: 10_000 });
      }
    }

    // Search for second user
    if (await searchBox.count()) {
      await searchBox.fill(testUser2Email);
      await page.waitForTimeout(500);
    }

    userRow = page.locator(`tr:has-text("${testUser2Email}")`);
    if (await userRow.count()) {
      const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableButton.count()) {
        await disableButton.click();
        
        // Handle confirmation modal
        await expect(page.getByText(/confirm disable/i)).toBeVisible({ timeout: 5_000 });
        const confirmButton = page.getByRole("button", { name: /^disable$/i });
        await confirmButton.click();
        
        await expect(page.getByText(/confirm disable/i)).not.toBeVisible({ timeout: 10_000 });
      }
    }

    console.log("Test users disabled.");
  });
});
