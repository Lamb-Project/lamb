<script>
	// src/routes/m/workshop/[activityId]/+page.svelte
	// Workshop build wizard + live observability dashboard.
	//
	// Entry: LTI launch redirects the student to /m/workshop/{activityId}?token={workshopJWT}
	// (the LTI launch contract). The token carries the workshop principal; the page
	// decodes the JWT payload (no verification needed — every API call re-verifies
	// server-side with the token in the `token` header) to learn its session_id,
	// restores persisted build_state, and renders the 5-step wizard.
	//
	// Adapter-static has no SSR: everything happens client-side in onMount.

	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { _ } from '$lib/i18n';
	import { createWorkshopFormState } from '$lib/components/workshop/logic/workshopFormState.svelte.js';
	import WizardSteps from '$lib/components/workshop/WizardSteps.svelte';
	import ObservabilityPanel from '$lib/components/workshop/ObservabilityPanel.svelte';
	import FormativeFeedback from '$lib/components/workshop/FormativeFeedback.svelte';
	import LocaleSwitcher from '$lib/components/workshop/LocaleSwitcher.svelte';
	import RagComparison from '$lib/components/workshop/RagComparison.svelte';
	import {
		dropObservations,
		latestObservation,
		recordObservation
	} from '$lib/components/workshop/logic/workshopObservations.svelte.js';	import { sendWorkshopChat } from '$lib/services/workshopChatService.js';
	import {
		createWorkshopApi,
		decodeTokenPayload,
		TOKEN_EXPIRED
	} from '$lib/services/workshopApi.js';
	import { initWorkshopLocale } from '$lib/workshop/workshopLocale.js';
	import { getWorkshopLlmConfig } from '$lib/config.js';

	// ── Auth / session (from URL) ──
	/** @type {string} */
	let token = $state('');
	/** @type {string} */
	let sessionId = $state('');
	let activityId = $state('');

	// ── Wizard state ──
	/** @type {ReturnType<typeof createWorkshopFormState> | null} */
	let formStore = /** @type {any} */ ($state(null));
	/** @type {any} */ let form = $state(null);
	/** @type {string} */
	let error = $state('');
	/** @type {boolean} */
	let reentryRequired = $state(false);
	/** @type {boolean} */
	let loading = $state(true);
	/** @type {boolean} */
	let assistantCreating = $state(false);
	/** @type {boolean} */
	let uploading = $state(false);
	/** @type {boolean} */
	let removingDocument = $state(false);
	/**
	 * Bumped whenever the attached document is removed, so an ingestion poll
	 * that is still running for the old document stops instead of resurrecting it.
	 */
	let documentEpoch = 0;
	/** @type {boolean} */
	let probing = $state(false);
	/** @type {boolean} */
	let submitting = $state(false);
	/** @type {boolean} */
	let evaluating = $state(false);
	/** @type {any | null} */
	let evaluation = $state(null);

	// ── Chat + observability ──
	// Entries may also carry assistant `tool_calls` / `role: tool` fields and an
	// `hidden` flag (tool trace persisted for context but not rendered).
	/** @type {Array<any>} */
	let chatMessages = $state([]);
	let chatInput = $state('');
	let streaming = $state(false);
	/** @type {AbortController | null} */
	let abortController = $state(null);
	/** @type {any | null} */
	let obsData = $state(null);
	/**
	 * The observability "request" frame — what is about to be sent, available
	 * before the model has produced anything (D1). Kept apart from `obsData`
	 * (the "result" frame) so the panel can show both.
	 * @type {any | null}
	 */
	let obsRequest = $state(null);
	/** @type {Array<any>} */
	let toolEvents = $state([]);
	/** @type {Array<any>} */
	let documentFiles = $state([]);
	/**
	 * Step 3's test question and what it retrieved. Read back from the
	 * observations so it survives navigating between steps and a page reload.
	 */
	const probe = $derived(latestObservation(form?.observations, 3, 'probe')?.data ?? null);

	/** @type {number | null} */
	let assistantId = $state(null);

	/** Tool definitions that will be sent to the model (steps 4 and 5). */
	const toolsPayload = $derived(
		(form?.selectedTools || []).map((/** @type {string} */ name) => ({
			type: 'function',
			function: { name }
		}))
	);

	/**
	 * The observation panel is the through-line of the wizard (D2), not a
	 * by-product of chatting: it is visible from step 2 on, whether or not the
	 * student has sent a message yet.
	 */
	const panelVisible = $derived(
		!!form &&
			(form.currentStep >= 2 || !!obsData || !!obsRequest || toolEvents.length > 0)
	);

	// ── API client (token renewal + readable 401s) ──
	/** @type {ReturnType<typeof createWorkshopApi> | null} */
	let api = null;

	/**
	 * Turn an error into the text the student should read.
	 *
	 * `token_expired` is special: renewal already failed (or is impossible), so
	 * the only way forward is re-entering from the course page — saying
	 * "invalid token" there would be a dead end.
	 * @param {any} e
	 */
	function errorText(e, fallback = 'Request failed') {
		if (e?.code === TOKEN_EXPIRED) {
			return $_('workshop.tokenExpired', {
				default: 'Your workshop session expired.'
			});
		}
		return e?.message || fallback;
	}

	/**
	 * Whether an error means "the student must re-enter from the course page".
	 * @param {any} e
	 */
	function needsReentry(e) {
		return e?.code === TOKEN_EXPIRED;
	}

	/**
	 * Record a failure for display.
	 * @param {any} e
	 * @param {string} [fallback]
	 */
	function fail(e, fallback = '') {
		error = errorText(e, fallback || undefined);
		reentryRequired = needsReentry(e);
	}

	async function fetchSession() {
		return api.request(`/sessions/${encodeURIComponent(sessionId)}`);
	}

	/** @param {string} path @param {Object} [body] */
	async function wsPost(path, body = {}) {
		return api.request(path, { method: 'POST', body });
	}

	/** @param {string} path @param {Object} [body] */
	async function wsPatch(path, body = {}) {
		return api.request(path, { method: 'PATCH', body });
	}

	/**
	 * Restore a previously generated evaluation (page reload) — best effort.
	 * A missing rubric/evaluation is not an error.
	 */
	async function fetchEvaluation() {
		try {
			const data = await api.request(
				`/sessions/${encodeURIComponent(sessionId)}/evaluation`);
			if (data.evaluation) {
				evaluation = { configured: data.configured, ...data.evaluation };
			} else if (data.configured === false) {
				evaluation = { configured: false };
			}
		} catch {
			// Non-fatal: feedback is optional.
		}
	}

	onMount(async () => {
		activityId = /** @type {string} */ ($page.params.activityId);

		// Locale chain (C6): the LMS locale travels in ?lang=, then the saved
		// choice, then the browser, then English. Applied without persisting —
		// a guess must not overwrite a choice made elsewhere in the app.
		initWorkshopLocale($page.url.searchParams.get('lang'));

		const urlToken = $page.url.searchParams.get('token') || '';
		token = urlToken;

		if (!token) {
			error = $_('workshop.missingToken', {
				default:
					'Missing workshop token. This page must be opened from an LTI launch link.'
			});
			loading = false;
			return;
		}

		const payload = decodeTokenPayload(token);
		sessionId = payload.session_id || '';

		if (!sessionId) {
			error = $_('workshop.missingSession', {
				default: 'Token payload is missing session_id.'
			});
			loading = false;
			return;
		}

		// One client per session: it renews the short-lived token in the
		// background (every 5 minutes / on tab focus) and writes the fresh
		// token back to the URL so a reload keeps working.
		api = createWorkshopApi({
			sessionId,
			token,
			onToken: (next) => {
				token = next;
			}
		});
		api.startAutoRenew();

		try {
			const session = await fetchSession();
			console.info('[workshop] restored session:', session);
			// Rehydrate the wizard from persisted build_state.
			formStore = createWorkshopFormState(session.build_state || {});
			form = formStore.form;
			if (session.assistant_id) {
				form.assistantId = assistantId = session.assistant_id;
				form.assistantName = form.assistantName || 'My AI Assistant';
			}
			// Rehydrate step 2/3 from the session record (KB/document binding).
			if (session.kb_id && !form.selectedKbId) form.selectedKbId = session.kb_id;
			if (session.document_file_id) {
				form.attachedFilePath = form.attachedFilePath || session.document_file_id;
				form.attachedFileMeta = form.attachedFileMeta || {
					name: session.document_name || 'document',
					path: session.document_file_id,
				};
				form.documentStatus = session.document_status || form.documentStatus;
			}
			chatMessages = form.chatMessages || [];
			// Re-populate step 2's observation after a reload: the fact that the
			// document was chunked a certain way does not change, but the panel
			// would otherwise be empty until the next upload.
			if (session.document_file_id) {
				await loadDocumentFiles();
			}
			await fetchEvaluation();
		} catch (/** @type {any} */ e) {
			console.error('[workshop] session load failed:', e);
			formStore = createWorkshopFormState({});
			form = formStore.form;
			error = errorText(e);
			reentryRequired = needsReentry(e);
		} finally {
			loading = false;
		}
	});

	onDestroy(() => {
		api?.stopAutoRenew();
	});

	async function createAssistantIfNeeded() {
		if (assistantId) return assistantId;
		if (assistantCreating) return null;

		assistantCreating = true;
		try {
			form.assistantName = form.assistantName || `My AI Assistant ${sessionId.slice(-6)}`;
			const body = {
				name: form.assistantName,
				description: 'Built in the AI Workshop wizard',
				system_prompt: form.instructions,
				// Pass the student's text through verbatim, then append the RAG
				// context. The processor only injects {context} when the template
				// contains it, so this is what makes retrieved excerpts reach the
				// LLM (and the observability panel).
				prompt_template:
					'{user_input}\n\nContext:\n{context}',
				// metadata (api_callback) — pin the connector/model so the
				// assistant resolves to a real LLM (the backend's *default*
				// plugin config falls back to an unavailable openai/gpt-4
				// placeholder). The values come from runtime config
				// (static/config.js → LAMB_CONFIG.workshop) so each deployment
				// can pick its own model without rebuilding or touching this
				// wizard. getWorkshopLlmConfig falls back to a built-in default
				// (ollama / qwen3.5:9b) when the deployment sets none.
				api_callback: JSON.stringify({
					prompt_processor: 'simple_augment',
					connector: getWorkshopLlmConfig().connector,
					llm: getWorkshopLlmConfig().llm,
					rag_processor: form.selectedKbId ? 'simple_rag' : '',
				}),
				rag_top_k: 3,
				// simple_rag parses comma-separated ids, not a JSON array.
				rag_collections: form.selectedKbId || '',
			};
			const result = await wsPost(`/sessions/${sessionId}/assistant`, body);
			form.assistantId = assistantId = result.assistant_id;
			persistBuildState();
			return assistantId;
		} catch (/** @type {any} */ e) {
			fail(e, 'Failed to create your assistant.');
			return null;
		} finally {
			assistantCreating = false;
		}
	}

	async function persistBuildState() {
		// Keep the local store in sync with the chat transcript. The full build
		// state is persisted on submit (handleSubmit sends
		// formStore.serialize()), which is what the formative evaluation and the
		// teacher dashboard read back.
		form.chatMessages = chatMessages;
	}

	/**
	 * Persist the step-1 "Instructions" to the existing assistant.
	 *
	 * The assistant is created on first completion of step 1, but the student
	 * can go back and edit the instructions afterwards. Without this, those
	 * edits never reached the backend, so `system_prompt` (and thus the
	 * observability panel's system message) stayed stale/empty.
	 */
	async function syncInstructions() {
		if (!assistantId) return;
		try {
			await wsPatch(`/sessions/${sessionId}/assistant/${assistantId}`, {
				system_prompt: form.instructions,
			});
		} catch (/** @type {any} */ e) {
			// Non-fatal: the student can still chat; the next sync retries.
			fail(e, 'Failed to save your instructions.');
		}
	}

	/**
	 * Upload a document to the session KB (step 2) and poll ingestion to
	 * completion. On success the KB is also recorded as the selected KB so the
	 * student can go straight to the retrieval test in step 3.
	 * @param {File} file
	 */
	async function handleUploadDocument(file) {
		if (!form || uploading) return;
		if (!assistantId) {
			const aid = await createAssistantIfNeeded();
			if (!aid) {
				error = 'Create the assistant first (finish step 1).';
				return;
			}
		}
		uploading = true;
		error = '';
		reentryRequired = false;
		form.documentStatus = 'uploading';
		const epoch = documentEpoch;
		try {
			const fd = new FormData();
			fd.append('file', file);
			const res = await api.fetchWithRenew(
				`/sessions/${encodeURIComponent(sessionId)}/assistant/${assistantId}/doc`,
				{ method: 'POST', body: fd }
			);
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				throw new Error(err.detail || `Upload failed (${res.status})`);
			}
			const data = await res.json();
			form.attachedFilePath = data.file_registry_id || file.name;
			form.attachedFileMeta = {
				name: file.name,
				path: data.file_registry_id || file.name,
			};
			form.documentStatus = data.status || 'processing';
			if (data.kb_id) form.selectedKbId = data.kb_id;
			persistBuildState();
			if (data.file_registry_id) {
				await pollDocumentStatus(data.file_registry_id);
			} else {
				form.documentStatus = 'completed';
			}
			// The student removed the document while it was still ingesting.
			if (epoch !== documentEpoch) return;
			// Step 2's observation: how the document was actually chunked. This
			// is the KB file registry (deterministic facts), not a guess from a
			// probe query's top-k hits (D2 / C16).
			await loadDocumentFiles();
		} catch (/** @type {any} */ e) {
			form.documentStatus = 'failed';
			fail(e, 'Upload failed');
		} finally {
			uploading = false;
		}
	}

	/**
	 * Remove the attached document (step 2).
	 *
	 * The server deletes the session KB and frees the one-document quota; only
	 * then is the browser state cleared. If the server refuses (e.g. the KB
	 * server is down) the document stays listed and the student can try again —
	 * clearing locally first would leave a session that still holds the old
	 * document and rejects the next upload.
	 */
	async function handleRemoveDocument() {
		if (!form || removingDocument) return;
		removingDocument = true;
		error = '';
		reentryRequired = false;
		try {
			if (assistantId) {
				const res = await api.fetchWithRenew(
					`/sessions/${encodeURIComponent(sessionId)}/assistant/${assistantId}/doc`,
					{ method: 'DELETE' }
				);
				if (!res.ok) {
					const err = await res.json().catch(() => ({}));
					throw new Error(err.detail || `Remove failed (${res.status})`);
				}
			}
			documentEpoch += 1; // stop any ingestion poll still running
			form.attachedFilePath = '';
			form.attachedFileMeta = null;
			form.documentStatus = '';
			form.selectedKbId = '';
			form.kbCollection = '';
			form.kbVerificationResult = null;
			documentFiles = [];
			// Their evidence described a knowledge base that no longer exists.
			form.observations = dropObservations(form.observations, ['document', 'probe']);
			persistBuildState();
		} catch (/** @type {any} */ e) {
			fail(e, 'Failed to remove the document.');
		} finally {
			removingDocument = false;
		}
	}

	/**
	 * Read the KB file registry for this session and snapshot it for the panel.
	 * Best effort: the upload already succeeded, so a registry read failure must
	 * not turn into a student-facing error.
	 */
	async function loadDocumentFiles() {
		if (!api || !sessionId) return;
		try {
			const data = await api.request(
				`/sessions/${encodeURIComponent(sessionId)}/doc/files`);
			documentFiles = data.files || [];
			if (documentFiles.length) {
				form.observations = recordObservation(
					form.observations, 2, 'document', { files: documentFiles });
			}
		} catch (/** @type {any} */ e) {			console.info('[workshop] document registry unavailable:', e?.message);
		}
	}

	/**
	 * Poll the KB server ingestion job until it completes or fails.
	 * @param {string} jobId
	 */
	async function pollDocumentStatus(jobId) {
		const maxAttempts = 60;
		const epoch = documentEpoch;
		for (let attempt = 0; attempt < maxAttempts; attempt++) {
			await new Promise((r) => setTimeout(r, 3000));
			if (epoch !== documentEpoch) return;
			try {
				const data = await api.request(
					`/sessions/${encodeURIComponent(sessionId)}/doc/status?job_id=${encodeURIComponent(jobId)}`
				);
				form.documentStatus = data.status;
				if (data.status === 'completed') return;
				if (data.status === 'failed' || data.status === 'cancelled') {
					error = data.error_message || 'Document ingestion failed.';
					return;
				}
			} catch {
				// transient — keep polling
			}
		}
		error = 'Ingestion is taking longer than expected. You can continue and check again later.';
	}

	/**
	 * Run a real probe query against the session KB (step 3) and show the
	 * retrieved excerpts + similarity.
	 */
	async function handleProbeKb() {
		if (!form || probing) return;
		if (!assistantId) {
			const aid = await createAssistantIfNeeded();
			if (!aid) {
				error = 'Create the assistant first (finish step 1).';
				return;
			}
		}
		probing = true;
		error = '';
		try {
			const data = await wsPost(
				`/sessions/${sessionId}/assistant/${assistantId}/kb`,
				{ kb_id: form.selectedKbId || undefined, query: form.kbQuery, top_k: 3 }
			);
			if (data.kb_id) {
				form.selectedKbId = data.kb_id;
				form.kbCollection = form.kbCollection || data.kb_id;
			}
			form.kbVerificationResult = data;
			// Step 3's observation: the excerpts this exact question retrieved
			// (as opposed to step 2's "how it was split" facts).
			form.observations = recordObservation(
				form.observations, 3, 'probe', {
					query: form.kbQuery,
					results: data.results || [],
					count: data.count || 0
				});
			persistBuildState();
		} catch (/** @type {any} */ e) {
			fail(e, 'Knowledge base test failed.');
		} finally {
			probing = false;
		}
	}

	async function handleNext() {
		// Step 1 → creating the assistant persists instructions as system_prompt.
		if (!formStore) return;
		if (form.currentStep === 1) {
			await createAssistantIfNeeded();
			if (!assistantId) {
				error = 'Assistant could not be created — check the backend is running.';
				return;
			}
			// The create sent the current instructions; editing them after a
			// re-entrance to step 1 needs an explicit update.
			await syncInstructions();
		}
		persistBuildState();
		formStore.nextStep();
	}

	function handleBack() {
		if (!formStore) return;
		persistBuildState();
		formStore.prevStep();
	}

	/**
	 * History to send to the backend: everything except the empty assistant
	 * placeholder, preserving assistant `tool_calls` and `role: tool` entries so
	 * the model keeps the full tool trace across turns. Hidden entries are sent
	 * too (they are part of the conversation), they're only hidden in the UI.
	 * @param {Array<any>} msgs
	 * @returns {Array<any>}
	 */
	function requestMessages(msgs) {
		return msgs
			.slice(0, -1)
			.filter(
				(m) =>
					m.role === 'tool' ||
					(m.tool_calls && m.tool_calls.length) ||
					(m.content && m.content.length)
			)
			// Strip frontend-only fields (`hidden`) — they must not reach the
			// model API. Keep role/content/tool_calls/tool_call_id.
			.map((m) => {
				const wire = { ...m };
				delete wire.hidden;
				return wire;
			});
	}

	async function handleSend() {
		const text = chatInput.trim();
		if (!text || streaming) return;
		// Create the assistant lazily if the student jumped straight to step 5
		// (pills allow skipping the step-1 "Next" button).
		if (!assistantId) {
			const aid = await createAssistantIfNeeded();
			if (!aid) {
				error = 'Create the assistant first (finish step 1).';
				return;
			}
		}
		if (assistantId == null) return;
		// Persist the current step-1 instructions so the LLM (and the
		// observability panel) always reflect what the student set.
		await syncInstructions();

		chatMessages = [...chatMessages, { role: 'user', content: text }, { role: 'assistant', content: '' }];
		let assistantSlot = chatMessages.length - 1;
		chatInput = '';
		streaming = true;
		toolEvents = [];
		obsData = null;
		obsRequest = null;
		abortController = new AbortController();

		// Tool definitions passed to the backend (calculator default per wizard).
		// With the knowledge base off, the retrieval tool is dropped too — the
		// backend enforces this as well, but the panel should show the truth.
		const ragMode = form.ragMode === 'off' ? 'off' : 'on';
		const tools = toolsPayload.filter(
			(t) => !(ragMode === 'off' && t.function.name === 'kb_query')
		);

		let assistantBuffer = '';
		let requestFrame = null;
		await sendWorkshopChat(
			{
				sessionId,
				assistantId,
				token,
				api,
				messages: requestMessages(chatMessages),
				opts: { tools, observability: true, ragMode },
			},
			{
				onChunk: (chunk) => {
					assistantBuffer += chunk;
					// Update only the assistant slot — never drop the user message.
					chatMessages = chatMessages.map((m, i) =>
						i === assistantSlot ? { role: 'assistant', content: assistantBuffer } : m
					);
				},
				onObservability: (data) => {
					// Two frames per turn (D1): "request" arrives before the
					// first LLM call, "result" at the end of the stream.
					if (data?.phase === 'request') {
						obsRequest = data;
						requestFrame = data;
						form.observations = recordObservation(
							form.observations, 5, 'chat_request', data);
					} else {
						obsData = data;
						form.observations = recordObservation(
							form.observations, 5, 'chat_result', data);
					}
				},
				onToolEvent: (evt) => {
					toolEvents = [...toolEvents, evt];
				},
				onToolMessages: (msgs) => {
					// Persist the assistant tool_calls / role:tool exchanges this
					// turn produced, right before the assistant reply, so they are
					// resent on later turns (full tool trace across the session).
					// Marked hidden so they don't render in the chat UI.
					if (!msgs || msgs.length === 0) return;
					const hidden = msgs.map((m) => ({ ...m, hidden: true }));
					chatMessages = [
						...chatMessages.slice(0, assistantSlot),
						...hidden,
						...chatMessages.slice(assistantSlot),
					];
					assistantSlot += hidden.length;
				},
				onDone: () => {
					streaming = false;
					abortController = null;
					recordTurn(text, ragMode, requestFrame, assistantBuffer);
					persistBuildState();
				},
				onError: (msg) => {
					streaming = false;
					abortController = null;
					error = msg || 'Stream error';
					// A failed turn still counts as an attempt: the comparison
					// should not silently lose the "off" run.
					recordTurn(text, ragMode, requestFrame, assistantBuffer);
				},
			},
			abortController.signal
		);
	}

	/**
	 * Remember one chat turn for the A/B comparison (D3).
	 *
	 * Stores the question, the mode, the excerpts that were sent and the answer
	 * — the four things a student needs side by side to explain why the two
	 * answers differ.
	 *
	 * @param {string} question
	 * @param {string} ragMode
	 * @param {any} frame - the observability "request" frame, when it arrived
	 * @param {string} answer
	 */
	function recordTurn(question, ragMode, frame, answer) {
		if (!form || !question) return;
		form.obsHistory = [
			...(form.obsHistory || []),
			{
				turn: (form.obsHistory || []).length + 1,
				ragMode,
				question,
				sources: frame?.retrieved_sources || [],
				ragContext: frame?.rag_context || '',
				answer: answer || ''
			}
		];
	}

	function handleStop() {
		if (abortController) abortController.abort();
		streaming = false;
		abortController = null;
	}

	async function handleSubmit() {
		if (submitting) return;
		submitting = true;
		error = '';
		try {
			persistBuildState();
			const buildState = formStore ? formStore.serialize() : {};
			await wsPost(`/sessions/${sessionId}/submit`, {
				saved_chat: JSON.stringify(chatMessages),
				// The three structured questions compose into the free-text
				// `reflection` the transcript and dashboard read (D5).
				reflection: formStore ? formStore.composeReflection() : form.reflection || '',
				// Persist the per-step decisions so the formative transcript and
				// the teacher dashboard can show what the student actually built.
				build_state: JSON.stringify(buildState),
			});
			form.stepValid = { ...form.stepValid, submitted: true };
			// Submit persisted the work; now generate rubric-based feedback.
			// Feedback is advisory and never blocks the submission.
			await evaluateWorkshop();
		} catch (/** @type {any} */ e) {
			fail(e, 'Submit failed');
		} finally {
			submitting = false;
		}
	}

	/**
	 * Request rubric-based formative feedback for the submitted session.
	 * Retryable; a missing rubric comes back as `{configured: false}`.
	 */
	async function evaluateWorkshop() {
		if (evaluating) return;
		evaluating = true;
		try {
			const result = await wsPost(`/sessions/${sessionId}/evaluate`, {});
			evaluation = result;
		} catch (/** @type {any} */ e) {
			fail(e, 'Could not generate feedback.');
		} finally {
			evaluating = false;
		}
	}

	function nextDisabled() {
		return !form || !formStore || !formStore.isStepComplete(form.currentStep);
	}

	/** @type {Array<{n: number, label: string}>} */
	const stepLabels = $derived([
		{ n: 1, label: $_('workshop.step1', { default: 'Instructions' }) },
		{ n: 2, label: $_('workshop.step2', { default: 'Attach Document' }) },
		{ n: 3, label: $_('workshop.step3', { default: 'Connect Knowledge Base' }) },
		{ n: 4, label: $_('workshop.step4', { default: 'Add Tool' }) },
		{ n: 5, label: $_('workshop.step5', { default: 'Test & Reflect' }) },
	]);
</script>

<svelte:head>
	<title>{$_('workshop.title', { default: 'AI Workshop' })}</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 py-6">
	<!-- Minimal student shell (C7): activity identity + language, no Creator
	     navigation. The LMS provides the "back to course" affordance. -->
	<header class="flex items-center justify-between gap-4 mb-6">
		<div class="min-w-0">
			<h1 class="text-2xl font-bold truncate">
				{$_('workshop.title', { default: 'AI Workshop' })}
			</h1>
			<p class="text-sm text-gray-500">Activity #{activityId || '—'}</p>
		</div>
		<LocaleSwitcher />
	</header>

	{#if loading}
		<div class="py-16 text-center text-gray-500">
			{$_('workshop.loadingWorkshop', { default: 'Loading your workshop…' })}
		</div>
	{:else if error && !form}
		<div class="border rounded p-4 bg-red-50 text-red-700 text-sm">
			<p class="font-medium">{$_('workshop.workshopUnavailable', { default: 'Workshop unavailable' })}</p>
			<p class="mt-1">{error}</p>
			{#if reentryRequired}
				<p class="mt-2">
					{$_('workshop.reenterFromCourse', { default: 'Open the activity again from your course page to continue.' })}
				</p>
			{/if}
		</div>
	{:else}
		{#if error}
			<div class="mb-4 border rounded p-3 bg-amber-50 text-amber-800 text-sm">
				<p>{error}</p>
				{#if reentryRequired}
					<p class="mt-1">
						{$_('workshop.reenterFromCourse', { default: 'Open the activity again from your course page to continue.' })}
					</p>
				{/if}
			</div>
		{/if}

		<!-- Step progress bar -->
		<nav class="flex gap-2 mb-6 overflow-x-auto pb-1">
			{#each stepLabels as s (s.n)}
				<button
					class="px-3 py-1 rounded-full text-xs font-medium border whitespace-nowrap
					{form.currentStep === s.n ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300'}"
					onclick={() => { if (formStore) formStore.goToStep(s.n); }}
				>{s.n}. {s.label}</button>
			{/each}
		</nav>

		<div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
			<!-- Wizard card -->
			<section class="lg:col-span-2 border rounded-lg p-5 bg-white shadow-sm">
				{#if form.currentStep <= 4}
					<p class="text-xs font-semibold uppercase text-gray-400 mb-4">
						{$_('workshop.stepOf', {
							values: { n: form.currentStep, label: stepLabels[form.currentStep - 1].label },
							default: `Step ${form.currentStep} of 5 — ${stepLabels[form.currentStep - 1].label}`
						})}
					</p>
				{/if}
				<WizardSteps
					{form}
					onNext={handleNext}
					onBack={handleBack}
					onSubmit={form.currentStep === 5 ? handleSubmit : undefined}
					onUploadDocument={handleUploadDocument}
					onRemoveDocument={handleRemoveDocument}
					onProbeKb={handleProbeKb}
					submitting={submitting || assistantCreating}
					uploading={uploading}
					removing={removingDocument}
					probing={probing}
					nextDisabled={nextDisabled()}
				/>
				{#if assistantCreating}
					<p class="text-xs text-blue-600 mt-3">
						{$_('workshop.creatingAssistant', { default: 'Creating your assistant…' })}
					</p>
				{/if}
			</section>

			<!-- Chat + observability. The panel is the through-line of the wizard
			     (D2): it carries the step's own evidence from step 2 on, not just
			     the last chat exchange. -->
			<section class="lg:col-span-3 space-y-6">
				<!-- Formative feedback (after submit / on restore) -->
				{#if evaluating || evaluation}
					<FormativeFeedback {evaluation} {evaluating} />
				{/if}

				{#if panelVisible}
					<div class="border rounded-lg p-4 bg-white shadow-sm">
						<h2 class="text-sm font-semibold mb-3">
							{$_('workshop.observabilityTitle', { default: 'What your assistant received' })}
						</h2>
						<ObservabilityPanel
							{obsData}
							{obsRequest}
							{toolEvents}
							documents={documentFiles}
							{probe}
							toolDefinitions={form.currentStep === 4 ? toolsPayload : null}
							step={form.currentStep}
							ragMode={form.ragMode === 'off' ? 'off' : 'on'}
						/>
					</div>
				{/if}

				<!-- A/B comparison (D3): shown once the student has run a turn -->
				{#if form.currentStep === 5 && (form.obsHistory || []).length > 0}
					<RagComparison history={form.obsHistory} />
				{/if}

				<!-- Chat panel -->
				<div class="border rounded-lg bg-white shadow-sm">
					<div class="border-b px-4 py-3">
						<h2 class="text-sm font-semibold">{$_('workshop.testChat', { default: 'Test your assistant' })}</h2>
						<p class="text-xs text-gray-500 mt-0.5">
							{#if assistantId}
								{$_('workshop.assistantLabel', { default: 'Assistant' })} #{assistantId} — {form.assistantName}
							{:else}
								{$_('workshop.noAssistantYet', { default: 'Finish step 1 to create your assistant first.' })}
							{/if}
						</p>
					</div>

					<!-- Messages -->
					<div class="h-80 overflow-y-auto p-4 space-y-3">
						{#if chatMessages.length === 0}
							<p class="text-sm text-gray-400 text-center pt-16">
								{$_('workshop.chatEmpty', { default: 'Send a message to test your assistant.' })}
							</p>
						{:else}
							{#each chatMessages as m, i (i)}
								{#if !m.hidden}
									<div class="flex {m.role === 'user' ? 'justify-end' : 'justify-start'}">
										<div class="max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap {m.role === 'user'
											? 'bg-blue-600 text-white'
											: 'bg-gray-100 text-gray-800'}">
											{#if m.role === 'assistant' && m.content === '' && streaming && i === chatMessages.length - 1}
												<span class="text-gray-400">…</span>
											{:else}
												{m.content}
											{/if}
										</div>
									</div>
								{/if}
							{/each}
							{#if streaming}
								<div class="text-xs text-gray-400 pl-1">
									{$_('workshop.streaming', { default: 'streaming…' })}
								</div>
							{/if}
						{/if}
					</div>

					<!-- Input -->
					<div class="border-t p-3 flex gap-2">
						<input
							class="flex-1 border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
							placeholder={$_('workshop.chatPlaceholder', { default: 'Ask your assistant something…' })}
							bind:value={chatInput}
							onkeydown={(e) => { if (e.key === 'Enter' && !streaming) handleSend(); }}
							disabled={streaming}
						/>
						{#if streaming}
							<button class="px-4 py-2 border rounded text-sm hover:bg-gray-50" onclick={handleStop}>
								{$_('workshop.stop', { default: 'Stop' })}
							</button>
						{:else}
							<button
								class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
								onclick={handleSend}
								disabled={!chatInput.trim()}
							>{$_('workshop.send', { default: 'Send' })}</button>
						{/if}
					</div>
				</div>
			</section>
		</div>
	{/if}
</div>
