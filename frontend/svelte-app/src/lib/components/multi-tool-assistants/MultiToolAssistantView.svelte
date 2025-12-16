<script>
	import { _ } from '$lib/i18n';
	import { parseMultiToolMetadata } from '$lib/services/multiToolAssistantService';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// Props
	let {
		assistant
	} = $props();

	// Parse metadata
	let metadata = $derived(parseMultiToolMetadata(assistant));

	// Helper functions
	function getToolIcon(category) {
		switch (category) {
			case 'rag': return '📚';
			case 'rubric': return '📋';
			case 'file': return '📄';
			default: return '🔧';
		}
	}

	function formatDate(dateString) {
		if (!dateString) return '';
		return new Date(dateString).toLocaleDateString();
	}

	// Handle actions
	function handleEdit() {
		dispatch('edit', { assistant });
	}

	function handleDelete() {
		dispatch('delete', { assistant });
	}

	function handleDuplicate() {
		dispatch('duplicate', { assistant });
	}

	function handleShare() {
		dispatch('share', { assistant });
	}

	function handleTest() {
		dispatch('test', { assistant });
	}
</script>

<div class="multi-tool-view">
	<!-- Header -->
	<div class="view-header">
		<div class="assistant-info">
			<div class="assistant-icon">🔧</div>
			<div class="assistant-details">
				<h1>{assistant.name}</h1>
				{#if assistant.description}
					<p class="description">{assistant.description}</p>
				{/if}
				<div class="meta-info">
					<span class="meta-item">
						<strong>{_("Type")}:</strong> Multi-Tool Assistant
					</span>
					<span class="meta-item">
						<strong>{_("Orchestrator")}:</strong> {metadata.orchestrator}
					</span>
					{#if assistant.owner}
						<span class="meta-item">
							<strong>{_("Owner")}:</strong> {assistant.owner}
						</span>
					{/if}
					{#if assistant.created_at}
						<span class="meta-item">
							<strong>{_("Created")}:</strong> {formatDate(assistant.created_at)}
						</span>
					{/if}
				</div>
			</div>
		</div>

		<div class="action-buttons">
			<button class="action-btn secondary" onclick={handleTest}>
				🧪 {_("Test Assistant")}
			</button>
			{#if assistant.published}
				<button class="action-btn warning" onclick={() => dispatch('unpublish', { assistant })}>
					🚫 {_("Unpublish")}
				</button>
			{:else}
				<button class="action-btn success" onclick={() => dispatch('publish', { assistant })}>
					📤 {_("Publish")}
				</button>
			{/if}
			<button class="action-btn secondary" onclick={handleShare}>
				🔗 {_("Share")}
			</button>
			<button class="action-btn secondary" onclick={handleDuplicate}>
				📋 {_("Duplicate")}
			</button>
			<button class="action-btn primary" onclick={handleEdit}>
				✏️ {_("Edit")}
			</button>
			<button class="action-btn danger" onclick={handleDelete}>
				🗑️ {_("Delete")}
			</button>
		</div>
	</div>

	<!-- Content Grid -->
	<div class="content-grid">
		<!-- Basic Configuration -->
		<div class="content-section">
			<h2>{_("Configuration")}</h2>

			<div class="config-grid">
				<div class="config-item">
					<div class="label">{_("Orchestrator Strategy")}</div>
					<div class="value">{metadata.orchestrator}</div>
					<small class="description">
						{#if metadata.orchestrator === 'sequential'}
							{_("Tools execute in order with chained context")}
						{:else if metadata.orchestrator === 'parallel'}
							{_("All tools execute concurrently")}
						{:else}
							{_("Custom execution strategy")}
						{/if}
					</small>
				</div>

				<div class="config-item">
					<div class="label">{_("Language Model")}</div>
					<div class="value">{metadata.connector} - {metadata.llm}</div>
				</div>

				<div class="config-item">
					<div class="label">{_("Verbose Reporting")}</div>
					<div class="value">
						{#if metadata.verbose}
							<span class="badge enabled">✓ {_("Enabled")}</span>
						{:else}
							<span class="badge disabled">✗ {_("Disabled")}</span>
						{/if}
					</div>
					<small class="description">
						{_("Returns detailed execution information")}
					</small>
				</div>
			</div>
		</div>

		<!-- System Prompt -->
		{#if assistant.system_prompt}
			<div class="content-section">
				<h2>{_("System Prompt")}</h2>
				<div class="code-block">
					<pre>{assistant.system_prompt}</pre>
				</div>
			</div>
		{/if}

		<!-- Prompt Template -->
		{#if assistant.prompt_template}
			<div class="content-section">
				<h2>{_("Prompt Template")}</h2>
				<div class="code-block">
					<pre>{assistant.prompt_template}</pre>
				</div>
				<div class="template-info">
					<h3>{_("Placeholders Used")}</h3>
					<div class="placeholders">
						{#each metadata.tools as tool}
							<span class="placeholder-tag">{tool.placeholder}</span>
						{/each}
						{#if assistant.prompt_template.includes('{user_input}')}
							<span class="placeholder-tag">user_input</span>
						{/if}
					</div>
				</div>
			</div>
		{/if}

		<!-- Tool Pipeline -->
		<div class="content-section">
			<h2>{_("Tool Pipeline")}</h2>

			{#if metadata.tools.length === 0}
				<div class="empty-state">
					<p>{_("No tools configured")}</p>
				</div>
			{:else}
				<div class="tool-pipeline">
					{#each metadata.tools as tool, index}
						<div class="tool-card" class:disabled={!tool.enabled}>
							<div class="tool-header">
								<div class="tool-order">{index + 1}</div>
								<div class="tool-icon">{getToolIcon('rag')}</div>
								<div class="tool-info">
									<h3>{tool.plugin}</h3>
									{#if !tool.enabled}
										<span class="disabled-badge">{_("Disabled")}</span>
									{/if}
								</div>
							</div>

							<div class="tool-details">
								<div class="detail-item">
									<strong>{_("Placeholder")}:</strong>
									<code>{tool.placeholder}</code>
								</div>

								{#if tool.config}
									<div class="tool-config">
										<strong>{_("Configuration")}:</strong>
										<div class="config-json">
											<pre>{JSON.stringify(tool.config, null, 2)}</pre>
										</div>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>

				<!-- Pipeline Flow -->
				<div class="pipeline-flow">
					<h3>{_("Execution Flow")}</h3>
					<div class="flow-diagram">
						{#each metadata.tools as tool, index}
							<div class="flow-step">
								<div class="step-number">{index + 1}</div>
								<div class="step-name">{tool.plugin}</div>
								<div class="step-output">{tool.placeholder}</div>
								{#if index < metadata.tools.length - 1}
									<div class="flow-arrow">→</div>
								{/if}
							</div>
						{/each}
						<div class="flow-arrow">→</div>
						<div class="flow-step final">
							<div class="step-number">✓</div>
							<div class="step-name">{_("LLM Response")}</div>
						</div>
					</div>
				</div>
			{/if}
		</div>

		<!-- Statistics -->
		<div class="content-section">
			<h2>{_("Statistics")}</h2>

			<div class="stats-grid">
				<div class="stat-item">
					<div class="stat-value">{metadata.tools.length}</div>
					<div class="stat-label">{_("Total Tools")}</div>
				</div>

				<div class="stat-item">
					<div class="stat-value">{metadata.tools.filter(t => t.enabled).length}</div>
					<div class="stat-label">{_("Active Tools")}</div>
				</div>

				<div class="stat-item">
					<div class="stat-value">{metadata.tools.filter(t => !t.enabled).length}</div>
					<div class="stat-label">{_("Disabled Tools")}</div>
				</div>

				{#if assistant.published}
					<div class="stat-item">
						<div class="stat-value published">📤</div>
						<div class="stat-label">{_("Published")}</div>
					</div>
				{:else}
					<div class="stat-item">
						<div class="stat-value draft">📝</div>
						<div class="stat-label">{_("Draft")}</div>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.multi-tool-view {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem;
	}

	.view-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 2rem;
		padding-bottom: 1.5rem;
		border-bottom: 2px solid #e9ecef;
	}

	.assistant-info {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		flex: 1;
	}

	.assistant-icon {
		font-size: 3rem;
		flex-shrink: 0;
	}

	.assistant-details h1 {
		margin: 0 0 0.5rem 0;
		color: #212529;
		font-size: 2.5rem;
	}

	.description {
		color: #6c757d;
		font-size: 1.1rem;
		margin: 0 0 1rem 0;
		line-height: 1.5;
	}

	.meta-info {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		font-size: 0.9rem;
	}

	.meta-item {
		color: #495057;
	}

	.action-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.action-btn {
		padding: 0.5rem 1rem;
		border: 1px solid #dee2e6;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.9rem;
		font-weight: 500;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.action-btn.primary {
		background: #0d6efd;
		color: white;
		border-color: #0d6efd;
	}

	.action-btn.primary:hover {
		background: #0b5ed7;
	}

	.action-btn.secondary {
		background: white;
		color: #6c757d;
	}

	.action-btn.secondary:hover {
		background: #f8f9fa;
		color: #495057;
	}

	.action-btn.success {
		background: #198754;
		color: white;
		border-color: #198754;
	}

	.action-btn.success:hover {
		background: #157347;
	}

	.action-btn.warning {
		background: #ffc107;
		color: #212529;
		border-color: #ffc107;
	}

	.action-btn.warning:hover {
		background: #e0a800;
	}

	.action-btn.danger {
		background: #dc3545;
		color: white;
		border-color: #dc3545;
	}

	.action-btn.danger:hover {
		background: #c82333;
	}

	.content-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 2rem;
	}

	.content-section {
		background: white;
		border: 1px solid #dee2e6;
		border-radius: 8px;
		padding: 1.5rem;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.content-section h2 {
		margin: 0 0 1.5rem 0;
		color: #212529;
		font-size: 1.5rem;
		border-bottom: 2px solid #e9ecef;
		padding-bottom: 0.5rem;
	}

	.config-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 1.5rem;
	}

	.config-item {
		padding: 1rem;
		background: #f8f9fa;
		border-radius: 6px;
		border: 1px solid #e9ecef;
	}

	.config-item .label {
		display: block;
		font-weight: 600;
		color: #212529;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.config-item .value {
		font-size: 1.1rem;
		color: #495057;
		margin-bottom: 0.25rem;
	}

	.config-item .description {
		color: #6c757d;
		font-size: 0.85rem;
		line-height: 1.4;
	}

	.badge {
		padding: 0.25rem 0.5rem;
		border-radius: 12px;
		font-size: 0.8rem;
		font-weight: 500;
	}

	.badge.enabled {
		background: #d1ecf1;
		color: #0c5460;
	}

	.badge.disabled {
		background: #f8d7da;
		color: #721c24;
	}

	.code-block {
		background: #f8f9fa;
		border: 1px solid #e9ecef;
		border-radius: 6px;
		padding: 1rem;
	}

	.code-block pre {
		margin: 0;
		white-space: pre-wrap;
		word-wrap: break-word;
		font-family: 'Monaco', 'Menlo', monospace;
		font-size: 0.9rem;
		line-height: 1.5;
		color: #212529;
	}

	.template-info {
		margin-top: 1.5rem;
	}

	.template-info h3 {
		margin: 0 0 0.75rem 0;
		color: #495057;
		font-size: 1.1rem;
	}

	.placeholders {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.placeholder-tag {
		background: #e9ecef;
		color: #495057;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-family: monospace;
		font-size: 0.85rem;
		font-weight: 500;
	}

	.tool-pipeline {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
		gap: 1rem;
		margin-bottom: 2rem;
	}

	.tool-card {
		background: white;
		border: 1px solid #dee2e6;
		border-radius: 8px;
		padding: 1rem;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
		transition: all 0.2s ease;
	}

	.tool-card:hover {
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
		border-color: #0d6efd;
	}

	.tool-card.disabled {
		opacity: 0.6;
		background: #f8f9fa;
	}

	.tool-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.tool-order {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		background: #0d6efd;
		color: white;
		border-radius: 50%;
		font-weight: bold;
		font-size: 0.9rem;
		flex-shrink: 0;
	}

	.tool-icon {
		font-size: 1.5rem;
		flex-shrink: 0;
	}

	.tool-info h3 {
		margin: 0 0 0.25rem 0;
		color: #212529;
		font-size: 1.1rem;
	}

	.disabled-badge {
		background: #ffc107;
		color: #212529;
		padding: 0.2rem 0.5rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 500;
	}

	.tool-details {
		font-size: 0.9rem;
	}

	.detail-item {
		margin-bottom: 0.75rem;
	}

	.detail-item strong {
		color: #495057;
		margin-right: 0.5rem;
	}

	.detail-item code {
		background: #f1f3f4;
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
		font-family: monospace;
	}

	.tool-config {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid #e9ecef;
	}

	.config-json pre {
		background: #f8f9fa;
		padding: 0.75rem;
		border-radius: 4px;
		margin: 0.5rem 0 0 0;
		font-size: 0.8rem;
		overflow-x: auto;
	}

	.pipeline-flow {
		margin-top: 2rem;
		padding-top: 2rem;
		border-top: 1px solid #e9ecef;
	}

	.pipeline-flow h3 {
		margin: 0 0 1rem 0;
		color: #495057;
		font-size: 1.2rem;
	}

	.flow-diagram {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 1rem;
		padding: 1rem;
		background: #f8f9fa;
		border-radius: 8px;
		overflow-x: auto;
	}

	.flow-step {
		display: flex;
		flex-direction: column;
		align-items: center;
		min-width: 120px;
		padding: 0.75rem;
		background: white;
		border-radius: 6px;
		border: 1px solid #dee2e6;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.flow-step.final {
		background: #d1ecf1;
		border-color: #bee5eb;
	}

	.step-number {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		background: #0d6efd;
		color: white;
		border-radius: 50%;
		font-weight: bold;
		font-size: 0.8rem;
		margin-bottom: 0.5rem;
	}

	.step-name {
		font-weight: 500;
		color: #212529;
		text-align: center;
		font-size: 0.85rem;
		margin-bottom: 0.25rem;
	}

	.step-output {
		font-family: monospace;
		font-size: 0.75rem;
		color: #6c757d;
		background: #f1f3f4;
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
	}

	.flow-arrow {
		font-size: 1.2rem;
		color: #6c757d;
		font-weight: bold;
	}

	.empty-state {
		text-align: center;
		padding: 2rem;
		color: #6c757d;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem;
	}

	.stat-item {
		text-align: center;
		padding: 1rem;
		background: #f8f9fa;
		border-radius: 8px;
		border: 1px solid #e9ecef;
	}

	.stat-value {
		font-size: 2rem;
		font-weight: bold;
		color: #212529;
		margin-bottom: 0.5rem;
		display: block;
	}

	.stat-value.published {
		font-size: 1.5rem;
	}

	.stat-value.draft {
		font-size: 1.5rem;
	}

	.stat-label {
		color: #6c757d;
		font-size: 0.9rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	@media (max-width: 768px) {
		.multi-tool-view {
			padding: 1rem;
		}

		.view-header {
			flex-direction: column;
			align-items: stretch;
			gap: 1rem;
		}

		.action-buttons {
			justify-content: center;
		}

		.assistant-details h1 {
			font-size: 2rem;
		}

		.tool-pipeline {
			grid-template-columns: 1fr;
		}

		.flow-diagram {
			justify-content: center;
		}
	}
</style>