<!-- src/lib/components/assistants/RagOptionsPanel.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { isKbBasedRag, isSingleFileRag, isRubricRag } from '$lib/utils/ragProcessorHelpers.js';
	import KnowledgeBaseSelector from './KnowledgeBaseSelector.svelte';
	import LibraryItemSelector from './LibraryItemSelector.svelte';

	let {
		selectedRagProcessor = '',
		RAG_Top_k = $bindable(3),
		ownedKnowledgeBases = [],
		sharedKnowledgeBases = [],
		selectedKnowledgeBases = $bindable([]),
		loadingKnowledgeBases = false,
		knowledgeBaseError = '',
		libraries = [],
		selectedLibraryId = $bindable(''),
		loadingLibraries = false,
		libraryError = '',
		libraryItems = [],
		selectedItemId = $bindable(''),
		loadingItems = false,
		itemsError = '',
		selectedFilePath = '',
		formState
	} = $props();

	let showKbSelector = $derived(isKbBasedRag(selectedRagProcessor));
	let showFileSelector = $derived(isSingleFileRag(selectedRagProcessor));
	let showTopK = $derived(isKbBasedRag(selectedRagProcessor));
	let isLegacyWithFilePath = $derived(isSingleFileRag(selectedRagProcessor) && !!selectedFilePath);
</script>

<div class="pt-4 border-t border-gray-200 space-y-4">
	<h4 class="text-md font-medium text-gray-700">
		{$_('assistants.form.ragOptions.title', { default: 'RAG Options' })}
	</h4>
	{#if isRubricRag(selectedRagProcessor)}
		<div class="p-3 bg-blue-50 border border-blue-200 rounded-md">
			<p class="text-sm text-blue-800">
				📋 {$_('assistants.form.rubric.configLocation', { default: 'See rubric options below the Prompt Template section' })}
			</p>
		</div>
	{/if}
	{#if showTopK}
		<div>
			<label for="rag-top-k" class="block text-sm font-medium text-gray-700">
				{$_('assistants.form.ragTopK.label', { default: 'RAG Top K' })}
			</label>
			<input type="number" id="rag-top-k" name="RAG_Top_k" bind:value={RAG_Top_k} min="1" max="10"
				class="mt-1 block w-24 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900 disabled:bg-gray-100 disabled:cursor-not-allowed">
			<p class="mt-1 text-xs text-gray-500">{$_('assistants.form.ragTopK.help', { default: 'Number of relevant documents to retrieve (1-10).' })}</p>
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
	{#if showFileSelector && isLegacyWithFilePath}
		<div class="p-3 bg-amber-50 border border-amber-200 rounded-md mb-3">
			<p class="text-sm text-amber-800">
				{$_('assistants.form.ragOptions.legacySingleFileNotice', { default: 'This assistant uses the legacy single-file RAG. The document cannot be changed. To use a different document, create a new assistant with the Reference Document option.' })}
			</p>
		</div>
		<div class="p-3 bg-gray-50 border border-gray-200 rounded-md">
			<p class="text-sm font-medium text-gray-700">{$_('assistants.form.ragOptions.document', { default: 'Document' })}</p>
			<p class="text-sm text-gray-500 font-mono mt-1">{selectedFilePath}</p>
		</div>
	{/if}
</div>
