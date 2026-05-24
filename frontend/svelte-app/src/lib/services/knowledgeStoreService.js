/**
 * @module knowledgeStoreService
 * API service for the new KB Server (Knowledge Store) endpoints
 * mounted at /creator/knowledge-stores/.
 *
 * Mirrors the libraryService.js pattern: axios, Bearer token auth via
 * authHeaders(), getApiUrl() base resolution, browser-only checks. Kept
 * entirely separate from knowledgeBaseService.js (which serves the legacy
 * stable KB Server) so neither can disturb the other.
 */

import axios from 'axios';
import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/**
 * @typedef {Object} KnowledgeStore
 * @property {string} id
 * @property {string} name
 * @property {string} description
 * @property {number} organization_id
 * @property {number} owner_user_id
 * @property {boolean} is_shared
 * @property {string} chunking_strategy
 * @property {Object} chunking_params
 * @property {string} embedding_vendor
 * @property {string} embedding_model
 * @property {string} [embedding_endpoint]
 * @property {string} vector_db_backend
 * @property {string} status
 * @property {boolean} [is_owner]
 * @property {string} [server_status]
 * @property {number} [document_count]
 * @property {number} [chunk_count]
 * @property {number} [content_count]
 * @property {Array<KSContentLink>} [content]
 * @property {string} [owner_name]
 * @property {string} [owner_email]
 * @property {number} created_at
 * @property {number} updated_at
 */

/**
 * @typedef {Object} KSContentLink
 * @property {number} id
 * @property {string} knowledge_store_id
 * @property {string} library_id
 * @property {string} library_item_id
 * @property {string} [kb_job_id]
 * @property {string} status
 * @property {number} chunks_created
 * @property {string} [error_message]
 * @property {string} [item_title]
 * @property {string} [item_source_type]
 * @property {string} [library_name]
 * @property {number} created_at
 * @property {number} updated_at
 */

/**
 * @typedef {Object} KSOptions
 * @property {Array<{name: string, [k: string]: any}>} vector_db_backends
 * @property {Array<{name: string, [k: string]: any}>} chunking_strategies
 * @property {Array<{name: string, [k: string]: any}>} embedding_vendors
 * @property {Object<string, string[]>} embedding_models
 */

/**
 * @typedef {Object} KSQueryResult
 * @property {string} text
 * @property {number} score
 * @property {Object} metadata
 */

function authHeaders() {
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}
	return { Authorization: `Bearer ${token}` };
}

/**
 * Raised by {@link getOptions} when the backend returns the structured
 * ``503 {error: "knowledge_store_unavailable"}`` body that signals the KB
 * Server is unreachable. The UI should render an actionable retry state
 * instead of treating this as a generic network error — there is no
 * hardcoded fallback catalogue of plugins by design.
 */
export class KnowledgeStoreUnavailableError extends Error {
	/** @param {string} detail */
	constructor(detail) {
		super(detail || 'Knowledge Store server unavailable');
		this.name = 'KnowledgeStoreUnavailableError';
		this.code = 'knowledge_store_unavailable';
		this.detail = detail || '';
	}
}

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

/**
 * Fetch the org's allow-lists (chunking strategies, embedding vendors / models,
 * vector DB backends). Used by the create-KS form / wizard to render the
 * locked-setup picker.
 *
 * Throws {@link KnowledgeStoreUnavailableError} when the backend returns
 * ``503 {error: "knowledge_store_unavailable", detail: "..."}``. Callers
 * should catch this specifically and render a retry state.
 * @returns {Promise<KSOptions>}
 */
export async function getOptions() {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl('/knowledge-stores/options');
	try {
		const response = await axios.get(url, { headers: authHeaders() });
		return response.data;
	} catch (/** @type {unknown} */ err) {
		if (axios.isAxiosError(err) && err.response?.status === 503) {
			const data = err.response.data;
			if (data && data.error === 'knowledge_store_unavailable') {
				throw new KnowledgeStoreUnavailableError(data.detail || '');
			}
		}
		throw err;
	}
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

/**
 * List Knowledge Stores accessible to the current user (owned + shared).
 * @returns {Promise<KnowledgeStore[]>}
 */
export async function getKnowledgeStores() {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl('/knowledge-stores');
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data?.knowledge_stores ?? [];
}

/**
 * Get details for a single Knowledge Store.
 * @param {string} ksId
 * @returns {Promise<KnowledgeStore>}
 */
export async function getKnowledgeStore(ksId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data;
}

/**
 * Create a new Knowledge Store. Store setup (chunking, embedding, vector DB)
 * is locked at creation time per ADR-3 of issue #334.
 * ``embedding_params`` carries any additional knobs declared by the
 * embedding vendor's schema beyond ``model``/``api_endpoint``/``api_key``
 * (those are already top-level fields). ``vector_db_params`` does the
 * same for the vector-DB backend. Both default to ``{}`` — empty for
 * today's vendors because none of them declare extras yet.
 * @param {{
 *   name: string,
 *   description?: string,
 *   chunking_strategy: string,
 *   chunking_params?: Object,
 *   embedding_vendor: string,
 *   embedding_model: string,
 *   embedding_endpoint?: string,
 *   embedding_params?: Object,
 *   vector_db_backend: string,
 *   vector_db_params?: Object,
 * }} data
 * @returns {Promise<KnowledgeStore>}
 */
export async function createKnowledgeStore(data) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl('/knowledge-stores');
	const response = await axios.post(url, data, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' }
	});
	return response.data;
}

/**
 * Update mutable fields on a Knowledge Store.
 *
 * Strategy, embedding vendor/model, and vector DB are locked at creation
 * (ADR-KS-5) — those cannot be edited here. ``chunking_params`` CAN be
 * edited, but the new values only apply to **future** ingestions; chunks
 * already in the store keep the parameters they were chunked with.
 *
 * @param {string} ksId
 * @param {{ name?: string, description?: string, chunking_params?: Record<string, unknown> }} data
 * @returns {Promise<KnowledgeStore>}
 */
export async function updateKnowledgeStore(ksId, data) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}`);
	const response = await axios.put(url, data, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' }
	});
	return response.data;
}

/**
 * Delete a Knowledge Store and all its vectors.
 * @param {string} ksId
 * @returns {Promise<{ message: string }>}
 */
export async function deleteKnowledgeStore(ksId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}`);
	const response = await axios.delete(url, { headers: authHeaders() });
	return response.data;
}

/**
 * Toggle organization-wide sharing for a Knowledge Store.
 * @param {string} ksId
 * @param {boolean} isShared
 * @returns {Promise<{ knowledge_store_id: string, is_shared: boolean, message: string }>}
 */
export async function toggleSharing(ksId, isShared) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/share`);
	const response = await axios.put(
		url,
		{ is_shared: isShared },
		{
			headers: { ...authHeaders(), 'Content-Type': 'application/json' }
		}
	);
	return response.data;
}

// ---------------------------------------------------------------------------
// Content (library item -> KS)
// ---------------------------------------------------------------------------

/**
 * Ingest one or more library items into a Knowledge Store.
 * @param {string} ksId
 * @param {{ libraryId: string, itemIds: string[] }} data
 * @returns {Promise<{ job_id: string, status: string, documents_total: number, links: any[] }>}
 */
export async function addContent(ksId, data) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/content`);
	const body = { library_id: data.libraryId, item_ids: data.itemIds };
	const response = await axios.post(url, body, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' },
		timeout: 120_000
	});
	return response.data;
}

/**
 * List linked library items for a Knowledge Store (lightweight — no KB Server call).
 * Returns an array of {library_item_id, status} objects.
 * @param {string} ksId
 * @returns {Promise<Array<{library_item_id: string, status: string}>>}
 */
export async function listContent(ksId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/content`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data?.items ?? [];
}

/**
 * Get the status of a single content link (auto-syncs from KB Server).
 * @param {string} ksId
 * @param {string} libraryItemId
 * @returns {Promise<KSContentLink>}
 */
export async function getContentLinkStatus(ksId, libraryItemId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/content/${libraryItemId}`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data;
}

/**
 * Remove a library item's vectors from a Knowledge Store.
 * Does not affect the library item itself.
 * @param {string} ksId
 * @param {string} libraryItemId
 * @returns {Promise<{ message: string }>}
 */
export async function removeContent(ksId, libraryItemId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/content/${libraryItemId}`);
	const response = await axios.delete(url, { headers: authHeaders() });
	return response.data;
}

// ---------------------------------------------------------------------------
// Query
// ---------------------------------------------------------------------------

/**
 * Run a similarity search against a Knowledge Store. Used by the assistant
 * builder's "test query" affordance and by the KS detail panel.
 * @param {string} ksId
 * @param {{ queryText: string, topK?: number }} data
 * @returns {Promise<{ results: KSQueryResult[], query: string, top_k: number }>}
 */
export async function queryKnowledgeStore(ksId, data) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/query`);
	const body = { query_text: data.queryText, top_k: data.topK ?? 5 };
	const response = await axios.post(url, body, {
		headers: { ...authHeaders(), 'Content-Type': 'application/json' },
		timeout: 60_000
	});
	return response.data;
}

/**
 * Retry a failed ingestion for a single content link.
 *
 * NOTE: the backend does not yet expose a dedicated retry endpoint —
 * this stub currently throws a `not_implemented` error. The
 * IngestionProgressModal surfaces a `toast.info("Coming soon.")` when
 * this rejects with that code, keeping the affordance discoverable
 * without blocking the user. When the backend endpoint lands, replace
 * the body of this function with the corresponding axios call.
 *
 * @param {string} ksId
 * @param {string} libraryItemId
 * @returns {Promise<{ message: string }>}
 */
export async function retryIngestion(ksId, libraryItemId) {
	if (!browser) throw new Error('Browser only.');
	// Touch the params so lint stays happy until the backend wires up.
	void ksId;
	void libraryItemId;
	const err = /** @type {Error & { code?: string }} */ (
		new Error('Retry ingestion is not yet supported by the backend.')
	);
	err.code = 'not_implemented';
	throw err;
}

/**
 * Poll a job's aggregate status (used when one batch ingested multiple items).
 * @param {string} ksId
 * @param {string} jobId
 * @returns {Promise<Object>}
 */
export async function getJobStatus(ksId, jobId) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/jobs/${jobId}`);
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data;
}

// ---------------------------------------------------------------------------
// Polling helper
// ---------------------------------------------------------------------------

/**
 * Poll a list of content links with exponential backoff (1s -> 16s, capped)
 * until each one is ready or failed, or the deadline is reached.
 *
 * Replaces the flaky 15s hard-budget pattern flagged by Marc in #336 #19.
 *
 * @param {string} ksId
 * @param {string[]} libraryItemIds
 * @param {{ onProgress?: (link: KSContentLink) => void, maxWaitMs?: number }} [opts]
 * @returns {Promise<Map<string, KSContentLink>>}
 */
export async function waitForLinks(ksId, libraryItemIds, opts = {}) {
	const onProgress = opts.onProgress || (() => {});
	const deadline = Date.now() + (opts.maxWaitMs ?? 600_000);
	const pending = new Set(libraryItemIds);
	const results = new Map();
	let delay = 1000;
	while (pending.size > 0 && Date.now() < deadline) {
		for (const itemId of [...pending]) {
			try {
				const link = await getContentLinkStatus(ksId, itemId);
				results.set(itemId, link);
				onProgress(link);
				if (link.status === 'ready' || link.status === 'failed') {
					pending.delete(itemId);
				}
			} catch (err) {
				console.error(`Error polling KS link ${itemId}:`, err);
			}
		}
		if (pending.size > 0) {
			await new Promise((r) => setTimeout(r, delay));
			delay = Math.min(delay * 2, 16000);
		}
	}
	return results;
}
