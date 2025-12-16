<script>
	import { _ } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// Props
	let {
		toolConfig = {},
		availableKnowledgeBases = []
	} = $props();

	// Reactive state
	let selectedCollections = $state(toolConfig.config?.collections || []);
	let topK = $state(toolConfig.config?.top_k || 3);

	// Dispatch config changes (called explicitly to avoid infinite loops)
	function notifyConfigChange() {
		const updatedConfig = {
			collections: selectedCollections,
			top_k: topK
		};

		dispatch('configChange', {
			config: updatedConfig
		});
	}

	// Handle collection selection
	function toggleCollection(collectionId) {
		if (selectedCollections.includes(collectionId)) {
			selectedCollections = selectedCollections.filter(id => id !== collectionId);
		} else {
			selectedCollections = [...selectedCollections, collectionId];
		}
		notifyConfigChange();
	}

	// Handle top_k change
	function handleTopKChange(event) {
		const value = parseInt(event.target.value);
		if (value >= 1 && value <= 20) {
			topK = value;
			notifyConfigChange();
		}
	}
</script>

<div class="tool-config-section">
	<h4>{_("Knowledge Base Collections")}</h4>
	<p class="tool-description">
		{_("Select knowledge base collections to query for context.")}
	</p>

	{#if availableKnowledgeBases.length === 0}
		<div class="warning-message">
			⚠️ {_("No knowledge bases available. Create some knowledge bases first.")}
		</div>
	{:else}
		<div class="collections-grid">
			{#each availableKnowledgeBases as kb}
				<label class="collection-checkbox">
					<input
						type="checkbox"
						checked={selectedCollections.includes(kb.id)}
						onchange={() => toggleCollection(kb.id)}
					/>
					<span class="checkmark"></span>
					<div class="collection-info">
						<strong>{kb.name}</strong>
						{#if kb.description}
							<small>{kb.description}</small>
						{/if}
					</div>
				</label>
			{/each}
		</div>
	{/if}

	<div class="config-row">
		<label for="top-k-slider">
			<strong>{_("Results per Collection (top_k)")}: {topK}</strong>
		</label>
		<input
			id="top-k-slider"
			type="range"
			min="1"
			max="20"
			step="1"
			value={topK}
			oninput={(e) => { topK = parseInt(e.target.value); notifyConfigChange(); }}
			class="top-k-slider"
		/>
		<input
			type="number"
			min="1"
			max="20"
			value={topK}
			onchange={handleTopKChange}
			class="top-k-input"
		/>
	</div>

	{#if selectedCollections.length === 0}
		<div class="error-message">
			❌ {_("At least one knowledge base collection must be selected.")}
		</div>
	{/if}
</div>

<style>
	.tool-config-section {
		padding: 1rem;
		background: #f8f9fa;
		border-radius: 8px;
		border: 1px solid #e9ecef;
	}

	.tool-description {
		color: #6c757d;
		margin-bottom: 1rem;
		font-size: 0.9rem;
	}

	.collections-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.collection-checkbox {
		display: flex;
		align-items: flex-start;
		padding: 0.75rem;
		background: white;
		border: 1px solid #dee2e6;
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.collection-checkbox:hover {
		border-color: #0d6efd;
		box-shadow: 0 2px 4px rgba(13, 110, 253, 0.1);
	}

	.collection-checkbox input[type="checkbox"] {
		display: none;
	}

	.checkmark {
		width: 20px;
		height: 20px;
		border: 2px solid #dee2e6;
		border-radius: 4px;
		margin-right: 0.75rem;
		margin-top: 2px;
		position: relative;
		flex-shrink: 0;
	}

	.collection-checkbox input:checked + .checkmark {
		background-color: #0d6efd;
		border-color: #0d6efd;
	}

	.collection-checkbox input:checked + .checkmark::after {
		content: '✓';
		position: absolute;
		color: white;
		font-size: 12px;
		font-weight: bold;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
	}

	.collection-info strong {
		display: block;
		color: #212529;
		margin-bottom: 0.25rem;
	}

	.collection-info small {
		color: #6c757d;
		font-size: 0.8rem;
		line-height: 1.2;
	}

	.config-row {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid #e9ecef;
	}

	.config-row label {
		display: block;
		margin-bottom: 0.75rem;
		color: #212529;
	}

	.top-k-slider {
		width: 100%;
		margin-bottom: 0.5rem;
	}

	.top-k-input {
		width: 80px;
		padding: 0.25rem 0.5rem;
		border: 1px solid #ced4da;
		border-radius: 4px;
		text-align: center;
	}

	.warning-message {
		padding: 0.75rem;
		background: #fff3cd;
		border: 1px solid #ffeaa7;
		border-radius: 4px;
		color: #856404;
		margin-bottom: 1rem;
	}

	.error-message {
		padding: 0.75rem;
		background: #f8d7da;
		border: 1px solid #f5c6cb;
		border-radius: 4px;
		color: #721c24;
		margin-top: 1rem;
	}
</style>