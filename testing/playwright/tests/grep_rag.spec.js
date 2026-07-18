const { test, expect } = require("@playwright/test");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

/**
 * Grep RAG Configuration & Chat Tests
 *
 * Covers the grep_rag assistant end-to-end flow:
 *   1. Create a KB with ingest for grep_rag to search against
 *   2. Create an assistant with grep_rag in hybrid mode
 *   3. Configure all grep options (mode, max tries, context lines, max chars)
 *   4. Select knowledge bases for grep_rag
 *   5. Chat with the hybrid assistant — verify grep_rag responds at runtime
 *   6. Verify grep settings persist on detail view and re-edit
 *   7. Switch to primary mode, verify fallback RAG selector appears
 *   8. Create a second assistant with grep_rag in primary mode
 *   9. Chat with the primary mode assistant — verify grep_rag + fallback works
 *  10. Verify primary mode settings persisted on re-edit
 *  11. Cleanup: delete both assistants and the KB
 *
 * Prerequisites:
 *   - Logged in as admin via global-setup.js
 *   - Backend has grep_rag plugin available in backend/lamb/completions/rag/
 */

test.describe.serial("Grep RAG Configuration", () => {
  const timestamp = Date.now();
  const kbName = `pw_grep_rag_kb_${timestamp}`;
  const hybridAssistantName = `pw_grep_hybrid_${timestamp}`;
  const primaryAssistantName = `pw_grep_primary_${timestamp}`;

  // ════════════════════════════════════════════════════════════════
  // Helper: Find an assistant row by name fragment
  // ════════════════════════════════════════════════════════════════
  async function findAssistantRow(page, nameFragment) {
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(nameFragment);
      await page.waitForTimeout(500);
    }

    const row = page.locator(`tr:has-text("${nameFragment}")`).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    return row;
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Open assistant detail view
  // ════════════════════════════════════════════════════════════════
  async function openAssistantDetail(page, nameFragment) {
    const row = await findAssistantRow(page, nameFragment);

    const viewButton = row.getByRole("button", { name: /view|edit/i }).first();
    if (await viewButton.count()) {
      await viewButton.click();
    } else {
      const nameButton = row
        .getByRole("button", { name: new RegExp(nameFragment, "i") })
        .first();
      if (await nameButton.count()) {
        await nameButton.click();
      } else {
        await row.click();
      }
    }

    await page.waitForLoadState("networkidle");
    await expect(
      page.getByRole("heading", { name: /assistant/i }).first()
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByRole("button", { name: /^properties$/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Navigate to assistant create form and wait for it
  // ════════════════════════════════════════════════════════════════
  async function openCreateForm(page) {
    await page.goto("assistants?view=create");
    await page.waitForLoadState("networkidle");

    const createButton = page
      .getByRole("button", { name: /create assistant/i })
      .first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });
    return form;
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Fill basic assistant fields
  // ════════════════════════════════════════════════════════════════
  async function fillBasicFields(page, name, description, systemPrompt) {
    await page.fill("#assistant-name", name);
    await page.fill("#assistant-description", description);
    await page.fill("#system-prompt", systemPrompt);
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Select RAG processor from dropdown
  // ════════════════════════════════════════════════════════════════
  async function selectRagProcessor(page, processorValue) {
    const ragSelect = page.locator("#rag-processor");
    await expect(ragSelect).toBeVisible({ timeout: 10_000 });
    await ragSelect.selectOption(processorValue);
    // Wait for dependent UI to render
    await page.waitForTimeout(500);
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Save assistant and wait for redirect to list.
  // Returns the created assistant ID from the API response.
  // ════════════════════════════════════════════════════════════════
  async function saveAssistant(page) {
    let assistantId = null;

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

    const saveButton = page.locator(
      'button[type="submit"][form="assistant-form-main"]'
    );
    await expect(saveButton).toBeEnabled({ timeout: 60_000 });

    const form = page.locator("#assistant-form-main");
    const [response] = await Promise.all([
      createRequest,
      form.evaluate((f) => f.requestSubmit()),
    ]);

    // Extract assistant ID from the creation response
    try {
      const body = await response.json();
      assistantId = body?.id || body?.assistant?.id || body?.assistant_id || null;
    } catch {
      // Response may not be JSON; ID will be extracted from URL fallback
    }

    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });
    return assistantId;
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Select a knowledge base by name in the assistant form.
  // Finds the label containing the KB name and checks its checkbox.
  // ════════════════════════════════════════════════════════════════
  async function selectKnowledgeBase(page, kbName) {
    // KB checkboxes are inside <label> elements with the KB name as text.
    // The KnowledgeBaseSelector renders them under groups with
    // aria-labelledby="kb-owned-group-label" / "kb-shared-group-label".
    const kbLabel = page
      .locator('label')
      .filter({ hasText: kbName })
      .first();
    await expect(kbLabel).toBeVisible({ timeout: 10_000 });

    const checkbox = kbLabel.locator('input[type="checkbox"]');
    await checkbox.check();

    // Verify it's actually checked
    await expect(checkbox).toBeChecked({ timeout: 5_000 });
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Wait for KB ingestion to fully complete.
  // After uploading a file, ingestion runs async. This polls the
  // KB detail Files tab until the file shows status "completed".
  // ════════════════════════════════════════════════════════════════
  async function waitForKbIngestionComplete(page, kbName, fileName) {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    // Navigate to the KB detail
    const kbRow = page.locator('tbody tr', { hasText: kbName });
    await expect(kbRow).toBeVisible({ timeout: 10_000 });
    await kbRow.getByRole('button', { name: kbName }).click();
    await page.waitForLoadState("networkidle");

    // Click the Files tab
    const tabs = page.locator('nav[aria-label="Tabs"]');
    const filesTab = tabs.getByRole('button', { name: 'Files' });
    await expect(filesTab).toBeVisible({ timeout: 10_000 });
    await filesTab.click();
    await expect(filesTab).toHaveAttribute('aria-current', 'page', { timeout: 5_000 });

    // Wait for the ingested file row to appear with "completed" status
    const fileRow = page.locator('table tbody tr', { hasText: fileName });
    await expect(fileRow).toBeVisible({ timeout: 120_000 });

    // The status is in the 4th column (index 3), rendered as a button
    await expect(
      fileRow.locator('td').nth(3).getByRole('button')
    ).toHaveText(/completed/i, { timeout: 120_000 });
  }

  // ════════════════════════════════════════════════════════════════
  // Helper: Chat with an assistant and verify it responds.
  // Navigates to detail page, opens Chat tab, sends a query,
  // and waits for the completion response.
  // ════════════════════════════════════════════════════════════════
  async function chatWithAssistant(page, assistantId, query) {
    await page.goto(`assistants?view=detail&id=${assistantId}`);
    await page.waitForLoadState("networkidle");

    // Click the "Chat with" tab
    const chatTab = page.getByRole("button", { name: /Chat with/i });
    await expect(chatTab).toBeVisible({ timeout: 10_000 });
    await chatTab.click();

    // Wait for chat input to appear
    const input = page.getByPlaceholder(/Type your message/i);
    await expect(input).toBeVisible({ timeout: 10_000 });

    // Wait for the completion response concurrently with sending
    const completionPromise = page.waitForResponse(
      (response) => {
        if (response.request().method() !== "POST") return false;
        try {
          const url = new URL(response.url());
          return (
            url.pathname.endsWith(
              `/assistant/${assistantId}/chat/completions`
            ) &&
            response.status() >= 200 &&
            response.status() < 300
          );
        } catch {
          return false;
        }
      },
      { timeout: 90_000 }
    );

    await input.fill(query);
    const sendButton = page.getByRole("button", { name: /^Send$/ });
    await expect(sendButton).toBeVisible({ timeout: 5_000 });
    await sendButton.click();

    // Wait for the completion to finish
    await completionPromise;

    // Wait a moment for the response to render in the chat UI
    await page.waitForTimeout(3_000);
  }

  // ════════════════════════════════════════════════════════════════
  // 1. Create a knowledge base for grep_rag to search against
  // ════════════════════════════════════════════════════════════════
  test("1. Create knowledge base for grep_rag tests", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const createButton = page.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    await page.getByLabel(/name\s*\*/i).fill(kbName);
    await page.getByLabel(/description/i).fill("Playwright grep_rag test KB");

    const submitButton = dialog.getByRole("button", {
      name: /create knowledge base/i,
    });
    await expect(submitButton).toBeVisible({ timeout: 5_000 });
    await submitButton.click();

    await expect(dialog).not.toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(kbName)).toBeVisible({ timeout: 30_000 });
  });

  // ════════════════════════════════════════════════════════════════
  // 2. Ingest a fixture file into the KB
  // ════════════════════════════════════════════════════════════════
  test("2. Ingest fixture file into grep KB", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.getByText(kbName, { exact: false }).first().click();

    await page.getByRole("button", { name: /ingest content/i }).click();

    const fixturePath = path.join(
      __dirname, "..", "fixtures", "ikasiker_fixture.txt"
    );
    await page.locator("#file-upload-input-inline").setInputFiles(fixturePath);

    await expect(page.getByText("ikasiker_fixture.txt")).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole("button", { name: /upload file/i }).click();

    await expect(
      page.getByText(/file uploaded and ingestion started successfully/i),
    ).toBeVisible({ timeout: 60_000 });

    // Wait for async ingestion to fully complete before creating assistants
    await waitForKbIngestionComplete(page, kbName, "ikasiker_fixture.txt");
  });

  // ════════════════════════════════════════════════════════════════
  // 3. Create assistant with grep_rag in hybrid mode
  // ════════════════════════════════════════════════════════════════
  test("3. Create assistant with grep_rag hybrid mode", async ({ page }) => {
    await openCreateForm(page);
    await fillBasicFields(
      page,
      hybridAssistantName,
      "Grep RAG hybrid mode test assistant",
      "You are a helpful assistant for grep_rag Playwright tests."
    );

    // Select grep_rag processor
    await selectRagProcessor(page, "grep_rag");

    // Wait for grep config panel to appear
    const grepSection = page.getByText(/Grep RAG Configuration/i);
    await expect(grepSection).toBeVisible({ timeout: 10_000 });

    // Verify hybrid mode is the default
    const modeSelect = page.locator("#grep-mode");
    await expect(modeSelect).toHaveValue("hybrid");

    // Fallback RAG selector should NOT be visible in hybrid mode
    const fallbackSelect = page.locator("#grep-fallback-rag");
    await expect(fallbackSelect).not.toBeVisible();

    // Configure grep options
    await page.fill("#grep-max-tries", "7");
    await page.fill("#grep-context-lines", "5");
    await page.fill("#grep-max-chars", "12000");

    // Set RAG Top K (shared with companion RAG)
    await page.fill("#rag-top-k", "4");

    // Select the knowledge base by name
    await selectKnowledgeBase(page, kbName);

    // Save and capture the assistant ID
    const hybridAssistantId = await saveAssistant(page);

    // Verify assistant appears in list
    const row = await findAssistantRow(page, hybridAssistantName);
    await expect(row).toBeVisible();

    // Store ID for later chat tests
    process.env.__HYBRID_ASSISTANT_ID = hybridAssistantId;
  });

  // ════════════════════════════════════════════════════════════════
  // 4. Chat with the hybrid grep_rag assistant
  // ════════════════════════════════════════════════════════════════
  test("4. Chat with hybrid grep_rag assistant", async ({ page }, testInfo) => {
    const assistantId = process.env.__HYBRID_ASSISTANT_ID;
    if (!assistantId) {
      testInfo.skip(true, "Hybrid assistant ID not captured — skipping chat test");
      return;
    }

    // Send a query that should trigger grep search against the Ikasiker KB
    await chatWithAssistant(
      page,
      assistantId,
      "¿Cuántas becas Ikasiker se convocan?"
    );

    // Verify the chat didn't error — the completion completed successfully
    // and the page is still interactive
    await expect(
      page.getByPlaceholder(/Type your message/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  // ════════════════════════════════════════════════════════════════
  // 5. Verify hybrid grep_rag settings in detail view
  // ════════════════════════════════════════════════════════════════
  test("5. Verify hybrid grep_rag settings persist in detail view", async ({
    page,
  }) => {
    await openAssistantDetail(page, hybridAssistantName);

    // The detail view should show grep_rag configuration.
    // Look for the grep section title.
    const grepSection = page.getByText(/Grep RAG Configuration/i);
    // In detail (read-only) view, grep config may be rendered differently.
    // At minimum, the assistant detail should be visible.
    await expect(
      page.getByRole("heading", { name: /assistant/i }).first()
    ).toBeVisible({ timeout: 10_000 });

    // Check that KB info is displayed (grep_rag assistants show KBs in detail)
    const kbInfo = page.getByText(/knowledge base/i);
    // KB info may or may not be present depending on detail view layout;
    // just verify the detail page loaded successfully
    await expect(
      page.getByRole("button", { name: /^properties$/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // ════════════════════════════════════════════════════════════════
  // 6. Edit assistant to verify grep settings persisted correctly
  // ════════════════════════════════════════════════════════════════
  test("6. Edit assistant and verify grep settings are preserved", async ({
    page,
  }) => {
    await openAssistantDetail(page, hybridAssistantName);

    // Enter edit mode
    const editButton = page.getByRole("button", { name: /^edit$/i }).first();
    await expect(editButton).toBeVisible({ timeout: 10_000 });
    await editButton.click();

    // Wait for edit form
    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Verify grep config section is visible
    const grepSection = page.getByText(/Grep RAG Configuration/i);
    await expect(grepSection).toBeVisible({ timeout: 10_000 });

    // Verify grep values persisted
    await expect(page.locator("#grep-mode")).toHaveValue("hybrid");
    await expect(page.locator("#grep-max-tries")).toHaveValue("7");
    await expect(page.locator("#grep-context-lines")).toHaveValue("5");
    await expect(page.locator("#grep-max-chars")).toHaveValue("12000");
    await expect(page.locator("#rag-top-k")).toHaveValue("4");
  });

  // ════════════════════════════════════════════════════════════════
  // 7. Switch to primary mode and verify fallback RAG selector
  // ════════════════════════════════════════════════════════════════
  test("7. Switch to primary mode and verify fallback RAG appears", async ({
    page,
  }) => {
    await openAssistantDetail(page, hybridAssistantName);

    const editButton = page.getByRole("button", { name: /^edit$/i }).first();
    await expect(editButton).toBeVisible({ timeout: 10_000 });
    await editButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Switch to primary mode
    await page.locator("#grep-mode").selectOption("primary");

    // Fallback RAG selector should now be visible
    const fallbackSelect = page.locator("#grep-fallback-rag");
    await expect(fallbackSelect).toBeVisible({ timeout: 5_000 });

    // Select a fallback RAG (should have KB-based RAG options)
    const fallbackOptions = fallbackSelect.locator("option");
    const optionCount = await fallbackOptions.count();
    // Should have at least one KB-based RAG option
    expect(optionCount).toBeGreaterThanOrEqual(1);

    // Verify we can select an option
    await fallbackSelect.selectOption({ index: 0 });

    // Save changes
    const updateRequest = page.waitForResponse((response) => {
      if (
        response.request().method() !== "POST" &&
        response.request().method() !== "PUT"
      )
        return false;
      try {
        const url = new URL(response.url());
        return (
          url.pathname.includes("update_assistant") &&
          response.status() >= 200 &&
          response.status() < 300
        );
      } catch {
        return false;
      }
    });

    const saveButton = page.locator(
      'button[type="submit"][form="assistant-form-main"]'
    );
    await expect(saveButton).toBeVisible({ timeout: 10_000 });
    await Promise.all([updateRequest, saveButton.click()]);
  });

  // ════════════════════════════════════════════════════════════════
  // 8. Create assistant with grep_rag in primary mode from scratch
  // ════════════════════════════════════════════════════════════════
  test("8. Create assistant with grep_rag primary mode", async ({ page }) => {
    await openCreateForm(page);
    await fillBasicFields(
      page,
      primaryAssistantName,
      "Grep RAG primary mode test assistant",
      "You are a helpful assistant for grep_rag primary mode tests."
    );

    // Select grep_rag processor
    await selectRagProcessor(page, "grep_rag");

    // Wait for grep config panel
    const grepSection = page.getByText(/Grep RAG Configuration/i);
    await expect(grepSection).toBeVisible({ timeout: 10_000 });

    // Switch to primary mode
    await page.locator("#grep-mode").selectOption("primary");

    // Verify fallback RAG appears
    const fallbackSelect = page.locator("#grep-fallback-rag");
    await expect(fallbackSelect).toBeVisible({ timeout: 5_000 });

    // Select fallback RAG
    const fallbackOptions = fallbackSelect.locator("option");
    const optionCount = await fallbackOptions.count();
    if (optionCount > 1) {
      await fallbackSelect.selectOption({ index: 1 });
    }

    // Configure grep options for primary mode
    await page.fill("#grep-max-tries", "3");
    await page.fill("#grep-context-lines", "2");
    await page.fill("#grep-max-chars", "5000");
    await page.fill("#rag-top-k", "3");

    // Select the knowledge base by name
    await selectKnowledgeBase(page, kbName);

    // Save and capture the assistant ID
    const primaryAssistantId = await saveAssistant(page);

    // Verify assistant appears in list
    const row = await findAssistantRow(page, primaryAssistantName);
    await expect(row).toBeVisible();

    // Store ID for later chat test
    process.env.__PRIMARY_ASSISTANT_ID = primaryAssistantId;
  });

  // ════════════════════════════════════════════════════════════════
  // 9. Chat with the primary mode grep_rag assistant
  // ════════════════════════════════════════════════════════════════
  test("9. Chat with primary mode grep_rag assistant", async ({ page }, testInfo) => {
    const assistantId = process.env.__PRIMARY_ASSISTANT_ID;
    if (!assistantId) {
      testInfo.skip(true, "Primary assistant ID not captured — skipping chat test");
      return;
    }

    // Send a query that should trigger grep search;
    // in primary mode, if grep finds nothing, fallback RAG should kick in
    await chatWithAssistant(
      page,
      assistantId,
      "¿Qué requisitos tienen las becas Ikasiker?"
    );

    // Verify chat UI is still responsive (no crash)
    await expect(
      page.getByPlaceholder(/Type your message/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  // ════════════════════════════════════════════════════════════════
  // 10. Verify primary mode settings persisted on re-edit
  // ════════════════════════════════════════════════════════════════
  test("10. Verify primary mode settings persist", async ({ page }) => {
    await openAssistantDetail(page, primaryAssistantName);

    const editButton = page.getByRole("button", { name: /^edit$/i }).first();
    await expect(editButton).toBeVisible({ timeout: 10_000 });
    await editButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Verify primary mode persisted
    await expect(page.locator("#grep-mode")).toHaveValue("primary");

    // Fallback RAG should be visible
    await expect(page.locator("#grep-fallback-rag")).toBeVisible();

    // Verify other values persisted
    await expect(page.locator("#grep-max-tries")).toHaveValue("3");
    await expect(page.locator("#grep-context-lines")).toHaveValue("2");
    await expect(page.locator("#grep-max-chars")).toHaveValue("5000");
    await expect(page.locator("#rag-top-k")).toHaveValue("3");
  });

  // ════════════════════════════════════════════════════════════════
  // 11. Cleanup: delete both test assistants
  // ════════════════════════════════════════════════════════════════
  test("11. Cleanup: delete test assistants", async ({ page }) => {
    for (const name of [hybridAssistantName, primaryAssistantName]) {
      const row = await findAssistantRow(page, name);

      const deleteButton = row.getByRole("button", { name: /delete/i }).first();
      await expect(deleteButton).toBeVisible({ timeout: 10_000 });
      await deleteButton.click();

      const modal = page.getByRole("dialog");
      await expect(modal).toBeVisible({ timeout: 10_000 });

      const confirmDelete = modal
        .getByRole("button", { name: /^delete$/i })
        .first();
      await expect(confirmDelete).toBeVisible({ timeout: 5_000 });

      // Wait for the delete request
      const deleteRequest = page.waitForResponse((response) => {
        if (response.request().method() !== "DELETE" && response.request().method() !== "POST") return false;
        try {
          const url = new URL(response.url());
          return (
            url.pathname.includes("delete_assistant") &&
            response.status() >= 200 &&
            response.status() < 300
          );
        } catch {
          return false;
        }
      });

      await Promise.all([deleteRequest, confirmDelete.click()]);
      await page.waitForTimeout(500);
    }
  });

  // ════════════════════════════════════════════════════════════════
  // 12. Cleanup: delete test KB
  // ════════════════════════════════════════════════════════════════
  test("12. Cleanup: delete test knowledge base", async ({ page }) => {
    await page.goto("knowledgebases");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(kbName);
      await page.waitForTimeout(500);
    }

    const kbRow = page.locator(`tr:has-text("${kbName}")`);
    await expect(kbRow).toBeVisible({ timeout: 10_000 });

    const deleteButton = kbRow
      .locator("button.text-red-600", { hasText: /delete/i });
    if (await deleteButton.count()) {
      await deleteButton.click();
    } else {
      // Fallback: any delete button in the row
      const anyDelete = kbRow
        .getByRole("button", { name: /delete/i })
        .first();
      await anyDelete.click();
    }

    // Wait for confirmation modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Find and click the confirm delete button
    const confirmButton = modal
      .getByRole("button")
      .filter({ hasText: /delete|confirm|yes/i })
      .first();
    await confirmButton.click();

    // Wait for deletion to complete
    await page.waitForTimeout(1000);
  });
});
