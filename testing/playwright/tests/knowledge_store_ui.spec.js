const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * Phase 2B — UI tests for the unified Knowledge page (/libraries) and the
 * Create-Knowledge wizard.
 *
 * API-level CRUD lives in knowledge_store_api.spec.js; this spec exercises
 * the actual DOM, sub-tab routing, and the wizard step machine. Ingestion,
 * polling, citations, and FR-10 are covered by the Phase 3 e2e workflow
 * spec (knowledge_store_e2e_workflow.spec.js) and require a working
 * embedding API key — none of that is asserted here.
 */
test.describe.serial("Knowledge Store UI", () => {
  let token;
  /** @type {string|undefined} */
  let seededKsId;
  const seededKsName = `pw_ks_ui_${Date.now()}`;

  // Defaults; will be narrowed by /options if the org has an allow-list.
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

    // Resolve the org allow-list (if any) so the seeded KS uses values the
    // creator endpoint will accept.
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

    // Seed one Knowledge Store so the list renders rows for the share /
    // delete UI assertions. Best-effort: if the backend rejects the
    // request the spec degrades gracefully (assertions are guarded).
    const created = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: seededKsName,
        description: "Seeded by knowledge_store_ui.spec.js",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });
    if (created.status === 200 && created.data?.id) {
      seededKsId = created.data.id;
    }

    await context.close();
  });

  test.afterAll(async ({ browser }) => {
    if (!seededKsId) return;
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await apiCall(
      page,
      "DELETE",
      `/creator/knowledge-stores/${seededKsId}`,
    ).catch(() => {});
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    // Each test starts at root and lets the test navigate explicitly.
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
  });

  test("default /libraries route shows sub-tabs and tab-contextual create buttons", async ({ page }) => {
    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");

    // Header
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 10_000 });

    // Sub-tabs
    const librariesTab = page.getByRole("button", { name: /^Libraries$/ });
    const ksTab = page.getByRole("button", { name: /^Knowledge Stores$/ });
    await expect(librariesTab).toBeVisible();
    await expect(ksTab).toBeVisible();

    // The redundant top-right "Create Knowledge" button has been removed.
    // The contextual + New Library button on the Libraries tab is the
    // primary create affordance now.
    const newLibBtn = page.getByRole("button", { name: /\+\s*New Library/i });
    await expect(newLibBtn).toBeVisible();
  });

  test("clicking the Knowledge Stores sub-tab updates the URL and renders the list", async ({ page }) => {
    await page.goto("/libraries");
    // Wait for the app to fully hydrate — Logout button appears after session + layout init.
    await expect(page.getByRole("button", { name: /^Logout$/i })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^Knowledge Stores$/ }).click();

    // URL should now carry section=knowledge-stores
    await expect(page).toHaveURL(/[?&]section=knowledge-stores/);

    // The KS list toolbar should show the "+ New Knowledge Store" button.
    await expect(page.getByRole("button", { name: /\+\s*New Knowledge Store/i })).toBeVisible({ timeout: 10_000 });

    // Switch back to Libraries.
    await page.getByRole("button", { name: /^Libraries$/ }).click();
    await expect(page).toHaveURL(/[?&]section=libraries(\b|&|$)/);
  });

  test("direct URL /libraries?section=knowledge-stores lands on the KS sub-tab", async ({ page }) => {
    await page.goto("/libraries?section=knowledge-stores");
    await page.waitForLoadState("domcontentloaded");

    // The KS list toolbar button confirms KnowledgeStoresList rendered.
    await expect(page.getByRole("button", { name: /\+\s*New Knowledge Store/i })).toBeVisible({ timeout: 10_000 });

    // The Knowledge Stores sub-tab should be the active one. The active
    // button has the [#2271b3] color class — easiest stable check is that
    // the KS list rendered (above) and the URL is preserved.
    await expect(page).toHaveURL(/[?&]section=knowledge-stores/);
  });

  test("direct URL /knowledge-stores redirects to /libraries?section=knowledge-stores", async ({ page }) => {
    await page.goto("/knowledge-stores");
    // Wait for the redirect (onMount uses goto with replaceState).
    await page.waitForURL(/[?&]section=knowledge-stores/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/libraries\?(?:.*&)?section=knowledge-stores/);
  });

  test("seeded Knowledge Store appears in the list", async ({ page }) => {
    test.skip(!seededKsId, "Seeding the KS failed — list-render assertion not applicable.");

    await page.goto("/libraries?section=knowledge-stores");
    await page.waitForLoadState("domcontentloaded");

    // Wait for the table row containing the seeded KS name.
    await expect(page.getByText(seededKsName)).toBeVisible({ timeout: 10_000 });

    // Table column headers should be present.
    await expect(page.getByRole("columnheader", { name: /^Name$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Embedding$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Chunking$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^#$/ })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Sharing$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Created$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Actions$/i })).toBeVisible();
  });

  test("+ New Knowledge Store button opens the create modal", async ({ page }) => {
    await page.goto("/libraries?section=knowledge-stores");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("button", { name: /\+\s*New Knowledge Store/i })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: /\+\s*New Knowledge Store/i }).first().click();

    // The CreateKnowledgeStoreModal dialog should open.
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Close cleanly via Esc.
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });
  });
});
