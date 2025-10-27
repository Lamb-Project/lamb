/**
 * Template Service
 * 
 * Handles API communication for prompt templates management.
 * All methods require authentication via JWT token.
 */

import axios from 'axios';
import { getConfig } from '../config';

const config = getConfig();
const API_BASE = config.api.lambServer;
const TEMPLATES_BASE = `${API_BASE}/creator/prompt-templates`;

/**
 * Get authorization headers with JWT token
 */
function getAuthHeaders() {
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('No authentication token found');
    }
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

/**
 * List user's own templates
 * @param {number} limit - Number of templates per page
 * @param {number} offset - Offset for pagination
 * @returns {Promise<{templates: Array, total: number, page: number, limit: number}>}
 */
export async function listUserTemplates(limit = 50, offset = 0) {
    try {
        const response = await axios.get(`${TEMPLATES_BASE}/list`, {
            headers: getAuthHeaders(),
            params: { limit, offset }
        });
        return response.data;
    } catch (error) {
        console.error('Error listing user templates:', error);
        throw error;
    }
}

/**
 * List shared templates in organization
 * @param {number} limit - Number of templates per page
 * @param {number} offset - Offset for pagination
 * @returns {Promise<{templates: Array, total: number, page: number, limit: number}>}
 */
export async function listSharedTemplates(limit = 50, offset = 0) {
    try {
        const response = await axios.get(`${TEMPLATES_BASE}/shared`, {
            headers: getAuthHeaders(),
            params: { limit, offset }
        });
        return response.data;
    } catch (error) {
        console.error('Error listing shared templates:', error);
        throw error;
    }
}

/**
 * Get template by ID
 * @param {number} templateId - Template ID
 * @returns {Promise<Object>} Template object
 */
export async function getTemplate(templateId) {
    try {
        const response = await axios.get(`${TEMPLATES_BASE}/${templateId}`, {
            headers: getAuthHeaders()
        });
        return response.data;
    } catch (error) {
        console.error('Error getting template:', error);
        throw error;
    }
}

/**
 * Create a new template
 * @param {Object} templateData - Template data
 * @param {string} templateData.name - Template name (required)
 * @param {string} templateData.description - Description (optional)
 * @param {string} templateData.system_prompt - System prompt (optional)
 * @param {string} templateData.prompt_template - Prompt template (optional)
 * @param {boolean} templateData.is_shared - Share with organization (default: false)
 * @returns {Promise<Object>} Created template
 */
export async function createTemplate(templateData) {
    try {
        const response = await axios.post(`${TEMPLATES_BASE}/create`, templateData, {
            headers: getAuthHeaders()
        });
        return response.data;
    } catch (error) {
        console.error('Error creating template:', error);
        throw error;
    }
}

/**
 * Update an existing template
 * @param {number} templateId - Template ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated template
 */
export async function updateTemplate(templateId, updates) {
    try {
        const response = await axios.put(`${TEMPLATES_BASE}/${templateId}`, updates, {
            headers: getAuthHeaders()
        });
        return response.data;
    } catch (error) {
        console.error('Error updating template:', error);
        throw error;
    }
}

/**
 * Delete a template
 * @param {number} templateId - Template ID
 * @returns {Promise<void>}
 */
export async function deleteTemplate(templateId) {
    try {
        await axios.delete(`${TEMPLATES_BASE}/${templateId}`, {
            headers: getAuthHeaders()
        });
    } catch (error) {
        console.error('Error deleting template:', error);
        throw error;
    }
}

/**
 * Duplicate a template
 * @param {number} templateId - Template ID to duplicate
 * @param {string} newName - Optional new name (will use "Copy of..." if not provided)
 * @returns {Promise<Object>} New template
 */
export async function duplicateTemplate(templateId, newName = null) {
    try {
        const response = await axios.post(
            `${TEMPLATES_BASE}/${templateId}/duplicate`,
            { new_name: newName },
            { headers: getAuthHeaders() }
        );
        return response.data;
    } catch (error) {
        console.error('Error duplicating template:', error);
        throw error;
    }
}

/**
 * Toggle sharing status of a template
 * @param {number} templateId - Template ID
 * @param {boolean} isShared - New sharing status
 * @returns {Promise<Object>} Updated template
 */
export async function toggleTemplateSharing(templateId, isShared) {
    try {
        const response = await axios.put(
            `${TEMPLATES_BASE}/${templateId}/share`,
            { is_shared: isShared },
            { headers: getAuthHeaders() }
        );
        return response.data;
    } catch (error) {
        console.error('Error toggling template sharing:', error);
        throw error;
    }
}

/**
 * Export templates as JSON
 * @param {Array<number>} templateIds - Array of template IDs to export
 * @returns {Promise<Object>} Export data with templates array
 */
export async function exportTemplates(templateIds) {
    try {
        const response = await axios.post(
            `${TEMPLATES_BASE}/export`,
            { template_ids: templateIds },
            { headers: getAuthHeaders() }
        );
        return response.data;
    } catch (error) {
        console.error('Error exporting templates:', error);
        throw error;
    }
}

/**
 * Download exported templates as JSON file
 * @param {Array<number>} templateIds - Array of template IDs to export
 * @param {string} filename - Optional filename (default: prompt-templates-export.json)
 */
export async function downloadTemplatesExport(templateIds, filename = 'prompt-templates-export.json') {
    try {
        const exportData = await exportTemplates(templateIds);
        
        // Create blob and download
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Error downloading templates export:', error);
        throw error;
    }
}

