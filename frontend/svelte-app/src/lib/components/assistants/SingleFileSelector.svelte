<!-- src/lib/components/assistants/SingleFileSelector.svelte -->
<script>
	import { _ } from '$lib/i18n';
	import { apiFetch } from '$lib/services/apiClient';

	let {
		userFiles = [],
		selectedFilePath = $bindable(''),
		loading = false,
		error = '',
		formState,
		onFilesChanged
	} = $props();

	let fileUploadLoading = $state(false);
	let fileUploadError = $state('');

	/** @param {Event} event */
	async function handleFileUpload(event) {
		const input = event.target;
		if (
			!input ||
			!(input instanceof HTMLInputElement) ||
			!input.files ||
			input.files.length === 0
		)
			return;
		const file = input.files[0];
		if (!file) return;
		fileUploadLoading = true;
		fileUploadError = '';
		const formData = new FormData();
		formData.append('file', file);
		try {
			const response = await apiFetch('/files/upload', {
				method: 'POST',
				body: formData
			});
			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`API error: ${response.status} - ${errorText || 'Unknown error'}`);
			}
			const data = await response.json();
			await onFilesChanged?.();
			if (data.path) {
				selectedFilePath = data.path;
			}
			input.value = '';
		} catch (err) {
			if (err instanceof Error && err.message.startsWith('Session expired')) return;
			fileUploadError = err instanceof Error ? err.message : 'Failed to upload file';
		} finally {
			fileUploadLoading = false;
		}
	}
</script>

<div>
	<h4 class="block text-sm font-medium text-gray-700 mb-1">
		{$_('assistants.form.singleFile.label', { default: 'Select File' })}
	</h4>
	<div class="mb-4">
		<label for="file-upload" class="block text-sm text-gray-700">{$_('assistants.form.singleFile.upload', { default: 'Upload New File' })}</label>
		<div class="mt-1 flex items-center">
			<input
				id="file-upload"
				type="file"
				accept=".txt,.json,.md,.pdf,.doc,.docx"
				class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-gray-50 file:text-gray-700 hover:file:bg-gray-100 disabled:cursor-not-allowed"
				onchange={handleFileUpload}
				disabled={fileUploadLoading}
			/>
			{#if fileUploadLoading}
				<span class="ml-2 text-sm text-gray-500">{$_('assistants.form.singleFile.uploading', { default: 'Uploading...' })}</span>
			{/if}
		</div>
		{#if fileUploadError}
			<p class="mt-1 text-sm text-red-600">{fileUploadError}</p>
		{/if}
	</div>
	{#if loading}
		<p class="text-sm text-gray-500">{$_('assistants.form.singleFile.loading', { default: 'Loading files...' })}</p>
	{:else if error}
		<p class="text-sm text-red-600">{$_('assistants.form.singleFile.error', { default: 'Error loading files:' })} {error}</p>
	{:else if userFiles.length === 0}
		<p class="text-sm text-gray-500">{$_('assistants.form.singleFile.noneFound', { default: 'No files found. Please upload a file.' })}</p>
	{:else}
		<div class="mt-2 space-y-2 max-h-48 overflow-y-auto border rounded p-2">
			{#each userFiles as file (file.path)}
				<label class="flex items-center space-x-2 p-1 cursor-pointer {selectedFilePath === file.path ? 'bg-blue-50' : 'hover:bg-gray-50'}">
					<input type="radio" name="file-selector" value={file.path} bind:group={selectedFilePath}
						class="h-4 w-4 text-brand rounded focus:ring-brand" />
					<span class="text-sm text-gray-700">{file.name}</span>
				</label>
			{/each}
		</div>
		{#if !selectedFilePath && formState === 'edit'}
			<p class="mt-1 text-xs text-red-500">{$_('assistants.form.singleFile.required', { default: 'Please select a file' })}</p>
		{/if}
	{/if}
</div>
