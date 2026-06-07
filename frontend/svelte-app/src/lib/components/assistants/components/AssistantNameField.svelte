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
			class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-gray-100 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm text-gray-900"
			placeholder={$_('assistants.form.name.placeholder')}
		/>
	{:else}
		<input
			type="text"
			id="assistant-name"
			name="name"
			bind:value
			disabled={false}
			oninput={oninput}
			class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
			placeholder={$_('assistants.form.name.placeholder')}
		/>
		{#if showSanitizationPreview}
			<div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-md">
				<p class="text-sm text-blue-800">
					<span class="font-semibold"
						>{$_('assistants.form.name.willBeSaved', { default: 'Will be saved as:' })}</span
					>
					<code class="ml-2 px-2 py-1 bg-blue-100 rounded text-blue-900 font-mono"
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
