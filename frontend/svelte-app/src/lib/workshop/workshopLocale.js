// src/lib/workshop/workshopLocale.js
/**
 * Locale resolution for the student workshop shell (decision C6).
 *
 * Students arrive from an LMS iframe with no LAMB session and no saved
 * preference, so the wizard cannot rely on `localStorage.lang` alone (which is
 * also why the global `i18n.js` default is left alone — changing it would move
 * the language of every existing Creator user).
 *
 * Chain:
 *   1. `?lang=` — appended by the LTI launch from `launch_presentation_locale`
 *   2. `localStorage.lang` — an explicit choice made in this browser
 *   3. the browser's own language
 *   4. `en`
 *
 * The result is applied *without persisting*: a guess must not overwrite the
 * language a teacher already chose for the Creator app. Only the wizard's
 * LocaleSwitcher persists (it is an explicit human choice).
 */

import { browser } from '$app/environment';
import { locale as svelteLocale, setLocale, supportedLocales, fallbackLocale } from '$lib/i18n';

/** Query parameter carrying the LMS locale. */
export const WORKSHOP_LANG_PARAM = 'lang';

/**
 * Match a locale-ish string against the supported list.
 *
 * Accepts BCP-47 tags with region/script subtags (`es-ES` → `es`) and is
 * case-insensitive.
 *
 * @param {string | null | undefined} value
 * @param {string[]} [supported]
 * @returns {string | null}
 */
export function matchLocale(value, supported = supportedLocales) {
	if (!value) return null;
	const base = String(value).trim().toLowerCase().replace(/_/g, '-').split('-')[0];
	return supported.includes(base) ? base : null;
}

/**
 * Resolve the workshop locale from the chain above (pure function).
 *
 * @param {{urlLang?: string | null, storedLang?: string | null,
 *          browserLang?: string | null, supported?: string[],
 *          fallback?: string}} [sources]
 * @returns {string}
 */
export function resolveWorkshopLocale(sources = {}) {
	const supported = sources.supported || supportedLocales;
	const fallback = sources.fallback || fallbackLocale;
	for (const candidate of [sources.urlLang, sources.storedLang, sources.browserLang]) {
		const match = matchLocale(candidate, supported);
		if (match) return match;
	}
	return fallback;
}

/**
 * Resolve and apply the workshop locale (browser only).
 *
 * @param {string | null} [urlLang]
 * @returns {string} the applied locale
 */
export function initWorkshopLocale(urlLang = null) {
	if (!browser) return fallbackLocale;

	const resolved = resolveWorkshopLocale({
		urlLang,
		storedLang: localStorage.getItem('lang'),
		browserLang: navigator.language
	});
	setLocale(resolved, { persist: false });
	return resolved;
}

/**
 * Apply a language chosen by the student (persisted, like the Creator app).
 *
 * @param {string} lang
 * @returns {string} the applied locale
 */
export function chooseWorkshopLocale(lang) {
	const match = matchLocale(lang) || fallbackLocale;
	setLocale(match, { persist: true });
	return match;
}

export { svelteLocale };
