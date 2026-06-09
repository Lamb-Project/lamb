<!-- src/lib/components/assistants/FormActions.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore';

	let { formState, formLoading = false, formError = '', successMessage = '', oncancel } = $props();
</script>

{#if formError}
	<p class="mt-4 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-600">
		Error: {formError}
	</p>
{/if}
{#if successMessage && formState !== 'edit'}
	<p class="mt-4 rounded border border-green-200 bg-green-50 p-2 text-sm text-green-600">
		{successMessage}
	</p>
{/if}

<div class="pt-5">
	<div class="flex justify-end space-x-3">
		{#if formState === 'edit'}
			<button
				type="button"
				onclick={oncancel}
				disabled={formLoading}
				class="focus:ring-brand rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
			>
				{$_('common.cancel', { default: 'Cancel' })}
			</button>
		{/if}
		<button
			type="submit"
			form="assistant-form-main"
			disabled={formLoading ||
				(formState === 'create' && !$assistantConfigStore.systemCapabilities)}
			class="bg-brand hover:bg-brand-hover focus:ring-brand inline-flex justify-center rounded-md border border-transparent px-4 py-2 text-sm font-medium text-white shadow-sm focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
		>
			{#if formState === 'create'}
				{formLoading
					? $_('common.saving', { default: 'Saving...' })
					: $_('common.save', { default: 'Save' })}
			{:else}
				{formLoading
					? $_('common.saving', { default: 'Saving...' })
					: $_('common.saveChanges', { default: 'Save Changes' })}
			{/if}
		</button>
	</div>
</div>
