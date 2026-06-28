<script>
  import { _, locale } from '$lib/i18n';
  import { renderMarkdownWithMath } from '$lib/utils/renderMarkdown.js';

	// Props
	let {
		rubricData = null,
		markdown = '',
		explanation = '',
		promptUsed = '',
		rawResponse = '',
		allowManualEdit = false,
		onaccept = () => {},
		onregenerate = () => {},
		oncancel = () => {},
		onjsonUpdated = () => {}
	} = $props();

	// Default text for when i18n isn't loaded yet
	let localeLoaded = $state(!!$locale);

	// State
	let activeTab = $state('markdown'); // 'markdown', 'raw', 'json'
	let editableJson = $state('');
	let jsonError = $state('');
	let showPromptDebug = $state(false);

	// Initialize editable JSON when rubricData changes
	$effect(() => {
		if (rubricData) {
			editableJson = JSON.stringify(rubricData, null, 2);
			jsonError = '';
		}
	});

	// Handle JSON editing
	function validateAndUpdateJson() {
		try {
			const parsed = JSON.parse(editableJson);
			jsonError = '';
			onjsonUpdated({ detail: { rubric: parsed } });
		} catch (e) {
			jsonError = `Invalid JSON: ${e.message}`;
		}
	}

	// Handle accept action
	function handleAccept() {
		if (activeTab === 'json') {
			// Validate JSON before accepting
			try {
				const parsed = JSON.parse(editableJson);
				onaccept({ detail: { rubric: parsed } });
			} catch (e) {
				jsonError = `Cannot accept: Invalid JSON - ${e.message}`;
				return;
			}
		} else {
			onaccept({ detail: { rubric: rubricData } });
		}
	}

	// Handle regenerate
	function handleRegenerate() {
		onregenerate();
	}

	// Handle cancel
	function handleCancel() {
		oncancel();
	}
</script>

<div class="mx-auto max-w-6xl rounded-lg bg-white shadow-lg">
	<!-- Header -->
	<div class="border-b px-6 py-4">
		<h2 class="text-2xl font-bold text-gray-900">
			{localeLoaded
				? $_('rubrics.ai.previewTitle', { default: 'AI Generated Rubric Preview' })
				: 'AI Generated Rubric Preview'}
		</h2>
		{#if explanation}
			<p class="mt-2 text-sm text-gray-600">
				<strong
					>{localeLoaded
						? $_('rubrics.ai.explanation', { default: 'AI Explanation:' })
						: 'AI Explanation:'}</strong
				>
				{explanation}
			</p>
		{/if}
	</div>

	<!-- Tabs -->
	<div class="border-b">
		<nav class="-mb-px flex px-6" aria-label="Tabs">
			<button
				type="button"
				onclick={() => (activeTab = 'markdown')}
				class={`border-b-2 px-6 py-4 text-sm font-medium ${
					activeTab === 'markdown'
						? 'border-blue-500 text-blue-600'
						: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
				}`}
			>
				📄 {localeLoaded
					? $_('rubrics.ai.markdownTab', { default: 'Markdown Preview' })
					: 'Markdown Preview'}
			</button>
			<button
				type="button"
				onclick={() => (activeTab = 'raw')}
				class={`border-b-2 px-6 py-4 text-sm font-medium ${
					activeTab === 'raw'
						? 'border-blue-500 text-blue-600'
						: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
				}`}
			>
				📝 {localeLoaded
					? $_('rubrics.ai.rawMarkdownTab', { default: 'Raw Markdown' })
					: 'Raw Markdown'}
			</button>
			<button
				type="button"
				onclick={() => (activeTab = 'json')}
				class={`border-b-2 px-6 py-4 text-sm font-medium ${
					activeTab === 'json'
						? 'border-blue-500 text-blue-600'
						: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
				}`}
			>
				🔧 {localeLoaded
					? $_('rubrics.ai.jsonTab', { default: 'JSON (Editable)' })
					: 'JSON (Editable)'}
			</button>
		</nav>
	</div>

  <!-- Tab Content -->
  <div class="p-6">
    {#if activeTab === 'markdown'}
      <!-- Rendered Markdown -->
      <div class="prose max-w-none">
        <div class="bg-gray-50 p-6 rounded border">
          {@html renderMarkdownWithMath(markdown)}
        </div>
      </div>
    {:else if activeTab === 'raw'}
      <!-- Raw Markdown Source -->
      <div class="bg-gray-900 text-gray-100 p-4 rounded font-mono text-sm overflow-x-auto">
        <pre>{markdown}</pre>
      </div>
    {:else if activeTab === 'json'}
      <!-- Editable JSON -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <label for="json-editor" class="block text-sm font-medium text-gray-700">
            {localeLoaded ? $_('rubrics.ai.editJsonLabel', { default: 'Edit JSON (changes will be used when you accept)' }) : 'Edit JSON (changes will be used when you accept)'}
          </label>
          <button
            type="button"
            onclick={validateAndUpdateJson}
            class="text-sm px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
          >
            {localeLoaded ? $_('rubrics.ai.validateJson', { default: 'Validate JSON' }) : 'Validate JSON'}
          </button>
        </div>
        
        <textarea
          id="json-editor"
          bind:value={editableJson}
          class="w-full h-96 font-mono text-sm border border-gray-300 rounded p-3 focus:ring-blue-500 focus:border-blue-500"
          spellcheck="false"
        ></textarea>
        
        {#if jsonError}
          <div class="mt-2 text-sm text-red-600 bg-red-50 p-3 rounded">
            {jsonError}
          </div>
        {:else}
          <div class="mt-2 text-sm text-green-600">
            ✓ {localeLoaded ? $_('rubrics.ai.jsonValid', { default: 'JSON is valid' }) : 'JSON is valid'}
          </div>
        {/if}
      </div>
    {/if}

		<!-- Manual Edit Mode (when JSON recovery failed) -->
		{#if allowManualEdit && rawResponse}
			<div class="mt-6 rounded border border-yellow-200 bg-yellow-50 p-4">
				<h3 class="mb-2 text-lg font-medium text-yellow-900">
					⚠️ {localeLoaded
						? $_('rubrics.ai.manualEditRequired', { default: 'Manual Edit Required' })
						: 'Manual Edit Required'}
				</h3>
				<p class="mb-3 text-sm text-yellow-700">
					{localeLoaded
						? $_('rubrics.ai.manualEditHelp', {
								default:
									'The AI response could not be automatically parsed. Please review and edit the JSON in the JSON tab.'
							})
						: 'The AI response could not be automatically parsed. Please review and edit the JSON in the JSON tab.'}
				</p>
				<details class="text-sm">
					<summary class="cursor-pointer font-medium text-yellow-800">
						{localeLoaded
							? $_('rubrics.ai.showRawResponse', { default: 'Show Raw AI Response' })
							: 'Show Raw AI Response'}
					</summary>
					<pre class="mt-2 overflow-x-auto rounded border bg-white p-3 text-xs">{rawResponse}</pre>
				</details>
			</div>
		{/if}
	</div>

	<!-- Advanced Debug Section -->
	{#if promptUsed}
		<div class="border-t bg-gray-50 px-6 py-3">
			<button
				type="button"
				onclick={() => (showPromptDebug = !showPromptDebug)}
				class="flex items-center text-sm text-gray-600 hover:text-gray-900"
			>
				<svg class="mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d={showPromptDebug ? 'M19 9l-7 7-7-7' : 'M9 5l7 7-7 7'}
					/>
				</svg>
				{localeLoaded
					? $_('rubrics.ai.showPrompt', { default: 'Show Prompt Sent to LLM (Advanced)' })
					: 'Show Prompt Sent to LLM (Advanced)'}
			</button>

			{#if showPromptDebug}
				<div class="mt-3 rounded border bg-white p-3">
					<pre class="text-xs whitespace-pre-wrap text-gray-700">{promptUsed}</pre>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Actions -->
	<div class="flex items-center justify-between border-t bg-gray-50 px-6 py-4">
		<div class="flex space-x-3">
			<button
				type="button"
				onclick={handleCancel}
				class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
			>
				{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
			</button>
			<button
				type="button"
				onclick={handleRegenerate}
				class="rounded-md border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100"
			>
				🔄 {localeLoaded ? $_('rubrics.ai.regenerate', { default: 'Regenerate' }) : 'Regenerate'}
			</button>
		</div>
		<button
			type="button"
			onclick={handleAccept}
			disabled={!rubricData || (activeTab === 'json' && jsonError)}
			class="rounded-md border border-transparent bg-green-600 px-6 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
		>
			✓ {localeLoaded
				? $_('rubrics.ai.acceptAndSave', { default: 'Accept and Save Rubric' })
				: 'Accept and Save Rubric'}
		</button>
	</div>
</div>
