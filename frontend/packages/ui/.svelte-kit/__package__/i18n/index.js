import { browser } from '$app/environment';
import { init, register, locale as svelteLocale, _, waitLocale } from 'svelte-i18n';

// Ensure this runs only once
let isInitialized = false;

export const supportedLocales = ['en', 'es', 'ca', 'eu'];
export const fallbackLocale = 'en'; // Defaulting to English might be safer

// Register the locales using dynamic imports relative to this file
// Assuming locale files are in $lib/locales/
supportedLocales.forEach(lang => {
  register(lang, () => import(`$lib/locales/${lang}.json`));
});

// Get the initial locale from localStorage or fallback
function getInitialLocale() {
  if (!browser) {
    return fallbackLocale; 
  }
  
  const savedLocale = localStorage.getItem('lang');
  
  if (savedLocale && supportedLocales.includes(savedLocale)) {
    return savedLocale;
  }
  
  // Optional: Could add browser language detection here
  // const browserLang = navigator.language.split('-')[0];
  // if (supportedLocales.includes(browserLang)) return browserLang;
  
  return fallbackLocale;
}

// Initialize the i18n library
export function setupI18n() {
  if (isInitialized) return;
  
  const initial = getInitialLocale();
  console.log(`Initializing svelte-i18n with initial locale: ${initial}, fallback: ${fallbackLocale}`);

  init({
    fallbackLocale: fallbackLocale,
    initialLocale: initial
  });
  
  isInitialized = true;

  // Set a default locale for SSR if needed (though initialLocale should handle it)
  // if (!browser) {
  //   svelteLocale.set(fallbackLocale);
  // }
}

// Set the current locale
/**
 * Sets the current application locale.
 * @param {string} newLocale - The locale code (e.g., 'en', 'es').
 */
export function setLocale(newLocale) {
  if (supportedLocales.includes(newLocale)) {
    if (browser) {
      localStorage.setItem('lang', newLocale);
    }
    svelteLocale.set(newLocale);
    console.log(`Locale set to: ${newLocale}`);
  } else {
    console.warn(`Attempted to set unsupported locale: ${newLocale}`);
  }
}

// Re-export the svelte-i18n tools
export { _ , svelteLocale as locale, waitLocale }; 