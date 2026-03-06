import { getApiUrl } from '$lib/config';
import { authenticatedFetch } from '$lib/utils/apiClient';

/**
 * Fetch the current user's profile (resource overview)
 * Automatically detects disabled accounts and forces logout.
 * @returns {Promise<any>} - Promise resolving to user profile data
 */
export async function getMyProfile() {
	try {
		const response = await authenticatedFetch(getApiUrl('/user/profile'));

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to fetch profile');
		}

		return await response.json();
	} catch (error) {
		console.error('Error fetching user profile:', error);
		throw error;
	}
}

/**
 * Fetch a specific user's profile (admin/org-admin)
 * Automatically detects disabled accounts and forces logout.
 * @param {number} userId - User ID to fetch profile for
 * @returns {Promise<any>} - Promise resolving to user profile data
 */
export async function getUserProfile(userId) {
	try {
		const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}/profile`));

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to fetch user profile');
		}

		return await response.json();
	} catch (error) {
		console.error('Error fetching user profile:', error);
		throw error;
	}
}

/**
 * Disable a user account
 * Automatically detects disabled accounts and forces logout.
 * @param {number} userId - User ID to disable
 * @returns {Promise<any>} - Promise resolving to operation result
 */
export async function disableUser(userId) {
	try {
		const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}/disable`), {
			method: 'PUT'
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to disable user');
		}

		return await response.json();
	} catch (error) {
		console.error('Error disabling user:', error);
		throw error;
	}
}

/**
 * Enable a user account
 * Automatically detects disabled accounts and forces logout.
 * @param {number} userId - User ID to enable
 * @returns {Promise<any>} - Promise resolving to operation result
 */
export async function enableUser(userId) {
	try {
		const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}/enable`), {
			method: 'PUT'
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to enable user');
		}

		return await response.json();
	} catch (error) {
		console.error('Error enabling user:', error);
		throw error;
	}
}

/**
 * Disable multiple user accounts
 * Automatically detects disabled accounts and forces logout.
 * @param {number[]} userIds - Array of user IDs to disable
 * @returns {Promise<any>} - Promise resolving to bulk operation result
 */
export async function disableUsersBulk(userIds) {
	try {
		const response = await authenticatedFetch(getApiUrl('/admin/users/disable-bulk'), {
			method: 'POST',
			body: JSON.stringify({ user_ids: userIds })
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to disable users');
		}

		return await response.json();
	} catch (error) {
		console.error('Error disabling users:', error);
		throw error;
	}
}

/**
 * Enable multiple user accounts
 * Automatically detects disabled accounts and forces logout.
 * @param {number[]} userIds - Array of user IDs to enable
 * @returns {Promise<any>} - Promise resolving to bulk operation result
 */
export async function enableUsersBulk(userIds) {
	try {
		const response = await authenticatedFetch(getApiUrl('/admin/users/enable-bulk'), {
			method: 'POST',
			body: JSON.stringify({ user_ids: userIds })
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to enable users');
		}

		return await response.json();
	} catch (error) {
		console.error('Error enabling users:', error);
		throw error;
	}
}

/**
 * Check user dependencies (assistants and knowledge bases)
 * Automatically detects disabled accounts and forces logout.
 * @param {number} userId - User ID to check
 * @returns {Promise<any>} - Promise resolving to dependencies info
 */
export async function checkUserDependencies(userId) {
	try {
		const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}/dependencies`));

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to check user dependencies');
		}

		return await response.json();
	} catch (error) {
		console.error('Error checking user dependencies:', error);
		throw error;
	}
}

/**
 * Delete a disabled user (must have no dependencies)
 * Automatically detects disabled accounts and forces logout.
 * @param {number} userId - User ID to delete
 * @returns {Promise<any>} - Promise resolving to operation result
 */
export async function deleteUser(userId) {
	try {
		const response = await authenticatedFetch(getApiUrl(`/admin/users/${userId}`), {
			method: 'DELETE'
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || error.detail || 'Failed to delete user');
		}

		return await response.json();
	} catch (error) {
		console.error('Error deleting user:', error);
		throw error;
	}
}
