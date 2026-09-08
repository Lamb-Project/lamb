import { apiFetch, apiJson } from '$lib/services/apiClient';

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

/**
 * List available AAC skills.
 * @returns {Promise<Array<{id: string, name: string, description: string, required_context: string[]}>>}
 */
export async function getSkills() {
	return apiJson('/aac/skills');
}

/**
 * List user's AAC sessions.
 * @returns {Promise<AacSession[]>}
 */
export async function getSessions() {
	return apiJson('/aac/sessions');
}

/**
 * Get a session with full conversation history.
 * @param {string} sessionId
 * @returns {Promise<AacSession>}
 */
export async function getSession(sessionId) {
	return apiJson(`/aac/sessions/${sessionId}`);
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
	return apiJson('/aac/sessions', {
		method: 'POST',
		body: JSON.stringify(body)
	});
}

/**
 * Send a message to the AAC agent (non-streaming).
 * @param {string} sessionId
 * @param {string} message
 * @returns {Promise<{response: string, stats: Object}>}
 */
export async function sendMessage(sessionId, message) {
	return apiJson(`/aac/sessions/${sessionId}/message`, {
		method: 'POST',
		body: JSON.stringify({ message })
	});
}

/**
 * Send a message and stream the response via SSE.
 *
 * Pass `signal` from an `AbortController` so the caller (typically the
 * AAC terminal component) can cancel the stream on unmount. Without this
 * the underlying fetch + reader keeps running in the background after the
 * user navigates away — memory leak + ghost HTTP traffic. (#352)
 *
 * Routed through `apiFetch` so an expired token triggers global session
 * recovery instead of a generic "HTTP 401" surfaced to the user. (#352, M1)
 *
 * @param {string} sessionId
 * @param {string} message
 * @param {(chunk: string) => void} onChunk - called for each text chunk
 * @param {(stats: Object) => void} [onDone] - called when stream completes
 * @param {(error: string) => void} [onError] - called on error
 * @param {(status: Object) => void} [onStatus] - called for tool/status events
 * @param {AbortSignal} [signal] - abort signal to cancel the stream
 */
export async function sendMessageStream(
	sessionId,
	message,
	onChunk,
	onDone,
	onError,
	onStatus,
	signal
) {
	let res;
	try {
		res = await apiFetch(`/aac/sessions/${sessionId}/message/stream`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ message }),
			signal
		});
	} catch (e) {
		// AbortError on unmount is expected; do not surface as an error.
		if (e?.name === 'AbortError') return;
		// Session-expired errors from apiFetch already triggered a redirect;
		// just exit quietly so we don't paint a duplicate error in the terminal.
		if (e instanceof Error && e.message.startsWith('Session expired')) return;
		throw e;
	}

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
		if (onError) onError(err.detail || `HTTP ${res.status}`);
		return;
	}

	const reader = res.body?.getReader();
	if (!reader) return;

	const decoder = new TextDecoder();
	let buffer = '';

	try {
		while (true) {
			if (signal?.aborted) {
				try {
					await reader.cancel();
				} catch (_) {
					/* noop */
				}
				return;
			}
			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });
			const lines = buffer.split('\n');
			buffer = lines.pop() || '';

			for (const line of lines) {
				if (!line.startsWith('data: ')) continue;
				const payload = line.slice(6);
				if (payload === '[DONE]') return;
				try {
					const data = JSON.parse(payload);
					if (data.content) onChunk(data.content);
					else if (data.status && onStatus) onStatus(data);
					if (data.done && onDone) onDone(data.stats || {});
					if (data.error && onError) onError(data.error);
				} catch (_) {
					/* ignore parse errors */
				}
			}
		}
	} catch (e) {
		if (e?.name === 'AbortError') return;
		throw e;
	}
}

/**
 * Delete (archive) a session.
 * @param {string} sessionId
 * @returns {Promise<{success: boolean}>}
 */
export async function deleteSession(sessionId) {
	return apiJson(`/aac/sessions/${sessionId}`, { method: 'DELETE' });
}
