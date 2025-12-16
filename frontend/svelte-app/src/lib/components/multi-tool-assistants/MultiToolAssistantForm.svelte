<script>
	import { _, locale } from '$lib/i18n';
	import multiToolStore, { multiToolStoreActions } from '$lib/stores/multiToolStore';
	import { createMultiToolAssistant, updateMultiToolAssistant, validateMultiToolConfig, getAvailableTools, getAvailableOrchestrators } from '$lib/services/multiToolAssistantService';
	import { getUserKnowledgeBases } from '$lib/services/knowledgeBaseService';
	import { fetchAccessibleRubrics } from '$lib/services/rubricService';
	import { getSystemCapabilities } from '$lib/services/assistantService';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { createEventDispatcher } from 'svelte';
	import { onMount, onDestroy } from 'svelte';
	import TemplateSelectModal from '$lib/components/modals/TemplateSelectModal.svelte';
	import { openTemplateSelectModal } from '$lib/stores/templateStore';
	import { sanitizeName } from '$lib/utils/nameSanitizer';
	import ToolsManager from './ToolsManager.svelte';

	const dispatch = createEventDispatcher();

	// Locale state for i18n
	let localeLoaded = $state(false);
	let localeUnsubscribe = () => {};
	$effect(() => {
		localeUnsubscribe = locale.subscribe(value => {
			localeLoaded = !!value;
		});
		return () => {
			localeUnsubscribe();
		};
	});

	// Props
	let {
		assistant = null,
		startInEdit = false
	} = $props();

	// Subscribe to store
	let storeUnsubscribe = () => {};
	let currentState = $state(null);

	// Reactive statements for store values (read-only for display)
	let name = $derived(currentState?.name || '');
	let description = $derived(currentState?.description || '');
	let system_prompt = $derived(currentState?.system_prompt || '');
	let prompt_template = $derived(currentState?.prompt_template || '');
	let orchestrator = $derived(currentState?.orchestrator || 'sequential');
	let connector = $derived(currentState?.connector || 'openai');
	let llm = $derived(currentState?.llm || 'gpt-4o-mini');
	let verbose = $derived(currentState?.verbose || false);
	let tools = $derived(currentState?.tools || []);
	let availableTools = $derived(currentState?.availableTools || []);
	let availableOrchestrators = $derived(currentState?.availableOrchestrators || []);
	let loading = $derived(currentState?.loading || false);
	let error = $derived(currentState?.error || null);
	let saving = $derived(currentState?.saving || false);

	// Helper functions to update store
	function updateName(value) {
		multiToolStoreActions.updateField('name', value);
	}
	function updateDescription(value) {
		multiToolStoreActions.updateField('description', value);
	}
	function updateSystemPrompt(value) {
		multiToolStoreActions.updateField('system_prompt', value);
	}
	function updatePromptTemplate(value) {
		multiToolStoreActions.updateField('prompt_template', value);
	}
	function updateOrchestrator(value) {
		multiToolStoreActions.updateField('orchestrator', value);
	}
	function updateConnector(value) {
		multiToolStoreActions.updateField('connector', value);
	}
	function updateLlm(value) {
		multiToolStoreActions.updateField('llm', value);
	}
	function updateVerbose(value) {
		multiToolStoreActions.updateField('verbose', value);
	}

	// Local state
	let formState = $state(assistant ? 'edit' : 'create');
	let isAdvancedMode = $state(false);

	// Data for tool configuration
	let availableKnowledgeBases = $state([]);
	let availableRubrics = $state([]);
	let availableFiles = $state([]); // For single_file_rag

	// Template modal state
	let showTemplateModal = $state(false);
	let templateTarget = $state(''); // 'system_prompt' or 'prompt_template'

	// Form validation
	let validationErrors = $derived(getFormValidationErrors());

	function getFormValidationErrors() {
		const errors = [];

		if (!name.trim()) {
			errors.push(localeLoaded ? $_('Assistant name is required') : 'Assistant name is required');
		}

		if (tools.length === 0) {
			errors.push(localeLoaded ? $_('At least one tool must be configured') : 'At least one tool must be configured');
		}

		// Validate tool configurations
		const toolErrors = validateMultiToolConfig({
			assistant_type: "multi_tool",
			tools: tools
		});

		errors.push(...toolErrors);

		return errors;
	}

	// Computed values
	let sanitizedNameInfo = $derived(sanitizeName(name));
	let showSanitizationPreview = $derived(formState === 'create' && sanitizedNameInfo.wasModified);

	// Initialize form
	onMount(async () => {
		storeUnsubscribe = multiToolStore.subscribe(state => {
			currentState = state;
		});

		// Reset store for new form
		multiToolStoreActions.reset();

		// Load available tools and orchestrators
		try {
			const [tools, orchestrators] = await Promise.all([
				getAvailableTools(),
				getAvailableOrchestrators()
			]);

			multiToolStoreActions.setAvailableTools(tools);
			multiToolStoreActions.setAvailableOrchestrators(orchestrators);
		} catch (err) {
			console.error('Error loading available tools/orchestrators:', err);
			multiToolStoreActions.setError('Failed to load available tools and orchestrators');
		}

		// Load data if editing existing assistant
		if (assistant) {
			multiToolStoreActions.loadFromAssistant(assistant);
		}

		// Load additional data needed for tool configuration
		await loadToolConfigurationData();
	});

	async function loadToolConfigurationData() {
		try {
			const [kbData, rubricsData] = await Promise.all([
				getUserKnowledgeBases(),
				fetchAccessibleRubrics()
			]);

			availableKnowledgeBases = kbData.knowledgeBases || [];
			availableRubrics = rubricsData || [];

			// TODO: Load available files for single_file_rag
			availableFiles = []; // Placeholder for now
		} catch (err) {
			console.error('Error loading tool configuration data:', err);
		}
	}

	// Handle form submission
	async function handleSubmit() {
		if (validationErrors.length > 0) {
			multiToolStoreActions.setError('Please fix validation errors before saving');
			return;
		}

		multiToolStoreActions.setSaving(true);
		multiToolStoreActions.clearError();

		try {
			const assistantData = {
				name: name.trim(),
				description: description.trim(),
				system_prompt: system_prompt.trim(),
				prompt_template: prompt_template.trim(),
				orchestrator,
				connector,
				llm,
				verbose,
				tools
			};

			let result;
			if (formState === 'create') {
				result = await createMultiToolAssistant(assistantData);
		} else {
			result = await updateMultiToolAssistant(assistant.id, assistantData);
		}

		dispatch('success', { assistant: result });
		goto(`${base}/assistants`);

	} catch (error) {
			console.error('Error saving multi-tool assistant:', error);
			multiToolStoreActions.setError(error.message || 'Failed to save assistant');
		} finally {
			multiToolStoreActions.setSaving(false);
		}
	}

	// Handle cancel
	function handleCancel() {
		const message = 'Are you sure you want to cancel? Any unsaved changes will be lost.';
		if (confirm(message)) {
			goto(`${base}/assistants`);
		}
	}

	// Handle tools change
	function handleToolsChange(event) {
		console.log('handleToolsChange called with event:', event);
		const { tools: newTools } = event.detail;
		console.log('New tools to update:', newTools);
		multiToolStoreActions.updateField('tools', newTools);
		console.log('Store updated with tools');
	}

	// Handle template insertion
	function handleInsertTemplate(targetField) {
		templateTarget = targetField;
		showTemplateModal = true;
		openTemplateSelectModal();
	}

	function handleTemplateSelected(event) {
		const { template } = event.detail;
		const targetField = templateTarget;

		if (targetField === 'system_prompt') {
			updateSystemPrompt(template.system_prompt || currentState?.system_prompt || '');
		} else if (targetField === 'prompt_template') {
			updatePromptTemplate(template.prompt_template || currentState?.prompt_template || '');
		}

		showTemplateModal = false;
		templateTarget = '';
	}

	// Cleanup on unmount
	onDestroy(() => {
		if (storeUnsubscribe) {
			storeUnsubscribe();
		}
	});
</script>

<div class="multi-tool-form">
	<div class="form-header">
		<h2>
			{formState === 'create' ? (localeLoaded ? $_('Create Multi-Tool Assistant') : 'Create Multi-Tool Assistant') : (localeLoaded ? $_('Edit Multi-Tool Assistant') : 'Edit Multi-Tool Assistant')}
		</h2>
		<p class="form-description">
			{localeLoaded ? $_('Configure an assistant that can use multiple tools to gather context before responding.') : 'Configure an assistant that can use multiple tools to gather context before responding.'}
		</p>
	</div>

	{#if error}
		<div class="error-banner">
			<strong>{localeLoaded ? $_('Error') : 'Error'}:</strong> {error}
		</div>
	{/if}

	<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
		<!-- Basic Information -->
		<div class="form-section">
			<h3>{localeLoaded ? $_('Basic Information') : 'Basic Information'}</h3>

			<div class="form-row">
				<label for="assistant-name">
					<strong>{localeLoaded ? $_('Assistant Name') : 'Assistant Name'} *</strong>
				</label>
				<input
					id="assistant-name"
					type="text"
					value={name}
					oninput={(e) => updateName(e.target.value)}
					placeholder={localeLoaded ? $_('Enter assistant name') : 'Enter assistant name'}
					required
					disabled={saving}
					class="form-input"
				/>
				{#if showSanitizationPreview}
					<div class="sanitization-preview">
						{localeLoaded ? $_('Will be saved as') : 'Will be saved as'}: <code>{sanitizedNameInfo.sanitized}</code>
					</div>
				{/if}
			</div>

			<div class="form-row">
				<label for="assistant-description">
					<strong>{localeLoaded ? $_('Description') : 'Description'}</strong>
				</label>
				<textarea
					id="assistant-description"
					value={description}
					oninput={(e) => updateDescription(e.target.value)}
					placeholder={localeLoaded ? $_('Describe what this assistant does') : 'Describe what this assistant does'}
					rows="3"
					disabled={saving}
					class="form-textarea"
				></textarea>
			</div>
		</div>

		<!-- System Prompt -->
		<div class="form-section">
			<div class="section-header">
				<h3>{localeLoaded ? $_('System Prompt') : 'System Prompt'}</h3>
				<button
					type="button"
					class="template-btn"
					onclick={() => handleInsertTemplate('system_prompt')}
					disabled={saving}
				>
					{localeLoaded ? $_('Use Template') : 'Use Template'}
				</button>
			</div>
			<textarea
				value={system_prompt}
				oninput={(e) => updateSystemPrompt(e.target.value)}
				placeholder={localeLoaded ? $_('Instructions for how the assistant should behave') : 'Instructions for how the assistant should behave'}
				rows="4"
				disabled={saving}
				class="form-textarea code-textarea"
			></textarea>
		</div>

		<!-- Orchestrator Settings -->
		<div class="form-section">
			<h3>{localeLoaded ? $_('Execution Strategy') : 'Execution Strategy'}</h3>

			<div class="form-row">
				<label for="orchestrator-select">
					<strong>{localeLoaded ? $_('Orchestrator Strategy') : 'Orchestrator Strategy'}</strong>
				</label>
				<select
					id="orchestrator-select"
					value={orchestrator}
					onchange={(e) => updateOrchestrator(e.target.value)}
					disabled={saving}
					class="form-select"
				>
					{#each availableOrchestrators as orch}
						<option value={orch.name}>
							{orch.name} - {orch.description}
						</option>
					{/each}
				</select>
			</div>

			<div class="form-row">
				<label class="checkbox-label">
					<input
						type="checkbox"
						checked={verbose}
						onchange={(e) => updateVerbose(e.target.checked)}
						disabled={saving}
					/>
					<span class="checkmark"></span>
					<strong>{localeLoaded ? $_('Enable Verbose Reporting') : 'Enable Verbose Reporting'}</strong>
					<small class="help-text">
						{localeLoaded ? $_('Return detailed execution information instead of processed messages') : 'Return detailed execution information instead of processed messages'}
					</small>
				</label>
			</div>
		</div>

		<!-- LLM Settings -->
		<div class="form-section">
			<h3>{localeLoaded ? $_('Language Model Settings') : 'Language Model Settings'}</h3>

			<div class="form-row">
				<label for="connector-select">
					<strong>{localeLoaded ? $_('Connector') : 'Connector'}</strong>
				</label>
				<select
					id="connector-select"
					value={connector}
					onchange={(e) => updateConnector(e.target.value)}
					disabled={saving}
					class="form-select"
				>
					<option value="openai">OpenAI</option>
					<option value="anthropic">Anthropic</option>
					<!-- Add other connectors as available -->
				</select>
			</div>

			<div class="form-row">
				<label for="llm-select">
					<strong>{localeLoaded ? $_('Model') : 'Model'}</strong>
				</label>
				<select
					id="llm-select"
					value={llm}
					onchange={(e) => updateLlm(e.target.value)}
					disabled={saving}
					class="form-select"
				>
					<option value="gpt-4o-mini">GPT-4o Mini</option>
					<option value="gpt-4o">GPT-4o</option>
					<option value="gpt-4-turbo">GPT-4 Turbo</option>
					<!-- Add other models as available -->
				</select>
			</div>
		</div>

		<!-- Prompt Template -->
		<div class="form-section">
			<div class="section-header">
				<h3>{localeLoaded ? $_('Prompt Template') : 'Prompt Template'}</h3>
				<button
					type="button"
					class="template-btn"
					onclick={() => handleInsertTemplate('prompt_template')}
					disabled={saving}
				>
					{localeLoaded ? $_('Use Template') : 'Use Template'}
				</button>
			</div>
			<textarea
				value={prompt_template}
				oninput={(e) => updatePromptTemplate(e.target.value)}
				placeholder={localeLoaded ? $_('Template with placeholders like {1_context}, {user_input}, etc.') : 'Template with placeholders like {1_context}, {user_input}, etc.'}
				rows="6"
				disabled={saving}
				class="form-textarea code-textarea"
		></textarea>
		<small class="help-text">
			{localeLoaded ? $_('Use {user_input} for the user\'s message. Tool outputs will be available as numbered placeholders like {1_context}.') : 'Use {user_input} for the user\'s message. Tool outputs will be available as numbered placeholders like {1_context}.'}
		</small>
	</div>

		<!-- Tools Manager -->
		<div class="form-section">
			<h3>{localeLoaded ? $_('Tool Configuration') : 'Tool Configuration'}</h3>
			<ToolsManager
				{tools}
				{availableTools}
				{availableKnowledgeBases}
				{availableRubrics}
				{availableFiles}
				disabled={saving}
				on:toolsChange={handleToolsChange}
			/>
		</div>

		<!-- Validation Errors -->
		{#if validationErrors.length > 0}
			<div class="validation-errors">
				<h4>{localeLoaded ? $_('Please fix the following errors') : 'Please fix the following errors'}:</h4>
				<ul>
					{#each validationErrors as error}
						<li>{error}</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Form Actions -->
		<div class="form-actions">
			<button
				type="button"
				class="cancel-btn"
				onclick={handleCancel}
				disabled={saving}
			>
				{localeLoaded ? $_('Cancel') : 'Cancel'}
			</button>
			<button
				type="submit"
				class="save-btn"
				disabled={saving || validationErrors.length > 0}
			>
				{#if saving}
					{localeLoaded ? $_('Saving...') : 'Saving...'}
				{:else}
					{formState === 'create' ? (localeLoaded ? $_('Create Assistant') : 'Create Assistant') : (localeLoaded ? $_('Update Assistant') : 'Update Assistant')}
				{/if}
			</button>
		</div>
	</form>
</div>

<!-- Template Modal -->
{#if showTemplateModal}
	<TemplateSelectModal
		on:select={handleTemplateSelected}
		on:cancel={() => showTemplateModal = false}
	/>
{/if}

<style>
	.multi-tool-form {
		max-width: 1000px;
		margin: 0 auto;
		padding: 2rem;
	}

	.form-header {
		margin-bottom: 2rem;
		text-align: center;
	}

	.form-header h2 {
		margin: 0 0 0.5rem 0;
		color: #212529;
		font-size: 2rem;
	}

	.form-description {
		color: #6c757d;
		margin: 0;
		font-size: 1.1rem;
	}

	.error-banner {
		padding: 1rem;
		background: #f8d7da;
		border: 1px solid #f5c6cb;
		border-radius: 6px;
		color: #721c24;
		margin-bottom: 2rem;
	}

	.form-section {
		background: white;
		border: 1px solid #dee2e6;
		border-radius: 8px;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.form-section h3 {
		margin: 0 0 1rem 0;
		color: #212529;
		font-size: 1.25rem;
		border-bottom: 2px solid #e9ecef;
		padding-bottom: 0.5rem;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}

	.section-header h3 {
		margin: 0;
		border: none;
		padding: 0;
	}

	.template-btn {
		background: #0d6efd;
		color: white;
		border: none;
		padding: 0.5rem 1rem;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.9rem;
		transition: background-color 0.2s ease;
	}

	.template-btn:hover:not(:disabled) {
		background: #0b5ed7;
	}

	.template-btn:disabled {
		background: #6c757d;
		cursor: not-allowed;
	}

	.form-row {
		margin-bottom: 1rem;
	}

	.form-row label {
		display: block;
		margin-bottom: 0.5rem;
		color: #212529;
		font-weight: 600;
	}

	.form-input, .form-textarea, .form-select {
		width: 100%;
		padding: 0.75rem;
		border: 1px solid #ced4da;
		border-radius: 4px;
		font-size: 1rem;
		transition: border-color 0.2s ease, box-shadow 0.2s ease;
	}

	.form-input:focus, .form-textarea:focus, .form-select:focus {
		outline: none;
		border-color: #0d6efd;
		box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
	}

	.form-textarea {
		resize: vertical;
		min-height: 80px;
	}

	.code-textarea {
		font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
		font-size: 0.9rem;
		line-height: 1.4;
	}

	.form-select {
		background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3e%3c/svg%3e");
		background-position: right 0.5rem center;
		background-repeat: no-repeat;
		background-size: 1.5em 1.5em;
		padding-right: 2.5rem;
	}

	.checkbox-label {
		display: flex;
		align-items: flex-start;
		cursor: pointer;
		font-weight: normal !important;
		margin-bottom: 0.5rem;
	}

	.checkbox-label input[type="checkbox"] {
		display: none;
	}

	.checkmark {
		width: 18px;
		height: 18px;
		border: 2px solid #dee2e6;
		border-radius: 3px;
		margin-right: 0.75rem;
		margin-top: 2px;
		position: relative;
		flex-shrink: 0;
	}

	.checkbox-label input:checked + .checkmark {
		background-color: #0d6efd;
		border-color: #0d6efd;
	}

	.checkbox-label input:checked + .checkmark::after {
		content: '✓';
		position: absolute;
		color: white;
		font-size: 12px;
		font-weight: bold;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
	}

	.help-text {
		color: #6c757d;
		font-size: 0.85rem;
		display: block;
		margin-top: 0.25rem;
	}

	.sanitization-preview {
		margin-top: 0.5rem;
		padding: 0.5rem;
		background: #fff3cd;
		border: 1px solid #ffeaa7;
		border-radius: 4px;
		font-size: 0.9rem;
	}

	.sanitization-preview code {
		background: #f8f9fa;
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
		font-family: monospace;
	}

	.validation-errors {
		background: #f8d7da;
		border: 1px solid #f5c6cb;
		border-radius: 6px;
		padding: 1rem;
		margin-bottom: 1.5rem;
	}

	.validation-errors h4 {
		margin: 0 0 0.75rem 0;
		color: #721c24;
		font-size: 1rem;
	}

	.validation-errors ul {
		margin: 0;
		padding-left: 1.5rem;
	}

	.validation-errors li {
		color: #721c24;
		margin-bottom: 0.25rem;
	}

	.form-actions {
		display: flex;
		justify-content: flex-end;
		gap: 1rem;
		margin-top: 2rem;
		padding-top: 1.5rem;
		border-top: 1px solid #e9ecef;
	}

	.cancel-btn, .save-btn {
		padding: 0.75rem 1.5rem;
		border-radius: 6px;
		font-size: 1rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s ease;
		border: 1px solid #dee2e6;
	}

	.cancel-btn {
		background: white;
		color: #6c757d;
	}

	.cancel-btn:hover:not(:disabled) {
		background: #f8f9fa;
		color: #495057;
	}

	.save-btn {
		background: #0d6efd;
		color: white;
		border-color: #0d6efd;
	}

	.save-btn:hover:not(:disabled) {
		background: #0b5ed7;
		border-color: #0b5ed7;
	}

	.cancel-btn:disabled, .save-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
</style>