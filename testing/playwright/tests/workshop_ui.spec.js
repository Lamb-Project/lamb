// @ts-check
/**
 * Track A — CI gate for the student workshop UI (decision C21).
 *
 * Every backend call is intercepted with `page.route`, so this spec needs no
 * model, no KB server and no seeded activity: it runs on any PR. It asserts the
 * things a unit test cannot see — that the *rendered* workshop shell has no
 * Creator chrome, that the observation panel is present from step 2 (not only
 * after chatting), that the language chain works, and that the A/B switch
 * really changes what the page shows.
 *
 * The real-model journey lives in `workshop_student_journey.spec.js`
 * (track B, `WORKSHOP_E2E=1`).
 */
const { test, expect } = require('@playwright/test');

const ACTIVITY_ID = '7';
const SESSION_ID = 'ws-7-70-1800000000';

/** Build an unsigned JWT the page can decode (it never verifies signatures). */
function makeToken(payload) {
  const b64 = (obj) =>
    Buffer.from(JSON.stringify(obj))
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  const now = Math.floor(Date.now() / 1000);
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({
    scope: 'workshop_student',
    session_id: SESSION_ID,
    activity_id: Number(ACTIVITY_ID),
    email: 'student@lamb-lti.local',
    organization_id: 1,
    iat: now,
    // Long-lived on purpose: the background renewal must not fire during the
    // test (it would add an unasserted /refresh call).
    exp: now + 3600
  })}.signature`;
}

const BUILD_STATE = {
  currentStep: 2,
  instructions: 'You explain fractions step by step.',
  attachedFileMeta: { name: 'fractions.md', path: 'file-1' },
  attachedFilePath: 'file-1',
  documentStatus: 'completed',
  selectedKbId: 'kb-1',
  kbCollection: 'kb-1',
  selectedTools: ['calculator'],
  reflectionAnswers: { q1: '', q2: '', q3: '' },
  ragMode: 'on',
  obsHistory: [],
  observations: [],
  chatMessages: []
};

const DOC_FILES = {
  success: true,
  kb_id: 'kb-1',
  document_name: 'fractions.md',
  document_status: 'completed',
  count: 1,
  files: [
    {
      original_filename: 'fractions.md',
      document_count: 45,
      file_size: 2048,
      status: 'completed',
      plugin_params: { chunk_size: 1000, chunk_overlap: 200 }
    }
  ]
};

/**
 * Intercept every workshop API call the page may make.
 * @param {import('@playwright/test').Page} page
 * @param {{buildState?: any, chatFrames?: string[], kbProbe?: any, calls?: string[]}} [options]
 *   `kbProbe` is the body of `POST …/kb` (step 3's test retrieval); `calls`
 *   collects `"METHOD /path"` for every non-GET request so a test can assert
 *   what the page sent.
 */
async function mockWorkshopApi(page, options = {}) {
  const buildState = options.buildState || BUILD_STATE;

  await page.route('**/lamb/v1/workshop/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method !== 'GET' && options.calls) {
      options.calls.push(`${method} ${new URL(url).pathname.replace(/^.*\/workshop/, '')}`);
    }

    if (method === 'POST' && options.kbProbe && new URL(url).pathname.endsWith('/kb')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(options.kbProbe)
      });
      return;
    }

    if (url.includes('/chat')) {
      const frames = options.chatFrames || [];
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
        body: frames.join('')
      });
      return;
    }

    if (url.includes('/doc/files')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DOC_FILES) });
      return;
    }

    if (url.includes('/evaluation')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ configured: false, evaluation: null })
      });
      return;
    }

    if (url.includes('/refresh')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, token: makeToken({}), expires_in: 1800 })
      });
      return;
    }

    // Session restore (GET) and every other workshop call.
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: SESSION_ID,
          activity_id: Number(ACTIVITY_ID),
          assistant_id: 42,
          status: 'in_progress',
          saved_chat: null,
          reflection: null,
          build_state: buildState,
          kb_id: 'kb-1',
          document_file_id: 'file-1',
          document_name: 'fractions.md',
          document_status: 'completed'
        })
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"success":true}' });
  });
}

/** @param {import('@playwright/test').Page} page @param {string} [query] */
async function openWizard(page, query = '') {
  const token = makeToken({});
  await page.goto(`/m/workshop/${ACTIVITY_ID}?token=${token}${query}`);
  // With `?lang=` the title may already be translated on first paint (the
  // bundle is cached once the dev server is warm), so match the heading by
  // role rather than by its English text.
  const title = query.includes('lang=')
    ? page.getByRole('heading', { level: 1 })
    : page.getByRole('heading', { name: 'AI Workshop' });
  await expect(title).toBeVisible();
}

test.describe('Workshop student UI (route-mocked)', () => {
  test.beforeEach(async ({ page }) => {
    await mockWorkshopApi(page);
  });

  test('shows no Creator navigation on a workshop route', async ({ page }) => {
    await openWizard(page);

    // The Creator chrome (assistants, knowledge bases, account menu) is a set
    // of dead ends for a workshop principal: the student has no LAMB session.
    await expect(page.getByRole('link', { name: /Assistants/i })).toHaveCount(0);
    await expect(page.getByRole('link', { name: /Knowledge [Bb]ases/i })).toHaveCount(0);
    // The student shell offers language switching instead.
    await expect(page.getByTestId('workshop-locale-switcher')).toBeVisible();
  });

  test('renders the observation panel at step 2, before any chat', async ({ page }) => {
    await openWizard(page);

    // Step 2 of the mocked build state: the panel is already there, carrying
    // the deterministic chunking facts of the uploaded document (D2/C16).
    await expect(page.getByText('What your assistant received')).toBeVisible();
    await expect(page.getByTestId('panel-document')).toBeVisible();
    await expect(page.getByText('How your document was split')).toBeVisible();
    await expect(page.getByText(/45 chunks/)).toBeVisible();
    await expect(page.getByText(/chunk size 1000/)).toBeVisible();
  });

  test('follows the LMS language and lets the student switch', async ({ page }) => {
    await openWizard(page, '&lang=eu');

    // `?lang=` (from launch_presentation_locale) wins the chain. Locale bundles
    // load lazily, so the first paint can still be English while `eu.json` is
    // fetched — hence the generous timeout (a cold dev server is slow).
    await expect(page.getByRole('button', { name: /Argibideak/ }))
      .toBeVisible({ timeout: 30_000 });

    // …and the student can correct it in class.
    await page.getByTestId('workshop-locale-switcher').selectOption('es');
    await expect(page.getByRole('button', { name: /Instrucciones/ }))
      .toBeVisible({ timeout: 30_000 });
  });

  test('step 3 shows what the test question retrieved in the panel', async ({ page }) => {
    await mockWorkshopApi(page, {
      buildState: { ...BUILD_STATE, currentStep: 3 },
      kbProbe: {
        success: true,
        kb_id: 'kb-1',
        query: 'How do I simplify 6/8?',
        count: 1,
        results: [
          { similarity: 0.7008, data: 'Divide both numbers by their GCD: 6/8 = 3/4.' }
        ]
      }
    });
    await openWizard(page);

    // Nothing has been asked yet, so there is no probe section.
    await expect(page.getByTestId('panel-probe')).toHaveCount(0);

    await page.locator('#ws-kb-query').fill('How do I simplify 6/8?');
    await page.getByRole('button', { name: /test retrieval/i }).click();

    // The response used to be stored but never rendered, so the panel stayed blank.
    const probe = page.getByTestId('panel-probe');
    await expect(probe).toBeVisible();
    await expect(probe).toContainText('How do I simplify 6/8?');
    await expect(probe).toContainText('0.701');
    await expect(probe).toContainText('Divide both numbers by their GCD');
  });

  test('step 2 Remove deletes the document on the server before clearing it', async ({ page }) => {
    /** @type {string[]} */
    const calls = [];
    await mockWorkshopApi(page, { calls });
    await openWizard(page);

    // The mocked session restores at step 2 with a document attached.
    await page.getByRole('button', { name: 'Remove' }).click();

    // Without this the session still holds the document and the next upload is
    // refused (429), even though the browser looked empty.
    await expect(page.locator('input[type=file]')).toBeVisible();
    expect(calls).toContain('DELETE /sessions/' + SESSION_ID + '/assistant/42/doc');
  });

  test('step 5 renders the A/B switch and applies the chosen mode', async ({ page }) => {
    await mockWorkshopApi(page, {
      buildState: {
        ...BUILD_STATE,
        currentStep: 5,
        chatMessages: [{ role: 'user', content: 'What is a fraction?' }]
      },
      chatFrames: [
        `data: ${JSON.stringify({
          type: 'observability',
          data: {
            phase: 'request',
            rag_mode: 'off',
            system_instructions: 'You explain fractions.',
            rag_context: '',
            retrieved_sources: [],
            request_body: { model: 'gpt-4o-mini', tools: [], messages: [] }
          }
        })}\n\n`,
        'data: {"choices":[{"delta":{"content":"A fraction is part of a whole."}}]}\n\n',
        'data: [DONE]\n\n'
      ]
    });

    // Re-open with the step-5 build state (the beforeEach mock is overridden).
    await openWizard(page);

    const on = page.getByTestId('rag-mode-on');
    const off = page.getByTestId('rag-mode-off');
    await expect(on).toBeVisible();
    await expect(off).toBeVisible();
    await expect(on).toHaveAttribute('aria-pressed', 'true');

    // Turn the knowledge base off, then chat: the panel must say so.
    await off.click();
    await expect(off).toHaveAttribute('aria-pressed', 'true');
    await page.getByPlaceholder(/Ask your assistant/).fill('What is a fraction?');
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(page.getByTestId('panel-rag-mode')).toContainText(
      'Knowledge base off');
    await expect(page.getByTestId('panel-request')).toBeVisible();
    // The answer lands in both the chat bubble and the comparison column —
    // the latter is the point of D3: the same question, both modes, side by side.
    await expect(page.getByText('A fraction is part of a whole.').first()).toBeVisible();
    await expect(page.getByTestId('rag-comparison')).toBeVisible();
    await expect(page.getByTestId('comparison-off')).toBeVisible();
  });
});
