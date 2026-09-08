import { browser } from '$app/environment';
import { get } from 'svelte/store';
import { user } from '../stores/userStore.js';

// ---------------------------------------------------------------------------
// Hook system — apps can register cleanup callbacks to run on clearCurrentSession.
// This allows @lamb/ui to stay decoupled from app-specific stores while still
// guaranteeing those stores are reset on every logout path (Nav button,
// 401/403 redirect, polling detection, etc.).
// ---------------------------------------------------------------------------

/** @type {Array<() => void>} */
const _onClearSessionCallbacks = [];

/**
 * Register a callback to run whenever `clearCurrentSession()` is called.
 * Call this once at app startup (e.g. in +layout.svelte onMount).
 *
 * @param {() => void} callback
 */
export function registerOnClearSession(callback) {
	_onClearSessionCallbacks.push(callback);
}

/**
 * Clear the current session (logout) and run all registered cleanup callbacks.
 * Consumer apps should register their store-reset logic via `registerOnClearSession`.
 */
export function clearCurrentSession() {
	if (!browser) return;
	user.logout();
	for (const cb of _onClearSessionCallbacks) {
		try {
			cb();
		} catch (e) {
			console.error('[sessionManager] onClearSession callback error:', e);
		}
	}
}

/**
 * Ensure the current session has a fully-loaded user profile.
 * Handles page refreshes where only a token was saved but the profile
 * wasn't fully populated. If the fetch fails or returns incomplete data,
 * the session is cleared to avoid a broken half-logged-in state.
 */
export async function ensureProfileLoaded() {
	if (!browser) return;
	const { isLoggedIn, name } = get(user);
	if (isLoggedIn && !name) {
		const result = await user.fetchAndPopulateProfile();
		if (!result?.success) {
			console.warn('[sessionManager] Profile bootstrap failed, clearing session:', result?.error);
			clearCurrentSession();
		}
	}
}
