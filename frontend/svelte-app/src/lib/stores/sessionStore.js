import { writable } from 'svelte/store';

/**
 * Store to manage session expiration state
 */
export const sessionExpired = writable(false);

/**
 * Show the session expired modal
 */
export function showSessionExpired() {
    sessionExpired.set(true);
}

/**
 * Hide the session expired modal
 */
export function hideSessionExpired() {
    sessionExpired.set(false);
}
