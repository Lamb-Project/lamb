<!-- src/lib/components/assistants/FormActions.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore';

	let {
		formState,
		formLoading = false,
		formError = '',
		successMessage = '',
		oncancel
	} = $props();
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
