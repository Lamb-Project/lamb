<!-- src/lib/components/assistants/ConfigurationPanel.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { tick } from 'svelte';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore';
	import { hasRagOptions } from '$lib/utils/ragProcessorHelpers.js';
	import {
		extractModelsMetadata
	} from '../logic/assistantFormUtils.svelte.js';
	import RagOptionsPanel from './RagOptionsPanel.svelte';
	import LibraryItemSelector from './LibraryItemSelector.svelte';

	let {
		formState,
		availableModels = [],
		isAdvancedMode = $bindable(false),
		promptProcessors = [],
		connectorsList = [],
		ragProcessors = [],
		selectedPromptProcessor = $bindable(''),
		selectedConnector = $bindable(''),
		selectedLlm = $bindable(''),
		selectedRagProcessor = $bindable(''),
		visionEnabled = $bindable(false),
		imageGenerationEnabled = $bindable(false),
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
		documentRagEnabled = $bindable(false),
		selectedFilePath = '',
		onchange
	} = $props();

	let currentConnectorMetadata = $derived.by(() => {
		const connectorData = $assistantConfigStore?.systemCapabilities?.connectors?.[selectedConnector];
		return connectorData?.metadata || null;
	});

	let currentModelsMetadata = $derived.by(() => {
		const connectorData = $assistantConfigStore?.systemCapabilities?.connectors?.[selectedConnector];
		return extractModelsMetadata(connectorData) || [];
	});

	let currentModelMetadata = $derived(currentModelsMetadata.find((m) => m.id === selectedLlm) || null);
	let imageGenerationForced = $derived(currentModelMetadata?.forced_capabilities?.image_generation === true);
	let showRagOptions = $derived(hasRagOptions(selectedRagProcessor));
	let isLegacySingleFileRag = $derived(selectedRagProcessor === 'single_file_rag');
	let showDocumentSection = $derived(!isLegacySingleFileRag);
	let filteredRAGProcessors = $derived(
		formState === 'edit'
			? ragProcessors
			: ragProcessors.filter((p) => p !== 'single_file_rag')
	);

	async function handleConnectorChange() {
		await tick();
		if (!availableModels.includes(selectedLlm)) {
			selectedLlm = availableModels.length > 0 ? availableModels[0] : '';
		}
		const connectorSupportsVision = currentConnectorMetadata?.capabilities?.vision_input === true;
		const connectorSupportsImageGen =
			currentConnectorMetadata?.capabilities?.image_generation === true;
		if (
			selectedConnector !== 'openai' &&
			selectedConnector !== 'banana_img' &&
			!connectorSupportsVision &&
			visionEnabled
		) {
			visionEnabled = false;
		}
		if (selectedConnector !== 'banana_img' && !connectorSupportsImageGen && imageGenerationEnabled) {
			imageGenerationEnabled = false;
		}
		if (connectorSupportsImageGen && currentConnectorMetadata?.capabilities?.image_generation) {
			imageGenerationEnabled = true;
		}
		onchange?.();
	}

</script>

{#if formState === 'create'}
	<div class="mb-3">
		<label class="inline-flex items-center cursor-pointer">
			<input type="checkbox" bind:checked={isAdvancedMode} class="sr-only peer" />
			<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
			<span class="ms-3 text-sm font-medium text-gray-900 dark:text-gray-300">
				{$_('assistants.form.advancedMode') || 'Advanced Mode'}
			</span>
		</label>
	</div>
{/if}

<fieldset class="border p-4 rounded-md space-y-4 h-full">
	<legend class="text-lg font-medium text-brand px-1">{$_('assistants.form.configSection.title', { default: 'Configuration' })}</legend>

	{#if isAdvancedMode || formState === 'edit'}
		<div>
			<label for="prompt-processor" class="block text-sm font-medium text-gray-700">{$_('assistants.form.promptProcessor.label', { default: 'Prompt Processor' })}</label>
			<select id="prompt-processor" name="prompt_processor" bind:value={selectedPromptProcessor} onchange={onchange}
				class="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900">
				{#each promptProcessors as processor (processor)}
					<option value={processor}>{processor}</option>
				{/each}
			</select>
		</div>
	{/if}

	{#if isAdvancedMode || formState === 'edit'}
		<div>
			<label for="connector" class="block text-sm font-medium text-gray-700">{$_('assistants.form.connector.label', { default: 'Connector' })}</label>
			<select id="connector" name="connector" bind:value={selectedConnector}
				onchange={() => { onchange?.(); handleConnectorChange(); }}
				class="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900">
				{#each connectorsList as connectorName (connectorName)}
					<option value={connectorName}>{connectorName}</option>
				{/each}
			</select>
			{#if currentConnectorMetadata?.description}
				<p class="mt-1 text-xs text-gray-500 italic">{currentConnectorMetadata.description}</p>
			{/if}
		</div>
	{/if}

	<div>
		<label for="llm" class="block text-sm font-medium text-gray-700">{$_('assistants.form.llm.label', { default: 'Language Model (LLM)' })}</label>
		<select id="llm" name="llm" bind:value={selectedLlm} onchange={onchange}
			disabled={availableModels.length === 0}
			class="mt-1 block w-full pl-3 pr-10 py-2 text-base text-gray-900 border border-gray-300 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm rounded-md bg-white">
			{#if availableModels.length > 0}
				{#each availableModels as model (model)}
					<option value={model}>{model}</option>
				{/each}
			{:else}
				<option value="" disabled>{$_('assistants.form.llm.noneAvailable', { default: 'No models available for selected connector' })}</option>
			{/if}
		</select>
	</div>

	{#if selectedConnector === 'openai' || selectedConnector === 'banana_img' || visionEnabled}
		<div class="mb-3">
			<label class="inline-flex items-start cursor-pointer">
				<input type="checkbox" bind:checked={visionEnabled} onchange={onchange} class="sr-only peer" />
				<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 shrink-0 mt-0.5"></div>
				<div class="ms-3">
					<span class="text-sm font-medium text-gray-900 dark:text-gray-300">{$_('assistants.form.vision.label', { default: 'Enable Vision Capability' })}</span>
					<p class="text-xs text-gray-500 mt-1">
						{#if selectedConnector === 'banana_img'}
							{$_('assistants.form.vision.imageToImageDescription', { default: 'Allow this assistant to accept images as input for image-to-image generation (editing, style transfer, etc.)' })}
						{:else}
							{$_('assistants.form.vision.description', { default: 'Allow this assistant to process images alongside text messages' })}
						{/if}
					</p>
				</div>
			</label>
		</div>
	{/if}

	{#if selectedConnector === 'banana_img' || imageGenerationEnabled || currentConnectorMetadata?.capabilities?.image_generation}
		<div class="mb-3">
			<label class="inline-flex items-start {imageGenerationForced ? 'cursor-not-allowed opacity-75' : 'cursor-pointer'}">
				<input type="checkbox" bind:checked={imageGenerationEnabled} onchange={onchange}
					disabled={imageGenerationForced} class="sr-only peer" />
				<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 dark:peer-focus:ring-green-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-green-600 {imageGenerationForced ? 'peer-disabled:opacity-50' : ''} shrink-0 mt-0.5"></div>
				<div class="ms-3">
					<span class="text-sm font-medium text-gray-900 dark:text-gray-300 flex items-center gap-2">
						{$_('assistants.form.imageGeneration.label', { default: 'Enable Image Generation' })}
						{#if imageGenerationForced}
							<span class="inline-flex items-center text-xs text-amber-600" title={$_('assistants.form.imageGeneration.requiredForModel', { default: 'This capability is required for the selected model' })}>
								<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
									<path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd"/>
								</svg>
							</span>
						{/if}
					</span>
					<p class="text-xs text-gray-500 mt-1">
						{#if imageGenerationForced}
							<span class="text-amber-600">{$_('assistants.form.imageGeneration.requiredForModelPrefix', { default: 'Required for this model - ' })}</span>
						{/if}
						{$_('assistants.form.imageGeneration.geminiDescription', { default: 'Allow this assistant to generate images using Google Gemini' })}
					</p>
				</div>
			</label>
		</div>
	{/if}

	<div>
		<label for="rag-processor" class="block text-sm font-medium text-gray-700">{$_('assistants.form.ragProcessor.label')}</label>
		<select id="rag-processor" bind:value={selectedRagProcessor} onchange={onchange}
			disabled={formState === 'edit'}
			class="mt-1 block w-full pl-3 pr-10 py-2 text-base text-gray-900 border border-gray-300 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm rounded-md bg-white disabled:bg-gray-100 disabled:cursor-not-allowed">
		{#each filteredRAGProcessors as processor (processor)}
			<option value={processor}>{processor.replace(/_/g, ' ').replace(/\b\w/g, (/** @type {string} */ l) => l.toUpperCase())}</option>
		{/each}
		</select>
	</div>

	{#if showDocumentSection}
		<div class="pt-4 border-t border-gray-200">
			<label class="inline-flex items-center cursor-pointer mb-2">
				<input type="checkbox" bind:checked={documentRagEnabled} onchange={onchange} disabled={formState === 'edit'} class="sr-only peer" />
				<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
				<span class="ms-3 text-sm font-medium text-gray-900">{$_('assistants.form.documentRag.label', { default: 'Reference Document' })}</span>
			</label>
			<p class="text-xs text-gray-500 mb-2">{$_('assistants.form.documentRag.description', { default: 'Attach a reference document that will be available in the system context for all messages.' })}</p>
			{#if documentRagEnabled}
				<LibraryItemSelector
					{libraries}
					bind:selectedLibraryId
					loadingLibraries={loadingLibraries}
					libraryError={libraryError}
					items={libraryItems}
					bind:selectedItemId
					loadingItems={loadingItems}
					itemsError={itemsError}
					{formState}
				/>
			{/if}
		</div>
	{/if}

	{#if showRagOptions}
		<RagOptionsPanel
			{selectedRagProcessor}
			bind:RAG_Top_k
			{ownedKnowledgeBases}
			{sharedKnowledgeBases}
			bind:selectedKnowledgeBases
			loadingKnowledgeBases={loadingKnowledgeBases}
			knowledgeBaseError={knowledgeBaseError}
			{libraries}
			bind:selectedLibraryId
			loadingLibraries={loadingLibraries}
			libraryError={libraryError}
			{libraryItems}
			bind:selectedItemId
			loadingItems={loadingItems}
			itemsError={itemsError}
			{selectedFilePath}
			{formState}
		/>
	{/if}
</fieldset>
