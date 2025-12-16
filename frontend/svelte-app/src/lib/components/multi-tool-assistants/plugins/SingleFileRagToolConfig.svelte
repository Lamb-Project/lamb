<script>
	import { _ } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// Props
	let {
		toolConfig = {},
		availableFiles = []
	} = $props();

	// Reactive state
	let selectedFilePath = $state(toolConfig.config?.file_path || '');
	let maxChars = $state(toolConfig.config?.max_chars || 50000);

	// Dispatch config changes (called explicitly to avoid infinite loops)
	function notifyConfigChange() {
		const updatedConfig = {
			file_path: selectedFilePath,
			max_chars: maxChars
		};

		dispatch('configChange', {
			config: updatedConfig
		});
	}

	// Get selected file info
	let selectedFile = $derived(availableFiles.find(f => f.path === selectedFilePath));

	// Handle max chars change
	function handleMaxCharsChange(event) {
		const value = parseInt(event.target.value);
		if (value >= 1000 && value <= 100000) {
			maxChars = value;
			notifyConfigChange();
		}
	}
</script>

<div class="tool-config-section">
	<h4>{_("Single File Context")}</h4>
	<p class="tool-description">
		{_("Select a file to include its contents as context for the assistant.")}
	</p>

	<div class="config-row">
		<label for="file-select">
			<strong>{_("Select File")}:</strong>
		</label>
		<select
			id="file-select"
			value={selectedFilePath}
			onchange={(e) => { selectedFilePath = e.target.value; notifyConfigChange(); }}
			class="file-select"
		>
			<option value="">{_("Choose a file...")}</option>
			{#each availableFiles as file}
				<option value={file.path}>
					{file.name} ({(file.size / 1024).toFixed(1)} KB)
				</option>
			{/each}
		</select>
	</div>

	{#if selectedFile}
		<div class="file-preview">
			<h5>{_("Selected File")}</h5>
			<div class="file-info">
				<p><strong>{_("Name")}:</strong> {selectedFile.name}</p>
				<p><strong>{_("Path")}:</strong> {selectedFile.path}</p>
				<p><strong>{_("Size")}:</strong> {(selectedFile.size / 1024).toFixed(1)} KB</p>
				{#if selectedFile.lastModified}
					<p><strong>{_("Last Modified")}:</strong> {new Date(selectedFile.lastModified).toLocaleDateString()}</p>
				{/if}
			</div>
		</div>
	{/if}

	<div class="config-row">
		<label for="max-chars-input">
			<strong>{_("Maximum Characters")}: {maxChars.toLocaleString()}</strong>
		</label>
		<div class="max-chars-controls">
			<input
				id="max-chars-input"
				type="range"
				min="1000"
				max="100000"
				step="1000"
				value={maxChars}
				oninput={(e) => { maxChars = parseInt(e.target.value); notifyConfigChange(); }}
				class="max-chars-slider"
			/>
			<input
				type="number"
				min="1000"
				max="100000"
				step="1000"
				value={maxChars}
				onchange={handleMaxCharsChange}
				class="max-chars-number"
			/>
		</div>
		<small class="help-text">
			{_("Limit the amount of content included from the file to prevent token limits.")}
		</small>
	</div>

	{#if !selectedFilePath}
		<div class="error-message">
			❌ {_("A file must be selected.")}
		</div>
	{/if}

	{#if availableFiles.length === 0}
		<div class="warning-message">
			⚠️ {_("No files available in the public directory. Upload some files first.")}
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

	.file-select {
		width: 100%;
		padding: 0.5rem;
		border: 1px solid #ced4da;
		border-radius: 4px;
		background: white;
		font-size: 0.9rem;
	}

	.file-preview {
		background: white;
		border: 1px solid #e9ecef;
		border-radius: 6px;
		padding: 1rem;
		margin: 1rem 0;
	}

	.file-preview h5 {
		margin: 0 0 0.75rem 0;
		color: #495057;
		font-size: 1rem;
	}

	.file-info p {
		margin: 0.5rem 0;
		font-size: 0.9rem;
	}

	.max-chars-controls {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.max-chars-slider {
		flex: 1;
	}

	.max-chars-number {
		width: 100px;
		padding: 0.25rem 0.5rem;
		border: 1px solid #ced4da;
		border-radius: 4px;
		text-align: center;
	}

	.help-text {
		color: #6c757d;
		font-size: 0.8rem;
		display: block;
		margin-top: 0.25rem;
	}

	.error-message {
		padding: 0.75rem;
		background: #f8d7da;
		border: 1px solid #f5c6cb;
		border-radius: 4px;
		color: #721c24;
		margin-top: 1rem;
	}

	.warning-message {
		padding: 0.75rem;
		background: #fff3cd;
		border: 1px solid #ffeaa7;
		border-radius: 4px;
		color: #856404;
		margin-top: 1rem;
	}
</style>