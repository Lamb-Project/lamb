/**
 * @module libraryService
 * API service for library management endpoints (/creator/libraries/).
 *
 * Follows the same pattern as knowledgeBaseService.js: axios with Bearer
 * token auth, getApiUrl() for base URL, browser-only checks.
 */

import axios from 'axios';
import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/**
 * @typedef {Object} Library
 * @property {string} id
 * @property {string} name
 * @property {string} description
 * @property {number} organization_id
 * @property {number} owner_user_id
 * @property {boolean} is_shared
 * @property {number} item_count
 * @property {boolean} [is_owner]
 * @property {string} [owner_name]
 * @property {string} [owner_email]
 * @property {number} created_at
 * @property {number} updated_at
 */

/**
 * @typedef {Object} LibraryItem
 * @property {string} id
 * @property {string} title
 * @property {string} source_type
 * @property {string} [original_filename]
 * @property {string} [content_type]
 * @property {number} [file_size]
 * @property {string} import_plugin
 * @property {string} status
 * @property {number} [page_count]
 * @property {number} [image_count]
 * @property {string} [permalink_base]
 * @property {Object} [metadata]
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * @typedef {Object} ImportPlugin
 * @property {string} name
 * @property {string} description
 * @property {string[]} supported_source_types
 */

/**
 * Return auth headers using the stored token.
 * @returns {{ Authorization: string }}
 * @throws {Error} If no token is available.
 */
function authHeaders() {
    const token = localStorage.getItem('userToken');
    if (!token) {
        throw new Error('User not authenticated.');
    }
    return { Authorization: `Bearer ${token}` };
}

/**
 * Extract a human-readable error message from an axios error.
 * @param {unknown} error
 * @param {string} fallback
 * @returns {string}
 */
function errorMessage(error, fallback) {
    if (axios.isAxiosError(error) && error.response) {
        return error.response.data?.detail || error.response.data?.message || `Request failed (${error.response.status})`;
    }
    if (error instanceof Error) {
        return error.message;
    }
    return fallback;
}

// ---------------------------------------------------------------------------
// Library CRUD
// ---------------------------------------------------------------------------

/**
 * List libraries accessible to the current user (owned + shared).
 * @returns {Promise<Library[]>}
 */
export async function getLibraries() {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl('/libraries');
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data?.libraries ?? [];
}

/**
 * Get details for a single library.
 * @param {string} libraryId
 * @returns {Promise<Library>}
 */
export async function getLibrary(libraryId) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}`);
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data;
}

/**
 * Create a new library.
 * @param {{ name: string, description?: string }} data
 * @returns {Promise<Library>}
 */
export async function createLibrary(data) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl('/libraries');
    const response = await axios.post(url, data, { headers: { ...authHeaders(), 'Content-Type': 'application/json' } });
    return response.data;
}

/**
 * Update a library's name and/or description.
 * @param {string} libraryId
 * @param {{ name?: string, description?: string }} data
 * @returns {Promise<Library>}
 */
export async function updateLibrary(libraryId, data) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}`);
    const response = await axios.put(url, data, { headers: { ...authHeaders(), 'Content-Type': 'application/json' } });
    return response.data;
}

/**
 * Delete a library and all its content.
 * @param {string} libraryId
 * @returns {Promise<{ message: string }>}
 */
export async function deleteLibrary(libraryId) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}`);
    const response = await axios.delete(url, { headers: authHeaders() });
    return response.data;
}

/**
 * Toggle organization-wide sharing for a library.
 * @param {string} libraryId
 * @param {boolean} isShared
 * @returns {Promise<{ library_id: string, is_shared: boolean, message: string }>}
 */
export async function toggleSharing(libraryId, isShared) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/share`);
    const response = await axios.put(url, { is_shared: isShared }, { headers: { ...authHeaders(), 'Content-Type': 'application/json' } });
    return response.data;
}

// ---------------------------------------------------------------------------
// Content importing
// ---------------------------------------------------------------------------

/**
 * Upload a file for import into a library.
 * @param {string} libraryId
 * @param {File} file
 * @param {{ pluginName?: string, title?: string }} [options]
 * @returns {Promise<{ item_id: string, job_id: string, status: string }>}
 */
export async function uploadFile(libraryId, file, options = {}) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/upload`);
    const form = new FormData();
    form.append('file', file);
    if (options.title) form.append('title', options.title);
    if (options.pluginName) form.append('plugin_name', options.pluginName);
    const response = await axios.post(url, form, { headers: authHeaders(), timeout: 120_000 });
    return response.data;
}

/**
 * Import content from a URL.
 * @param {string} libraryId
 * @param {{ url: string, pluginName?: string, title?: string }} data
 * @returns {Promise<{ item_id: string, job_id: string, status: string }>}
 */
export async function importUrl(libraryId, data) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/import-url`);
    const body = {
        url: data.url,
        plugin_name: data.pluginName || 'url_import',
        title: data.title || data.url,
    };
    const response = await axios.post(url, body, { headers: { ...authHeaders(), 'Content-Type': 'application/json' } });
    return response.data;
}

/**
 * Import a YouTube video transcript.
 * @param {string} libraryId
 * @param {{ videoUrl: string, language?: string, title?: string }} data
 * @returns {Promise<{ item_id: string, job_id: string, status: string }>}
 */
export async function importYouTube(libraryId, data) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/import-youtube`);
    const body = {
        video_url: data.videoUrl,
        language: data.language || 'en',
        title: data.title || data.videoUrl,
        plugin_name: 'youtube_transcript_import',
    };
    const response = await axios.post(url, body, { headers: { ...authHeaders(), 'Content-Type': 'application/json' } });
    return response.data;
}

// ---------------------------------------------------------------------------
// Content items
// ---------------------------------------------------------------------------

/**
 * List items in a library.
 * @param {string} libraryId
 * @param {{ limit?: number, offset?: number, status?: string }} [params]
 * @returns {Promise<{ items: LibraryItem[], total: number }>}
 */
export async function getItems(libraryId, params = {}) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/items`);
    const response = await axios.get(url, { headers: authHeaders(), params });
    return response.data;
}

/**
 * Get details of a single item.
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<LibraryItem>}
 */
export async function getItem(libraryId, itemId) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}`);
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data;
}

/**
 * Get the import status for an item.
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<{ item_id: string, status: string, error_message?: string }>}
 */
export async function getItemStatus(libraryId, itemId) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}/status`);
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data;
}

/**
 * Delete an item from a library.
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<{ message: string }>}
 */
export async function deleteItem(libraryId, itemId) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}`);
    const response = await axios.delete(url, { headers: authHeaders() });
    return response.data;
}

// ---------------------------------------------------------------------------
// Plugins
// ---------------------------------------------------------------------------

/**
 * List available import plugins.
 * @returns {Promise<ImportPlugin[]>}
 */
export async function getPlugins() {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl('/libraries/plugins');
    const response = await axios.get(url, { headers: authHeaders() });
    return response.data?.plugins ?? [];
}

// ---------------------------------------------------------------------------
// Export / Import
// ---------------------------------------------------------------------------

/**
 * Export a library as a ZIP file and trigger browser download.
 * @param {string} libraryId
 * @param {string} [filename]
 * @returns {Promise<void>}
 */
export async function exportLibrary(libraryId, filename) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl(`/libraries/${libraryId}/export`);
    const response = await axios.get(url, {
        headers: authHeaders(),
        responseType: 'blob',
        timeout: 300_000,
    });
    const blob = new Blob([response.data], { type: 'application/zip' });
    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename || `library-${libraryId.slice(0, 8)}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
}

/**
 * Import a library from a ZIP file.
 * @param {File} file
 * @returns {Promise<{ library_id: string, library_name: string, item_count: number }>}
 */
export async function importLibrary(file) {
    if (!browser) throw new Error('Browser only.');
    const url = getApiUrl('/libraries/import');
    const form = new FormData();
    form.append('file', file);
    const response = await axios.post(url, form, { headers: authHeaders(), timeout: 300_000 });
    return response.data;
}
