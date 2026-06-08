<!-- src/lib/components/assistants/components/KnowledgeStoreSelector.svelte -->
<script>
	import { _ } from '$lib/i18n';

	let {
		ownedKnowledgeStores = [],
		sharedKnowledgeStores = [],
		selectedKnowledgeStores = $bindable([]),
		loading = false,
		error = ''
	} = $props();
</script>

<div data-testid="ks-picker">
	<h4 class="block text-sm font-medium text-gray-700 mb-1">
		{$_('assistants.form.knowledgeStores.label', { default: 'Knowledge Stores' })}
	</h4>
	{#if loading}
		<p class="text-sm text-gray-500">
			{$_('assistants.form.knowledgeStores.loading', { default: 'Loading knowledge stores...' })}
		</p>
	{:else if error}
		<p class="text-sm text-red-600">
			{$_('assistants.form.knowledgeStores.error', { default: 'Error loading knowledge stores:' })} {error}
		</p>
	{:else if ownedKnowledgeStores.length === 0 && sharedKnowledgeStores.length === 0}
		<p class="text-sm text-gray-500">
			{$_('assistants.form.knowledgeStores.noneFound', { default: 'No accessible knowledge stores found.' })}
		</p>
	{:else}
		<div class="mt-2 space-y-4">
			{#if ownedKnowledgeStores.length > 0}
				<div>
					<h5 class="text-sm font-semibold text-gray-700 mb-2">
						{$_('assistants.form.knowledgeStores.myKS', { default: 'My Knowledge Stores' })}
					</h5>
					<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group">
						{#each ownedKnowledgeStores as ks (ks.id)}
							<label class="flex items-center space-x-2 cursor-pointer">
								<input type="checkbox" bind:group={selectedKnowledgeStores} value={ks.id}
									class="rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50">
								<span class="text-sm text-gray-700">
									{ks.name}
									<span class="ml-1 text-xs text-gray-400">({ks.embedding_vendor}/{ks.embedding_model})</span>
								</span>
							</label>
						{/each}
					</div>
				</div>
			{/if}
			{#if sharedKnowledgeStores.length > 0}
				<div>
					<h5 class="text-sm font-semibold text-gray-700 mb-2">
						{$_('assistants.form.knowledgeStores.sharedKS', { default: 'Shared Knowledge Stores' })}
					</h5>
					<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group">
						{#each sharedKnowledgeStores as ks (ks.id)}
							<label class="flex items-center space-x-2 cursor-pointer">
								<input type="checkbox" bind:group={selectedKnowledgeStores} value={ks.id}
									class="rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50">
								<span class="text-sm text-gray-700">
									{ks.name}
									<span class="ml-1 text-xs text-gray-400">({ks.embedding_vendor}/{ks.embedding_model})</span>
								</span>
							</label>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
