import { apiFetch } from '$lib/services/apiClient';

/**
 * Get list of all assistants in the organization
 * @param {string} token - Authorization token
 * @returns {Promise<any>} - Promise resolving to assistants list
 */
export async function getOrganizationAssistants(token) {
  try {
    const response = await apiFetch('/admin/org-admin/assistants', {
      method: 'GET',
      token,
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch organization assistants');
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching organization assistants:', error);
    throw error;
  }
}
