<script>
	import { _ } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// Props
	let {
		toolConfig = {},
		availableRubrics = []
	} = $props();

	// Reactive state
	let selectedRubricId = $state(toolConfig.config?.rubric_id || null);
	let format = $state(toolConfig.config?.format || 'markdown');

	// Dispatch config changes (called explicitly to avoid infinite loops)
	function notifyConfigChange() {
		const updatedConfig = {
			rubric_id: selectedRubricId,
			format: format
		};

		dispatch('configChange', {
			config: updatedConfig
		});
	}

	// Get selected rubric info
	let selectedRubric = $derived(availableRubrics.find(r => r.id === selectedRubricId));
</script>

<div class="tool-config-section">
	<h4>{_("Assessment Rubric")}</h4>
	<p class="tool-description">
		{_("Select a rubric to include in the assistant's context for assessment tasks.")}
	</p>

	<div class="config-row">
		<label for="rubric-select">
			<strong>{_("Select Rubric")}:</strong>
		</label>
		<select
			id="rubric-select"
			value={selectedRubricId}
			onchange={(e) => { selectedRubricId = e.target.value; notifyConfigChange(); }}
			class="rubric-select"
		>
			<option value={null}>{_("Choose a rubric...")}</option>
			{#each availableRubrics as rubric}
				<option value={rubric.id}>
					{rubric.title} - {rubric.description ? rubric.description.substring(0, 50) + '...' : ''}
				</option>
			{/each}
		</select>
	</div>

	{#if selectedRubric}
		<div class="rubric-preview">
			<h5>{_("Selected Rubric")}</h5>
			<div class="rubric-info">
				<p><strong>{_("Title")}:</strong> {selectedRubric.title}</p>
				{#if selectedRubric.description}
					<p><strong>{_("Description")}:</strong> {selectedRubric.description}</p>
				{/if}
			</div>
		</div>
	{/if}

	<div class="config-row">
		<div class="label">
			<strong>{_("Output Format")}:</strong>
		</div>
		<div class="format-options">
			<label class="format-option">
				<input
					type="radio"
					checked={format === 'markdown'}
					onchange={() => { format = 'markdown'; notifyConfigChange(); }}
					value="markdown"
				/>
				<span class="radio-checkmark"></span>
				{_("Markdown")}
			</label>
			<label class="format-option">
				<input
					type="radio"
					checked={format === 'json'}
					onchange={() => { format = 'json'; notifyConfigChange(); }}
					value="json"
				/>
				<span class="radio-checkmark"></span>
				{_("JSON")}
			</label>
		</div>
	</div>

	{#if !selectedRubricId}
		<div class="error-message">
			❌ {_("A rubric must be selected.")}
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

	.config-row {
		margin-bottom: 1.5rem;
	}

	.config-row label {
		display: block;
		margin-bottom: 0.5rem;
		color: #212529;
		font-weight: 600;
	}

	.rubric-select {
		width: 100%;
		padding: 0.5rem;
		border: 1px solid #ced4da;
		border-radius: 4px;
		background: white;
		font-size: 0.9rem;
	}

	.rubric-preview {
		background: white;
		border: 1px solid #e9ecef;
		border-radius: 6px;
		padding: 1rem;
		margin: 1rem 0;
	}

	.rubric-preview h5 {
		margin: 0 0 0.75rem 0;
		color: #495057;
		font-size: 1rem;
	}

	.rubric-info p {
		margin: 0.5rem 0;
		font-size: 0.9rem;
	}

	.format-options {
		display: flex;
		gap: 1rem;
	}

	.format-option {
		display: flex;
		align-items: center;
		cursor: pointer;
		font-weight: normal;
	}

	.format-option input[type="radio"] {
		display: none;
	}

	.radio-checkmark {
		width: 16px;
		height: 16px;
		border: 2px solid #dee2e6;
		border-radius: 50%;
		margin-right: 0.5rem;
		position: relative;
		flex-shrink: 0;
	}

	.format-option input:checked + .radio-checkmark {
		border-color: #0d6efd;
	}

	.format-option input:checked + .radio-checkmark::after {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		width: 6px;
		height: 6px;
		background: #0d6efd;
		border-radius: 50%;
		transform: translate(-50%, -50%);
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