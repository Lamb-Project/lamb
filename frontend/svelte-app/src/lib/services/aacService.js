import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';

/**
 * @typedef {Object} AacSession
 * @property {string} id
 * @property {number|null} assistant_id
 * @property {string} title
 * @property {string} status
 * @property {string} skill
 * @property {string} created_at
 * @property {string} updated_at
 * @property {Array} conversation
 * @property {string} [first_message]
 */

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
 * List available AAC skills.
 * @returns {Promise<Array<{id: string, name: string, description: string, required_context: string[]}>>}
 */
export async function getSkills() {
	return apiFetch('/aac/skills');
}

/**
 * List user's AAC sessions.
 * @returns {Promise<AacSession[]>}
 */
export async function getSessions() {
	return apiFetch('/aac/sessions');
}

/**
 * Get a session with full conversation history.
 * @param {string} sessionId
 * @returns {Promise<AacSession>}
 */
export async function getSession(sessionId) {
	return apiFetch(`/aac/sessions/${sessionId}`);
}

/**
 * Create a new AAC session, optionally with a skill.
 * @param {Object} params
 * @param {number} [params.assistantId]
 * @param {string} [params.skill]
 * @param {Object} [params.context]
 * @returns {Promise<AacSession>}
 */
export async function createSession({ assistantId, skill, context } = {}) {
	/** @type {Object} */
	const body = {};
	if (assistantId != null) body.assistant_id = assistantId;
	if (skill) {
		body.skill = skill;
		body.context = { ...context };
		if (assistantId != null) body.context.assistant_id = assistantId;
	}
	return apiFetch('/aac/sessions', {
		method: 'POST',
		body: JSON.stringify(body),
	});
}

/**
 * Send a message to the AAC agent.
 * @param {string} sessionId
 * @param {string} message
 * @returns {Promise<{response: string, stats: Object}>}
 */
export async function sendMessage(sessionId, message) {
	return apiFetch(`/aac/sessions/${sessionId}/message`, {
		method: 'POST',
		body: JSON.stringify({ message }),
	});
}

/**
 * Delete (archive) a session.
 * @param {string} sessionId
 * @returns {Promise<{success: boolean}>}
 */
export async function deleteSession(sessionId) {
	return apiFetch(`/aac/sessions/${sessionId}`, { method: 'DELETE' });
}
