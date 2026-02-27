// Shared i18n setup and initialization
import { init, register, locale as svelteLocale, _, waitLocale } from 'svelte-i18n';
import { browser } from '$app/environment';

export const supportedLocales = ['en', 'es', 'ca', 'eu'];
export const fallbackLocale = 'en';

let isInitialized = false;

/**
 * Register a locale with base messages
 * @param {string} lang - Language code (e.g., 'en')
 * @param {Object} messages - Translation messages for that language
 */
export function addMessages(lang, messages) {
  if (supportedLocales.includes(lang)) {
    register(lang, () => Promise.resolve(messages));
  }
}

/**
 * Get the initial locale from localStorage or browser settings
 */
function getInitialLocale() {
  if (!browser) {
    return fallbackLocale;
  }

  const savedLocale = localStorage.getItem('lang');
  if (savedLocale && supportedLocales.includes(savedLocale)) {
    return savedLocale;
  }

  return fallbackLocale;
}

/**
 * Initialize i18n with base translations
 * Must be called once before components render
 */
export function initI18n() {
  if (isInitialized) return;

  const initial = getInitialLocale();
  console.log(`Initializing svelte-i18n with locale: ${initial}`);

  init({
    fallbackLocale: fallbackLocale,
    initialLocale: initial
  });

  isInitialized = true;
}

// Re-export svelte-i18n utilities
export { svelteLocale as locale, _, waitLocale };
