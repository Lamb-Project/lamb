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
	 *   submitting?: boolean,
	 *   nextDisabled?: boolean
	 * }}
	 */
	let { form, onNext, onBack, onSubmit, submitting = false, nextDisabled = false } = $props();

	/** @param {string} field */
	function bindField(field) {
		return (/** @type {Event} */ e) => {
			/** @type {any} */ (form)[field] = /** @type {HTMLInputElement} */ (e.target).value;
		};
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
				<div class="border rounded p-3 bg-green-50 flex items-center justify-between">
					<span class="text-sm truncate">📎 {form.attachedFileMeta.name}</span>
					<button
						class="text-xs text-red-600 hover:underline"
						onclick={() => { form.attachedFilePath = ''; form.attachedFileMeta = null; }}
					>Remove</button>
				</div>
			{:else}
				<div class="border-2 border-dashed rounded p-6 text-center text-sm text-gray-500">
					<p>Document upload is not yet wired; content is not stored.</p>
				</div>
				<button
					class="px-4 py-2 border rounded text-sm hover:bg-gray-50"
					onclick={() => {
						form.attachedFilePath = '/uploads/placeholder.pdf';
						form.attachedFileMeta = { name: 'placeholder.pdf', path: '/uploads/placeholder.pdf' };
					}}
				>Simulate attachment</button>
			{/if}
		</div>
	{:else if form.currentStep === 3}
		<!-- Step 3: Connect KB -->
		<div class="space-y-3">
			<label class="block text-sm font-medium text-gray-700" for="ws-kb">Knowledge base collection</label>
			<input
				id="ws-kb"
				value={form.kbCollection}
				oninput={bindField('kbCollection')}
				class="w-full border rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
				placeholder="e.g. fractions-lab"
			/>
			{#if form.kbCollection}
				<button
					class="px-4 py-2 border rounded text-sm hover:bg-gray-50"
					onclick={() => {
						form.selectedKbId = form.kbCollection;
						form.kbVerificationResult = { ok: true, collection: form.kbCollection };
					}}
				>Use this collection</button>
				{#if form.selectedKbId}
					<p class="text-xs text-green-600">✓ Connected to <code>{form.selectedKbId}</code></p>
				{/if}
			{/if}
			<p class="text-xs text-gray-500">KB wiring is not yet wired; this records the collection name.</p>
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