import { describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { initI18n, locale, waitLocale } from '$lib/i18n.js';

describe('translations of the module app', () => {
	it('start in the default language when the browser denies storage to the frame', async () => {
		// Inside an LMS frame of another site, a browser that blocks third-party storage throws here.
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new DOMException('Access is denied for this document.', 'SecurityError');
		});

		expect(() => initI18n()).not.toThrow();
		await waitLocale();
		expect(get(locale)).toBe('en');
	});
});
