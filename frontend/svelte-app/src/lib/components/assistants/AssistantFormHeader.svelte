<!-- src/lib/components/assistants/AssistantFormHeader.svelte -->
<script>
	import { _ } from '$lib/i18n';

	/** @type {{ formState: 'edit' | 'create', assistantId: number | null, importError: string, onImportFile: (event: Event) => void }} */
	let { formState, assistantId = null, importError = '', onImportFile } = $props();

	/** @type {HTMLInputElement | null} */
	let fileInputRef = $state(null);

	function triggerFileInput() {
		fileInputRef?.click();
	}
</script>

<div class="mb-6 pb-4 border-b border-gray-200">
	<div class="flex justify-between items-center">
		<h2 class="text-2xl font-semibold text-brand">
			{#if formState === 'create'}
				{$_('assistants.form.titleCreate', { default: 'Create New Assistant' })}
			{:else}
				{$_('assistants.form.titleViewEdit', { default: 'Assistant Details' })}
				{#if assistantId} (ID: {assistantId}){/if}
			{/if}
		</h2>
		{#if formState === 'create'}
			<div>
				<button
					type="button"
					onclick={triggerFileInput}
					class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
				>
					<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
						></path>
					</svg>
					{$_('assistants.form.import.button', { default: 'Import from JSON' })}
				</button>
			</div>
		{/if}
	</div>
	{#if importError}
		<div class="mt-3 p-3 border border-red-200 bg-red-50 rounded-md">
			<div class="flex">
				<div class="flex-shrink-0">
					<svg class="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
						<path
							fill-rule="evenodd"
							d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
							clip-rule="evenodd"
						></path>
					</svg>
				</div>
				<div class="ml-3">
					<h3 class="text-sm font-medium text-red-800">
						{$_('assistants.form.import.error', { default: 'Import Error' })}
					</h3>
					<p class="mt-1 text-sm text-red-700">{importError}</p>
				</div>
			</div>
		</div>
	{/if}
</div>

<input
	bind:this={fileInputRef}
	type="file"
	accept=".json"
	onchange={onImportFile}
	style="display: none;"
/>
