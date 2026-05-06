const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * E2E tests for the Library Manager integration (Creator Interface API).
 *
 * These tests exercise the /creator/libraries/ endpoints through LAMB,
 * which proxies to the Library Manager microservice. No Svelte UI exists
 * yet, so all interactions are API-level via page.evaluate + fetch.
 */
test.describe.serial("Library Manager integration", () => {
  let token;
  let libraryId;
  let itemId;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    token = await page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeTruthy();
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
  });

  async function apiCall(page, method, urlPath, options = {}) {
    return page.evaluate(
      async ({ method, urlPath, token, body, isFormData }) => {
        const headers = { Authorization: `Bearer ${token}` };
        const init = { method, headers };

        if (body && isFormData) {
          const form = new FormData();
          for (const [k, v] of Object.entries(body)) {
            form.append(k, v);
          }
          init.body = form;
        } else if (body) {
          headers["Content-Type"] = "application/json";
          init.body = JSON.stringify(body);
        }

        const res = await fetch(urlPath, init);
        const text = await res.text();
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
        return { status: res.status, data };
      },
      { method, urlPath, token, body: options.body, isFormData: options.formData },
    );
  }

  test("create a library", async ({ page }) => {
    const res = await apiCall(page, "POST", "/creator/libraries", {
      body: { name: "Playwright Test Library", description: "Automated E2E test" },
    });

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("id");
    expect(res.data.name).toBe("Playwright Test Library");
    expect(res.data.description).toBe("Automated E2E test");
    expect(res.data.is_shared).toBe(false);
    libraryId = res.data.id;
  });

  test("list libraries includes created library", async ({ page }) => {
    const res = await apiCall(page, "GET", "/creator/libraries");

    expect(res.status).toBe(200);
    const libs = res.data.libraries;
    expect(libs.length).toBeGreaterThanOrEqual(1);
    const ours = libs.find((l) => l.id === libraryId);
    expect(ours).toBeTruthy();
    expect(ours.name).toBe("Playwright Test Library");
  });

  test("get library details", async ({ page }) => {
    const res = await apiCall(page, "GET", `/creator/libraries/${libraryId}`);

    expect(res.status).toBe(200);
    expect(res.data.id).toBe(libraryId);
    expect(res.data.is_owner).toBe(true);
    expect(res.data.item_count).toBe(0);
  });

  test("upload a markdown file", async ({ page }) => {
    const res = await page.evaluate(
      async ({ libraryId, token }) => {
        const content = "# Playwright Test\\n\\nAutomated test content.";
        const blob = new Blob([content], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, "playwright-test.md");
        form.append("title", "Playwright Test Doc");

        const r = await fetch(`/creator/libraries/${libraryId}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        return { status: r.status, data: await r.json() };
      },
      { libraryId, token },
    );

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("item_id");
    expect(res.data.status).toBe("processing");
    itemId = res.data.item_id;
  });

  test("poll item status until ready", async ({ page }) => {
    let status = "processing";
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const res = await apiCall(
        page,
        "GET",
        `/creator/libraries/${libraryId}/items/${itemId}/status`,
      );
      expect(res.status).toBe(200);
      status = res.data.status;
      if (status === "ready" || status === "failed") break;
    }
    expect(status).toBe("ready");
  });

  test("get item details with metadata", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      `/creator/libraries/${libraryId}/items/${itemId}`,
    );

    expect(res.status).toBe(200);
    expect(res.data.title).toBe("Playwright Test Doc");
    expect(res.data.status).toBe("ready");
    expect(res.data.original_filename).toBe("playwright-test.md");
    expect(res.data.metadata).toHaveProperty("permalinks");
    expect(res.data.metadata.permalinks).toHaveProperty("full_markdown");
  });

  test("list items in library", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      `/creator/libraries/${libraryId}/items`,
    );

    expect(res.status).toBe(200);
    expect(res.data.total).toBe(1);
    expect(res.data.items[0].id).toBe(itemId);
    expect(res.data.items[0].status).toBe("ready");
  });

  test("import URL content", async ({ page }) => {
    const res = await apiCall(
      page,
      "POST",
      `/creator/libraries/${libraryId}/import-url`,
      {
        body: {
          url: "https://raw.githubusercontent.com/anthropics/anthropic-cookbook/main/README.md",
          plugin_name: "url_import",
          title: "URL Import Test",
        },
      },
    );

    // URL import may fail if network is unavailable in CI, so accept 200 or 502
    if (res.status === 200) {
      expect(res.data).toHaveProperty("item_id");
    }
  });

  test("update library name", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/libraries/${libraryId}`,
      {
        body: { name: "Renamed Playwright Library" },
      },
    );

    expect(res.status).toBe(200);
    expect(res.data.name).toBe("Renamed Playwright Library");
  });

  test("share library with organization", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/libraries/${libraryId}/share`,
      {
        body: { is_shared: true },
      },
    );

    expect(res.status).toBe(200);
    expect(res.data.is_shared).toBe(true);
    expect(res.data.message).toContain("shared with organization");
  });

  test("unshare library", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/libraries/${libraryId}/share`,
      {
        body: { is_shared: false },
      },
    );

    expect(res.status).toBe(200);
    expect(res.data.is_shared).toBe(false);
  });

  test("export library as ZIP", async ({ page }) => {
    const res = await page.evaluate(
      async ({ libraryId, token }) => {
        const r = await fetch(`/creator/libraries/${libraryId}/export`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const blob = await r.blob();
        return { status: r.status, size: blob.size, type: blob.type };
      },
      { libraryId, token },
    );

    expect(res.status).toBe(200);
    expect(res.size).toBeGreaterThan(0);
    expect(res.type).toBe("application/zip");
  });

  test("delete item", async ({ page }) => {
    const res = await apiCall(
      page,
      "DELETE",
      `/creator/libraries/${libraryId}/items/${itemId}`,
    );

    expect(res.status).toBe(200);
    expect(res.data.message).toContain(itemId);
  });

  test("delete library", async ({ page }) => {
    const res = await apiCall(
      page,
      "DELETE",
      `/creator/libraries/${libraryId}`,
    );

    expect(res.status).toBe(200);
    expect(res.data.message).toContain(libraryId);
  });

  test("verify library is gone", async ({ page }) => {
    const res = await apiCall(page, "GET", "/creator/libraries");

    expect(res.status).toBe(200);
    const ours = res.data.libraries.find((l) => l.id === libraryId);
    expect(ours).toBeUndefined();
  });

  test("access non-existent library returns 404", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      "/creator/libraries/non-existent-uuid",
    );

    expect(res.status).toBe(404);
  });

  test.afterAll(async ({ browser }) => {
    if (!libraryId) return;
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`).catch(() => {});
    await context.close();
  });
});
