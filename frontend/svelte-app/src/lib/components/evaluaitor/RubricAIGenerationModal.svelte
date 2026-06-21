<script>
	import { _, locale } from '$lib/i18n';
	import { aiGenerateRubric, createRubric } from '$lib/services/rubricService';
	import RubricPreview from './RubricPreview.svelte';

	// Props
	let { show = false, onclose = () => {}, onrubricCreated = () => {} } = $props();

	// Default text for when i18n isn't loaded yet
	let localeLoaded = $state(!!$locale);

	// State
	let currentStep = $state('input'); // 'input', 'preview', 'error'
	let userPrompt = $state('');
	let isGenerating = $state(false);
	let error = $state('');

	// AI response data
	let generatedRubric = $state(null);
	let markdown = $state('');
	let explanation = $state('');
	let promptUsed = $state('');
	let rawResponse = $state('');
	let allowManualEdit = $state(false);

	// Advanced mode
	let showAdvanced = $state(false);
	let editablePrompt = $state('');
	let useCustomPrompt = $state(false);

	// Get current language from locale
	let currentLanguage = $derived($locale || 'en');

	// Handle generate
	async function handleGenerate() {
		if (!userPrompt.trim()) {
			error = localeLoaded
				? $_('rubrics.ai.promptRequired', { default: 'Please enter a prompt' })
				: 'Please enter a prompt';
			return;
		}

		isGenerating = true;
		error = '';

		try {
			const result = await aiGenerateRubric(userPrompt, currentLanguage);

			if (result.success) {
				// Success - show preview
				generatedRubric = result.rubric;
				markdown = result.markdown || '';
				explanation = result.explanation || '';
				promptUsed = result.prompt_used || '';
				currentStep = 'preview';
			} else {
				// Failure - show error with manual edit option
				error = result.error || 'Unknown error';
				rawResponse = result.raw_response || '';
				allowManualEdit = result.allow_manual_edit || false;

				if (allowManualEdit) {
					// Try to extract some JSON for manual editing
					generatedRubric = result.rubric || {};
					markdown = result.markdown || '';
					currentStep = 'preview'; // Show preview with error state
				} else {
					currentStep = 'error';
				}
			}
		} catch (err) {
			error =
				err.message ||
				(localeLoaded
					? $_('rubrics.ai.generationError', { default: 'Failed to generate rubric' })
					: 'Failed to generate rubric');
			currentStep = 'error';
		} finally {
			isGenerating = false;
		}
	}

	// Handle regenerate
	function handleRegenerate() {
		currentStep = 'input';
		generatedRubric = null;
		markdown = '';
		explanation = '';
		error = '';
	}

	// Handle accept and save
	async function handleAccept(event) {
		const rubricToSave = event.detail.rubric;

		isGenerating = true;
		error = '';

		try {
			// Save rubric to database
			const result = await createRubric(rubricToSave);

			if (result.success || result.rubric) {
				// Success! Close modal and notify parent
				handleClose();
				onrubricCreated({
					detail: {
						rubricId: result.rubric?.rubricId || result.rubricId
					}
				});
			} else {
				throw new Error(result.error || 'Failed to save rubric');
			}
		} catch (err) {
			error =
				err.message ||
				(localeLoaded
					? $_('rubrics.ai.saveError', { default: 'Failed to save rubric' })
					: 'Failed to save rubric');
			currentStep = 'error';
		} finally {
			isGenerating = false;
		}
	}

	// Handle cancel
	function handleCancel() {
		handleClose();
	}

	// Reset and close
	function handleClose() {
		currentStep = 'input';
		userPrompt = '';
		generatedRubric = null;
		markdown = '';
		explanation = '';
		error = '';
		rawResponse = '';
		isGenerating = false;
		showAdvanced = false;
		onclose();
	}

	// Handle JSON update from preview
	function handleJsonUpdated(event) {
		generatedRubric = event.detail.rubric;
	}
</script>

{#if show}
	<!-- Modal Overlay -->
	<div
		class="bg-opacity-75 fixed inset-0 z-50 flex items-center justify-center bg-gray-500 p-4"
		onclick={handleClose}
	>
		<div
			class="max-h-[90vh] w-full max-w-6xl overflow-y-auto rounded-lg bg-white shadow-xl"
			role="presentation"
			onclick={(e) => e.stopPropagation()}
		>
			{#if currentStep === 'input'}
				<!-- Step 1: Prompt Input -->
				<div class="p-6">
					<div class="mb-4 flex items-start justify-between">
						<div>
							<h2 class="text-2xl font-bold text-gray-900">
								{localeLoaded
									? $_('rubrics.ai.generateTitle', { default: 'Generate Rubric with AI' })
									: 'Generate Rubric with AI'}
							</h2>
							<p class="mt-1 text-sm text-gray-600">
								{localeLoaded
									? $_('rubrics.ai.generateDescription', {
											default:
												'Describe the rubric you want to create, and AI will generate it for you.'
										})
									: 'Describe the rubric you want to create, and AI will generate it for you.'}
							</p>
						</div>
						<button
							type="button"
							onclick={handleClose}
							class="text-gray-400 hover:text-gray-600"
							aria-label="Close"
						>
							<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</button>
					</div>

					<div class="mb-4">
						<label for="ai-prompt" class="mb-2 block text-sm font-medium text-gray-700">
							{localeLoaded
								? $_('rubrics.ai.promptLabel', { default: 'Describe your rubric' })
								: 'Describe your rubric'}
						</label>
						<textarea
							id="ai-prompt"
							bind:value={userPrompt}
							rows="6"
							class="w-full rounded-md border border-gray-300 p-3 shadow-sm focus:border-blue-500 focus:ring-blue-500"
							placeholder={localeLoaded
								? $_('rubrics.ai.promptPlaceholder', {
										default:
											'e.g., Create a rubric for evaluating 5-paragraph argumentative essays for 9th grade English students'
									})
								: 'e.g., Create a rubric for evaluating 5-paragraph argumentative essays for 9th grade English students'}
							disabled={isGenerating}
						></textarea>
						<p class="mt-1 text-xs text-gray-500">
							{localeLoaded ? $_('rubrics.ai.languageNote', { default: 'Language' }) : 'Language'}:
							<strong>{currentLanguage.toUpperCase()}</strong>
						</p>
					</div>

					<!-- Advanced Options -->
					<div class="mb-4">
						<button
							type="button"
							onclick={() => (showAdvanced = !showAdvanced)}
							class="flex items-center text-sm text-blue-600 hover:text-blue-800"
						>
							<svg class="mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d={showAdvanced ? 'M19 9l-7 7-7-7' : 'M9 5l7 7-7 7'}
								/>
							</svg>
							{localeLoaded
								? $_('rubrics.ai.advancedOptions', { default: 'Advanced Options' })
								: 'Advanced Options'}
						</button>

						{#if showAdvanced}
							<div class="mt-3 rounded border bg-gray-50 p-4">
								<p class="mb-2 text-sm text-gray-600">
									{localeLoaded
										? $_('rubrics.ai.advancedHelp', {
												default:
													'Advanced users can view and edit the complete prompt template that will be sent to the LLM.'
											})
										: 'Advanced users can view and edit the complete prompt template that will be sent to the LLM.'}
								</p>
								<p class="text-xs text-gray-500 italic">
									{localeLoaded
										? $_('rubrics.ai.advancedWarning', {
												default:
													'Note: Editing the prompt may affect generation quality. Only modify if you understand the rubric JSON structure.'
											})
										: 'Note: Editing the prompt may affect generation quality. Only modify if you understand the rubric JSON structure.'}
								</p>
							</div>
						{/if}
					</div>

					{#if error}
						<div class="mb-4 rounded-md border border-red-200 bg-red-50 p-4">
							<div class="text-sm text-red-700">{error}</div>
						</div>
					{/if}

					<div class="flex justify-end space-x-3">
						<button
							type="button"
							onclick={handleClose}
							disabled={isGenerating}
							class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
						>
							{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
						</button>
						<button
							type="button"
							onclick={handleGenerate}
							disabled={isGenerating || !userPrompt.trim()}
							class="inline-flex items-center rounded-md border border-transparent bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
						>
							{#if isGenerating}
								<svg
									class="mr-2 -ml-1 h-4 w-4 animate-spin text-white"
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
								>
									<circle
										class="opacity-25"
										cx="12"
										cy="12"
										r="10"
										stroke="currentColor"
										stroke-width="4"
									></circle>
									<path
										class="opacity-75"
										fill="currentColor"
										d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
									></path>
								</svg>
								{localeLoaded
									? $_('rubrics.ai.generating', { default: 'Generating...' })
									: 'Generating...'}
							{:else}
								⚡ {localeLoaded
									? $_('rubrics.ai.generateButton', { default: 'Generate with AI' })
									: 'Generate with AI'}
							{/if}
						</button>
					</div>
				</div>
			{:else if currentStep === 'preview'}
				<!-- Step 2: Preview Generated Rubric -->
				<RubricPreview
					rubricData={generatedRubric}
					{markdown}
					{explanation}
					{promptUsed}
					{rawResponse}
					{allowManualEdit}
					onaccept={handleAccept}
					onregenerate={handleRegenerate}
					oncancel={handleCancel}
					onjsonUpdated={handleJsonUpdated}
				/>
			{:else if currentStep === 'error'}
				<!-- Step 3: Error State -->
				<div class="p-6">
					<div class="mb-4 flex items-start justify-between">
						<h2 class="text-2xl font-bold text-red-900">
							{localeLoaded
								? $_('rubrics.ai.errorTitle', { default: 'Generation Failed' })
								: 'Generation Failed'}
						</h2>
						<button
							type="button"
							onclick={handleClose}
							class="text-gray-400 hover:text-gray-600"
							aria-label="Close"
						>
							<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</button>
					</div>

					<div class="mb-4 rounded-md border border-red-200 bg-red-50 p-4">
						<p class="text-sm text-red-700">{error}</p>
					</div>

					{#if rawResponse}
						<details class="mb-4">
							<summary class="mb-2 cursor-pointer text-sm font-medium text-gray-700">
								{localeLoaded
									? $_('rubrics.ai.showRawResponse', { default: 'Show Raw AI Response' })
									: 'Show Raw AI Response'}
							</summary>
							<div
								class="mt-2 overflow-x-auto rounded bg-gray-900 p-4 font-mono text-xs text-gray-100"
							>
								<pre>{rawResponse}</pre>
							</div>
						</details>
					{/if}

					<div class="flex justify-end space-x-3">
						<button
							type="button"
							onclick={handleClose}
							class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
						>
							{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
						</button>
						<button
							type="button"
							onclick={handleRegenerate}
							class="rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
						>
							{localeLoaded ? $_('rubrics.ai.tryAgain', { default: 'Try Again' }) : 'Try Again'}
						</button>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
