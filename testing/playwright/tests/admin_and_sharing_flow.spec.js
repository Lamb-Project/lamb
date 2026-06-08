const { test, expect } = require("@playwright/test");

/**
 * Admin & Assistant Sharing Flow Tests
 * 
 * Combined test suite that runs sequentially to avoid worker parallelism issues.
 * 
 * Tests cover:
 * Part 1 - Admin Flow (basic CRUD):
 *   a) Create a user as system admin
 *   b) Create an organization with that user as admin
 *   c) Disable the user
 *   d) Delete the organization
 * 
 * Part 2 - Assistant Sharing Flow:
 *   a) Create first user (future org admin)
 *   b) Create organization with that user as admin
 *   c) Create second user in the organization
 *   d) Login as first user, create assistant
 *   e) Share assistant with second user
 *   f) Verify sharing works (second user can see assistant)
 *   g) Unshare assistant and verify second user CANNOT see it
 *   h) Cleanup (delete assistant, org, disable users)
 * 
 * Prerequisites: 
 * - Logged in as admin via global-setup.js
 */

test.describe.serial("Admin & Assistant Sharing Flow", () => {
  // ============================================
  // PART 1: Admin Flow (basic user/org CRUD)
  // ============================================
  const timestamp1 = Date.now();
  const adminTestUserEmail = `pwuser_${timestamp1}@test.com`;
  const adminTestUserName = `pw_user_${timestamp1}`;
  const adminTestPassword = "test_password_123";
  const adminTestOrgSlug = `pw-org-${timestamp1}`;
  const adminTestOrgName = `PW Org ${timestamp1}`;

  test("1. Admin: Create user as system admin", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button (first one opens the dialog)
    const createButton = page.getByRole("button", { name: /create user/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the modal dialog to appear first
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Wait for the create user form to appear within modal
    const emailInput = modal.locator('input[name="email"]');
    await expect(emailInput).toBeVisible({ timeout: 5_000 });

    // Wait for organization dropdown to finish loading - scope to modal to avoid ambiguity
    const orgSelect = modal.locator("select#organization");
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });

    // Wait for form to be fully ready
    await page.waitForTimeout(500);

    // Fill in user details - use name attribute selectors within modal
    await modal.locator('input[name="email"]').fill(adminTestUserEmail);
    await modal.locator('input[name="name"]').fill(adminTestUserName);
    await modal.locator('input[name="password"]').fill(adminTestPassword);

    // Select User Type: Creator
    await modal.locator('select[name="user_type"]').selectOption('creator');

    // Submit the form - find button inside the modal
    const submitButton = modal.getByRole("button", { name: /^create user$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(page.getByText(/user created successfully/i)).toBeVisible({
      timeout: 15_000,
    });

    // Verify user appears in the list
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(adminTestUserEmail);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(adminTestUserEmail)).toBeVisible({ timeout: 10_000 });
    console.log(`User "${adminTestUserName}" (${adminTestUserEmail}) successfully created.`);
  });

  test("2. Admin: Create organization with user as admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click "Create Organization" button
    const createButton = page.getByRole("button", { name: /create organization/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create org form/dialog to appear
    await expect(page.locator('input#org_slug')).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(500);

    // Fill in organization details using standard fill() - form now reads from DOM via FormData
    await page.locator('input#org_slug').fill(adminTestOrgSlug);
    await page.locator('input#org_name').fill(adminTestOrgName);

    // Wait for admin dropdown to load
    const adminSelect = page.getByRole("combobox", { name: /organization admin/i });
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    
    // Wait for options to load
    await page.waitForFunction(
      () => {
        const selects = document.querySelectorAll('select');
        for (const select of selects) {
          if (select.options && select.options.length > 1) {
            return true;
          }
        }
        return false;
      },
      { timeout: 15_000 }
    ).catch(() => page.waitForTimeout(3000));

    // Find and select the option containing our user
    const options = await adminSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(adminTestUserEmail)) {
        const value = await option.getAttribute("value");
        if (value) {
          await adminSelect.selectOption(value);
          foundOption = true;
          break;
        }
      }
    }

    if (!foundOption) {
      const availableOptions = [];
      for (const option of options) {
        availableOptions.push(await option.textContent());
      }
      throw new Error(`Could not find option for user: ${adminTestUserEmail}. Available: ${availableOptions.join(', ')}`);
    }

    // Small delay to ensure form is ready
    await page.waitForTimeout(500);

    // Submit - find button inside the dialog overlay
    const submitButton = page.locator('.fixed.inset-0').getByRole("button", { name: /^create organization$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click({ force: true });

    // Wait for success message
    await expect(page.getByText(/organization created successfully/i)).toBeVisible({ timeout: 15_000 });

    // Verify organization appears in the list
    await expect(page.getByText(adminTestOrgSlug)).toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${adminTestOrgName}" (${adminTestOrgSlug}) successfully created.`);
  });

  test("3. Admin: Disable user", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Search for the user
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(adminTestUserEmail);
      await page.waitForTimeout(500);
    }

    // Find the user row
    const userRow = page.locator(`tr:has-text("${adminTestUserEmail}")`);
    await expect(userRow).toBeVisible({ timeout: 10_000 });

    // Verify user is currently Active
    await expect(userRow.getByText("Active")).toBeVisible();

    // Click the disable button
    const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
    await expect(disableButton).toBeVisible({ timeout: 5_000 });
    await disableButton.click();

    // Wait for the confirmation modal (UserActionModal shows "Disable User Account")
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await expect(modal.getByText(/disable user account/i)).toBeVisible({ timeout: 5_000 });

    // Click the "Disable" button in the modal
    const confirmButton = modal.getByRole("button", { name: /^disable$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to disappear and status to change
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(userRow.getByText("Disabled")).toBeVisible({ timeout: 10_000 });
    console.log(`User "${adminTestUserEmail}" successfully disabled.`);
  });

  test("4. Admin: Delete organization", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for the org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(adminTestOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`tr:has-text("${adminTestOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Click delete button (named "Delete Organization")
    const deleteButton = orgRow.getByRole("button", { name: /delete organization/i });
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Wait for the confirmation modal to appear (dialog named "Delete Organization")
    const modal = page.getByRole("dialog", { name: /delete organization/i });
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Click the Delete button in the modal
    const confirmButton = modal.getByRole("button", { name: /^delete$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to close and org to be removed
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(orgRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${adminTestOrgSlug}" successfully deleted.`);
  });

  // ============================================
  // PART 2: Assistant Sharing Flow
  // ============================================
  const timestamp2 = Date.now() + 1; // Ensure unique
  const sharingUser1Email = `sharing_user1_${timestamp2}@test.com`;
  const sharingUser1Name = `Sharing User 1 ${timestamp2}`;
  const sharingUser2Email = `sharing_user2_${timestamp2}@test.com`;
  const sharingUser2Name = `Sharing User 2 ${timestamp2}`;
  const sharingPassword = "test_password_123";
  const sharingOrgSlug = `sharing-org-${timestamp2}`;
  const sharingOrgName = `Sharing Org ${timestamp2}`;
  const assistantName = `Shared Assistant ${timestamp2}`;

  test("5. Sharing: Create first user (future org admin)", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button
    const createButton = page.getByRole("button", { name: /create user/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the modal dialog to appear first
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Wait for the create user form to appear within modal
    const emailInput = modal.locator('input[name="email"]');
    await expect(emailInput).toBeVisible({ timeout: 5_000 });

    // Wait for organization dropdown to finish loading
    const orgSelect = modal.getByRole("combobox", { name: /organization/i });
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });

    // Wait for form to be fully ready
    await page.waitForTimeout(500);

    // Fill in user details - use name attribute selectors within modal
    await modal.locator('input[name="email"]').fill(sharingUser1Email);
    await modal.locator('input[name="name"]').fill(sharingUser1Name);
    await modal.locator('input[name="password"]').fill(sharingPassword);

    // Select User Type: Creator
    await modal.locator('select[name="user_type"]').selectOption('creator');

    // Submit - find button inside the modal
    const submitButton = modal.getByRole("button", { name: /^create user$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(page.getByText(/user created successfully/i)).toBeVisible({ timeout: 15_000 });

    // Verify user appears
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(sharingUser1Email);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(sharingUser1Email)).toBeVisible({ timeout: 10_000 });
    console.log(`User "${sharingUser1Name}" (${sharingUser1Email}) successfully created.`);
  });

  test("6. Sharing: Create organization with first user as admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click "Create Organization" button
    const createButton = page.getByRole("button", { name: /create organization/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create org form to appear
    await expect(page.locator('input#org_slug')).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(500);

    // Fill in organization details using standard fill() - form now reads from DOM via FormData
    await page.locator('input#org_slug').fill(sharingOrgSlug);
    await page.locator('input#org_name').fill(sharingOrgName);

    // Wait for admin dropdown to load
    const adminSelect = page.getByRole("combobox", { name: /organization admin/i });
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    
    await page.waitForFunction(
      () => {
        const selects = document.querySelectorAll('select');
        for (const select of selects) {
          if (select.options && select.options.length > 1) return true;
        }
        return false;
      },
      { timeout: 15_000 }
    ).catch(() => page.waitForTimeout(3000));

    // Find and select user
    const options = await adminSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(sharingUser1Email)) {
        const value = await option.getAttribute("value");
        if (value) {
          await adminSelect.selectOption(value);
          foundOption = true;
          break;
        }
      }
    }

    if (!foundOption) {
      const availableOptions = [];
      for (const option of options) {
        availableOptions.push(await option.textContent());
      }
      throw new Error(`Could not find option for user: ${sharingUser1Email}. Available: ${availableOptions.join(', ')}`);
    }

    // Small delay to ensure form is ready
    await page.waitForTimeout(500);

    // Submit - find button inside the dialog overlay
    const submitButton = page.locator('.fixed.inset-0').getByRole("button", { name: /^create organization$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click({ force: true });

    // Wait for success message
    await expect(page.getByText(/organization created successfully/i)).toBeVisible({ timeout: 15_000 });

    // Verify org appears
    await expect(page.getByText(sharingOrgSlug)).toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${sharingOrgName}" (${sharingOrgSlug}) successfully created.`);
  });

  test("7. Sharing: Create second user in the organization", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button
    const createButton = page.getByRole("button", { name: /create user/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the modal dialog to appear first
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Wait for the create user form to appear within modal
    const emailInput = modal.locator('input[name="email"]');
    await expect(emailInput).toBeVisible({ timeout: 5_000 });

    // Wait for organization dropdown to finish loading
    const orgSelect = modal.locator('select[name="organization_id"]');
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });

    // Wait for form to be fully ready
    await page.waitForTimeout(500);

    // Fill in user details - use name attribute selectors within modal
    await modal.locator('input[name="email"]').fill(sharingUser2Email);
    await modal.locator('input[name="name"]').fill(sharingUser2Name);
    await modal.locator('input[name="password"]').fill(sharingPassword);

    // Select User Type: Creator
    await modal.locator('select[name="user_type"]').selectOption('creator');

    // Find and select the organization we created
    const options = await orgSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(sharingOrgName)) {
        const value = await option.getAttribute("value");
        if (value) {
          await orgSelect.selectOption(value);
          foundOption = true;
          break;
        }
      }
    }

    if (!foundOption) {
      throw new Error(`Could not find organization option: ${sharingOrgName}`);
    }

    // Submit - find button inside the modal
    const submitButton = modal.getByRole("button", { name: /^create user$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(page.getByText(/user created successfully/i)).toBeVisible({ timeout: 15_000 });

    // Verify user appears
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(sharingUser2Email);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(sharingUser2Email)).toBeVisible({ timeout: 10_000 });
    console.log(`User "${sharingUser2Name}" (${sharingUser2Email}) successfully created.`);
  });

  test("8. Sharing: Login as first user and create an assistant", async ({ page }) => {
    // Use the app's logout feature to properly sign out
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    
    // Click logout button
    await page.getByRole("button", { name: "Logout" }).click();
    
    // Wait for login form to appear
    await page.waitForSelector("#email", { timeout: 30_000 });

    // Login as the first test user
    await page.fill("#email", sharingUser1Email);
    await page.fill("#password", sharingPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);

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
    const saveButton = page.locator('button[type="submit"][form="assistant-form-main"]');
    await expect(saveButton).toBeEnabled({ timeout: 60_000 });

    // Submit the form
    await Promise.all([createRequest, form.evaluate((f) => f.requestSubmit())]);

    // The app navigates back to the assistants list
    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

    // Verify assistant was created (search by timestamp since backend transforms name)
    // Backend adds user_id prefix and converts to lowercase with underscores
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(timestamp2.toString());
      await page.waitForTimeout(500);
    }

    // Look for the timestamp in the table (appears in transformed name)
    await expect(page.getByText(timestamp2.toString()).first()).toBeVisible({ timeout: 30_000 });
    console.log(`Assistant with timestamp "${timestamp2}" successfully created.`);
  });

  test("9. Sharing: Share assistant with second user", async ({ page }) => {
    // Login as first user (assistant owner) - each test starts with global auth state
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", sharingUser1Email);
    await page.fill("#password", sharingPassword);
    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);
    await page.waitForTimeout(2000);

    // Find and view the assistant
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(timestamp2.toString());
      await page.waitForTimeout(500);
    }

    // Click View button for the assistant (search by timestamp since backend transforms name)
    const assistantRow = page.locator(`tr:has-text("${timestamp2}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });
    await assistantRow.getByRole("button", { name: /view/i }).first().click();

    await page.waitForLoadState("networkidle");

    // Click Share tab (use exact match to avoid matching "Shared with Me")
    const shareTab = page.getByRole("button", { name: /^share$/i });
    await expect(shareTab).toBeVisible({ timeout: 10_000 });
    await shareTab.click();
    
    // Wait for the Share view to load - look for "Manage Shared Users" button
    const manageButton = page.getByRole("button", { name: /manage shared users/i });
    await expect(manageButton).toBeVisible({ timeout: 15_000 });
    await manageButton.click();

    await page.waitForTimeout(2000);

    // Check that the modal is visible
    const modal = page.locator(".modal, [role='dialog']");
    await expect(modal.first()).toBeVisible({ timeout: 5_000 });

    // Check the checkbox for the second user in Available Users, then click < to share
    const user2Checkbox = modal.locator(`label:has-text("${sharingUser2Email}") input[type="checkbox"]`).first();
    await expect(user2Checkbox).toBeVisible({ timeout: 10_000 });
    await user2Checkbox.check();

    // Click the < button (move-left) to transfer the selected user to Shared Users
    const moveLeftButton = modal.locator('button.move-left');
    await expect(moveLeftButton).toBeVisible({ timeout: 5_000 });
    await moveLeftButton.click();

    // Save changes
    const saveButton = modal.locator('button.btn-save');
    await expect(saveButton).toBeVisible({ timeout: 5_000 });
    await saveButton.click();

    await page.waitForTimeout(2000);
    console.log(`Assistant shared with ${sharingUser2Email}`);
  });

  test("10. Sharing: Verify shared assistant appears for second user", async ({ page }) => {
    // Use the app's logout feature to properly sign out
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    
    // Click logout button
    await page.getByRole("button", { name: "Logout" }).click();
    
    // Wait for login form to appear
    await page.waitForSelector("#email", { timeout: 30_000 });

    // Login as the second test user
    await page.fill("#email", sharingUser2Email);
    await page.fill("#password", sharingPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);

    await page.waitForTimeout(2000);

    // Navigate to assistants and switch to "Shared with Me" tab
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    // Click the "Shared with Me" tab to see shared assistants
    const sharedWithMeTab = page.getByRole("button", { name: /shared with me/i });
    await expect(sharedWithMeTab).toBeVisible({ timeout: 10_000 });
    await sharedWithMeTab.click();

    // Wait for shared-with-me API call
    await page.waitForResponse(
      (response) => response.url().includes("shared-with-me"),
      { timeout: 10_000 }
    ).catch(() => null);

    // Search by timestamp since backend transforms assistant name
    await expect(page.getByText(timestamp2.toString()).first()).toBeVisible({ timeout: 30_000 });
    console.log(`Shared assistant with timestamp "${timestamp2}" visible to ${sharingUser2Email}`);
  });

  test("11. Sharing: Unshare assistant and verify it disappears for second user", async ({ page }) => {
    // === Step 1: Login as first user (owner) and unshare the assistant ===
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", sharingUser1Email);
    await page.fill("#password", sharingPassword);
    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);
    await page.waitForTimeout(2000);

    // Navigate to assistants and find the created assistant
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(timestamp2.toString());
      await page.waitForTimeout(500);
    }

    // View the assistant
    const assistantRow = page.locator(`tr:has-text("${timestamp2}")`);
    await expect(assistantRow).toBeVisible({ timeout: 10_000 });
    await assistantRow.getByRole("button", { name: /view/i }).first().click();
    await page.waitForLoadState("networkidle");

    // Go to Share tab
    const shareTab = page.getByRole("button", { name: /^share$/i });
    await expect(shareTab).toBeVisible({ timeout: 10_000 });
    await shareTab.click();

    // Open sharing modal
    const manageButton = page.getByRole("button", { name: /manage shared users/i });
    await expect(manageButton).toBeVisible({ timeout: 15_000 });
    await manageButton.click();
    await page.waitForTimeout(2000);

    // Move the shared user back to available (unshare).
    // Check the checkbox for user 2 in Shared Users, then click >> (move-all-right).
    const sharedModal = page.locator(".modal, [role='dialog']");
    await expect(sharedModal.first()).toBeVisible({ timeout: 5_000 });

    const sharedUser2Checkbox = sharedModal.locator(`label:has-text("${sharingUser2Email}") input[type="checkbox"]`).first();
    await expect(sharedUser2Checkbox).toBeVisible({ timeout: 10_000 });
    await sharedUser2Checkbox.check();

    // Click the >> button (move-all-right) to transfer the user back to Available
    const moveAllRightButton = sharedModal.locator('button.move-all-right');
    await expect(moveAllRightButton).toBeVisible({ timeout: 5_000 });
    await moveAllRightButton.click();

    // Save the unshare
    const saveButton = sharedModal.locator('button.btn-save');
    await expect(saveButton).toBeVisible({ timeout: 5_000 });
    await saveButton.click();
    await page.waitForTimeout(2000);
    console.log(`Assistant unshared from ${sharingUser2Email}`);

    // === Step 2: Login as second user and verify assistant is GONE ===
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", sharingUser2Email);
    await page.fill("#password", sharingPassword);
    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);
    await page.waitForTimeout(2000);

    // Navigate to assistants and switch to "Shared with Me" tab
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    // Click the "Shared with Me" tab
    const sharedWithMeTab = page.getByRole("button", { name: /shared with me/i });
    await expect(sharedWithMeTab).toBeVisible({ timeout: 10_000 });
    await sharedWithMeTab.click();

    // Wait for shared-with-me API call
    await page.waitForResponse(
      (response) => response.url().includes("shared-with-me"),
      { timeout: 10_000 }
    ).catch(() => null);

    // The assistant should NOT be visible to the unshared user.
    // Search within the main content area for the assistant's timestamp.
    const contentArea = page.locator(".bg-white.shadow.rounded-lg, [role='main']");
    await expect(contentArea.first()).toBeVisible({ timeout: 10_000 });
    await expect(contentArea.first().getByText(timestamp2.toString())).not.toBeVisible({ timeout: 15_000 });
    console.log(`Verified: unshared assistant with timestamp "${timestamp2}" is NOT visible to ${sharingUser2Email}`);
  });

  test("12. Sharing: Cleanup — delete test assistant", async ({ page }) => {
    // Login as first user (assistant owner)
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", sharingUser1Email);
    await page.fill("#password", sharingPassword);
    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);
    await page.waitForTimeout(2000);

    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(timestamp2.toString());
      await page.waitForTimeout(500);
    }

    // Find and delete the assistant
    const assistantRow = page.locator(`tr:has-text("${timestamp2}")`);
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
    console.log(`Assistant with timestamp "${timestamp2}" deleted.`);
  });

  test("13. Sharing: Delete test organization (as system admin)", async ({ page }) => {
    // Use the app's logout feature to properly sign out
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    
    // Click logout button
    await page.getByRole("button", { name: "Logout" }).click();
    
    // Wait for login form to appear
    await page.waitForSelector("#email", { timeout: 30_000 });

    // Use admin credentials from env or defaults
    const adminEmail = process.env.LOGIN_EMAIL || "admin@owi.com";
    const adminPassword = process.env.LOGIN_PASSWORD || "admin";

    // Re-login as system admin
    await page.fill("#email", adminEmail);
    await page.fill("#password", adminPassword);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button')
    ]);

    await page.waitForTimeout(1500);

    // Navigate to organizations
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for the org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(sharingOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`tr:has-text("${sharingOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Click delete button (named "Delete Organization")
    const deleteButton = orgRow.getByRole("button", { name: /delete organization/i });
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Wait for the confirmation modal to appear (dialog named "Delete Organization")
    const modal = page.getByRole("dialog", { name: /delete organization/i });
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Click the Delete button in the modal
    const confirmButton = modal.getByRole("button", { name: /^delete$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to close and org to be removed
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(orgRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${sharingOrgSlug}" deleted.`);
  });

  test("14. Sharing: Disable test users (as system admin)", async ({ page }) => {
    // Still logged in as admin from previous test
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    
    // Disable first test user
    if (await searchBox.count()) {
      await searchBox.fill(sharingUser1Email);
      await page.waitForTimeout(500);
    }

    let userRow = page.locator(`tr:has-text("${sharingUser1Email}")`);
    if (await userRow.count()) {
      const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableButton.count()) {
        await disableButton.click();
        // Wait for UserActionModal to appear
        const modal = page.getByRole("dialog");
        await expect(modal).toBeVisible({ timeout: 5_000 });
        await expect(modal.getByText(/disable user account/i)).toBeVisible({ timeout: 5_000 });
        const confirmButton = modal.getByRole("button", { name: /^disable$/i });
        await confirmButton.click();
        await expect(modal).not.toBeVisible({ timeout: 10_000 });
      }
    }

    // Disable second test user
    if (await searchBox.count()) {
      await searchBox.fill(sharingUser2Email);
      await page.waitForTimeout(500);
    }

    userRow = page.locator(`tr:has-text("${sharingUser2Email}")`);
    if (await userRow.count()) {
      const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableButton.count()) {
        await disableButton.click();
        // Wait for UserActionModal to appear
        const modal = page.getByRole("dialog");
        await expect(modal).toBeVisible({ timeout: 5_000 });
        await expect(modal.getByText(/disable user account/i)).toBeVisible({ timeout: 5_000 });
        const confirmButton = modal.getByRole("button", { name: /^disable$/i });
        await confirmButton.click();
        await expect(modal).not.toBeVisible({ timeout: 10_000 });
      }
    }

    console.log("Test users disabled.");
  });
});
