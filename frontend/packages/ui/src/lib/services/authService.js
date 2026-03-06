const browser = typeof window !== 'undefined';

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
  },

  /**
   * Login with email and password
   * @param {string} email - User email
   * @param {string} password - User password
   * @returns {Promise<{success: boolean, data?: object, error?: string}>}
   */
  login: async (email, password) => {
    if (!browser) {
      return { success: false, error: 'Not in browser environment' };
    }

    try {
      const response = await fetch('/creator/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ email, password }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        // Store token if present in response
        if (data.data?.token) {
          authService.setToken(data.data.token);
        }
        return { success: true, data: data.data };
      } else {
        return { 
          success: false, 
          error: data.error || 'Login failed' 
        };
      }
    } catch (error) {
      console.error('Login error:', error);
      return { 
        success: false, 
        error: error.message || 'Network error' 
      };
    }
  },

  /**
   * Fetch user profile using auth token
   * @param {string} token - Auth token
   * @returns {Promise<{success: boolean, data?: object, error?: string}>}
   */
  fetchUserProfile: async (token) => {
    if (!browser) {
      return { success: false, error: 'Not in browser environment' };
    }

    try {
      const response = await fetch('/creator/profile', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (response.ok && data.success) {
        return { success: true, data: data.data };
      } else {
        return { 
          success: false, 
          error: data.error || 'Failed to fetch profile' 
        };
      }
    } catch (error) {
      console.error('Profile fetch error:', error);
      return { 
        success: false, 
        error: error.message || 'Network error' 
      };
    }
  }
};
