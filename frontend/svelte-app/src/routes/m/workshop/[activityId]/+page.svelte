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

	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { _ } from '$lib/i18n';
	import { createWorkshopFormState } from '$lib/components/workshop/logic/workshopFormState.svelte.js';
	import WizardSteps from '$lib/components/workshop/WizardSteps.svelte';
	import ObservabilityPanel from '$lib/components/workshop/ObservabilityPanel.svelte';
	import { sendWorkshopChat } from '$lib/services/workshopChatService.js';
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
	let loading = $state(true);
	/** @type {boolean} */
	let assistantCreating = $state(false);
	/** @type {boolean} */
	let submitting = $state(false);

	// ── Chat + observability ──
	/** @type {Array<{role: string, content: string}>} */
	let chatMessages = $state([]);
	let chatInput = $state('');
	let streaming = $state(false);
	/** @type {AbortController | null} */
	let abortController = $state(null);
	/** @type {any | null} */
	let obsData = $state(null);
	/** @type {Array<any>} */
	let toolEvents = $state([]);

	/** @type {number | null} */
	let assistantId = $state(null);

	// Token payload decode (JWT middle segment, base64url → JSON). No crypto;
	// the server re-verifies the token on every authenticated call.
	/** @param {string} jwt */
	function decodeTokenPayload(jwt) {
		try {
			const part = jwt.split('.')[1] || '';
			const b64 = part.replace(/-/g, '+').replace(/_/g, '/');
			const pad = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
			const json = decodeURIComponent(
				atob(pad)
					.split('')
					.map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
					.join('')
			);
			return JSON.parse(json);
		} catch (e) {
			console.error('Failed to decode token payload:', e);
			return {};
		}
	}

	async function fetchSession() {
		const res = await fetch(
			`/lamb/v1/workshop/sessions/${encodeURIComponent(sessionId)}`,
			{ headers: { token } }
		);
		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			throw new Error(err.detail || `Failed to load session (${res.status})`);
		}
		return res.json();
	}

	/** @param {string} path @param {Object} [body] */
	async function wsPost(path, body = {}) {
		const res = await fetch(`/lamb/v1/workshop${path}`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', token },
			body: JSON.stringify(body),
		});
		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			throw new Error(err.detail || `Request failed (${res.status})`);
		}
		return res.json();
	}

	/** @param {string} path @param {Object} [body] */
	async function wsPatch(path, body = {}) {
		const res = await fetch(`/lamb/v1/workshop${path}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json', token },
			body: JSON.stringify(body),
		});
		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			throw new Error(err.detail || `Request failed (${res.status})`);
		}
		return res.json();
	}

	onMount(async () => {
		activityId = /** @type {string} */ ($page.params.activityId);
		const urlToken = $page.url.searchParams.get('token') || '';
		token = urlToken;

		if (!token) {
			error = 'Missing workshop token. This page must be opened from an LTI launch link.';
			loading = false;
			return;
		}

		const payload = decodeTokenPayload(token);
		sessionId = payload.session_id || '';

		if (!sessionId) {
			error = 'Token payload is missing session_id.';
			loading = false;
			return;
		}

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
			chatMessages = form.chatMessages || [];
		} catch (/** @type {any} */ e) {
			console.error('[workshop] session load failed:', e);
			formStore = createWorkshopFormState({});
			form = formStore.form;
			error = e?.message || 'Failed to load your workshop session.';
		} finally {
			loading = false;
		}
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
				// Pass the student's text through verbatim (no "Answer:" / "Context:"
				// wrapper) so the LLM sees the raw input — clearer for the student
				// observability panel. RAG context is injected by the processor
				// only when the template actually contains {context}.
				prompt_template:
					'{user_input}',
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
					rag_processor: '',
				}),
				rag_top_k: 3,
				rag_collections: form.selectedKbId ? `["${form.selectedKbId}"]` : '[]',
			};
			const result = await wsPost(`/sessions/${sessionId}/assistant`, body);
			form.assistantId = assistantId = result.assistant_id;
			persistBuildState();
			return assistantId;
		} catch (/** @type {any} */ e) {
			error = e?.message || 'Failed to create your assistant.';
			return null;
		} finally {
			assistantCreating = false;
		}
	}

	async function persistBuildState() {
		// Best-effort: the submitted session record persists build_state on
		// submit; here we keep the local store in sync for the UI. (A dedicated
		// PATCH endpoint lands later.)
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
			error = e?.message || 'Failed to save your instructions.';
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
		// Persist the current step-1 instructions so the LLM (and the
		// observability panel) always reflect what the student set.
		await syncInstructions();

		chatMessages = [...chatMessages, { role: 'user', content: text }, { role: 'assistant', content: '' }];
		const assistantSlot = chatMessages.length - 1;
		chatInput = '';
		streaming = true;
		toolEvents = [];
		obsData = null;
		abortController = new AbortController();

		// Tool definitions passed to the backend (calculator default per wizard).
		const tools = (form.selectedTools || ['calculator']).map((/** @type {string} */ name) => ({
			type: 'function',
			function: { name },
		}));

		let assistantBuffer = '';
		await sendWorkshopChat(
			{
				sessionId,
				assistantId,
				token,
				messages: chatMessages.filter((m) => m.content !== ''),
				opts: { tools, observability: true },
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
					obsData = data;
				},
				onToolEvent: (evt) => {
					toolEvents = [...toolEvents, evt];
				},
				onDone: () => {
					streaming = false;
					abortController = null;
					persistBuildState();
				},
				onError: (msg) => {
					streaming = false;
					abortController = null;
					error = msg || 'Stream error';
				},
			},
			abortController.signal
		);
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
			await wsPost(`/sessions/${sessionId}/submit`, {
				saved_chat: JSON.stringify(chatMessages),
				reflection: form.reflection || '',
			});
			form.stepValid = { ...form.stepValid, submitted: true };
			alert('Workshop submitted ✓');
		} catch (/** @type {any} */ e) {
			error = e?.message || 'Submit failed';
		} finally {
			submitting = false;
		}
	}

	function nextDisabled() {
		return !form || !formStore || !formStore.isStepComplete(form.currentStep);
	}

	/** @type {Array<{n: number, label: string}>} */
	const stepLabels = [
		{ n: 1, label: 'Instructions' },
		{ n: 2, label: 'Document' },
		{ n: 3, label: 'Knowledge Base' },
		{ n: 4, label: 'Tools' },
		{ n: 5, label: 'Test & Reflect' },
	];
</script>

<svelte:head>
	<title>AI Workshop</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 py-6">
	<!-- Header -->
	<header class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold">{$_('workshop.title', { default: 'AI Workshop' })}</h1>
			<p class="text-sm text-gray-500">Activity #{activityId || '—'}</p>
		</div>
	</header>

	{#if loading}
		<div class="py-16 text-center text-gray-500">Loading your workshop…</div>
	{:else if error && !form}
		<div class="border rounded p-4 bg-red-50 text-red-700 text-sm">
			<p class="font-medium">Workshop unavailable</p>
			<p class="mt-1">{error}</p>
		</div>
	{:else}
		{#if error}
			<div class="mb-4 border rounded p-3 bg-amber-50 text-amber-800 text-sm">{error}</div>
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
						Step {form.currentStep} of 5 — {stepLabels[form.currentStep - 1].label}
					</p>
				{/if}
				<WizardSteps
					{form}
					onNext={handleNext}
					onBack={handleBack}
					onSubmit={form.currentStep === 5 ? handleSubmit : undefined}
					submitting={submitting || assistantCreating}
					nextDisabled={nextDisabled()}
				/>
				{#if assistantCreating}
					<p class="text-xs text-blue-600 mt-3">Creating your assistant…</p>
				{/if}
			</section>

			<!-- Chat + observability (appears from step 5, but dashboard also aids step 1-4) -->
			<section class="lg:col-span-3 space-y-6">
				<!-- Observability dashboard always visible once chat starts -->
				{#if obsData || toolEvents.length > 0 || chatMessages.length > 0}
					<div class="border rounded-lg p-4 bg-white shadow-sm">
						<h2 class="text-sm font-semibold mb-3">{$_('workshop.observabilityTitle', { default: 'What your assistant received' })}</h2>
						<ObservabilityPanel {obsData} {toolEvents} />
					</div>
				{/if}

				<!-- Chat panel -->
				<div class="border rounded-lg bg-white shadow-sm">
					<div class="border-b px-4 py-3">
						<h2 class="text-sm font-semibold">{$_('workshop.testChat', { default: 'Test your assistant' })}</h2>
						<p class="text-xs text-gray-500 mt-0.5">
							{#if assistantId}
								Assistant #{assistantId} — {form.assistantName}
							{:else}
								Finish step 1 to create your assistant first.
							{/if}
						</p>
					</div>

					<!-- Messages -->
					<div class="h-80 overflow-y-auto p-4 space-y-3">
						{#if chatMessages.length === 0}
							<p class="text-sm text-gray-400 text-center pt-16">Send a message to test your assistant.</p>
						{:else}
							{#each chatMessages as m, i (i)}
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
							{/each}
							{#if streaming}
								<div class="text-xs text-gray-400 pl-1">streaming…</div>
							{/if}
						{/if}
					</div>

					<!-- Input -->
					<div class="border-t p-3 flex gap-2">
						<input
							class="flex-1 border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
							placeholder="Ask your assistant something…"
							bind:value={chatInput}
							onkeydown={(e) => { if (e.key === 'Enter' && !streaming) handleSend(); }}
							disabled={streaming}
						/>
						{#if streaming}
							<button class="px-4 py-2 border rounded text-sm hover:bg-gray-50" onclick={handleStop}>
								Stop
							</button>
						{:else}
							<button
								class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
								onclick={handleSend}
								disabled={!chatInput.trim()}
							>Send</button>
						{/if}
					</div>
				</div>
			</section>
		</div>
	{/if}
</div>