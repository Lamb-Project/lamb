<!-- src/lib/components/assistants/RagOptionsPanel.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { isKbBasedRag, isSingleFileRag, isRubricRag } from '$lib/utils/ragProcessorHelpers.js';
	import KnowledgeBaseSelector from './KnowledgeBaseSelector.svelte';
	import SingleFileSelector from './SingleFileSelector.svelte';

	let {
		selectedRagProcessor = '',
		RAG_Top_k = $bindable(3),
		ownedKnowledgeBases = [],
		sharedKnowledgeBases = [],
		selectedKnowledgeBases = $bindable([]),
		loadingKnowledgeBases = false,
		knowledgeBaseError = '',
		userFiles = [],
		selectedFilePath = $bindable(''),
		loadingFiles = false,
		fileError = '',
		formState,
		onFilesChanged
	} = $props();

	let showKbSelector = $derived(isKbBasedRag(selectedRagProcessor));
	let showFileSelector = $derived(isSingleFileRag(selectedRagProcessor));
	let showTopK = $derived(isKbBasedRag(selectedRagProcessor));
</script>

<div class="space-y-4 border-t border-gray-200 pt-4">
	<h4 class="text-md font-medium text-gray-700">
		{$_('assistants.form.ragOptions.title', { default: 'RAG Options' })}
	</h4>
	{#if isRubricRag(selectedRagProcessor)}
		<div class="rounded-md border border-blue-200 bg-blue-50 p-3">
			<p class="text-sm text-blue-800">
				📋 {$_('assistants.form.rubric.configLocation', {
					default: 'See rubric options below the Prompt Template section'
				})}
			</p>
		</div>
	{/if}
	{#if showTopK}
		<div>
			<label for="rag-top-k" class="block text-sm font-medium text-gray-700">
				{$_('assistants.form.ragTopK.label', { default: 'RAG Top K' })}
			</label>
			<input
				type="number"
				id="rag-top-k"
				name="RAG_Top_k"
				bind:value={RAG_Top_k}
				min="1"
				max="10"
				class="focus:ring-brand focus:border-brand mt-1 block w-24 rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:outline-none disabled:cursor-not-allowed disabled:bg-gray-100 sm:text-sm"
			/>
			<p class="mt-1 text-xs text-gray-500">
				{$_('assistants.form.ragTopK.help', {
					default: 'Number of relevant documents to retrieve (1-10).'
				})}
			</p>
		</div>
	{/if}
	{#if showKbSelector}
		<KnowledgeBaseSelector
			{ownedKnowledgeBases}
			{sharedKnowledgeBases}
			bind:selectedKnowledgeBases
			loading={loadingKnowledgeBases}
			error={knowledgeBaseError}
		/>
	{/if}
	{#if showFileSelector}
		<SingleFileSelector
			{userFiles}
			bind:selectedFilePath
			loading={loadingFiles}
			error={fileError}
			{formState}
			{onFilesChanged}
		/>
	{/if}
</div>
