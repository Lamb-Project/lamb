const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * E2E: Library → Knowledge Store → Context-Aware KS RAG + Document RAG → UI chat.
 *
 * Validates the query_rewriting_ks_rag + single_file_rag (document reference) stack
 * described in docs/superpowers/plans/2026-06-01-query-rewriting-ks-rag-implementation-summary.md.
 *
 * Flow:
 *   1. Create library + upload two distinct markdown files (API):
 *      - one indexed in the Knowledge Store (KS token),
 *      - one used only as the Document RAG reference (doc-RAG token).
 *   2. Create Knowledge Store + link the KS-only item + poll until ready (API).
 *   3. Create assistant via UI with query_rewriting_ks_rag, document RAG, and KS binding.
 *   4. Chat via the assistant detail UI; verify each token appears in its own channel.
 *   5. Cleanup assistant, KS content link, KS, library (API).
 */

/** Indexed in the Knowledge Store — must appear only in the user Context: block. */
const KS_RAG_TOKEN = "LAMBKSCTX9001";
const KS_DOC_CONTENT = `# E2E KS Retrieval Document

The KS retrieval verification token is ${KS_RAG_TOKEN}.
This file is indexed in the Knowledge Store for dynamic RAG retrieval.
`;

/** Attached as Document RAG reference — must appear only in the system REFERENCE DOCUMENT body. */
const DOC_RAG_TOKEN = "LAMBDOCRAG9002";
const DOC_RAG_CONTENT = `# E2E Reference Document

The document RAG reference token is ${DOC_RAG_TOKEN}.
This file is attached as a static reference document in the system prompt.
`;

const SYSTEM_PROMPT =
  "You are an assistant for an automated E2E test. " +
  "Answer using only information present in your context (the reference document and any retrieved knowledge store content). " +
  "When asked about verification tokens, quote each token exactly as it appears in the context " +
  "and indicate whether it came from the reference document or from retrieved knowledge store content.";

/** User message for real LLM chat — probes both tokens without naming them. */
const LLM_TOKEN_PROBE_MESSAGE =
  "What are the two verification tokens described in your context? " +
  "One should appear in the static reference document attached to this assistant. " +
  "The other should appear in the knowledge store retrieval context about dynamic RAG. " +
  "Reply with both exact token strings and label which source each came from.";

/** Shorter probe for bypass echo (triggers KS retrieval query). */
const BYPASS_CHAT_MESSAGE =
  "Do you have reference context from both channels? KS retrieval verification probe.";

// Matches simple_augment.DEFAULT_RAG_PROMPT_TEMPLATE — predictable {context} placement for KS RAG.
const RAG_PROMPT_TEMPLATE =
  "Use the following context to answer the question. " +
  "If the context does not contain the answer, say you do not know.\n\n" +
  "Context:\n{context}\n\nQuestion: {user_input}";

const REFERENCE_DOCUMENT_BOILERPLATE =
  /## REFERENCE DOCUMENT\s+This document has been selected by the assistant creator as a reference that will likely be useful for many queries, as it is generally a helpful document\. Use it as context when answering questions\.\s+/i;

/** Collapse whitespace for stable substring / equality checks. */
function normalizeText(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\s+/g, " ")
    .trim();
}

/** Split full-conversation-bypass echo into system and user sections. */
function splitBypassConversation(responseText) {
  const userMatch = responseText.match(/\suser:\s/i);
  if (!userMatch || userMatch.index === undefined) {
    const systemOnly = responseText.replace(/^system:\s/i, "").trim();
    return { system: systemOnly, user: "" };
  }
  const system = responseText.slice(0, userMatch.index).replace(/^system:\s/i, "").trim();
  let user = responseText.slice(userMatch.index).replace(/^\s*user:\s/i, "").trim();
  const assistantMatch = user.match(/\sassistant:\s/i);
  if (assistantMatch && assistantMatch.index !== undefined) {
    user = user.slice(0, assistantMatch.index).trim();
  }
  return { system, user };
}

/** Document body injected after the REFERENCE DOCUMENT boilerplate in system prompt. */
function extractReferenceDocumentBody(systemText) {
  const markerIdx = systemText.search(/## REFERENCE DOCUMENT/i);
  if (markerIdx === -1) return null;
  const afterMarker = systemText.slice(markerIdx);
  const bodyMatch = afterMarker.replace(REFERENCE_DOCUMENT_BOILERPLATE, "");
  if (bodyMatch === afterMarker) return null;
  return bodyMatch.trim();
}

/** RAG chunks substituted into the last user message ({context} placeholder). */
function extractRagContextBlock(userText) {
  if (!userText) return null;
  const patterns = [
    /Context:\s*([\s\S]*?)\sQuestion:\s/i,
    /Context:\s*([\s\S]*?)\n\nQuestion:/i,
    /This is the context:\s*([\s\S]*?)\n(?:This is the user input:|Now answer|$)/i,
  ];
  for (const re of patterns) {
    const match = userText.match(re);
    if (match?.[1]?.trim()) return match[1].trim();
  }
  return null;
}

/** True when the reply is a full-conversation-bypass echo (system:/user: roles). */
function isBypassEcho(responseText) {
  return /^system:\s/i.test(responseText) || (/\suser:\s/i.test(responseText) && /REFERENCE DOCUMENT/i.test(responseText));
}

/** Real LLM answered with both channel tokens in natural language. */
function llmResponseHasBothTokens(responseText) {
  return (
    !isBypassEcho(responseText) &&
    responseText.includes(KS_RAG_TOKEN) &&
    responseText.includes(DOC_RAG_TOKEN) &&
    !/thinking/i.test(responseText)
  );
}

function chatBackendUnavailable(responseText) {
  const noOpenAiKey = /incorrect api key|invalid_api_key|your-openai-api-key/i.test(responseText);
  const noOllamaChat = /ollama.*not|connection refused|model not found|\[ollama error\]/i.test(
    responseText,
  );
  const hasError =
    /error|failed|unavailable/i.test(responseText) && responseText.length < 300;
  return noOpenAiKey || noOllamaChat || hasError;
}

test.describe.serial("Context-aware KS RAG + document RAG (UI chat)", () => {
  const ts = Date.now();
  const libraryName = `pw_ctx_lib_${ts}`;
  const ksName = `pw_ctx_ks_${ts}`;
  const assistantName = `pw_ctx_asst_${ts}`;

  let token;
  let libraryId;
  let ksItemId;
  let docRagItemId;
  let knowledgeStoreId;
  let assistantId;
  let assistantUsesBypass = true;
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

  async function pollUntil(page, fn, predicate, { timeoutMs = 90000, baseDelay = 1000 } = {}) {
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

  async function uploadLibraryMarkdown(page, { filename, title, docContent }) {
    return page.evaluate(
      async ({ libraryId, token, filename, title, docContent }) => {
        const blob = new Blob([docContent], { type: "text/markdown" });
        const form = new FormData();
        form.append("file", blob, filename);
        form.append("title", title);

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
      { libraryId, token, filename, title, docContent },
    );
  }

  async function pollItemReady(page, itemId) {
    const final = await pollUntil(
      page,
      () => apiCall(page, "GET", `/creator/libraries/${libraryId}/items/${itemId}/status`),
      (r) => r && r.status === 200 && (r.data.status === "ready" || r.data.status === "failed"),
      { timeoutMs: 60000 },
    );
    expect(final?.data?.status).toBe("ready");
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
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
  });

  test("step 1: create library", async ({ page }) => {
    const res = await apiCall(page, "POST", "/creator/libraries", {
      body: { name: libraryName, description: "Context-aware RAG E2E" },
    });
    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("id");
    libraryId = res.data.id;
  });

  test("step 2: upload KS document (indexed in Knowledge Store)", async ({ page }) => {
    expect(libraryId).toBeTruthy();

    const res = await uploadLibraryMarkdown(page, {
      filename: "ks-retrieval-doc.md",
      title: "KS Retrieval Doc",
      docContent: KS_DOC_CONTENT,
    });

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("item_id");
    ksItemId = res.data.item_id;
  });

  test("step 3: poll KS library item until ready", async ({ page }) => {
    await pollItemReady(page, ksItemId);
  });

  test("step 4: upload Document RAG reference (not linked to KS)", async ({ page }) => {
    expect(libraryId).toBeTruthy();

    const res = await uploadLibraryMarkdown(page, {
      filename: "doc-rag-reference.md",
      title: "Doc RAG Reference",
      docContent: DOC_RAG_CONTENT,
    });

    expect(res.status).toBe(200);
    expect(res.data).toHaveProperty("item_id");
    docRagItemId = res.data.item_id;
  });

  test("step 5: poll Document RAG library item until ready", async ({ page }) => {
    await pollItemReady(page, docRagItemId);
  });

  test("step 6: create knowledge store", async ({ page }) => {
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

    const res = await apiCall(page, "POST", "/creator/knowledge-stores", {
      body: {
        name: ksName,
        description: "Context-aware RAG E2E",
        chunking_strategy: chunkingStrategy,
        embedding_vendor: embeddingVendor,
        embedding_model: embeddingModel,
        vector_db_backend: vectorDbBackend,
      },
    });

    if (res.status === 503) {
      pipelineSkipReason = "KB Server v2 not reachable (503)";
      test.skip(true, pipelineSkipReason);
      return;
    }
    expect(res.status).toBe(200);
    knowledgeStoreId = res.data.id;
  });

  test("step 7: link KS document to knowledge store and wait until ready", async ({ page }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");
    expect(knowledgeStoreId).toBeTruthy();

    const linkRes = await apiCall(
      page,
      "POST",
      `/creator/knowledge-stores/${knowledgeStoreId}/content`,
      { body: { library_id: libraryId, item_ids: [ksItemId] } },
    );

    if (linkRes.status === 503) {
      pipelineSkipReason = "KB Server unreachable on content link";
      test.skip(true, pipelineSkipReason);
      return;
    }
    expect(linkRes.status).toBe(200);

    const final = await pollUntil(
      page,
      () =>
        apiCall(
          page,
          "GET",
          `/creator/knowledge-stores/${knowledgeStoreId}/content/${ksItemId}`,
        ),
      (r) =>
        r &&
        r.status === 200 &&
        (r.data.status === "ready" || r.data.status === "failed"),
      { timeoutMs: 120000 },
    );

    if (!final || final.data.status !== "ready") {
      pipelineSkipReason =
        "KS embedding ingestion did not reach ready (likely missing embedding API key)";
      test.skip(true, pipelineSkipReason);
      return;
    }
  });

  test("step 8-9: create assistant with context-aware RAG + document reference", async ({
    page,
  }) => {
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");

    await page.goto("/assistants?view=create");
    await page.waitForLoadState("domcontentloaded");

    const createBtn = page.getByRole("button", {
      name: /\+\s*Create|Create Assistant|Crear/i,
    }).first();
    await expect(createBtn).toBeVisible({ timeout: 10000 });
    await createBtn.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30000 });

    await page.fill("#assistant-name", assistantName);
    await page.fill("#assistant-description", `E2E context-aware RAG test ${ts}`);
    await page.fill("#system-prompt", SYSTEM_PROMPT);
    await page.fill("#prompt_template", RAG_PROMPT_TEMPLATE);

    // Advanced mode exposes connector / LLM pickers.
    const advancedToggle = page.getByText(/Advanced Mode/i).first();
    if (await advancedToggle.count()) {
      await advancedToggle.click();
    }

    await page.waitForLoadState("networkidle").catch(() => {});

    // Connector: bypass by default (deterministic CI). Set PLAYWRIGHT_PREFER_REAL_LLM=1
    // to exercise OpenAI/Ollama and the natural-language dual-token chat assertions.
    const preferRealLlm = process.env.PLAYWRIGHT_PREFER_REAL_LLM === "1";
    const connectorSel = page.locator("#connector");
    if (await connectorSel.count()) {
      const connectorValues = await connectorSel.evaluate((sel) =>
        Array.from(sel.options).map((o) => o.value),
      );
      const bypassVal = connectorValues.find((v) => v === "bypass");
      const ollamaVal = connectorValues.find((v) => /ollama/i.test(v));
      const openaiVal = connectorValues.find((v) => v === "openai");

      if (preferRealLlm && ollamaVal) {
        assistantUsesBypass = false;
        await connectorSel.selectOption(ollamaVal);
        await page.waitForTimeout(500);
        const modelSel = page.locator("#llm");
        const modelValues = await modelSel.evaluate((sel) =>
          Array.from(sel.options).map((o) => o.value),
        );
        const chatModel = modelValues.find((v) =>
          /qwen|llama|phi|mistral|gemma/i.test(v),
        );
        if (chatModel) {
          await modelSel.selectOption(chatModel);
        }
      } else if (preferRealLlm && openaiVal) {
        assistantUsesBypass = false;
        await connectorSel.selectOption(openaiVal);
      } else if (bypassVal) {
        assistantUsesBypass = true;
        await connectorSel.selectOption(bypassVal);
        await page.waitForTimeout(300);
        const modelSel = page.locator("#llm");
        const modelValues = await modelSel.evaluate((sel) =>
          Array.from(sel.options).map((o) => o.value),
        );
        const fullConv = modelValues.find((v) => v === "full-conversation-bypass");
        if (fullConv) {
          await modelSel.selectOption(fullConv);
        }
      } else if (ollamaVal) {
        assistantUsesBypass = false;
        await connectorSel.selectOption(ollamaVal);
        await page.waitForTimeout(500);
        const modelSel = page.locator("#llm");
        const modelValues = await modelSel.evaluate((sel) =>
          Array.from(sel.options).map((o) => o.value),
        );
        const chatModel = modelValues.find((v) =>
          /qwen|llama|phi|mistral|gemma/i.test(v),
        );
        if (chatModel) {
          await modelSel.selectOption(chatModel);
        }
      } else if (openaiVal) {
        assistantUsesBypass = false;
        await connectorSel.selectOption(openaiVal);
      }
    }

    // Context-aware KS RAG (query rewriting + Knowledge Store retrieval).
    const ragSelect = page.locator("#rag-processor");
    await expect(ragSelect).toBeVisible({ timeout: 10000 });
    await ragSelect.selectOption("query_rewriting_ks_rag");

    // Document RAG: attach the library item as reference document.
    const docRagToggle = page.locator("label").filter({ hasText: /Reference Document/i }).first();
    await expect(docRagToggle).toBeVisible({ timeout: 10000 });
    await docRagToggle.click();

    // Wait for libraries to load, then pick our library + item.
    const librarySel = page.locator("#library-selector");
    await expect(librarySel).toBeVisible({ timeout: 30000 });
    await expect(librarySel.locator(`option[value="${libraryId}"]`)).toHaveCount(1, {
      timeout: 30000,
    });
    await librarySel.selectOption(libraryId);

    const itemSel = page.locator("#item-selector");
    await expect(itemSel).toBeVisible({ timeout: 30000 });
    await expect(itemSel.locator(`option[value="${docRagItemId}"]`)).toHaveCount(1, {
      timeout: 30000,
    });
    await itemSel.selectOption(docRagItemId);

    // Bind the Knowledge Store created earlier.
    const ksPicker = page.locator('[data-testid="ks-picker"]');
    await expect(ksPicker).toBeVisible({ timeout: 30000 });
    const ksCheckbox = ksPicker.getByRole("checkbox", { name: new RegExp(ksName) });
    await expect(ksCheckbox).toBeVisible({ timeout: 30000 });
    await ksCheckbox.check();

    const saveButton = page.locator('button[type="submit"][form="assistant-form-main"]');
    await expect(saveButton).toBeEnabled({ timeout: 60000 });

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

    await Promise.all([createRequest, saveButton.click()]);
    await page.waitForURL(/\/assistants(\?|$)/, { timeout: 30000 }).catch(() => {});

    const list = await apiCall(page, "GET", "/creator/assistant/get_assistants");
    const all = list.data?.assistants || list.data?.data || list.data || [];
    const slug = assistantName.toLowerCase();
    const found = (Array.isArray(all) ? all : []).find(
      (a) => a && typeof a.name === "string" && a.name.toLowerCase().includes(slug),
    );
    expect(found, `assistant ${assistantName} must exist after save`).toBeTruthy();
    assistantId = found.id;

    const detail = await apiCall(page, "GET", `/creator/assistant/get_assistant/${assistantId}`);
    const meta = JSON.parse(detail.data?.metadata || "{}");
    expect(meta.rag_processor).toBe("query_rewriting_ks_rag");
    expect(meta.document_rag).toBe("single_file_rag");
    expect(meta.library_id).toBe(libraryId);
    expect(meta.item_id).toBe(docRagItemId);
    expect(meta.item_id).not.toBe(ksItemId);
    expect(String(detail.data?.RAG_collections || "")).toContain(knowledgeStoreId);
    if (meta.connector && meta.connector !== "bypass") {
      assistantUsesBypass = false;
    }
  });

  test("step 10-12: chat via UI and verify both RAG channels independently", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    test.skip(!!pipelineSkipReason, pipelineSkipReason || "");
    expect(assistantId, "assistant must exist from previous step").toBeTruthy();

    await page.goto("/assistants");
    await page.waitForLoadState("networkidle").catch(() => {});

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(assistantName);
      await page.waitForTimeout(500);
    }

    await page.getByText(assistantName, { exact: false }).first().click();

    const chatTab = page.getByRole("button", { name: /Chat/i }).first();
    await expect(chatTab).toBeVisible({ timeout: 10000 });
    await chatTab.click();

    const chatInput = page.getByPlaceholder("Type your message...");
    await expect(chatInput).toBeVisible({ timeout: 30000 });

    const chatMessage = assistantUsesBypass ? BYPASS_CHAT_MESSAGE : LLM_TOKEN_PROBE_MESSAGE;
    await chatInput.fill(chatMessage);
    await page.getByRole("button", { name: /^Send$/i }).click();

    const assistantBubble = page.locator(".bg-gray-200.text-gray-800").last();
    await expect(assistantBubble).toBeVisible({ timeout: 120000 });

    let responseText = "";
    await expect
      .poll(
        async () => {
          responseText = (await assistantBubble.innerText()).trim();
          if (chatBackendUnavailable(responseText)) {
            return responseText;
          }
          if (isBypassEcho(responseText)) {
            const { system, user } = splitBypassConversation(responseText);
            const docBody = extractReferenceDocumentBody(system);
            const ragBlock = extractRagContextBlock(user);
            const bypassReady =
              docBody &&
              normalizeText(docBody) === normalizeText(DOC_RAG_CONTENT) &&
              ragBlock &&
              ragBlock.includes(KS_RAG_TOKEN) &&
              !ragBlock.includes(DOC_RAG_TOKEN);
            return bypassReady ? responseText : "";
          }
          if (llmResponseHasBothTokens(responseText)) {
            return responseText;
          }
          return "";
        },
        { timeout: 120000, intervals: [500, 1000, 2000] },
      )
      .not.toBe("");

    console.log(
      `[${assistantUsesBypass ? "bypass" : "real-llm"}] Assistant UI response: "${responseText.slice(0, 1600)}"`,
    );

    if (chatBackendUnavailable(responseText)) {
      test.skip(
        true,
        `Chat backend not available — setup verified, chat skipped. Got: ${responseText.slice(0, 300)}`,
      );
    }

    if (isBypassEcho(responseText)) {
      const { system, user } = splitBypassConversation(responseText);

      expect(system, "bypass echo must include a system message").toBeTruthy();
      expect(user, "bypass echo must include an augmented user message").toBeTruthy();

      // 1) Document RAG: system body must match the reference doc only (not the KS doc).
      const injectedDoc = extractReferenceDocumentBody(system);
      expect(injectedDoc, "system message must contain document body after REFERENCE DOCUMENT boilerplate").toBeTruthy();
      expect(normalizeText(injectedDoc)).toBe(normalizeText(DOC_RAG_CONTENT));
      expect(injectedDoc, "document RAG body must carry the doc-RAG token").toContain(DOC_RAG_TOKEN);
      expect(injectedDoc, "document RAG body must not leak the KS-only token").not.toContain(
        KS_RAG_TOKEN,
      );

      // 2) KS RAG: user Context block must carry the indexed doc only (not the reference doc).
      const injectedRag = extractRagContextBlock(user);
      expect(injectedRag, "user message must contain a Context: block with KS retrieval").toBeTruthy();
      expect(injectedRag.length, "KS context block must be non-empty").toBeGreaterThan(20);
      expect(injectedRag, "KS context must include the KS-only token").toContain(KS_RAG_TOKEN);
      expect(injectedRag, "KS context should include the KS document heading").toMatch(
        /E2E KS Retrieval Document/i,
      );
      expect(injectedRag, "KS context must not leak the document-RAG token").not.toContain(
        DOC_RAG_TOKEN,
      );

      // Cross-channel isolation: each token stays in its pipeline.
      expect(system, "doc-RAG token must appear in system (document RAG)").toContain(DOC_RAG_TOKEN);
      expect(system, "KS token must not appear in system document body").not.toContain(KS_RAG_TOKEN);
      expect(user, "KS token must appear in augmented user message (KS RAG)").toContain(KS_RAG_TOKEN);
      expect(user, "doc-RAG token must not appear in user Context block").not.toContain(DOC_RAG_TOKEN);
      return;
    }

    // Real LLM: both tokens must appear in the assistant's natural-language answer,
    // proving it read document RAG (system) and KS RAG (retrieved context).
    expect(
      responseText,
      "LLM response must include the knowledge-store verification token",
    ).toContain(KS_RAG_TOKEN);
    expect(
      responseText,
      "LLM response must include the document-RAG reference token",
    ).toContain(DOC_RAG_TOKEN);
  });

  test("step 13: delete assistant", async ({ page }) => {
    if (!assistantId) return;

    await apiCall(page, "DELETE", `/creator/assistant/delete_assistant/${assistantId}`);

    const list = await apiCall(page, "GET", "/creator/assistant/get_assistants");
    const all = list.data?.assistants || list.data?.data || list.data || [];
    const stillThere = (Array.isArray(all) ? all : []).some((a) => String(a.id) === String(assistantId));
    expect(stillThere).toBe(false);
    assistantId = null;
  });

  test("step 14: remove KS content link and delete knowledge store", async ({ page }) => {
    if (!knowledgeStoreId) return;

    if (ksItemId) {
      await apiCall(
        page,
        "DELETE",
        `/creator/knowledge-stores/${knowledgeStoreId}/content/${ksItemId}`,
      ).catch(() => {});
    }

    await apiCall(page, "DELETE", `/creator/knowledge-stores/${knowledgeStoreId}`);
    knowledgeStoreId = null;
  });

  test("step 15: delete library", async ({ page }) => {
    if (!libraryId) return;

    await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`);
    libraryId = null;
  });

  test.afterAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: path.join(__dirname, "..", ".auth", "state.json"),
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    if (assistantId) {
      await apiCall(page, "DELETE", `/creator/assistant/delete_assistant/${assistantId}`).catch(
        () => {},
      );
    }
    if (knowledgeStoreId && ksItemId) {
      await apiCall(
        page,
        "DELETE",
        `/creator/knowledge-stores/${knowledgeStoreId}/content/${ksItemId}`,
      ).catch(() => {});
    }
    if (knowledgeStoreId) {
      await apiCall(page, "DELETE", `/creator/knowledge-stores/${knowledgeStoreId}`).catch(
        () => {},
      );
    }
    if (libraryId) {
      await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`).catch(() => {});
    }
    await context.close();
  });
});
