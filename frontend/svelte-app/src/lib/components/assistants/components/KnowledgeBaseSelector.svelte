<!-- src/lib/components/assistants/KnowledgeBaseSelector.svelte -->
<script>
	import { _ } from '$lib/i18n';

	let {
		ownedKnowledgeBases = [],
		sharedKnowledgeBases = [],
		selectedKnowledgeBases = $bindable([]),
		loading = false,
		error = ''
	} = $props();

	let allKnowledgeBases = $derived([...ownedKnowledgeBases, ...sharedKnowledgeBases]);
</script>

<div>
	<h4 class="block text-sm font-medium text-gray-700 mb-1">
		{$_('assistants.form.knowledgeBases.label', { default: 'Knowledge Bases' })}
	</h4>
	{#if loading}
		<p class="text-sm text-gray-500">{$_('assistants.form.knowledgeBases.loading', { default: 'Loading knowledge bases...' })}</p>
	{:else if error}
		<p class="text-sm text-red-600">{$_('assistants.form.knowledgeBases.error', { default: 'Error loading knowledge bases:' })} {error}</p>
	{:else if allKnowledgeBases.length === 0}
		<p class="text-sm text-gray-500">{$_('assistants.form.knowledgeBases.noneFound', { default: 'No accessible knowledge bases found.' })}</p>
	{:else}
		<div class="mt-2 space-y-4">
			{#if ownedKnowledgeBases.length > 0}
				<div>
					<h5 class="text-sm font-semibold text-gray-700 mb-2">{$_('assistants.form.knowledgeBases.myKB', { default: 'My Knowledge Bases' })}</h5>
					<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group" aria-labelledby="kb-owned-group-label">
						<span id="kb-owned-group-label" class="sr-only">{$_('assistants.form.knowledgeBases.myKB', { default: 'My Knowledge Bases' })}</span>
						{#each ownedKnowledgeBases as kb (kb.id)}
							<label class="flex items-center space-x-2 cursor-pointer">
								<input type="checkbox" bind:group={selectedKnowledgeBases} value={kb.id}
									class="rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50">
								<span class="text-sm text-gray-700">{kb.name}</span>
							</label>
						{/each}
					</div>
				</div>
			{/if}
			{#if sharedKnowledgeBases.length > 0}
				<div>
					<h5 class="text-sm font-semibold text-gray-700 mb-2">{$_('assistants.form.knowledgeBases.sharedKB', { default: 'Shared Knowledge Bases' })}</h5>
					<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group" aria-labelledby="kb-shared-group-label">
						<span id="kb-shared-group-label" class="sr-only">{$_('assistants.form.knowledgeBases.sharedKB', { default: 'Shared Knowledge Bases' })}</span>
						{#each sharedKnowledgeBases as kb (kb.id)}
							<label class="flex items-center space-x-2 cursor-pointer">
								<input type="checkbox" bind:group={selectedKnowledgeBases} value={kb.id}
									class="rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50">
								<span class="text-sm text-gray-700">
									{kb.name}
									<span class="ml-2 text-xs text-gray-500">
										({$_('assistants.form.knowledgeBases.shared', { values: { owner: kb.shared_by || 'Unknown' }, default: `Shared by ${kb.shared_by || 'Unknown'}` })})
									</span>
								</span>
							</label>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
