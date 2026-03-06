const { test, expect, chromium } = require("@playwright/test");
const fs = require("fs");

/**
 * Organization Migration Flow Test
 *
 * Uses persistent browser contexts (one per actor) so the same session
 * is reused across every test, avoiding the storageState/expired-token
 * problem that appears when each test gets a fresh page fixture.
 *
 * Actors:
 *   adminPage  — system admin (tests 1-4, 8-10, 14)
 *   user1Page  — org-admin creator  (tests 5, 11)
 *   user2Page  — creator member     (tests 6, 12)
 *   user3Page  — end_user member    (tests 7, 13)
 *
 * Flow:
 *   1.  (Admin) Create org-admin user (user1)
 *   2.  (Admin) Create source organization with user1 as admin
 *   3.  (Admin) Create creator user (user2) assigned to source org
 *   4.  (Admin) Create end_user (user3) assigned to source org
 *   5.  (User1) Login and create assistant "asst_admin_<ts>"
 *   6.  (User2) Login, create assistant "asst_creator_<ts>" + knowledge base
 *   7.  (User3) Login and verify access
 *   8.  (Admin) Create empty target organization
 *   9.  (Admin) Migrate source -> target (preserve roles, delete source)
 *   10. (Admin) Verify target org has 3 users and 2 assistants
 *   11. (User1) Verify login + assistant still exist after migration
 *   12. (User2) Verify login + assistant + KB still exist after migration
 *   13. (User3) Verify login still works after migration
 *   14. (Admin) Cleanup: delete target org + disable test users
 */

test.describe.serial("Organization Migration Flow", () => {
  const ts = Date.now();

  // Credentials
  const adminEmail    = process.env.LOGIN_EMAIL    || "admin@owi.com";
  const adminPassword = process.env.LOGIN_PASSWORD || "admin";
  const testPassword  = "TestMigr_123!";
  const baseURL       = process.env.BASE_URL       || "http://localhost:9099/";

  // Test users
  const user1Email = `mig_admin_${ts}@test.com`;
  const user1Name  = `Mig Admin ${ts}`;
  const user2Email = `mig_creator_${ts}@test.com`;
  const user2Name  = `Mig Creator ${ts}`;
  const user3Email = `mig_enduser_${ts}@test.com`;
  const user3Name  = `Mig EndUser ${ts}`;

  // Organizations
  const sourceOrgSlug = `mig-src-${ts}`;
  const sourceOrgName = `Mig Source ${ts}`;
  const targetOrgSlug = `mig-tgt-${ts}`;
  const targetOrgName = `Mig Target ${ts}`;

  // Assistant / KB names
  const asst1Name = `asst_admin_${ts}`;
  const asst2Name = `asst_creator_${ts}`;
  const kbName    = `kb_mig_${ts}`;

  // Persistent browser state
  let browser;
  let adminPage, user1Page, user2Page, user3Page;

  // beforeAll: launch browser + create one page per actor
  test.beforeAll(async () => {
    browser = await chromium.launch();

    // Admin context: try to reuse auth file, but we always re-login in test 1
    const authFile = ".auth/state.json";
    const adminContext = fs.existsSync(authFile)
      ? await browser.newContext({ storageState: authFile })
      : await browser.newContext();
    adminPage = await adminContext.newPage();

    // User contexts: always fresh (no stored state)
    user1Page = await (await browser.newContext()).newPage();
    user2Page = await (await browser.newContext()).newPage();
    user3Page = await (await browser.newContext()).newPage();

    console.log(`[migration] Browser contexts ready. ts=${ts}`);
  });

  test.afterAll(async () => {
    await browser?.close();
    console.log(`[migration] Browser closed.`);
  });

  // ── Helpers ─────────────────────────────────────────────────────────────────

  /**
   * Ensure page is authenticated as the given user.
   * Handles: expired token banner, active session, broken session, login page.
   */
  async function loginAs(page, email, password) {
    await page.goto(baseURL);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1_500);

    // Expired-token banner
    const hasTokenError = await page
      .getByText(/invalid or expired authentication token/i)
      .isVisible()
      .catch(() => false);
    if (hasTokenError) {
      console.log(`  [loginAs] Expired token banner — clearing localStorage`);
      await page.evaluate(() => {
        localStorage.removeItem("userToken");
        localStorage.removeItem("user");
      });
      await page.reload();
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(1_000);
    }

    // Active session -> logout first
    const logoutBtn = page.getByRole("button", { name: "Logout" });
    if (await logoutBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      console.log(`  [loginAs] Active session found — logging out`);
      await logoutBtn.click();

      const formAfterLogout = await page.locator("#email").isVisible({ timeout: 5_000 }).catch(() => false);
      if (!formAfterLogout) {
        console.log(`  [loginAs] Login form did not appear after logout — force-clearing localStorage`);
        await page.evaluate(() => {
          localStorage.removeItem("userToken");
          localStorage.removeItem("user");
        });
        await page.reload();
        await page.waitForLoadState("domcontentloaded");
        await page.waitForTimeout(1_000);
      }
    } else {
      // No logout button: check login form visible, else force-clear
      const loginFormVisible = await page.locator("#email").isVisible({ timeout: 3_000 }).catch(() => false);
      if (!loginFormVisible) {
        console.log(`  [loginAs] No logout button and no login form — force-clearing localStorage`);
        await page.evaluate(() => {
          localStorage.removeItem("userToken");
          localStorage.removeItem("user");
        });
        await page.reload();
        await page.waitForLoadState("domcontentloaded");
        await page.waitForTimeout(1_000);
      }
    }

    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", email);
    await page.fill("#password", password);

    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click('button[type="submit"], form button'),
    ]);

    await page.waitForTimeout(2_000);
    console.log(`  [loginAs] Logged in as ${email}`);
  }

  /** Select a <select> option whose text contains the given string */
  async function selectOptionByText(selectLocator, text) {
    const options = await selectLocator.locator("option").all();
    for (const opt of options) {
      const t = await opt.textContent();
      if (t && t.includes(text)) {
        const value = await opt.getAttribute("value");
        if (value) { await selectLocator.selectOption(value); return; }
      }
    }
    const all = [];
    for (const opt of options) all.push(await opt.textContent());
    throw new Error(`Option containing "${text}" not found. Available: ${all.join(" | ")}`);
  }

  /** Create a user via the admin Users panel. adminPage must already be authenticated. */
  async function createUser(page, { email, name, password, userType, orgName }) {
    await page.goto("admin?view=users");
    await page.waitForLoadState("networkidle");

    const createBtn = page.getByRole("button", { name: /create user/i }).first();
    await expect(createBtn).toBeVisible({ timeout: 10_000 });
    await createBtn.click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await expect(modal.locator('input[name="email"]')).toBeVisible({ timeout: 5_000 });

    const orgSelect = modal.locator('select[name="organization_id"]');
    await expect(orgSelect).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/loading organizations/i)).not.toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(500);

    await modal.locator('input[name="email"]').fill(email);
    await modal.locator('input[name="name"]').fill(name);
    await modal.locator('input[name="password"]').fill(password);

    if (userType) await modal.locator('select[name="user_type"]').selectOption(userType);
    if (orgName) await selectOptionByText(orgSelect, orgName);

    await modal.getByRole("button", { name: /^create user$/i }).click();
    await expect(page.getByText(/user created successfully/i)).toBeVisible({ timeout: 15_000 });
    console.log(`  ✔ User created: ${email} (type=${userType ?? "creator"})`);
  }

  /** Create an assistant. Page must already be authenticated as the desired user. */
  async function createAssistant(page, assistantName) {
    await page.goto("assistants?view=create");
    await page.waitForLoadState("networkidle");

    const createBtn = page.getByRole("button", { name: /create assistant/i }).first();
    await expect(createBtn).toBeVisible({ timeout: 10_000 });
    await createBtn.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    await page.fill("#assistant-name", assistantName);
    await page.fill("#assistant-description", `Playwright migration test — ${assistantName}`);
    await page.fill("#system-prompt", "You are a helpful assistant created for migration testing.");

    const createResponse = page.waitForResponse((res) => {
      if (res.request().method() !== "POST") return false;
      try {
        return new URL(res.url()).pathname.endsWith("/assistant/create_assistant") &&
               res.status() >= 200 && res.status() < 300;
      } catch { return false; }
    });

    const saveBtn = page.locator('button[type="submit"][form="assistant-form-main"]');
    await expect(saveBtn).toBeEnabled({ timeout: 60_000 });

    await Promise.all([createResponse, form.evaluate((f) => f.requestSubmit())]);
    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) { await searchBox.fill(ts.toString()); await page.waitForTimeout(500); }
    await expect(page.getByText(ts.toString()).first()).toBeVisible({ timeout: 30_000 });
    console.log(`  ✔ Assistant "${assistantName}" created`);
  }

  // ═══════════════════════════════════════════════════════════════════
  // SETUP PHASE
  // ═══════════════════════════════════════════════════════════════════

  test("1. Admin: Login fresh and create org-admin user (user1)", async () => {
    await loginAs(adminPage, adminEmail, adminPassword);
    await createUser(adminPage, { email: user1Email, name: user1Name, password: testPassword, userType: "creator" });
  });

  test("2. Admin: Create source organization with user1 as admin", async () => {
    await adminPage.goto("admin?view=organizations");
    await adminPage.waitForLoadState("networkidle");

    const createBtn = adminPage.getByRole("button", { name: /create organization/i }).first();
    await expect(createBtn).toBeVisible({ timeout: 10_000 });
    await createBtn.click();

    await expect(adminPage.locator("input#org_slug")).toBeVisible({ timeout: 5_000 });
    await adminPage.waitForTimeout(500);

    await adminPage.locator("input#org_slug").fill(sourceOrgSlug);
    await adminPage.locator("input#org_name").fill(sourceOrgName);

    const adminSelect = adminPage.getByRole("combobox", { name: /organization admin/i });
    await expect(adminSelect).toBeVisible({ timeout: 10_000 });

    await adminPage.waitForFunction(
      () => { for (const s of document.querySelectorAll("select")) if (s.options?.length > 1) return true; return false; },
      { timeout: 15_000 }
    ).catch(() => adminPage.waitForTimeout(3_000));

    await selectOptionByText(adminSelect, user1Email);
    await adminPage.waitForTimeout(500);

    const submitBtn = adminPage.locator(".fixed.inset-0").getByRole("button", { name: /^create organization$/i });
    await expect(submitBtn).toBeVisible({ timeout: 5_000 });
    await submitBtn.click({ force: true });

    await expect(adminPage.getByText(/organization created successfully/i)).toBeVisible({ timeout: 15_000 });
    await expect(adminPage.getByText(sourceOrgSlug)).toBeVisible({ timeout: 10_000 });
    console.log(`  ✔ Source org "${sourceOrgName}" (${sourceOrgSlug}) created`);
  });

  test("3. Admin: Create creator user (user2) in source org", async () => {
    await createUser(adminPage, { email: user2Email, name: user2Name, password: testPassword, userType: "creator", orgName: sourceOrgName });
  });

  test("4. Admin: Create end_user (user3) in source org", async () => {
    await createUser(adminPage, { email: user3Email, name: user3Name, password: testPassword, userType: "end_user", orgName: sourceOrgName });
  });

  // ═══════════════════════════════════════════════════════════════════
  // CONTENT CREATION PHASE
  // ═══════════════════════════════════════════════════════════════════

  test("5. User1: Login and create assistant", async () => {
    await loginAs(user1Page, user1Email, testPassword);
    await createAssistant(user1Page, asst1Name);
  });

  test("6. User2: Login, create assistant and knowledge base", async () => {
    await loginAs(user2Page, user2Email, testPassword);
    await createAssistant(user2Page, asst2Name);

    await user2Page.goto("knowledge-bases");
    await user2Page.waitForLoadState("networkidle");

    const createKbBtn = user2Page.getByRole("button", { name: /create knowledge base/i }).first();
    await expect(createKbBtn).toBeVisible({ timeout: 10_000 });
    await createKbBtn.click();

    const kbModal = user2Page.getByRole("dialog");
    await expect(kbModal).toBeVisible({ timeout: 5_000 });

    const nameInput = kbModal.locator('input[name="name"], input[placeholder*="Name" i]').first();
    await expect(nameInput).toBeVisible({ timeout: 5_000 });
    await nameInput.fill(kbName);

    const descInput = kbModal.locator('textarea[name="description"], input[name="description"]').first();
    if (await descInput.count()) await descInput.fill("Migration test knowledge base");

    await kbModal.getByRole("button", { name: /create knowledge base/i }).click();
    await expect(user2Page.getByText(kbName)).toBeVisible({ timeout: 15_000 });
    console.log(`  ✔ Knowledge base "${kbName}" created`);
  });

  test("7. User3: Login and verify access", async () => {
    await loginAs(user3Page, user3Email, testPassword);
    const onLoginPage = await user3Page.locator("#email").isVisible({ timeout: 3_000 }).catch(() => false);
    expect(onLoginPage, "end_user should not be stuck on login page").toBe(false);
    console.log(`  ✔ User3 (end_user) logged in. URL: ${user3Page.url()}`);
  });

  // ═══════════════════════════════════════════════════════════════════
  // MIGRATION PHASE
  // ═══════════════════════════════════════════════════════════════════

  test("8. Admin: Create empty target organization", async () => {
    await adminPage.goto("admin?view=organizations");
    await adminPage.waitForLoadState("networkidle");

    const createBtn = adminPage.getByRole("button", { name: /create organization/i }).first();
    await expect(createBtn).toBeVisible({ timeout: 10_000 });
    await createBtn.click();

    await expect(adminPage.locator("input#org_slug")).toBeVisible({ timeout: 5_000 });
    await adminPage.waitForTimeout(500);

    await adminPage.locator("input#org_slug").fill(targetOrgSlug);
    await adminPage.locator("input#org_name").fill(targetOrgName);
    await adminPage.waitForTimeout(500);

    const submitBtn = adminPage.locator(".fixed.inset-0").getByRole("button", { name: /^create organization$/i });
    await expect(submitBtn).toBeVisible({ timeout: 5_000 });
    await submitBtn.click({ force: true });

    await expect(adminPage.getByText(/organization created successfully/i)).toBeVisible({ timeout: 15_000 });
    await expect(adminPage.getByText(targetOrgSlug)).toBeVisible({ timeout: 10_000 });
    console.log(`  ✔ Target org "${targetOrgName}" (${targetOrgSlug}) created (empty)`);
  });

  test("9. Admin: Execute migration (source -> target, preserve roles, delete source)", async () => {
    await adminPage.goto("admin?view=organizations");
    await adminPage.waitForLoadState("networkidle");

    const sb = adminPage.locator('input[placeholder*="Search" i]');
    if (await sb.count()) { await sb.fill(sourceOrgSlug); await adminPage.waitForTimeout(500); }

    const sourceRow = adminPage.locator(`tr:has-text("${sourceOrgSlug}")`).first();
    await expect(sourceRow).toBeVisible({ timeout: 10_000 });

    const migrateBtn = sourceRow.getByLabel(/migrate organization/i);
    await expect(migrateBtn).toBeVisible({ timeout: 5_000 });
    await migrateBtn.click();

    const migrationModal = adminPage.getByRole("dialog");
    await expect(migrationModal).toBeVisible({ timeout: 10_000 });

    const targetSelect = adminPage.getByLabel(/target organization/i);
    await expect(targetSelect).toBeVisible({ timeout: 10_000 });

    await adminPage.waitForFunction(
      () => { for (const s of document.querySelectorAll("select")) if (s.options?.length > 1) return true; return false; },
      { timeout: 15_000 }
    ).catch(() => adminPage.waitForTimeout(3_000));

    await selectOptionByText(targetSelect, targetOrgName);

    await adminPage.getByRole("button", { name: /validate migration/i }).click();
    await expect(adminPage.getByText(/3\s*(users?)?/i).first()).toBeVisible({ timeout: 15_000 });

    const preserveCheckbox = adminPage.getByRole("checkbox", { name: /preserve admin roles/i });
    await expect(preserveCheckbox).toBeVisible({ timeout: 5_000 });
    if (!(await preserveCheckbox.isChecked())) await preserveCheckbox.check();
    await expect(preserveCheckbox).toBeChecked();

    const deleteCheckbox = adminPage.getByRole("checkbox", { name: /delete source organization/i });
    await expect(deleteCheckbox).toBeVisible({ timeout: 5_000 });
    if (!(await deleteCheckbox.isChecked())) await deleteCheckbox.check();
    await expect(deleteCheckbox).toBeChecked();

    await adminPage.getByRole("button", { name: /execute migration/i }).click();
    await expect(adminPage.getByText(/migration completed successfully/i)).toBeVisible({ timeout: 30_000 });
    console.log(`  ✔ Migration executed successfully`);
  });

  // ═══════════════════════════════════════════════════════════════════
  // VERIFICATION PHASE
  // ═══════════════════════════════════════════════════════════════════

  test("10. Admin: Verify target org has 3 users and 2 assistants", async () => {
    await adminPage.goto("admin?view=organizations");
    await adminPage.waitForLoadState("networkidle");

    const sb = adminPage.locator('input[placeholder*="Search" i]');

    // Source org must be gone
    if (await sb.count()) { await sb.fill(sourceOrgSlug); await adminPage.waitForTimeout(500); }
    await expect(adminPage.locator(`tr:has-text("${sourceOrgSlug}")`)).not.toBeVisible({ timeout: 5_000 });
    console.log(`  ✔ Source org deleted`);

    // Expand target org detail
    if (await sb.count()) { await sb.fill(targetOrgSlug); await adminPage.waitForTimeout(500); }
    const targetRow = adminPage.locator(`tr:has-text("${targetOrgSlug}")`).first();
    await expect(targetRow).toBeVisible({ timeout: 10_000 });

    const orgDetailBtn = targetRow.getByRole("button", { name: new RegExp(targetOrgName, "i") });
    if (await orgDetailBtn.count()) { await orgDetailBtn.click(); } else { await targetRow.click(); }

    await adminPage.waitForLoadState("networkidle");
    await adminPage.waitForTimeout(1_000);

    await expect(adminPage.getByText(/3\s*active/i).first()).toBeVisible({ timeout: 10_000 });
    console.log(`  ✔ Target org shows 3 active users`);

    await expect(adminPage.getByText(/2\s*(published|assistants)/i).first()).toBeVisible({ timeout: 10_000 });
    console.log(`  ✔ Target org shows 2 assistants`);
  });

  test("11. User1: Verify assistant still exists after migration", async () => {
    // user1Page already has the logged-in session from test 5
    await user1Page.goto("assistants");
    await user1Page.waitForLoadState("networkidle");

    const sb = user1Page.locator('input[placeholder*="Search" i]');
    if (await sb.count()) { await sb.fill(ts.toString()); await user1Page.waitForTimeout(500); }

    await expect(user1Page.getByText(new RegExp("asst_admin", "i")).first()).toBeVisible({ timeout: 30_000 });
    console.log(`  ✔ User1's assistant visible after migration`);
  });

  test("12. User2: Verify assistant and KB still exist after migration", async () => {
    // user2Page already has the logged-in session from test 6
    await user2Page.goto("assistants");
    await user2Page.waitForLoadState("networkidle");

    const sb = user2Page.locator('input[placeholder*="Search" i]');
    if (await sb.count()) { await sb.fill(ts.toString()); await user2Page.waitForTimeout(500); }

    await expect(user2Page.getByText(new RegExp("asst_creator", "i")).first()).toBeVisible({ timeout: 30_000 });
    console.log(`  ✔ User2's assistant visible after migration`);

    await user2Page.goto("knowledge-bases");
    await user2Page.waitForLoadState("networkidle");
    await expect(user2Page.getByText(kbName)).toBeVisible({ timeout: 15_000 });
    console.log(`  ✔ User2's KB "${kbName}" visible after migration`);
  });

  test("13. User3: Verify session still valid after migration", async () => {
    // user3Page already has the logged-in session from test 7
    await user3Page.goto(baseURL);
    await user3Page.waitForLoadState("networkidle");

    const onLoginPage = await user3Page.locator("#email").isVisible({ timeout: 3_000 }).catch(() => false);
    expect(onLoginPage, "user3 should still be authenticated after migration").toBe(false);
    console.log(`  ✔ User3 session still valid. URL: ${user3Page.url()}`);
  });

  // ═══════════════════════════════════════════════════════════════════
  // CLEANUP PHASE
  // ═══════════════════════════════════════════════════════════════════

  test("14. Cleanup: Delete target org and disable test users", async () => {
    // Delete target org
    await adminPage.goto("admin?view=organizations");
    await adminPage.waitForLoadState("networkidle");

    const sb = adminPage.locator('input[placeholder*="Search" i]');
    if (await sb.count()) { await sb.fill(targetOrgSlug); await adminPage.waitForTimeout(500); }

    const targetRow = adminPage.locator(`tr:has-text("${targetOrgSlug}")`).first();
    if (await targetRow.count()) {
      const deleteOrgBtn = targetRow.getByRole("button", { name: /delete organization/i });
      if (await deleteOrgBtn.count()) {
        await deleteOrgBtn.click();
        const modal = adminPage.getByRole("dialog", { name: /delete organization/i });
        await expect(modal).toBeVisible({ timeout: 5_000 });
        await modal.getByRole("button", { name: /^delete$/i }).click();
        await expect(modal).not.toBeVisible({ timeout: 10_000 });
        console.log(`  ✔ Target org "${targetOrgSlug}" deleted`);
      }
    }

    // Disable all 3 test users
    for (const email of [user1Email, user2Email, user3Email]) {
      await adminPage.goto("admin?view=users");
      await adminPage.waitForLoadState("networkidle");

      const usb = adminPage.locator('input[placeholder*="Search" i]');
      if (await usb.count()) { await usb.fill(email); await adminPage.waitForTimeout(500); }

      const userRow = adminPage.locator(`tr:has-text("${email}")`).first();
      if (!(await userRow.count())) { console.log(`  ⚠ ${email} not found — skipping`); continue; }

      const disableBtn = userRow.getByRole("button", { name: /disable/i }).first();
      if (await disableBtn.count()) {
        await disableBtn.click();
        const modal = adminPage.getByRole("dialog");
        await expect(modal).toBeVisible({ timeout: 5_000 });
        await modal.getByRole("button", { name: /^disable$/i }).click();
        await expect(modal).not.toBeVisible({ timeout: 10_000 });
        console.log(`  ✔ ${email} disabled`);
      } else {
        console.log(`  ⚠ ${email} already disabled or button not found`);
      }
    }
  });
});
