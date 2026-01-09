const { test, expect } = require("@playwright/test");

test.describe.serial("Admin flow (create user + create org)", () => {
  const timestamp = Date.now();
  const userEmail = `pwuser_${timestamp}@test.com`;
  const userName = `pw_user_${timestamp}`;
  const userPassword = "test_password_123";
  const orgSlug = `pw-org-${timestamp}`;
  const orgName = `PW Org ${timestamp}`;

  test("Create user as admin", async ({ page }) => {
    // Use system admin view (not org-admin)
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Click "Create User" button
    const createButton = page.getByRole("button", { name: /create user/i });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for the create user form/dialog to appear
    await expect(
      page.getByRole("textbox", { name: /email\s*\*/i })
    ).toBeVisible({
      timeout: 5_000,
    });

    // Wait for organization dropdown to finish loading (important for remote sites)
    const orgSelect = page.getByRole("combobox", { name: /organization/i });
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    // Wait until "Loading" text disappears
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });

    // Fill in user details
    await page.getByRole("textbox", { name: /email\s*\*/i }).fill(userEmail);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(userName);
    await page
      .getByRole("textbox", { name: /password\s*\*/i })
      .fill(userPassword);

    // Select User Type: Creator
    const userTypeSelect = page.getByRole("combobox", { name: /user type/i });
    await userTypeSelect.selectOption("creator");

    // Submit the form (note: form uses div, not <form> element)
    // Find the submit button in the Create New User dialog (not the header button)
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
      await searchBox.fill(userEmail);
      await page.waitForTimeout(500);
    }
    await expect(page.getByText(userEmail)).toBeVisible({ timeout: 10_000 });
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
    await expect(page.getByRole("textbox", { name: /slug\s*\*/i })).toBeVisible(
      {
        timeout: 5_000,
      }
    );

    // Fill in organization details
    await page.getByRole("textbox", { name: /slug\s*\*/i }).fill(orgSlug);
    await page.getByRole("textbox", { name: /name\s*\*/i }).fill(orgName);

    // Wait for admin dropdown to load
    const adminSelect = page.getByRole("combobox", { name: /organization admin\s*\*/i });
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    
    // Wait for options to load (more than just the placeholder)
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
    ).catch(() => {
      // Fallback: just wait a bit
      return page.waitForTimeout(3000);
    });

    // Get all options and find the one containing our user
    const options = await adminSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(userEmail)) {
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
      throw new Error(`Could not find option for user: ${userEmail}. Available: ${availableOptions.join(', ')}`);
    }

    // Submit the form (note: form uses div, not <form> element)
    // Find the submit button in the Create Organization dialog (not the header button)
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
    await expect(page.getByText(/confirm disable/i)).toBeVisible({
      timeout: 5_000,
    });

    // Click the "Disable" button in the modal
    const confirmButton = page.getByRole("button", { name: /^disable$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for the modal to disappear and user status to change to "Disabled"
    await expect(page.getByText(/confirm disable/i)).not.toBeVisible({
      timeout: 10_000,
    });
    await expect(userRow.getByText("Disabled")).toBeVisible({
      timeout: 10_000,
    });
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
