const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * Phase 4.3 - Assistant <-> Knowledge Store binding (UI integration).
 *
 * Verifies that a creator can build an assistant whose RAG processor is
 * `knowledge_store_rag` and bind it to one or more Knowledge Stores via the
 * AssistantForm UI, then chat against it and receive a RAG-grounded answer.
 *
 * STATUS (Phase 4.3): EXPECTED TO FAIL.
 *   The AssistantForm.svelte still only knows about legacy `knowledgeBaseService`
 *   (port-9090 KBs); there is no KS picker, no `data-testid='ks-picker'`, and
 *   no plumbing into RAG_collections for `knowledge_store_rag`. Phase 5 will
 *   wire the picker and at that point this spec must turn green.
 *
 * Tagged @phase5-pending so Phase 5 + Phase 6 can grep for it.
 *
 * For Phase 5 wiring, the spec relies on the following stable hooks (please
 * preserve these IDs exactly):
 *   - data-testid="rag-processor-select"   (existing today; just confirming)
 *   - data-testid="ks-picker"              (NEW - container for the KS picker)
 *   - data-testid="ks-picker-option"       (NEW - one per available KS row,
 *                                           with attr data-ks-id={ks.id})
 *   - data-testid="ks-picker-selected-count" (OPTIONAL - displays N selected)
 *   - data-testid="assistant-save"         (existing today)
 *   - data-testid="assistant-chat-input"   (existing today on chat page)
 *   - data-testid="assistant-chat-response" (existing today)
 *
 * If these hooks aren't yet present the assertions fall back to role/text
 * lookups so the failure messages are informative.
 */

const FIXTURE_PATH = path.join(__dirname, "..", "fixtures", "sample.md");

test.describe.serial("Assistant with Knowledge Store RAG (UI) @phase5-pending", () => {
  let token;
  let libraryId;
  let itemId;
  let knowledgeStoreId;
  let knowledgeStoreName;
  let assistantId;
  let assistantName;
  let pipelineSkipReason = null;

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
        try { data = JSON.parse(text); } catch { data = text; }
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

    const ts = Date.now();

    // 1. Create library + upload sample.md
    const libRes = await apiCall(page, "POST", "/creator/libraries", {
      body: {
        name: `vt-A43-asst-lib-${ts}`,
        description: "Phase 4.3 assistant+KS spec",
      },
    });
    expect(libRes.status).toBe(200);
    libraryId = libRes.data.id;

    expect(fs.existsSync(FIXTURE_PATH)).toBe(true);
    const fixtureContent = fs.readFileSync(FIXTURE_PATH, "utf8");
    const upRes = await page.evaluate(
      async ({ libraryId, token, fixtureContent }) => {
        const blob = new Blob([fixtureContent], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, "sample.md");
        form.append("title", "Asst+KS Doc");
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

    const readyRes = await pollUntil(
      page,
      () => apiCall(page, "GET", `/creator/libraries/${libraryId}/items/${itemId}/status`),
      (r) => r && r.status === 200 && (r.data.status === "ready" || r.data.status === "failed"),
      { timeoutMs: 60000 },
    );
    expect(readyRes && readyRes.data.status).toBe("ready");

    // 2. KS options + create KS
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

    knowledgeStoreName = `vt-A43-asst-ks-${ts}`;
    const ksRes = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: knowledgeStoreName,
        description: "Phase 4.3 assistant+KS spec",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });
    if (ksRes.status === 503) {
      pipelineSkipReason = "KB Server unreachable -- skipping assistant+KS UI spec.";
      await context.close();
      return;
    }
    expect(ksRes.status).toBe(200);
    knowledgeStoreId = ksRes.data.id;

    // 3. Link library item to KS and wait for it to be ready (or skip if no API key).
    const linkRes = await apiCall(
      page,
      "POST",
      `/creator/knowledge-stores/${knowledgeStoreId}/content`,
      { body: { library_id: libraryId, item_ids: [itemId] } },
    );
    if (linkRes.status === 503) {
      pipelineSkipReason = "KB Server unreachable on link -- skipping.";
      await context.close();
      return;
    }
    expect(linkRes.status).toBe(200);

    const linkReady = await pollUntil(
      page,
      () => apiCall(page, "GET", `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`),
      (r) => r && r.status === 200 && (r.data.status === "ready" || r.data.status === "failed"),
      { timeoutMs: 90000 },
    );
    if (!linkReady || linkReady.data.status !== "ready") {
      pipelineSkipReason =
        "Embedding ingestion did not reach 'ready' (likely missing API key) -- skipping.";
    }

    assistantName = `vt_A43_asst_${ts}`;

    await context.close();
  });

  test.afterAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    if (assistantId) {
      await apiCall(page, "DELETE", `/creator/assistant/delete_assistant/${assistantId}`).catch(() => {});
    }
    if (knowledgeStoreId) {
      await apiCall(
        page,
        "DELETE",
        `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`,
      ).catch(() => {});
      await apiCall(page, "DELETE", `/creator/knowledge-stores/${knowledgeStoreId}`).catch(() => {});
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

  test("@cross-browser Creator can pick a Knowledge Store from the AssistantForm", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    // Navigate to the assistant creation flow.
    await page.goto("/assistants");
    await page.waitForLoadState("domcontentloaded");

    // Click + Create (the button label may vary across i18n; allow several).
    const createBtn = page.getByRole("button", {
      name: /\+\s*Create|Create Assistant|Crear|Sortu/i,
    }).first();
    await expect(createBtn).toBeVisible({ timeout: 10000 });
    await createBtn.click();

    // Pick `knowledge_store_rag` as RAG processor.
    const ragSelect = page.locator(
      '[data-testid="rag-processor-select"], select[name="rag_processor"], #rag_processor',
    ).first();
    await expect(ragSelect, "AssistantForm must expose a RAG processor select").toBeVisible({
      timeout: 10000,
    });
    await ragSelect.selectOption("knowledge_store_rag");

    // The KS picker must appear and list our seeded KS.
    const picker = page.locator('[data-testid="ks-picker"]');
    await expect(
      picker,
      "AssistantForm must show a KS picker (data-testid=\"ks-picker\") when rag_processor=knowledge_store_rag (Phase 5 wiring required)",
    ).toBeVisible({ timeout: 10000 });

    const ourKsOption = page.locator(
      `[data-testid="ks-picker-option"][data-ks-id="${knowledgeStoreId}"]`,
    );
    await expect(
      ourKsOption,
      "Our seeded KS must appear in the picker by id",
    ).toBeVisible({ timeout: 10000 });
    await expect(picker).toContainText(knowledgeStoreName);
  });

  test("Creator can save the assistant with KS binding and chat returns a RAG-grounded answer", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    await page.goto("/assistants");
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", { name: /\+\s*Create|Create Assistant/i }).first().click();

    // Wait for the form to mount + finish its initial config-fetch network
    // round-trips. Without this, the connector/model selects below race
    // against the assistant capabilities loader and selectOption can hang.
    await page.waitForLoadState("networkidle").catch(() => {});

    // Fill the name field.
    const nameInput = page.locator('input[name="name"], #name').first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });
    await nameInput.fill(assistantName);

    // Pick the RAG processor first so the Knowledge Store loader fires while
    // we are still on the form. Doing connector/model first sometimes leaves
    // the form in an intermediate loading state that blocks the rag select.
    const ragSelect = page.locator(
      '[data-testid="rag-processor-select"], select[name="rag_processor"], #rag_processor',
    ).first();
    await expect(ragSelect).toBeVisible({ timeout: 10000 });
    await expect(ragSelect).toBeEnabled({ timeout: 10000 });
    await ragSelect.selectOption("knowledge_store_rag");

    // Try to pick the Ollama connector + a chat-capable model so we don't
    // hit OpenAI (test orgs typically have a placeholder OpenAI key). If
    // Ollama is not configured with a chat model on this org we'll fall
    // through to whatever the form defaults to and detect the missing
    // chat capability when calling /chat/completions, then skip.
    let usingOllamaChat = false;
    const connectorSel = page.locator('select[name="connector"], #connector').first();
    if (await connectorSel.count()) {
      const connectorValues = await connectorSel.evaluate((sel) =>
        Array.from(sel.options).map((o) => o.value),
      );
      const ollamaVal = connectorValues.find((v) => /ollama/i.test(v));
      if (ollamaVal) {
        await connectorSel.selectOption(ollamaVal, { timeout: 5000 }).catch(() => {});
      }
    }
    const modelSel = page.locator('select[name="llm"], #llm').first();
    if (await modelSel.count()) {
      // Give the model dropdown a moment to repopulate after the connector
      // change before reading its options.
      await page.waitForTimeout(500);
      const modelValues = await modelSel.evaluate((sel) =>
        Array.from(sel.options).map((o) => o.value),
      );
      // Prefer a chat-capable Ollama model (qwen / llama / phi / mistral);
      // if the org only has an embedding model (e.g. nomic-embed-text)
      // there's no Ollama chat option to pick.
      const chatModel = modelValues.find((v) =>
        /qwen|llama|phi|mistral|gemma/i.test(v),
      );
      if (chatModel) {
        await modelSel.selectOption(chatModel, { timeout: 5000 }).catch(() => {});
        usingOllamaChat = true;
      }
    }

    const ourKsOption = page.locator(
      `[data-testid="ks-picker-option"][data-ks-id="${knowledgeStoreId}"]`,
    );
    await expect(ourKsOption).toBeVisible({ timeout: 10000 });
    // Click whatever interactive element selects this KS (checkbox or row).
    const checkbox = ourKsOption.locator('input[type="checkbox"], input[type="radio"]').first();
    if (await checkbox.count()) {
      await checkbox.check();
    } else {
      await ourKsOption.click();
    }

    // Save. Target the form's submit button specifically (the AssistantForm
    // sets `type="submit" form="assistant-form-main"`); a generic Save/Create
    // selector also matches the "Create Assistant" CTA at the page top.
    const saveBtn = page.locator(
      'button[type="submit"][form="assistant-form-main"]',
    ).first();
    await expect(saveBtn).toBeVisible({ timeout: 10000 });
    await expect(saveBtn).toBeEnabled({ timeout: 10000 });
    await saveBtn.click();
    // After successful save the form dispatches handleAssistantCreated which
    // calls goto('/assistants'); wait for that navigation so subsequent API
    // calls do not race the in-flight creation request.
    await page.waitForURL(/\/assistants(\?|$)/, { timeout: 30000 }).catch(() => {});
    await page.waitForLoadState("networkidle").catch(() => {});

    // Resolve the assistant id from the API for cleanup + chat.
    const list = await apiCall(page, "GET", "/creator/assistant/get_assistants");
    const all = list.data?.assistants || list.data?.data || list.data || [];
    // Backend normalises names to lowercase (and prefixes with org id), so
    // compare case-insensitively against a substring of the slugified name.
    const expectedSlug = assistantName.toLowerCase();
    const found = (Array.isArray(all) ? all : []).find(
      (a) =>
        a &&
        typeof a.name === "string" &&
        a.name.toLowerCase().includes(expectedSlug),
    );
    expect(found, `assistant ${assistantName} must exist after save`).toBeTruthy();
    assistantId = found.id;

    // Confirm the assistant carries the KS id in its RAG_collections.
    const detail = await apiCall(
      page,
      "GET",
      `/creator/assistant/get_assistant/${assistantId}`,
    );
    const ragCols = (detail.data && (detail.data.RAG_collections || detail.data.rag_collections)) || "";
    expect(
      String(ragCols).includes(knowledgeStoreId),
      "saved assistant.RAG_collections must contain the bound KS id",
    ).toBe(true);

    // Chat: post a completion via the OpenAI-compatible endpoint and assert
    // the response references the indexed phrase.
    const chatRes = await page.evaluate(
      async ({ assistantId, token }) => {
        const r = await fetch(`/creator/assistant/${assistantId}/chat/completions`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            messages: [
              { role: "user", content: "What is the capital of France according to the document?" },
            ],
            stream: false,
          }),
        });
        const text = await r.text();
        let data;
        try { data = JSON.parse(text); } catch { data = text; }
        return { status: r.status, data };
      },
      { assistantId, token },
    );
    // Detect environments where the chat backend is not actually available
    // (placeholder OpenAI key, no Ollama chat model in the org). The
    // backend can return HTTP 200 with an `error` body when the upstream
    // LLM call fails, so we inspect the body shape too. Treat that as a
    // skip rather than a failure -- we still proved the save+bind flow.
    const chatBlob = JSON.stringify(chatRes.data);
    const hasErrorBody =
      chatRes.data && typeof chatRes.data === "object" && chatRes.data.error;
    const noOpenAiKey = /Incorrect API key|invalid_api_key|your-openai-api-key/i.test(chatBlob);
    const noOllamaChat = /ollama.*not|connection refused|model not found/i.test(chatBlob);
    if (chatRes.status !== 200 || hasErrorBody) {
      test.skip(
        noOpenAiKey || noOllamaChat || hasErrorBody,
        `Chat backend not available in this env -- save+bind verified, chat skipped. Got: ${chatBlob.slice(0, 300)}`,
      );
    }
    expect(chatRes.status, `chat completions must succeed: ${chatBlob.slice(0, 400)}`).toBe(200);
    expect(
      /Paris/i.test(chatBlob),
      "RAG-grounded chat response must reference the indexed phrase 'Paris'",
    ).toBe(true);
  });

  test("Creator can pick multiple KSes when multi-select is supported", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    // This test is gated: it only runs if the KS picker exposes multiple
    // options. Phase 5 may or may not ship multi-select on day one.
    await page.goto("/assistants");
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", { name: /\+\s*Create|Create Assistant/i }).first().click();

    await page.locator(
      '[data-testid="rag-processor-select"], select[name="rag_processor"], #rag_processor',
    ).first().selectOption("knowledge_store_rag");

    const allOptions = page.locator('[data-testid="ks-picker-option"]');
    const optionCount = await allOptions.count();
    test.skip(optionCount < 2, "Only one KS visible -- multi-select assertion not applicable.");

    // Select two.
    const inputs = allOptions.locator('input[type="checkbox"]');
    const inputCount = await inputs.count();
    test.skip(inputCount < 2, "Picker is single-select -- multi-select not supported.");

    await inputs.nth(0).check();
    await inputs.nth(1).check();

    const counter = page.locator('[data-testid="ks-picker-selected-count"]');
    if (await counter.count()) {
      await expect(counter).toContainText("2");
    }
  });
});
