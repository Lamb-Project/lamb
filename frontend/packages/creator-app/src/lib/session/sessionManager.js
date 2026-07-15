/**
 * creator-app session management.
 *
 * `clearCurrentSession` and `ensureProfileLoaded` are delegated to @lamb/ui,
 * which now has a hook system (`registerOnClearSession`) that ensures
 * `resetAllUserScopedStores` runs on every logout path — including the Nav
 * button, 401/403 redirects from apiClient, and session polling.
 *
 * This file only holds creator-app–specific logic:
 *   - `resetAllUserScopedStores()` — registered as a callback in +layout.svelte
 *   - `replaceSessionWithLoginData()` — used by Login.svelte
 *   - `replaceSessionWithToken()` — used by +layout.svelte for LTI flows
 */

import { browser } from '$app/environment';
import { user, clearCurrentSession, ensureProfileLoaded } from '@lamb/ui';
import { assistants } from '$lib/stores/assistantStore';
import { assistantConfigStore } from '$lib/stores/assistantConfigStore';
import { rubricStore } from '$lib/stores/rubricStore.svelte.js';
import { resetTemplateStore } from '$lib/stores/templateStore';
import { resetAssistantPublishState } from '$lib/stores/assistantPublish';
import { resetTabs as resetAacTabs } from '$lib/stores/aacStore.svelte';

// Re-export so existing imports of '$lib/session/sessionManager' keep working
// without any changes in apiClient.js, Login.svelte, or +layout.svelte.
export { clearCurrentSession, ensureProfileLoaded };

/**
 * Reset frontend stores that can leak user-scoped state between sessions.
 * This is registered as an onClearSession callback in +layout.svelte so it
 * runs automatically on every logout path.
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
