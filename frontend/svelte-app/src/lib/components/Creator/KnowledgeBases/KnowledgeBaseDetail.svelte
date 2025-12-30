<script>
    import { onMount } from 'svelte';
    import { 
        getKnowledgeBaseDetails, 
        getIngestionPlugins, 
        uploadFileWithPlugin,
        runBaseIngestionPlugin
    } from '$lib/services/knowledgeBaseService';
    import { _ } from '$lib/i18n';
    import { page } from '$app/stores';
    // Import types for JSDoc
    /**
     * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBase} KnowledgeBase
     * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBaseCreate} KnowledgeBaseCreate
     * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBaseCreateResponse} KnowledgeBaseCreateResponse
     * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBaseFile} ImportedKnowledgeBaseFile // Renamed to avoid conflict
     * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBaseDetails} KnowledgeBaseDetails
     * @typedef {import('$lib/services/knowledgeBaseService').IngestionPlugin} IngestionPlugin
     * @typedef {import('$lib/services/knowledgeBaseService').IngestionParameterDetail} IngestionParameterDetail
     * @typedef {import('$lib/services/knowledgeBaseService').QueryPlugin} QueryPlugin 
     * @typedef {import('$lib/services/knowledgeBaseService').QueryPluginParamDetail} QueryPluginParamDetail
     * @typedef {import('$lib/services/knowledgeBaseService').QueryResultItem} QueryResultItem
     */
    
    /** 
     * Local definition reflecting template usage
     * @typedef {Object} KnowledgeBaseFile
     * @property {string} id
     * @property {string} filename
     * @property {number} [size]
     * @property {string} [content_type]
     * @property {number} [created_at] // Assuming might be added later
     * @property {string} [file_url]
     */

    // Component props
    /** @type {{ kbId?: string }} */
    let { kbId = '' } = $props();
    
    // Component state
    /** @type {any | null} */
    let kb = $state(null);
    let loading = $state(true);
    /** @type {string} */
    let error = $state('');
    let serverOffline = $state(false);
    /** @type {string} */
    let previousKbId = ''; 

    // Tab state
    /** @type {'files' | 'ingest'} */
    let activeTab = $state('files');

    // Ingestion state
    /** @type {IngestionPlugin[]} */
    let ingestionPlugins = $state([]);
    let loadingIngestionPlugins = $state(false);
    /** @type {string} */
    let ingestionPluginsError = $state('');
    /** @type {IngestionPlugin | null} */
    let selectedIngestionPlugin = $state(null);
    let selectedIngestionPluginIndex = $state(0);
    /** @type {Record<string, any>} */
    let ingestionPluginParams = $state({});
    /** @type {File | null} */
    let selectedFile = $state(null);
    let uploading = $state(false);
    let isSubmitting = false; // Synchronous lock for preventing rapid submissions
    /** @type {string} */
    let uploadError = $state('');
    let uploadSuccess = $state(false);
    let lastSubmitTime = 0; // Track last submission time for debouncing
    
    // Initialization and cleanup
    onMount(() => {
        console.log('KnowledgeBaseDetail mounted, kbId:', kbId);
        previousKbId = kbId; 
        return () => {
            console.log('KnowledgeBaseDetail unmounted');
        };
    });
    
    // Effect to load KB details
    $effect(() => {
        console.log('Effect running. kbId:', kbId, 'previousKbId:', previousKbId, 'kb:', kb !== null);
        if (kbId && (kbId !== previousKbId || kb === null)) {
            console.log('Condition met: Loading knowledge base for kbId:', kbId);
            loadKnowledgeBase(kbId);
            // Reset tabs and related state when KB ID changes
            activeTab = 'files';
            ingestionPlugins = []; // Clear potentially old plugins
            previousKbId = kbId; 
        } else {
            console.log('Condition not met: Skipping loadKnowledgeBase.');
            if (!kbId && kb !== null) {
                 console.log('kbId is empty, resetting kb state.');
                 kb = null;
                 previousKbId = '';
                 activeTab = 'files'; // Reset tab as well
            }
            if (kbId !== previousKbId) {
                 previousKbId = kbId;
            }
        }
    });

    /**
     * Function to change active tab
     * @param {'files' | 'ingest'} tabName - The name of the tab to select
     */
    function selectTab(tabName) {
        console.log('Selecting tab:', tabName);
        // Prevent accessing ingest tab if user doesn't have modify permissions
        if (tabName === 'ingest' && kb && kb.can_modify !== true) {
            console.warn('User attempted to access ingest tab without permissions');
            activeTab = 'files'; // Redirect to files tab
            return;
        }
        activeTab = tabName;
        
        // Fetch relevant plugins if tab is opened for the first time
        if (tabName === 'ingest' && ingestionPlugins.length === 0 && !loadingIngestionPlugins) {
            console.log('Ingest tab selected, fetching ingestion plugins.');
            fetchIngestionPlugins();
        }
        
        // Reset status messages when switching tabs
        uploadError = '';
        uploadSuccess = false;
        
        // Optionally reset file input when switching away from ingest tab
        if (tabName !== 'ingest') {
            selectedFile = null;
            resetFileInput();
        }
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
        if (!kb) loading = true; 
        error = '';
        serverOffline = false; 
        
        try {
            const data = await getKnowledgeBaseDetails(id);
            kb = data;
            console.log('Knowledge base details loaded:', kb);
        } catch (/** @type {any} */ err) { // Use 'any' for caught error
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
     * @param {number | undefined | null} bytes - File size in bytes
     * @returns {string} Formatted file size
     */
    function formatFileSize(bytes) {
        if (bytes === undefined || bytes === null || isNaN(bytes)) return 'N/A';
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
    function handleDeleteFile(fileId) {
        console.log(`Delete file requested: ${fileId}`);
        alert($_('knowledgeBases.detail.fileDeleteNotImplemented', { default: 'File delete functionality not yet implemented' }));
    }

    // --- Ingestion Functions ---
    /** Fetches available ingestion plugins */
    async function fetchIngestionPlugins() {
        loadingIngestionPlugins = true;
        ingestionPluginsError = '';
        try {
            ingestionPlugins = await getIngestionPlugins();
            console.log('Fetched ingestion plugins:', ingestionPlugins);
            if (ingestionPlugins.length > 0) {
                selectIngestionPlugin(0);
            }
        } catch (/** @type {any} */ err) { // Use 'any' for caught error
            console.error('Error fetching ingestion plugins:', err);
            ingestionPluginsError = err instanceof Error ? err.message : 'Failed to load ingestion plugins';
            if (err instanceof Error && err.message.includes('server offline')) {
                serverOffline = true; 
            }
        } finally {
            loadingIngestionPlugins = false;
        }
    }
    
    /** 
     * Selects an ingestion plugin 
     * @param {number} index
     */
    function selectIngestionPlugin(index) {
        if (index >= 0 && index < ingestionPlugins.length) {
            selectedIngestionPluginIndex = index;
            selectedIngestionPlugin = ingestionPlugins[index];
            ingestionPluginParams = {};
            if (selectedIngestionPlugin && selectedIngestionPlugin.parameters) {
                for (const paramName in selectedIngestionPlugin.parameters) {
                    ingestionPluginParams[paramName] = selectedIngestionPlugin.parameters[paramName].default;
                }
            }
            console.log('Selected ingestion plugin:', selectedIngestionPlugin?.name, 'with params:', ingestionPluginParams);
        }
    }
    
    /** 
     * Handles file selection 
     * @param {Event} event
     */
    function handleFileSelect(event) {
        const input = /** @type {HTMLInputElement} */ (event.target);
        if (input.files && input.files.length > 0) {
            selectedFile = input.files[0];
            uploadError = '';
            uploadSuccess = false;
            console.log('Selected file:', selectedFile.name, selectedFile.type, selectedFile.size);
        } else {
            selectedFile = null;
        }
    }
    
    /** 
     * Updates an ingestion plugin parameter 
     * @param {string} paramName
     * @param {Event} event
     */
    function updateIngestionParamValue(paramName, event) {
        const input = /** @type {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} */ (event.target);
        const paramDef = selectedIngestionPlugin?.parameters?.[paramName];
        if (paramDef && input) {
            if (paramDef.type === 'integer' || paramDef.type === 'number') {
                ingestionPluginParams[paramName] = input.value ? Number(input.value) : paramDef.default;
            } else if (paramDef.type === 'boolean') {
                 // Check if it's a checkbox input
                 if ('checked' in input) {
                    ingestionPluginParams[paramName] = input.checked;
                 }
            } else if (paramDef.type === 'array') {
                 ingestionPluginParams[paramName] = input.value.split('\n').filter(s => s.trim() !== '');
            } else { // string or enum (select)
                ingestionPluginParams[paramName] = input.value;
            }
            console.log(`Updated ingestion param ${paramName} to:`, ingestionPluginParams[paramName]);
        }
    }
    
    /** Uploads the selected file */
    async function uploadFile() {
        // Guard: Prevent duplicate submissions - SET THIS FIRST!
        if (uploading || isSubmitting) {
            console.warn('Upload already in progress, ignoring duplicate submission');
            return;
        }
        isSubmitting = true; // Synchronous lock - set immediately
        uploading = true; // UI state - may update asynchronously
        
        console.log('uploadFile called, selectedFile:', selectedFile?.name, 'selectedPlugin:', selectedIngestionPlugin?.name);
        
        // Guard: Debounce rapid submissions (within 1 second)
        const now = Date.now();
        if (now - lastSubmitTime < 1000) {
            console.warn('Upload submission debounced (too soon after last submission)');
            uploading = false; // Reset since we're aborting
            isSubmitting = false;
            return;
        }
        lastSubmitTime = now;
        
        if (!selectedFile || !selectedIngestionPlugin) {
            uploadError = 'Please select a file and plugin.';
            console.warn('Upload aborted: missing file or plugin');
            uploading = false; // Reset since we're aborting
            isSubmitting = false;
            return;
        }
        uploadError = '';
        uploadSuccess = false;
        console.log('Upload parameters:', { 
            kbId, 
            fileName: selectedFile?.name, 
            fileSize: selectedFile?.size, 
            fileType: selectedFile?.type, 
            pluginName: selectedIngestionPlugin.name, 
            ingestionPluginParams 
        });
        try {
            const result = await uploadFileWithPlugin(kbId, selectedFile, selectedIngestionPlugin.name, ingestionPluginParams);
            console.log('Upload result:', result);
            uploadSuccess = true;
            selectedFile = null;
            resetFileInput();
            await loadKnowledgeBase(kbId); // Reload KB details to show the new file
        } catch (/** @type {any} */ err) { // Use 'any' for caught error
            console.error('Error uploading file:', err);
            uploadError = err instanceof Error ? err.message : 'Failed to upload file';
            if (err instanceof Error && err.message.includes('server offline')) {
                 serverOffline = true;
            }
        } finally {
            uploading = false;
            isSubmitting = false;
        }
    }
    
    /** Runs the selected base ingestion plugin */
    async function runBaseIngestion() {
        // Guard: Prevent duplicate submissions - SET THIS FIRST!
        if (uploading || isSubmitting) {
            console.warn('Ingestion already in progress, ignoring duplicate submission');
            return;
        }
        isSubmitting = true; // Synchronous lock - set immediately
        uploading = true; // UI state - may update asynchronously
        
        console.log('runBaseIngestion called, selectedPlugin:', selectedIngestionPlugin?.name);
        
        // Guard: Debounce rapid submissions (within 1 second)
        const now = Date.now();
        if (now - lastSubmitTime < 1000) {
            console.warn('Ingestion submission debounced (too soon after last submission)');
            uploading = false; // Reset since we're aborting
            isSubmitting = false;
            return;
        }
        lastSubmitTime = now;
        
        if (!selectedIngestionPlugin) {
            uploadError = 'Please select a plugin.'; // Changed error message
            console.warn('Ingestion aborted: missing plugin');
            uploading = false; // Reset since we're aborting
            isSubmitting = false;
            return;
        }
        uploadError = '';
        uploadSuccess = false;
        console.log('Base ingestion parameters:', { 
            kbId, 
            pluginName: selectedIngestionPlugin.name, 
            ingestionPluginParams 
        });
        try {
            // Assuming runBaseIngestionPlugin is imported
            const result = await runBaseIngestionPlugin(kbId, selectedIngestionPlugin.name, ingestionPluginParams);
            console.log('Base ingestion result:', result);
            uploadSuccess = true; // Use same success flag
            // No file to reset, but maybe clear params?
            // ingestionPluginParams = {}; // Optional: Reset params on success
            
            // Reload KB details - even if no files were added, metadata might change
            await loadKnowledgeBase(kbId); 
        } catch (/** @type {any} */ err) { // Use 'any' for caught error
            console.error('Error running base ingestion:', err);
            // Use same error flag, maybe tailor message slightly?
            uploadError = err instanceof Error ? err.message : 'Failed to run ingestion plugin'; 
            if (err instanceof Error && err.message.includes('server offline')) {
                 serverOffline = true;
            }
        } finally {
            uploading = false;
            isSubmitting = false;
        }
    }
    
    /** Handles the form submission based on plugin type */
    function handleIngestSubmit() {
        if (selectedIngestionPlugin?.kind === 'file-ingest') {
            uploadFile();
        } else {
            runBaseIngestion();
        }
    }
    

</script>

<div class="bg-white shadow overflow-hidden sm:rounded-lg">
    <div style="background-color: red; color: white; padding: 10px; margin: 5px; font-weight: bold;">
        DEBUG TEST - TOP OF COMPONENT (Before conditions)
    </div>
    {#if loading}
        <div class="p-6 text-center">
            <div class="animate-pulse text-gray-500">{$_('knowledgeBases.detail.loading', { default: 'Loading knowledge base details...' })}</div>
        </div>
    {:else if error}
        <div class="p-6 text-center">
            <div class="text-red-500">
                 {#if serverOffline}
                    <div>
                        <p class="font-bold mb-2">{$_('knowledgeBases.detail.serverOfflineTitle', { default: 'Knowledge Base Server Offline' })}</p>
                        <p>{$_('knowledgeBases.detail.serverOfflineMessage', { default: 'Could not load details. Please try again later or contact an administrator.' })}</p>
                    </div>
                {:else}
                    <p>{error}</p>
                {/if}
                <button onclick={() => loadKnowledgeBase(kbId)} class="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3]" style="background-color: #2271b3;">
                    {$_('knowledgeBases.detail.retryButton', { default: 'Retry' })}
                </button>
            </div>
        </div>
    {:else if kb}
        <div style="background-color: blue; color: white; padding: 10px; margin: 5px; font-weight: bold;">
            DEBUG TEST - INSIDE KB BLOCK (After kb condition)
        </div>
        <div>
            <!-- Header section -->
             <div class="px-4 py-5 sm:px-6 border-b border-gray-200">
                <h3 class="text-lg leading-6 font-medium text-gray-900">
                    {kb.name}
                </h3>
                <p class="mt-1 max-w-2xl text-sm text-gray-500">
                    {kb.description || $_('knowledgeBases.detail.noDescription', { default: 'No description provided.' })}
                </p>
            </div>
            
            <!-- Knowledge base metadata section -->
             <div class="border-b border-gray-200">
                <dl>
                    
                    <div class="bg-gray-50 px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">
                            {$_('knowledgeBases.detail.idLabel', { default: 'ID' })}
                        </dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            {kb.id}
                        </dd>
                    </div>
                    
                    {#if kb.owner} <!-- Keep check, assumes owner might exist -->
                    <div class="bg-white px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">
                            {$_('knowledgeBases.detail.ownerLabel', { default: 'Owner' })}
                        </dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            {kb.owner}
                        </dd>
                    </div>
                    {/if}
                    
                    {#if kb.created_at} <!-- Keep check, assumes created_at might exist -->
                    <div class="bg-gray-50 px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">
                            {$_('knowledgeBases.detail.createdLabel', { default: 'Created' })}
                        </dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            {kb.created_at ? new Date(kb.created_at * 1000).toLocaleString() : 'N/A'}
                        </dd>
                    </div>
                    {/if}
                    
                    <!-- Commenting out Access Control section for testing -->
                    <!--
                    {#if kb?.metadata?.access_control}
                    <div class="bg-white px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">
                            {$_('knowledgeBases.detail.accessLabel', { default: 'Access Control' })}
                        </dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {kb.metadata.access_control === 'private' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}">
                                {kb.metadata.access_control}
                            </span>
                        </dd>
                    </div>
                    {/if}
                    -->
                </dl>
            </div>
            
            <div style="background-color: green; color: white; padding: 10px; margin: 5px; font-weight: bold;">
                DEBUG TEST - AFTER METADATA (Before tabs)
            </div>
            
            <!-- Files / Ingestion / Query Section with Tabs -->
            <div class="border-t border-gray-200">
                
                <!-- Tab List -->
                <div class="border-b border-gray-200">
                    <nav class="-mb-px flex space-x-8 px-4 sm:px-6" aria-label="Tabs">
                        <!-- Files Tab -->
                        <button 
                            type="button"
                            onclick={() => selectTab('files')}
                            class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm {activeTab === 'files' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            style="{activeTab === 'files' ? 'border-color: #2271b3; color: #2271b3;' : ''}"
                            aria-current={activeTab === 'files' ? 'page' : undefined}
                        >
                            {$_('knowledgeBases.detail.filesTab', { default: 'Files' })}
                        </button>
                        
                        <!-- Ingest Content Tab -->
                        {#if kb.can_modify === true}
                        <button 
                            type="button"
                            onclick={() => selectTab('ingest')}
                            class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm {activeTab === 'ingest' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                            style="{activeTab === 'ingest' ? 'border-color: #2271b3; color: #2271b3;' : ''}"
                             aria-current={activeTab === 'ingest' ? 'page' : undefined}
                       >
                            {$_('knowledgeBases.detail.ingestTab', { default: 'Ingest Content' })}
                        </button>
                        {/if}
                    </nav>
                </div>

                <!-- Tab Panels -->
                <div class="px-4 py-5 sm:px-6">
                    <p style="color: magenta; font-weight: bold; padding: 5px; border: 1px solid magenta;">DEBUG: Current activeTab is: {activeTab}</p>
                    <!-- Files Panel -->
                    {#if activeTab === 'files'}
                         <div>
                             {#if kb.files && kb.files.length > 0}
                                <div class="overflow-x-auto">
                                    <table class="min-w-full divide-y divide-gray-200">
                                        <thead class="bg-gray-50">
                                             <tr>
                                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {$_('knowledgeBases.detail.fileNameColumn', { default: 'File Name' })}
                                                </th>
                                                 <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {$_('knowledgeBases.detail.fileSizeColumn', { default: 'Size' })}
                                                </th>
                                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {$_('knowledgeBases.detail.fileTypeColumn', { default: 'Type' })}
                                                </th>
                                                <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {$_('knowledgeBases.detail.fileActionsColumn', { default: 'Actions' })}
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody class="bg-white divide-y divide-gray-200">
                                            {#each kb.files as file (file.id)}
                                                <tr>
                                                    <td class="px-6 py-4 whitespace-nowrap">
                                                        <div class="flex items-center">
                                                            <div class="text-sm font-medium text-gray-900">
                                                                {#if file.file_url} <!-- Use updated KnowledgeBaseFile def -->
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
                                                            {formatFileSize(file.size)} <!-- Use updated KnowledgeBaseFile def -->
                                                        </div>
                                                    </td>
                                                    <td class="px-6 py-4 whitespace-nowrap">
                                                        <div class="text-sm text-gray-900">
                                                            {file.content_type || 'Unknown'} <!-- Use updated KnowledgeBaseFile def -->
                                                        </div>
                                                    </td>
                                                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                        {#if kb.can_modify === true}
                                                        <button 
                                                            onclick={() => handleDeleteFile(file.id)}
                                                            class="text-red-600 hover:text-red-900"
                                                        >
                                                            {$_('knowledgeBases.detail.fileDeleteButton', { default: 'Delete' })}
                                                        </button>
                                                        {/if}
                                                    </td>
                                                </tr>
                                            {/each}
                                        </tbody>
                                    </table>
                                </div>
                            {:else}
                                <div class="text-center text-gray-500 py-4">
                                    {$_('knowledgeBases.detail.noFiles', { default: 'No files have been uploaded to this knowledge base.' })}
                                </div>
                            {/if}
                        </div>
                    {/if}

                    <!-- Ingest Content Panel -->
                    {#if activeTab === 'ingest'}
                        {@const isFilePlugin = selectedIngestionPlugin?.kind === 'file-ingest'}
                        {@const acceptTypes = isFilePlugin ? (selectedIngestionPlugin?.supported_file_types ?? []).join(',') : ''}
                        
                        <!-- MORE DEBUGGING -->
                        <div class="p-2 border border-blue-500 my-1">
                            <p class="text-xs text-blue-700">SIMPLE DEBUG: Selected Plugin Name: {selectedIngestionPlugin?.name || 'Not Set'}</p>
                        </div>

                        <!-- DEBUGGING LOGS -->
                        {console.log('Rendering Ingest Tab. Selected Plugin:', selectedIngestionPlugin)}
                        {console.log('isFilePlugin calculated as:', isFilePlugin)}
                        <!-- END DEBUGGING LOGS -->

                        <div class="bg-gray-50 -mx-4 -my-5 sm:-mx-6 px-4 py-5 sm:px-6">
                             <h4 class="text-md font-medium text-gray-700 mb-4">
                                {isFilePlugin 
                                    ? $_('knowledgeBases.fileUpload.sectionTitleFile', { default: 'Upload and Ingest New File' })
                                    : $_('knowledgeBases.fileUpload.sectionTitleBase', { default: 'Configure and Run Ingestion' })
                                }
                            </h4>
                            {#if loadingIngestionPlugins}
                                <div class="py-4 text-center"> <div class="animate-pulse text-gray-500"> {$_('knowledgeBases.fileUpload.loadingPlugins', { default: 'Loading ingestion plugins...' })} </div> </div>
                            {:else if ingestionPluginsError}
                                 <div class="py-4 text-center"> <div class="text-red-500"> {#if serverOffline} <div> <p class="font-bold mb-2"> {$_('knowledgeBases.fileUpload.serverOffline', { default: 'Knowledge Base Server Offline' })} </p> <p> {$_('knowledgeBases.fileUpload.tryAgainLater', { default: 'Please try again later or contact an administrator.' })} </p> </div> {:else} {ingestionPluginsError} {/if} </div> <button onclick={fetchIngestionPlugins} class="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3]" style="background-color: #2271b3;"> {$_('knowledgeBases.fileUpload.retry', { default: 'Retry' })} </button> </div>
                            {:else if ingestionPlugins.length === 0}
                                 <div class="py-4 text-center"> <div class="text-gray-500"> {$_('knowledgeBases.fileUpload.noPlugins', { default: 'No ingestion plugins available.' })} </div> </div>
                            {:else}
                                <form onsubmit={(e) => { 
                                    e.preventDefault(); 
                                    // Prevent form submission if triggered by Enter key in an input field
                                    if (e.submitter === null || e.submitter?.tagName === 'INPUT') {
                                        console.log('Form submission blocked - triggered by Enter in input field');
                                        return;
                                    }
                                    handleIngestSubmit(); 
                                }} class="space-y-6">
                                    {#if isFilePlugin}
                                        {console.log('File input rendered because isFilePlugin is true.')}
                                        <div> <label for="file-upload-input-inline" class="block text-sm font-medium text-gray-700"> {$_('knowledgeBases.fileUpload.fileLabel', { default: 'Select File' })} {#if acceptTypes}<span class="text-xs text-gray-500 ml-1">(Supported: {acceptTypes})</span>{/if} </label> <div class="mt-1 flex items-center"> <input id="file-upload-input-inline" type="file" class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-[#2271b3] file:text-white hover:file:bg-[#195a91]" style="file:background-color: #2271b3;" onchange={handleFileSelect} accept={acceptTypes} /> </div> {#if selectedFile} <p class="mt-2 text-sm text-gray-500"> {selectedFile.name} ({formatFileSize(selectedFile.size)}) </p> {/if} </div>
                                    {:else}
                                        {console.log('File input NOT rendered because isFilePlugin is false.')}
                                    {/if}
                                    
                                    <div> <label for="plugin-select-inline" class="block text-sm font-medium text-gray-700"> {$_('knowledgeBases.fileUpload.pluginLabel', { default: 'Ingestion Plugin' })} </label> <div class="mt-1"> <select id="plugin-select-inline" class="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm rounded-md" onchange={(e) => { const select = /** @type {HTMLSelectElement} */ (e.target); if (select && select.value) { selectIngestionPlugin(parseInt(select.value)); } }} > {#each ingestionPlugins as plugin, i} <option value={i} selected={i === selectedIngestionPluginIndex}> {plugin.name} - {plugin.description} </option> {/each} </select> </div> </div>
                                    
                                    <div class="p-4 border border-dashed border-red-500 my-2">
                                        <h6 class="font-bold text-red-700">DEBUGGING OUTPUT:</h6>
                                        <p class="text-xs text-gray-600">Selected Plugin Parameters (raw from template):</p>
                                        <pre class="text-xs bg-red-50 p-2 rounded overflow-x-auto">{JSON.stringify(selectedIngestionPlugin?.parameters, null, 2)}</pre>
                                        <p class="text-xs text-gray-600 mt-1">Number of keys in parameters (template): {Object.keys(selectedIngestionPlugin?.parameters || {}).length}</p>
                                        <p class="text-xs text-gray-600 mt-1">Condition Check (template): {selectedIngestionPlugin && selectedIngestionPlugin.parameters && Object.keys(selectedIngestionPlugin.parameters).length > 0}</p>
                                    </div>
                                    
                                    {#if selectedIngestionPlugin && selectedIngestionPlugin.parameters && Object.keys(selectedIngestionPlugin.parameters).length > 0} <div class="space-y-4 border-t border-gray-200 pt-4"> <h5 class="font-medium text-gray-700"> {$_('knowledgeBases.fileUpload.parametersLabel', { default: 'Plugin Parameters' })} </h5> {#each Object.entries(selectedIngestionPlugin.parameters) as [paramName, paramDef] (paramName)}
                            {console.log('DEBUG: paramDef for', paramName, 'is:', paramDef)}
                            <div> <label for={`param-${paramName}-ingest`} class="block text-sm font-medium text-gray-700">
                                    {paramName}
                                    {paramDef.required ? ' *' : ''}
                                    {#if paramDef.description}
                                        <span class="text-xs text-gray-500 ml-1">({paramDef.description})</span>
                                    {/if}
                                </label>
                                <div class="mt-1">
                                    {#if paramDef.enum && Array.isArray(paramDef.enum)}
                                        <select
                                            id={`param-${paramName}-ingest`}
                                            class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                            value={ingestionPluginParams[paramName]}
                                            onchange={(e) => updateIngestionParamValue(paramName, e)}
                                        >
                                            {#each paramDef.enum as enumValue}
                                                <option value={enumValue} selected={ingestionPluginParams[paramName] === enumValue}>
                                                    {enumValue}
                                                </option>
                                            {/each}
                                        </select>
                                    {:else if paramDef.type === 'boolean'}
                                        <div class="flex items-center">
                                            <input
                                                id={`param-${paramName}-ingest`}
                                                type="checkbox"
                                                class="h-4 w-4 text-[#2271b3] focus:ring-[#2271b3] border-gray-300 rounded"
                                                checked={ingestionPluginParams[paramName] === true}
                                                onchange={(e) => updateIngestionParamValue(paramName, e)}
                                            />
                                            <label for={`param-${paramName}-ingest`} class="ml-2 block text-sm text-gray-900">
                                                {paramDef.default ? 'Enabled' : 'Disabled'} by default
                                            </label>
                                        </div>
                                    {:else if paramDef.type === 'integer' || paramDef.type === 'number'}
                                        <input
                                            id={`param-${paramName}-ingest`}
                                            type="number"
                                            class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                            value={ingestionPluginParams[paramName]}
                                            placeholder={paramDef.default !== undefined && paramDef.default !== null ? paramDef.default.toString() : ''}
                                            onchange={(e) => updateIngestionParamValue(paramName, e)}
                                        />
                                    {:else if paramDef.type === 'array'}
                                        <textarea
                                            id={`param-${paramName}-ingest`}
                                            rows="3"
                                            class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                            value={Array.isArray(ingestionPluginParams[paramName]) ? ingestionPluginParams[paramName].join('\n') : ingestionPluginParams[paramName] || ''}
                                            placeholder={paramDef.description || 'Enter values, one per line'}
                                            onchange={(e) => updateIngestionParamValue(paramName, e)}
                                        ></textarea>
                                        <p class="mt-1 text-xs text-gray-500">Enter values separated by new lines.</p>
                                    {:else if paramDef.type === 'long-string'}
                                        <textarea
                                            id={`param-${paramName}-ingest`}
                                            rows="4" 
                                            class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                            value={ingestionPluginParams[paramName]}
                                            placeholder={paramDef.default !== undefined && paramDef.default !== null ? paramDef.default.toString() : (paramDef.description || '')}
                                            onchange={(e) => updateIngestionParamValue(paramName, e)}
                                        ></textarea>
                                    {:else} 
                                        <input
                                            id={`param-${paramName}-ingest`}
                                            type="text"
                                            class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                            value={ingestionPluginParams[paramName]}
                                            placeholder={paramDef.default !== undefined && paramDef.default !== null ? paramDef.default.toString() : (paramDef.description || '')}
                                            onchange={(e) => updateIngestionParamValue(paramName, e)}
                                        />
                                    {/if}
                                </div>
                            </div>
                        {/each}
                    </div>
                {/if}
                                     <!-- Submit Button and Feedback -->
                                     <div class="pt-4 flex flex-col sm:flex-row sm:items-center sm:justify-end gap-3">
                                        <!-- Inline feedback messages -->
                                        {#if uploadSuccess}
                                            <div class="flex-1 p-3 bg-green-50 border border-green-200 rounded-md">
                                                <div class="text-sm text-green-700 flex items-center">
                                                    <svg class="h-4 w-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                                                    </svg>
                                                    {$_('knowledgeBases.fileUpload.success', { default: 'File uploaded and ingestion started successfully!' })}
                                                </div>
                                            </div>
                                        {/if}
                                        {#if uploadError}
                                            <div class="flex-1 p-3 bg-red-50 border border-red-200 rounded-md">
                                                <div class="text-sm text-red-700 flex items-center">
                                                    <svg class="h-4 w-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                                                    </svg>
                                                    {uploadError}
                                                </div>
                                            </div>
                                        {/if}
                                        <button type="submit" class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] flex-shrink-0" style="background-color: #2271b3;" disabled={!selectedIngestionPlugin || uploading || (isFilePlugin && !selectedFile)}> {#if uploading} <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"> <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle> <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path> </svg> {$_('knowledgeBases.fileUpload.uploadingButton', { default: 'Uploading...' })} {:else} {isFilePlugin ? $_('knowledgeBases.fileUpload.uploadButton', { default: 'Upload File' }) : $_('knowledgeBases.fileUpload.runButton', { default: 'Run Ingestion' })} {/if} </button>
                                     </div>
                                </form>
                            {/if}
                        </div>
                    {/if}
                </div> <!-- End Tab Panels -->
            </div> <!-- End Files / Ingestion / Query Section -->
            
        </div>
    {:else}
        <!-- Show 'No data' message if kb is null after loading finishes -->
         <div class="p-6 text-center text-gray-500">
            {$_('knowledgeBases.detail.noData', { default: 'No knowledge base data available.' })}
        </div>
    {/if}
</div> 