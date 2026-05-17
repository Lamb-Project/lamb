/**
 * @module benchmarkService
 * KG-RAG benchmark API client for Knowledge Stores.
 *
 * Targets the LAMB backend proxy at
 * ``/creator/knowledge-stores/{ksId}/benchmarks/...``, which forwards to the
 * new KB Server's ``/benchmarks`` router. Like the graph endpoints, these
 * are only available when ``KG_RAG_ENABLED=true`` on the KB Server.
 */

import axios from 'axios';
import { browser } from '$app/environment';
import { getApiUrl } from '$lib/config';

function authHeaders() {
	const token = localStorage.getItem('userToken');
	if (!token) throw new Error('User not authenticated.');
	return { Authorization: `Bearer ${token}` };
}

/**
 * List built-in benchmark datasets.
 */
export async function listDatasets() {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl('/knowledge-stores/benchmarks/datasets');
	const response = await axios.get(url, { headers: authHeaders() });
	return response.data;
}

/**
 * Run a benchmark dataset against a Knowledge Store, comparing
 * ``simple_query`` (vector baseline) against ``kg_rag_query`` (vector +
 * graph expansion).
 * @param {string} ksId
 * @param {{ dataset_id?: string, top_k?: number, graph_depth?: number, threshold?: number }} body
 */
export async function runBenchmark(ksId, body) {
	if (!browser) throw new Error('Browser only.');
	const url = getApiUrl(`/knowledge-stores/${ksId}/benchmarks/run`);
	const response = await axios.post(url, body, { headers: authHeaders() });
	return response.data;
}
