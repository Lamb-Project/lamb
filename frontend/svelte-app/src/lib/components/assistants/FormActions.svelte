<!-- src/lib/components/assistants/FormActions.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore';
	import { sanitizeName } from '$lib/utils/nameSanitizer';

	let {
		formState,
		formLoading = false,
		formError = '',
		successMessage = '',
		name = '',
		oncancel
	} = $props();

	let sanitizedNameInfo = $derived(sanitizeName(name));
	let showSanitizationPreview = $derived(formState === 'create' && sanitizedNameInfo.wasModified);
</script>

{#if formError}
	<p class="text-sm text-red-600 mt-4 p-2 border border-red-200 bg-red-50 rounded">Error: {formError}</p>
{/if}
{#if successMessage && formState !== 'edit'}
	<p class="text-sm text-green-600 mt-4 p-2 border border-green-200 bg-green-50 rounded">{successMessage}</p>
{/if}

<div class="pt-5">
	<div class="flex justify-end space-x-3">
		{#if formState === 'edit'}
			<button
				type="button"
				onclick={oncancel}
				disabled={formLoading}
				class="py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
			>
				{$_('common.cancel', { default: 'Cancel' })}
			</button>
		{/if}
		{#if showSanitizationPreview}
			<div class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
				<div class="flex items-center">
					<svg class="w-5 h-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
					</svg>
					<div class="flex-1">
						<p class="text-sm font-semibold text-blue-800">
							{$_('assistants.form.name.willBeSaved', { default: 'Will be saved as:' })}
						</p>
						<code class="inline-block mt-1 px-3 py-1 bg-blue-100 rounded text-blue-900 font-mono text-sm">{sanitizedNameInfo.sanitized}</code>
					</div>
				</div>
			</div>
		{/if}
		<button
			type="submit"
			form="assistant-form-main"
			disabled={formLoading || (formState === 'create' && !$assistantConfigStore.systemCapabilities)}
			class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
		>
			{#if formState === 'create'}
				{formLoading ? $_('common.saving', { default: 'Saving...' }) : $_('common.save', { default: 'Save' })}
			{:else}
				{formLoading ? $_('common.saving', { default: 'Saving...' }) : $_('common.saveChanges', { default: 'Save Changes' })}
			{/if}
		</button>
	</div>
</div>
