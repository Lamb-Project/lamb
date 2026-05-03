const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * E2E API tests for the Knowledge Store (new KB Server) integration.
 *
 * Covers the LAMB-side surface at /creator/knowledge-stores/* — CRUD,
 * share toggle, allow-list validation, and 404 hiding. The full
 * library -> KS -> query workflow lives in
 * knowledge_store_e2e_workflow.spec.js (Phase 3 of issue #337) which
 * additionally exercises ingestion, polling, citations, and FR-10.
 *
 * The legacy /creator/knowledgebases (stable KB Server) tests in
 * kb_detail_modals.spec.js / kb_delete_modal.spec.js are not touched.
 */
test.describe.serial("Knowledge Store API integration", () => {
  let token;
  let knowledgeStoreId;
  // Defaults; will be overridden by /options if the org allow-list narrows them.
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

  function pickAllowed(plugins, fallback) {
    if (Array.isArray(plugins) && plugins.length > 0) {
      const first = plugins[0];
      return (first && first.name) || fallback;
    }
    return fallback;
  }

  test("options endpoint returns the org's allow-list", async ({ page }) => {
    const res = await apiCall(page, "GET", "/creator/knowledge-stores/options");

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("vector_db_backends");
    expect(res.data).toHaveProperty("chunking_strategies");
    expect(res.data).toHaveProperty("embedding_vendors");
    expect(res.data).toHaveProperty("embedding_models");

    // Use the first allowed option for each (or fall back to the defaults).
    chunkingStrategy = pickAllowed(res.data.chunking_strategies, chunkingStrategy);
    vectorDbBackend = pickAllowed(res.data.vector_db_backends, vectorDbBackend);
    embeddingVendor = pickAllowed(res.data.embedding_vendors, embeddingVendor);

    const modelsForVendor = (res.data.embedding_models || {})[embeddingVendor];
    if (Array.isArray(modelsForVendor) && modelsForVendor.length > 0) {
      embeddingModel = modelsForVendor[0];
    }
  });

  test("create a knowledge store", async ({ page }) => {
    const res = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: "Playwright KS",
        description: "Automated KS API test",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("id");
    expect(res.data.name).toBe("Playwright KS");
    expect(res.data.description).toBe("Automated KS API test");
    expect(res.data.is_shared).toBe(false);
    expect(res.data.status).toBe("active");
    expect(res.data.chunking_strategy).toBe(chunkingStrategy);
    expect(res.data.embedding_vendor).toBe(embeddingVendor);
    expect(res.data.embedding_model).toBe(embeddingModel);
    expect(res.data.vector_db_backend).toBe(vectorDbBackend);
    knowledgeStoreId = res.data.id;
  });

  test("create with invalid chunking strategy is rejected", async ({ page }) => {
    const res = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: "Bad KS",
        description: "Should fail allow-list",
        chunking_strategy: "definitely_not_a_real_strategy",
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });

    // Either the org has an allow-list (400 from LAMB) or the KB Server
    // rejects unknown strategy (502 from LAMB). Both are acceptable
    // failure modes; what matters is the create did not succeed.
    expect([400, 502]).toContain(res.status);
  });

  test("duplicate name is rejected with 409", async ({ page }) => {
    const res = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: "Playwright KS",
        description: "Duplicate name",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });

    expect(res.status).toBe(409);
  });

  test("list knowledge stores includes the created KS", async ({ page }) => {
    const res = await apiCall(page, "GET", "/creator/knowledge-stores");

    expect(res.status).toBe(200);
    const items = res.data.knowledge_stores;
    expect(Array.isArray(items)).toBe(true);
    expect(items.length).toBeGreaterThanOrEqual(1);
    const ours = items.find((k) => k.id === knowledgeStoreId);
    expect(ours).toBeTruthy();
    expect(ours.name).toBe("Playwright KS");
  });

  test("get knowledge store details", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      `/creator/knowledge-stores/${knowledgeStoreId}`,
    );

    expect(res.status).toBe(200);
    expect(res.data.id).toBe(knowledgeStoreId);
    expect(res.data.is_owner).toBe(true);
    expect(res.data.chunking_strategy).toBe(chunkingStrategy);
    expect(res.data.embedding_vendor).toBe(embeddingVendor);
    expect(res.data.vector_db_backend).toBe(vectorDbBackend);
    expect(Array.isArray(res.data.content)).toBe(true);
    expect(res.data.content.length).toBe(0);
  });

  test("update name and description", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/knowledge-stores/${knowledgeStoreId}`,
      {
        body: {
          name: "Renamed Playwright KS",
          description: "Updated description",
        },
      },
    );

    expect(res.status).toBe(200);
    expect(res.data.name).toBe("Renamed Playwright KS");
    expect(res.data.description).toBe("Updated description");
  });

  test("update with no fields returns 400", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/knowledge-stores/${knowledgeStoreId}`,
      { body: {} },
    );

    expect(res.status).toBe(400);
  });

  test("share with organization", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/knowledge-stores/${knowledgeStoreId}/share`,
      { body: { is_shared: true } },
    );

    expect(res.status).toBe(200);
    expect(res.data.is_shared).toBe(true);
    expect(res.data.message).toContain("shared with organization");
  });

  test("unshare from organization", async ({ page }) => {
    const res = await apiCall(
      page,
      "PUT",
      `/creator/knowledge-stores/${knowledgeStoreId}/share`,
      { body: { is_shared: false } },
    );

    expect(res.status).toBe(200);
    expect(res.data.is_shared).toBe(false);
  });

  test("list-content for an empty KS returns empty list", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      `/creator/knowledge-stores/${knowledgeStoreId}/content`,
    );

    expect(res.status).toBe(200);
    expect(Array.isArray(res.data.content)).toBe(true);
    expect(res.data.content.length).toBe(0);
  });

  test("get non-existent content link returns 404", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      `/creator/knowledge-stores/${knowledgeStoreId}/content/non-existent-item`,
    );

    expect(res.status).toBe(404);
  });

  test("add-content with cross-org library is rejected", async ({ page }) => {
    // No library exists in this test, so the library-not-found 404 path is
    // exercised. The forbidden-cross-org path is covered in the e2e workflow
    // spec where an actual library is created.
    const res = await apiCall(
      page,
      "POST",
      `/creator/knowledge-stores/${knowledgeStoreId}/content`,
      {
        body: {
          library_id: "non-existent-library-uuid",
          item_ids: ["non-existent-item"],
        },
      },
    );

    expect([400, 404]).toContain(res.status);
  });

  test("delete the knowledge store", async ({ page }) => {
    const res = await apiCall(
      page,
      "DELETE",
      `/creator/knowledge-stores/${knowledgeStoreId}`,
    );

    expect(res.status).toBe(200);
    expect(res.data.message).toContain(knowledgeStoreId);
  });

  test("verify the KS is gone from the list", async ({ page }) => {
    const res = await apiCall(page, "GET", "/creator/knowledge-stores");

    expect(res.status).toBe(200);
    const ours = res.data.knowledge_stores.find((k) => k.id === knowledgeStoreId);
    expect(ours).toBeUndefined();
  });

  test("access non-existent knowledge store returns 404", async ({ page }) => {
    const res = await apiCall(
      page,
      "GET",
      "/creator/knowledge-stores/non-existent-uuid",
    );

    expect(res.status).toBe(404);
  });

  test.afterAll(async ({ browser }) => {
    if (!knowledgeStoreId) return;
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await apiCall(
      page,
      "DELETE",
      `/creator/knowledge-stores/${knowledgeStoreId}`,
    ).catch(() => {});
    await context.close();
  });
});
