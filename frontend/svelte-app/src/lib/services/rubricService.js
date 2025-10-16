import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/**
 * Get authentication token from localStorage
 * @returns {string} The token
 */
function getAuthToken() {
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }
    return token;
}

/**
 * Make authenticated fetch request
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} The fetch response
 */
async function authenticatedFetch(url, options = {}) {
    const token = getAuthToken();

    const defaultOptions = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    };

    return fetch(url, { ...defaultOptions, ...options });
}

/**
 * @typedef {Object} Rubric - Defines the structure of a rubric object
 * @property {number} id - Internal database ID
 * @property {string} rubricId - External UUID identifier
 * @property {string} title - Rubric title
 * @property {string} description - Rubric description
 * @property {string} subject - Academic subject
 * @property {string} gradeLevel - Target grade level
 * @property {string} ownerEmail - Creator's email
 * @property {number} organizationId - Organization ID
 * @property {boolean} isPublic - Whether rubric is visible to organization
 * @property {boolean} isShowcase - Whether marked as showcase template
 * @property {string} rubricData - JSON string of full rubric structure
 * @property {number} createdAt - Unix timestamp
 * @property {number} updatedAt - Unix timestamp
 */

/**
 * @typedef {Object} RubricData - The complete rubric JSON structure
 * @property {string} rubricId - Unique identifier
 * @property {string} title - Rubric title
 * @property {string} description - Rubric description
 * @property {Object} metadata - Rubric metadata
 * @property {Array} criteria - Array of criterion objects
 * @property {string} scoringType - Type of scoring (points, percentage, etc.)
 * @property {number} maxScore - Maximum possible score
 */

/**
 * Fetch all rubrics for the current user
 * @param {number} [limit=10] - Number of rubrics per page
 * @param {number} [offset=0] - Offset for pagination
 * @param {Object} [filters={}] - Optional filters (subject, gradeLevel, etc.)
 * @returns {Promise<{rubrics: Rubric[], total: number}>}
 * @throws {Error} If not authenticated or fetch fails
 */
export async function fetchRubrics(limit = 10, offset = 0, filters = {}) {
    if (!browser) {
        throw new Error('fetchRubrics called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    // Build query parameters
    const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString()
    });

    // Add filters if provided
    Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            params.append(key, value.toString());
        }
    });

    const apiUrl = getApiUrl(`/rubrics?${params}`);
    console.log('Fetching rubrics from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        let errorDetail = 'Failed to fetch rubrics';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore if response is not JSON
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const data = await response.json();

    // Return expected structure
    return {
        rubrics: Array.isArray(data?.rubrics) ? data.rubrics : [],
        total: typeof data?.total === 'number' ? data.total : 0
    };
}

/**
 * Fetch public rubrics in the organization
 * @param {number} [limit=10] - Number of rubrics per page
 * @param {number} [offset=0] - Offset for pagination
 * @param {Object} [filters={}] - Optional filters
 * @returns {Promise<{rubrics: Rubric[], total: number}>}
 * @throws {Error} If not authenticated or fetch fails
 */
export async function fetchPublicRubrics(limit = 10, offset = 0, filters = {}) {
    if (!browser) {
        throw new Error('fetchPublicRubrics called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString()
    });

    Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            params.append(key, value.toString());
        }
    });

    const apiUrl = getApiUrl(`/rubrics/public?${params}`);
    console.log('Fetching public rubrics from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        let errorDetail = 'Failed to fetch public rubrics';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const data = await response.json();
    return {
        rubrics: Array.isArray(data?.rubrics) ? data.rubrics : [],
        total: typeof data?.total === 'number' ? data.total : 0
    };
}

/**
 * Fetch showcase templates
 * @returns {Promise<Rubric[]>}
 * @throws {Error} If not authenticated or fetch fails
 */
export async function fetchShowcaseRubrics() {
    if (!browser) {
        throw new Error('fetchShowcaseRubrics called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl('/rubrics/showcase');
    console.log('Fetching showcase rubrics from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        let errorDetail = 'Failed to fetch showcase rubrics';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const data = await response.json();
    return Array.isArray(data?.rubrics) ? data.rubrics : [];
}

/**
 * Fetch a single rubric by ID
 * @param {string} rubricId - The rubric ID
 * @returns {Promise<Rubric>} The rubric details
 * @throws {Error} If not authenticated, not found, or fetch fails
 */
export async function fetchRubric(rubricId) {
    if (!browser) {
        throw new Error('fetchRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}`);
    console.log('Fetching rubric from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        let errorDetail = `Failed to fetch rubric with ID ${rubricId}`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Create a new rubric
 * @param {RubricData} rubricData - The rubric data to create
 * @returns {Promise<Rubric>} The created rubric
 * @throws {Error} If not authenticated or creation fails
 */
export async function createRubric(rubricData) {
    if (!browser) {
        throw new Error('createRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    // Convert rubric data to form data format expected by backend
    const formData = new FormData();
    formData.append('title', rubricData.title || '');
    formData.append('description', rubricData.description || '');
    formData.append('subject', rubricData.metadata?.subject || '');
    formData.append('gradeLevel', rubricData.metadata?.gradeLevel || '');
    formData.append('scoringType', rubricData.scoringType || 'points');
    formData.append('maxScore', (rubricData.maxScore || 100).toString());
    formData.append('criteria', JSON.stringify(rubricData.criteria || []));

    const apiUrl = getApiUrl('/rubrics');
    console.log('Creating rubric at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
            // Don't set Content-Type for FormData, let browser set it
        },
        body: formData
    });

    if (!response.ok) {
        let errorDetail = 'Failed to create rubric';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Update an existing rubric
 * @param {string} rubricId - The rubric ID to update
 * @param {RubricData} rubricData - The updated rubric data
 * @returns {Promise<Rubric>} The updated rubric
 * @throws {Error} If not authenticated, not owner, or update fails
 */
export async function updateRubric(rubricId, rubricData) {
    if (!browser) {
        throw new Error('updateRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    // Convert to form data
    const formData = new FormData();
    formData.append('title', rubricData.title || '');
    formData.append('description', rubricData.description || '');
    formData.append('subject', rubricData.metadata?.subject || '');
    formData.append('gradeLevel', rubricData.metadata?.gradeLevel || '');
    formData.append('scoringType', rubricData.scoringType || 'points');
    formData.append('maxScore', (rubricData.maxScore || 100).toString());

    // Keep IDs in criteria (backend validator requires them)
    formData.append('criteria', JSON.stringify(rubricData.criteria || []));

    const apiUrl = getApiUrl(`/rubrics/${rubricId}`);
    console.log('Updating rubric at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
    });

    if (!response.ok) {
        let errorDetail = `Failed to update rubric with ID ${rubricId}`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Delete a rubric
 * @param {string} rubricId - The rubric ID to delete
 * @returns {Promise<boolean>} True if deleted successfully
 * @throws {Error} If not authenticated, not owner, or delete fails
 */
export async function deleteRubric(rubricId) {
    if (!browser) {
        throw new Error('deleteRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}`);
    console.log('Deleting rubric at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!response.ok) {
        let errorDetail = `Failed to delete rubric with ID ${rubricId}`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return true;
}

/**
 * Duplicate a rubric
 * @param {string} rubricId - The rubric ID to duplicate
 * @returns {Promise<Rubric>} The new duplicated rubric
 * @throws {Error} If not authenticated or duplication fails
 */
export async function duplicateRubric(rubricId) {
    if (!browser) {
        throw new Error('duplicateRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/duplicate`);
    console.log('Duplicating rubric at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!response.ok) {
        let errorDetail = `Failed to duplicate rubric with ID ${rubricId}`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Toggle rubric visibility (public/private)
 * @param {string} rubricId - The rubric ID
 * @param {boolean} isPublic - Whether to make it public
 * @returns {Promise<Rubric>} The updated rubric
 * @throws {Error} If not authenticated or toggle fails
 */
export async function toggleRubricVisibility(rubricId, isPublic) {
    if (!browser) {
        throw new Error('toggleRubricVisibility called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/visibility`);
    console.log('Toggling rubric visibility at:', apiUrl);

    // Use form data as expected by Creator Interface
    const formData = new FormData();
    formData.append('is_public', isPublic.toString());

    const response = await fetch(apiUrl, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`
            // Don't set Content-Type - let browser set it for FormData
        },
        body: formData
    });

    if (!response.ok) {
        let errorDetail = `Failed to toggle visibility for rubric ${rubricId}`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Set showcase status for a rubric (admin only)
 * @param {string} rubricId - The rubric ID
 * @param {boolean} isShowcase - Whether to mark as showcase
 * @returns {Promise<Rubric>} The updated rubric
 * @throws {Error} If not admin or operation fails
 */
export async function setShowcaseStatus(rubricId, isShowcase) {
    if (!browser) {
        throw new Error('setShowcaseStatus called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/showcase`);
    console.log('Setting showcase status at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ isShowcase })
    });

    if (!response.ok) {
        let errorDetail = `Failed to set showcase status for rubric ${rubricId}`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Export rubric as JSON
 * @param {string} rubricId - The rubric ID to export
 * @returns {Promise<void>} Triggers download
 * @throws {Error} If not authenticated or export fails
 */
export async function exportRubricJSON(rubricId) {
    if (!browser) {
        throw new Error('exportRubricJSON called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/export/json`);
    console.log('Exporting rubric JSON from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!response.ok) {
        let errorDetail = 'Failed to export rubric as JSON';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition');
    let filename = `rubric-${rubricId}.json`;

    if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/i);
        if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1];
        }
    }

    // Create download link
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

/**
 * Fetch rubric markdown content as text (for display, not download)
 * @param {string} rubricId - The rubric ID to fetch
 * @returns {Promise<string>} The markdown content
 * @throws {Error} If not authenticated or fetch fails
 */
export async function fetchRubricMarkdown(rubricId) {
    if (!browser) {
        throw new Error('fetchRubricMarkdown called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/export/markdown`);
    console.log('Fetching rubric Markdown from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!response.ok) {
        let errorDetail = 'Failed to fetch rubric as Markdown';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const text = await response.text();
    return text;
}

/**
 * Export rubric as Markdown
 * @param {string} rubricId - The rubric ID to export
 * @returns {Promise<void>} Triggers download
 * @throws {Error} If not authenticated or export fails
 */
export async function exportRubricMarkdown(rubricId) {
    if (!browser) {
        throw new Error('exportRubricMarkdown called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/export/markdown`);
    console.log('Exporting rubric Markdown from:', apiUrl);

    const response = await fetch(apiUrl, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!response.ok) {
        let errorDetail = 'Failed to export rubric as Markdown';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition');
    let filename = `rubric-${rubricId}.md`;

    if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/i);
        if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1];
        }
    }

    // Create download link
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

/**
 * Import rubric from JSON file
 * @param {File} file - The JSON file to import
 * @returns {Promise<Rubric>} The imported rubric
 * @throws {Error} If not authenticated, file invalid, or import fails
 */
export async function importRubric(file) {
    if (!browser) {
        throw new Error('importRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    // Create form data with file
    const formData = new FormData();
    formData.append('file', file);

    const apiUrl = getApiUrl('/rubrics/import');
    console.log('Importing rubric at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
    });

    if (!response.ok) {
        let errorDetail = 'Failed to import rubric';
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Generate rubric using AI from natural language prompt
 * @param {string} prompt - Natural language description of desired rubric
 * @returns {Promise<{rubric: RubricData, explanation: string}>}
 * @throws {Error} If not authenticated or generation fails
 */
/**
 * Generate a new rubric using AI (returns preview, does not save)
 * @param {string} prompt - Natural language description of desired rubric
 * @param {string} language - Language code (en, es, eu, ca) - defaults to 'en'
 * @param {string} model - Optional specific model override
 * @returns {Promise<{success: boolean, rubric: Object, markdown: string, explanation: string, prompt_used: string}>}
 * @throws {Error} If not authenticated or generation fails
 */
export async function aiGenerateRubric(prompt, language = 'en', model = null) {
    if (!browser) {
        throw new Error('aiGenerateRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl('/rubrics/ai-generate');
    console.log('Generating rubric with AI at:', apiUrl, 'language:', language);

    const requestBody = { prompt, language };
    if (model) {
        requestBody.model = model;
    }

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        let errorDetail = 'Failed to generate rubric with AI';
        try {
            const error = await response.json();
            errorDetail = error?.detail || error?.error || errorDetail;
        } catch (e) {
            // Ignore JSON parse error
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const result = await response.json();
    
    // Handle both success and failure responses
    if (!result.success && result.error) {
        console.warn('AI generation failed:', result.error);
    }
    
    return result;
}

/**
 * Modify existing rubric using AI
 * @param {string} rubricId - The rubric ID to modify
 * @param {string} prompt - Natural language modification instructions
 * @returns {Promise<{rubric: RubricData, explanation: string, changes_summary: Object}>}
 * @throws {Error} If not authenticated or modification fails
 */
export async function aiModifyRubric(rubricId, prompt) {
    if (!browser) {
        throw new Error('aiModifyRubric called outside browser context');
    }
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('Not authenticated');
    }

    const apiUrl = getApiUrl(`/rubrics/${rubricId}/ai-modify`);
    console.log('Modifying rubric with AI at:', apiUrl);

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt })
    });

    if (!response.ok) {
        let errorDetail = `Failed to modify rubric ${rubricId} with AI`;
        try {
            const error = await response.json();
            errorDetail = error?.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}

/**
 * Fetch accessible rubrics for assistant attachment
 * @returns {Promise<{rubrics: Array, total: number}>}
 */
export async function fetchAccessibleRubrics() {
    const response = await authenticatedFetch(`${getApiUrl('/rubrics/accessible')}`);

    if (!response.ok) {
        let errorDetail = "Failed to fetch accessible rubrics";
        try {
            const errorData = await response.json();
            errorDetail = errorData.detail || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error("API error response status:", response.status, "Detail:", errorDetail);
        throw new Error(errorDetail);
    }

    return await response.json();
}
