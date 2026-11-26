import '@testing-library/jest-dom/vitest';
import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { initI18n, locale, waitLocale } from '$lib/i18n.js';
import Setup from './+page.svelte';

vi.mock('$app/stores', async () => {
  const { writable } = await import('svelte/store');
  return { page: writable({ url: new URL('http://localhost/m/chat/setup?token=synthetic-launch') }) };
});

it('renders the activity picker before translations load, then translates its name', async () => {
  await locale.set(null);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    modules: [{ name: 'file_evaluation', display_name: 'Supervised Assessment', requires_assistants: true }],
    org_modules: { 9: ['file_evaluation'] },
    org_names: { 9: 'Synthetic university' },
    orgs_with_assistants: { 9: [{ id: 1, name: 'Synthetic evaluator', rubric_eval_ready: true }] },
    modules_fields: {}, creator_access: []
  }) }));
  render(Setup);
  expect(await screen.findByText('Supervised Assessment', { exact: true })).toBeInTheDocument();
  expect(screen.getByRole('radio')).toHaveAttribute('value', 'file_evaluation');
  initI18n();
  await locale.set('es');
  await waitLocale();
  expect(await screen.findByText('Evaluación supervisada', { exact: true })).toBeInTheDocument();
  expect(screen.getByRole('radio')).toHaveAttribute('value', 'file_evaluation');
  vi.unstubAllGlobals();
});
