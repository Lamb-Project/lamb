const { test, expect } = require("@playwright/test");

/**
 * Organization Without Admin & Role Promotion Tests (Issue #249)
 *
 * Tests the two features implemented in issue #249:
 *   1. Organizations can be created without an administrator
 *   2. System admin can promote any user (including LTI Creator) to org admin
 *
 * Flow:
 *   Part 1 — Create organization without admin:
 *     1. Open org creation modal, verify admin field is optional
 *     2. Create org without selecting an admin
 *     3. Verify org appears in the list
 *
 *   Part 2 — Create user, assign to org, promote via Members modal:
 *     4. Create a user in the system org
 *     5. Open Members modal for the new org (shows empty)
 *     6. Move user to the org (create a 2nd org with the user as admin — 
 *        but instead we use the API to assign. Since the Members panel
 *        only promotes existing members, we first create a user directly
 *        in the org via the org-admin user creation flow)
 *     — Simpler: create user in the system org, create org with that user,
 *       then test promote/demote via the Members modal.
 *     7. Open Members modal, verify Promote button is visible
 *     8. Promote user to admin
 *     9. Verify role changes to Admin
 *    10. Demote user back to member
 *    11. Verify role changes back to Member
 *
 *   Part 3 — Cleanup:
 *    12. Delete the test organization
 *    13. Disable the test user
 *
 * Prerequisites:
 *   - Logged in as system admin via global-setup.js
 */

test.describe.serial("Organization Without Admin & Role Promotion (issue #249)", () => {
  // Variables initialized in beforeAll to ensure consistency across retries
  let timestamp;
  let noAdminOrgSlug;
  let noAdminOrgName;
  let testUserEmail;
  let testUserName;
  let testUserPassword;
  let promoOrgSlug;
  let promoOrgName;

  test.beforeAll(async () => {
    // Generate timestamp once to ensure all tests use consistent data
    timestamp = Date.now();

    // Test data for org without admin
    noAdminOrgSlug = `no-admin-org-${timestamp}`;
    noAdminOrgName = `No Admin Org ${timestamp}`;

    // Test data for user/org used in promotion tests
    testUserEmail = `promo_user_${timestamp}@test.com`;
    testUserName = `Promo User ${timestamp}`;
    testUserPassword = "TestPromo_249!";
    promoOrgSlug = `promo-org-${timestamp}`;
    promoOrgName = `Promo Org ${timestamp}`;
  });

  // ============================================
  // PART 1: Create organization without admin
  // ============================================

  test("1. Org creation modal shows admin field as optional", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click Create Organization button
    const createButton = page.getByRole("button", { name: /create organization/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for modal to appear
    await expect(page.locator('input#org_slug')).toBeVisible({ timeout: 5_000 });

    // Verify admin dropdown label says "(optional)" and is NOT required
    const adminLabel = page.locator('label[for="admin_user"]');
    await expect(adminLabel).toBeVisible();
    await expect(adminLabel).toContainText("optional");

    const adminSelect = page.locator('select#admin_user');
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    // The select should NOT have the 'required' attribute
    const isRequired = await adminSelect.getAttribute('required');
    expect(isRequired).toBeNull();

    // Verify the default option says "No admin (assign later)"
    const firstOption = adminSelect.locator("option").first();
    await expect(firstOption).toContainText(/no admin/i);

    console.log("Admin field is optional with correct default text.");
  });

  test("2. Create organization without selecting an admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click Create Organization button
    const createButton = page.getByRole("button", { name: /create organization/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for modal
    await expect(page.locator('input#org_slug')).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(500);

    // Fill only slug and name — do NOT select an admin
    await page.locator('input#org_slug').fill(noAdminOrgSlug);
    await page.locator('input#org_name').fill(noAdminOrgName);

    // Wait for admin dropdown to load (but don't select anything)
    const adminSelect = page.locator('select#admin_user');
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1000);

    // Submit the form
    const submitButton = page.locator('.fixed.inset-0').getByRole("button", { name: /^create organization$/i });
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();
    await submitButton.click({ force: true });

    // Wait for success message
    await expect(page.getByText(/organization created successfully/i)).toBeVisible({ timeout: 15_000 });

    console.log(`Organization "${noAdminOrgName}" created without an admin.`);
  });

  test("3. Verify org without admin appears in the list", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for our org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(noAdminOrgSlug);
      await page.waitForTimeout(500);
    }

    // Verify org appears
    await expect(page.getByText(noAdminOrgSlug)).toBeVisible({ timeout: 10_000 });

    console.log(`Organization "${noAdminOrgSlug}" found in the list.`);
  });

  // ============================================
  // PART 2: User creation + role promotion
  // ============================================

  test("4. Create test user for promotion tests", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Open Create User dialog
    const createButton = page.getByRole("button", { name: /create user/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for dialog
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    const emailInput = modal.locator('input[name="email"]');
    await expect(emailInput).toBeVisible({ timeout: 5_000 });

    // Wait for org dropdown to load
    const orgSelect = modal.getByRole("combobox", { name: /organization/i });
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(500);

    // Fill user details
    await modal.locator('input[name="email"]').fill(testUserEmail);
    await modal.locator('input[name="name"]').fill(testUserName);
    await modal.locator('input[name="password"]').fill(testUserPassword);
    await modal.locator('select[name="user_type"]').selectOption('creator');

    // Submit
    const submitButton = modal.getByRole("button", { name: /^create user$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    // Wait for success
    await expect(page.getByText(/user created successfully/i)).toBeVisible({ timeout: 15_000 });

    console.log(`Test user "${testUserEmail}" created.`);
  });

  test("5. Create organization with the test user as admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Click Create Organization button
    const createButton = page.getByRole("button", { name: /create organization/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    // Wait for modal
    await expect(page.locator('input#org_slug')).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(500);

    // Fill org details
    await page.locator('input#org_slug').fill(promoOrgSlug);
    await page.locator('input#org_name').fill(promoOrgName);

    // Wait for admin dropdown to load
    const adminSelect = page.locator('select#admin_user');
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });

    await page.waitForFunction(
      () => {
        const select = document.querySelector('select#admin_user');
        return select && select.options && select.options.length > 1;
      },
      { timeout: 15_000 }
    ).catch(() => page.waitForTimeout(3000));

    // Find and select our test user
    const options = await adminSelect.locator("option").all();
    let foundOption = false;
    for (const option of options) {
      const text = await option.textContent();
      if (text && text.includes(testUserEmail)) {
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
      throw new Error(`Could not find option for user: ${testUserEmail}. Available: ${availableOptions.join(', ')}`);
    }

    await page.waitForTimeout(500);

    // Submit
    const submitButton = page.locator('.fixed.inset-0').getByRole("button", { name: /^create organization$/i });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click({ force: true });

    // Wait for success
    await expect(page.getByText(/organization created successfully/i)).toBeVisible({ timeout: 15_000 });

    console.log(`Organization "${promoOrgName}" created with "${testUserEmail}" as admin.`);
  });

  test("6. Open Members modal and verify user is shown as Admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for our org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(promoOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`tr:has-text("${promoOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Click the Members button
    const membersButton = orgRow.getByRole("button", { name: /members/i });
    await expect(membersButton).toBeVisible({ timeout: 5_000 });
    await membersButton.click();

    // Wait for the members modal to appear
    const modalTitle = page.getByText(`Members: ${promoOrgName}`);
    await expect(modalTitle).toBeVisible({ timeout: 10_000 });

    // Wait for members table to load
    await page.waitForTimeout(2000);

    // Verify the test user appears in the members list
    const memberRow = page.locator(`tr:has-text("${testUserEmail}")`);
    await expect(memberRow).toBeVisible({ timeout: 10_000 });

    // Verify user's current role is Admin (they were assigned admin during org creation)
    await expect(memberRow.locator('text=Admin')).toBeVisible();

    // Verify a Demote button is visible (since user is admin)
    const demoteButton = memberRow.getByRole("button", { name: /demote/i });
    await expect(demoteButton).toBeVisible();

    console.log(`Members modal shows "${testUserEmail}" as Admin with Demote button.`);
  });

  test("7. Demote user from Admin to Member", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for our org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(promoOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row and click Members
    const orgRow = page.locator(`tr:has-text("${promoOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });
    await orgRow.getByRole("button", { name: /members/i }).click();

    // Wait for the members modal
    await expect(page.getByText(`Members: ${promoOrgName}`)).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(2000);

    // Find the member row
    const memberRow = page.locator(`tr:has-text("${testUserEmail}")`);
    await expect(memberRow).toBeVisible({ timeout: 10_000 });

    // Click Demote
    const demoteButton = memberRow.getByRole("button", { name: /demote/i });
    await expect(demoteButton).toBeVisible();
    await demoteButton.click();

    // Wait for success message
    await expect(page.getByText(/role updated.*member.*successfully/i)).toBeVisible({ timeout: 10_000 });

    // Verify role changed to Member
    await page.waitForTimeout(1000);
    await expect(memberRow.locator('span:has-text("Member")')).toBeVisible({ timeout: 5_000 });

    // Verify a Promote button is now visible
    const promoteButton = memberRow.getByRole("button", { name: /promote/i });
    await expect(promoteButton).toBeVisible();

    console.log(`User "${testUserEmail}" demoted to Member.`);
  });

  test("8. Promote user from Member to Admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for our org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(promoOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row and click Members
    const orgRow = page.locator(`tr:has-text("${promoOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });
    await orgRow.getByRole("button", { name: /members/i }).click();

    // Wait for the members modal
    await expect(page.getByText(`Members: ${promoOrgName}`)).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(2000);

    // Find the member row
    const memberRow = page.locator(`tr:has-text("${testUserEmail}")`);
    await expect(memberRow).toBeVisible({ timeout: 10_000 });

    // Click Promote
    const promoteButton = memberRow.getByRole("button", { name: /promote/i });
    await expect(promoteButton).toBeVisible();
    await promoteButton.click();

    // Wait for success message
    await expect(page.getByText(/role updated.*admin.*successfully/i)).toBeVisible({ timeout: 10_000 });

    // Verify role changed to Admin
    await page.waitForTimeout(1000);
    await expect(memberRow.locator('span:has-text("Admin")')).toBeVisible({ timeout: 5_000 });

    // Verify a Demote button is now visible
    const demoteButton = memberRow.getByRole("button", { name: /demote/i });
    await expect(demoteButton).toBeVisible();

    console.log(`User "${testUserEmail}" promoted to Admin.`);
  });

  test("9. Members modal shows helpful note about LTI Creator users", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for our org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(promoOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row and click Members
    const orgRow = page.locator(`tr:has-text("${promoOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });
    await orgRow.getByRole("button", { name: /members/i }).click();

    // Wait for the members modal
    await expect(page.getByText(`Members: ${promoOrgName}`)).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1500);

    // Verify the note about LTI Creator users
    await expect(page.getByText(/any user.*including lti creator.*can be promoted/i)).toBeVisible({ timeout: 10_000 });

    // Close the modal (use the text "Close" button at the bottom, not the X icon)
    const closeButton = page.locator('.fixed.inset-0').getByRole("button", { name: /^close$/i }).last();
    await closeButton.click();
    await expect(page.getByText(`Members: ${promoOrgName}`)).not.toBeVisible({ timeout: 5_000 });

    console.log("Members modal shows LTI Creator promotion note and closes correctly.");
  });

  // ============================================
  // PART 3: Cleanup
  // ============================================

  test("10. Cleanup: Delete org without admin", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for the no-admin org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(noAdminOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`tr:has-text("${noAdminOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Click delete button
    const deleteButton = orgRow.getByRole("button", { name: /delete organization/i });
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Confirm deletion
    const modal = page.getByRole("dialog", { name: /delete organization/i });
    await expect(modal).toBeVisible({ timeout: 5_000 });
    const confirmButton = modal.getByRole("button", { name: /^delete$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to close and org to be removed
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(orgRow).not.toBeVisible({ timeout: 10_000 });

    console.log(`Cleanup: Organization "${noAdminOrgSlug}" deleted.`);
  });

  test("11. Cleanup: Delete promotion test org", async ({ page }) => {
    await page.goto("admin?view=organizations");
    await page.waitForLoadState("networkidle");

    // Search for the promotion org
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(promoOrgSlug);
      await page.waitForTimeout(500);
    }

    // Find the org row
    const orgRow = page.locator(`tr:has-text("${promoOrgSlug}")`);
    await expect(orgRow).toBeVisible({ timeout: 10_000 });

    // Click delete button
    const deleteButton = orgRow.getByRole("button", { name: /delete organization/i });
    await expect(deleteButton).toBeVisible({ timeout: 5_000 });
    await deleteButton.click();

    // Confirm deletion
    const modal = page.getByRole("dialog", { name: /delete organization/i });
    await expect(modal).toBeVisible({ timeout: 5_000 });
    const confirmButton = modal.getByRole("button", { name: /^delete$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to close and org to be removed
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(orgRow).not.toBeVisible({ timeout: 10_000 });

    console.log(`Cleanup: Organization "${promoOrgSlug}" deleted.`);
  });

  test("12. Cleanup: Disable test user", async ({ page }) => {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    // Search for the user
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(testUserEmail);
      await page.waitForTimeout(500);
    }

    // Find the user row
    const userRow = page.locator(`tr:has-text("${testUserEmail}")`);
    await expect(userRow).toBeVisible({ timeout: 10_000 });

    // Click the disable button
    const disableButton = userRow.getByRole("button", { name: /disable/i }).first();
    await expect(disableButton).toBeVisible({ timeout: 5_000 });
    await disableButton.click();

    // Confirm in modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    const confirmButton = modal.getByRole("button", { name: /^disable$/i });
    await expect(confirmButton).toBeVisible({ timeout: 5_000 });
    await confirmButton.click();

    // Wait for modal to close and status change
    await expect(modal).not.toBeVisible({ timeout: 10_000 });
    await expect(userRow.getByText("Disabled")).toBeVisible({ timeout: 10_000 });

    console.log(`Cleanup: User "${testUserEmail}" disabled.`);
  });
});
