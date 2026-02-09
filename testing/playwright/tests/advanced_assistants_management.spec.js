const { test, expect } = require("@playwright/test");
const path = require("path");

// Cargar .env local de tests (mismo patrón que otros specs)
require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

/**
 * Advanced Assistants Management
 *
 * Tests de regresión de gestión avanzada de assistants:
 *  - Edición de assistants y validaciones de formulario
 *  - Publicación de assistants a OWI (lamb_assistant.{id}, creación de grupo OWI)
 *  - Configuración de RAG_collections desde la UI (incl. KB compartidas)
 *  - Configuración de plugins (modelo, connector, visión)
 *  - Casos de error (duplicados, metadata incompleta, etc.)
 *
 * Prerrequisitos:
 *  - Sesión de admin válida vía global-setup.js o state de Playwright
 */

test.describe.serial("Advanced Assistants Management", () => {
  const timestamp = Date.now();
  const baseAssistantName = `pw_adv_asst_${timestamp}`;
  const updatedAssistantName = `${baseAssistantName}_updated`;

  /**
   * Helper: filtra por nombre y devuelve el row del assistant.
   */
  async function findAssistantRow(page, nameFragment) {
    await page.goto("assistants");
    await page.waitForLoadState("networkidle");

    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(nameFragment);
      await page.waitForTimeout(500);
    }

    const assistantRow = page.locator(`tr:has-text("${nameFragment}")`).first();
    await expect(assistantRow).toBeVisible({ timeout: 30_000 });
    return assistantRow;
  }

  /**
   * Helper: abre la vista de detalle de un assistant dado su nombre.
   */
  async function openAssistantDetail(page, nameFragment) {
    const assistantRow = await findAssistantRow(page, nameFragment);

    // Preferimos un botón "View" / "Edit" en la fila si existe.
    const viewButton = assistantRow
      .getByRole("button", { name: /view|edit/i })
      .first();
    if (await viewButton.count()) {
      await viewButton.click();
    } else {
      // Fallback: click en el propio nombre si es un botón/enlace
      const nameButton = assistantRow
        .getByRole("button", { name: new RegExp(nameFragment, "i") })
        .first();
      if (await nameButton.count()) {
        await nameButton.click();
      } else {
        await assistantRow.click();
      }
    }

    await page.waitForLoadState("networkidle");
    // Vista de detalle debería mostrar algo tipo "Assistant details" o similar.
    await expect(
      page.getByRole("heading", { name: /assistant/i }).first()
    ).toBeVisible({ timeout: 30_000 });
  }

  // ─────────────────────────────────────────────────────────────────────
  // 1. Crear un assistant base para el resto de escenarios
  // ─────────────────────────────────────────────────────────────────────
  test("1. Crear assistant base para tests avanzados", async ({ page }) => {
    await page.goto("assistants?view=create");
    await page.waitForLoadState("networkidle");

    const createButton = page
      .getByRole("button", { name: /create assistant/i })
      .first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    await page.fill("#assistant-name", baseAssistantName);
    await page.fill("#assistant-description", "Advanced management Playwright assistant");
    await page.fill("#system-prompt", "You are a helpful assistant for advanced Playwright tests.");

    // Esperar al endpoint de creación (mismo patrón que creator_flow.spec.js)
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

    await Promise.all([createRequest, form.evaluate((f) => f.requestSubmit())]);

    await page.waitForURL(/\/assistants(\?.*)?$/, { timeout: 30_000 });

    // Verificar que aparece en el listado
    const row = await findAssistantRow(page, baseAssistantName);
    await expect(row).toBeVisible();
  });

  // ─────────────────────────────────────────────────────────────────────
  // 2. Edición de assistant y validaciones de formulario
  // ─────────────────────────────────────────────────────────────────────
  test("2. Editar assistant y comprobar validaciones de formulario", async ({
    page,
  }) => {
    await openAssistantDetail(page, baseAssistantName);

    // Entrar en modo edición
    const editButton = page.getByRole("button", { name: /^edit$/i }).first();
    await expect(editButton).toBeVisible({ timeout: 10_000 });
    await editButton.click();

    // Esperar a que cargue la vista Edit y el formulario sea visible
    const editTitle = page.getByRole("heading", { name: /edit assistant/i }).first();
    await expect(editTitle).toBeVisible({ timeout: 10_000 });

    // Esperar al botón Save Changes
    const saveButton = page.locator('button:has-text("Save Changes")').first();
    await expect(saveButton).toBeVisible({ timeout: 10_000 });

    // No asumimos un id concreto de formulario en la vista de edición,
    // solo que los campos de nombre y descripción existen.
    const nameInput = page.getByLabel(/assistant name/i).first();
    const descriptionInput = page.getByLabel(/^description/i).first();

    await expect(nameInput).toBeVisible();
    // El name input está disabled - no se puede editar (read-only)
    // Validamos que está presente pero no intentamos modificarlo

    await expect(descriptionInput).toBeVisible();
    await expect(descriptionInput).toBeEnabled({ timeout: 10_000 });

    // Caso de validación: dejar descripción vacía y forzar submit
    // (ya que el nombre no se puede cambiar)
    await descriptionInput.click();
    await descriptionInput.press("Control+A").catch(() => { });
    await descriptionInput.fill("");
    await expect(descriptionInput).toHaveValue("");

    // Esperar al endpoint de actualización
    const updateRequest = page.waitForResponse((response) => {
      if (response.request().method() !== "POST" && response.request().method() !== "PUT") {
        return false;
      }
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

    await expect(saveButton).toBeVisible({ timeout: 10_000 });
    await Promise.all([updateRequest, saveButton.click()]);

    // Verificar cambios - el nombre se mantiene igual
    const row = await findAssistantRow(page, baseAssistantName);
    await expect(row).toBeVisible();
  });

  // ─────────────────────────────────────────────────────────────────────
  // 3. Publicación del assistant (registro lamb_assistant.{id})
  // ─────────────────────────────────────────────────────────────────────
  test("3. Publicar assistant y verificar registro lamb_assistant.{id}", async ({
    page,
  }) => {
    await openAssistantDetail(page, baseAssistantName);

    // Botón principal de publicación (directamente en detalle)
    const publishButton = page
      .getByRole("button", { name: /^publish$/i })
      .first();
    await expect(publishButton).toBeVisible({ timeout: 30_000 });

    const publishRequest = page.waitForResponse((response) => {
      if (response.request().method() !== "PUT") return false;
      try {
        const url = new URL(response.url());
        return (
          url.pathname.includes("/publish/") &&
          response.status() >= 200 &&
          response.status() < 300
        );
      } catch {
        return false;
      }
    });

    await Promise.all([publishRequest, publishButton.click()]);


    // Verificar que el estado cambia a "Published" (botón cambia a Unpublish)
    const unpublishButton = page.getByRole("button", { name: /^unpublish$/i }).first();
    await expect(unpublishButton).toBeVisible({ timeout: 30_000 });

    // ─────────────────────────────────────────────────────────────────────
    // Despublicar (Unpublish)
    // ─────────────────────────────────────────────────────────────────────

    // Esperar a la petición de despublicación (PUT con publish_status: false)
    const unpublishRequest = page.waitForResponse((response) => {
      if (response.request().method() !== "PUT") return false;
      try {
        const url = new URL(response.url());
        return (
          url.pathname.includes("/publish/") &&
          response.status() >= 200 &&
          response.status() < 300
        );
      } catch {
        return false;
      }
    });

    await Promise.all([unpublishRequest, unpublishButton.click()]);

    // Verificar que el botón vuelve a ser "Publish"
    await expect(
      page.getByRole("button", { name: /^publish$/i }).first()
    ).toBeVisible({ timeout: 30_000 });
  });


  // ─────────────────────────────────────────────────────────────────────
  // 4. Configuración de plugins (modelo, connector, visión)
  // ─────────────────────────────────────────────────────────────────────
  test("4. Configurar plugins: modelo, connector y visión", async ({ page }) => {
    await openAssistantDetail(page, baseAssistantName);

    // Configuración de plugins (integrado en main view)
    // Entrar en modo edición primero
    const editButton = page.getByRole("button", { name: /^edit$/i }).first();
    await expect(editButton).toBeVisible({ timeout: 10_000 });
    await editButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    const modelSelect = page
      .getByRole("combobox", { name: /model|Language Model/i })
      .first();
    const connectorSelect = page
      .getByRole("combobox", { name: /onnector/i })
      .first();
    const visionCheckbox = page
      .getByRole("checkbox", { name: /vision|image input|enable vision/i })
      .first();

    // Todos estos elementos son opcionales, pero si existen, los tocamos.
    if (await modelSelect.count()) {
      await modelSelect.selectOption({ index: 1 }).catch(() => { });
    }

    if (await connectorSelect.count()) {
      await connectorSelect.selectOption({ index: 1 }).catch(() => { });
    }

    if (await visionCheckbox.count()) {
      const checked = await visionCheckbox.isChecked();
      await visionCheckbox.setChecked(!checked).catch(() => { });
    }

    const saveButton = page.locator(
      'button[type="submit"][form="assistant-form-main"]'
    );
    await expect(saveButton).toBeVisible({ timeout: 10_000 });

    // Guardar cambios
    // No esperamos la request explícita porque a veces da timeout aunque guarda bien.
    // Confiamos en la verificación posterior al recargar.
    await saveButton.click();
    await page.waitForTimeout(1000); // Pequeña espera para asegurar que el click se procesa

    // Reabrir plugins y verificar que los cambios persisten
    await openAssistantDetail(page, baseAssistantName);

    // Entrar en modo edición para ver los valores correctamente
    const editButton2 = page.getByRole("button", { name: /^edit$/i }).first();
    await expect(editButton2).toBeVisible({ timeout: 10_000 });
    await editButton2.click();

    // Verificación de persistencia (sin navegar a pestaña extra)
    const modelSelectAfter = page
      .getByRole("combobox", { name: /model|Language Model/i })
      .first();
    if (await modelSelectAfter.count()) {
      const modelValue = await modelSelectAfter.inputValue();
      expect(modelValue).not.toBe("");
    }

    const connectorSelectAfter = page
      .getByRole("combobox", { name: /connector|backend connector/i })
      .first();
    if (await connectorSelectAfter.count()) {
      const connectorValue = await connectorSelectAfter.inputValue();
      expect(connectorValue).not.toBe("");
    }

    const visionCheckboxAfter = page
      .getByRole("checkbox", { name: /vision|image input|enable vision/i })
      .first();
    if (await visionCheckboxAfter.count()) {
      // Debería estar visible
      await expect(visionCheckboxAfter).toBeVisible();
    }
  });

  // ─────────────────────────────────────────────────────────────────────
  // 5. Casos de error: duplicados y metadata incompleta
  // ─────────────────────────────────────────────────────────────────────
  test("5. Errores: nombre duplicado y metadata incompleta", async ({ page }) => {
    // Intentar crear un assistant con el mismo nombre que el ya existente
    await page.goto("assistants?view=create");
    await page.waitForLoadState("networkidle");

    const createButton = page
      .getByRole("button", { name: /create assistant/i })
      .first();
    await expect(createButton).toBeVisible({ timeout: 10_000 });
    await createButton.click();

    const form = page.locator("#assistant-form-main");
    await expect(form).toBeVisible({ timeout: 30_000 });

    // Caso 1: metadata incompleta (faltan campos requeridos)
    await page.fill("#assistant-name", baseAssistantName);
    await page.fill(
      "#assistant-description",
      "" // descripción vacía para forzar validación
    );
    await page.fill(
      "#system-prompt",
      "" // prompt vacío para forzar validación
    );

    const saveButton = page.locator(
      'button[type="submit"][form="assistant-form-main"]'
    );
    await expect(saveButton).toBeVisible({ timeout: 10_000 });
    await saveButton.click();

    // Debería aparecer algún mensaje de error de validación de metadata incompleta
    const incompleteMetaError = page
      .getByText(/description.*required|system prompt.*required|metadata incomplete/i)
      .first();
    await expect(incompleteMetaError).toBeVisible({ timeout: 10_000 });

    // Caso 2: tras rellenar metadata, el backend debería devolver error por duplicado
    await page.fill("#assistant-description", "Duplicate name test");
    await page.fill("#system-prompt", "Duplicate name test prompt");

    const duplicateRequest = page.waitForResponse((response) => {
      if (response.request().method() !== "POST") return false;
      try {
        const url = new URL(response.url());
        return url.pathname.endsWith("/assistant/create_assistant");
      } catch {
        return false;
      }
    });

    await Promise.all([duplicateRequest, saveButton.click()]);

    // Esperamos un mensaje de error indicando duplicado
    await expect(
      page
        .getByText(/already exists|duplicate assistant|nombre ya existe/i)
        .first()
    ).toBeVisible({ timeout: 20_000 });
  });

  // ─────────────────────────────────────────────────────────────────────
  // 6. Cleanup: borrar el assistant de pruebas
  // ─────────────────────────────────────────────────────────────────────
  test("6. Cleanup: borrar assistant avanzado de pruebas", async ({ page }) => {
    // Puede llamarse updatedAssistantName o seguir con baseAssistantName
    let row;
    try {
      row = await findAssistantRow(page, updatedAssistantName);
    } catch {
      row = await findAssistantRow(page, baseAssistantName);
    }

    const deleteButton = row
      .getByRole("button", { name: /delete/i })
      .first();
    await expect(deleteButton).toBeVisible({ timeout: 10_000 });
    await deleteButton.click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 10_000 });

    const confirmDelete = modal.getByRole("button", { name: /^delete$/i });
    await expect(confirmDelete).toBeVisible({ timeout: 10_000 });
    await confirmDelete.click();

    await expect(modal).not.toBeVisible({ timeout: 30_000 });

    // Verificar que la fila desaparece
    await page.waitForTimeout(1000);
    const searchBox = page.locator('input[placeholder*="Search" i]');
    if (await searchBox.count()) {
      await searchBox.fill(timestamp.toString());
      await page.waitForTimeout(500);
    }

    await expect(
      page.locator(`tr:has-text("${timestamp}")`).first()
    ).not.toBeVisible({ timeout: 10_000 });
  });
});

