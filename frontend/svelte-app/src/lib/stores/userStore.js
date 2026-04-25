import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Function to safely parse JSON from localStorage
/**
 * @param {string} key The localStorage key to retrieve.
 * @returns {any | null} The parsed JSON object or null if not found/invalid.
 */
function getStoredJson(key) {
  if (!browser) return null;
  const item = localStorage.getItem(key);
  try {
    return item ? JSON.parse(item) : null;
  } catch (e) {
    console.error(`Error parsing localStorage item "${key}":`, e);
    localStorage.removeItem(key); // Remove corrupted item
    return null;
  }
}

function getUrlToken() {
  if (!browser) return null;
  try {
    return new URL(window.location.href).searchParams.get('token');
  } catch (e) {
    console.error('Error reading token from URL:', e);
    return null;
  }
}

// Initialize user state from localStorage if available
const bootstrapToken = getUrlToken();
const storedUser = browser 
  ? (bootstrapToken
    ? { token: null, name: null, email: null, owiUrl: null, data: null }
    : {
      token: localStorage.getItem('userToken'),
      name: localStorage.getItem('userName'),
      email: localStorage.getItem('userEmail'),
      owiUrl: localStorage.getItem('OWI_url'),
      data: getStoredJson('userData') // Use safe parse function
    })
  : { token: null, name: null, email: null, owiUrl: null, data: null };

// Create the user store
const createUserStore = () => {
  const { subscribe, set } = writable({
    isLoggedIn: !!storedUser.token,
    ...storedUser
  });

  return {
    subscribe,
    
    /**
     * Logs the user in and updates the store and localStorage.
     * @param {object} userData - User data from the API.
     * @param {string} userData.token - Authentication token.
     * @param {string} userData.name - User's name.
     * @param {string} userData.email - User's email.
     * @param {string} [userData.launch_url] - Optional OpenWebUI launch URL.
     * @param {any} [userData.role] - User role (within nested data, actual structure might vary)
     */
    login: (userData) => {
      // Only store in localStorage if in browser environment
      if (browser) {
        localStorage.setItem('userToken', userData.token);
        localStorage.setItem('userName', userData.name);
        localStorage.setItem('userEmail', userData.email);
        if (userData.launch_url) {
          localStorage.setItem('OWI_url', userData.launch_url);
        }
        localStorage.setItem('userData', JSON.stringify(userData)); // Store the whole object again
      }
      
      // Update the store
      set({
        isLoggedIn: true,
        token: userData.token,
        name: userData.name,
        email: userData.email,
        owiUrl: userData.launch_url || null, // Handle potential undefined
        data: userData
      });
    },
    
    /**
     * Sets just the auth token (for LTI login scenarios where we don't have full user data yet).
     * After setting the token, call fetchAndPopulateProfile() to load user info.
     * @param {string} token - Authentication token.
     */
    setToken: (token) => {
      if (browser && token) {
        localStorage.setItem('userToken', token);
        localStorage.removeItem('userName');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('OWI_url');
        localStorage.removeItem('userData');
      }
      set({
        isLoggedIn: true,
        token: token,
        name: null,
        email: null,
        owiUrl: null,
        data: null
      });
    },
    
    /**
     * Fetches the user profile from the backend and populates the store.
     * Should be called after setToken() for LTI login flows.
     *
     * Validates that the response carries the minimum required fields
     * (name + email). Previously a `{success: true, data: {}}` reply would
     * leave the user "logged in" with name=null/email=null, breaking every
     * downstream component that assumes those fields exist. Now treated as
     * a failure and surfaced via the returned result. (#353, H6)
     */
    fetchAndPopulateProfile: async () => {
      const { fetchUserProfile } = await import('$lib/services/authService.js');
      const token = browser ? localStorage.getItem('userToken') : null;
      if (!token) return null;

      const result = await fetchUserProfile(token);
      const data = result?.success ? result.data : null;
      if (data && data.name && data.email) {
        const userData = { ...data, token };
        if (browser) {
          localStorage.setItem('userName', userData.name);
          localStorage.setItem('userEmail', userData.email);
          if (userData.launch_url) {
            localStorage.setItem('OWI_url', userData.launch_url);
          }
          localStorage.setItem('userData', JSON.stringify(userData));
        }
        set({
          isLoggedIn: true,
          token: token,
          name: userData.name,
          email: userData.email,
          owiUrl: userData.launch_url || null,
          data: userData
        });
        return result;
      }

      // Profile response missing required fields — surface a structured
      // failure so callers (sessionManager.replaceSessionWithToken,
      // sessionManager.ensureProfileLoaded) can decide whether to clear
      // the session and force re-login.
      return {
        success: false,
        error: result?.error || 'Profile data missing required fields (name/email)',
      };
    },
    
    // Logout function
    logout: () => {
      if (browser) {
        console.log('Logging out: Clearing user identity from localStorage');
        localStorage.removeItem('userToken');
        localStorage.removeItem('userName');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('OWI_url');
        localStorage.removeItem('userData');
      }
      
      // Update the store
      set({
        isLoggedIn: false,
        token: null,
        name: null,
        email: null,
        owiUrl: null,
        data: null
      });
    }
  };
};

// Export the user store
export const user = createUserStore();
