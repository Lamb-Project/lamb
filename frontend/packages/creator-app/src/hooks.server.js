import { locale } from 'svelte-i18n';

/** @type {import('@sveltejs/kit').Handle} */
export const handle = async ({ event, resolve }) => {
    // Set locale for SSR based on Accept-Language header or default to 'en'
    const lang = event.request.headers.get('accept-language')?.split(',')[0] || 'en';
    
    // Initialize locale for server-side rendering
    locale.set(lang);
    
    return resolve(event);
};