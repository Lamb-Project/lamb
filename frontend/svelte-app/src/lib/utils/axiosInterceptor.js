import axios from 'axios';
import { browser } from '$app/environment';
import { sessionExpired } from '$lib/stores/sessionStore';

/**
 * Setup axios interceptor to handle 401 errors globally
 * Call this once during app initialization
 */
export function setupAxiosInterceptor() {
    if (!browser) return;

    // Response interceptor
    axios.interceptors.response.use(
        (response) => {
            // Any status code that lie within the range of 2xx cause this function to trigger
            return response;
        },
        (error) => {
            // Any status codes that fall outside the range of 2xx cause this function to trigger
            if (axios.isAxiosError(error)) {
                const status = error.response?.status;
                const errorData = error.response?.data;
                const errorMessage = errorData?.detail || errorData?.error || '';

                // Check for 401 Unauthorized
                if (status === 401) {
                    // Check if it's an authentication/session error
                    if (errorMessage.includes('authentication') || 
                        errorMessage.includes('session') || 
                        errorMessage.includes('token') ||
                        errorMessage.includes('expired') ||
                        errorMessage.includes('invalid')) {
                        // Show session expired modal
                        sessionExpired.set(true);
                    }
                }
            }

            // Return error to allow component-level handling
            return Promise.reject(error);
        }
    );

    // Request interceptor to add auth token
    axios.interceptors.request.use(
        (config) => {
            if (browser) {
                const token = localStorage.getItem('userToken');
                if (token && !config.headers.Authorization) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
            }
            return config;
        },
        (error) => {
            return Promise.reject(error);
        }
    );
}
