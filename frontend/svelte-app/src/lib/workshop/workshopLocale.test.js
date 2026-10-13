// src/lib/workshop/workshopLocale.test.js
import { describe, test, expect } from 'vitest';
import {
	matchLocale,
	resolveWorkshopLocale,
	WORKSHOP_LANG_PARAM
} from './workshopLocale.js';

describe('matchLocale', () => {
	test('matches a plain language code', () => {
		expect(matchLocale('es')).toBe('es');
	});

	test('matches region and script subtags', () => {
		expect(matchLocale('es-ES')).toBe('es');
		expect(matchLocale('ca_ES_valencia')).toBe('ca');
		expect(matchLocale('EU-fr')).toBe('eu');
	});

	test('rejects unsupported and empty values', () => {
		expect(matchLocale('pt-BR')).toBeNull();
		expect(matchLocale('')).toBeNull();
		expect(matchLocale(null)).toBeNull();
		expect(matchLocale(undefined)).toBeNull();
	});
});

describe('resolveWorkshopLocale — the C6 chain', () => {
	test('the LMS locale wins over everything', () => {
		expect(resolveWorkshopLocale({
			urlLang: 'eu', storedLang: 'ca', browserLang: 'es-ES'
		})).toBe('eu');
	});

	test('the saved choice wins over the browser language', () => {
		expect(resolveWorkshopLocale({
			urlLang: null, storedLang: 'ca', browserLang: 'es-ES'
		})).toBe('ca');
	});

	test('the browser language is used when nothing else is known', () => {
		expect(resolveWorkshopLocale({
			urlLang: null, storedLang: null, browserLang: 'es-ES'
		})).toBe('es');
	});

	test('falls back to English', () => {
		expect(resolveWorkshopLocale({})).toBe('en');
		expect(resolveWorkshopLocale({
			urlLang: 'pt', storedLang: 'de', browserLang: 'fr'
		})).toBe('en');
	});

	test('an unsupported LMS locale does not block the rest of the chain', () => {
		expect(resolveWorkshopLocale({
			urlLang: 'pt-BR', storedLang: 'ca', browserLang: 'es'
		})).toBe('ca');
	});

	test('honours an explicit supported/fallback override', () => {
		expect(resolveWorkshopLocale({
			urlLang: 'fr', supported: ['en', 'fr'], fallback: 'fr'
		})).toBe('fr');
		expect(resolveWorkshopLocale({
			supported: ['fr'], fallback: 'fr'
		})).toBe('fr');
	});
});

describe('lang parameter name', () => {
	test('is the query parameter the LTI launch appends', () => {
		expect(WORKSHOP_LANG_PARAM).toBe('lang');
	});
});
