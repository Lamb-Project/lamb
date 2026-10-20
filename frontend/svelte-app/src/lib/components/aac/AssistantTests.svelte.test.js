import { describe, test, expect, vi } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';

import { init, register } from 'svelte-i18n';
register('en', () => import('$lib/locales/en.json'));
init({ fallbackLocale: 'en', initialLocale: 'en' });
const calls = { runs: 0 };
vi.mock('$lib/services/testService', () => ({
	getScenarios: vi.fn(async () => []),
	getRuns: vi.fn(async () => { calls.runs++; return []; }),
	getEvaluations: vi.fn(async () => []),
	createScenario: vi.fn(), deleteScenario: vi.fn(), runTests: vi.fn(), evaluateRun: vi.fn()
}));
import AssistantTests from './AssistantTests.svelte';

describe('AssistantTests', () => {
	test('reloads when LAMB LEGATUS changes this assistant’s tests, and only this one', async () => {
		render(AssistantTests, { assistantId: 9 });
		await waitFor(() => expect(calls.runs).toBe(1));
		window.dispatchEvent(new CustomEvent('lamb-tests-changed', { detail: { assistantId: 12 } }));
		await new Promise((r) => setTimeout(r, 20));
		expect(calls.runs).toBe(1);
		window.dispatchEvent(new CustomEvent('lamb-tests-changed', { detail: { assistantId: 9 } }));
		await waitFor(() => expect(calls.runs).toBe(2));
	});
});
