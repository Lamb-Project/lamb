<script>
	// src/lib/components/workshop/ObservabilityPanel.svelte
	// The single rendering surface for "what is my assistant working with?"
	// across all five steps (D1 + D2).
	//
	// Data comes from three props:
	//   - obsData     — latest observability frame (has `phase` = request|result)
	//   - obsRequest  — the "request" frame, kept separately so the panel can
	//                   show what is *about to be* sent while the model is still
	//                   generating
	//   - documents   — step 2: the KB file registry (how the upload was chunked)
	//   - toolDefinitions — step 4: the tool JSON that will be sent
	//   - toolEvents  — accumulated tool timeline entries
	// The parent page owns all of these; this component is pure rendering.

	import { _ } from '$lib/i18n';
	import { describeDocument, formatBytes } from './logic/workshopObservations.svelte.js';

	/**
	 * @type {{
	 *   obsData?: any | null,
	 *   obsRequest?: any | null,
	 *   toolEvents?: Array<any>,
	 *   documents?: Array<any>,
	 *   toolDefinitions?: Array<any> | null,
	 *   step?: number,
	 *   ragMode?: string
	 * }}
	 */
	let {
		obsData = null,
		obsRequest = null,
		toolEvents = [],
		documents = [],
		toolDefinitions = null,
		step = 0,
		ragMode = 'on'
	} = $props();

	/** @type {Array<{type: string, name?: string, success?: boolean, args?: string}>} */
	let toolTimeline = $derived(toolEvents);

	/** The frame that describes what is *about* to be sent (D1). */
	let requestFrame = $derived(
		obsRequest || (obsData?.phase === 'request' ? obsData : null)
	);
	/**
	 * The frame with the messages the model finally saw.
	 *
	 * A frame without a `phase` is treated as a result frame: panels rendered
	 * from an older/other caller stay working (the field is additive).
	 */
	let resultFrame = $derived(
		obsData && obsData.phase !== 'request' ? obsData : null
	);

	/** Whether anything at all is available to show. */
	let hasAnything = $derived(
		!!requestFrame ||
			!!resultFrame ||
			toolTimeline.length > 0 ||
			documents.length > 0 ||
			(step === 4 && !!toolDefinitions)
	);

	const summarisedDocuments = $derived((documents || []).map(describeDocument));

	/**
	 * @param {{type: string, name?: string, success?: boolean, args?: string}} t
	 */
	function toolIcon(t) {
		if (t.type === 'thinking') return '🧠';
		if (t.type === 'tool_done') return t.success ? '✓' : '✗';
		return '⚡';
	}

	/**
	 * @param {{type: string, name?: string, success?: boolean, args?: string}} t
	 */
	function toolLabel(t) {
		if (t.name) return t.name;
		if (t.type === 'thinking') return 'thinking';
		return t.type;
	}

	/**
	 * Render a value as pretty JSON, falling back to string.
	 * @param {any} value
	 * @returns {string}
	 */
	function rawJson(value) {
		try {
			return JSON.stringify(value, null, 2);
		} catch {
			return String(value);
		}
	}
</script>

<div class="space-y-4">
	{#if !hasAnything}
		<div class="border rounded p-4 bg-gray-50 text-sm text-gray-500">
			{$_('workshop.panelEmpty', { default: 'Nothing to observe yet — the panel fills in as you build.' })}
		</div>
	{:else}
		<!-- A/B badge: which mode this turn ran in (D3) -->
		{#if step === 5 && (requestFrame || resultFrame)}
			<span
				class="inline-block px-2 py-0.5 rounded-full text-xs {ragMode === 'off'
					? 'bg-amber-100 text-amber-800'
					: 'bg-green-100 text-green-800'}"
				data-testid="panel-rag-mode"
			>
				{ragMode === 'off'
					? $_('workshop.ragOffBadge', { default: 'Knowledge base off' })
					: $_('workshop.ragOnBadge', { default: 'Knowledge base on' })}
			</span>
		{/if}

		<!-- Step 2: what happened to the uploaded document (deterministic facts) -->
		{#if summarisedDocuments.length > 0}
			<section class="border rounded p-3 bg-gray-50" data-testid="panel-document">
				<h4 class="text-xs font-semibold uppercase text-gray-500">
					{$_('workshop.chunksTitle', { default: 'How your document was split' })}
				</h4>
				<ul class="text-xs mt-2 space-y-2">
					{#each summarisedDocuments as doc, i (i)}
						<li class="border-t pt-2 first:border-t-0 first:pt-0">
							<div class="font-medium text-gray-700">{doc.name}</div>
							<div class="text-gray-600">
								{$_('workshop.chunksSummary', {
									values: {
										count: doc.chunks,
										size: doc.chunkSize ?? '—',
										overlap: doc.chunkOverlap ?? '—'
									},
									default: `${doc.chunks} chunks · chunk size ${doc.chunkSize ?? '—'} · overlap ${doc.chunkOverlap ?? '—'}`
								})}
							</div>
							<div class="text-gray-500">
								{formatBytes(doc.fileSize)} · {doc.status}
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<!-- Step 4: the tool definitions that will be sent -->
		{#if step === 4 && toolDefinitions}
			<section class="border rounded p-3 bg-gray-50" data-testid="panel-tools">
				<h4 class="text-xs font-semibold uppercase text-gray-500">
					{$_('workshop.toolsPreviewTitle', { default: 'Tools that will be sent to the model' })}
				</h4>
				{#if toolDefinitions.length === 0}
					<p class="text-xs text-gray-400 mt-1">
						{$_('workshop.toolsPreviewEmpty', { default: 'No tools selected — the assistant will answer with text only.' })}
					</p>
				{:else}
					<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(toolDefinitions)}</pre>
				{/if}
			</section>
		{/if}

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<!-- RAG excerpts, from whichever frame carries them -->
			{#if requestFrame?.rag_context || resultFrame?.rag_context || (requestFrame?.retrieved_sources || resultFrame?.retrieved_sources || []).length > 0}
				{@const frame = requestFrame || resultFrame}
				<section class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500">
						{$_('workshop.retrievedContext', { default: 'Retrieved context' })}
					</h4>
					{#if frame.rag_context}
						<p class="text-xs mt-1">{frame.rag_context}</p>
					{/if}
					{#if (frame.retrieved_sources || []).length > 0}
						<ol class="text-xs mt-2 space-y-1">
							{#each frame.retrieved_sources as src, i (i)}
								<li class="opacity-80">
									<span class="font-mono">{src.similarity?.toFixed?.(3) ?? src.similarity}</span>
									· {src.content}
								</li>
							{/each}
						</ol>
					{/if}
				</section>
			{/if}

			<!-- Stored system prompt for the assistant (separate from the request messages) -->
			{#if (requestFrame || resultFrame)?.system_instructions !== undefined}
				{@const frame = requestFrame || resultFrame}
				<section class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500">
						{$_('workshop.systemInstructions', { default: 'Active instructions' })}
					</h4>
					{#if frame.system_instructions}
						<p class="text-xs mt-1">{frame.system_instructions}</p>
					{:else}
						<p class="text-xs text-gray-400 mt-1">
							{$_('workshop.noSystemInstructions', { default: "None set on this assistant — that's why no role: system message appears." })}
						</p>
					{/if}
				</section>
			{/if}

			<!-- The request frame: what is about to be sent (D1) -->
			{#if requestFrame?.request_body}
				<section class="border rounded p-3 bg-blue-50" data-testid="panel-request">
					<h4 class="text-xs font-semibold uppercase text-gray-500 flex items-center justify-between gap-2">
						<span>{$_('workshop.requestPhase', { default: 'About to be sent' })}</span>
						<span class="font-mono text-gray-400">{requestFrame.request_body.model}</span>
					</h4>
					{#if (requestFrame.request_body.tools || []).length === 0}
						<p class="text-xs text-gray-400 mt-1">
							{$_('workshop.noToolsDefined', { default: 'No tools defined.' })}
						</p>
					{/if}
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80"><code>tools</code></summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(requestFrame.request_body.tools)}</pre>
					</details>
					<details class="border border-gray-200 rounded px-2 py-1">
						<summary class="opacity-80">
							<code>messages ({requestFrame.request_body.messages.length})</code>
						</summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(requestFrame.request_body.messages)}</pre>
					</details>
				</section>
			{/if}

			<!-- The result frame: the messages the model finally saw -->
			{#if resultFrame?.request_body}
				<section class="border rounded p-3 bg-gray-50" data-testid="panel-result">
					<h4 class="text-xs font-semibold uppercase text-gray-500 flex items-center justify-between gap-2">
						<span>{$_('workshop.resultPhase', { default: 'Sent to the model' })}</span>
						<span class="font-mono text-gray-400">{resultFrame.request_body.model}</span>
					</h4>
					{#if (resultFrame.request_body.tools || []).length === 0}
						<p class="text-xs text-gray-400 mt-1">
							{$_('workshop.noToolsDefined', { default: 'No tools defined.' })}
						</p>
					{/if}
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80"><code>model</code></summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{resultFrame.request_body.model}</pre>
					</details>
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80"><code>tools</code></summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(resultFrame.request_body.tools)}</pre>
					</details>
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80">
							<code>messages ({resultFrame.request_body.messages.length})</code>
						</summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(resultFrame.request_body.messages)}</pre>
					</details>
				</section>
			{:else if (resultFrame?.final_llm_messages || []).length > 0}
				<!-- Fallback for frames that carry no reconstructed request body. -->
				<section class="border rounded p-3 bg-gray-50" data-testid="panel-result">
					<h4 class="text-xs font-semibold uppercase text-gray-500">
						{$_('workshop.finalMessages', { default: 'Messages sent to LLM' })}
					</h4>
					<div class="text-xs mt-1 space-y-1">
						{#each resultFrame.final_llm_messages as msg, i (i)}
							<details class="border border-gray-200 rounded px-2 py-1" open>
								<summary class="opacity-80">
									<code>{msg.role}{#if msg.tool_call_id} › {msg.tool_call_id}{/if}</code>
								</summary>
								<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(msg)}</pre>
							</details>
						{/each}
					</div>
				</section>
			{/if}
		</div>

		<!-- Tool timeline -->
		<div class="border rounded p-3 bg-gray-50">
			<h4 class="text-xs font-semibold uppercase text-gray-500">
				{$_('workshop.toolTimeline', { default: 'Tool calls' })}
			</h4>
			{#if toolTimeline.length === 0}
				<p class="text-xs text-gray-400 mt-1">
					{$_('workshop.noToolActivity', { default: 'No tool activity yet.' })}
				</p>
			{:else}
				<div class="text-xs mt-1 space-y-1">
					{#each toolTimeline as t, i (t.type + (t.name ?? '') + i)}
						<div class="flex gap-2 items-center">
							<span>{toolIcon(t)}</span>
							<span class="font-mono">{toolLabel(t)}</span>
							{#if t.args}<span class="text-gray-500 truncate">{t.args}</span>{/if}
							{#if t.success === false}
								<span class="text-red-500">{$_('workshop.toolFailed', { default: 'failed' })}</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
