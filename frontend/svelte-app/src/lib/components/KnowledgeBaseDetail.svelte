<script>
// @ts-nocheck
	import { onMount } from 'svelte';
	import {
		getKnowledgeBaseDetails,
		getIngestionPlugins,
		uploadFileWithPlugin,
		deleteFileFromKnowledgeBase
	} from '$lib/services/knowledgeBaseService';
	import { _ } from '$lib/i18n';
	import { page } from '$app/stores';
	import axios from 'axios'; // Import axios
	import { getApiUrl } from '$lib/config'; // Import getApiUrl
	import { browser } from '$app/environment'; // Import browser

	/**
	 * @typedef {import('$lib/services/knowledgeBaseService').IngestionPlugin} IngestionPlugin
	 * @typedef {import('$lib/services/knowledgeBaseService').IngestionParameterDetail} IngestionParameterDetail
	 * @typedef {Object} KnowledgeBaseFile
	 * @property {string} id
	 * @property {string} filename
	 * @property {number} [size]
	 * @property {string} [content_type]
	 * @property {number} [created_at] // Assuming this might come from backend eventually
	 * @property {string} [file_url] // Add the file_url property
	 */

	/**
	 * @typedef {Object} QueryResultMetadata
	 * @property {number} [chunk_count]
	 * @property {number} [chunk_index]
	 * @property {number} [chunk_overlap]
	 * @property {number} [chunk_size]
	 * @property {string} [chunk_unit]
	 * @property {string} [chunking_strategy]
	 * @property {string} document_id
	 * @property {string} [embedding_model]
	 * @property {string} [embedding_vendor]
	 * @property {string} [extension]
	 * @property {number} [file_size]
	 * @property {string} [file_url]
	 * @property {string} filename
	 * @property {string} [ingestion_timestamp]
	 * @property {string} [source]
	 */

	/**
	 * @typedef {Object} QueryResultItem
	 * @property {number} similarity
	 * @property {string} data
	 * @property {QueryResultMetadata} metadata
	 */

	/**
	 * @typedef {Object} QueryApiResponse
	 * @property {QueryResultItem[]} results
	 * @property {string} status
	 * @property {string} kb_id
	 * @property {string} query
	 * @property {object} [debug_info]
	 */

	// Component props (using Svelte 5 runes syntax)
	let { kbId = /** @type {string} */ ('') } = $props();

	// Component state (using Svelte 5 runes syntax)
	/** @type {any} */
	let kb = $state(null);
	let loading = $state(true);
	let error = $state('');
	let serverOffline = $state(false);

	// Ingestion state
	/** @type {'files' | 'ingest' | 'query'} */
	let activeTab = $state('files'); // New state for tabs: 'files' or 'ingest' or 'query'
	/** @type {IngestionPlugin[]} */
	let plugins = $state([]);
	let loadingPlugins = $state(false);
	let pluginsError = $state('');
	/** @type {IngestionPlugin | null} */
	let selectedPlugin = $state(null);
	let selectedPluginIndex = $state(0);
	/** @type {Record<string, any>} */
	let pluginParams = $state({});
	/** @type {File | null} */
	let selectedFile = $state(null);
	let uploading = $state(false);
	let uploadError = $state('');
	let uploadSuccess = $state(false);

	// File delete state
	let deletingFileId = $state('');
	let deleteError = $state('');
	let deleteSuccess = $state(false);

	let previousKbId = ''; // Track previous kbId

	// State for query tab
	let queryText = $state('');
	/** @type {QueryApiResponse | null} */
	let queryResult = $state(null);
	let queryLoading = $state(false);
	let queryError = $state('');

	// Initialization and cleanup
	onMount(() => {
		console.log('KnowledgeBaseDetail mounted, kbId:', kbId);
		previousKbId = kbId; // Initialize previousKbId
		return () => {
			console.log('KnowledgeBaseDetail unmounted');
		};
	});

	// Load knowledge base details only when kbId actually changes or initially
	$effect(() => {
		console.log('Effect running. kbId:', kbId, 'previousKbId:', previousKbId, 'kb:', kb !== null);
		if (kbId && (kbId !== previousKbId || kb === null)) {
			console.log('Condition met: Loading knowledge base for kbId:', kbId);
			loadKnowledgeBase(kbId);
			previousKbId = kbId; // Update previousKbId after initiating load
		} else {
			console.log('Condition not met: Skipping loadKnowledgeBase.');
			// If kbId becomes empty (e.g., navigating back), reset kb state
			if (!kbId && kb !== null) {
				console.log('kbId is empty, resetting kb state.');
				kb = null;
				previousKbId = '';
			}
			// Update previousKbId if kbId changed but we skipped loading (e.g., kbId becomes null)
			if (kbId !== previousKbId) {
				previousKbId = kbId;
			}
		}
	});

	/**
	 * Function to change active tab
	 * @param {'files' | 'ingest' | 'query'} tabName - The name of the tab to select
	 */
	function selectTab(tabName) {
		console.log('Selecting tab:', tabName);
		activeTab = tabName;
		if (tabName === 'ingest' && plugins.length === 0 && !loadingPlugins) {
			console.log('Ingest tab selected, fetching plugins.');
			fetchPlugins();
		}
		// Reset upload status when switching tabs
		uploadError = '';
		uploadSuccess = false;
		// Optionally reset file input when switching away from ingest tab
		if (tabName !== 'ingest') {
			selectedFile = null;
			resetFileInput();
		}
		// Reset query state when switching tabs
		queryText = '';
		queryResult = null;
		queryError = '';
		queryLoading = false;
	}

	function resetFileInput() {
		/** @type {HTMLInputElement | null} */
		const fileInput = document.querySelector('#file-upload-input-inline');
		if (fileInput) {
			fileInput.value = '';
		}
	}

	/**
	 * Load knowledge base details
	 * @param {string} id - Knowledge base ID
	 */
	async function loadKnowledgeBase(id) {
		// Keep loading state related to the main KB details
		// If not already loading, set loading = true ? Maybe not, only for initial load.
		if (!kb) loading = true;
		error = '';
		serverOffline = false; // Assume server is online unless KB detail fetch fails

		try {
			const data = await getKnowledgeBaseDetails(id);
			kb = data;
			console.log('Knowledge base details loaded:', kb);
			// Debug: log the full files array
			if (kb && kb.files) {
				console.log('Knowledge base files array:', kb.files);
			} else {
				console.log('No files found in knowledge base details.');
			}
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading knowledge base details:', err);
			error = err instanceof Error ? err.message : 'Failed to load knowledge base details';
			if (err instanceof Error && err.message.includes('server offline')) {
				serverOffline = true;
			}
		} finally {
			loading = false;
		}
	}

	/**
	 * Format file size to readable format
	 * @param {number} bytes - File size in bytes
	 * @returns {string} Formatted file size
	 */
	function formatFileSize(bytes) {
		if (bytes === undefined || bytes === null) return 'N/A';

		const units = ['B', 'KB', 'MB', 'GB'];
		let size = bytes;
		let unitIndex = 0;

		while (size >= 1024 && unitIndex < units.length - 1) {
			size /= 1024;
			unitIndex++;
		}

		return `${size.toFixed(1)} ${units[unitIndex]}`;
	}

	/**
	 * Handle file delete
	 * @param {string} fileId - ID of the file to delete
	 */
	async function handleDeleteFile(fileId) {
		// Find the file to get its name for confirmation
		const file = kb.files?.find((f) => f.id === fileId);
		const fileName = file?.filename || 'this file';

		// Debug: log the file object and fileId
		console.log('Attempting to delete file:', file);
		console.log('File ID being sent for deletion:', fileId);
		console.log('Available files in KB:', kb.files);
		console.log('KB ID:', kbId);

		const confirmed = confirm(
			$_('knowledgeBases.detail.deleteConfirmation', {
				values: { fileName },
				default: `Are you sure you want to delete "${fileName}"? This action cannot be undone.`
			})
		);

		if (!confirmed) return;

		console.log(`Delete file requested: ${fileId}`);
		deletingFileId = fileId;
		deleteError = '';
		deleteSuccess = false;

		try {
			await deleteFileFromKnowledgeBase(kbId, fileId);
			console.log('File deleted successfully');

			// Remove file from local state so UI updates immediately
			if (kb.files) kb.files = kb.files.filter((f) => f.id !== fileId);

			deleteSuccess = true;
			setTimeout(() => (deleteSuccess = false), 5000);
		} catch (/** @type {unknown} */ err) {
			console.error('Error deleting file:', err);
			deleteError = err instanceof Error ? err.message : 'Failed to delete file';
		} finally {
			deletingFileId = '';
		}
	}

	// --- Ingestion Functions (Moved from Modal) ---

	/**
	 * Fetches available ingestion plugins
	 */
	async function fetchPlugins() {
		loadingPlugins = true;
		pluginsError = '';
		// Assume server is online unless plugin fetch fails with specific error
		// serverOffline = false;

		try {
			plugins = await getIngestionPlugins();
			console.log('Fetched plugins:', plugins);

			// Select the first plugin by default if available
			if (plugins.length > 0) {
				selectPlugin(0);
			}
		} catch (/** @type {unknown} */ err) {
			console.error('Error fetching plugins:', err);
			pluginsError = err instanceof Error ? err.message : 'Failed to load ingestion plugins';
			if (err instanceof Error && err.message.includes('server offline')) {
				serverOffline = true; // Set server offline if plugin fetch confirms it
			}
		} finally {
			loadingPlugins = false;
		}
	}

	/**
	 * Selects a plugin and initializes its parameters
	 * @param {number} index - The index of the plugin to select
	 */
	function selectPlugin(index) {
		if (index >= 0 && index < plugins.length) {
			selectedPluginIndex = index;
			selectedPlugin = plugins[index];

			// Initialize parameters with defaults from the parameters object
			pluginParams = {};
			if (selectedPlugin && selectedPlugin.parameters) {
				// Iterate over the parameters object
				for (const paramName in selectedPlugin.parameters) {
					pluginParams[paramName] = selectedPlugin.parameters[paramName].default;
				}
			}
			console.log('Selected plugin:', selectedPlugin?.name, 'with params:', pluginParams);
		}
	}

	/**
	 * Handles file selection
	 * @param {Event} event - The file input change event
	 */
	function handleFileSelect(/** @type {Event} */ event) {
		/** @type {HTMLInputElement} */
		const input = /** @type {HTMLInputElement} */ (event.target);

		if (input.files && input.files.length > 0) {
			selectedFile = input.files[0];
			uploadSuccess = false; // Reset success message on new file selection
			uploadError = '';
			console.log('Selected file:', selectedFile.name, selectedFile.type, selectedFile.size);
		} else {
			selectedFile = null;
		}
	}

	/**
	 * Updates a plugin parameter value
	 * @param {string} paramName - The name of the parameter to update
	 * @param {Event} event - The input change event
	 */
	function updateParamValue(paramName, /** @type {Event} */ event) {
		const input = /** @type {HTMLInputElement} */ (event.target);
		// Find the parameter definition using the key in the parameters object
		const paramDef = selectedPlugin?.parameters?.[paramName];

		if (paramDef) {
			if (paramDef.type === 'integer' || paramDef.type === 'number') {
				pluginParams[paramName] = input.value ? Number(input.value) : paramDef.default;
			} else if (paramDef.type === 'boolean') {
				pluginParams[paramName] = input.checked;
			} else {
				pluginParams[paramName] = input.value;
			}
			console.log(`Updated param ${paramName} to:`, pluginParams[paramName]);
		}
	}

	/**
	 * Uploads the selected file with the selected plugin
	 */
	async function uploadFile() {
		console.log(
			'uploadFile called, selectedFile:',
			selectedFile?.name,
			'selectedPlugin:',
			selectedPlugin?.name
		);

		if (!selectedFile || !selectedPlugin) {
			uploadError = 'Please select a file and plugin.';
			console.warn('Upload aborted: missing file or plugin');
			return;
		}

		uploading = true;
		uploadError = '';
		uploadSuccess = false;

		console.log('Upload parameters:', {
			kbId,
			fileName: selectedFile.name,
			fileSize: selectedFile.size,
			fileType: selectedFile.type,
			pluginName: selectedPlugin.name,
			pluginParams
		});

		try {
			const result = await uploadFileWithPlugin(
				kbId,
				selectedFile,
				selectedPlugin.name,
				pluginParams
			);
			console.log('Upload result:', result);
			uploadSuccess = true;
			selectedFile = null;
			resetFileInput();
			// Reload the KB details to show the new file in the list
			await loadKnowledgeBase(kbId);
			// Optionally hide the ingestion box after success
			// showIngestionBox = false;
		} catch (/** @type {unknown} */ err) {
			console.error('Error uploading file:', err);
			uploadError = err instanceof Error ? err.message : 'Failed to upload file';
			if (err instanceof Error && err.message.includes('server offline')) {
				serverOffline = true;
			}
		} finally {
			uploading = false;
		}
	}

	/**
	 * Handle successful file upload (placeholder if needed, main logic moved to uploadFile)
	 */
	function handleFileUploaded() {
		console.log('File uploaded event potentially received (now handled in uploadFile)');
		// loadKnowledgeBase(kbId); // Reload is now done in uploadFile
	}

	// --- Query Function ---
	async function handleQuerySubmit() {
		if (!queryText.trim() || !kbId) return; // Basic validation

		if (!browser) {
			queryError = 'Querying is only available in the browser.';
			return;
		}

		const token = localStorage.getItem('userToken');
		if (!token) {
			queryError = 'User not authenticated. Please log in.';
			// Optionally, redirect to login or show a more prominent message
			return;
		}

		queryLoading = true;
		queryError = '';
		queryResult = null;

		try {
			const apiUrl = getApiUrl(`/knowledgebases/kb/${kbId}/query`);
			const requestBody = {
				query_text: queryText,
				plugin_name: 'simple_query', // Hardcoded as requested
				plugin_params: {
					top_k: 3, // Hardcoded default
					threshold: 0 // Changed from 0.7 to 0
				}
			};

			console.log('Sending query request:', { url: apiUrl, body: requestBody });

			const response = await axios.post(apiUrl, requestBody, {
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${token}` // Add Authorization header
				},
				withCredentials: true // Assuming session cookies are needed
			});

			console.log('Query response received:', response.data);

			// Process results: remove source field from metadata for security
			const processedResults =
				response.data.results?.map((/** @type {QueryResultItem} */ result) => {
					const { source, ...metadataWithoutSource } = result.metadata || {};
					return {
						...result,
						metadata: metadataWithoutSource
					};
				}) || [];

			// Store the processed response data (with source removed from metadata)
			queryResult = {
				...response.data,
				results: processedResults
			};
		} catch (/** @type {unknown} */ err) {
			console.error('Error performing query:', err);
			// Assuming err is AxiosError
			const axiosError = /** @type {import('axios').AxiosError} */ (err);
			queryError =
				axiosError.response?.data?.detail ||
				(axiosError instanceof Error
					? axiosError.message
					: 'An unknown error occurred during query.');
			// Check for server offline based on status or specific message if available
			if (
				axiosError.response?.status === 503 ||
				(axiosError instanceof Error && axiosError.message.includes('server offline'))
			) {
				serverOffline = true; // Set server offline flag if query fails due to it
			}
		} finally {
			queryLoading = false;
		}
	}
</script>

<div class="overflow-hidden bg-white shadow sm:rounded-lg">
	<!-- Loading state -->
	{#if loading}
		<div class="p-6 text-center">
			<div class="animate-pulse text-gray-500">
				{$_('knowledgeBases.detail.loading', { default: 'Loading knowledge base details...' })}
			</div>
		</div>

		<!-- Error state -->
	{:else if error && !kb}
		<div class="p-6 text-center">
			<div class="text-red-500">
				{#if serverOffline}
					<div>
						<p class="mb-2 font-bold">
							{$_('knowledgeBases.detail.serverOffline', {
								default: 'Knowledge Base Server Offline'
							})}
						</p>
						<p>
							{$_('knowledgeBases.detail.tryAgainLater', {
								default: 'Please try again later or contact an administrator.'
							})}
						</p>
					</div>
				{:else}
					{error}
				{/if}
			</div>
			<button
				onclick={() => loadKnowledgeBase(kbId)}
				class="mt-4 inline-flex items-center rounded-md border border-transparent bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
				style="background-color: #2271b3;"
			>
				{$_('knowledgeBases.detail.retry', { default: 'Retry' })}
			</button>
		</div>

		<!-- Success state with KB details -->
	{:else if kb}
		<div>
			<!-- Header section -->
			<div class="border-b border-gray-200 px-4 py-5 sm:px-6">
				<h3 class="text-lg leading-6 font-medium text-gray-900">
					{kb.name}
				</h3>
				<p class="mt-1 max-w-2xl text-sm text-gray-500">
					{kb.description ||
						$_('knowledgeBases.detail.noDescription', { default: 'No description provided.' })}
				</p>
			</div>

			<!-- Knowledge base metadata section -->
			<div class="border-b border-gray-200">
				<dl>
					<div class="bg-gray-50 px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
						<dt class="text-sm font-medium text-gray-500">
							{$_('knowledgeBases.detail.idLabel', { default: 'ID' })}
						</dt>
						<dd class="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
							{kb.id}
						</dd>
					</div>

					{#if kb.owner}
						<div class="bg-white px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
							<dt class="text-sm font-medium text-gray-500">
								{$_('knowledgeBases.detail.ownerLabel', { default: 'Owner' })}
							</dt>
							<dd class="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
								{kb.owner}
							</dd>
						</div>
					{/if}

					{#if kb.created_at}
						<div class="bg-gray-50 px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
							<dt class="text-sm font-medium text-gray-500">
								{$_('knowledgeBases.detail.createdLabel', { default: 'Created' })}
							</dt>
							<dd class="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
								{new Date(kb.created_at * 1000).toLocaleString()}
							</dd>
						</div>
					{/if}

					{#if kb.metadata?.access_control}
						<div class="bg-white px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
							<dt class="text-sm font-medium text-gray-500">
								{$_('knowledgeBases.detail.accessLabel', { default: 'Access Control' })}
							</dt>
							<dd class="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
								<span
									class="inline-flex rounded-full px-2 text-xs leading-5 font-semibold {kb.metadata
										.access_control === 'private'
										? 'bg-yellow-100 text-yellow-800'
										: 'bg-green-100 text-green-800'}"
								>
									{kb.metadata.access_control}
								</span>
							</dd>
						</div>
					{/if}
				</dl>
			</div>

			<!-- Files / Ingestion Section with Tabs -->
			<div class="border-t border-gray-200">
				<!-- Tab List -->
				<div class="border-b border-gray-200">
					<nav class="-mb-px flex space-x-8 px-4 sm:px-6" aria-label="Tabs">
						<!-- Files Tab -->
						<button
							type="button"
							onclick={() => selectTab('files')}
							class="border-b-2 px-1 py-4 text-sm font-medium whitespace-nowrap {activeTab ===
							'files'
								? 'border-[#2271b3] text-[#2271b3]'
								: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
							style={activeTab === 'files' ? 'border-color: #2271b3; color: #2271b3;' : ''}
							aria-current={activeTab === 'files' ? 'page' : undefined}
						>
							{$_('knowledgeBases.detail.filesTab', { default: 'Files' })}
						</button>

						<!-- Ingest Content Tab -->
						<button
							type="button"
							onclick={() => selectTab('ingest')}
							class="border-b-2 px-1 py-4 text-sm font-medium whitespace-nowrap {activeTab ===
							'ingest'
								? 'border-[#2271b3] text-[#2271b3]'
								: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
							style={activeTab === 'ingest' ? 'border-color: #2271b3; color: #2271b3;' : ''}
							aria-current={activeTab === 'ingest' ? 'page' : undefined}
						>
							{$_('knowledgeBases.detail.ingestTab', { default: 'Ingest Content' })}
						</button>

						<!-- Query Tab -->
						<button
							onclick={() => selectTab('query')}
							class="{activeTab === 'query'
								? 'border-brand text-brand'
								: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} border-b-2 px-1 py-4 text-sm font-medium whitespace-nowrap"
							style={activeTab === 'query' ? 'border-color: #2271b3; color: #2271b3;' : ''}
							aria-current={activeTab === 'query' ? 'page' : undefined}
						>
							{$_('knowledgeBases.detail.tabs.query', { default: 'Query' })}
						</button>
					</nav>
				</div>

				<!-- Tab Panels -->
				<div class="px-4 py-5 sm:px-6">
					<!-- Files Panel -->
					{#if activeTab === 'files'}
						<div>
							{#if deleteSuccess}
								<div class="mb-4 rounded border border-green-100 bg-green-50 p-4">
									<div class="text-sm text-green-700">
										{$_('knowledgeBases.detail.fileDeleteSuccess', {
											default: 'File deleted successfully!'
										})}
									</div>
								</div>
							{/if}
							{#if deleteError}
								<div class="mb-4 rounded border border-red-100 bg-red-50 p-4">
									<div class="text-sm text-red-700">{deleteError}</div>
								</div>
							{/if}
							{#if kb.files && kb.files.length > 0}
								<div class="overflow-x-auto">
									<table class="min-w-full divide-y divide-gray-200">
										<thead class="bg-gray-50">
											<tr>
												<th
													scope="col"
													class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
												>
													{$_('knowledgeBases.detail.fileNameColumn', { default: 'File Name' })}
												</th>
												<th
													scope="col"
													class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
												>
													{$_('knowledgeBases.detail.fileSizeColumn', { default: 'Size' })}
												</th>
												<th
													scope="col"
													class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase"
												>
													{$_('knowledgeBases.detail.fileTypeColumn', { default: 'Type' })}
												</th>
												<th
													scope="col"
													class="px-6 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase"
												>
													{$_('knowledgeBases.detail.fileActionsColumn', { default: 'Actions' })}
												</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-gray-200 bg-white">
											{#each kb.files as file (file.id)}
												<tr>
													<td class="px-6 py-4 whitespace-nowrap">
														<div class="flex items-center">
															<div class="text-sm font-medium text-gray-900">
																{#if file.file_url}
																	<a
																		href={file.file_url}
																		target="_blank"
																		rel="noopener noreferrer"
																		class="text-[#2271b3] hover:text-[#195a91] hover:underline"
																		style="color: #2271b3;"
																	>
																		{file.filename}
																	</a>
																{:else}
																	<span>{file.filename}</span>
																{/if}
															</div>
														</div>
													</td>
													<td class="px-6 py-4 whitespace-nowrap">
														<div class="text-sm text-gray-900">
															{file.size ? formatFileSize(file.size) : 'N/A'}
														</div>
													</td>
													<td class="px-6 py-4 whitespace-nowrap">
														<div class="text-sm text-gray-900">
															{file.content_type || 'Unknown'}
														</div>
													</td>
													<td class="px-6 py-4 text-right text-sm font-medium whitespace-nowrap">
														<button
															onclick={() => handleDeleteFile(file.id)}
															class="text-red-600 hover:text-red-900 disabled:cursor-not-allowed disabled:opacity-50"
															disabled={deletingFileId === file.id}
														>
															{#if deletingFileId === file.id}
																<svg
																	class="mr-1 inline h-4 w-4 animate-spin"
																	xmlns="http://www.w3.org/2000/svg"
																	fill="none"
																	viewBox="0 0 24 24"
																>
																	<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
																	<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
																</svg>
																{$_('knowledgeBases.detail.fileDeleting', { default: 'Deleting...' })}
															{:else}
																{$_('knowledgeBases.detail.fileDeleteButton', { default: 'Delete' })}
															{/if}
														</button>
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{:else}
								<div class="py-4 text-center text-gray-500">
									{$_('knowledgeBases.detail.noFiles', {
										default: 'No files have been uploaded to this knowledge base.'
									})}
								</div>
							{/if}
						</div>
					{/if}

					<!-- Ingest Content Panel -->
					{#if activeTab === 'ingest'}
						<div class="-mx-4 -my-5 bg-gray-50 px-4 py-5 sm:-mx-6 sm:px-6">
							<h4 class="text-md mb-4 font-medium text-gray-700">
								{$_('knowledgeBases.fileUpload.sectionTitle', {
									default: 'Upload and Ingest New File'
								})}
							</h4>

							{#if loadingPlugins}
								<!-- ... plugin loading indicator ... -->
							{:else if pluginsError}
								<!-- ... plugin error display ... -->
							{:else if plugins.length === 0}
								<!-- ... no plugins message ... -->
							{:else}
								<!-- Ingestion Form -->
								<form
									onsubmit={(e) => {
										e.preventDefault();
										uploadFile();
									}}
									class="space-y-6"
								>
									<!-- Success message -->
									{#if uploadSuccess}
										<div class="rounded border border-green-100 bg-green-50 p-4">
											<div class="text-sm text-green-700">
												{$_('knowledgeBases.fileUpload.success', {
													default: 'File uploaded and ingestion started successfully!'
												})}
											</div>
										</div>
									{/if}

									<!-- Error message -->
									{#if uploadError}
										<div class="rounded border border-red-100 bg-red-50 p-4">
											<div class="text-sm text-red-700">
												{uploadError}
											</div>
										</div>
									{/if}

									<!-- File selection -->
									<div>
										<label
											for="file-upload-input-inline"
											class="block text-sm font-medium text-gray-700"
										>
											{$_('knowledgeBases.fileUpload.fileLabel', { default: 'Select File' })}
										</label>
										<div class="mt-1 flex items-center">
											<input
												id="file-upload-input-inline"
												type="file"
												class="block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-[#2271b3] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-[#195a91]"
												style="file:background-color: #2271b3;"
												onchange={handleFileSelect}
											/>
										</div>
										{#if selectedFile}
											<p class="mt-2 text-sm text-gray-500">
												{selectedFile.name} ({formatFileSize(selectedFile.size)})
											</p>
										{/if}
									</div>

									<!-- Plugin selection -->
									<div>
										<label
											for="plugin-select-inline"
											class="block text-sm font-medium text-gray-700"
										>
											{$_('knowledgeBases.fileUpload.pluginLabel', { default: 'Ingestion Plugin' })}
										</label>
										<div class="mt-1">
											<select
												id="plugin-select-inline"
												class="block w-full rounded-md border-gray-300 py-2 pr-10 pl-3 text-base focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none sm:text-sm"
												onchange={(/** @type {Event} */ e) => {
													const select = /** @type {HTMLSelectElement} */ (e.target);
													if (select && select.value) {
														selectPlugin(parseInt(select.value));
													}
												}}
											>
												{#each plugins as plugin, i}
													<option value={i} selected={i === selectedPluginIndex}>
														{plugin.name} - {plugin.description}
													</option>
												{/each}
											</select>
										</div>
									</div>

									<!-- Plugin parameters -->
									{#if selectedPlugin && selectedPlugin.parameters && Object.keys(selectedPlugin.parameters).length > 0}
										<div class="space-y-4 border-t border-gray-200 pt-4">
											<h5 class="font-medium text-gray-700">
												{$_('knowledgeBases.fileUpload.parametersLabel', {
													default: 'Plugin Parameters'
												})}
											</h5>

											{#each Object.entries(selectedPlugin.parameters) as [paramName, paramDef] (paramName)}
												<div>
													<label
														for={`param-${paramName}-inline`}
														class="block text-sm font-medium text-gray-700"
													>
														{paramName}
														{paramDef.required ? ' *' : ''}
														{#if paramDef.description}
															<span class="ml-1 text-xs text-gray-500"
																>({paramDef.description})</span
															>
														{/if}
													</label>
													<div class="mt-1">
														{#if paramDef.enum && Array.isArray(paramDef.enum)}
															<!-- Render as select dropdown if enum is present -->
															<select
																id={`param-${paramName}-inline`}
																class="block w-full rounded-md border-gray-300 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] sm:text-sm"
																value={pluginParams[paramName]}
																onchange={(e) => updateParamValue(paramName, e)}
															>
																{#each paramDef.enum as enumValue}
																	<option
																		value={enumValue}
																		selected={pluginParams[paramName] === enumValue}
																	>
																		{enumValue}
																	</option>
																{/each}
															</select>
														{:else if paramDef.type === 'boolean'}
															<!-- Render as checkbox -->
															<div class="flex items-center">
																<input
																	id={`param-${paramName}-inline`}
																	type="checkbox"
																	class="h-4 w-4 rounded border-gray-300 text-[#2271b3] focus:ring-[#2271b3]"
																	checked={pluginParams[paramName] === true}
																	onchange={(e) => updateParamValue(paramName, e)}
																/>
																<label
																	for={`param-${paramName}-inline`}
																	class="ml-2 block text-sm text-gray-900"
																>
																	{paramDef.default ? 'Enabled' : 'Disabled'} by default
																</label>
															</div>
														{:else if paramDef.type === 'integer' || paramDef.type === 'number'}
															<!-- Render as number input -->
															<input
																id={`param-${paramName}-inline`}
																type="number"
																class="block w-full rounded-md border-gray-300 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] sm:text-sm"
																value={pluginParams[paramName]}
																placeholder={paramDef.default !== undefined &&
																paramDef.default !== null
																	? paramDef.default.toString()
																	: ''}
																onchange={(e) => updateParamValue(paramName, e)}
															/>
														{:else if paramDef.type === 'array'}
															<!-- Render as textarea for arrays (e.g., URLs) -->
															<textarea
																id={`param-${paramName}-inline`}
																rows="3"
																class="block w-full rounded-md border-gray-300 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] sm:text-sm"
																value={Array.isArray(pluginParams[paramName])
																	? pluginParams[paramName].join('\n')
																	: pluginParams[paramName] || ''}
																placeholder={paramDef.description || 'Enter values, one per line'}
																onchange={(e) => updateParamValue(paramName, e)}
															></textarea>
															<p class="mt-1 text-xs text-gray-500">
																Enter values separated by new lines.
															</p>
														{:else}
															<!-- Render as text input for other types (string, etc.) -->
															<input
																id={`param-${paramName}-inline`}
																type="text"
																class="block w-full rounded-md border-gray-300 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] sm:text-sm"
																value={pluginParams[paramName]}
																placeholder={paramDef.default !== undefined &&
																paramDef.default !== null
																	? paramDef.default.toString()
																	: ''}
																onchange={(e) => updateParamValue(paramName, e)}
															/>
														{/if}
													</div>
												</div>
											{/each}
										</div>
									{/if}

									<!-- Submit Button -->
									<div class="flex justify-end pt-4">
										<button
											type="submit"
											class="inline-flex items-center rounded-md border border-transparent bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none"
											style="background-color: #2271b3;"
											disabled={!selectedFile || !selectedPlugin || uploading}
										>
											{#if uploading}
												<!-- ... uploading indicator ... -->
												{$_('knowledgeBases.fileUpload.uploadingButton', {
													default: 'Uploading...'
												})}
											{:else}
												{$_('knowledgeBases.fileUpload.uploadButton', { default: 'Upload File' })}
											{/if}
										</button>
									</div>
								</form>
							{/if}
						</div>
					{/if}

					<!-- Query Tab Content -->
					{#if activeTab === 'query'}
						<div class="space-y-4">
							<h3 class="text-lg leading-6 font-medium text-gray-900">
								{$_('knowledgeBases.detail.query.title', { default: 'Query Knowledge Base' })}
							</h3>

							<form
								onsubmit={(e) => {
									e.preventDefault();
									handleQuerySubmit();
								}}
								class="space-y-4"
							>
								<div>
									<label for="query-text" class="block text-sm font-medium text-gray-700">
										{$_('knowledgeBases.detail.query.inputLabel', { default: 'Enter your query:' })}
									</label>
									<textarea
										id="query-text"
										rows="3"
										class="mt-1 block w-full rounded-md border border-gray-300 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] sm:text-sm"
										bind:value={queryText}
										required
									></textarea>
								</div>

								<div>
									<button
										type="submit"
										class="inline-flex items-center rounded-md border border-transparent bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none disabled:opacity-50"
										style="background-color: #2271b3;"
										disabled={queryLoading || !queryText.trim()}
									>
										{#if queryLoading}
											<!-- Loading spinner or text -->
											{$_('knowledgeBases.detail.query.loadingButton', { default: 'Querying...' })}
										{:else}
											{$_('knowledgeBases.detail.query.submitButton', { default: 'Submit Query' })}
										{/if}
									</button>
								</div>
							</form>

							<!-- Query Results Section -->
							{#if queryLoading}
								<div class="mt-4 rounded-md border bg-gray-50 p-4 text-center text-gray-500">
									{$_('knowledgeBases.detail.query.loadingResults', {
										default: 'Fetching results...'
									})}
								</div>
							{/if}

							{#if queryError}
								<div class="mt-4 rounded-md border bg-red-50 p-4 text-red-700">
									<p class="font-bold">
										{$_('knowledgeBases.detail.query.errorTitle', { default: 'Error:' })}
									</p>
									<pre class="text-sm whitespace-pre-wrap">{queryError}</pre>
								</div>
							{/if}

							{#if queryResult}
								<div class="mt-4 space-y-4 rounded-md border bg-blue-50 p-4">
									<h4 class="text-md font-medium text-gray-900">
										{$_('knowledgeBases.detail.query.resultsTitle', { default: 'Query Results:' })}
									</h4>

									{#if queryResult.results && queryResult.results.length > 0}
										<div class="space-y-6">
											{#each queryResult.results as result, i}
												<div class="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
													<!-- File Link (if available) -->
													{#if result.metadata?.file_url && result.metadata?.filename}
														<div class="mb-2 text-sm">
															<a
																href={result.metadata.file_url}
																target="_blank"
																rel="noopener noreferrer"
																class="font-medium text-[#2271b3] hover:text-[#195a91] hover:underline"
																style="color: #2271b3;"
																title={`Open file: ${result.metadata.filename}`}
															>
																<svg
																	xmlns="http://www.w3.org/2000/svg"
																	class="-mt-0.5 mr-1 inline-block h-4 w-4"
																	viewBox="0 0 20 20"
																	fill="currentColor"
																>
																	<path
																		fill-rule="evenodd"
																		d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l1.5 1.5a.5.5 0 00.707 0l1.5-1.5a.5.5 0 00-.707-.707l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0l1.5 1.5a.5.5 0 00.707 0l1.5-1.5a.5.5 0 00-.707-.707l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l1.5 1.5a.5.5 0 00.707 0l1.5-1.5a.5.5 0 00-.707-.707l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5a2 2 0 11-2.828-2.828z"
																		clip-rule="evenodd"
																	/>
																</svg>
																{result.metadata.filename}
															</a>
														</div>
													{/if}

													<div class="mb-2 flex items-start justify-between">
														<h5
															class="text-sm font-semibold text-[#2271b3]"
															style="color: #2271b3;"
														>
															{$_('knowledgeBases.detail.query.resultItemTitle', {
																default: 'Result'
															})}
															{i + 1}
														</h5>
														<span
															class="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800"
														>
															{$_('knowledgeBases.detail.query.similarityLabel', {
																default: 'Similarity:'
															})}
															{result.similarity.toFixed(4)}
														</span>
													</div>

													<div class="mb-3 text-sm text-gray-700">
														<p class="mb-1 font-medium">
															{$_('knowledgeBases.detail.query.contentLabel', {
																default: 'Content:'
															})}
														</p>
														<div
															class="prose prose-sm max-w-none rounded border bg-gray-50 p-2 break-words whitespace-pre-wrap"
														>
															{result.data}
														</div>
													</div>

													<div class="border-t pt-2 text-xs text-gray-500">
														<p class="mb-1 font-medium">
															{$_('knowledgeBases.detail.query.metadataLabel', {
																default: 'Metadata:'
															})}
														</p>
														<pre
															class="overflow-x-auto rounded bg-gray-50 p-2 text-xs whitespace-pre-wrap shadow-inner">{JSON.stringify(
																result.metadata,
																null,
																2
															)}</pre>
													</div>
												</div>
											{/each}
										</div>
									{:else}
										<p class="text-sm text-gray-600">
											{$_('knowledgeBases.detail.query.noResults', {
												default: 'No relevant results found for your query.'
											})}
										</p>
									{/if}

									<!-- Optional: Keep raw JSON for debugging -->
									<details class="text-xs">
										<summary class="cursor-pointer text-gray-500 hover:text-gray-700"
											>{$_('knowledgeBases.detail.query.showRawJson', {
												default: 'Show Raw JSON Response'
											})}</summary
										>
										<pre
											class="mt-2 overflow-x-auto rounded bg-white p-2 text-xs whitespace-pre-wrap shadow-sm">{JSON.stringify(
												queryResult,
												null,
												2
											)}</pre>
									</details>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		</div>
	{:else}
		<div class="p-6 text-center text-gray-500">
			{$_('knowledgeBases.detail.noData', { default: 'No knowledge base data available.' })}
		</div>
	{/if}
</div>
