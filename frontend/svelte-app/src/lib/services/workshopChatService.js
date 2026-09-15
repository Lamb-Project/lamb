// src/lib/services/workshopChatService.js
/**
 * Workshop chat SSE service.
 *
 * Sends a message to the student's workshop assistant and streams the reply.
 * The SSE dialect is the shared LAMB dialect:
 *   - `data: {"choices":[{"delta":{"content":"..."}}]}`   → assistant text chunks
 *   - `data: {"type":"tool_event","data":{...}}`           → tool timeline frames
 *   - `data: {"type":"observability","data":{...}}`        → obs dashboard frames
 *   - `data: [DONE]`                                       → stream end
 *
 * Auth: the workshop student token travels in the custom `token` header
 * (the LTI launch contract), NOT the Bearer header — so we must NOT use apiFetch,
 * which auto-attaches Bearer and triggers the creator 401 redirect. We fetch
 * directly against the backend `/lamb` mount.
 */

/**
 * Send a chat message to a workshop assistant, streaming SSE.
 *
 * @param {Object} params
 * @param {string} params.sessionId - workshop session id
 * @param {number} params.assistantId - workshop-built assistant id
 * @param {string} params.token - workshop_student JWT
 * @param {Array<{role: string, content: string}>} params.messages - full chat history
 * @param {Object} [params.opts]
 * @param {Array<Object>} [params.opts.tools] - tool definitions for the ToolLoop
 * @param {boolean} [params.opts.observability] - request observability frames (default true)
 * @param {Object} handlers
 * @param {(chunk: string) => void} [handlers.onChunk]
 * @param {(data: Object) => void} [handlers.onObservability]
 * @param {(evt: Object) => void} [handlers.onToolEvent]
 * @param {() => void} [handlers.onDone]
 * @param {(msg: string) => void} [handlers.onError]
 * @param {AbortSignal} [signal]
 */
export async function sendWorkshopChat(
	{ sessionId, assistantId, token, messages, opts = {} },
	handlers = {},
	signal
) {
	const { onChunk, onObservability, onToolEvent, onDone, onError } = handlers;

	// Dev (5173) proxies /lamb to the backend; prod SPA is served by the same
	// origin. Use the relative /lamb path in both cases. getLambApiUrl would
	// point at the raw backend port which is not proxied in dev via the SPA.
	const path = `/lamb/v1/workshop/sessions/${encodeURIComponent(sessionId)}/assistant/${assistantId}/chat`;

	let res;
	try {
		res = await fetch(path, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				token,
			},
			body: JSON.stringify({
				messages,
				stream: true,
				observability: opts.observability ?? true,
				tools: opts.tools || [],
			}),
			signal,
		});
	} catch (/** @type {any} */ e) {
		// AbortError on unmount is expected; do not surface as an error.
		if (e?.name === 'AbortError') return;
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
				try { await reader.cancel(); } catch { /* noop */ }
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
				if (payload === '[DONE]') {
					if (onDone) onDone();
					return;
				}
				try {
					const data = JSON.parse(payload);
					if (data.type === 'observability') {
						if (onObservability) onObservability(data.data);
					} else if (data.type === 'tool_event') {
						if (onToolEvent) onToolEvent(data.data);
					} else if (
						data.choices &&
						data.choices[0] &&
						data.choices[0].delta &&
						data.choices[0].delta.content
					) {
						if (onChunk) onChunk(data.choices[0].delta.content);
					}
				} catch { /* ignore non-JSON */ }
			}
		}
	} catch (/** @type {any} */ e) {
		if (e?.name === 'AbortError') return;
		throw e;
	}
}