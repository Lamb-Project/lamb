import { apiFetch } from '$lib/services/apiClient';

// All admin endpoints route through apiFetch so an expired token triggers a
// global session reset + redirect, instead of a generic "Failed to fetch"
// banner that would otherwise force the admin to manually reload. (#352, M16)
// Token is resolved internally by apiFetch via getStoredToken() — callers
// never pass it explicitly.

/**
 * @param {string} path
 * @param {RequestInit} [init]
 * @returns {Promise<any>}
 */
async function jsonRequest(path, init = {}) {
	const response = await apiFetch(path, {
		headers: { 'Content-Type': 'application/json' },
		...init
	});
	if (!response.ok) {
		// Tolerate non-JSON 5xx responses (Caddy/proxy HTML) instead of throwing
		// the misleading "Failed to fetch" that the bare .json() path produced.
		let detail;
		try {
			const err = await response.json();
			detail = err?.error || err?.detail;
		} catch {
			/* not JSON */
		}
		throw new Error(detail || `Request failed (${response.status})`);
	}
	return response.json();
}

/**
 * Fetch the current user's profile (resource overview)
 * @returns {Promise<any>}
 */
export async function getMyProfile() {
	return jsonRequest('/user/profile', { method: 'GET' });
}

/**
 * Fetch a specific user's profile (admin/org-admin)
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function getUserProfile(userId) {
	return jsonRequest(`/admin/users/${userId}/profile`, { method: 'GET' });
}

/**
 * Disable a user account
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function disableUser(userId) {
	return jsonRequest(`/admin/users/${userId}/disable`, { method: 'PUT' });
}

/**
 * Enable a user account
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function enableUser(userId) {
	return jsonRequest(`/admin/users/${userId}/enable`, { method: 'PUT' });
}

/**
 * Disable multiple user accounts
 * @param {number[]} userIds
 * @returns {Promise<any>}
 */
export async function disableUsersBulk(userIds) {
	return jsonRequest('/admin/users/disable-bulk', {
		method: 'POST',
		body: JSON.stringify({ user_ids: userIds })
	});
}

/**
 * Enable multiple user accounts
 * @param {number[]} userIds
 * @returns {Promise<any>}
 */
export async function enableUsersBulk(userIds) {
	return jsonRequest('/admin/users/enable-bulk', {
		method: 'POST',
		body: JSON.stringify({ user_ids: userIds })
	});
}

/**
 * Check user dependencies (assistants and knowledge bases)
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function checkUserDependencies(userId) {
	return jsonRequest(`/admin/users/${userId}/dependencies`, { method: 'GET' });
}

/**
 * Delete a disabled user (must have no dependencies)
 * @param {number} userId
 * @returns {Promise<any>}
 */
export async function deleteUser(userId) {
	return jsonRequest(`/admin/users/${userId}`, { method: 'DELETE' });
}

export async function fetchCostOverview() {
	return jsonRequest('/admin/cost-overview', { method: 'GET' });
}

export async function fetchCostSummaryByOrg(organizationId) {
	return jsonRequest(`/admin/cost-overview/summary?organization_id=${organizationId}`, { method: 'GET' });
}

export async function searchOrganizations(name) {
	return jsonRequest(`/admin/organizations/search?name=${encodeURIComponent(name)}`, { method: 'GET' });
}

export async function fetchAssistantUsageByModel(assistantId) {
	return jsonRequest(`/admin/assistant/${assistantId}/usage-by-model`, { method: 'GET' });
}

export async function fetchModelPricing() {
	return jsonRequest('/admin/model-pricing', { method: 'GET' });
}

export async function createModelPricing(data) {
	return jsonRequest('/admin/model-pricing', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateModelPricing(id, data) {
	return jsonRequest(`/admin/model-pricing/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export async function deleteModelPricing(id) {
	return jsonRequest(`/admin/model-pricing/${id}`, { method: 'DELETE' });
}
