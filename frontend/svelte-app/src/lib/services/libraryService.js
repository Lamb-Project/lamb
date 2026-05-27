/**
 * @module libraryService
 * API service for library management endpoints (/creator/libraries/).
 *
 * Follows the same pattern as knowledgeBaseService.js: axios with Bearer
 * token auth, getApiUrl() for base URL, browser-only checks.
 */

// Shared axios instance with global 401 handling (#352, M1/M2/M3).
import { apiAxios as axios } from '$lib/services/apiClient';
import { isAxiosError } from 'axios';
axios.isAxiosError = isAxiosError;
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
		return (
			error.response.data?.detail ||
			error.response.data?.message ||
			`Request failed (${error.response.status})`
		);
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
	const response = await axios.post(url, data, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' }
	});
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
	const response = await axios.put(url, data, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' }
	});
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
	const response = await axios.put(
		url,
		{ is_shared: isShared },
		{ headers: { ...authHeaders(), 'Content-Type': 'application/json' } }
	);
	return response.data;
}

// ---------------------------------------------------------------------------
// Content importing
// ---------------------------------------------------------------------------

/**
 * Upload a file for import into a library.
 *
 * The ``params`` field carries plugin-specific options declared by the
 * import plugin's ``get_parameters()`` schema. Empty or missing → backend
 * applies each parameter's schema default. The renderer at
 * ``components/plugins/PluginParamFields.svelte`` produces this dict.
 *
 * @param {string} libraryId
 * @param {File} file
 * @param {{ pluginName?: string, title?: string, params?: Record<string, unknown> }} [options]
 * @returns {Promise<{ item_id: string, job_id: string, status: string }>}
 */
export async function uploadFile(libraryId, file, options = {}) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/upload`);
	const form = new FormData();
	form.append('file', file);
	if (options.title) form.append('title', options.title);
	if (options.pluginName) form.append('plugin_name', options.pluginName);
	if (options.params && Object.keys(options.params).length > 0) {
		form.append('plugin_params', JSON.stringify(options.params));
	}
	if (options.folderId) form.append('folder_id', options.folderId);
	const response = await axios.post(url, form, { headers: authHeaders(), timeout: 120_000 });
	return response.data;
}

/**
 * Import content from a URL.
 *
 * Callers MUST pass ``pluginName`` — the appropriate plugin is discovered
 * via {@link getPlugins} (filter by ``source_type === 'url'``). The service
 * does not pick a default plugin so that adding a new URL plugin doesn't
 * silently route around the caller's choice.
 *
 * @param {string} libraryId
 * @param {{ url: string, pluginName: string, title?: string, params?: Record<string, unknown> }} data
 * @returns {Promise<{ item_id: string, job_id: string, status: string }>}
 * @throws {Error} If ``pluginName`` is missing.
 */
export async function importUrl(libraryId, data) {
	if (!browser) throw new Error('Browser only.');
	if (!data?.pluginName) {
		throw new Error(
			'importUrl: pluginName is required. Pass an explicit plugin name from /libraries/plugins.'
		);
	}
	const url = getApiUrl(`/libraries/${libraryId}/import-url`);
	const body = {
		url: data.url,
		plugin_name: data.pluginName,
		title: data.title || data.url,
		plugin_params: data.params || {}
	};
	const response = await axios.post(url, body, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' }
	});
	return response.data;
}

/**
 * Import a YouTube video transcript.
 *
 * Like {@link importUrl}, callers MUST pass ``pluginName`` (discovered via
 * {@link getPlugins} filtered by ``source_type === 'youtube'``). No silent
 * default — the plugin name comes from the registry, not the frontend.
 *
 * Plugin-specific options (``language``, ``proxy_url``, anything a future
 * YouTube plugin declares) live in ``params``. The legacy top-level
 * ``language`` is still accepted but folded into ``plugin_params`` for the
 * router so a single transport carries everything.
 *
 * @param {string} libraryId
 * @param {{ videoUrl: string, pluginName: string, language?: string, title?: string, params?: Record<string, unknown> }} data
 * @returns {Promise<{ item_id: string, job_id: string, status: string }>}
 * @throws {Error} If ``pluginName`` is missing.
 */
export async function importYouTube(libraryId, data) {
	if (!browser) throw new Error('Browser only.');
	if (!data?.pluginName) {
		throw new Error(
			'importYouTube: pluginName is required. Pass an explicit plugin name from /libraries/plugins.'
		);
	}
	const url = getApiUrl(`/libraries/${libraryId}/import-youtube`);
	const params = { ...(data.params || {}) };
	if (data.language && !('language' in params)) {
		params.language = data.language;
	}
	const body = {
		video_url: data.videoUrl,
		title: data.title || data.videoUrl,
		plugin_name: data.pluginName,
		plugin_params: params
	};
	const response = await axios.post(url, body, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' }
	});
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
 * Get the rendered markdown content of an item.
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<string>} Raw markdown
 */
export async function getItemContent(libraryId, itemId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}/content`);
	const response = await axios.get(url, {
		headers: authHeaders(),
		params: { format: 'markdown' },
		responseType: 'text',
		transformResponse: (v) => v
	});
	return response.data;
}

/**
 * Result of {@link getItemOriginal}. One of:
 * - ``{ type: 'blob', blob, filename, contentType }`` — binary original
 *   resolved to a Blob (caller wraps with URL.createObjectURL to open).
 * - ``{ type: 'url', url, sourceType }`` — item has no binary original
 *   (URL / YouTube imports); caller should open ``url`` directly.
 * @typedef {{ type: 'blob', blob: Blob, filename: string, contentType: string }
 *           | { type: 'url', url: string, sourceType?: string }} ItemOriginal
 */

/**
 * @typedef {Object} LibraryKnowledgeStore
 * @property {string} id
 * @property {string} name
 * @property {string|null} [description]
 * @property {string} chunking_strategy
 * @property {string} embedding_vendor
 * @property {string} embedding_model
 * @property {string} vector_db_backend
 * @property {boolean} is_shared
 * @property {number} item_count
 * @property {number} ready_count
 * @property {number} failed_count
 * @property {'owner'|'shared'} access
 */

/**
 * List Knowledge Stores that reference any item from this library.
 *
 * Inverse of the per-KS content listing — useful for the LibraryDetail
 * page to surface which KSs are populated from the current library.
 * KSs the current user cannot access are filtered out server-side.
 *
 * @param {string} libraryId
 * @returns {Promise<LibraryKnowledgeStore[]>}
 */
export async function getLibraryKnowledgeStores(libraryId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/knowledge-stores`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data?.knowledge_stores ?? [];
}

/**
 * Resolve the original source for a library item.
 *
 * Binary imports stream the file with a Content-Disposition; URL / YouTube
 * imports return ``{ type: 'url' }`` so the caller can simply open the
 * source URL in a new tab without proxying.
 *
 * Throws when the item has neither a binary original nor a source URL, or
 * when the request fails for any other reason.
 *
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<ItemOriginal>}
 */
export async function getItemOriginal(libraryId, itemId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}/original`);
	try {
		const response = await axios.get(url, {
			headers: authHeaders(),
			responseType: 'blob',
			timeout: 300_000
		});
		const blob = response.data;
		// axios headers are typed as a union of string|number|object — coerce
		// to a string so the consumer always sees a plain MIME / filename.
		const contentType = String(response.headers['content-type'] || 'application/octet-stream');
		// Extract filename from Content-Disposition: prefer RFC 5987 filename*,
		// fall back to quoted filename. The backend sets both.
		const cd = String(response.headers['content-disposition'] || '');
		let filename = '';
		const m5987 = /filename\*=UTF-8''([^;]+)/i.exec(cd);
		if (m5987) {
			try {
				filename = decodeURIComponent(m5987[1]);
			} catch {
				filename = m5987[1];
			}
		}
		if (!filename) {
			const mPlain = /filename="([^"]+)"/i.exec(cd);
			if (mPlain) filename = mPlain[1];
		}
		if (!filename) filename = `${itemId}`;
		return { type: 'blob', blob, filename, contentType };
	} catch (error) {
		// 404 with structured body means the item has no binary original;
		// fall back to the source URL if the backend supplied one.
		if (axios.isAxiosError(error) && error.response?.status === 404) {
			// Body was fetched as blob; convert to JSON before reading.
			let detail = null;
			const data = error.response.data;
			if (data instanceof Blob) {
				try {
					const text = await data.text();
					const parsed = JSON.parse(text);
					detail = parsed?.detail;
				} catch {
					detail = null;
				}
			} else if (data && typeof data === 'object') {
				detail = /** @type {{ detail?: unknown }} */ (data).detail;
			}
			if (detail && typeof detail === 'object') {
				const d = /** @type {{ source_url?: string, source_type?: string }} */ (detail);
				if (d.source_url) {
					return { type: 'url', url: d.source_url, sourceType: d.source_type };
				}
			}
		}
		throw new Error(errorMessage(error, 'Failed to load original.'));
	}
}

/**
 * Pre-check which Knowledge Stores reference an item — used before
 * showing the delete-confirm modal so we can route directly to the
 * blockers panel when the item is in use.
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<{ item_id: string, knowledge_stores: Array<{ id: string, name: string, status: string }> }>}
 */
export async function getItemKbLinks(libraryId, itemId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}/kb-links`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data;
}

/**
 * @param {string} libraryId
 * @returns {Promise<{ library_id: string, items: Array<{ id: string, title: string, knowledge_store_id: string }>, knowledge_stores: Array<{ id: string, name: string }> }>}
 */
export async function getLibraryKbLinks(libraryId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/kb-links`);
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
		timeout: 300_000
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

// ---------------------------------------------------------------------------
// Capabilities (content viewer)
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} CapabilityMeta
 * @property {string} capability
 * @property {string} description
 */

/**
 * List all capability handlers registered on the Library Manager.
 * @returns {Promise<CapabilityMeta[]>}
 */
export async function getCapabilities() {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl('/libraries/capabilities');
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data?.capabilities ?? [];
}

/**
 * List the capabilities a specific library item exposes.
 *
 * Returns the per-item capability list written to ``metadata.json`` during
 * import. Legacy items default to ``["text"]`` on the backend.
 *
 * @param {string} libraryId
 * @param {string} itemId
 * @returns {Promise<string[]>}
 */
export async function getItemCapabilities(libraryId, itemId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}/capabilities`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data?.capabilities ?? [];
}

/**
 * Fetch a capability's payload for a single item.
 *
 * For ``text`` the response is markdown; for ``pages`` and ``images`` the
 * response is JSON (a page list or image gallery, respectively). The caller
 * is responsible for routing the payload to the correct renderer — see
 * ``components/libraries/capabilities/``.
 *
 * @param {string} libraryId
 * @param {string} itemId
 * @param {string} capability
 * @returns {Promise<{ mime: string, body: unknown }>}
 */
export async function getItemContentByCapability(libraryId, itemId, capability) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/libraries/${libraryId}/items/${itemId}/content/${capability}`);
	const response = await axios.get(url, {
		headers: authHeaders(),
		// Read as text first so we can dispatch on content-type. JSON
		// responses are parsed below; text responses (markdown) pass through.
		responseType: 'text',
		transformResponse: (v) => v
	});
	const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
	let body;
	if (contentType.includes('application/json')) {
		try {
			body = JSON.parse(response.data);
		} catch {
			body = response.data;
		}
	} else {
		body = response.data;
	}
	return { mime: contentType || 'text/plain', body };
}

/**
 * Build the absolute URL for the raw bytes of an image extracted by an
 * import plugin. The capability viewer's images renderer uses this to
 * point ``<img>`` tags at the backend without proxying the bytes through
 * JS.
 *
 * @param {string} libraryId
 * @param {string} itemId
 * @param {string} filename
 * @returns {string}
 */
export function getCapabilityImageUrl(libraryId, itemId, filename) {
	return getApiUrl(
		`/libraries/${libraryId}/items/${itemId}/content/images/file/${encodeURIComponent(filename)}`
	);
}

/**
 * Fetch the raw bytes for an extracted image and return them as a
 * browser-local blob URL suitable for ``<img src>``.
 *
 * The HTML ``<img>`` element doesn't carry our Bearer token, so a naked
 * ``src=getCapabilityImageUrl(...)`` 403s. Routing the fetch through axios
 * (which sets ``Authorization`` from ``authHeaders()``) and wrapping the
 * resulting blob in an object URL gives us an unauthenticated, browser-
 * local URL the ``<img>`` tag can resolve.
 *
 * Callers MUST revoke the URL with ``URL.revokeObjectURL`` when the image
 * is no longer needed (typically on component teardown), or they leak the
 * underlying blob.
 *
 * @param {string} libraryId
 * @param {string} itemId
 * @param {string} filename
 * @returns {Promise<string>} blob: URL
 */
export async function getCapabilityImageBlobUrl(libraryId, itemId, filename) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(
		`/libraries/${libraryId}/items/${itemId}/content/images/file/${encodeURIComponent(filename)}`
	);
	const response = await axios.get(url, {
		headers: authHeaders(),
		responseType: 'blob',
		timeout: 120_000
	});
	return URL.createObjectURL(response.data);
}

// ---------------------------------------------------------------------------
// Folders & tree
// ---------------------------------------------------------------------------

/**
 * Fetch the full library tree (flat folder + item lists). The frontend
 * builds the nested structure from these via ``treeOps.buildTree``.
 *
 * @param {string} libraryId
 * @returns {Promise<{ library_id: string, folders: Array<object>, items: Array<object> }>}
 */
export async function getLibraryTree(libraryId) {
	if (!browser) throw new Error('Browser only.');
	const response = await axios.get(getApiUrl(`/libraries/${libraryId}/tree`), {
		headers: authHeaders()
	});
	return response.data;
}

/**
 * Create a folder under ``parent_folder_id`` (or at the library root).
 *
 * @param {string} libraryId
 * @param {{ name: string, parent_folder_id?: string|null }} data
 */
export async function createFolder(libraryId, data) {
	if (!browser) throw new Error('Browser only.');
	const response = await axios.post(
		getApiUrl(`/libraries/${libraryId}/folders`),
		{ name: data.name, parent_folder_id: data.parent_folder_id ?? null },
		{ headers: authHeaders() }
	);
	return response.data;
}

/** Rename a folder. */
export async function renameFolder(libraryId, folderId, name) {
	if (!browser) throw new Error('Browser only.');
	const response = await axios.put(
		getApiUrl(`/libraries/${libraryId}/folders/${folderId}`),
		{ name },
		{ headers: authHeaders() }
	);
	return response.data;
}

/** Move a folder under a new parent (null = library root). */
export async function moveFolder(libraryId, folderId, parentFolderId) {
	if (!browser) throw new Error('Browser only.');
	const response = await axios.put(
		getApiUrl(`/libraries/${libraryId}/folders/${folderId}/move`),
		{ parent_folder_id: parentFolderId },
		{ headers: authHeaders() }
	);
	return response.data;
}

/**
 * Delete a folder. Server-side, the folder's items and subfolders are
 * reparented up to the deleted folder's parent — never cascade-deleted.
 */
export async function deleteFolder(libraryId, folderId) {
	if (!browser) throw new Error('Browser only.');
	const response = await axios.delete(getApiUrl(`/libraries/${libraryId}/folders/${folderId}`), {
		headers: authHeaders()
	});
	return response.data;
}

/**
 * Move a batch of items to a folder (or to root). The backend enforces
 * cross-library FK rejection and caps the array at 500.
 *
 * @param {string} libraryId
 * @param {{ item_ids: string[], folder_id: string|null }} data
 */
export async function moveItems(libraryId, data) {
	if (!browser) throw new Error('Browser only.');
	const response = await axios.post(
		getApiUrl(`/libraries/${libraryId}/items/move`),
		{ item_ids: data.item_ids, folder_id: data.folder_id ?? null },
		{ headers: authHeaders() }
	);
	return response.data;
}

/** Convenience wrapper for moving a single item. */
export async function moveItem(libraryId, itemId, folderId) {
	return moveItems(libraryId, { item_ids: [itemId], folder_id: folderId ?? null });
}
