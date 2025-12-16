import { browser } from '$app/environment';
import { sessionExpired } from '$lib/stores/sessionStore';

/**
 * Wrapper around fetch that handles authentication errors globally
 * @param {string} url - The URL to fetch
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>} The fetch response
 */
export async function authenticatedFetch(url, options = {}) {
    if (!browser) {
        // Server-side: just pass through
        return fetch(url, options);
    }

    // Get token from localStorage
    const token = localStorage.getItem('userToken');
    
    // Add Authorization header if token exists
    const headers = new Headers(options.headers || {});
    if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    // Make the request
    const response = await fetch(url, {
        ...options,
        headers
    });

    // Check for 401 Unauthorized
    if (response.status === 401) {
        // Check if it's an authentication error
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            try {
                const errorData = await response.clone().json();
                const errorMessage = errorData?.detail || errorData?.error || '';
                
                // Check if it's an authentication/session error
                if (errorMessage.includes('authentication') || 
                    errorMessage.includes('session') || 
                    errorMessage.includes('token') ||
                    errorMessage.includes('expired') ||
                    errorMessage.includes('invalid')) {
                    // Show session expired modal
                    sessionExpired.set(true);
                    // Don't throw here - let the modal handle navigation
                }
            } catch (e) {
                // If we can't parse JSON, still show modal for 401
                sessionExpired.set(true);
            }
        } else {
            // Non-JSON 401 response, still show modal
            sessionExpired.set(true);
        }
    }

    return response;
}

/**
 * Create an axios-like interceptor for fetch
 * This can be used to replace axios calls with authenticatedFetch
 */
export const httpClient = {
    get: (url, config = {}) => authenticatedFetch(url, { ...config, method: 'GET' }),
    post: (url, data, config = {}) => authenticatedFetch(url, {
        ...config,
        method: 'POST',
        body: data instanceof FormData ? data : JSON.stringify(data),
        headers: {
            ...(data instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
            ...(config.headers || {})
        }
    }),
    put: (url, data, config = {}) => authenticatedFetch(url, {
        ...config,
        method: 'PUT',
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json',
            ...(config.headers || {})
        }
    }),
    delete: (url, config = {}) => authenticatedFetch(url, { ...config, method: 'DELETE' })
};
