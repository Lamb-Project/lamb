// src/lib/components/workshop/LocaleSwitcher.svelte.test.js
import { describe, test, expect, beforeAll, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { waitLocale, locale } from 'svelte-i18n';
import { get } from 'svelte/store';
import { setupI18n } from '$lib/i18n';
import LocaleSwitcher from './LocaleSwitcher.svelte';

beforeAll(async () => {
	setupI18n();
	await waitLocale();
});

beforeEach(async () => {
	localStorage.clear();
	await locale.set('en');
});

/**
 * Wait for a locale switch triggered through the UI to settle.
 *
 * svelte-i18n's `locale.set` flushes a queued dictionary loader first, so the
 * store flips asynchronously; the component's handler cannot be awaited, hence
 * the extra macrotask.
 * @param {string} lang
 */
async function settleLocale(lang) {
	await waitLocale(lang);
	await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('LocaleSwitcher — the student language control (C19)', () => {
	test('L1: offers all four languages', () => {
		render(LocaleSwitcher);
		const select = screen.getByTestId('workshop-locale-switcher');
		const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
		expect(options).toEqual(['en', 'es', 'ca', 'eu']);
	});

	test('L2: language names stay in their own language', () => {
		render(LocaleSwitcher);
		expect(screen.getByRole('option', { name: 'Euskara' })).toBeInTheDocument();
		expect(screen.getByRole('option', { name: 'Català' })).toBeInTheDocument();
		expect(screen.getByRole('option', { name: 'Español' })).toBeInTheDocument();
	});

	test('L3: choosing a language switches the app locale and persists it', async () => {
		render(LocaleSwitcher);
		const select = screen.getByTestId('workshop-locale-switcher');

		await fireEvent.change(select, { target: { value: 'ca' } });
		await settleLocale('ca');

		expect(get(locale)).toBe('ca');
		// An explicit human choice *is* persisted (same key as the Creator app).
		expect(localStorage.getItem('lang')).toBe('ca');
	});

	test('L4: selecting an unsupported value falls back to English', async () => {
		render(LocaleSwitcher);
		const select = screen.getByTestId('workshop-locale-switcher');

		await fireEvent.change(select, { target: { value: 'pt' } });

		expect(get(locale)).toBe('en');
	});

	test('L5: the select shows the active locale', async () => {
		await locale.set('eu');
		await settleLocale('eu');
		render(LocaleSwitcher);
		const select = /** @type {HTMLSelectElement} */ (
			screen.getByTestId('workshop-locale-switcher')
		);
		expect(select.value).toBe('eu');
	});
});
