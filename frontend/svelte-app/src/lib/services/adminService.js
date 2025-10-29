import { getApiUrl } from '$lib/config';

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
        'Authorization': `Bearer ${token}`,
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
        'Authorization': `Bearer ${token}`,
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
        'Authorization': `Bearer ${token}`,
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
        'Authorization': `Bearer ${token}`,
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

