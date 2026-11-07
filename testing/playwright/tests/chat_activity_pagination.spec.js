const { test, expect } = require('@playwright/test');
const fs = require('fs');

// Seed dedicated, retained synthetic assistants; never run against ordinary chats.
// Fixture: {cases:[{assistant_id,name,expected:[{id,title,stamp}]}]}.
const fixturePath = process.env.PAGINATION_FIXTURE;
test.describe('Chat activity pagination regression', () => {
  test.skip(!fixturePath, 'Set PAGINATION_FIXTURE to the synthetic fixture inventory');
  test('page buttons, page sizes and API traversal preserve the complete inventory', async ({ page, request }) => {
    const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
    const auth = JSON.parse(fs.readFileSync(process.env.PAGINATION_AUTH, 'utf8'));
    await page.goto('/');
    if (await page.locator('#email').isVisible()) {
      await page.locator('#email').fill(auth.admin_email);
      await page.locator('#password').fill(auth.admin_password);
      await page.locator('button[type=submit]').click();
    }
    await page.waitForFunction(() => !!localStorage.getItem('userToken'));
    const token = await page.evaluate(() => localStorage.getItem('userToken'));
    const headers = { Authorization: `Bearer ${token}` };
    for (const fixtureCase of fixture.cases) {
      const expected = fixtureCase.expected;
      const endpoint = `/creator/analytics/assistant/${fixtureCase.assistant_id}/chats`;
      for (const size of [10, 20, 50, 100]) {
        const seen = [];
        const totalPages = Math.ceil(expected.length / size);
        for (let n = 1; n <= totalPages + 1; n++) {
          const response = await request.get(`${endpoint}?page=${n}&per_page=${size}`, { headers });
          expect(response.ok()).toBeTruthy();
          const result = await response.json();
          expect(result.total).toBe(expected.length);
          expect(result.total_pages).toBe(totalPages);
          expect(result.chats.map(c => c.id)).toEqual(expected.slice((n - 1) * size, n * size).map(c => c.id));
          seen.push(...result.chats.map(c => c.id));
        }
        expect(seen).toEqual(expected.map(c => c.id));
      }
      await page.goto(`/assistants?view=detail&id=${fixtureCase.assistant_id}&aacTab=activity`);
      const rows = page.locator('tbody tr').filter({ hasText: 'PaginationQA' });
      const titles = () => rows.locator('td:nth-child(4)').allTextContents();
      async function check(start, count) {
        await expect(rows).toHaveCount(Math.min(count, expected.length - start));
        await expect.poll(async () => (await titles()).map(t => t.trim())).toEqual(expected.slice(start, start + count).map(c => c.title));
      }
      await check(0, 20);
      await page.getByRole('button', { name: 'Page 2', exact: true }).click();
      await check(20, 20);
      await page.getByRole('button', { name: 'Previous page', exact: true }).click();
      await check(0, 20);
      await page.getByRole('button', { name: 'Next page', exact: true }).click();
      await check(20, 20);
      // Changing page size on page 2 resets to page 1.
      await page.locator('#items-per-page').selectOption('50');
      await check(0, 50);
      await page.locator('#items-per-page').selectOption('10');
      await check(0, 10);
      await page.getByRole('button', { name: 'Last page', exact: true }).click();
      await check(Math.floor((expected.length - 1) / 10) * 10, 10);
      await expect(page.getByRole('button', { name: 'Next page', exact: true })).toBeDisabled();
      await rows.last().click();
      await expect(page.getByText('TAIL_SENTINEL_ORCHID', { exact: false })).toBeVisible();
    }
  });
});
