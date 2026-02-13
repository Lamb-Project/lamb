const { test: base, expect } = require("@playwright/test");

/**
 * Account Disable Security Tests (Dual Browser)
 *
 * Verifies security layers work when a user is disabled while actively using the app.
 *
 * Flow:
 *   1. Admin1 creates Admin2
 *   2. Admin2 logs in (separate browser)  
 *   3. Admin1 disables Admin2
 *   4. Admin2 tries to disable Admin1 → Error
 *   5. Admin2 tries to navigate → Forced logout
 *   6. Direct URL access blocked
 *   7. Cleanup
 */

// Extended test fixture with dual pages
const test = base.extend({
  admin1Page: async ({ page }, use) => {
    await use(page); // Default page from global-setup (Admin1)
  },
  admin2Page: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
});

test.describe.serial("Account Disable Security (Dual Browser)", () => {
  const timestamp = Date.now();
  const admin2Email = `admin2_sec_${timestamp}@test.com`;
  const admin2Name = `Admin2Sec${timestamp}`;
  const admin2Password = "TestSecure_456!";

  const baseAdminEmail = process.env.LOGIN_EMAIL || "admin@owi.com";

  test("1. Admin1 creates Admin2", async ({ admin1Page }) => {
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("networkidle");

    const createButton = admin1Page.getByRole("button", { name: /create user/i }).first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const modal = admin1Page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    await admin1Page.waitForTimeout(500);

    await modal.getByRole("textbox", { name: "Email *" }).fill(admin2Email);
    await modal.getByRole("textbox", { name: "Name *" }).fill(admin2Name);
    await modal.getByRole("textbox", { name: "Password *" }).fill(admin2Password);
    await modal.getByLabel("Role").selectOption("admin");

    const submit = modal.getByRole("button", { name: "Create User" });
    await submit.click();

    await admin1Page.waitForTimeout(2000);

    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    if (await searchBox.count()) {
      await searchBox.fill(admin2Email);
      await admin1Page.waitForTimeout(500);
    }

    await expect(admin1Page.getByText(admin2Email)).toBeVisible({ timeout: 10_000 });
    console.log(`[security] Admin1 created ${admin2Email}`);
  });

  test("2. Admin2 logs in (separate browser)", async ({ admin1Page, admin2Page }) => {
    const baseURL = admin1Page.url().split("/")[0] + "//" + admin1Page.url().split("/")[2];
    
    console.log(`[security] Admin2 logging in at ${baseURL}`);
    
    await admin2Page.goto(baseURL);
    await admin2Page.waitForLoadState("domcontentloaded");
    
    await admin2Page.waitForSelector("#email", { timeout: 10_000 });
    await admin2Page.getByRole("textbox", { name: "Email" }).fill(admin2Email);
    await admin2Page.getByRole("textbox", { name: "Password" }).fill(admin2Password);
    
    await Promise.all([
      admin2Page.waitForLoadState("networkidle").catch(() => {}),
      admin2Page.getByRole("button", { name: "Login" }).click()
    ]);
    
    await admin2Page.waitForTimeout(2000);

    await expect(admin2Page.getByRole("link", { name: "Admin" })).toBeVisible({ timeout: 10_000 });
    console.log(`[security] Admin2 logged in successfully`);
  });

  test("3. Admin2 navigates to users page", async ({ admin2Page }) => {
    await admin2Page.goto("/admin?view=users");
    await admin2Page.waitForLoadState("networkidle");

    await expect(
      admin2Page.getByRole("button", { name: "Users", exact: true })
    ).toBeVisible({ timeout: 10_000 });

    console.log(`[security] Admin2 on users page`);
  });

  test("4. Admin1 disables Admin2", async ({ admin1Page }) => {
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("networkidle");

    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const userRow = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    await expect(userRow).toBeVisible({ timeout: 5_000 });

    const disableButton = userRow.getByLabel("Disable User");
    await disableButton.click();

    const confirmButton = admin1Page.getByRole("button", { name: "Disable", exact: true });
    await confirmButton.click();

    await admin1Page.waitForTimeout(2000);

    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const disabledRow = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    await expect(disabledRow.getByLabel("Enable User")).toBeVisible({ timeout: 5_000 });

    console.log(`[security] Admin1 disabled ${admin2Email}`);
  });

  test("5. Admin2 tries to disable Admin1 → Error", async ({ admin2Page }) => {
    const searchBox = admin2Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(baseAdminEmail);
    await admin2Page.waitForTimeout(500);

    const admin1Row = admin2Page.getByRole("row", { name: new RegExp(baseAdminEmail, "i") });

    let dialogMessage = "";
    admin2Page.once("dialog", async (dialog) => {
      dialogMessage = dialog.message();
      console.log(`[security] Error: ${dialogMessage}`);
      await dialog.accept();
    });

    const disableBtn = admin1Row.getByLabel("Disable User");
    if (await disableBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await disableBtn.click();

      const confirmBtn = admin2Page.getByRole("button", { name: "Disable", exact: true });
      if (await confirmBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await confirmBtn.click();
      }
    }

    await admin2Page.waitForTimeout(2000);

    expect(dialogMessage).not.toBe("");
    expect(admin2Page.url()).toContain("/admin");

    console.log(`[security] Admin2 got error, stayed on page`);
  });

  test("6. Admin2 navigates → Forced logout", async ({ admin2Page }) => {
    const responsePromise = admin2Page.waitForResponse(
      (res) => res.status() === 403,
      { timeout: 10_000 }
    ).catch(() => null);

    const orgButton = admin2Page.getByRole("button", { name: "Organizations" });
    await expect(orgButton).toBeVisible({ timeout: 5_000 });
    await orgButton.click();

    const response = await responsePromise;
    if (response) {
      console.log(`[security] Detected 403`);
    }

    await admin2Page.waitForURL(/\/$/, { timeout: 10_000 });

    await expect(admin2Page.getByRole("textbox", { name: "Email" })).toBeVisible({ timeout: 5_000 });

    const token = await admin2Page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeNull();

    console.log(`[security] Admin2 forced logout`);
  });

  test("7. Direct URL access blocked", async ({ admin2Page }) => {
    const protectedUrls = ["/assistants", "/knowledgebases", "/admin"];

    for (const url of protectedUrls) {
      await admin2Page.goto(url);
      await admin2Page.waitForURL(/\/$/, { timeout: 5_000 });

      const emailInput = admin2Page.getByRole("textbox", { name: "Email" });
      await expect(emailInput).toBeVisible({ timeout: 3_000 });

      console.log(`[security] ${url} blocked`);
    }
  });

  test("8. Cleanup", async ({ admin1Page }) => {
    await admin1Page.goto("/admin?view=users");
    await admin1Page.waitForLoadState("networkidle");

    const searchBox = admin1Page.getByRole("textbox", { name: /search users by name, email/i });
    await searchBox.fill(admin2Email);
    await admin1Page.waitForTimeout(500);

    const userRow = admin1Page.getByRole("row", { name: new RegExp(admin2Email, "i") });
    const deleteButton = userRow.getByLabel("Delete User");
    await deleteButton.click();

    const confirmButton = admin1Page.getByRole("button", { name: /delete|confirm/i });
    await confirmButton.click();

    await admin1Page.waitForTimeout(2000);

    console.log(`[security] Cleanup done`);
  });
});
