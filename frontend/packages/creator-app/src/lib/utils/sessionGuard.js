/**
 * Session Guard — periodic session validation.
 *
 * Provides `startSessionPolling()` / `stopSessionPolling()` for a periodic
 * heartbeat that catches token expiry or account disablement even if the
 * user is idle.
 *
 * Auth-error handling (401/403) is centralised in `services/apiClient.js`,
 * so this module only needs to fire the check — the apiClient will handle
 * the logout & redirect if the backend returns an auth error.
 */

import { browser } from '$app/environment';
import { apiFetch } from '$lib/services/apiClient';
import { userStore as user } from '@lamb/ui';
import { get } from 'svelte/store';

/** @type {ReturnType<typeof setInterval> | null} */
let pollingInterval = null;

/**
 * Perform a lightweight token validation call to the backend.
 * If the backend returns 401 or 403-disabled, the centralized apiClient
 * will handle the logout & redirect automatically.
 *
 * @returns {Promise<boolean>} `true` if the session is still valid
 */
export async function checkSession() {
	if (!browser) return true;

	const currentUser = get(user);
	if (!currentUser.isLoggedIn || !currentUser.token) return false;

	try {
		const response = await apiFetch('/user/status');
		return response.ok;
	} catch (error) {
		// If apiFetch threw 'Session expired' or 'Account disabled', the
		// redirect is already in flight — return false so callers abort.
		if (error instanceof Error && error.message.includes('redirecting to login')) {
			return false;
		}
		// Network error — don't force logout, could be temporary
		console.warn('Session check failed (network):', error);
		return true; // Assume valid to avoid false positives
	}
}

/**
 * Start periodic session validation.
 * @param {number} [intervalMs=60000] - Polling interval in milliseconds (default: 60s)
 */
export function startSessionPolling(intervalMs = 60000) {
	if (!browser) return;
	stopSessionPolling(); // Clear any existing interval

	pollingInterval = setInterval(() => {
		const currentUser = get(user);
		if (currentUser.isLoggedIn) {
			checkSession().catch(err => console.error('Error during session polling check:', err));
		} else {
			// User already logged out — stop polling
			stopSessionPolling();
		}
	}, intervalMs);
}

/**
 * Stop periodic session validation.
 */
export function stopSessionPolling() {
	if (pollingInterval !== null) {
		clearInterval(pollingInterval);
		pollingInterval = null;
	}
}
