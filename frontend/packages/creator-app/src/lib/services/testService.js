import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/** @returns {string} */
function getToken() {
	if (!browser) return '';
	return localStorage.getItem('userToken') || '';
}

/** @param {string} endpoint @param {Object} [options] */
async function apiFetch(endpoint, options = {}) {
	const token = getToken();
	if (!token) throw new Error('Not authenticated');

	const url = getApiUrl(endpoint);
	const res = await fetch(url, {
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json',
			...options.headers,
		},
		...options,
	});

	if (!res.ok) {
		let detail = `API error (${res.status})`;
		try {
			const err = await res.json();
			detail = err?.detail || detail;
		} catch (_) { /* ignore */ }
		throw new Error(detail);
	}

	return res.json();
}

/**
 * List test scenarios for an assistant.
 * @param {number} assistantId
 * @returns {Promise<Array>}
 */
export async function getScenarios(assistantId) {
	return apiFetch(`/assistant/${assistantId}/tests/scenarios`);
}

/**
 * Create a test scenario.
 * @param {number} assistantId
 * @param {Object} scenario
 * @returns {Promise<Object>}
 */
export async function createScenario(assistantId, scenario) {
	return apiFetch(`/assistant/${assistantId}/tests/scenarios`, {
		method: 'POST',
		body: JSON.stringify(scenario),
	});
}

/**
 * Delete a test scenario.
 * @param {number} assistantId
 * @param {string} scenarioId
 * @returns {Promise<Object>}
 */
export async function deleteScenario(assistantId, scenarioId) {
	return apiFetch(`/assistant/${assistantId}/tests/scenarios/${scenarioId}`, {
		method: 'DELETE',
	});
}

/**
 * Run test scenarios.
 * @param {number} assistantId
 * @param {Object} [options]
 * @param {string} [options.scenarioId] - Run a specific scenario
 * @param {boolean} [options.bypass] - Debug bypass mode (zero tokens)
 * @returns {Promise<Object>}
 */
export async function runTests(assistantId, options = {}) {
	const body = {};
	if (options.scenarioId) body.scenario_id = options.scenarioId;
	if (options.bypass) body.debug_bypass = true;
	return apiFetch(`/assistant/${assistantId}/tests/run`, {
		method: 'POST',
		body: JSON.stringify(body),
	});
}

/**
 * List test runs for an assistant.
 * @param {number} assistantId
 * @param {number} [limit=20]
 * @returns {Promise<Array>}
 */
export async function getRuns(assistantId, limit = 20) {
	return apiFetch(`/assistant/${assistantId}/tests/runs?limit=${limit}`);
}

/**
 * Get full test run details.
 * @param {number} assistantId
 * @param {string} runId
 * @returns {Promise<Object>}
 */
export async function getRunDetail(assistantId, runId) {
	return apiFetch(`/assistant/${assistantId}/tests/runs/${runId}`);
}

/**
 * Submit an evaluation for a test run.
 * @param {number} assistantId
 * @param {string} runId
 * @param {Object} evaluation
 * @param {'good'|'bad'|'mixed'} evaluation.verdict
 * @param {string} [evaluation.notes]
 * @returns {Promise<Object>}
 */
export async function evaluateRun(assistantId, runId, evaluation) {
	return apiFetch(`/assistant/${assistantId}/tests/runs/${runId}/evaluate`, {
		method: 'POST',
		body: JSON.stringify(evaluation),
	});
}

/**
 * List evaluations for an assistant.
 * @param {number} assistantId
 * @returns {Promise<Array>}
 */
export async function getEvaluations(assistantId) {
	return apiFetch(`/assistant/${assistantId}/tests/evaluations`);
}
