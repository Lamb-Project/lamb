import { describe, it, expect } from 'vitest';
import { apiKeysText } from './apiKeysText';

describe('apiKeysText (#519)', () => {
	it('has the same non-empty keys in en, es, ca and eu', () => {
		const en = Object.keys(apiKeysText('en')).sort();
		for (const code of ['es', 'ca', 'eu']) {
			const t = apiKeysText(code);
			expect(Object.keys(t).sort()).toEqual(en);
			for (const key of en) expect(t[key].trim().length).toBeGreaterThan(0);
		}
	});
	it('falls back to English and accepts regional codes', () => {
		expect(apiKeysText('fr').nav).toBe('API keys');
		expect(apiKeysText('ca-ES').nav).toBe('Claus API');
	});
});
