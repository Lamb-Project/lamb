<!-- src/lib/components/assistants/AssistantNameField.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { sanitizeName } from '$lib/utils/nameSanitizer';

	let {
		value = $bindable(''),
		formState,
		/** @type {(event: Event) => void} */
		oninput
	} = $props();

	let sanitizedNameInfo = $derived(sanitizeName(value));
	let showSanitizationPreview = $derived(formState === 'create' && sanitizedNameInfo.wasModified);
</script>

<div>
	<label for="assistant-name" class="block text-sm font-medium text-gray-700">
		{$_('assistants.form.name.label')} <span class="text-red-600">*</span>
	</label>
	{#if formState === 'edit'}
		<input
			type="text"
			id="assistant-name"
			name="name"
			bind:value
			disabled={true}
			class="focus:ring-brand focus:border-brand mt-1 block w-full rounded-md border border-gray-300 bg-gray-100 px-3 py-2 text-gray-900 shadow-sm focus:outline-none sm:text-sm"
			placeholder={$_('assistants.form.name.placeholder')}
		/>
	{:else}
		<input
			type="text"
			id="assistant-name"
			name="name"
			bind:value
			disabled={false}
			{oninput}
			class="focus:ring-brand focus:border-brand mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:outline-none sm:text-sm"
			placeholder={$_('assistants.form.name.placeholder')}
		/>
		{#if showSanitizationPreview}
			<div class="mt-2 rounded-md border border-blue-200 bg-blue-50 p-2">
				<p class="text-sm text-blue-800">
					<span class="font-semibold"
						>{$_('assistants.form.name.willBeSaved', { default: 'Will be saved as:' })}</span
					>
					<code class="ml-2 rounded bg-blue-100 px-2 py-1 font-mono text-blue-900"
						>{sanitizedNameInfo.sanitized}</code
					>
				</p>
			</div>
		{:else if !value.trim()}
			<p class="mt-1 text-xs text-gray-500">
				{$_('assistants.form.name.hint', {
					default: 'Special characters and spaces will be converted to underscores'
				})}
			</p>
		{/if}
	{/if}
</div>
