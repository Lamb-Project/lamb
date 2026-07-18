<!-- src/lib/components/assistants/RagOptionsPanel.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { isKbBasedRag, isSingleFileRag, isRubricRag, isGrepRag } from '$lib/utils/ragProcessorHelpers.js';
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
		onFilesChanged,
		// Grep RAG fields
		grepMode = $bindable('hybrid'),
		grepFallbackRag = $bindable('simple_rag'),
		grepMaxTries = $bindable(5),
		grepContextLines = $bindable(3),
		grepMaxTotalChars = $bindable(8000),
		ragProcessors = []
	} = $props();

	let showKbSelector = $derived(isKbBasedRag(selectedRagProcessor) || isGrepRag(selectedRagProcessor));
	let showFileSelector = $derived(isSingleFileRag(selectedRagProcessor));
	let showTopK = $derived(isKbBasedRag(selectedRagProcessor) || isGrepRag(selectedRagProcessor));
	let showGrepOptions = $derived(isGrepRag(selectedRagProcessor));
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
	{#if showGrepOptions}
		<div class="space-y-3 p-3 bg-gray-50 border border-gray-200 rounded-md">
			<h5 class="text-sm font-semibold text-gray-700">
				{$_('assistants.form.grepRag.sectionTitle', { default: 'Grep RAG Configuration' })}
			</h5>

			<!-- Mode -->
			<div>
				<label for="grep-mode" class="block text-sm font-medium text-gray-700">
					{$_('assistants.form.grepRag.mode.label', { default: 'Mode' })}
				</label>
				<select id="grep-mode" bind:value={grepMode}
					class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white text-gray-900">
					<option value="hybrid">{$_('assistants.form.grepRag.mode.hybrid', { default: 'Hybrid (grep + RAG in parallel)' })}</option>
					<option value="primary">{$_('assistants.form.grepRag.mode.primary', { default: 'Primary (grep first, RAG fallback)' })}</option>
				</select>
				<p class="mt-1 text-xs text-gray-500">
					{$_('assistants.form.grepRag.mode.description', { default: 'How grep interacts with embedding-based RAG' })}
				</p>
			</div>

			<!-- Fallback RAG (only relevant in primary mode) -->
			{#if grepMode === 'primary'}
			<div>
				<label for="grep-fallback-rag" class="block text-sm font-medium text-gray-700">
					{$_('assistants.form.grepRag.fallbackRag.label', { default: 'Fallback RAG' })}
				</label>
				<select id="grep-fallback-rag" bind:value={grepFallbackRag}
					class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white text-gray-900">
					{#each ragProcessors.filter(p => isKbBasedRag(p)) as processor}
						<option value={processor}>{processor.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</option>
					{/each}
				</select>
				<p class="mt-1 text-xs text-gray-500">
					{$_('assistants.form.grepRag.fallbackRag.description', { default: 'Embedding RAG to fall back to when grep finds no matches' })}
				</p>
			</div>
			{/if}

			<!-- Max Tries -->
			<div>
				<label for="grep-max-tries" class="block text-sm font-medium text-gray-700">
					{$_('assistants.form.grepRag.maxTries.label', { default: 'Max Search Tries' })}
				</label>
				<input type="number" id="grep-max-tries" bind:value={grepMaxTries} min="1" max="10"
					class="mt-1 block w-24 px-3 py-2 text-sm border border-gray-300 rounded-md bg-white text-gray-900">
				<p class="mt-1 text-xs text-gray-500">
					{$_('assistants.form.grepRag.maxTries.description', { default: 'Maximum number of search iterations (1-10)' })}
				</p>
			</div>

			<!-- Context Lines -->
			<div>
				<label for="grep-context-lines" class="block text-sm font-medium text-gray-700">
					{$_('assistants.form.grepRag.contextLines.label', { default: 'Context Lines' })}
				</label>
				<input type="number" id="grep-context-lines" bind:value={grepContextLines} min="1" max="10"
					class="mt-1 block w-24 px-3 py-2 text-sm border border-gray-300 rounded-md bg-white text-gray-900">
				<p class="mt-1 text-xs text-gray-500">
					{$_('assistants.form.grepRag.contextLines.description', { default: 'Lines of context before/after each match (1-10)' })}
				</p>
			</div>

			<!-- Max Total Chars -->
			<div>
				<label for="grep-max-chars" class="block text-sm font-medium text-gray-700">
					{$_('assistants.form.grepRag.maxTotalChars.label', { default: 'Max Result Characters' })}
				</label>
				<input type="number" id="grep-max-chars" bind:value={grepMaxTotalChars} min="1000" max="32000" step="1000"
					class="mt-1 block w-32 px-3 py-2 text-sm border border-gray-300 rounded-md bg-white text-gray-900">
				<p class="mt-1 text-xs text-gray-500">
					{$_('assistants.form.grepRag.maxTotalChars.description', { default: 'Max total characters of grep results sent to main LLM (1000-32000)' })}
				</p>
			</div>
		</div>
	{/if}
</div>
