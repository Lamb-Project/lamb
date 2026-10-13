// @ts-check
/**
 * Track B — the real student journey (decision C21).
 *
 * Merged from the three throwaway `workshop_e2e*.cjs` scripts, which lived
 * outside `testDir` and so were never collected by any runner. This spec walks
 * the whole lesson against a **live stack and a real model**:
 *
 *   launch → consent → assistant → document → retrieval → tools → chat →
 *   reflection → submit → feedback
 *
 * It is NOT the regression gate. It needs a running stack, a seeded workshop
 * activity and a working LLM, so in practice it runs before a release (or on
 * `workflow_dispatch`) — the route-mocked `workshop_ui.spec.js` plus the
 * backend pytest suite are what protect every PR.
 *
 * Env:
 *   WORKSHOP_E2E=1   – required, otherwise every test is skipped
 *   WORKSHOP_URL     – the wizard URL to open, e.g.
 *                      http://localhost:9099/m/workshop/12?token=…
 *                      (seed one with `python tests/mvp_smoke.py --seed-only`)
 */
const { test, expect } = require('@playwright/test');

const ENABLED = !!process.env.WORKSHOP_E2E;
const WIZARD_URL = process.env.WORKSHOP_URL || '';
const SKIP_REASON =
  'Track B needs a live stack, a seeded workshop and a real model: set ' +
  'WORKSHOP_E2E=1 and WORKSHOP_URL (see testing/playwright/README.md).';

const DOCUMENT = {
  name: 'fractions-notes.md',
  mimeType: 'text/markdown',
  buffer: Buffer.from(
    '# Fractions\n\n' +
    'A fraction shows equal parts of a whole. In 3/4 the bottom number (4) is ' +
    'the denominator and the top number (3) is the numerator.\n\n' +
    'To simplify, divide both by their greatest common divisor: 6/8 -> 3/4.\n'
  )
};

const QUESTION = 'According to my document, what is a fraction?';

test.describe('Workshop student journey (live stack + real model)', () => {
  test.skip(!ENABLED || !WIZARD_URL, SKIP_REASON);

  test('walks the whole lesson', async ({ page }) => {
    test.setTimeout(300_000);

    // ── 1. Launch ─────────────────────────────────────────────────────────
    await page.goto(WIZARD_URL, { waitUntil: 'domcontentloaded' });

    // ── 2. Consent (only on a first launch) ───────────────────────────────
    if (page.url().includes('/workshop/consent')) {
      await expect(page.getByRole('button', { name: /start the activity|empezar|començar|hasi/i }))
        .toBeVisible();
      // The disclosure must state the three purposes, not just "build & test".
      const consentText = await page.textContent('body');
      expect(consentText.length).toBeGreaterThan(200);
      await page.getByRole('button').first().click();
      await page.waitForURL(/\/m\/workshop\//);
    }

    await expect(page.getByRole('heading', { name: /AI Workshop|Taller|Tailerra/ })).toBeVisible();

    // ── 3. Step 1: instructions → assistant ───────────────────────────────
    await page.locator('#ws-instructions').fill(
      'You are a tutor that explains fractions using only the attached notes.');
    await page.getByRole('button', { name: /Next|Siguiente|Següent|Hurrengoa/ }).click();
    await expect(page.locator('#ws-kb')).toBeVisible();

    // ── 4. Step 2: attach a document and wait for ingestion ───────────────
    await page.locator('input[type="file"]').setInputFiles(DOCUMENT);
    await expect(page.getByText(/ingested|ingerido|ingerit|sartu/i).first())
      .toBeVisible({ timeout: 120_000 });
    // The deterministic chunking facts must reach the panel (D2/C16).
    await expect(page.getByTestId('panel-document')).toBeVisible({ timeout: 60_000 });

    // ── 5. Step 3: retrieval probe ────────────────────────────────────────
    await page.getByRole('button', { name: /Next|Siguiente|Següent|Hurrengoa/ }).click();
    await page.locator('#ws-kb-query').fill(QUESTION);
    await page.getByRole('button', { name: /Test retrieval|Probar recuperación|Prova la recuperació|Probatu berreskuratzea/ })
      .click();
    // The excerpts are rendered by the shared panel, not by an inline list.
    await expect(page.getByText('Retrieved context')).toBeVisible({ timeout: 60_000 });

    // ── 6. Step 4: tools, with the payload previewed ──────────────────────
    await page.getByRole('button', { name: /Next|Siguiente|Següent|Hurrengoa/ }).click();
    await expect(page.getByTestId('panel-tools')).toBeVisible();

    // ── 7. Step 5: chat, with the request frame arriving first ────────────
    await page.getByRole('button', { name: /5\./ }).click();
    await page.locator('input[placeholder*="Ask your assistant"]').fill(QUESTION);
    await page.getByRole('button', { name: /Send|Enviar|Envia|Bidali/ }).click();

    // The panel shows what is about to be sent before the answer lands (D1).
    await expect(page.getByTestId('panel-request')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('panel-rag-mode')).toContainText(/on|activada|piztuta/i);
    // …and the answer eventually arrives.
    await expect(page.locator('div.bg-gray-100').first()).not.toBeEmpty({ timeout: 120_000 });

    // ── 8. A/B: run the same question with the knowledge base off ─────────
    await page.getByTestId('rag-mode-off').click();
    await page.locator('input[placeholder*="Ask your assistant"]').fill(QUESTION);
    await page.getByRole('button', { name: /Send|Enviar|Envia|Bidali/ }).click();
    await expect(page.getByTestId('panel-rag-mode')).toContainText(/off|desactivada|itzalita/i);
    await expect(page.getByTestId('rag-comparison')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('comparison-on')).toBeVisible();
    await expect(page.getByTestId('comparison-off')).toBeVisible();

    // ── 9. Reflection (the three guided questions) ────────────────────────
    await page.getByTestId('reflection-q1').fill('I asked it to explain fractions from my notes.');
    await page.getByTestId('reflection-q2').fill('With the knowledge base on it cited my notes; with it off it generalised.');
    await page.getByTestId('reflection-q3').fill('I would add more examples to the notes.');

    // ── 10. Submit + feedback ─────────────────────────────────────────────
    await page.getByRole('button', { name: /Submit workshop|Enviar taller|Envia el taller|Tailerra bidali/ })
      .click();

    // Either rubric feedback arrives, or the activity has no rubric — both are
    // valid end states; a stuck spinner is not.
    await expect(
      page.getByText(/formative feedback|No rubric|comentarios|comentaris|iritzi/i).first()
    ).toBeVisible({ timeout: 120_000 });
  });
});
