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
					textareaRef.selectionStart = textareaRef.selectionEnd = start + placeholder.length;
				}
			});
		}
	}
</script>

<div>
	<div class="mb-2 flex items-center justify-between">
		<label for="system-prompt" class="block text-sm font-medium text-gray-700">
			{$_('assistants.form.systemPrompt.label', { default: 'System Prompt' })}
		</label>
		{#if formState === 'create'}
			<button
				type="button"
				onclick={handleLoadTemplate}
				class="focus:ring-brand inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none"
			>
				<svg class="mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
		{oninput}
		rows="4"
		disabled={false}
		class="focus:ring-brand focus:border-brand mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:outline-none sm:text-sm"
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
				class="focus:ring-brand ml-1 rounded bg-gray-200 px-2 py-0.5 text-xs hover:bg-gray-300 focus:ring-2 focus:outline-none dark:bg-gray-700 dark:hover:bg-gray-600"
				onclick={() => insertPlaceholder(placeholder)}
			>
				{placeholder}
			</button>
		{/each}
	</div>
	<textarea
		bind:this={textareaRef}
		bind:value={promptTemplate}
		{oninput}
		id="prompt_template"
		rows="6"
		class="mt-1 block w-full rounded-md border border-gray-300 bg-white text-gray-900 shadow-sm sm:text-sm"
		placeholder={$_('assistants.form.promptTemplate.placeholder', {
			default: 'e.g. Use the {context} to answer the question: {user_input}'
		})}
	></textarea>
	{#if promptTemplate}
		<div class="mt-2 rounded border border-gray-200 bg-gray-50 p-3 text-sm">
			<div class="mb-1 text-xs text-gray-500">
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
