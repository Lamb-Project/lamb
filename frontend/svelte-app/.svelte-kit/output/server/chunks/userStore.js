import { w as writable } from "./index.js";
const storedUser = { token: null, name: null, email: null, owiUrl: null, data: null };
const createUserStore = () => {
  const { subscribe, set, update } = writable({
    isLoggedIn: false,
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
      set({
        isLoggedIn: true,
        token: userData.token,
        name: userData.name,
        email: userData.email,
        owiUrl: userData.launch_url || null,
        // Handle potential undefined
        data: userData
      });
    },
    /**
     * Sets just the auth token (for LTI login scenarios where we don't have full user data yet).
     * After setting the token, call fetchAndPopulateProfile() to load user info.
     * @param {string} token - Authentication token.
     */
    setToken: (token) => {
      update((state) => ({
        ...state,
        isLoggedIn: true,
        token
      }));
    },
    /**
     * Fetches the user profile from the backend and populates the store.
     * Should be called after setToken() for LTI login flows.
     */
    fetchAndPopulateProfile: async () => {
      const { fetchUserProfile } = await import("./authService.js");
      return;
    },
    // Logout function
    logout: () => {
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
const user = createUserStore();
export {
  user as u
};
