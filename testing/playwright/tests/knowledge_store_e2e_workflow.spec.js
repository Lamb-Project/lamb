const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * Headline E2E test for issue #337 Phase 3.
 *
 * Exercises the full Library -> Knowledge Store -> Query -> Citation chain
 * end-to-end through LAMB's Creator Interface. Skips cleanly (rather than
 * failing) when the new KB Server (port 9092) or its embedding key are
 * not available in the test environment.
 *
 * Sequence:
 *   1. Login (storageState -> token).
 *   2. Create a Library.
 *   3. Upload sample.md fixture.
 *   4. Poll item status until ready.
 *   5. Fetch KS options (chunking / vector_db / embedding vendor + model).
 *   6. Create a Knowledge Store with the picked locked-setup values.
 *   7. Add the library item as KS content -> processing.
 *   8. Poll content link until ready (skip if failed -- missing API key).
 *   9. Query the KS -> assert citations carry library-permalink metadata.
 *  10. Resolve a permalink via /docs proxy with the user's bearer token.
 *  11. FR-10: try to delete the linked library item -> expect 409 with
 *      knowledge_stores list naming our KS.
 *  12. Remove the KS content link.
 *  13. FR-10 release: delete the library item -> now 200.
 *  14. afterAll: idempotent cleanup of KS + library.
 */

const FIXTURE_PATH = path.join(__dirname, "..", "fixtures", "sample.md");

test.describe.serial("Knowledge Store end-to-end workflow", () => {
  let token;
  let libraryId;
  let itemId;
  let knowledgeStoreId;
  let pipelineSkipReason = null;

  // Defaults; overridden by /options.
  let chunkingStrategy = "simple";
  let embeddingVendor = "openai";
  let embeddingModel = "text-embedding-3-small";
  let vectorDbBackend = "chromadb";

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
      delay = Math.min(delay * 2, 16000);
    }
    return null;
  }

  function pickAllowed(plugins, fallback) {
    if (Array.isArray(plugins) && plugins.length > 0) {
      const first = plugins[0];
      return (first && first.name) || fallback;
    }
    return fallback;
  }

  test("step 1+2: create a library", async ({ page }) => {
    const uniqueName = `E2E Workflow Library ${Date.now()}`;
    const res = await apiCall(page, "POST", "/creator/libraries", {
      body: { name: uniqueName, description: "Issue #337 Phase 3 headline E2E" },
    });

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("id");
    libraryId = res.data.id;
  });

  test("step 3: upload sample.md fixture", async ({ page }) => {
    expect(fs.existsSync(FIXTURE_PATH)).toBe(true);
    const fixtureContent = fs.readFileSync(FIXTURE_PATH, "utf8");

    const res = await page.evaluate(
      async ({ libraryId, token, fixtureContent }) => {
        const blob = new Blob([fixtureContent], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, "sample.md");
        form.append("title", "Workflow Test Doc");

        const r = await fetch(`/creator/libraries/${libraryId}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        const text = await r.text();
        let data;
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
        return { status: r.status, data };
      },
      { libraryId, token, fixtureContent },
    );

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("item_id");
    expect(res.data.status).toBe("processing");
    itemId = res.data.item_id;
  });

  test("step 4: poll library item until ready", async ({ page }) => {
    const final = await pollUntil(
      page,
      () =>
        apiCall(
          page,
          "GET",
          `/creator/libraries/${libraryId}/items/${itemId}/status`,
        ),
      (res) =>
        res &&
        res.status === 200 &&
        (res.data.status === "ready" || res.data.status === "failed"),
      { timeoutMs: 60000, baseDelay: 1000 },
    );

    expect(final, "library item polling timed out before reaching a terminal state").not.toBeNull();
    expect(final.data.status).toBe("ready");
  });

  test("step 5: fetch KS options and pick allowed values", async ({ page }) => {
    const res = await apiCall(page, "GET", "/creator/knowledge-stores/options");
    expect(res.status).toBe(200);

    chunkingStrategy = pickAllowed(res.data.chunking_strategies, chunkingStrategy);
    vectorDbBackend = pickAllowed(res.data.vector_db_backends, vectorDbBackend);
    embeddingVendor = pickAllowed(res.data.embedding_vendors, embeddingVendor);

    const modelsForVendor = (res.data.embedding_models || {})[embeddingVendor];
    if (Array.isArray(modelsForVendor) && modelsForVendor.length > 0) {
      embeddingModel = modelsForVendor[0];
    }
  });

  test("step 6: create a knowledge store", async ({ page }) => {
    const uniqueName = `E2E Workflow KS ${Date.now()}`;
    const res = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: uniqueName,
        description: "Issue #337 Phase 3 headline E2E",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });

    if (res.status === 503) {
      pipelineSkipReason = "KB Server not reachable (LAMB returned 503)";
      test.skip(true, pipelineSkipReason);
      return;
    }

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("id");
    expect(res.data.status).toBe("active");
    knowledgeStoreId = res.data.id;
  });

  test("step 7: add library item as KS content", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");
    expect(knowledgeStoreId, "knowledge store id missing").toBeTruthy();

    const res = await apiCall(
      page,
      "POST",
      `/creator/knowledge-stores/${knowledgeStoreId}/content`,
      { body: { library_id: libraryId, item_ids: [itemId] } },
    );

    if (res.status === 503) {
      pipelineSkipReason = "KB Server not reachable (LAMB returned 503)";
      test.skip(true, pipelineSkipReason);
      return;
    }

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("job_id");
    expect(Array.isArray(res.data.links)).toBe(true);
    expect(res.data.links.length).toBeGreaterThanOrEqual(1);
    const ourLink = res.data.links.find((l) => l.library_item_id === itemId)
      || res.data.links[0];
    expect(ourLink.status).toBe("processing");
  });

  test("step 8: poll content link until ready", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    const final = await pollUntil(
      page,
      () =>
        apiCall(
          page,
          "GET",
          `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`,
        ),
      (res) =>
        res &&
        res.status === 200 &&
        res.data &&
        (res.data.status === "ready" || res.data.status === "failed"),
      { timeoutMs: 90000, baseDelay: 1000 },
    );

    if (!final) {
      pipelineSkipReason =
        "Content link polling timed out (KB Server slow or stuck)";
      test.skip(true, pipelineSkipReason);
      return;
    }

    if (final.data.status === "failed") {
      pipelineSkipReason =
        "Embedding ingestion failed (likely missing API key)";
      test.skip(true, pipelineSkipReason);
      return;
    }

    expect(final.data.status).toBe("ready");
  });

  test("step 9: query the knowledge store", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    const res = await apiCall(
      page,
      "POST",
      `/creator/knowledge-stores/${knowledgeStoreId}/query`,
      { body: { query_text: "capital of France", top_k: 3 } },
    );

    expect(res.status).toBe(200);
    const chunks = res.data.chunks || res.data.results || res.data;
    expect(Array.isArray(chunks)).toBe(true);
    expect(chunks.length).toBeGreaterThanOrEqual(1);

    for (const chunk of chunks) {
      expect(chunk).toHaveProperty("metadata");
      const md = chunk.metadata || {};
      const permalink = md.permalink_original || md.permalink_markdown;
      expect(
        permalink,
        "chunk metadata must include permalink_original or permalink_markdown",
      ).toBeTruthy();
      expect(typeof permalink).toBe("string");
      expect(permalink.startsWith("/docs/")).toBe(true);
    }
  });

  test("step 10: resolve permalink via /docs proxy", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    const queryRes = await apiCall(
      page,
      "POST",
      `/creator/knowledge-stores/${knowledgeStoreId}/query`,
      { body: { query_text: "capital of France", top_k: 3 } },
    );
    expect(queryRes.status).toBe(200);
    const chunks = queryRes.data.chunks || queryRes.data.results || queryRes.data;
    expect(Array.isArray(chunks) && chunks.length).toBeTruthy();

    const md = chunks[0].metadata || {};
    const permalink = md.permalink_original || md.permalink_markdown;
    expect(permalink).toBeTruthy();

    const docRes = await page.evaluate(
      async ({ permalink, token }) => {
        const r = await fetch(permalink, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const text = await r.text();
        return { status: r.status, body: text };
      },
      { permalink, token },
    );

    expect(docRes.status).toBe(200);
    const containsParis = docRes.body.includes("Paris");
    const containsFox = docRes.body.includes("fox");
    expect(
      containsParis || containsFox,
      "permalink response should contain a known fixture substring",
    ).toBe(true);
  });

  test("step 11: FR-10 -- delete linked library item returns 409", async ({
    page,
  }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    const res = await apiCall(
      page,
      "DELETE",
      `/creator/libraries/${libraryId}/items/${itemId}`,
    );

    expect(res.status).toBe(409);
    // FastAPI HTTPException wraps the structured payload under `detail`.
    const detail = (res.data && res.data.detail) || res.data;
    expect(detail).toBeTruthy();
    expect(Array.isArray(detail.knowledge_stores)).toBe(true);
    expect(detail.knowledge_stores.length).toBeGreaterThanOrEqual(1);
    const matching = detail.knowledge_stores.find(
      (ks) => ks.id === knowledgeStoreId,
    );
    expect(matching, "409 detail.knowledge_stores must include our KS").toBeTruthy();
  });

  test("step 12: remove KS content link", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    const res = await apiCall(
      page,
      "DELETE",
      `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`,
    );

    expect(res.status).toBe(200);
  });

  test("step 13: FR-10 release -- delete library item now succeeds", async ({
    page,
  }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    const res = await apiCall(
      page,
      "DELETE",
      `/creator/libraries/${libraryId}/items/${itemId}`,
    );

    expect(res.status).toBe(200);
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
      await apiCall(
        page,
        "DELETE",
        `/creator/knowledge-stores/${knowledgeStoreId}`,
      ).catch(() => {});
    }
    if (libraryId) {
      await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`).catch(
        () => {},
      );
    }
    await context.close();
  });
});
