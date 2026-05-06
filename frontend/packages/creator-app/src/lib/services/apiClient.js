/**
 * Centralized API client for LAMB — single source of truth.
 *
 * Handles:
 * - Bearer token attachment (from localStorage userToken)
 * - Global 401 handling — clears the session and redirects to login,
 *   so an expired OWI session no longer leaves the UI silently broken
 *   until the user manually reloads the page (#352, M1/M2/M3).
 * - Global 403 handling — detects disabled/deleted accounts via the
 *   `X-Account-Status` response header and forces logout.
 *
 * Three transports are exported:
 *
 *   - `apiFetch(path, options)` — fetch-based, returns Response
 *   - `apiJson(path, options)`  — fetch-based, parses JSON, throws on !ok
 *   - `apiAxios`                — axios instance with the same interceptors
 *
 * Backward-compatible aliases (from the former utils/apiClient.js):
 *   - `authenticatedFetch`     — alias for `apiFetch`
 *   - `authenticatedFetchJson` — alias for `apiJson`
 *
 * Extra options on top of standard `RequestInit`:
 *   - `skipAuth`  — disable token auto-attach AND auth redirect (login/signup)
 *   - `token`     — use this token instead of the stored one (e.g. LTI bootstrap)
 */

import axios from 'axios';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { base } from '$app/paths';
import { getApiUrl } from '$lib/config';

// Guard against re-entrant redirects: if a page has many concurrent in-flight
// requests and they all 401 at once, only fire one redirect.
let _redirecting = false;

/** @returns {string} */
function getStoredToken() {
	return browser ? (localStorage.getItem('userToken') || '') : '';
}

/**
 * Force-logout and redirect to login.
 * Handles both 401 (expired) and 403 (disabled/deleted) scenarios.
 *
 * @param {string} [reason='expired'] - Reason for logout: 'expired', 'disabled', 'deleted'
 */
async function handleUnauthorized(reason = 'expired') {
	if (!browser) return;
	if (_redirecting) return;
	_redirecting = true;

	/** @type {Record<string, string>} */
	const messages = {
		expired: 'Session expired — redirecting to login',
		disabled: 'Account disabled — forcing logout',
		deleted: 'Account deleted — forcing logout'
	};
	console.warn(messages[reason] || messages.expired);

	try {
		// Dynamic import to avoid circular dep with stores at module load.
		const { clearCurrentSession } = await import('$lib/session/sessionManager');
		clearCurrentSession();
	} catch (e) {
		console.error('Failed to clear session during auth handling:', e);
	}

	try {
		// Root path renders the Login component when not authenticated.
		await goto(`${base}/`, { replaceState: true });
	} catch (e) {
		console.error('Failed to redirect after auth error:', e);
	}

	// Reset the guard after navigation has had time to settle.
	setTimeout(() => { _redirecting = false; }, 1500);
}

/**
 * Check a fetch Response for 403 with X-Account-Status header indicating
 * the account has been disabled or deleted by an admin.
 *
 * @param {Response} res
 * @param {boolean} skipAuth
 * @param {string} tokenForRequest
 */
function checkAccountDisabled(res, skipAuth, tokenForRequest) {
	if (res.status === 403 && !skipAuth && tokenForRequest) {
		const accountStatus = res.headers?.get?.('X-Account-Status');
		if (accountStatus === 'disabled' || accountStatus === 'deleted') {
			handleUnauthorized(accountStatus === 'deleted' ? 'deleted' : 'disabled');
			throw new Error(`Account ${accountStatus} — redirecting to login`);
		}
	}
}

/**
 * @typedef {RequestInit & { skipAuth?: boolean, token?: string }} ApiFetchOptions
 */

/**
 * Centralized fetch with bearer-token attachment and global 401 handling.
 *
 * @param {string} path - API path (e.g. '/creator/assistants') or full URL
 * @param {ApiFetchOptions} [options]
 * @returns {Promise<Response>}
 */
export async function apiFetch(path, options = {}) {
	const { skipAuth, token: explicitToken, headers: rawHeaders, ...fetchOptions } = options;
	const headers = new Headers(rawHeaders || {});

	let tokenForRequest = '';
	if (!skipAuth) {
		tokenForRequest = explicitToken || getStoredToken();
		if (tokenForRequest && !headers.has('Authorization')) {
			headers.set('Authorization', `Bearer ${tokenForRequest}`);
		}
	}

	const url = path.startsWith('http') ? path : getApiUrl(path);
	const res = await fetch(url, { ...fetchOptions, headers });

	if (res.status === 401 && !skipAuth && tokenForRequest) {
		// We sent a token and the server rejected it: session expired.
		handleUnauthorized('expired');
		throw new Error('Session expired — redirecting to login');
	}

	// 403 with X-Account-Status: disabled/deleted → force logout
	checkAccountDisabled(res, !!skipAuth, tokenForRequest);

	return res;
}

/**
 * JSON convenience wrapper. Throws on non-OK with the parsed `detail` or
 * `error` field as the message. Use this for the common case of JSON
 * request → JSON response endpoints.
 *
 * @param {string} path
 * @param {ApiFetchOptions} [options]
 * @returns {Promise<any>}
 */
export async function apiJson(path, options = {}) {
	const headers = new Headers(options.headers || {});
	if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
		headers.set('Content-Type', 'application/json');
	}
	const res = await apiFetch(path, { ...options, headers });

	if (!res.ok) {
		let detail = `API error (${res.status})`;
		try {
			const err = await res.json();
			detail = err?.detail || err?.error || detail;
		} catch (_) { /* response wasn't JSON */ }
		throw new Error(detail);
	}

	// 204 No Content
	if (res.status === 204) return null;

	const text = await res.text();
	if (!text) return null;
	try {
		return JSON.parse(text);
	} catch (e) {
		throw new Error('Invalid JSON response from server');
	}
}

/**
 * Shared axios instance for legacy services (knowledgeBaseService,
 * assistantService, analyticsService, libraryService, templateService).
 *
 * - Auto-attaches the bearer token via a request interceptor (services no
 *   longer need to thread the token through manually, though they may still
 *   pass `Authorization` in headers and that takes precedence).
 * - On 401 with a stored token, clears the session and redirects to login —
 *   same global recovery as `apiFetch` (#352, M1/M2/M3).
 *
 * Use this instead of importing axios directly so 401 handling is consistent.
 */
export const apiAxios = axios.create();

apiAxios.interceptors.request.use((config) => {
	const headers = config.headers;
	if (!headers.Authorization && !headers.authorization) {
		const token = getStoredToken();
		if (token) {
			// axios v1 accepts header mutation either way; keep the case used
			// elsewhere in this codebase.
			config.headers.Authorization = `Bearer ${token}`;
		}
	}
	return config;
});

apiAxios.interceptors.response.use(
	(response) => response,
	(error) => {
		const status = error?.response?.status;
		const token = getStoredToken();

		if (status === 401 && token) {
			handleUnauthorized('expired');
			return Promise.reject(new Error('Session expired — redirecting to login'));
		}

		// 403 with X-Account-Status: disabled/deleted → force logout
		if (status === 403 && token) {
			const accountStatus = error.response?.headers?.['x-account-status'];
			if (accountStatus === 'disabled' || accountStatus === 'deleted') {
				handleUnauthorized(accountStatus === 'deleted' ? 'deleted' : 'disabled');
				return Promise.reject(new Error(`Account ${accountStatus} — redirecting to login`));
			}
		}

		return Promise.reject(error);
	}
);

// ---------------------------------------------------------------------------
// Backward-compatible aliases
//
// These match the exports from the former utils/apiClient.js so that
// consumers (admin/+page.svelte, org-admin/+page.svelte) can migrate
// with a simple import-path change.
// ---------------------------------------------------------------------------
export { apiFetch as authenticatedFetch };
export { apiJson as authenticatedFetchJson };

