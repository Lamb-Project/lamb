import { writable } from 'svelte/store';

/**
 * User store - shared across all LAMB apps
 * Tracks the current authenticated user
 */
function createUserStore() {
  const { subscribe, set, update } = writable(null);

  return {
    subscribe,
    setUser: (user) => set(user),
    clearUser: () => set(null),
    updateUser: (updates) =>
      update((user) => (user ? { ...user, ...updates } : null))
  };
}

export const userStore = createUserStore();
