/**
 * Organization admin utilities
 */

/**
 * Check if user has organization admin privileges
 * @param {object} userData - User data from store
 * @returns {Promise<boolean>} - True if user is organization admin
 */
export async function isOrganizationAdmin(userData) {
    if (!userData.isLoggedIn || !userData.token) {
        return false;
    }

    try {
        const response = await fetch('/creator/admin/org-admin/dashboard', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${userData.token}`,
                'Content-Type': 'application/json'
            }
        });

        return response.status === 200;
    } catch (error) {
        console.error('Error checking organization admin status:', error);
        return false;
    }
}

/**
 * Get organization admin info
 * @param {object} userData - User data from store
 * @returns {Promise<object|null>} - Organization admin info or null
 */
export async function getOrganizationAdminInfo(userData) {
    if (!userData.isLoggedIn || !userData.token) {
        return null;
    }

    try {
        const response = await fetch('/creator/admin/org-admin/dashboard', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${userData.token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.status === 200) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Error getting organization admin info:', error);
        return null;
    }
}