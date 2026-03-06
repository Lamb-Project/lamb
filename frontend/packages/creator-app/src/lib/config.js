import { browser } from '$app/environment';

// Default config structure (adjust as needed based on actual config.js)
const defaultConfig = {
    api: {
        baseUrl: '/creator', // Default or fallback base URL
        lambServer: 'http://localhost:9099', // Default LAMB server URL
        // Note: lambApiKey removed for security - now using user authentication
    },
    // Static assets configuration
    assets: {
        path: '/static'
    },
    // Feature flags
    features: {
        enableOpenWebUi: true,
        enableDebugMode: true
    }
};

/**
 * Safely retrieves the runtime config from window.LAMB_CONFIG or falls back to defaults.
 * @returns {typeof defaultConfig} The configuration object.
 */
export function getConfig() {
    if (browser && window.LAMB_CONFIG) {
        return window.LAMB_CONFIG;
    }
    console.warn('LAMB_CONFIG not found on window, using default.');
    return defaultConfig;
}

/**
 * Gets the full API URL for a given endpoint path UNDER the /creator base.
 * @param {string} endpoint - The API endpoint path (e.g., '/login').
 * @returns {string} The full API URL.
 */
export function getApiUrl(endpoint) {
    const config = getConfig();
    const base = config?.api?.baseUrl || defaultConfig.api.baseUrl;
    // Ensure no double slashes
    return `${base.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`;
}

/**
 * Gets the full API URL for a given endpoint path UNDER the /lamb base.
 * This is used for endpoints that are not under /creator (e.g., /lamb/v1/*).
 * Note: Most endpoints should now go through /creator proxies.
 * @param {string} endpoint - The API endpoint path (e.g., '/creator/lamb/assistant-sharing/check-permission').
 * @returns {string} The full API URL using lambServer config.
 */
export function getLambApiUrl(endpoint) {
    const config = getConfig();
    const baseUrl = config?.api?.lambServer || defaultConfig.api.lambServer;
    // Ensure no double slashes
    const cleanBase = baseUrl.replace(/\/$/, '');
    const cleanEndpoint = endpoint.replace(/^\//, '');
    return `${cleanBase}/${cleanEndpoint}`;
}

// You might export other config values if needed
// export const API_CONFIG = getConfig().api; 