const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * E2E tests for the file-tree / folder endpoints
 * (/creator/libraries/{id}/{tree,folders,items/move}).
 *
 * Mirrors the API-level pattern of library_api.spec.js — no UI, just
 * fetch through the browser context so cookies/auth match a real user.
 */
test.describe.serial("Library tree + folder endpoints", () => {
  let token;
  let libraryId;
  let folderId;
  let subfolderId;
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
      async ({ method, urlPath, token, body }) => {
        const headers = { Authorization: `Bearer ${token}` };
        const init = { method, headers };
        if (body) {
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
      { method, urlPath, token, body: options.body },
    );
  }

  test("create library for folder tests", async ({ page }) => {
    const res = await apiCall(page, "POST", "/creator/libraries", {
      body: { name: "Playwright Tree Test", description: "folder/tree e2e" },
    });
    expect(res.status).toBe(200);
    libraryId = res.data.id;
  });

  test("empty tree", async ({ page }) => {
    const res = await apiCall(page, "GET", `/creator/libraries/${libraryId}/tree`);
    expect(res.status).toBe(200);
    expect(res.data.library_id).toBe(libraryId);
    expect(res.data.folders).toEqual([]);
    expect(res.data.items).toEqual([]);
  });

  test("create a root folder", async ({ page }) => {
    const res = await apiCall(page, "POST", `/creator/libraries/${libraryId}/folders`, {
      body: { name: "Q1 Research", parent_folder_id: null },
    });
    expect(res.status).toBe(201);
    expect(res.data.name).toBe("Q1 Research");
    expect(res.data.parent_folder_id).toBeNull();
    folderId = res.data.id;
  });

  test("create a subfolder", async ({ page }) => {
    const res = await apiCall(page, "POST", `/creator/libraries/${libraryId}/folders`, {
      body: { name: "Drafts", parent_folder_id: folderId },
    });
    expect(res.status).toBe(201);
    expect(res.data.parent_folder_id).toBe(folderId);
    subfolderId = res.data.id;
  });

  test("duplicate sibling name rejected", async ({ page }) => {
    const res = await apiCall(page, "POST", `/creator/libraries/${libraryId}/folders`, {
      body: { name: "Q1 Research", parent_folder_id: null },
    });
    expect(res.status).toBe(409);
  });

  test("invalid folder name rejected", async ({ page }) => {
    const res = await apiCall(page, "POST", `/creator/libraries/${libraryId}/folders`, {
      body: { name: "with/slash", parent_folder_id: null },
    });
    expect([400, 422]).toContain(res.status);
  });

  test("rename folder", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/libraries/${libraryId}/folders/${folderId}`,
      { body: { name: "Q1 Research (updated)" } },
    );
    expect(res.status).toBe(200);
    expect(res.data.name).toBe("Q1 Research (updated)");
  });

  test("cannot move folder into descendant", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/libraries/${libraryId}/folders/${folderId}/move`,
      { body: { parent_folder_id: subfolderId } },
    );
    expect(res.status).toBe(400);
  });

  test("upload file into a folder", async ({ page }) => {
    const res = await page.evaluate(
      async ({ libraryId, folderId, token }) => {
        const blob = new Blob(["# Hello\n\nfolder upload test"], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, "in-folder.md");
        form.append("title", "In Folder");
        form.append("folder_id", folderId);
        const r = await fetch(`/creator/libraries/${libraryId}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        return { status: r.status, data: await r.json() };
      },
      { libraryId, folderId, token },
    );
    expect(res.status).toBe(200);
    itemId = res.data.item_id;
  });

  test("uploaded item appears under the folder in the tree", async ({ page }) => {
    // Wait for processing to settle, but the folder_id should be set immediately.
    await page.waitForTimeout(800);
    const res = await apiCall(page, "GET", `/creator/libraries/${libraryId}/tree`);
    expect(res.status).toBe(200);
    const item = res.data.items.find((i) => i.id === itemId);
    expect(item).toBeTruthy();
    expect(item.folder_id).toBe(folderId);
  });

  test("bulk move item back to root", async ({ page }) => {
    const res = await apiCall(page, "POST", `/creator/libraries/${libraryId}/items/move`, {
      body: { item_ids: [itemId], folder_id: null },
    });
    expect(res.status).toBe(200);
    expect(res.data.moved).toBe(1);
  });

  test("cross-library folder rejected on upload", async ({ page }) => {
    // Make a second library and try to upload to lib1 with lib2's folder_id.
    const lib2 = await apiCall(page, "POST", "/creator/libraries", {
      body: { name: "Tree Test Lib 2", description: "" },
    });
    expect(lib2.status).toBe(200);
    const foreignFolder = await apiCall(
      page,
      "POST",
      `/creator/libraries/${lib2.data.id}/folders`,
      { body: { name: "Foreign", parent_folder_id: null } },
    );
    expect(foreignFolder.status).toBe(201);

    const res = await page.evaluate(
      async ({ libraryId, foreignFolderId, token }) => {
        const blob = new Blob(["x"], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, "x.md");
        form.append("title", "X");
        form.append("folder_id", foreignFolderId);
        const r = await fetch(`/creator/libraries/${libraryId}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        return { status: r.status };
      },
      { libraryId, foreignFolderId: foreignFolder.data.id, token },
    );
    expect(res.status).toBe(400);

    // Cleanup lib2
    await apiCall(page, "DELETE", `/creator/libraries/${lib2.data.id}`);
  });

  test("delete subfolder reparents items + cleanup", async ({ page }) => {
    // Move our item into the subfolder, then delete subfolder, then verify
    // the item moved to the parent folder.
    await apiCall(page, "POST", `/creator/libraries/${libraryId}/items/move`, {
      body: { item_ids: [itemId], folder_id: subfolderId },
    });

    const del = await apiCall(
      page,
      "DELETE",
      `/creator/libraries/${libraryId}/folders/${subfolderId}`,
    );
    expect(del.status).toBe(200);

    const itemRes = await apiCall(
      page,
      "GET",
      `/creator/libraries/${libraryId}/items/${itemId}`,
    );
    expect(itemRes.status).toBe(200);
    expect(itemRes.data.folder_id).toBe(folderId);

    // Clean up library
    await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`);
  });
});
