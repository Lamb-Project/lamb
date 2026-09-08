const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, "..", ".env"), quiet: true });

/**
 * Knowledge Store, created the way an instructor creates it, must work end to end.
 *
 * Origin: 2026-09-08, Marc's hands-on review of aac-refactoring. A store created
 * through the UI with its DEFAULT embedding vendor (Ollama, first in the list)
 * was born with an unreachable endpoint and every document failed at ingestion.
 * The only spec covering assistant + Knowledge Store RAG skipped itself for the
 * same reason, so nothing was red.
 *
 * This spec drives the real surfaces:
 *   1. API:  create a library and upload the sample fixture (setup, not under test).
 *   2. UI:   "New Knowledge Store" modal -> name -> Advanced -> keep the DEFAULT
 *            vendor/model the UI proposes -> Create.
 *   3. UI:   store detail -> "Add Content" -> pick the library -> pick the item -> Add.
 *   4. API:  the content link must reach `ready` with chunks > 0.
 *            (This is the assertion that would have failed on 2026-09-08.)
 *   5. UI:   assistant form -> RAG processor `knowledge_store_rag` -> pick the store
 *            -> Save, keeping the organization's default connector and model.
 *   6. API:  chat completion against the assistant answers from the store.
 *   7. Cleanup (skip with KEEP_FIXTURES=1).
 *
 * A missing or unreachable embedding provider is a FAILURE here, never a skip:
 * the whole point is that the default the UI proposes has to work.
 */

const FIXTURE_PATH = path.join(__dirname, "..", "fixtures", "sample.md");
const STAMP = Date.now();
const LIBRARY_NAME = `ksdef_lib_${STAMP}`;
const KS_NAME = `ksdef_ks_${STAMP}`;
const ASSISTANT_NAME = `ksdef_asst_${STAMP}`;

async function apiCall(page, method, url, body) {
  return page.evaluate(
    async ({ method, url, body }) => {
      const token = localStorage.getItem("userToken");
      const r = await fetch(url, {
        method,
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data = null;
      try { data = await r.json(); } catch (_) { data = null; }
      return { status: r.status, data };
    },
    { method, url, body },
  );
}

async function pollUntil(fn, done, { timeoutMs = 120000, intervalMs = 2000 } = {}) {
  const t0 = Date.now();
  let last = null;
  while (Date.now() - t0 < timeoutMs) {
    last = await fn();
    if (done(last)) return last;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return last;
}

test.describe.serial("Knowledge Store with the UI's default vendor -> assistant RAG", () => {
  test.setTimeout(150000);
  let libraryId;
  let itemId;
  let knowledgeStoreId;
  let assistantId;
  let defaultVendor;
  let defaultModel;

  test("setup: library with the sample document (API)", async ({ page }) => {
    await page.goto("/");
    const lib = await apiCall(page, "POST", "/creator/libraries", { name: LIBRARY_NAME, description: "default-vendor spec" });
    expect(lib.status, JSON.stringify(lib.data).slice(0, 300)).toBe(200);
    libraryId = lib.data.id || (lib.data.library && lib.data.library.id);
    expect(libraryId).toBeTruthy();

    const fileB64 = fs.readFileSync(FIXTURE_PATH).toString("base64");
    const up = await page.evaluate(
      async ({ libraryId, fileB64 }) => {
        const token = localStorage.getItem("userToken");
        const bytes = Uint8Array.from(atob(fileB64), (c) => c.charCodeAt(0));
        const fd = new FormData();
        fd.append("file", new Blob([bytes], { type: "text/markdown" }), "sample.md");
        const r = await fetch(`/creator/libraries/${libraryId}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        let data = null;
        try { data = await r.json(); } catch (_) {}
        return { status: r.status, data };
      },
      { libraryId, fileB64 },
    );
    expect(up.status, JSON.stringify(up.data).slice(0, 300)).toBe(200);
    itemId = up.data.item_id || up.data.id || (up.data.item && up.data.item.id);
    expect(itemId).toBeTruthy();

    const ready = await pollUntil(
      () => apiCall(page, "GET", `/creator/libraries/${libraryId}/items/${itemId}/status`),
      (r) => r && r.status === 200 && ["ready", "failed"].includes(r.data.status),
      { timeoutMs: 60000 },
    );
    expect(ready && ready.data.status, JSON.stringify(ready && ready.data).slice(0, 300)).toBe("ready");
  });

  test("UI: create the store keeping the default vendor and model", async ({ page }) => {
    await page.goto("/libraries?section=knowledge-stores");
    await page.locator("button", { hasText: /New Knowledge Store/i }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10000 });

    await dialog.locator("#ks-name").fill(KS_NAME);
    // Open "Advanced: chunking, embedding, vector DB" and read what the UI proposes.
    await dialog.locator("summary", { hasText: /Advanced/i }).click();
    const vendorSel = dialog.locator("#ks-vendor");
    await expect(vendorSel).toBeVisible({ timeout: 10000 });
    await expect
      .poll(async () => vendorSel.inputValue(), { timeout: 15000, message: "vendor default must load" })
      .not.toBe("");
    defaultVendor = await vendorSel.inputValue();
    defaultModel = await dialog.locator("#ks-model").inputValue();
    test.info().annotations.push({ type: "default-vendor", description: `${defaultVendor} / ${defaultModel}` });

    await dialog.getByRole("button", { name: /^Create Knowledge Store$/i }).click();
    await expect(dialog).not.toBeVisible({ timeout: 20000 });

    // The list is the UI's own proof; the API gives us the id.
    await expect(page.getByText(KS_NAME).first()).toBeVisible({ timeout: 15000 });
    const list = await apiCall(page, "GET", "/creator/knowledge-stores");
    const rows = Array.isArray(list.data) ? list.data : (list.data.knowledge_stores || list.data.items || []);
    const mine = rows.find((k) => k.name === KS_NAME);
    expect(mine, "created store must be listed by the API").toBeTruthy();
    knowledgeStoreId = mine.id;
    expect(mine.embedding_vendor).toBe(defaultVendor);
  });

  test("UI: add the library document to the store", async ({ page }) => {
    await page.goto("/libraries?section=knowledge-stores");
    await page.getByText(KS_NAME).first().click();
    await expect(page.getByRole("heading", { name: /Knowledge Store Details/i })).toBeVisible({ timeout: 15000 });

    await page.locator("button", { hasText: /Add Content/i }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10000 });

    // Step 1: pick the library. The radios carry the library id as value and no
    // accessible name (worth a UX finding of its own).
    const libRadio = dialog.locator(`input[type="radio"][value="${libraryId}"]`);
    await expect(libRadio).toHaveCount(1, { timeout: 10000 });
    await libRadio.check({ force: true });
    await dialog.getByRole("button", { name: /^Next$/i }).click();

    // Step 2: the library's items, pre-selected; make sure ours is ticked.
    await expect(dialog.getByRole("button", { name: /Deselect all|Select all/i })).toBeVisible({ timeout: 10000 });
    const boxes = dialog.locator('input[type="checkbox"]');
    const n = await boxes.count();
    expect(n, "the library must list at least one item").toBeGreaterThan(0);
    for (let i = 0; i < n; i++) {
      if (!(await boxes.nth(i).isChecked())) await boxes.nth(i).check({ force: true });
    }
    await dialog.getByRole("button", { name: /^Next$/i }).click();

    // Step 3: review -> Add.
    const addBtn = dialog.getByRole("button", { name: /^Add to Knowledge Store$|^Add$/i });
    await expect(addBtn).toBeEnabled({ timeout: 10000 });
    await addBtn.click();
    await expect(dialog).not.toBeVisible({ timeout: 30000 });
  });

  test("ingestion with the default vendor must reach ready (this is the 2026-09-08 bug)", async ({ page }) => {
    await page.goto("/");
    const link = await pollUntil(
      () => apiCall(page, "GET", `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`),
      (r) => r && r.status === 200 && ["ready", "failed"].includes(r.data.status),
      { timeoutMs: 180000 },
    );
    const detail = JSON.stringify(link && link.data).slice(0, 600);
    expect(link && link.status, detail).toBe(200);
    expect(
      link.data.status,
      `Store created with the UI default (${defaultVendor} / ${defaultModel}) must ingest. Got: ${detail}`,
    ).toBe("ready");
    expect(link.data.chunks_created, detail).toBeGreaterThan(0);

    // And the UI must show it: no "Failed" badge on the store's content table.
    await page.goto("/libraries?section=knowledge-stores");
    await page.getByText(KS_NAME).first().click();
    await expect(page.getByRole("heading", { name: /Knowledge Store Details/i })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Ingestion failed/i)).toHaveCount(0);
  });

  test("UI: assistant bound to the store, default connector and model", async ({ page }) => {
    await page.goto("/assistants");
    await page.getByRole("button", { name: /\+\s*Create|Create Assistant/i }).first().click();

    const nameInput = page.locator('input[name="name"], #assistant-name').first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });
    await nameInput.fill(ASSISTANT_NAME);

    const sysPrompt = page.locator('textarea[name="system_prompt"], #system-prompt, #system_prompt').first();
    if (await sysPrompt.count()) {
      await sysPrompt.fill("Answer only from the provided context. If the context does not contain the answer, say NOT_IN_CONTEXT.");
    }

    const ragSelect = page.locator("#rag-processor");
    await expect(ragSelect).toBeVisible({ timeout: 10000 });
    await expect(ragSelect).toBeEnabled({ timeout: 10000 });
    await ragSelect.selectOption("knowledge_store_rag");

    const picker = page.locator('[data-testid="ks-picker"]');
    await expect(picker).toBeVisible({ timeout: 10000 });
    const ourBox = picker.getByRole("checkbox", { name: new RegExp(KS_NAME) });
    if (await ourBox.count()) {
      await ourBox.first().check();
    } else {
      await picker.locator(`input[type="checkbox"][value="${knowledgeStoreId}"]`).check();
    }

    const saveBtn = page.locator('[data-testid="assistant-save"], button[type="submit"][form="assistant-form-main"]').first();
    await expect(saveBtn).toBeVisible({ timeout: 10000 });
    await expect(saveBtn).toBeEnabled({ timeout: 10000 });
    await saveBtn.click();
    await page.waitForURL(/\/assistants(\?|$)/, { timeout: 30000 }).catch(() => {});
    await page.waitForLoadState("networkidle").catch(() => {});

    const found = await pollUntil(
      async () => {
        const r = await apiCall(page, "GET", "/creator/assistant/get_assistants");
        const arr = (r.data && (r.data.assistants || r.data.items)) || (Array.isArray(r.data) ? r.data : []);
        const slug = ASSISTANT_NAME.toLowerCase();
        return arr.find((a) => a && typeof a.name === "string" && a.name.toLowerCase().includes(slug));
      },
      (a) => !!a,
      { timeoutMs: 20000, intervalMs: 1000 },
    );
    expect(found, `assistant ${ASSISTANT_NAME} must exist after save`).toBeTruthy();
    assistantId = found.id;
    expect(String(found.RAG_collections || ""), "assistant must be bound to the store").toContain(knowledgeStoreId);
    const meta = typeof found.metadata === "string" ? found.metadata : JSON.stringify(found.metadata || found.api_callback || "");
    expect(meta).toContain("knowledge_store_rag");
  });

  test("chat answers from the store", async ({ page }) => {
    await page.goto("/");
    const res = await apiCall(page, "POST", `/creator/assistant/${assistantId}/chat/completions`, {
      messages: [{ role: "user", content: "According to the context, what is the capital of France?" }],
      stream: false,
      max_tokens: 120,
    });
    const blob = JSON.stringify(res.data).slice(0, 800);
    expect(res.status, `chat completions must succeed: ${blob}`).toBe(200);
    const answer = (res.data && res.data.choices && res.data.choices[0] && res.data.choices[0].message && res.data.choices[0].message.content) || "";
    expect(answer.toLowerCase(), `RAG answer must come from the indexed document. Got: ${blob}`).toContain("paris");
  });

  test("cleanup", async ({ page }) => {
    test.skip(!!process.env.KEEP_FIXTURES, "KEEP_FIXTURES set: leaving fixtures for inspection.");
    await page.goto("/");
    if (assistantId) await apiCall(page, "DELETE", `/creator/assistant/delete_assistant/${assistantId}`);
    if (knowledgeStoreId && itemId) await apiCall(page, "DELETE", `/creator/knowledge-stores/${knowledgeStoreId}/content/${itemId}`);
    if (knowledgeStoreId) await apiCall(page, "DELETE", `/creator/knowledge-stores/${knowledgeStoreId}`);
    if (libraryId) await apiCall(page, "DELETE", `/creator/libraries/${libraryId}`);
  });
});
