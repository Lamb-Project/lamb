import { browser } from '$app/environment';
import { apiFetch } from '$lib/services/apiClient';

async function authenticatedFetch(url, options = {}) {
    return apiFetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
}

/**
 * @typedef {Object} Rubric
 * @property {number} id
 * @property {string} rubricId
 * @property {string} title
 * @property {string} description
 * @property {string} subject
 * @property {string} gradeLevel
 * @property {string} ownerEmail
 * @property {number} organizationId
 * @property {boolean} isPublic
 * @property {boolean} isShowcase
 * @property {string} rubricData
 * @property {number} createdAt
 * @property {number} updatedAt
 */

/**
 * @typedef {Object} RubricData
 * @property {string} rubricId
 * @property {string} title
 * @property {string} description
 * @property {Object} metadata
 * @property {Array} criteria
 * @property {string} scoringType
 * @property {number} maxScore
 */

export async function fetchRubrics(limit = 10, offset = 0, filters = {}) {
    if (!browser) {
        throw new Error('fetchRubrics called outside browser context');
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

    const response = await authenticatedFetch(`/rubrics?${params}`);

    if (!response.ok) {
        let errorDetail = 'Failed to fetch rubrics';
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

export async function fetchPublicRubrics(limit = 10, offset = 0, filters = {}) {
    if (!browser) {
        throw new Error('fetchPublicRubrics called outside browser context');
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

    const response = await authenticatedFetch(`/rubrics/public?${params}`);

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

export async function fetchShowcaseRubrics() {
    if (!browser) {
        throw new Error('fetchShowcaseRubrics called outside browser context');
    }

    const response = await authenticatedFetch('/rubrics/showcase');

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

export async function fetchRubric(rubricId) {
    if (!browser) {
        throw new Error('fetchRubric called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}`);

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

export async function createRubric(rubricData) {
    if (!browser) {
        throw new Error('createRubric called outside browser context');
    }

    const formData = new FormData();
    formData.append('title', rubricData.title || '');
    formData.append('description', rubricData.description || '');
    formData.append('subject', rubricData.metadata?.subject || '');
    formData.append('gradeLevel', rubricData.metadata?.gradeLevel || '');
    formData.append('scoringType', rubricData.scoringType || 'points');
    formData.append('maxScore', (rubricData.maxScore || 100).toString());
    formData.append('criteria', JSON.stringify(rubricData.criteria || []));

    const response = await authenticatedFetch('/rubrics', {
        method: 'POST',
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

export async function updateRubric(rubricId, rubricData) {
    if (!browser) {
        throw new Error('updateRubric called outside browser context');
    }

    const formData = new FormData();
    formData.append('title', rubricData.title || '');
    formData.append('description', rubricData.description || '');
    formData.append('subject', rubricData.metadata?.subject || '');
    formData.append('gradeLevel', rubricData.metadata?.gradeLevel || '');
    formData.append('scoringType', rubricData.scoringType || 'points');
    formData.append('maxScore', (rubricData.maxScore || 100).toString());
    formData.append('criteria', JSON.stringify(rubricData.criteria || []));

    const response = await authenticatedFetch(`/rubrics/${rubricId}`, {
        method: 'PUT',
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

export async function deleteRubric(rubricId) {
    if (!browser) {
        throw new Error('deleteRubric called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}`, {
        method: 'DELETE'
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

export async function duplicateRubric(rubricId) {
    if (!browser) {
        throw new Error('duplicateRubric called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}/duplicate`, {
        method: 'POST'
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

export async function toggleRubricVisibility(rubricId, isPublic) {
    if (!browser) {
        throw new Error('toggleRubricVisibility called outside browser context');
    }

    const formData = new FormData();
    formData.append('is_public', isPublic.toString());

    const response = await authenticatedFetch(`/rubrics/${rubricId}/visibility`, {
        method: 'PUT',
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

export async function setShowcaseStatus(rubricId, isShowcase) {
    if (!browser) {
        throw new Error('setShowcaseStatus called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}/showcase`, {
        method: 'PUT',
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

export async function exportRubricJSON(rubricId) {
    if (!browser) {
        throw new Error('exportRubricJSON called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}/export/json`);

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

    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

export async function fetchRubricMarkdown(rubricId) {
    if (!browser) {
        throw new Error('fetchRubricMarkdown called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}/export/markdown`);

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

export async function exportRubricMarkdown(rubricId) {
    if (!browser) {
        throw new Error('exportRubricMarkdown called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}/export/markdown`);

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

    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

export async function importRubric(file) {
    if (!browser) {
        throw new Error('importRubric called outside browser context');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await authenticatedFetch('/rubrics/import', {
        method: 'POST',
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

export async function aiGenerateRubric(prompt, language = 'en', model = null) {
    if (!browser) {
        throw new Error('aiGenerateRubric called outside browser context');
    }

    const requestBody = { prompt, language };
    if (model) {
        requestBody.model = model;
    }

    const response = await authenticatedFetch('/rubrics/ai-generate', {
        method: 'POST',
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        let errorDetail = 'Failed to generate rubric with AI';
        try {
            const error = await response.json();
            errorDetail = error?.detail || error?.error || errorDetail;
        } catch (e) {
            // Ignore
        }
        console.error('API error response status:', response.status, 'Detail:', errorDetail);
        throw new Error(errorDetail);
    }

    const result = await response.json();

    if (!result.success && result.error) {
        console.warn('AI generation failed:', result.error);
    }

    return result;
}

export async function aiModifyRubric(rubricId, prompt) {
    if (!browser) {
        throw new Error('aiModifyRubric called outside browser context');
    }

    const response = await authenticatedFetch(`/rubrics/${rubricId}/ai-modify`, {
        method: 'POST',
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

export async function fetchAccessibleRubrics() {
    const response = await authenticatedFetch('/rubrics/accessible');

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
