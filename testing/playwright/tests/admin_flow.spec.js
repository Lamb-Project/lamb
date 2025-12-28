const { test, expect } = require("@playwright/test");

test.describe.serial("Admin flow (create user + create org)", () => {
  const timestamp = Date.now();
  const userEmail = `pwuser_${timestamp}@test.com`;
  const userName = `pw_user_${timestamp}`;
  const userPassword = "test_password_123";
  const orgSlug = `pw-org-${timestamp}`;
  const orgName = `PW Org ${timestamp}`;

  test("Create user as admin", async ({ page }) => {
    await page.goto("org-admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button
    const createButton = page.getByRole("button", { name: /create user/i });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create user form/dialog to appear
    await expect(page.getByRole("textbox", { name: /email\s*\*/i })).toBeVisible({
      timeout: 5_000,
    });

    // Fill in user details
    await page.getByRole("textbox", { name: /email\s*\*/i }).fill(userEmail);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(userName);
    await page.getByRole("textbox", { name: /password\s*\*/i }).fill(userPassword);

    // Select User Type: Creator (use the value, not the label)
    const userTypeSelect = page.locator('select').filter({ hasText: 'Creator (Can create assistants)' });
    await userTypeSelect.selectOption("creator");

    // Ensure "User enabled" checkbox is checked
    const userEnabledCheckbox = page.getByRole("checkbox", { name: /user enabled/i });
    const isChecked = await userEnabledCheckbox.isChecked();
    if (!isChecked) {
      await userEnabledCheckbox.check();
    }

    // Submit the form
    const submitButton = page
      .locator("form")
      .getByRole("button", { name: /create user/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(
      page.getByText(/user created successfully/i)
    ).toBeVisible({ timeout: 10_000 });

    // Verify user appears in the list
    await expect(page.getByText(userEmail)).toBeVisible({ timeout: 5_000 });
    console.log(`User "${userName}" (${userEmail}) successfully created.`);
  });

  test("Create organization as system admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click "Create Organization" button
    const createButton = page.getByRole("button", {
      name: /create organization/i,
    });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create org form/dialog to appear
    await expect(page.getByRole("textbox", { name: /slug\s*\*/i })).toBeVisible({
      timeout: 5_000,
    });

    // Fill in organization details
    await page.getByRole("textbox", { name: /slug\s*\*/i }).fill(orgSlug);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(orgName);

    // Select the admin user we just created
    const adminSelect = page.getByLabel(/organization admin\s*\*/i);
    await expect(adminSelect).toBeVisible({ timeout: 5_000 });
    
    // Find and select the option that contains our user email (by text matching)
    // The option text format is: "username (email) - role"
    const userOptionText = `${userName} (${userEmail})`;
    
    // Get all options and find the one containing our user
    const options = await adminSelect.locator('option').all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(userEmail)) {
        const value = await option.getAttribute('value');
        if (value) {
          await adminSelect.selectOption(value);
          foundOption = true;
          break;
        }
      }
    }
    
    if (!foundOption) {
      throw new Error(`Could not find option for user: ${userEmail}`);
    }

    // Optional: Toggle MCP Enabled if needed (depends on your requirements)
    // await page.getByRole('checkbox', { name: /mcp enabled/i }).click();

    // Submit the form
    const submitButton = page
      .locator("form")
      .getByRole("button", { name: /create organization/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success message
    await expect(
      page.getByText(/organization created successfully/i)
    ).toBeVisible({ timeout: 10_000 });

    // Verify organization appears in the list
    await expect(page.getByText(orgSlug)).toBeVisible({ timeout: 5_000 });
    console.log(`Organization "${orgName}" (${orgSlug}) successfully created.`);
  });

  test("Disable user", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Search for the user to ensure it's visible
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(userEmail);
      await page.waitForTimeout(500);
    }

    // Find the user row
    const userRow = page.locator(`tr:has-text("${userEmail}")`);
    await expect(userRow).toBeVisible({ timeout: 10_000 });

    // Verify user is currently Active
    await expect(userRow.getByText("Active")).toBeVisible();

    // Click the disable button (user icon with slash)
    const disableButton = userRow
      .getByRole("button", { name: /disable/i })
      .first();
    await expect(disableButton).toBeVisible({ timeout: 5_000 });
    await disableButton.click();

    // Wait for the confirmation modal to appear (it's not a dialog role, just a container)
    await expect(page.getByText(/confirm disable/i)).toBeVisible({ timeout: 5_000 });

    // Click the "Disable" button in the modal
    const confirmButton = page.getByRole("button", { name: /^disable$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for the modal to disappear and user status to change to "Disabled"
    await expect(page.getByText(/confirm disable/i)).not.toBeVisible({ timeout: 10_000 });
    await expect(userRow.getByText("Disabled")).toBeVisible({ timeout: 10_000 });
    console.log(`User "${userEmail}" successfully disabled.`);
  });

  test("Delete organization", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for the org to ensure it's visible
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(orgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`text=${orgSlug}`).first();
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Click the delete button
    const deleteButton = page
      .locator(`tr:has-text("${orgSlug}")`)
      .getByRole("button", { name: /delete/i })
      .first();
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });

    // Handle confirmation dialog (browser native or custom modal)
    page.once("dialog", async (dialog) => {
      console.log("Confirm dialog:", dialog.message());
      await dialog.accept();
    });

    await deleteButton.click();

    // Wait for the org to be removed from the list
    await expect(orgRow).not.toBeVisible({ timeout: 10_000 });
    console.log(`Organization "${orgSlug}" successfully deleted.`);
  });
});
