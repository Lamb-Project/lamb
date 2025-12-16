<script>
	import { _, locale } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';
	import { getToolComponent } from './plugins/index.js';
	import ToolConfigCard from './ToolConfigCard.svelte';

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
		tools = [],
		availableTools = [],
		availableKnowledgeBases = [],
		availableRubrics = [],
		availableFiles = [],
		disabled = false
	} = $props();

	// NOTE: Removed automatic dispatch on tools change to prevent infinite loop
	// Tools are updated via explicit event handlers (handleToolConfigChange, toggleToolEnabled, etc.)

	// Handle tool configuration changes
	function handleToolConfigChange(index, event) {
		const { config } = event.detail;
		const updatedTools = [...tools];
		updatedTools[index] = {
			...updatedTools[index],
			config: config
		};
		dispatch('toolsChange', { tools: updatedTools });
	}

	// Handle tool enable/disable
	function toggleToolEnabled(index) {
		const updatedTools = [...tools];
		updatedTools[index] = {
			...updatedTools[index],
			enabled: !updatedTools[index].enabled
		};
		dispatch('toolsChange', { tools: updatedTools });
	}

	// Remove tool
	function removeTool(index) {
		const updatedTools = tools.filter((tool, i) => i !== index);
		dispatch('toolsChange', { tools: updatedTools });
	}

	// Move tool up
	function moveToolUp(index) {
		if (index > 0) {
			const updatedTools = [...tools];
			[updatedTools[index - 1], updatedTools[index]] = [updatedTools[index], updatedTools[index - 1]];
			dispatch('toolsChange', { tools: updatedTools });
		}
	}

	// Move tool down
	function moveToolDown(index) {
		if (index < tools.length - 1) {
			const updatedTools = [...tools];
			[updatedTools[index], updatedTools[index + 1]] = [updatedTools[index + 1], updatedTools[index]];
			dispatch('toolsChange', { tools: updatedTools });
		}
	}

	// Add new tool
	function addTool(toolName) {
		console.log('addTool called with:', toolName);
		console.log('availableTools:', availableTools);
		console.log('current tools:', tools);
		
		const toolDef = availableTools.find(t => t.name === toolName);
		if (!toolDef) {
			console.error('Tool definition not found for:', toolName);
			return;
		}

		// Generate placeholder
		const toolType = toolDef.placeholder;
		const existingNumbers = tools
			.filter(t => t.placeholder && t.placeholder.endsWith(`_${toolType}`))
			.map(t => {
				const match = t.placeholder.match(/^(\d+)_/);
				return match ? parseInt(match[1]) : 0;
			});

		const nextNumber = existingNumbers.length > 0 ? Math.max(...existingNumbers) + 1 : 1;
		const placeholder = `${nextNumber}_${toolType}`;

		const newTool = {
			plugin: toolName,
			placeholder: placeholder,
			enabled: true,
			config: {}
		};

		console.log('Dispatching toolsChange with new tool:', newTool);
		dispatch('toolsChange', { tools: [...tools, newTool] });
	}

	// Get available tools that aren't already added
	let availableToolOptions = $derived(availableTools.filter(toolDef =>
		!tools.some(addedTool => addedTool.plugin === toolDef.name)
	));
	
	$effect(() => {
		console.log('availableToolOptions changed:', availableToolOptions);
		console.log('availableTools:', availableTools);
		console.log('tools:', tools);
	});

	// Get tool definition for a tool
	function getToolDefinition(toolName) {
		return availableTools.find(t => t.name === toolName);
	}
</script>

<div class="tools-manager">
	<div class="tools-header">
		<h3>{localeLoaded ? $_('Tool Pipeline') : 'Tool Pipeline'}</h3>
		<p class="tools-description">
			{localeLoaded ? $_('Configure the sequence of tools that will process user queries. Each tool adds context to the assistant\'s response.') : 'Configure the sequence of tools that will process user queries. Each tool adds context to the assistant\'s response.'}
		</p>
	</div>

	<!-- Tool Pipeline -->
	<div class="tools-pipeline">
		{#if tools.length === 0}
			<div class="empty-state">
				<div class="empty-icon">🔧</div>
				<h4>{localeLoaded ? $_('No tools configured') : 'No tools configured'}</h4>
				<p>{localeLoaded ? $_('Add tools below to start building your assistant\'s capabilities.') : 'Add tools below to start building your assistant\'s capabilities.'}</p>
			</div>
		{:else}
			<div class="tools-list">
				{#each tools as tool, index}
					{@const toolDef = getToolDefinition(tool.plugin)}
					<ToolConfigCard
						{tool}
						{toolDef}
						{index}
						{availableKnowledgeBases}
						{availableRubrics}
						{availableFiles}
						{disabled}
						totalTools={tools.length}
						onConfigChange={(event) => handleToolConfigChange(index, event)}
						onToggleEnabled={() => toggleToolEnabled(index)}
						onRemove={() => removeTool(index)}
						onMoveUp={() => moveToolUp(index)}
						onMoveDown={() => moveToolDown(index)}
					/>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Add Tool Section -->
	<div class="add-tool-section">
		<h4>{localeLoaded ? $_('Add Tool') : 'Add Tool'}</h4>
		{#if availableToolOptions.length === 0}
			<div class="no-tools-available">
				{localeLoaded ? $_('All available tools have been added to the pipeline.') : 'All available tools have been added to the pipeline.'}
			</div>
		{:else}
			<div class="tool-buttons">
				{#each availableToolOptions as toolDef}
					<button
						class="add-tool-btn"
						type="button"
						onclick={() => addTool(toolDef.name)}
						disabled={disabled}
					>
						<span class="tool-icon">
							{#if toolDef.category === 'rag'}
								📚
							{:else if toolDef.category === 'rubric'}
								📋
							{:else if toolDef.category === 'file'}
								📄
							{:else}
								🔧
							{/if}
						</span>
						<div class="tool-info">
							<strong>{toolDef.display_name}</strong>
							<small>{toolDef.description}</small>
						</div>
					</button>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Pipeline Summary -->
	{#if tools.length > 0}
		<div class="pipeline-summary">
			<h4>{localeLoaded ? $_('Pipeline Summary') : 'Pipeline Summary'}</h4>
			<div class="summary-items">
				{#each tools as tool, index}
					{@const toolDef = getToolDefinition(tool.plugin)}
					<div class="summary-item" class:disabled={!tool.enabled}>
						<span class="step-number">{index + 1}</span>
						<span class="tool-name">{toolDef?.display_name || tool.plugin}</span>
						<span class="placeholder">→ {tool.placeholder}</span>
						{#if !tool.enabled}
							<span class="disabled-badge">{localeLoaded ? $_('Disabled') : 'Disabled'}</span>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.tools-manager {
		width: 100%;
	}

	.tools-header {
		margin-bottom: 2rem;
	}

	.tools-header h3 {
		margin: 0 0 0.5rem 0;
		color: #212529;
		font-size: 1.5rem;
	}

	.tools-description {
		color: #6c757d;
		margin: 0;
		font-size: 0.95rem;
		line-height: 1.5;
	}

	.tools-pipeline {
		margin-bottom: 2rem;
	}

	.empty-state {
		text-align: center;
		padding: 3rem 2rem;
		background: #f8f9fa;
		border: 2px dashed #dee2e6;
		border-radius: 8px;
	}

	.empty-icon {
		font-size: 3rem;
		margin-bottom: 1rem;
		opacity: 0.5;
	}

	.empty-state h4 {
		color: #495057;
		margin: 0 0 0.5rem 0;
	}

	.empty-state p {
		color: #6c757d;
		margin: 0;
	}

	.tools-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.add-tool-section {
		border-top: 1px solid #e9ecef;
		padding-top: 2rem;
		margin-bottom: 2rem;
	}

	.add-tool-section h4 {
		margin: 0 0 1rem 0;
		color: #212529;
		font-size: 1.2rem;
	}

	.no-tools-available {
		padding: 1rem;
		background: #f8f9fa;
		border-radius: 6px;
		color: #6c757d;
		text-align: center;
		font-style: italic;
	}

	.tool-buttons {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 1rem;
	}

	.add-tool-btn {
		display: flex;
		align-items: center;
		padding: 1rem;
		background: white;
		border: 2px solid #e9ecef;
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
		width: 100%;
	}

	.add-tool-btn:hover:not(:disabled) {
		border-color: #0d6efd;
		box-shadow: 0 2px 8px rgba(13, 110, 253, 0.15);
		transform: translateY(-1px);
	}

	.add-tool-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.tool-icon {
		font-size: 1.5rem;
		margin-right: 0.75rem;
		flex-shrink: 0;
	}

	.tool-info strong {
		display: block;
		color: #212529;
		margin-bottom: 0.25rem;
		font-size: 1rem;
	}

	.tool-info small {
		color: #6c757d;
		font-size: 0.85rem;
		line-height: 1.3;
	}

	.pipeline-summary {
		background: #f8f9fa;
		border-radius: 8px;
		padding: 1.5rem;
		border: 1px solid #e9ecef;
	}

	.pipeline-summary h4 {
		margin: 0 0 1rem 0;
		color: #212529;
		font-size: 1.1rem;
	}

	.summary-items {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.summary-item {
		display: flex;
		align-items: center;
		padding: 0.5rem 0.75rem;
		background: white;
		border-radius: 6px;
		border: 1px solid #dee2e6;
		font-size: 0.9rem;
	}

	.summary-item.disabled {
		opacity: 0.6;
		background: #f8f9fa;
	}

	.step-number {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		background: #0d6efd;
		color: white;
		border-radius: 50%;
		font-weight: bold;
		font-size: 0.8rem;
		margin-right: 0.75rem;
		flex-shrink: 0;
	}

	.tool-name {
		flex: 1;
		font-weight: 500;
		color: #212529;
	}

	.placeholder {
		color: #6c757d;
		font-family: monospace;
		margin-right: 0.75rem;
	}

	.disabled-badge {
		background: #ffc107;
		color: #212529;
		padding: 0.2rem 0.5rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 500;
	}
</style>