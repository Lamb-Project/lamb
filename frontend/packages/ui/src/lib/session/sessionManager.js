import { browser } from '$app/environment';
import { get } from 'svelte/store';
import { user } from '../stores/userStore.js';

/**
 * Clear the current session (logout only).
 * Consumer apps can wrap this to also reset app-specific stores.
 */
export function clearCurrentSession() {
	if (!browser) return;
	user.logout();
}

/**
 * Ensure the current session has a fully-loaded user profile.
 * Handles page refreshes where only a token was saved but the
 * profile wasn't fully populated.
 */
export async function ensureProfileLoaded() {
	if (!browser) return;
	const { isLoggedIn, name } = get(user);
	if (isLoggedIn && !name) {
		await user.fetchAndPopulateProfile();
	}
}
