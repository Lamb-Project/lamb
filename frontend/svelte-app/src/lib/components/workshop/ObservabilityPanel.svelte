<script>
	// src/lib/components/workshop/ObservabilityPanel.svelte
	// Live dashboard: shows what the assistant received for the last exchange.
	//
	// Real-time data comes via two props:
	//   - obsData     — latest observability frame payload (build_observability_payload)
	//   - toolEvents  — accumulated tool timeline entries ({type, name, success, args})
	// The parent page owns these; this panel is pure rendering.

	/** @type {any | null} */
	let { obsData = null, toolEvents = [] } = $props();

	/** @type {Array<{type: string, name?: string, success?: boolean, args?: string}>} */
	let toolTimeline = $derived(toolEvents);

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
	{#if !obsData && toolTimeline.length === 0}
		<div class="border rounded p-4 bg-gray-50 text-sm text-gray-500">
			Send a test message to start seeing what your assistant receives.
		</div>
	{:else}
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<!-- RAG excerpts -->
			{#if obsData?.rag_context || (obsData?.retrieved_sources || []).length > 0}
				<section class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500">Retrieved context</h4>
					{#if obsData.rag_context}
						<p class="text-xs mt-1">{obsData.rag_context}</p>
					{/if}
					{#if (obsData.retrieved_sources || []).length > 0}
						<ol class="text-xs mt-2 space-y-1">
							{#each obsData.retrieved_sources as src, i (src.chunk_id ?? i)}
								<li class="opacity-80">
									<span class="font-mono">{src.similarity?.toFixed(3)}</span>
									· {src.content}
								</li>
							{/each}
						</ol>
					{/if}
				</section>
			{/if}

			<!-- Stored system prompt for the assistant (separate from the request messages) -->
			{#if obsData?.system_instructions !== undefined}
				<section class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500">System instructions (configured)</h4>
					{#if obsData.system_instructions}
						<p class="text-xs mt-1">{obsData.system_instructions}</p>
					{:else}
						<p class="text-xs text-gray-400 mt-1">None set on this assistant — that's why no <code>role: system</code> message appears.</p>
					{/if}
				</section>
			{/if}

			<!-- Request body sent to LLM (model + tools + messages) -->
			{#if obsData?.request_body}
				<section class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500 flex items-center justify-between gap-2">
						<span>Request sent to LLM</span>
						<span class="font-mono text-gray-400">{obsData.request_body.model}</span>
					</h4>
					{#if (obsData.request_body.tools || []).length === 0}
						<p class="text-xs text-gray-400 mt-1">No tools defined.</p>
					{/if}
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80">
							<code>model</code>
						</summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{obsData.request_body.model}</pre>
					</details>
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80">
							<code>tools</code>
						</summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(obsData.request_body.tools)}</pre>
					</details>
					<details class="border border-gray-200 rounded px-2 py-1" open>
						<summary class="opacity-80">
							<code>messages ({obsData.request_body.messages.length})</code>
						</summary>
						<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{rawJson(obsData.request_body.messages)}</pre>
					</details>
				</section>
			{:else if (obsData?.final_llm_messages || []).length > 0}
				<section class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500">
						Messages sent to LLM
					</h4>
					<div class="text-xs mt-1 space-y-1">
						{#each obsData.final_llm_messages as msg, i}
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
			<h4 class="text-xs font-semibold uppercase text-gray-500">Tool calls</h4>
			{#if toolTimeline.length === 0}
				<p class="text-xs text-gray-400 mt-1">No tool activity yet.</p>
			{:else}
				<div class="text-xs mt-1 space-y-1">
					{#each toolTimeline as t, i (t.type + (t.name ?? '') + i)}
						<div class="flex gap-2 items-center">
							<span>{toolIcon(t)}</span>
							<span class="font-mono">{toolLabel(t)}</span>
							{#if t.args}<span class="text-gray-500 truncate">{t.args}</span>{/if}
							{#if t.success === false}
								<span class="text-red-500">failed</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>