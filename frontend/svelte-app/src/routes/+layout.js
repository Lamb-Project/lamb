import { browser } from '$app/environment';
import '$lib/i18n'; // Import to initialize. Important for SSR!
import { locale, waitLocale } from 'svelte-i18n';
import { setupI18n, setLocale, supportedLocales, fallbackLocale } from '$lib/i18n';

/** @type {import('./$types').LayoutLoad} */
export const load = async () => {
	console.log('Running i18n setup in +layout.js load...');

	// Always setup i18n (both client and server)
	setupI18n();

	if (browser) {
		// On client: use localStorage preference or browser language
		let storedLocale = localStorage.getItem('lang');
		let localeToSet = fallbackLocale; // Default to fallback

		if (storedLocale && supportedLocales.includes(storedLocale)) {
			localeToSet = storedLocale; // Use stored locale if valid
		}

		// Set the client locale
		setLocale(localeToSet);
	}

	// Wait for the locale to be fully loaded before continuing
	// This is critical for SSR to work properly
	await waitLocale();

	// The load function needs to return an object, even if empty
	return {};
};
