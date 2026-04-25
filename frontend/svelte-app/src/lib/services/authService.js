import { getApiUrl } from '$lib/config'; // Use the new config helper
import { apiFetch } from '$lib/services/apiClient';

// This will be proxied to your FastAPI backend
// NOTE: login() and signup() use raw fetch on purpose — at that point we have
// no stored token yet, so the apiFetch 401 redirect would be incorrect (a 401
// from the login endpoint is "wrong credentials", not "session expired").

/**
 * Handles user login
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<any>} - Promise resolving to login result (adjust 'any' type if possible)
 */
export async function login(email, password) {
  try {
    const formData = new FormData();
    formData.append('email', email);
    formData.append('password', password);
    
    const response = await fetch(getApiUrl('/login'), {
      method: 'POST',
      body: formData
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('Failed to parse response:', e);
      data = {};
    }
    
    if (!response.ok) {
      throw new Error(data?.error || 'Login failed'); // Safe access to error property
    }
    
    return data;
  } catch (error) {
    console.error('Login error:', error);
    let message = 'An error occurred during login';
    if (error instanceof Error) {
      message = error.message;
    }
    // Return a consistent error shape if possible
    return {
      success: false,
      error: message
    };
  }
}

/**
 * Handles user signup
 * @param {string} name - User name
 * @param {string} email - User email
 * @param {string} password - User password
 * @param {string} secretKey - Secret key for registration
 * @returns {Promise<any>} - Promise resolving to signup result (adjust 'any' type if possible)
 */
export async function signup(name, email, password, secretKey) {
  try {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('email', email);
    formData.append('password', password);
    formData.append('secret_key', secretKey);
    
    const response = await fetch(getApiUrl('/signup'), {
      method: 'POST',
      body: formData
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('Failed to parse response:', e);
      data = {};
    }
    
    if (!response.ok) {
      throw new Error(data?.error || 'Signup failed'); // Safe access to error property
    }
    
    return data;
  } catch (error) {
    console.error('Signup error:', error);
    let message = 'An error occurred during signup';
    if (error instanceof Error) {
      message = error.message;
    }
    // Return a consistent error shape if possible
    return {
      success: false,
      error: message
    };
  }
}

/**
 * Fetches the current user's profile using their auth token.
 * Used after LTI login to populate user store with name, email, etc.
 *
 * Routed through apiFetch so an expired token triggers global session
 * recovery (clear + redirect to login) instead of leaving the app in a
 * partial-login state where every subsequent call silently fails. (#352, M2)
 *
 * @param {string} token - Authentication token (LTI bootstrap path passes
 *                         a token that may not be in localStorage yet).
 * @returns {Promise<any>} - Promise resolving to user profile data
 */
export async function fetchUserProfile(token) {
  try {
    const response = await apiFetch('/me', {
      method: 'GET',
      token,
    });

    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('Failed to parse profile response:', e);
      data = {};
    }

    if (!response.ok) {
      throw new Error(data?.error || 'Failed to fetch user profile');
    }

    return data;
  } catch (error) {
    console.error('Fetch user profile error:', error);
    let message = 'An error occurred while fetching user profile';
    if (error instanceof Error) {
      message = error.message;
    }
    return {
      success: false,
      error: message
    };
  }
}

/**
 * Sends a help request to the LAMB assistant
 * @param {string} question - User question
 * @param {string} token - User authentication token
 * @returns {Promise<any>} - Promise resolving to help response (adjust 'any' type if possible)
 */
export async function getHelp(question, token) {
  try {
    const response = await apiFetch('/lamb_helper_assistant', {
      method: 'POST',
      token,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    
    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      console.error('Failed to parse response:', e);
      data = {};
    }
    
    if (!response.ok) {
      throw new Error(data?.error || 'Help request failed'); // Safe access to error property
    }
    
    return data;
  } catch (error) {
    console.error('Help request error:', error);
    let message = 'An error occurred while getting help';
    if (error instanceof Error) {
      message = error.message;
    }
    // Return a consistent error shape if possible
    return {
      success: false,
      error: message
    };
  }
} 