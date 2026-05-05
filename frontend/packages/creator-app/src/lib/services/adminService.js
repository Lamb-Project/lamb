import { apiFetch } from '$lib/services/apiClient';

// All admin endpoints route through apiFetch so an expired token triggers a
// global session reset + redirect, instead of a generic "Failed to fetch"
// banner that would otherwise force the admin to manually reload. (#352, M16)

/**
 * @param {string} path
 * @param {string} token
 * @param {RequestInit} [init]
 * @returns {Promise<any>}
 */
async function jsonRequest(path, token, init = {}) {
	const response = await apiFetch(path, {
		token,
		headers: { 'Content-Type': 'application/json' },
		...init,
	});
	if (!response.ok) {
		// Tolerate non-JSON 5xx responses (Caddy/proxy HTML) instead of throwing
		// the misleading "Failed to fetch" that the bare .json() path produced.
		let detail;
		try {
			const err = await response.json();
			detail = err?.error || err?.detail;
		} catch (_) { /* not JSON */ }
		throw new Error(detail || `Request failed (${response.status})`);
	}
	return response.json();
}

/**
 * Fetch the current user's profile (resource overview)
 * @param {string} token
 * @returns {Promise<any>}
 */
export async function getMyProfile(token) {
	return jsonRequest('/user/profile', token, { method: 'GET' });
}

/**
 * Fetch a specific user's profile (admin/org-admin)
 * @param {string} token
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function getUserProfile(token, userId) {
	return jsonRequest(`/admin/users/${userId}/profile`, token, { method: 'GET' });
}

/**
 * Disable a user account
 * @param {string} token
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function disableUser(token, userId) {
	return jsonRequest(`/admin/users/${userId}/disable`, token, { method: 'PUT' });
}

/**
 * Enable a user account
 * @param {string} token
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function enableUser(token, userId) {
	return jsonRequest(`/admin/users/${userId}/enable`, token, { method: 'PUT' });
}

/**
 * Disable multiple user accounts
 * @param {string} token
 * @param {number[]} userIds
 * @returns {Promise<any>}
 */
export async function disableUsersBulk(token, userIds) {
	return jsonRequest('/admin/users/disable-bulk', token, {
		method: 'POST',
		body: JSON.stringify({ user_ids: userIds }),
	});
}

/**
 * Enable multiple user accounts
 * @param {string} token
 * @param {number[]} userIds
 * @returns {Promise<any>}
 */
export async function enableUsersBulk(token, userIds) {
	return jsonRequest('/admin/users/enable-bulk', token, {
		method: 'POST',
		body: JSON.stringify({ user_ids: userIds }),
	});
}

/**
 * Check user dependencies (assistants and knowledge bases)
 * @param {string} token
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function checkUserDependencies(token, userId) {
	return jsonRequest(`/admin/users/${userId}/dependencies`, token, { method: 'GET' });
}

/**
 * Delete a disabled user (must have no dependencies)
 * @param {string} token
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function deleteUser(token, userId) {
	return jsonRequest(`/admin/users/${userId}`, token, { method: 'DELETE' });
}
