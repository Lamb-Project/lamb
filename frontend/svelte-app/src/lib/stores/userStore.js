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

// Initialize user state from localStorage if available
const storedUser = browser 
  ? {
      token: localStorage.getItem('userToken'),
      name: localStorage.getItem('userName'),
      email: localStorage.getItem('userEmail'),
      owiUrl: localStorage.getItem('OWI_url'),
      data: getStoredJson('userData') // Use safe parse function
    }
  : { token: null, name: null, email: null, owiUrl: null, data: null };

// Create the user store
const createUserStore = () => {
  const { subscribe, set, update } = writable({
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
     * The user info will be fetched later when API calls are made.
     * @param {string} token - Authentication token.
     */
    setToken: (token) => {
      if (browser && token) {
        localStorage.setItem('userToken', token);
      }
      update(state => ({
        ...state,
        isLoggedIn: true,
        token: token
      }));
    },
    
    // Logout function
    logout: () => {
      // Only remove from localStorage if in browser environment
      if (browser) {
        console.log('Logging out: Clearing user and cache data from localStorage');
        localStorage.removeItem('userToken');
        localStorage.removeItem('userName');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('OWI_url');
        localStorage.removeItem('userData');
        // Clear assistant config cache on logout for debugging
        localStorage.removeItem('lamb_assistant_capabilities');
        localStorage.removeItem('lamb_assistant_defaults');
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
