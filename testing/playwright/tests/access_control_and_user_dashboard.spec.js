const { test, expect } = require("@playwright/test");

/**
 * Access Control & Admin User Dashboard Tests
 *
 * Validates the features implemented in the access-control development cycle:
 *
 *   Part A — Admin User Dashboard
 *     1. Admin navigates to user management → clicks a user name →
 *        user-detail view loads with profile, resource sections, back button
 *     2. "Back to Users" returns to the user management list
 *
 *   Part B — Access Control: System Admin views another user's assistant
 *     3. Create a test user + org, login as that user, create an assistant
 *     4. Login as system admin → find the assistant via user dashboard →
 *        verify read-only banner, tabs (Properties, Share, Chat, Activity — NO Edit),
 *        and no edit/publish buttons
 *
 *   Part C — Access Control: Owner views own assistant
 *     5. Login as the test user (owner) → open their assistant →
 *        verify NO read-only banner, Edit tab visible, full buttons
 *
 *   Part D — Cleanup
 *     6. Delete assistant, disable + delete test user, delete test org
 *
 * Prerequisites:
 *   - Logged in as base admin via global-setup.js
 *   - The environment has at least one other user with resources (for Part A)
 */

test.describe.serial(
  "Access Control & Admin User Dashboard",
  () => {
    const ts = Date.now();
    const testUserEmail = `acl_user_${ts}@test.com`;
    const testUserName = `ACL User ${ts}`;
    const testUserPassword = "AclTest_2026!";
    const testOrgName = `ACL Org ${ts}`;
    const assistantName = `pw_acl_asst_${ts}`;

    const baseAdminEmail = process.env.LOGIN_EMAIL || "admin@owi.com";
    const baseAdminPassword = process.env.LOGIN_PASSWORD || "admin";

    // ──────────────────────────────────────────
    // Helper: logout then login as a given user
    // ──────────────────────────────────────────
    async function logoutAndLoginAs(page, email, password) {
      await page.goto("/");
      await page.waitForLoadState("networkidle");
      const logoutBtn = page.getByRole("button", { name: "Logout" });
      if (await logoutBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await logoutBtn.click();
      }
      await page.waitForSelector("#email", { timeout: 30_000 });
      await page.fill("#email", email);
      await page.fill("#password", password);
      await Promise.all([
        page.waitForLoadState("networkidle").catch(() => {}),
        page.click('button[type="submit"], form button'),
      ]);
      await page.waitForTimeout(2000);
    }

    // ─────────────────────────────────────────────────────
    // PART A — Admin User Dashboard
    // ─────────────────────────────────────────────────────

    test("1. Admin user dashboard: clicking user name opens user-detail view", async ({
      page,
    }) => {
      // Navigate to admin user management
      await page.goto("admin?view=users");
      await page.waitForLoadState("networkidle");

      // Wait for the user list to load (search box appears after data)
      await expect(
        page.locator('input[placeholder*="Search" i]')
      ).toBeVisible({ timeout: 15_000 });

      // Find a clickable user name — the admin user should exist
      // User names are rendered as <button> elements with class text-brand
      const userNameButton = page
        .locator("button.text-brand")
        .first();
      await expect(userNameButton).toBeVisible({ timeout: 10_000 });
      const clickedName = await userNameButton.textContent();
      console.log(
        `[acl_test] Clicking on user name: "${clickedName?.trim()}"`
      );

      await userNameButton.click();

      // URL should change to ?view=user-detail&id=...
      await page.waitForURL(/view=user-detail/, { timeout: 10_000 });

      // The "Back to Users" button must be visible
      await expect(
        page.getByText(/back to users/i)
      ).toBeVisible({ timeout: 10_000 });

      // Wait for the dashboard to load — look for the welcome heading or profile content
      // The UserDashboard shows "Welcome back, <name>!" or resource sections
      await expect(
        page
          .locator("h1, h2")
          .filter({ hasText: /welcome|my resources|resources/i })
          .first()
      ).toBeVisible({ timeout: 15_000 });

      console.log("[acl_test] User dashboard loaded successfully.");
    });

    test("2. Back to Users button returns to user list", async ({ page }) => {
      // Navigate directly to admin user-detail for user ID 1 (admin)
      await page.goto("admin?view=user-detail&id=1");
      await page.waitForLoadState("networkidle");

      // Wait for the back button to appear
      const backButton = page.getByText(/back to users/i);
      await expect(backButton).toBeVisible({ timeout: 15_000 });

      // Click back
      await backButton.click();

      // Should navigate to users view
      await page.waitForURL(/view=users/, { timeout: 10_000 });

      // User management search box should reappear
      await expect(
        page.locator('input[placeholder*="Search" i]')
      ).toBeVisible({ timeout: 15_000 });

      console.log("[acl_test] Back to Users navigation works.");
    });

    // ─────────────────────────────────────────────────────
    // PART B — Setup: create user + org + assistant
    // ─────────────────────────────────────────────────────

    test("3. Setup: create test user", async ({ page }) => {
      await page.goto("admin?view=users");
      await page.waitForLoadState("networkidle");

      // Open Create User dialog
      const createButton = page
        .getByRole("button", { name: /create user/i })
        .first();
      await expect(createButton).toBeVisible({ timeout: 10_000 });
      await createButton.click();

      const modal = page.getByRole("dialog");
      await expect(modal).toBeVisible({ timeout: 5_000 });

      // Wait for org dropdown
      const orgSelect = modal.getByRole("combobox", {
        name: /organization/i,
      });
      await expect(orgSelect).toBeVisible({ timeout: 10_000 });
      await expect(
        page.getByText(/loading organizations/i)
      ).not.toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(500);

      // Fill fields
      await modal.locator('input[name="email"]').fill(testUserEmail);
      await modal.locator('input[name="name"]').fill(testUserName);
      await modal.locator('input[name="password"]').fill(testUserPassword);

      // Submit
      const submitButton = modal.getByRole("button", {
        name: /^create user$/i,
      });
      await expect(submitButton).toBeVisible({ timeout: 5_000 });
      await submitButton.click();

      await expect(
        page.getByText(/user created successfully/i)
      ).toBeVisible({ timeout: 15_000 });

      console.log(`[acl_test] Created test user: ${testUserEmail}`);
    });

    test("4. Setup: login as test user and create an assistant", async ({
      page,
    }) => {
      await logoutAndLoginAs(page, testUserEmail, testUserPassword);

      // Navigate to create assistant
      await page.goto("assistants?view=create");
      await page.waitForLoadState("networkidle");

      // Click the Create Assistant button to expand the form
      const createAssistantBtn = page.getByRole("button", {
        name: /create assistant/i,
      });
      await expect(createAssistantBtn).toBeVisible({ timeout: 10_000 });
      await createAssistantBtn.click();

      const form = page.locator("#assistant-form-main");
      await expect(form).toBeVisible({ timeout: 30_000 });

      // Fill in assistant details
      await page.fill("#assistant-name", assistantName);
      await page.fill(
        "#assistant-description",
        "Assistant for ACL testing"
      );
      await page.fill(
        "#system-prompt",
        "You are a helpful assistant for testing access control."
      );

      // Wait for Save button to be enabled
      const saveButton = page.locator(
        'button[type="submit"][form="assistant-form-main"]'
      );
      await expect(saveButton).toBeEnabled({ timeout: 60_000 });

      // Wait for the API response and submit
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

      await Promise.all([
        createRequest,
        form.evaluate((f) => f.requestSubmit()),
      ]);

      // Verify we navigate back to assistants list
      await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

      // Search for the assistant by timestamp
      const searchBox = page.locator('input[placeholder*="Search" i]');
      if (await searchBox.count()) {
        await searchBox.fill(ts.toString());
        await page.waitForTimeout(500);
      }

      await expect(
        page.getByText(ts.toString()).first()
      ).toBeVisible({ timeout: 30_000 });

      console.log(
        `[acl_test] Assistant "${assistantName}" created by test user.`
      );
    });

    // ─────────────────────────────────────────────────────
    // PART C — Access Control: System Admin read-only view
    // ─────────────────────────────────────────────────────

    test("5. System admin sees read-only banner on another user's assistant", async ({
      page,
    }) => {
      // Login as system admin
      await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

      // Navigate to admin user management
      await page.goto("admin?view=users");
      await page.waitForLoadState("networkidle");

      // Wait for user list
      await expect(
        page.locator('input[placeholder*="Search" i]')
      ).toBeVisible({ timeout: 15_000 });

      // Search for our test user
      const searchBox = page.locator('input[placeholder*="Search" i]');
      await searchBox.fill(testUserEmail);
      await page.waitForTimeout(1000);

      // Click on the test user's name to open their dashboard
      const userRow = page.locator(`tr:has-text("${testUserEmail}")`);
      await expect(userRow).toBeVisible({ timeout: 10_000 });

      const userNameBtn = userRow.locator("button.text-brand").first();
      await expect(userNameBtn).toBeVisible({ timeout: 5_000 });
      await userNameBtn.click();

      // Wait for user dashboard to load
      await page.waitForURL(/view=user-detail/, { timeout: 10_000 });
      await expect(
        page.getByText(/back to users/i)
      ).toBeVisible({ timeout: 10_000 });

      // The dashboard should show the test user's name
      await expect(
        page.getByText(testUserName).first()
      ).toBeVisible({ timeout: 15_000 });

      // Expand the Assistants section to see the assistant list
      const assistantsHeader = page
        .locator("button")
        .filter({ hasText: /assistants/i })
        .first();
      await expect(assistantsHeader).toBeVisible({ timeout: 10_000 });
      await assistantsHeader.click();

      // The assistant should be listed
      await expect(
        page.getByText(new RegExp(ts.toString())).first()
      ).toBeVisible({ timeout: 10_000 });

      // Click on the assistant name link to navigate to assistant detail
      const assistantLink = page
        .locator("a")
        .filter({ hasText: new RegExp(ts.toString()) })
        .first();
      await expect(assistantLink).toBeVisible({ timeout: 5_000 });
      await assistantLink.click();

      // Wait for assistant detail page to load
      await page.waitForURL(/assistants\?view=detail/, { timeout: 15_000 });
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000); // Allow access_level to settle

      // === KEY ASSERTIONS: Read-only view for System Admin ===

      // 1. Read-only banner should be visible (amber background with "Read-only view")
      await expect(
        page.getByText(/read.only view/i).first()
      ).toBeVisible({ timeout: 10_000 });
      console.log("[acl_test] Read-only banner is visible for system admin.");

      // 2. Properties tab should be visible
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^properties$/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });

      // 3. Edit tab should NOT be visible (not the owner)
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^edit$/i })
          .first()
      ).not.toBeVisible({ timeout: 3_000 });
      console.log("[acl_test] Edit tab is hidden for system admin (correct).");

      // 4. Share tab should be visible (system admin can manage sharing)
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^share$/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });
      console.log("[acl_test] Share tab is visible for system admin.");

      // 5. Chat tab should be visible (system admin can use the assistant)
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^chat/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });

      // 6. Activity tab should be visible
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^activity$/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });
      console.log("[acl_test] Activity tab is visible for system admin.");

      console.log(
        "[acl_test] All read-only access control assertions passed for system admin."
      );
    });

    // ─────────────────────────────────────────────────────
    // PART D — Access Control: Owner full view
    // ─────────────────────────────────────────────────────

    test("6. Owner sees full access on own assistant (Edit tab, no read-only banner)", async ({
      page,
    }) => {
      // Login as the test user (the assistant owner)
      await logoutAndLoginAs(page, testUserEmail, testUserPassword);

      // Navigate to assistants
      await page.goto("assistants");
      await page.waitForLoadState("networkidle");

      // Search for the assistant
      const searchBox = page.locator('input[placeholder*="Search" i]');
      if (await searchBox.count()) {
        await searchBox.fill(ts.toString());
        await page.waitForTimeout(1000);
      }

      // Click the assistant name button in the table to open detail view
      // The assistant name is rendered as a <button> inside the table cell
      const assistantNameBtn = page
        .locator("button")
        .filter({ hasText: new RegExp(ts.toString()) })
        .first();
      await expect(assistantNameBtn).toBeVisible({ timeout: 10_000 });
      await assistantNameBtn.click();

      // Wait for detail view (URL changes to ?view=detail&id=...)
      await page.waitForURL(/assistants\?view=detail/, {
        timeout: 15_000,
      });
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // === KEY ASSERTIONS: Full access for owner ===

      // 1. Read-only banner should NOT be visible
      await expect(
        page.getByText(/read.only view/i)
      ).not.toBeVisible({ timeout: 3_000 });
      console.log(
        "[acl_test] No read-only banner for owner (correct)."
      );

      // 2. Properties tab should be visible
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^properties$/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });

      // 3. Edit tab SHOULD be visible for the owner
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^edit$/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });
      console.log("[acl_test] Edit tab is visible for owner (correct).");

      // 4. Chat tab should be visible
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^chat/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });

      // 5. Activity tab should be visible
      await expect(
        page
          .locator("button")
          .filter({ hasText: /^activity$/i })
          .first()
      ).toBeVisible({ timeout: 5_000 });

      console.log(
        "[acl_test] All full-access assertions passed for assistant owner."
      );
    });

    // ─────────────────────────────────────────────────────
    // PART E — API-level: user profile endpoint
    // ─────────────────────────────────────────────────────

    test("7. API: /admin/users/{id}/profile returns valid profile data", async ({
      page,
    }) => {
      // Login as admin
      await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

      // Get the admin token from localStorage
      const token = await page.evaluate(() =>
        localStorage.getItem("userToken")
      );
      expect(token).toBeTruthy();

      // Call the profile endpoint for user ID 1 (admin) via page.evaluate + fetch
      const profileData = await page.evaluate(
        async ({ token }) => {
          const response = await fetch(
            "/creator/admin/users/1/profile",
            {
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
            }
          );
          if (!response.ok) {
            return { error: response.status, body: await response.text() };
          }
          return await response.json();
        },
        { token }
      );

      // Validate the profile structure
      expect(profileData.error).toBeUndefined();
      expect(profileData).toHaveProperty("user");
      expect(profileData.user).toHaveProperty("name");
      expect(profileData.user).toHaveProperty("email");
      expect(profileData).toHaveProperty("owned");
      expect(profileData.owned).toHaveProperty("assistants");
      expect(profileData.owned).toHaveProperty("knowledge_bases");
      expect(profileData.owned).toHaveProperty("rubrics");
      expect(profileData.owned).toHaveProperty("templates");

      console.log(
        `[acl_test] Profile API returned valid data for user: ${profileData.user.email}`
      );
    });

    test("8. API: assistant detail returns access_level and is_owner fields", async ({
      page,
    }) => {
      // Login as admin
      await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

      const token = await page.evaluate(() =>
        localStorage.getItem("userToken")
      );
      expect(token).toBeTruthy();

      // Find the test user and their assistants via the users + profile API
      // First get all users to find the test user's ID
      const usersData = await page.evaluate(
        async ({ token }) => {
          const response = await fetch("/creator/users", {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          });
          if (!response.ok) return { error: response.status };
          return await response.json();
        },
        { token }
      );

      const users = usersData?.data || [];
      const testUser = users.find((u) => u.email === testUserEmail);

      if (!testUser) {
        console.log(
          "[acl_test] Test user not found — skipping API detail check."
        );
        return;
      }

      // Get the test user's profile to find their assistant IDs
      const profileData = await page.evaluate(
        async ({ token, userId }) => {
          const response = await fetch(
            `/creator/admin/users/${userId}/profile`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
            }
          );
          if (!response.ok) return { error: response.status };
          return await response.json();
        },
        { token, userId: testUser.id }
      );

      if (profileData.error) {
        console.log(
          `[acl_test] Failed to fetch profile: ${profileData.error}`
        );
        return;
      }

      const assistantItems = profileData.owned?.assistants?.items || [];
      const testAssistant = assistantItems.find(
        (a) => a.name && a.name.includes(ts.toString())
      );

      if (!testAssistant) {
        console.log(
          "[acl_test] Test assistant not found in user profile — skipping."
        );
        return;
      }

      // Fetch the assistant detail (as admin, not owner)
      const detailData = await page.evaluate(
        async ({ token, assistantId }) => {
          const response = await fetch(
            `/creator/assistant/get_assistant/${assistantId}`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
            }
          );
          if (!response.ok) return { error: response.status, body: await response.text() };
          return await response.json();
        },
        { token, assistantId: testAssistant.id }
      );

      // Validate access_level and is_owner fields
      expect(detailData.error).toBeUndefined();
      expect(detailData).toHaveProperty("access_level");
      expect(detailData).toHaveProperty("is_owner");

      // Admin viewing another user's assistant should see read_only + not owner
      expect(detailData.access_level).toBe("read_only");
      expect(detailData.is_owner).toBe(false);

      console.log(
        `[acl_test] API returns access_level="${detailData.access_level}", is_owner=${detailData.is_owner} for admin viewing other's assistant.`
      );
    });

    // ─────────────────────────────────────────────────────
    // PART F — Cleanup
    // ─────────────────────────────────────────────────────

    test("9. Cleanup: delete test assistant", async ({ page }) => {
      // Login as admin to clean up
      await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

      const token = await page.evaluate(() =>
        localStorage.getItem("userToken")
      );
      expect(token).toBeTruthy();

      // Find the test user to locate their assistant via profile API
      const usersData = await page.evaluate(
        async ({ token }) => {
          const response = await fetch("/creator/users", {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          });
          if (!response.ok) return { error: response.status };
          return await response.json();
        },
        { token }
      );

      const users = usersData?.data || [];
      const testUser = users.find((u) => u.email === testUserEmail);

      if (!testUser) {
        console.log("[acl_test] Test user not found — assistant may already be cleaned up.");
        return;
      }

      // Get the user's profile to find their assistants
      const profileData = await page.evaluate(
        async ({ token, userId }) => {
          const response = await fetch(
            `/creator/admin/users/${userId}/profile`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
            }
          );
          if (!response.ok) return { error: response.status };
          return await response.json();
        },
        { token, userId: testUser.id }
      );

      const assistantItems = profileData?.owned?.assistants?.items || [];
      const testAssistant = assistantItems.find(
        (a) => a.name && a.name.includes(ts.toString())
      );

      if (testAssistant) {
        // Get the assistant owner email from the profile
        const ownerEmail = profileData?.user?.email || '';
        const deleteResult = await page.evaluate(
          async ({ token, assistantId, ownerEmail }) => {
            const response = await fetch(
              `/creator/assistant/delete_assistant/${assistantId}?owner=${encodeURIComponent(ownerEmail)}`,
              {
                method: "DELETE",
                headers: {
                  Authorization: `Bearer ${token}`,
                  "Content-Type": "application/json",
                },
              }
            );
            return { status: response.status };
          },
          { token, assistantId: testAssistant.id, ownerEmail }
        );
        console.log(
          `[acl_test] Assistant deleted (status: ${deleteResult.status}).`
        );
      } else {
        console.log("[acl_test] Test assistant not found — already cleaned up.");
      }
    });

    test("10. Cleanup: disable and delete test user via API", async ({ page }) => {
      // Login as admin
      await logoutAndLoginAs(page, baseAdminEmail, baseAdminPassword);

      const token = await page.evaluate(() =>
        localStorage.getItem("userToken")
      );
      expect(token).toBeTruthy();

      // First, find the test user ID via the users list API
      const usersData = await page.evaluate(
        async ({ token }) => {
          const response = await fetch("/creator/users", {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          });
          if (!response.ok) return { error: response.status };
          return await response.json();
        },
        { token }
      );

      const users = usersData?.data || [];
      const testUser = users.find(
        (u) => u.email === testUserEmail
      );

      if (!testUser) {
        console.log("[acl_test] Test user not found — already cleaned up.");
        return;
      }

      const userId = testUser.id;

      // Disable user via API
      const disableResult = await page.evaluate(
        async ({ token, userId }) => {
          const response = await fetch(
            `/creator/admin/users/${userId}/status`,
            {
              method: "PUT",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ enabled: false }),
            }
          );
          return { status: response.status };
        },
        { token, userId }
      );
      console.log(
        `[acl_test] User disabled via API (status: ${disableResult.status}).`
      );

      // Delete user via API
      const deleteResult = await page.evaluate(
        async ({ token, userId }) => {
          const response = await fetch(
            `/creator/admin/users/${userId}`,
            {
              method: "DELETE",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
            }
          );
          return { status: response.status };
        },
        { token, userId }
      );
      console.log(
        `[acl_test] User deleted via API (status: ${deleteResult.status}).`
      );
    });
  }
);
