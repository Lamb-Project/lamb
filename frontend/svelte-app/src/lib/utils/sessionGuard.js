/**
 * Session Guard - Detects disabled accounts mid-session and forces logout.
 *
 * The backend returns HTTP 403 or 401 with detail "Account disabled..." when a
 * disabled user tries to use a valid token.  This module:
 *   1. Provides `checkSession()` to validate the current token against the backend.
 *   2. Provides `handleApiResponse()` to inspect any fetch/axios response for
 *      the "account disabled" signal and trigger logout if detected.
 *   3. Provides `startSessionPolling()` / `stopSessionPolling()` for a periodic
 *      heartbeat that catches disablement even if the user is idle.
 */

import { browser } from '$app/environment';
import { getApiUrl } from '$lib/config';
import { user } from '$lib/stores/userStore';
import { goto } from '$app/navigation';
import { base } from '$app/paths';
import { get } from 'svelte/store';

/** @type {ReturnType<typeof setInterval> | null} */
let pollingInterval = null;


/**
 * Check whether a fetch Response indicates the account has been disabled or deleted.
 * If so, force-logout the user and redirect to root.
 *
 * Call this after every `fetch()` / `axios` response in services, or use
 * the polling mechanism for background detection.
 *
 * @param {Response | { status: number, data?: any }} response - A fetch Response or axios-like response object
 * @returns {Promise<boolean>} `true` if the account was disabled/deleted (caller should abort further processing)
 */
export async function handleApiResponse(response) {
	if (!browser) return false;

	const status = response.status ?? response?.status;
	if (status !== 403 && status !== 401) return false;

	// 403: check X-Account-Status header (disabled or deleted account)
	if (status === 403) {
		const accountStatus = response.headers?.get?.('X-Account-Status');
		if (accountStatus === 'disabled' || accountStatus === 'deleted') {
			forceLogout(accountStatus === 'deleted' ? 'deleted' : 'disabled');
			return true;
		}
		return false; // 403 for other reasons (e.g. permissions) — don't logout
	}

	// 401: token is invalid or expired
	forceLogout('expired');
	return true;
}

/**
 * Perform a lightweight token validation call to the backend.
 * If the backend returns 403 "Account disabled/deleted" or 401, force-logout.
 *
 * @returns {Promise<boolean>} `true` if the session is still valid
 */
export async function checkSession() {
	if (!browser) return true;

	const currentUser = get(user);
	if (!currentUser.isLoggedIn || !currentUser.token) return false;

	try {
		const response = await fetch(getApiUrl('/user/status'), {
			method: 'GET',
			headers: {
				Authorization: `Bearer ${currentUser.token}`,
				'Content-Type': 'application/json'
			}
		});

		// Delegate all auth-error handling to handleApiResponse
		const handled = await handleApiResponse(response);
		if (handled) return false;

		return response.ok;
	} catch (error) {
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
			// Add catch to handle potential unhandled promise rejections during polling
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

/**
 * Force-logout the user and redirect to login page.
 * Displays a brief message via console.
 * 
 * @param {string} [reason='disabled'] - Reason for logout: 'disabled', 'deleted', 'expired'
 */
function forceLogout(reason = 'disabled') {
	if (!browser) return;

	const messages = {
		disabled: 'Account disabled detected — forcing logout',
		deleted: 'Account no longer exists — forcing logout',
		expired: 'Session expired — forcing logout'
	};

	console.warn(messages[reason] || messages.disabled);
	user.logout();
	// Use replaceState so the user can't "back" into the disabled session
	goto(`${base}/`, { replaceState: true });
}
