import { browser } from '$app/environment';
import { get } from 'svelte/store';
import { user } from '@lamb/ui';
import { assistants } from '$lib/stores/assistantStore';
import { assistantConfigStore } from '$lib/stores/assistantConfigStore';
import { rubricStore } from '$lib/stores/rubricStore.svelte.js';
import { resetTemplateStore } from '$lib/stores/templateStore';
import { resetAssistantPublishState } from '$lib/stores/assistantPublish';
import { resetTabs as resetAacTabs } from '$lib/stores/aacStore.svelte';

/**
 * Reset frontend stores that can leak user-scoped state.
 */
export function resetAllUserScopedStores() {
	if (!browser) return;

	assistants.reset();
	assistantConfigStore.clearCache();
	rubricStore.reset();
	resetTemplateStore();
	resetAssistantPublishState();
	resetAacTabs();
}

/**
 * Clear the current session and reset all user-scoped state.
 */
export function clearCurrentSession() {
	if (!browser) return;

	user.logout();
	resetAllUserScopedStores();
}

/**
 * Replace any existing session with a fresh login payload.
 * @param {any} userData
 */
export function replaceSessionWithLoginData(userData) {
	if (!browser) return;

	clearCurrentSession();
	user.login(userData);
}

/**
 * Replace any existing session with a token from an external login flow.
 * @param {string} token
 * @returns {Promise<any>}
 */
export async function replaceSessionWithToken(token) {
	if (!browser) return null;

	clearCurrentSession();
	user.setToken(token);

	const result = await user.fetchAndPopulateProfile();
	if (!result?.success) {
		clearCurrentSession();
		throw new Error(result?.error || 'Failed to bootstrap session from token');
	}

	return result;
}

/**
 * Ensure the current session has a fully-loaded user profile.
 * Recovery path for page refreshes where the profile wasn't fully
 * populated (e.g. interrupted LTI flow that saved a token but not the name).
 *
 * If the profile fetch returns incomplete data (missing name/email), clear
 * the session — staying half-logged-in is worse than forcing a re-login,
 * because every downstream component breaks on `null` user fields. (#353, H6)
 */
export async function ensureProfileLoaded() {
	if (!browser) return;
	const { isLoggedIn, name } = get(user);
	if (isLoggedIn && !name) {
		const result = await user.fetchAndPopulateProfile();
		if (!result?.success) {
			console.warn('Profile bootstrap failed, clearing session:', result?.error);
			clearCurrentSession();
		}
	}
}
