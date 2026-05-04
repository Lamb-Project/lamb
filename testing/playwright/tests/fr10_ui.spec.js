const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * Phase 4.3 - FR-10 UI surface spec.
 *
 * FR-10 (issue #337): a Library item referenced by any active Knowledge
 * Store cannot be deleted from its Library. The backend enforces this and
 * returns a structured 409 with `detail.knowledge_stores: [{id, name, ...}]`.
 *
 * This spec asserts that the UI surfaces the FR-10 conflict to the user
 * when they attempt the deletion through the Library detail page, and that
 * the item is in fact still present after the failed attempt. After
 * unlinking the KS content the same delete must succeed.
 *
 * The current LibraryDetail.svelte just renders `err.message` from axios in
 * a generic error banner -- it does NOT surface the structured 409 payload
 * (so the KS name + id are not shown). This spec is therefore lenient: it
 * insists the item is still listed (no silent loss) and that *some* error
 * indicator is visible after the attempt. If/when Phase 5 adds an explicit
 * conflict modal that names the KS, the assertions can be tightened.
 */

const FIXTURE_PATH = path.join(__dirname, "..", "fixtures", "sample.md");

test.describe.serial("FR-10 - UI surface", () => {
  let token;
  let libraryId;
  let itemId;
  let knowledgeStoreId;
  let knowledgeStoreName;
  let pipelineSkipReason = null;

  // Defaults; overridden by /options.
  let chunkingStrategy = "simple";
  let embeddingVendor = "openai";
  let embeddingModel = "text-embedding-3-small";
  let vectorDbBackend = "chromadb";

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

  async function pollUntil(
    page,
    fn,
    predicate,
    { timeoutMs = 60000, baseDelay = 1000 } = {},
  ) {
    let delay = baseDelay;
    const deadline = Date.now() + timeoutMs;
    let last = null;
    while (Date.now() < deadline) {
      last = await fn();
      if (predicate(last)) return last;
      await page.waitForTimeout(delay);
      delay = Math.min(delay * 2, 8000);
    }
    return last;
  }

  function pickAllowed(plugins, fallback) {
    if (Array.isArray(plugins) && plugins.length > 0) {
      const first = plugins[0];
      return (first && first.name) || fallback;
    }
    return fallback;
  }

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    token = await page.evaluate(() => localStorage.getItem("userToken"));
    expect(token).toBeTruthy();

    // 1. Create a fresh library.
    const ts = Date.now();
    const libRes = await apiCall(page, "POST", "/creator/libraries", {
      body: {
        name: `vt-A43-fr10-lib-${ts}`,
        description: "Phase 4.3 FR-10 UI spec",
      },
    });
    expect(libRes.status).toBe(200);
    libraryId = libRes.data.id;

    // 2. Upload sample.md.
    expect(fs.existsSync(FIXTURE_PATH)).toBe(true);
    const fixtureContent = fs.readFileSync(FIXTURE_PATH, "utf8");
    const upRes = await page.evaluate(
      async ({ libraryId, token, fixtureContent }) => {
        const blob = new Blob([fixtureContent], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, "sample.md");
        form.append("title", "FR-10 UI Doc");
        const r = await fetch(`/creator/libraries/${libraryId}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        const text = await r.text();
        let data;
        try { data = JSON.parse(text); } catch { data = text; }
        return { status: r.status, data };
      },
      { libraryId, token, fixtureContent },
    );
    expect(upRes.status).toBe(200);
    itemId = upRes.data.item_id;

    // 3. Wait for the item to be ready.
    const readyRes = await pollUntil(
      page,
      () => apiCall(page, "GET", `/creator/libraries/${libraryId}/items/${itemId}/status`),
      (r) => r && r.status === 200 && (r.data.status === "ready" || r.data.status === "failed"),
      { timeoutMs: 60000 },
    );
    expect(readyRes && readyRes.data.status).toBe("ready");

    // 4. Pick KS options + create a fresh KS.
    const opts = await apiCall(page, "GET", "/creator/knowledge-stores/options");
    if (opts.status === 200 && opts.data) {
      chunkingStrategy = pickAllowed(opts.data.chunking_strategies, chunkingStrategy);
      vectorDbBackend = pickAllowed(opts.data.vector_db_backends, vectorDbBackend);
      embeddingVendor = pickAllowed(opts.data.embedding_vendors, embeddingVendor);
      const modelsForVendor = (opts.data.embedding_models || {})[embeddingVendor];
      if (Array.isArray(modelsForVendor) && modelsForVendor.length > 0) {
        embeddingModel = modelsForVendor[0];
      }
    }

    knowledgeStoreName = `vt-A43-fr10-ks-${ts}`;
    const ksRes = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: knowledgeStoreName,
        description: "Phase 4.3 FR-10 UI spec",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });
    if (ksRes.status === 503) {
      pipelineSkipReason = "KB Server (port 9092) unreachable -- skipping FR-10 UI spec.";
    } else {
      expect(ksRes.status).toBe(200);
      knowledgeStoreId = ksRes.data.id;

      // 5. Link the library item to the KS.
      const linkRes = await apiCall(
        page,
        "POST",
        `/creator/knowledge-stores/${knowledgeStoreId}/content`,
        { body: { library_id: libraryId, item_ids: [itemId] } },
      );
      if (linkRes.status === 503) {
        pipelineSkipReason = "KB Server unreachable on link -- skipping FR-10 UI spec.";
      } else {
        expect(linkRes.status).toBe(200);
        // We do NOT need ingestion to be 'ready' for FR-10 to fire -- the
        // backend treats any status != 'failed' as active. Belt and braces:
        // give the worker a moment so the link is at least 'processing'.
        await page.waitForTimeout(500);
      }
    }

    await context.close();
  });

  test.afterAll(async ({ browser }) => {
    if (!libraryId && !knowledgeStoreId) return;
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    if (knowledgeStoreId) {
      // Best-effort unlink so library delete is not blocked.
      await apiCall(
        page,
        "DELETE",
        `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`,
      ).catch(() => {});
      await apiCall(
        page,
        "DELETE",
        `/creator/knowledge-stores/${knowledgeStoreId}`,
      ).catch(() => {});
    }
    if (libraryId) {
      await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`).catch(() => {});
    }
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
  });

  test("@cross-browser deleting a referenced library item is blocked in the UI and the item survives", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    // Capture the network response so we can confirm the UI even attempted
    // the delete (axios will throw AND surface err.message in the banner).
    const deleteResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes(`/creator/libraries/${libraryId}/items/${itemId}`) &&
        resp.request().method() === "DELETE",
      { timeout: 15000 },
    );

    await page.goto(`/libraries?section=libraries&view=detail&id=${libraryId}`);
    await page.waitForLoadState("domcontentloaded");

    // The item row should show the title we uploaded (sample.md / "FR-10 UI Doc").
    const rowText = page.getByText("FR-10 UI Doc").first();
    await expect(rowText).toBeVisible({ timeout: 10000 });

    // Click the per-row Delete button.
    const deleteButtons = page.getByRole("button", { name: /Delete|Eliminar|Borrar/i });
    expect(await deleteButtons.count()).toBeGreaterThan(0);
    // The first per-row Delete button (the page-level "Delete library" -- if
    // any -- usually has different label; the per-item ones say plain "Delete").
    await deleteButtons.first().click();

    // Confirmation modal -> click confirm.
    const confirmButton = page
      .getByRole("button", { name: /^Delete$|Confirm|Confirmar/i })
      .last();
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
    await confirmButton.click();

    // The DELETE request must come back with 409.
    const deleteResp = await deleteResponsePromise;
    expect(deleteResp.status()).toBe(409);

    // Backend payload sanity-check: it must name our KS.
    const detailJson = await deleteResp.json().catch(() => ({}));
    const detail = (detailJson && detailJson.detail) || detailJson;
    expect(detail).toBeTruthy();
    expect(Array.isArray(detail.knowledge_stores)).toBe(true);
    const matchingKs = detail.knowledge_stores.find(
      (ks) => ks.id === knowledgeStoreId,
    );
    expect(matchingKs, "409 detail.knowledge_stores must name our KS by id").toBeTruthy();
    expect(matchingKs.name).toBe(knowledgeStoreName);

    // The UI must surface SOME error indication. Today the LibraryDetail
    // page shows a generic axios error message; if Phase 5 introduces a
    // dedicated conflict modal we will tighten this assertion.
    // We accept any of: a visible error banner OR an explicit modal/toast.
    const errorBanner = page.locator(
      '.text-red-500, [data-testid="library-error"], [role="alert"]',
    );
    await expect(errorBanner.first()).toBeVisible({ timeout: 5000 });

    // Critical: the item must still be present in the library listing.
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByText("FR-10 UI Doc").first()).toBeVisible({
      timeout: 10000,
    });

    // API-level sanity: the item is still listed.
    const listRes = await apiCall(
      page,
      "GET",
      `/creator/libraries/${libraryId}/items`,
    );
    expect(listRes.status).toBe(200);
    const items = listRes.data?.items || listRes.data || [];
    const found = (Array.isArray(items) ? items : []).find(
      (i) => i.id === itemId,
    );
    expect(found, "library item must still exist after blocked delete").toBeTruthy();
  });

  test("after unlinking the KS content, the same library item can be deleted", async ({
    page,
  }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    // Unlink via the API (UI for this is the KS detail page; the API path
    // is what the UI ultimately calls and is what FR-10 keys off of).
    const unlinkRes = await apiCall(
      page,
      "DELETE",
      `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`,
    );
    expect(unlinkRes.status).toBe(200);

    // Now retry the delete. Use the API to keep the spec deterministic --
    // the previous test already covered the UI-surfacing path.
    const delRes = await apiCall(
      page,
      "DELETE",
      `/creator/libraries/${libraryId}/items/${itemId}`,
    );
    expect(delRes.status).toBe(200);

    // The item is gone.
    const listRes = await apiCall(
      page,
      "GET",
      `/creator/libraries/${libraryId}/items`,
    );
    const items = listRes.data?.items || listRes.data || [];
    const found = (Array.isArray(items) ? items : []).find(
      (i) => i.id === itemId,
    );
    expect(found).toBeFalsy();
  });
});
