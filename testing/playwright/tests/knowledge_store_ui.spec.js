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

  test("default /libraries route shows sub-tabs and Create Knowledge button", async ({ page }) => {
    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");

    // Header
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 10_000 });

    // Sub-tabs
    const librariesTab = page.getByRole("button", { name: /^Libraries$/ });
    const ksTab = page.getByRole("button", { name: /^Knowledge Stores$/ });
    await expect(librariesTab).toBeVisible();
    await expect(ksTab).toBeVisible();

    // "Create Knowledge" button (top-right)
    const createBtn = page.getByRole("button", { name: /\+\s*Create Knowledge/i });
    await expect(createBtn).toBeVisible();
  });

  test("clicking the Knowledge Stores sub-tab updates the URL and renders the list", async ({ page }) => {
    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", { name: /^Knowledge Stores$/ }).click();

    // URL should now carry section=knowledge-stores
    await expect(page).toHaveURL(/[?&]section=knowledge-stores/);

    // The KS list owned/shared sub-tab buttons should appear.
    await expect(page.getByRole("button", { name: /My Knowledge Stores/i })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /^Shared/i })).toBeVisible();

    // Switch back to Libraries.
    await page.getByRole("button", { name: /^Libraries$/ }).click();
    await expect(page).toHaveURL(/[?&]section=libraries(\b|&|$)/);
  });

  test("direct URL /libraries?section=knowledge-stores lands on the KS sub-tab", async ({ page }) => {
    await page.goto("/libraries?section=knowledge-stores");
    await page.waitForLoadState("domcontentloaded");

    // The owned/shared tabs in KnowledgeStoresList should be visible.
    await expect(page.getByRole("button", { name: /My Knowledge Stores/i })).toBeVisible({ timeout: 10_000 });

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

  test("seeded Knowledge Store appears in the My Knowledge Stores list", async ({ page }) => {
    test.skip(!seededKsId, "Seeding the KS failed — list-render assertion not applicable.");

    await page.goto("/libraries?section=knowledge-stores");
    await page.waitForLoadState("domcontentloaded");

    // Wait for the table row containing the seeded KS name.
    await expect(page.getByText(seededKsName)).toBeVisible({ timeout: 10_000 });

    // Table column headers should be present.
    await expect(page.getByRole("columnheader", { name: /^Name$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Embedding$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Chunking$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Content$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Sharing$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Created$/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /^Actions$/i })).toBeVisible();
  });

  test("clicking Create Knowledge opens the wizard at Step 0", async ({ page }) => {
    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", { name: /\+\s*Create Knowledge/i }).click();

    const dialog = page.getByRole("dialog", { name: /Create Knowledge/i });
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Step 0 heading: "Library"
    await expect(dialog.getByRole("heading", { name: /^Library$/i })).toBeVisible();

    // Esc closes the wizard cleanly.
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });
  });

  test("new-library wizard path walks Step 0 -> Step 4 and aborts without persisting", async ({ page }) => {
    // Capture pre-wizard counts so we can confirm nothing was created.
    const beforeLibs = await apiCall(page, "GET", "/creator/libraries");
    const beforeKs = await apiCall(page, "GET", "/creator/knowledge-stores");
    const libCountBefore = (beforeLibs.data?.libraries || []).length;
    const ksCountBefore = (beforeKs.data?.knowledge_stores || []).length;

    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", { name: /\+\s*Create Knowledge/i }).click();

    const dialog = page.getByRole("dialog", { name: /Create Knowledge/i });
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Step 0 — pick "Create new" (default). Click Next.
    await expect(dialog.getByRole("heading", { name: /^Library$/i })).toBeVisible();
    const newRadio = dialog.locator('input[type="radio"][value="new"]').first();
    await newRadio.check();
    await dialog.getByRole("button", { name: /^Next$/ }).click();

    // Step 1 — auto-suggested library name should be pre-populated.
    await expect(dialog.getByRole("heading", { name: /Library details/i })).toBeVisible({ timeout: 5_000 });
    const nameInput = dialog.locator("#wizard-library-name");
    await expect(nameInput).toBeVisible();
    const suggestedName = await nameInput.inputValue();
    expect(suggestedName.length).toBeGreaterThan(0);

    // Replace with a unique name to avoid colliding with previous runs.
    const uniqueName = `pw_wiz_lib_${Date.now()}`;
    await nameInput.fill(uniqueName);
    await dialog.getByRole("button", { name: /^Next$/ }).click();

    // Step 2 — defaults are valid; just click Next.
    await expect(dialog.getByRole("heading", { name: /Library import config/i })).toBeVisible({ timeout: 5_000 });
    await dialog.getByRole("button", { name: /^Next$/ }).click();

    // Step 3 — skippable. Click Skip.
    await expect(dialog.getByRole("heading", { name: /Initial content/i })).toBeVisible({ timeout: 5_000 });
    await dialog.getByRole("button", { name: /^Skip$/ }).click();

    // Step 4 — "Knowledge Store" path picker. Pick "Create new".
    await expect(dialog.getByRole("heading", { name: /^Knowledge Store$/i })).toBeVisible({ timeout: 5_000 });
    const newKsRadio = dialog.locator('input[type="radio"][value="new"]').first();
    await newKsRadio.check();

    // Abort by closing the wizard. All DB writes happen at Step 8, so
    // nothing should have been persisted.
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });

    // Counts must be unchanged.
    const afterLibs = await apiCall(page, "GET", "/creator/libraries");
    const afterKs = await apiCall(page, "GET", "/creator/knowledge-stores");
    expect((afterLibs.data?.libraries || []).length).toBe(libCountBefore);
    expect((afterKs.data?.knowledge_stores || []).length).toBe(ksCountBefore);

    // The unique library name we typed must not have been persisted.
    const matched = (afterLibs.data?.libraries || []).find((l) => l.name === uniqueName);
    expect(matched).toBeUndefined();
  });

  test("existing-Library skip rule jumps from Step 0 directly to Step 4", async ({ page }) => {
    // Need at least one accessible library for this assertion.
    const libs = await apiCall(page, "GET", "/creator/libraries");
    const haveLib =
      libs.status === 200 && Array.isArray(libs.data?.libraries) && libs.data.libraries.length > 0;
    test.skip(!haveLib, "No libraries accessible to this user — skip-rule cannot be tested.");

    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", { name: /\+\s*Create Knowledge/i }).click();

    const dialog = page.getByRole("dialog", { name: /Create Knowledge/i });
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Pick "Use existing" library.
    const existingRadio = dialog.locator('input[type="radio"][value="existing"]').first();
    await existingRadio.check();

    // The library dropdown should appear; first library auto-selected.
    await expect(dialog.locator("#step0-library-select")).toBeVisible({ timeout: 5_000 });

    await dialog.getByRole("button", { name: /^Next$/ }).click();

    // Skip rule: Step 1, 2, 3 are skipped — next visible step is Step 4 ("Knowledge Store").
    await expect(dialog.getByRole("heading", { name: /^Knowledge Store$/i })).toBeVisible({ timeout: 5_000 });
    // The Library-details heading must NOT be visible.
    await expect(dialog.getByRole("heading", { name: /Library details/i })).not.toBeVisible();

    // Close cleanly.
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });
  });

  test("existing-KS skip rule jumps from Step 4 directly to Step 7", async ({ page }) => {
    test.skip(!seededKsId, "Seeded KS missing — existing-KS skip rule cannot be tested.");

    // Need at least one library for the existing-Library path (so we can
    // skip directly to Step 4 without having to fill out Steps 1-3).
    const libs = await apiCall(page, "GET", "/creator/libraries");
    const haveLib =
      libs.status === 200 && Array.isArray(libs.data?.libraries) && libs.data.libraries.length > 0;
    test.skip(!haveLib, "No libraries accessible to this user — cannot reach Step 4 cleanly.");

    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", { name: /\+\s*Create Knowledge/i }).click();

    const dialog = page.getByRole("dialog", { name: /Create Knowledge/i });
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Step 0 — existing library to skip Steps 1-3.
    await dialog.locator('input[type="radio"][value="existing"]').first().check();
    await expect(dialog.locator("#step0-library-select")).toBeVisible({ timeout: 5_000 });
    await dialog.getByRole("button", { name: /^Next$/ }).click();

    // Step 4 — pick "Use existing Knowledge Store".
    await expect(dialog.getByRole("heading", { name: /^Knowledge Store$/i })).toBeVisible({ timeout: 5_000 });
    await dialog.locator('input[type="radio"][value="existing"]').first().check();
    await expect(dialog.locator("#step4-ks-select")).toBeVisible({ timeout: 5_000 });

    await dialog.getByRole("button", { name: /^Next$/ }).click();

    // Skip rule: Steps 5, 6 skipped — next visible step is Step 7 ("Pick items to ingest").
    await expect(dialog.getByRole("heading", { name: /Pick items to ingest/i })).toBeVisible({ timeout: 5_000 });
    // Step 5 ("Knowledge Store Details" heading) must NOT be visible.
    await expect(dialog.getByRole("heading", { name: /Knowledge Store Details/i })).not.toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });
  });

  test("Back button on Step 4 returns to the previous non-skipped step (Step 0)", async ({ page }) => {
    const libs = await apiCall(page, "GET", "/creator/libraries");
    const haveLib =
      libs.status === 200 && Array.isArray(libs.data?.libraries) && libs.data.libraries.length > 0;
    test.skip(!haveLib, "No libraries accessible to this user — Back-skip path cannot be tested.");

    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", { name: /\+\s*Create Knowledge/i }).click();

    const dialog = page.getByRole("dialog", { name: /Create Knowledge/i });
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // Existing library path so Steps 1-3 are skipped.
    await dialog.locator('input[type="radio"][value="existing"]').first().check();
    await expect(dialog.locator("#step0-library-select")).toBeVisible({ timeout: 5_000 });
    await dialog.getByRole("button", { name: /^Next$/ }).click();

    await expect(dialog.getByRole("heading", { name: /^Knowledge Store$/i })).toBeVisible({ timeout: 5_000 });

    // Click Back — should return to Step 0 (Library), skipping 3, 2, 1.
    await dialog.getByRole("button", { name: /^Back$/ }).click();
    await expect(dialog.getByRole("heading", { name: /^Library$/i })).toBeVisible({ timeout: 5_000 });

    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });
  });

  test("Esc key closes the wizard and creates no resources", async ({ page }) => {
    const beforeLibs = await apiCall(page, "GET", "/creator/libraries");
    const beforeKs = await apiCall(page, "GET", "/creator/knowledge-stores");
    const libCountBefore = (beforeLibs.data?.libraries || []).length;
    const ksCountBefore = (beforeKs.data?.knowledge_stores || []).length;

    await page.goto("/libraries");
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", { name: /\+\s*Create Knowledge/i }).click();
    const dialog = page.getByRole("dialog", { name: /Create Knowledge/i });
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 5_000 });

    const afterLibs = await apiCall(page, "GET", "/creator/libraries");
    const afterKs = await apiCall(page, "GET", "/creator/knowledge-stores");
    expect((afterLibs.data?.libraries || []).length).toBe(libCountBefore);
    expect((afterKs.data?.knowledge_stores || []).length).toBe(ksCountBefore);
  });
});
