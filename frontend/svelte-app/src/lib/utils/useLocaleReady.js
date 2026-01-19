/**
 * Utility for tracking locale loading state in Svelte 5 components.
 * 
 * This module provides a simple way to check if the i18n locale has been loaded,
 * eliminating the need for repeated boilerplate code across components.
 * 
 * @module useLocaleReady
 * 
 * @example
 * // In a Svelte component:
 * import { locale } from '$lib/i18n';
 * import { isLocaleLoaded } from '$lib/utils/useLocaleReady';
 * 
 * // Option 1: Use the derived check (recommended for simple cases)
 * // Just use: $locale ? $_('key') : 'fallback'
 * 
 * // Option 2: Use the helper function for complex conditional rendering
 * let localeReady = $derived(isLocaleLoaded($locale));
 * 
 * // Option 3: For components that need to track loading state with $state
 * import { createLocaleTracker } from '$lib/utils/useLocaleReady';
 * const { localeLoaded, cleanup } = createLocaleTracker(locale);
 * onDestroy(cleanup);
 */

import { get } from 'svelte/store';

/**
 * Check if a locale value indicates the locale is loaded.
 * 
 * @param {string|null|undefined} localeValue - The current locale value
 * @returns {boolean} True if locale is loaded
 * 
 * @example
 * let localeReady = $derived(isLocaleLoaded($locale));
 * {#if localeReady}
 *   {$_('greeting')}
 * {:else}
 *   Loading...
 * {/if}
 */
export function isLocaleLoaded(localeValue) {
    return !!localeValue;
}

/**
 * Create a locale tracker with subscription management.
 * Useful for components that need more control over the subscription lifecycle.
 * 
 * @param {import('svelte/store').Readable<string>} localeStore - The locale store from svelte-i18n
 * @returns {{ localeLoaded: boolean, cleanup: () => void }}
 * 
 * @example
 * import { locale } from '$lib/i18n';
 * import { createLocaleTracker } from '$lib/utils/useLocaleReady';
 * 
 * const tracker = createLocaleTracker(locale);
 * let localeLoaded = $state(tracker.localeLoaded);
 * 
 * // Update on changes
 * $effect(() => {
 *   const unsub = locale.subscribe(v => localeLoaded = !!v);
 *   return unsub;
 * });
 */
export function createLocaleTracker(localeStore) {
    let localeLoaded = !!get(localeStore);
    let unsubscribe = () => {};
    
    unsubscribe = localeStore.subscribe(value => {
        localeLoaded = !!value;
    });
    
    return {
        get localeLoaded() { return localeLoaded; },
        cleanup: unsubscribe
    };
}

/**
 * Get the initial locale loaded state.
 * Useful for initializing $state in components.
 * 
 * @param {import('svelte/store').Readable<string>} localeStore - The locale store from svelte-i18n
 * @returns {boolean} Current locale loaded state
 * 
 * @example
 * import { locale } from '$lib/i18n';
 * import { getInitialLocaleState } from '$lib/utils/useLocaleReady';
 * 
 * let localeLoaded = $state(getInitialLocaleState(locale));
 */
export function getInitialLocaleState(localeStore) {
    return !!get(localeStore);
}

/**
 * RECOMMENDED PATTERN for Svelte 5 components:
 * 
 * Instead of tracking localeLoaded state, use inline checks:
 * 
 * ```svelte
 * <script>
 *   import { _, locale } from '$lib/i18n';
 * </script>
 * 
 * <h1>{$locale ? $_('title') : 'Default Title'}</h1>
 * ```
 * 
 * Or for multiple strings, use a derived value:
 * 
 * ```svelte
 * <script>
 *   import { _, locale } from '$lib/i18n';
 *   
 *   let localeReady = $derived(!!$locale);
 * </script>
 * 
 * {#if localeReady}
 *   <h1>{$_('title')}</h1>
 *   <p>{$_('description')}</p>
 * {:else}
 *   <div class="loading">Loading...</div>
 * {/if}
 * ```
 */
