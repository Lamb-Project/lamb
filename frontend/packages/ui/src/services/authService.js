import { browser } from '$app/environment';

/**
 * Auth service - handles user authentication
 * Shared across all LAMB apps
 */
export const authService = {
  /**
   * Get the current auth token from localStorage
   */
  getToken: () => {
    if (!browser) return null;
    return localStorage.getItem('authToken');
  },

  /**
   * Set the auth token in localStorage
   */
  setToken: (token) => {
    if (!browser) return;
    if (token) {
      localStorage.setItem('authToken', token);
    } else {
      localStorage.removeItem('authToken');
    }
  },

  /**
   * Clear auth token on logout
   */
  logout: () => {
    if (browser) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('user');
    }
  },

  /**
   * Get authorization headers for API requests
   */
  getAuthHeaders: () => {
    const token = authService.getToken();
    return token
      ? { Authorization: `Bearer ${token}` }
      : {};
  }
};
