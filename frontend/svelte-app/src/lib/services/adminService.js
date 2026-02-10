import { getApiUrl } from '$lib/config';

/**
 * Fetch the current user's profile (resource overview)
 * @param {string} token - Authorization token
 * @returns {Promise<any>} - Promise resolving to user profile data
 */
export async function getMyProfile(token) {
	try {
		const response = await fetch(getApiUrl('/user/profile'), {
			method: 'GET',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

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
 * @param {string} token - Authorization token
 * @param {number} userId - User ID to fetch profile for
 * @returns {Promise<any>} - Promise resolving to user profile data
 */
export async function getUserProfile(token, userId) {
	try {
		const response = await fetch(getApiUrl(`/admin/users/${userId}/profile`), {
			method: 'GET',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

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
 * @param {string} token - Authorization token
 * @param {number} userId - User ID to disable
 * @returns {Promise<any>} - Promise resolving to operation result
 */
export async function disableUser(token, userId) {
	try {
		const response = await fetch(getApiUrl(`/admin/users/${userId}/disable`), {
			method: 'PUT',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
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
 * @param {string} token - Authorization token
 * @param {number} userId - User ID to enable
 * @returns {Promise<any>} - Promise resolving to operation result
 */
export async function enableUser(token, userId) {
	try {
		const response = await fetch(getApiUrl(`/admin/users/${userId}/enable`), {
			method: 'PUT',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
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
 * @param {string} token - Authorization token
 * @param {number[]} userIds - Array of user IDs to disable
 * @returns {Promise<any>} - Promise resolving to bulk operation result
 */
export async function disableUsersBulk(token, userIds) {
	try {
		const response = await fetch(getApiUrl('/admin/users/disable-bulk'), {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
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
 * @param {string} token - Authorization token
 * @param {number[]} userIds - Array of user IDs to enable
 * @returns {Promise<any>} - Promise resolving to bulk operation result
 */
export async function enableUsersBulk(token, userIds) {
	try {
		const response = await fetch(getApiUrl('/admin/users/enable-bulk'), {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
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
 * @param {string} token - Authorization token
 * @param {number} userId - User ID to check
 * @returns {Promise<any>} - Promise resolving to dependencies info
 */
export async function checkUserDependencies(token, userId) {
	try {
		const response = await fetch(getApiUrl(`/admin/users/${userId}/dependencies`), {
			method: 'GET',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

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
 * @param {string} token - Authorization token
 * @param {number} userId - User ID to delete
 * @returns {Promise<any>} - Promise resolving to operation result
 */
export async function deleteUser(token, userId) {
	try {
		const response = await fetch(getApiUrl(`/admin/users/${userId}`), {
			method: 'DELETE',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
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
