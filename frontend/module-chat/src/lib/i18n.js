// Translations for this LTI module app. lamb-0.8 builds the module apps next to svelte-app
// without the 1.0-alpha pnpm workspace, so this replaces the i18n part of @lamb/ui (same API).
const browser = typeof window !== 'undefined';
import { init, register, locale as svelteLocale, _, waitLocale } from 'svelte-i18n';

let isInitialized = false;

export const supportedLocales = ['en', 'es', 'ca', 'eu'];
export const fallbackLocale = 'en';

supportedLocales.forEach((lang) => {
	register(lang, () => import(`./locales/${lang}.json`));
});

function getInitialLocale() {
	if (!browser) return fallbackLocale;
	const saved = localStorage.getItem('lang');
	return saved && supportedLocales.includes(saved) ? saved : fallbackLocale;
}

export function setupI18n() {
	if (isInitialized) return;
	init({ fallbackLocale, initialLocale: getInitialLocale() });
	isInitialized = true;
}

/** @param {string} newLocale */
export function setLocale(newLocale) {
	if (!supportedLocales.includes(newLocale)) return;
	if (browser) localStorage.setItem('lang', newLocale);
	svelteLocale.set(newLocale);
}

export { setupI18n as initI18n };
export { _, svelteLocale as locale, waitLocale };
