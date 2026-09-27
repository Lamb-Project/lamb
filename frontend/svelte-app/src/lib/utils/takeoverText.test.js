import { describe, test, expect } from 'vitest';
import { takeoverText, fill, when } from './takeoverText.js';

describe('takeoverText', () => {
	test('every language has every text', () => {
		const keys = Object.keys(takeoverText('en')).sort();
		for (const lang of ['es', 'ca', 'eu']) expect(Object.keys(takeoverText(lang)).sort()).toEqual(keys);
		expect(takeoverText('ca-ES').back).toBe('Torna al meu compte');
		expect(takeoverText('xx')).toBe(takeoverText('en'));
	});
	test('fills placeholders and formats times', () => {
		expect(fill(takeoverText('en').acting, { name: 'Ana', email: 'ana@x.test' })).toBe('You are acting as Ana (ana@x.test)');
		expect(when(0, 'en')).toBe('');
		expect(when(1790000000, 'en', true)).toMatch(/\d/);
	});
});
