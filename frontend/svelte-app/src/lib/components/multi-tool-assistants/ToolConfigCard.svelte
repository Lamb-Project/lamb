<script>
	import { _ } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';
	import { getToolComponent } from './plugins/index.js';

	const dispatch = createEventDispatcher();

	// Props
	let {
		tool,
		toolDef,
		index,
		availableKnowledgeBases = [],
		availableRubrics = [],
		availableFiles = [],
		disabled = false,
		totalTools = 1
	} = $props();

	// Local state
	let expanded = $state(false);

	// Get the specific config component for this tool
	let ToolConfigComponent = $derived(getToolComponent(tool.plugin));

	// Handle config changes from child component
	function handleConfigChange(event) {
		dispatch('configChange', event.detail);
	}

	// Get tool icon
	function getToolIcon(category) {
		switch (category) {
			case 'rag': return '📚';
			case 'rubric': return '📋';
			case 'file': return '📄';
			default: return '🔧';
		}
	}

	// Get validation errors
	let validationErrors = $derived(getValidationErrors());

	function getValidationErrors() {
		const errors = [];

		if (!tool.plugin) {
			errors.push($_("Tool plugin is required"));
		}

		if (!tool.placeholder) {
			errors.push($_("Placeholder is required"));
		}

		// Tool-specific validation
		if (tool.plugin === 'simple_rag') {
			if (!tool.config?.collections || tool.config.collections.length === 0) {
				errors.push($_("At least one knowledge base collection must be selected"));
			}
		} else if (tool.plugin === 'rubric_rag') {
			if (!tool.config?.rubric_id) {
				errors.push($_("A rubric must be selected"));
			}
		} else if (tool.plugin === 'single_file_rag') {
			if (!tool.config?.file_path) {
				errors.push($_("A file must be selected"));
			}
		}

		return errors;
	}
</script>

<div class="tool-card" class:disabled={!tool.enabled}>
	<!-- Card Header -->
	<div
		class="card-header"
		onclick={() => expanded = !expanded}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expanded = !expanded; } }}
		role="button"
		tabindex="0"
		aria-expanded={expanded}
		aria-controls="tool-config-content"
	>
		<div class="tool-info">
			<div class="tool-icon">
				{getToolIcon(toolDef?.category)}
			</div>
			<div class="tool-details">
				<h4 class="tool-name">
					{index + 1}. {toolDef?.display_name || tool.plugin}
					{#if !tool.enabled}
						<span class="disabled-indicator">({$_("Disabled")})</span>
					{/if}
				</h4>
				<p class="tool-description">{toolDef?.description || ''}</p>
				<div class="tool-meta">
					<span class="placeholder">{$_("Placeholder")}: <code>{tool.placeholder}</code></span>
					{#if toolDef?.category}
						<span class="category category-{toolDef.category}">{toolDef.category}</span>
					{/if}
				</div>
			</div>
		</div>

		<div class="card-actions">
			<!-- Move Up/Down buttons -->
			{#if totalTools > 1}
				<div class="move-buttons">
					<button
						class="move-btn"
						onclick={(e) => { e.stopPropagation(); dispatch('moveUp'); }}
						disabled={index === 0 || disabled}
						title={$_("Move up")}
					>
						▲
					</button>
					<button
						class="move-btn"
						onclick={(e) => { e.stopPropagation(); dispatch('moveDown'); }}
						disabled={index === totalTools - 1 || disabled}
						title={$_("Move down")}
					>
						▼
					</button>
				</div>
			{/if}

			<!-- Enable/Disable toggle -->
				<label class="toggle-switch" title={tool.enabled ? $_("Disable tool") : $_("Enable tool")}>
					<input
						type="checkbox"
						bind:checked={tool.enabled}
						onchange={(e) => { e.stopPropagation(); dispatch('toggleEnabled'); }}
						disabled={disabled}
					/>
					<span class="toggle-slider"></span>
				</label>

			<!-- Expand/Collapse button -->
			<button
				class="expand-btn"
				onclick={(e) => { e.stopPropagation(); expanded = !expanded; }}
				disabled={disabled}
			>
				{expanded ? '−' : '+'}
			</button>

			<!-- Remove button -->
			<button
				class="remove-btn"
				onclick={(e) => { e.stopPropagation(); dispatch('remove'); }}
				disabled={disabled}
				title={$_("Remove tool")}
			>
				✕
			</button>
		</div>
	</div>

	<!-- Validation Errors -->
	{#if validationErrors.length > 0}
		<div class="validation-errors">
			{#each validationErrors as error}
				<div class="error-item">⚠️ {error}</div>
			{/each}
		</div>
	{/if}

	<!-- Expandable Configuration -->
	{#if expanded}
		<div
			class="card-content"
			id="tool-config-content"
			transition:slide={{ duration: 200 }}
		>
			{#if ToolConfigComponent}
				<ToolConfigComponent
					{tool}
					{availableKnowledgeBases}
					{availableRubrics}
					{availableFiles}
					onconfigChange={handleConfigChange}
				/>
			{:else}
				<div class="no-config">
					{$_("No configuration options available for this tool.")}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.tool-card {
		background: white;
		border: 1px solid #dee2e6;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
		transition: all 0.2s ease;
	}

	.tool-card:hover:not(.disabled) {
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
		border-color: #0d6efd;
	}

	.tool-card.disabled {
		opacity: 0.7;
		background: #f8f9fa;
	}

	.card-header {
		display: flex;
		align-items: center;
		padding: 1rem;
		cursor: pointer;
		border-radius: 8px 8px 0 0;
		transition: background-color 0.2s ease;
	}

	.card-header:hover {
		background: #f8f9fa;
	}

	.tool-info {
		display: flex;
		align-items: flex-start;
		flex: 1;
		gap: 0.75rem;
	}

	.tool-icon {
		font-size: 1.5rem;
		flex-shrink: 0;
		margin-top: 0.25rem;
	}

	.tool-details {
		flex: 1;
		min-width: 0;
	}

	.tool-name {
		margin: 0 0 0.25rem 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: #212529;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.disabled-indicator {
		color: #6c757d;
		font-weight: normal;
		font-size: 0.9rem;
	}

	.tool-description {
		margin: 0 0 0.5rem 0;
		color: #6c757d;
		font-size: 0.9rem;
		line-height: 1.4;
	}

	.tool-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		font-size: 0.85rem;
	}

	.placeholder {
		color: #495057;
	}

	.placeholder code {
		background: #f1f3f4;
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
		font-family: 'Monaco', 'Menlo', monospace;
		font-size: 0.8rem;
	}

	.category {
		padding: 0.2rem 0.5rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 500;
		text-transform: uppercase;
	}

	.category-rag {
		background: #d1ecf1;
		color: #0c5460;
	}

	.category-rubric {
		background: #d4edda;
		color: #155724;
	}

	.category-file {
		background: #f8d7da;
		color: #721c24;
	}

	.card-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.move-buttons {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.move-btn {
		width: 24px;
		height: 20px;
		border: 1px solid #dee2e6;
		background: white;
		border-radius: 3px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		color: #6c757d;
		transition: all 0.2s ease;
	}

	.move-btn:hover:not(:disabled) {
		background: #0d6efd;
		color: white;
		border-color: #0d6efd;
	}

	.move-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.toggle-switch {
		position: relative;
		display: inline-block;
		width: 44px;
		height: 24px;
		cursor: pointer;
	}

	.toggle-switch input {
		opacity: 0;
		width: 0;
		height: 0;
	}

	.toggle-slider {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: #ccc;
		border-radius: 24px;
		transition: 0.3s;
	}

	.toggle-slider:before {
		position: absolute;
		content: "";
		height: 18px;
		width: 18px;
		left: 3px;
		bottom: 3px;
		background-color: white;
		border-radius: 50%;
		transition: 0.3s;
	}

	input:checked + .toggle-slider {
		background-color: #0d6efd;
	}

	input:checked + .toggle-slider:before {
		transform: translateX(20px);
	}

	.expand-btn, .remove-btn {
		width: 28px;
		height: 28px;
		border: 1px solid #dee2e6;
		background: white;
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 14px;
		color: #6c757d;
		transition: all 0.2s ease;
	}

	.expand-btn:hover:not(:disabled) {
		background: #e9ecef;
		color: #495057;
	}

	.remove-btn:hover:not(:disabled) {
		background: #dc3545;
		color: white;
		border-color: #dc3545;
	}

	.expand-btn:disabled, .remove-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.validation-errors {
		padding: 0.75rem 1rem;
		background: #f8d7da;
		border-top: 1px solid #f5c6cb;
	}

	.error-item {
		color: #721c24;
		font-size: 0.9rem;
		margin-bottom: 0.25rem;
	}

	.error-item:last-child {
		margin-bottom: 0;
	}

	.card-content {
		padding: 0;
		border-top: 1px solid #e9ecef;
		background: #f8f9fa;
		border-radius: 0 0 8px 8px;
	}

	.no-config {
		padding: 1rem;
		color: #6c757d;
		font-style: italic;
		text-align: center;
	}

	/* Slide transition */
	:global(.tool-card .card-content) {
		overflow: hidden;
	}

	:global(.tool-card .card-content > div) {
		padding: 1rem;
	}
</style>