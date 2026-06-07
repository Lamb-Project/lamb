<!-- src/lib/components/assistants/AssistantPromptFields.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { tick } from 'svelte';
	import { openTemplateSelectModal } from '$lib/stores/templateStore';
	import TemplateSelectModal from '$lib/components/modals/TemplateSelectModal.svelte';
	import { highlightPlaceholders } from '../logic/assistantFormUtils.svelte.js';

	let {
		systemPrompt = $bindable(''),
		promptTemplate = $bindable(''),
		ragPlaceholders = [],
		selectedPromptProcessor = '',
		formState,
		/** @type {(event: Event) => void} */
		oninput,
		onTemplateApplied
	} = $props();

	/** @type {HTMLTextAreaElement | null} */
	let textareaRef = $state(null);

	function handleLoadTemplate() {
		openTemplateSelectModal((/** @type {any} */ template) => {
			systemPrompt = template.system_prompt || '';
			promptTemplate = template.prompt_template || '';
			onTemplateApplied?.();
		});
	}

	/** @param {string} placeholder */
	function insertPlaceholder(placeholder) {
		if (textareaRef) {
			const start = textareaRef.selectionStart;
			const end = textareaRef.selectionEnd;
			const text = promptTemplate;
			promptTemplate = text.substring(0, start) + placeholder + text.substring(end);
			textareaRef.focus();
			tick().then(() => {
				if (textareaRef) {
					textareaRef.selectionStart = textareaRef.selectionEnd =
						start + placeholder.length;
				}
			});
		}
	}
</script>

<div>
	<div class="flex items-center justify-between mb-2">
		<label for="system-prompt" class="block text-sm font-medium text-gray-700">
			{$_('assistants.form.systemPrompt.label', { default: 'System Prompt' })}
		</label>
		{#if formState === 'create'}
			<button
				type="button"
				onclick={handleLoadTemplate}
				class="inline-flex items-center px-3 py-1 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
			>
				<svg class="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
					></path>
				</svg>
				{$_('promptTemplates.loadTemplate', { default: 'Load Template' })}
			</button>
		{/if}
	</div>
	<textarea
		id="system-prompt"
		name="system_prompt"
		bind:value={systemPrompt}
		oninput={oninput}
		rows="4"
		disabled={false}
		class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
		placeholder={$_('assistants.form.systemPrompt.placeholder', {
			default: "Define the assistant's role and personality..."
		})}
	></textarea>
</div>

<div>
	<label for="prompt-template" class="block text-sm font-medium text-gray-700">
		{$_('assistants.form.promptTemplate.label', { default: 'Prompt Template' })}
	</label>
	<div class="mt-1 mb-2">
		<span class="text-xs text-gray-600 dark:text-gray-400"
			>{$_('insert_placeholder') || 'Insert placeholder:'}:</span
		>
		{#each ragPlaceholders as placeholder (placeholder)}
			<button
				type="button"
				class="ml-1 px-2 py-0.5 text-xs bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-brand"
				onclick={() => insertPlaceholder(placeholder)}
			>
				{placeholder}
			</button>
		{/each}
	</div>
	<textarea
		bind:this={textareaRef}
		bind:value={promptTemplate}
		oninput={oninput}
		id="prompt_template"
		rows="6"
		class="mt-1 block w-full shadow-sm sm:text-sm border border-gray-300 rounded-md bg-white text-gray-900"
		placeholder={$_('assistants.form.promptTemplate.placeholder', { default: 'e.g. Use the {context} to answer the question: {user_input}' })}
	></textarea>
	{#if promptTemplate}
		<div class="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-sm">
			<div class="text-xs text-gray-500 mb-1">
				{$_('preview') || 'Preview with highlighted placeholders:'}
			</div>
			<div class="whitespace-pre-wrap" data-testid="prompt-preview">
				{@html highlightPlaceholders(promptTemplate, ragPlaceholders)}
			</div>
		</div>
	{/if}
	{#if selectedPromptProcessor === 'template_validator_processor'}
		<p class="mt-1 text-xs text-gray-500">
			{$_('assistants.form.promptTemplate.help', {
				default: 'This processor requires a valid prompt template.'
			})}
		</p>
	{/if}
</div>

<TemplateSelectModal />
