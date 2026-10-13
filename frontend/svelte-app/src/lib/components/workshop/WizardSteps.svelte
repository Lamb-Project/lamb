<script>
	// src/lib/components/workshop/WizardSteps.svelte
	// 5-step build wizard body. Pure presentational: the page controller owns
	// the form store (createWorkshopFormState) and API calls; this component
	// binds inputs to form fields and emits next/back.
	//
	// Steps (Lean MVP):
	//   1. Instructions → 2. Attach document → 3. Connect KB →
	//   4. Add tool → 5. Test & reflect
	//
	// Every student-visible string is localized (en/es/ca/eu) — students reach
	// this page straight from the LMS, with no Creator session in between.
	// Step 3's retrieval results are rendered by the shared ObservabilityPanel
	// (the page owns that panel), so all five steps observe the same way (D2).

	import { _ } from '$lib/i18n';

	/**
	 * @type {{
	 *   form: ReturnType<typeof import('./logic/workshopFormState.svelte.js').createWorkshopFormState>['form'],
	 *   onNext?: () => void,
	 *   onBack?: () => void,
	 *   onSubmit?: () => void,
	 *   onUploadDocument?: (file: File) => void,
	 *   onProbeKb?: () => void,
	 *   submitting?: boolean,
	 *   uploading?: boolean,
	 *   probing?: boolean,
	 *   nextDisabled?: boolean
	 * }}
	 */
	let {
		form,
		onNext,
		onBack,
		onSubmit,
		onUploadDocument,
		onProbeKb,
		submitting = false,
		uploading = false,
		probing = false,
		nextDisabled = false
	} = $props();

	/** @param {string} field */
	function bindField(field) {
		return (/** @type {Event} */ e) => {
			/** @type {any} */ (form)[field] = /** @type {HTMLInputElement} */ (e.target).value;
		};
	}

	/** @param {Event} e */
	function handleFile(e) {
		const input = /** @type {HTMLInputElement} */ (e.target);
		const file = input.files && input.files[0];
		if (file && onUploadDocument) onUploadDocument(file);
	}

	/** @param {string} toolId */
	function toggleTool(toolId) {
		if (form.selectedTools.includes(toolId)) {
			form.selectedTools = form.selectedTools.filter((/** @type {string} */ t) => t !== toolId);
		} else {
			form.selectedTools = [...form.selectedTools, toolId];
		}
	}

	/**
	 * The exact tool definitions this wizard sends to the backend (name-only —
	 * the backend completes them against the canonical schema). Shown verbatim
	 * in step 4 so "adding a tool" is not a leap of faith (D2).
	 */
	const toolsPayload = $derived(
		(form.selectedTools || []).map((/** @type {string} */ name) => ({
			type: 'function',
			function: { name }
		}))
	);

	/** @param {boolean} on */
	function setRagMode(on) {
		form.ragMode = on ? 'on' : 'off';
	}
</script>

<div class="space-y-6">
	{#if form.currentStep === 1}
		<!-- Step 1: Instructions -->
		<div>
			<label class="block text-sm font-medium text-gray-700 mb-1" for="ws-instructions">
				{$_('workshop.instructionsPlaceholder', { default: 'Write what your assistant should do and how to answer...' })}
			</label>
			<textarea
				id="ws-instructions"
				bind:value={form.instructions}
				rows="8"
				class="w-full border rounded-md p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
				placeholder="You are a helpful tutor that explains fractions step by step..."
			></textarea>
			<p class="text-xs text-gray-500 mt-1">
				{$_('workshop.instructionHint', { default: 'System prompt for your assistant.' })}
			</p>
		</div>
	{:else if form.currentStep === 2}
		<!-- Step 2: Attach document -->
		<div class="space-y-3">
			{#if form.attachedFileMeta}
				<div class="border rounded p-3 bg-green-50">
					<div class="flex items-center justify-between">
						<span class="text-sm truncate">📎 {form.attachedFileMeta.name}</span>
						<button
							class="text-xs text-red-600 hover:underline"
							onclick={() => { form.attachedFilePath = ''; form.attachedFileMeta = null; form.documentStatus = ''; }}
						>{$_('workshop.remove', { default: 'Remove' })}</button>
					</div>
					{#if form.documentStatus === 'completed'}
						<p class="text-xs text-green-700 mt-1">
							{$_('workshop.uploadDone', { default: 'Document ingested — it is now knowledge your assistant can retrieve.' })}
						</p>
					{:else if form.documentStatus === 'failed'}
						<p class="text-xs text-red-600 mt-1">
							{$_('workshop.uploadFailed', { default: 'Ingestion failed. Remove and try another file.' })}
						</p>
					{:else}
						<p class="text-xs text-blue-600 mt-1">
							{$_('workshop.uploading', { default: 'Ingesting your document…' })}
						</p>
					{/if}
				</div>
			{:else}
				<div class="border-2 border-dashed rounded p-6 text-center text-sm text-gray-500">
					<p>
						{$_('workshop.attachDocHint', { default: 'Choose a file (PDF, text or markdown). It will be ingested into a knowledge base for your assistant.' })}
					</p>
					<input
						type="file"
						class="mt-3 text-xs"
						disabled={uploading}
						onchange={handleFile}
					/>
				</div>
				{#if uploading}
					<p class="text-xs text-blue-600">
						{$_('workshop.uploading', { default: 'Ingesting your document…' })}
					</p>
				{/if}
			{/if}
			<p class="text-xs text-gray-500">
				{$_('workshop.documentStepTitle', { default: 'What happened to your document' })} —
				{$_('workshop.panelHint', { default: 'see the panel for how it was split.' })}
			</p>
		</div>
	{:else if form.currentStep === 3}
		<!-- Step 3: Connect KB + verify retrieval (results render in the panel) -->
		<div class="space-y-3">
			<label class="block text-sm font-medium text-gray-700" for="ws-kb">
				{$_('workshop.kbCollection', { default: 'Knowledge base collection' })}
			</label>
			<input
				id="ws-kb"
				value={form.selectedKbId}
				readonly
				class="w-full border rounded-md p-2 text-sm bg-gray-100 text-gray-600 cursor-not-allowed focus:outline-none"
				placeholder={$_('workshop.kbCollectionEmpty', { default: 'Created automatically when you upload a document in step 2.' })}
			/>
			<label class="block text-sm font-medium text-gray-700" for="ws-kb-query">
				{$_('workshop.kbTestQuestion', { default: 'Ask a test question' })}
			</label>
			<input
				id="ws-kb-query"
				value={form.kbQuery}
				oninput={bindField('kbQuery')}
				class="w-full border rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
				placeholder={$_('workshop.kbTestPlaceholder', { default: 'What does the document say about…?' })}
			/>
			<button
				class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
				disabled={probing || !form.kbQuery.trim()}
				onclick={() => onProbeKb && onProbeKb()}
			>{probing
					? $_('workshop.probing', { default: 'Retrieving…' })
					: $_('workshop.verifyKb', { default: 'Test retrieval' })}</button>
			<p class="text-xs text-gray-500">
				{$_('workshop.probeHitsTitle', { default: 'Excerpts retrieved by this test question' })} —
				{$_('workshop.panelHint', { default: 'see the panel for how it was split.' })}
			</p>
		</div>
	{:else if form.currentStep === 4}
		<!-- Step 4: Add tool -->
		<div class="space-y-3">
			<p class="text-sm font-medium text-gray-700">
				{$_('workshop.selectTools', { default: 'Select tools your assistant can call' })}
			</p>
			<label class="flex items-center gap-2 border rounded p-3 cursor-pointer">
				<input type="checkbox" checked={form.selectedTools.includes('calculator')} onchange={() => toggleTool('calculator')} />
				<span class="text-sm">🧮 {$_('workshop.calculator', { default: 'Calculator' })}</span>
			</label>
			<label class="flex items-center gap-2 border rounded p-3 cursor-pointer">
				<input type="checkbox" checked={form.selectedTools.includes('kb_query')} onchange={() => toggleTool('kb_query')} />
				<span class="text-sm">📚 {$_('workshop.kbQuery', { default: 'Knowledge Base Query' })}</span>
			</label>
			<label class="flex items-center gap-2 border rounded p-3 opacity-50">
				<input type="checkbox" disabled checked={false} />
				<span class="text-sm">🖥️ {$_('workshop.sandbox', { default: 'Sandbox Execution (unavailable)' })}</span>
			</label>

			<div class="border rounded p-3 bg-gray-50">
				<h4 class="text-xs font-semibold uppercase text-gray-500">
					{$_('workshop.toolsPreviewTitle', { default: 'Tools that will be sent to the model' })}
				</h4>
				{#if toolsPayload.length === 0}
					<p class="text-xs text-gray-400 mt-1">
						{$_('workshop.toolsPreviewEmpty', { default: 'No tools selected — the assistant will answer with text only.' })}
					</p>
				{:else}
					<pre class="text-[10px] whitespace-pre-wrap mt-1 text-gray-600">{JSON.stringify(toolsPayload, null, 2)}</pre>
				{/if}
			</div>
		</div>
	{:else}
		<!-- Step 5: Test & reflect -->
		<div class="space-y-4">
			<p class="text-sm text-gray-700">
				{$_('workshop.chatHint', { default: 'Send a message to test your assistant, and watch what it receives below.' })}
			</p>

			<!-- A/B experiment: knowledge base on vs off (D3) -->
			<div class="border rounded p-3">
				<div class="flex items-center justify-between gap-2">
					<span class="text-sm font-medium">
						{$_('workshop.abToggle', { default: 'Knowledge base' })}
					</span>
					<div class="inline-flex rounded border overflow-hidden text-xs" role="group">
						<button
							class="px-3 py-1 {form.ragMode !== 'off' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600'}"
							aria-pressed={form.ragMode !== 'off'}
							data-testid="rag-mode-on"
							onclick={() => setRagMode(true)}
						>{$_('workshop.abOn', { default: 'On' })}</button>
						<button
							class="px-3 py-1 {form.ragMode === 'off' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600'}"
							aria-pressed={form.ragMode === 'off'}
							data-testid="rag-mode-off"
							onclick={() => setRagMode(false)}
						>{$_('workshop.abOff', { default: 'Off' })}</button>
					</div>
				</div>
				<p class="text-xs text-gray-500 mt-2">
					{$_('workshop.abHint', { default: 'Ask the same question twice — once with the knowledge base on and once off — and compare the answers.' })}
				</p>
			</div>

			<!-- Reflection: three fixed questions (D5) -->
			<div class="space-y-2">
				<h4 class="text-sm font-semibold">
					{$_('workshop.reflectionTitle', { default: 'Reflection' })}
				</h4>
				{#each [
					{ key: 'q1', label: $_('workshop.reflectionQ1', { default: 'What did you ask your assistant to do, and why?' }) },
					{ key: 'q2', label: $_('workshop.reflectionQ2', { default: 'What did you see in the panels — what did the assistant actually receive?' }) },
					{ key: 'q3', label: $_('workshop.reflectionQ3', { default: 'What would you change in your design after testing it?' }) }
				] as question (question.key)}
					<label class="block text-xs font-medium text-gray-700" for="ws-reflection-{question.key}">
						{question.label}
					</label>
					<textarea
						id="ws-reflection-{question.key}"
						data-testid="reflection-{question.key}"
						bind:value={form.reflectionAnswers[question.key]}
						rows="2"
						class="w-full border rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
					></textarea>
				{/each}
				{#if form.reflection}
					<p class="text-xs text-gray-500">
						{$_('workshop.reflectionLegacyHint', { default: 'Your earlier reflection is kept below as written.' })}
					</p>
					<textarea
						readonly
						rows="3"
						value={form.reflection}
						class="w-full border rounded-md p-2 text-xs bg-gray-50 text-gray-600"
					></textarea>
				{/if}
			</div>

			{#if onSubmit}
				<button
					class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
					disabled={submitting}
					onclick={onSubmit}
				>{submitting
						? $_('workshop.submitting', { default: 'Submitting…' })
						: $_('workshop.submit', { default: 'Submit workshop' })}</button>
			{/if}
		</div>
	{/if}

	<!-- Navigation -->
	<div class="flex justify-between pt-4 border-t mt-6">
		{#if form.currentStep > 1}
			<button class="px-4 py-2 border rounded text-sm hover:bg-gray-50" onclick={onBack}>
				← {$_('workshop.back', { default: 'Back' })}
			</button>
		{:else}
			<span></span>
		{/if}
		{#if form.currentStep < 5}
			<button
				class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
				disabled={nextDisabled}
				onclick={onNext}
			>{$_('workshop.next', { default: 'Next' })} →</button>
		{/if}
	</div>
</div>