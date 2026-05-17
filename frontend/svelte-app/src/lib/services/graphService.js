/**
 * @module graphService
 * KG-RAG / semantic-graph API client for Knowledge Stores.
 *
 * Targets the LAMB backend proxy at
 * ``/creator/knowledge-stores/{ksId}/graph/...``, which forwards to the new
 * KB Server's ``/graph`` router. The KB Server only exposes graph
 * endpoints when ``KG_RAG_ENABLED=true`` — callers should gate UI on the
 * result of {@link getGraphStatus}.
 */

import axios from 'axios';
import { browser } from '$app/environment';
import { getApiUrl } from '$lib/config';

function authHeaders() {
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('User not authenticated.');
	}
	return { Authorization: `Bearer ${token}` };
}

/**
 * Get the KG-RAG feature-flag + Neo4j availability for the current user's
 * org. Cached by the caller (it shouldn't flap inside a session).
 * @returns {Promise<{enabled: boolean, index_on_ingest: boolean, neo4j_configured: boolean, neo4j_available: boolean}>}
 */
export async function getGraphStatus() {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl('/knowledge-stores/graph/status');
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data;
}

/**
 * Trigger KG-RAG migration for an existing Knowledge Store.
 * @param {string} ksId
 * @param {{ openai_api_key?: string }} [body]
 */
export async function migrateToGraph(ksId, body = {}) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/graph/migrate`);
	const response = await axios.post(url, body, { headers: authHeaders() });
	return response.data;
}

/**
 * Fetch the graph snapshot (nodes + edges + counts) for visualization.
 * @param {string} ksId
 * @param {Object} [params]
 */
export async function getGraphSnapshot(ksId, params = {}) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/graph/snapshot`);
	const response = await axios.get(url, { headers: authHeaders(), params });
	return response.data;
}

/**
 * List recent graph change events.
 * @param {string} ksId
 * @param {Object} [params]
 */
export async function listGraphChanges(ksId, params = {}) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/graph/changes`);
	const response = await axios.get(url, { headers: authHeaders(), params });
	return response.data;
}

/**
 * Rename a concept within a Knowledge Store's graph.
 * @param {string} ksId
 * @param {string} concept
 * @param {{ new_name: string, actor?: string, reason?: string }} body
 */
export async function renameConcept(ksId, concept, body) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(
		`/knowledge-stores/${ksId}/graph/concepts/${encodeURIComponent(concept)}/rename`,
	);
	const response = await axios.patch(url, body, { headers: authHeaders() });
	return response.data;
}

/**
 * Merge concepts into a target concept.
 * @param {string} ksId
 * @param {{ source_names: string[], target_name: string, actor?: string, reason?: string }} body
 */
export async function mergeConcepts(ksId, body) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/graph/concepts/merge`);
	const response = await axios.post(url, body, { headers: authHeaders() });
	return response.data;
}

/**
 * Update concept curation metadata (notes / tags / verification_state).
 * Approving sets ``verification_state='verified'``, rejecting sets
 * ``'rejected'`` which expunges the concept from KG-RAG retrieval but
 * keeps the audit event for traceability.
 * @param {string} ksId
 * @param {string} concept
 * @param {Object} body
 */
export async function curateConcept(ksId, concept, body) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(
		`/knowledge-stores/${ksId}/graph/concepts/${encodeURIComponent(concept)}/curation`,
	);
	const response = await axios.patch(url, body, { headers: authHeaders() });
	return response.data;
}

/**
 * Edit a relationship (rename / re-weight / annotate / verify).
 * @param {string} ksId
 * @param {Object} body
 */
export async function editRelationship(ksId, body) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/graph/relationships`);
	const response = await axios.patch(url, body, { headers: authHeaders() });
	return response.data;
}

/**
 * Approve / reject / annotate a relationship without changing its type.
 * @param {string} ksId
 * @param {Object} body
 */
export async function curateRelationship(ksId, body) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(
		`/knowledge-stores/${ksId}/graph/relationships/curation`,
	);
	const response = await axios.patch(url, body, { headers: authHeaders() });
	return response.data;
}
