<script>
	// src/lib/components/workshop/WizardSteps.svelte
	// 5-step build wizard body. Pure presentational: the page controller owns
	// the form store (createWorkshopFormState) and API calls; this component
	// binds inputs to form fields and emits next/back.
	//
	// Steps (Lean MVP):
	//   1. Instructions → 2. Attach document → 3. Connect KB →
	//   4. Add tool → 5. Test & reflect

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
			<p class="text-xs text-gray-500 mt-1">System prompt for your assistant.</p>
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
						>Remove</button>
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
		</div>
	{:else if form.currentStep === 3}
		<!-- Step 3: Connect KB + verify retrieval -->
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

			{#if form.kbVerificationResult}
				{@const results = form.kbVerificationResult.results || []}
				<div class="border rounded p-3 bg-gray-50">
					<h4 class="text-xs font-semibold uppercase text-gray-500">
						{$_('workshop.kbRetrieved', { default: 'Excerpts your assistant can retrieve' })}
					</h4>
					{#if results.length === 0}
						<p class="text-xs text-gray-400 mt-1">
							{$_('workshop.kbNoHits', { default: 'No matching excerpts — try a different question or document.' })}
						</p>
					{:else}
						<ol class="text-xs mt-2 space-y-2">
							{#each results as r, i (i)}
								<li class="border-t pt-2 first:border-t-0 first:pt-0">
									<span class="font-mono text-gray-500">
										{$_('workshop.similarity', { default: 'similarity' })} {r.similarity?.toFixed?.(3) ?? r.similarity}
									</span>
									<p class="mt-0.5 whitespace-pre-wrap">{r.data}</p>
								</li>
							{/each}
						</ol>
					{/if}
				</div>
			{/if}
		</div>
	{:else if form.currentStep === 4}
		<!-- Step 4: Add tool -->
		<div class="space-y-3">
			<p class="text-sm font-medium text-gray-700">Select tools your assistant can call</p>
			<label class="flex items-center gap-2 border rounded p-3 cursor-pointer">
				<input type="checkbox" checked={form.selectedTools.includes('calculator')} onchange={() => toggleTool('calculator')} />
				<span class="text-sm">🧮 Calculator</span>
			</label>
			<label class="flex items-center gap-2 border rounded p-3 cursor-pointer">
				<input type="checkbox" checked={form.selectedTools.includes('kb_query')} onchange={() => toggleTool('kb_query')} />
				<span class="text-sm">📚 Knowledge Base Query</span>
			</label>
			<label class="flex items-center gap-2 border rounded p-3 opacity-50">
				<input type="checkbox" disabled checked={false} />
				<span class="text-sm">🖥️ Sandbox Execution (unavailable)</span>
			</label>
		</div>
	{:else}
		<!-- Step 5: Test & reflect -->
		<div class="space-y-3">
			<p class="text-sm text-gray-700">Chat panel appears below — send a message to test your assistant, watch the observability dashboard update live.</p>
			<label class="block text-sm font-medium text-gray-700" for="ws-reflection">Reflection</label>
			<textarea
				id="ws-reflection"
				bind:value={form.reflection}
				rows="4"
				class="w-full border rounded-md p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
				placeholder="What did you notice about what your assistant received?"
			></textarea>
			{#if onSubmit}
				<button
					class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
					disabled={submitting}
					onclick={onSubmit}
				>{submitting ? 'Submitting…' : $_('workshop.submit', { default: 'Submit workshop' })}</button>
			{/if}
		</div>
	{/if}

	<!-- Navigation -->
	<div class="flex justify-between pt-4 border-t mt-6">
		{#if form.currentStep > 1}
			<button class="px-4 py-2 border rounded text-sm hover:bg-gray-50" onclick={onBack}>← Back</button>
		{:else}
			<span></span>
		{/if}
		{#if form.currentStep < 5}
			<button
				class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
				disabled={nextDisabled}
				onclick={onNext}
			>Next →</button>
		{/if}
	</div>
</div>