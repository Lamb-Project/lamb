<script>
    import { onMount } from 'svelte';
    import { getKnowledgeBaseDetails, getIngestionPlugins, uploadFileWithPlugin, runBaseIngestionPlugin, deleteKnowledgeBaseFile, listIngestionJobs, retryIngestionJob, cancelIngestionJob, getIngestionJobStatus } from '$lib/services/knowledgeBaseService';
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
     * @typedef {Object} IngestionProgress
     * @property {number} [current]
     * @property {number} [total]
     * @property {number} [percentage]
     * @property {string} [message]
     */

    /**
     * @typedef {Object} StageTiming
     * @property {string} stage
     * @property {number} duration_ms
     * @property {string} message
     * @property {string} [timestamp]
     */

    /**
     * @typedef {Object} ChunkStats
     * @property {number} count
     * @property {number} avg_size
     * @property {number} min_size
     * @property {number} max_size
     */

    /**
     * @typedef {Object} OutputFiles
     * @property {string} [markdown_url]
     * @property {string} [images_folder_url]
     * @property {string} [original_file_url]
     */

    /**
     * @typedef {Object} LLMCallDetail
     * @property {string} image
     * @property {number} duration_ms
     * @property {boolean} success
     * @property {number} [tokens_used]
     * @property {string} [error]
     */

    /**
     * @typedef {Object} ProcessingStats
     * @property {number} content_length
     * @property {number} images_extracted
     * @property {number} images_with_llm_descriptions
     * @property {LLMCallDetail[]} llm_calls
     * @property {number} total_llm_duration_ms
     * @property {string} [chunking_strategy]
     * @property {ChunkStats} [chunk_stats]
     * @property {StageTiming[]} stage_timings
     * @property {OutputFiles} [output_files]
     * @property {string} [markdown_preview]
     */

    /**
     * @typedef {Object} IngestionJob
     * @property {number} id
     * @property {number} collection_id
     * @property {string} original_filename
     * @property {string} [file_path]
     * @property {string} [file_url]
     * @property {number} [file_size]
     * @property {string} [content_type]
     * @property {string} plugin_name
     * @property {Object} [plugin_params]
     * @property {'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'deleted'} status
     * @property {number} document_count
     * @property {string} [created_at]
     * @property {string} [updated_at]
     * @property {string} [processing_started_at]
     * @property {string} [processing_completed_at]
     * @property {number} [processing_duration_seconds]
     * @property {IngestionProgress} [progress]
     * @property {string} [error_message]
     * @property {Object} [error_details]
     * @property {ProcessingStats} [processing_stats]
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
    
    // Derived: filter parameters that should be visible based on visible_when conditions
    // We need to access the state snapshot to ensure reactivity when params change
    let visibleParamKeys = $derived.by(() => {
        // Get a plain object snapshot for reliable access
        const params = $state.snapshot(pluginParams);
        
        if (!selectedPlugin?.parameters) return [];
        const paramKeys = Object.keys(selectedPlugin.parameters).filter(name => !name.startsWith('_'));
        
        const result = paramKeys.filter(paramName => {
            const paramDef = selectedPlugin.parameters[paramName];
            // If no visible_when condition, always show
            if (!paramDef.visible_when) {
                return true;
            }
            // Check all conditions in visible_when
            for (const [field, allowedValues] of Object.entries(paramDef.visible_when)) {
                const currentValue = params[field];
                // If the current value is not in the allowed values array, hide the parameter
                if (!Array.isArray(allowedValues) || !allowedValues.includes(currentValue)) {
                    return false;
                }
            }
            return true;
        });
        
        return result;
    });
    
    /** @type {File | null} */
    let selectedFile = $state(null);
    // Derived flag: treat only explicit 'file-ingest' as requiring a file. Other kinds (base-ingest, remote-ingest, etc.) run without file upload.
    $effect(() => {
        // If switching to a non file plugin, clear any previous file selection requirement
        if (selectedPlugin && selectedPlugin.kind && selectedPlugin.kind !== 'file-ingest') {
            // Non-file plugin: ensure selectedFile isn't blocking UI logic
            // (We purposely do NOT reset selectedFile so user can switch back without reselecting.)
        }
    });
    let uploading = $state(false);
    let uploadError = $state('');
    let uploadSuccess = $state(false);
    
    let previousKbId = ''; // Track previous kbId
    
    // State for query tab
    let queryText = $state('');
    /** @type {QueryApiResponse | null} */
    let queryResult = $state(null);
    let queryLoading = $state(false);
    let queryError = $state('');

    // State for ingestion jobs
    /** @type {IngestionJob[]} */
    let ingestionJobs = $state([]);
    let loadingJobs = $state(false);
    let jobsError = $state('');
    
    // State for job detail modal
    /** @type {IngestionJob | null} */
    let selectedJob = $state(null);
    let showJobModal = $state(false);
    let jobActionLoading = $state(false);

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
        // Prevent accessing ingest tab if user doesn't have modify permissions
        if (tabName === 'ingest' && kb && kb.can_modify !== true) {
            console.warn('User attempted to access ingest tab without permissions');
            activeTab = 'files'; // Redirect to files tab
            return;
        }
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
            console.log('can_modify value:', kb?.can_modify, 'type:', typeof kb?.can_modify);
            
            // Fetch ingestion jobs alongside KB details
            await loadIngestionJobs(id);
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
     * Load ingestion jobs for the knowledge base
     * @param {string} id - Knowledge base ID
     */
    async function loadIngestionJobs(id) {
        loadingJobs = true;
        jobsError = '';
        
        try {
            const response = await listIngestionJobs(id, { limit: 200, sort_by: 'created_at', sort_order: 'desc' });
            ingestionJobs = response.items || [];
            console.log('Ingestion jobs loaded:', ingestionJobs.length);
        } catch (/** @type {unknown} */ err) {
            console.error('Error loading ingestion jobs:', err);
            jobsError = err instanceof Error ? err.message : 'Failed to load ingestion jobs';
            ingestionJobs = [];
        } finally {
            loadingJobs = false;
        }
    }
    
    /**
     * Get the most recent ingestion job for a file by filename
     * @param {string} filename - The filename to search for
     * @returns {IngestionJob | null} The most recent job for this file or null
     */
    function getJobForFile(filename) {
        if (!ingestionJobs || ingestionJobs.length === 0) return null;
        
        // Find jobs matching this filename (most recent first since sorted by created_at desc)
        const job = ingestionJobs.find(j => j.original_filename === filename);
        return job || null;
    }
    
    /**
     * Get status badge color classes based on job status
     * @param {'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'deleted' | string} status
     * @returns {{ bg: string, text: string, ring: string }}
     */
    function getStatusColors(status) {
        switch (status) {
            case 'completed':
                return { bg: 'bg-emerald-100', text: 'text-emerald-800', ring: 'ring-emerald-600/20' };
            case 'processing':
                return { bg: 'bg-blue-100', text: 'text-blue-800', ring: 'ring-blue-600/20' };
            case 'pending':
                return { bg: 'bg-amber-100', text: 'text-amber-800', ring: 'ring-amber-600/20' };
            case 'failed':
                return { bg: 'bg-red-100', text: 'text-red-800', ring: 'ring-red-600/20' };
            case 'cancelled':
                return { bg: 'bg-gray-100', text: 'text-gray-800', ring: 'ring-gray-600/20' };
            case 'deleted':
                return { bg: 'bg-slate-100', text: 'text-slate-600', ring: 'ring-slate-600/20' };
            default:
                return { bg: 'bg-gray-100', text: 'text-gray-600', ring: 'ring-gray-600/20' };
        }
    }
    
    /**
     * Open job detail modal
     * @param {IngestionJob} job
     */
    function openJobModal(job) {
        selectedJob = job;
        showJobModal = true;
    }
    
    /**
     * Close job detail modal
     */
    function closeJobModal() {
        showJobModal = false;
        selectedJob = null;
    }
    
    /**
     * Retry a failed job
     * @param {number} jobId
     */
    async function handleRetryJob(jobId) {
        if (!kbId) return;
        jobActionLoading = true;
        
        try {
            await retryIngestionJob(kbId, jobId);
            // Refresh jobs after retry
            await loadIngestionJobs(kbId);
            closeJobModal();
        } catch (/** @type {unknown} */ err) {
            console.error('Error retrying job:', err);
            alert(err instanceof Error ? err.message : 'Failed to retry job');
        } finally {
            jobActionLoading = false;
        }
    }
    
    /**
     * Cancel a pending/processing job
     * @param {number} jobId
     */
    async function handleCancelJob(jobId) {
        if (!kbId) return;
        if (!confirm('Cancel this ingestion job?')) return;
        jobActionLoading = true;
        
        try {
            await cancelIngestionJob(kbId, jobId);
            // Refresh jobs after cancel
            await loadIngestionJobs(kbId);
            closeJobModal();
        } catch (/** @type {unknown} */ err) {
            console.error('Error cancelling job:', err);
            alert(err instanceof Error ? err.message : 'Failed to cancel job');
        } finally {
            jobActionLoading = false;
        }
    }
    
    /**
     * Refresh file statuses manually
     */
    async function refreshFileStatus() {
        if (!kbId) return;
        await loadIngestionJobs(kbId);
    }
    
    /**
     * Refresh the currently selected job's status
     */
    async function refreshSelectedJob() {
        if (!kbId || !selectedJob) return;
        jobActionLoading = true;
        
        try {
            const updatedJob = await getIngestionJobStatus(kbId, selectedJob.id);
            selectedJob = updatedJob;
            // Also refresh the jobs list to keep it in sync
            await loadIngestionJobs(kbId);
        } catch (/** @type {unknown} */ err) {
            console.error('Error refreshing job:', err);
        } finally {
            jobActionLoading = false;
        }
    }
    
    /**
     * Format milliseconds to human readable duration
     * @param {number} ms
     * @returns {string}
     */
    function formatMilliseconds(ms) {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        const minutes = Math.floor(ms / 60000);
        const seconds = ((ms % 60000) / 1000).toFixed(0);
        return `${minutes}m ${seconds}s`;
    }
    
    /**
     * Format number with thousands separator
     * @param {number} num
     * @returns {string}
     */
    function formatNumber(num) {
        return num.toLocaleString();
    }
    
    /**
     * Format date string for display
     * @param {string | undefined} dateStr
     * @returns {string}
     */
    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        try {
            return new Date(dateStr).toLocaleString();
        } catch {
            return dateStr;
        }
    }
    
    /**
     * Format duration in seconds to readable format
     * @param {number | undefined} seconds
     * @returns {string}
     */
    function formatDuration(seconds) {
        if (seconds === undefined || seconds === null) return 'N/A';
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${mins}m ${secs}s`;
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
        if (!kbId) return;
        if (!confirm($_('knowledgeBases.detail.confirmDelete', { default: 'Delete this file and its embeddings? This cannot be undone.' }))) {
            return;
        }
        try {
            await deleteKnowledgeBaseFile(kbId, fileId, true);
            // Refresh list
            await loadKnowledgeBase(kbId);
        } catch (err) {
            console.error('Failed to delete file', err);
            alert(err instanceof Error ? err.message : 'File deletion failed');
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
            // Skip underscore-prefixed parameters (informational only, not submitted)
            pluginParams = {};
            if (selectedPlugin && selectedPlugin.parameters) {
                // Iterate over the parameters object
                for (const paramName in selectedPlugin.parameters) {
                    if (paramName.startsWith('_')) continue; // Skip info-only params
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
     * Check if a parameter should be visible based on visible_when conditions
     * @param {IngestionParameterDetail} paramDef - The parameter definition
     * @returns {boolean} Whether the parameter should be shown
     */
    function shouldShowParameter(paramDef) {
        // If no visible_when condition, always show
        if (!paramDef.visible_when) return true;
        
        // Check all conditions in visible_when
        for (const [field, allowedValues] of Object.entries(paramDef.visible_when)) {
            const currentValue = pluginParams[field];
            // If the current value is not in the allowed values array, hide the parameter
            if (!Array.isArray(allowedValues) || !allowedValues.includes(currentValue)) {
                return false;
            }
        }
        return true;
    }
    
    /**
     * Check if a parameter controls visibility of other parameters (has dependents)
     * @param {string} paramName - The parameter name to check
     * @returns {boolean} Whether this parameter has dependent parameters
     */
    function hasVisibleWhenDependents(paramName) {
        if (!selectedPlugin?.parameters) return false;
        
        for (const [, paramDef] of Object.entries(selectedPlugin.parameters)) {
            if (paramDef.visible_when && paramName in paramDef.visible_when) {
                return true;
            }
        }
        return false;
    }
    
    /**
     * Get the label for an enum value using enum_labels if available
     * @param {IngestionParameterDetail} paramDef - The parameter definition
     * @param {string} enumValue - The raw enum value
     * @returns {string} The display label
     */
    function getEnumLabel(paramDef, enumValue) {
        if (paramDef.enum_labels && paramDef.enum_labels[enumValue]) {
            return paramDef.enum_labels[enumValue];
        }
        return enumValue;
    }
    
    /**
     * Validate numeric input against min/max constraints
     * @param {number} value - The input value
     * @param {IngestionParameterDetail} paramDef - The parameter definition
     * @returns {{ valid: boolean, message?: string }} Validation result
     */
    function validateNumericInput(value, paramDef) {
        if (paramDef.min !== undefined && value < paramDef.min) {
            return { valid: false, message: `Minimum value is ${paramDef.min}` };
        }
        if (paramDef.max !== undefined && value > paramDef.max) {
            return { valid: false, message: `Maximum value is ${paramDef.max}` };
        }
        return { valid: true };
    }
    
    /**
     * Uploads the selected file with the selected plugin
     */
    async function uploadFile() {
        console.log('uploadFile called, selectedFile:', selectedFile?.name, 'selectedPlugin:', selectedPlugin?.name);
        
        if (!selectedFile || !selectedPlugin) {
            uploadError = 'Please select a file and plugin.';
            console.warn('Upload aborted: missing file or plugin');
            return;
        }
        
        uploading = true;
        uploadError = '';
        uploadSuccess = false;
        
        console.log('Upload parameters:', { kbId, fileName: selectedFile.name, fileSize: selectedFile.size, fileType: selectedFile.type, pluginName: selectedPlugin.name, pluginParams });
        
        try {
            const result = await uploadFileWithPlugin(kbId, selectedFile, selectedPlugin.name, pluginParams);
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

    /** Run a non-file (base / remote) ingestion plugin */
    async function runBaseIngestion() {
        console.log('runBaseIngestion invoked for plugin:', selectedPlugin?.name, 'params:', pluginParams);
        if (!selectedPlugin) {
            uploadError = 'Please select a plugin.';
            return;
        }
        // Guard: if plugin actually requires a file (defensive)
        if (selectedPlugin.kind === 'file-ingest') {
            uploadError = 'Selected plugin requires a file.';
            return;
        }
        uploading = true;
        uploadError = '';
        uploadSuccess = false;
        try {
            const result = await runBaseIngestionPlugin(kbId, selectedPlugin.name, pluginParams);
            console.log('Base ingestion result:', result);
            uploadSuccess = true;
            await loadKnowledgeBase(kbId);
        } catch (err) {
            console.error('Error running base ingestion:', err);
            uploadError = err instanceof Error ? err.message : 'Failed to run ingestion plugin';
        } finally {
            uploading = false;
        }
    }

    /** Decide which ingestion path to use based on plugin kind */
    function handleSubmitIngestion() {
        if (!selectedPlugin) {
            uploadError = 'Please select a plugin.';
            return;
        }
        if (selectedPlugin.kind === 'file-ingest') {
            uploadFile();
        } else {
            runBaseIngestion();
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
                    'Authorization': `Bearer ${token}` // Add Authorization header
                },
                // Removed withCredentials to allow wildcard CORS (no credentialed requests needed; we use Bearer token)
            });
            
            console.log('Query response received:', response.data);

            // Process results: remove source field from metadata for security
            const processedResults = response.data.results?.map((/** @type {QueryResultItem} */ result) => {
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
            queryError = axiosError.response?.data?.detail || (axiosError instanceof Error ? axiosError.message : 'An unknown error occurred during query.');
            // Check for server offline based on status or specific message if available
            if (axiosError.response?.status === 503 || (axiosError instanceof Error && axiosError.message.includes('server offline'))) {
                serverOffline = true; // Set server offline flag if query fails due to it
            }
        } finally {
            queryLoading = false;
        }
    }

</script>

<div class="bg-white shadow overflow-hidden sm:rounded-lg">
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
                        <p class="font-bold mb-2">
                            {$_('knowledgeBases.detail.serverOffline', { default: 'Knowledge Base Server Offline' })}
                        </p>
                        <p>
                            {$_('knowledgeBases.detail.tryAgainLater', { default: 'Please try again later or contact an administrator.' })}
                        </p>
                    </div>
                {:else}
                    {error}
                {/if}
            </div>
            <button
                onclick={() => loadKnowledgeBase(kbId)}
                class="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3]"
                style="background-color: #2271b3;"
            >
                {$_('knowledgeBases.detail.retry', { default: 'Retry' })}
            </button>
        </div>
    
    <!-- Success state with KB details -->
    {:else if kb}
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
                    
                    {#if kb.owner}
                    <div class="bg-white px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">
                            {$_('knowledgeBases.detail.ownerLabel', { default: 'Owner' })}
                        </dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            {kb.owner}
                        </dd>
                    </div>
                    {/if}
                    
                    {#if kb.created_at}
                    <div class="bg-gray-50 px-4 py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                        <dt class="text-sm font-medium text-gray-500">
                            {$_('knowledgeBases.detail.createdLabel', { default: 'Created' })}
                        </dt>
                        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                            {new Date(kb.created_at * 1000).toLocaleString()}
                        </dd>
                    </div>
                    {/if}
                    
                    {#if kb.metadata?.access_control}
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

                        <!-- Query Tab -->
                        <button
                            onclick={() => selectTab('query')}
                            class="{activeTab === 'query' ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'} whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm"
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
                            <!-- Refresh button -->
                            <div class="mb-4 flex items-center justify-between">
                                <div class="text-sm text-gray-500">
                                    {#if loadingJobs}
                                        <span class="inline-flex items-center">
                                            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-[#2271b3]" fill="none" viewBox="0 0 24 24">
                                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            Loading status...
                                        </span>
                                    {:else if jobsError}
                                        <span class="text-amber-600">⚠ {jobsError}</span>
                                    {/if}
                                </div>
                                <button
                                    type="button"
                                    onclick={refreshFileStatus}
                                    disabled={loadingJobs}
                                    class="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <svg class="h-4 w-4 mr-1.5 {loadingJobs ? 'animate-spin' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                    {$_('knowledgeBases.detail.refreshStatus', { default: 'Refresh Status' })}
                                </button>
                            </div>
                            
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
                                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {$_('knowledgeBases.detail.fileStatusColumn', { default: 'Status' })}
                                                </th>
                                                <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {$_('knowledgeBases.detail.fileActionsColumn', { default: 'Actions' })}
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody class="bg-white divide-y divide-gray-200">
                                            {#each kb.files as file (file.id)}
                                                {@const job = getJobForFile(file.filename)}
                                                {@const statusColors = job ? getStatusColors(job.status) : getStatusColors('unknown')}
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
                                                    <td class="px-6 py-4 whitespace-nowrap">
                                                        {#if job}
                                                            <button
                                                                type="button"
                                                                onclick={() => openJobModal(job)}
                                                                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ring-1 ring-inset cursor-pointer hover:opacity-80 transition-opacity {statusColors.bg} {statusColors.text} {statusColors.ring}"
                                                                title="Click for details"
                                                            >
                                                                {#if job.status === 'processing'}
                                                                    <svg class="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                                                                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                                                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                                                    </svg>
                                                                {:else if job.status === 'completed'}
                                                                    <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                                                        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                                                                    </svg>
                                                                {:else if job.status === 'failed'}
                                                                    <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                                                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                                                                    </svg>
                                                                {:else if job.status === 'pending'}
                                                                    <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
                                                                    </svg>
                                                                {/if}
                                                                {job.status}
                                                            </button>
                                                        {:else if loadingJobs}
                                                            <span class="text-xs text-gray-400 italic">Loading...</span>
                                                        {:else}
                                                            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-500 ring-1 ring-inset ring-gray-500/10">
                                                                Unknown
                                                            </span>
                                                        {/if}
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
                        {#key selectedPlugin?.kind}
                        <div class="bg-gray-50 -mx-4 -my-5 sm:-mx-6 px-4 py-5 sm:px-6">
                            <h4 class="text-md font-medium text-gray-700 mb-4">
                                {selectedPlugin?.kind === 'file-ingest'
                                    ? $_('knowledgeBases.fileUpload.sectionTitle', { default: 'Upload and Ingest New File' })
                                    : $_('knowledgeBases.fileUpload.sectionTitleBase', { default: 'Configure and Run Ingestion' })}
                            </h4>
                            
                            {#if loadingPlugins}
                                <!-- ... plugin loading indicator ... -->
                            {:else if pluginsError}
                                <!-- ... plugin error display ... -->
                            {:else if plugins.length === 0}
                                <!-- ... no plugins message ... -->
                            {:else}
                                <!-- Ingestion Form -->
                                <form onsubmit={(e) => { e.preventDefault(); handleSubmitIngestion(); }} class="space-y-6">
                                    <!-- File selection (only for file-ingest plugins) -->
                                    {#if selectedPlugin?.kind === 'file-ingest'}
                                        <div>
                                            <label for="file-upload-input-inline" class="block text-sm font-medium text-gray-700">
                                                {$_('knowledgeBases.fileUpload.fileLabel', { default: 'Select File' })}
                                            </label>
                                            <div class="mt-1 flex items-center">
                                                <input
                                                    id="file-upload-input-inline"
                                                    type="file"
                                                    class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-[#2271b3] file:text-white hover:file:bg-[#195a91]"
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
                                    {/if}
                                    
                                    <!-- Plugin selection -->
                                    <div>
                                        <label for="plugin-select-inline" class="block text-sm font-medium text-gray-700">
                                            {$_('knowledgeBases.fileUpload.pluginLabel', { default: 'Ingestion Plugin' })}
                                        </label>
                                        <div class="mt-1">
                                            <select
                                                id="plugin-select-inline"
                                                class="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm rounded-md"
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
                                    
                                    <!-- Plugin warnings (parameters starting with _) -->
                                    {#if selectedPlugin?.parameters}
                                        {#each Object.entries(selectedPlugin.parameters).filter(([name]) => name.startsWith('_')) as [paramName, paramDef] (paramName)}
                                            <div class="p-4 bg-amber-50 border border-amber-200 rounded-md">
                                                <div class="flex items-start">
                                                    <svg class="h-5 w-5 text-amber-400 mr-3 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                                                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                                                    </svg>
                                                    <div>
                                                        <h4 class="text-sm font-medium text-amber-800">
                                                            {paramName.replace(/^_/, '').replace(/_/g, ' ')}
                                                        </h4>
                                                        <p class="mt-1 text-sm text-amber-700">
                                                            {paramDef.description || paramDef.default || ''}
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        {/each}
                                    {/if}
                                    
                                    <!-- Plugin parameters (excluding underscore-prefixed info params) -->
                                    {#if selectedPlugin && selectedPlugin.parameters && visibleParamKeys.length > 0}
                                        <div class="space-y-4 border-t border-gray-200 pt-4">
                                            <h5 class="font-medium text-gray-700">
                                                {$_('knowledgeBases.fileUpload.parametersLabel', { default: 'Plugin Parameters' })}
                                            </h5>
                                            
                                            {#each visibleParamKeys as paramName (paramName)}
                                                {@const paramDef = selectedPlugin.parameters[paramName]}
                                                    <!-- Parameter container with conditional indentation for dependent params -->
                                                    <div class={paramDef.visible_when ? 'ml-6 pl-4 border-l-2 border-gray-200' : ''}>
                                                        <!-- Parameter label with optional controller styling -->
                                                        <label 
                                                            for={`param-${paramName}-inline`} 
                                                            class="block text-sm font-medium {hasVisibleWhenDependents(paramName) ? 'text-[#2271b3]' : 'text-gray-700'}"
                                                        >
                                                            {paramName}
                                                            {paramDef.required ? ' *' : ''}
                                                            {#if paramDef.description}
                                                                <span class="text-xs text-gray-500 ml-1 font-normal">({paramDef.description})</span>
                                                            {/if}
                                                            {#if hasVisibleWhenDependents(paramName)}
                                                                <span class="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-normal">
                                                                    controls options
                                                                </span>
                                                            {/if}
                                                        </label>
                                                        
                                                        <div class="mt-1">
                                                            {#if paramDef.enum && Array.isArray(paramDef.enum)}
                                                                <!-- Render as select dropdown if enum is present -->
                                                                <select
                                                                    id={`param-${paramName}-inline`}
                                                                    class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm {hasVisibleWhenDependents(paramName) ? 'border-[#2271b3] border-2' : ''}"
                                                                    value={pluginParams[paramName]}
                                                                    onchange={(e) => updateParamValue(paramName, e)}
                                                                >
                                                                    {#each paramDef.enum as enumValue}
                                                                        <option value={enumValue} selected={pluginParams[paramName] === enumValue}>
                                                                            {getEnumLabel(paramDef, enumValue)}
                                                                        </option>
                                                                    {/each}
                                                                </select>
                                                            {:else if paramDef.type === 'boolean'}
                                                                <!-- Render as checkbox -->
                                                                <div class="flex items-center">
                                                                    <input
                                                                        id={`param-${paramName}-inline`}
                                                                        type="checkbox"
                                                                        class="h-4 w-4 text-[#2271b3] focus:ring-[#2271b3] border-gray-300 rounded"
                                                                        checked={pluginParams[paramName] === true}
                                                                        onchange={(e) => updateParamValue(paramName, e)}
                                                                    />
                                                                    <label for={`param-${paramName}-inline`} class="ml-2 block text-sm text-gray-900">
                                                                        {paramDef.default ? 'Enabled' : 'Disabled'} by default
                                                                    </label>
                                                                </div>
                                                            {:else if paramDef.type === 'integer' || paramDef.type === 'number'}
                                                                <!-- Render as number input with min/max validation -->
                                                                <input
                                                                    id={`param-${paramName}-inline`}
                                                                    type="number"
                                                                    class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                                                    value={pluginParams[paramName]}
                                                                    placeholder={paramDef.default !== undefined && paramDef.default !== null ? paramDef.default.toString() : ''}
                                                                    min={paramDef.min}
                                                                    max={paramDef.max}
                                                                    onchange={(e) => updateParamValue(paramName, e)}
                                                                />
                                                                {#if paramDef.min !== undefined || paramDef.max !== undefined}
                                                                    <p class="mt-1 text-xs text-gray-500">
                                                                        {#if paramDef.min !== undefined && paramDef.max !== undefined}
                                                                            Range: {paramDef.min} - {paramDef.max}
                                                                        {:else if paramDef.min !== undefined}
                                                                            Minimum: {paramDef.min}
                                                                        {:else}
                                                                            Maximum: {paramDef.max}
                                                                        {/if}
                                                                    </p>
                                                                {/if}
                                                            {:else if paramDef.type === 'array'}
                                                                <!-- Render as textarea for arrays (e.g., URLs) -->
                                                                <textarea
                                                                    id={`param-${paramName}-inline`}
                                                                    rows="3"
                                                                    class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                                                    value={Array.isArray(pluginParams[paramName]) ? pluginParams[paramName].join('\n') : pluginParams[paramName] || ''}
                                                                    placeholder={paramDef.description || 'Enter values, one per line'}
                                                                    onchange={(e) => updateParamValue(paramName, e)} 
                                                                ></textarea>
                                                                <p class="mt-1 text-xs text-gray-500">Enter values separated by new lines.</p>
                                                            {:else if paramDef.type === 'long-string'}
                                                                <!-- Render as textarea for long strings -->
                                                                <textarea
                                                                    id={`param-${paramName}-inline`}
                                                                    rows="4"
                                                                    class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                                                    value={pluginParams[paramName] || ''}
                                                                    placeholder={paramDef.default !== undefined && paramDef.default !== null ? paramDef.default.toString() : (paramDef.description || '')}
                                                                    onchange={(e) => updateParamValue(paramName, e)}
                                                                ></textarea>
                                                            {:else}
                                                                <!-- Render as text input for other types (string, etc.) -->
                                                                <input
                                                                    id={`param-${paramName}-inline`}
                                                                    type="text"
                                                                    class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                                                    value={pluginParams[paramName]}
                                                                    placeholder={paramDef.default !== undefined && paramDef.default !== null ? paramDef.default.toString() : ''}
                                                                    onchange={(e) => updateParamValue(paramName, e)}
                                                                />
                                                            {/if}
                                                        </div>
                                                        
                                                        <!-- Help text display -->
                                                        {#if paramDef.help_text}
                                                            <p class="mt-1 text-xs text-gray-500 italic">{paramDef.help_text}</p>
                                                        {/if}
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
                                        <button
                                            type="submit"
                                            class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] disabled:opacity-50 flex-shrink-0"
                                            style="background-color: #2271b3;"
                                            disabled={(!selectedPlugin) || uploading || (selectedPlugin?.kind === 'file-ingest' && !selectedFile)}
                                        >
                                            {#if uploading}
                                                {$_('knowledgeBases.fileUpload.uploadingButton', { default: 'Uploading...' })}
                                            {:else if selectedPlugin?.kind === 'file-ingest'}
                                                {$_('knowledgeBases.fileUpload.uploadButton', { default: 'Upload File' })}
                                            {:else}
                                                {$_('knowledgeBases.fileUpload.runButton', { default: 'Run Ingestion' })}
                                            {/if}
                                        </button>
                                    </div>
                                </form>
                            {/if}
                        </div>
                        {/key}
                    {/if}

                    <!-- Query Tab Content -->
                    {#if activeTab === 'query'}
                        <div class="space-y-4">
                            <h3 class="text-lg font-medium leading-6 text-gray-900">
                                {$_('knowledgeBases.detail.query.title', { default: 'Query Knowledge Base' })}
                            </h3>
                            
                            <form onsubmit={(e) => { e.preventDefault(); handleQuerySubmit(); }} class="space-y-4">
                                <div>
                                    <label for="query-text" class="block text-sm font-medium text-gray-700">
                                        {$_('knowledgeBases.detail.query.inputLabel', { default: 'Enter your query:' })}
                                    </label>
                                    <textarea 
                                        id="query-text" 
                                        rows="3" 
                                        class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-[#2271b3] focus:border-[#2271b3] sm:text-sm"
                                        bind:value={queryText}
                                        required
                                    ></textarea>
                                </div>
                                
                                <div>
                                    <button 
                                        type="submit"
                                        class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#2271b3] hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] disabled:opacity-50"
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
                                <div class="mt-4 p-4 border rounded-md bg-gray-50 text-center text-gray-500">
                                    {$_('knowledgeBases.detail.query.loadingResults', { default: 'Fetching results...' })}
                                </div>
                            {/if}
                    
                            {#if queryError}
                                <div class="mt-4 p-4 border rounded-md bg-red-50 text-red-700">
                                    <p class="font-bold">{$_('knowledgeBases.detail.query.errorTitle', { default: 'Error:' })}</p>
                                    <pre class="whitespace-pre-wrap text-sm">{queryError}</pre>
                                </div>
                            {/if}
                    
                            {#if queryResult}
                                <div class="mt-4 p-4 border rounded-md bg-blue-50 space-y-4">
                                    <h4 class="text-md font-medium text-gray-900">
                                        {$_('knowledgeBases.detail.query.resultsTitle', { default: 'Query Results:' })}
                                    </h4>
                                    
                                    {#if queryResult.results && queryResult.results.length > 0}
                                        <div class="space-y-6">
                                            {#each queryResult.results as result, i}
                                                <div class="p-4 bg-white rounded-md shadow-sm border border-gray-200">
                                                    
                                                    <!-- File Link (if available) -->
                                                    {#if result.metadata?.file_url && result.metadata?.filename}
                                                        <div class="mb-2 text-sm">
                                                            <a 
                                                                href={result.metadata.file_url} 
                                                                target="_blank" 
                                                                rel="noopener noreferrer"
                                                                class="text-[#2271b3] hover:text-[#195a91] hover:underline font-medium"
                                                                style="color: #2271b3;"
                                                                title={`Open file: ${result.metadata.filename}`}
                                                            >
                                                                
                                                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 inline-block mr-1 -mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                                                                    <path fill-rule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l1.5 1.5a.5.5 0 00.707 0l1.5-1.5a.5.5 0 00-.707-.707l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0l1.5 1.5a.5.5 0 00.707 0l1.5-1.5a.5.5 0 00-.707-.707l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l1.5 1.5a.5.5 0 00.707 0l1.5-1.5a.5.5 0 00-.707-.707l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5a2 2 0 11-2.828-2.828z" clip-rule="evenodd" />
                                                                </svg>
                                                                {result.metadata.filename}
                                                            </a>
                                                        </div>
                                                    {/if}

                                                    <div class="flex justify-between items-start mb-2">
                                                        <h5 class="text-sm font-semibold text-[#2271b3]" style="color: #2271b3;">
                                                            {$_('knowledgeBases.detail.query.resultItemTitle', { default: 'Result' })} {i + 1}
                                                        </h5>
                                                        <span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                                                            {$_('knowledgeBases.detail.query.similarityLabel', { default: 'Similarity:' })} {result.similarity.toFixed(4)}
                                                        </span>
                                                    </div>

                                                    <div class="text-sm text-gray-700 mb-3">
                                                        <p class="font-medium mb-1">{$_('knowledgeBases.detail.query.contentLabel', { default: 'Content:' })}</p>
                                                        <div class="prose prose-sm max-w-none p-2 border rounded bg-gray-50 whitespace-pre-wrap break-words">
                                                            {result.data}
                                                        </div>
                                                    </div>

                                                    <div class="text-xs text-gray-500 border-t pt-2">
                                                        <p class="font-medium mb-1">{$_('knowledgeBases.detail.query.metadataLabel', { default: 'Metadata:' })}</p> 
                                                        <pre class="whitespace-pre-wrap text-xs bg-gray-50 p-2 rounded shadow-inner overflow-x-auto">{JSON.stringify(result.metadata, null, 2)}</pre>
                                                    </div>
                                                </div>
                                            {/each}
                                        </div>
                                    {:else}
                                        <p class="text-sm text-gray-600">{$_('knowledgeBases.detail.query.noResults', { default: 'No relevant results found for your query.' })}</p>
                                    {/if}

                                    <!-- Optional: Keep raw JSON for debugging -->
                                    <details class="text-xs">
                                        <summary class="cursor-pointer text-gray-500 hover:text-gray-700">{$_('knowledgeBases.detail.query.showRawJson', { default: 'Show Raw JSON Response' })}</summary>
                                        <pre class="mt-2 whitespace-pre-wrap text-xs bg-white p-2 rounded shadow-sm overflow-x-auto">{JSON.stringify(queryResult, null, 2)}</pre>
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

<!-- Job Detail Modal -->
{#if showJobModal && selectedJob}
    {@const colors = getStatusColors(selectedJob.status)}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div 
        class="fixed inset-0 z-50 overflow-y-auto" 
        aria-labelledby="modal-title" 
        role="dialog" 
        aria-modal="true"
    >
        <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center">
            <!-- Background overlay -->
            <div 
                class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" 
                aria-hidden="true"
                onclick={closeJobModal}
            ></div>

            <!-- Modal panel -->
            <div class="relative bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all w-full max-w-2xl mx-4">
                <!-- Modal header -->
                <div class="bg-gray-50 px-4 py-4 sm:px-6 border-b border-gray-200">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <h3 class="text-lg leading-6 font-semibold text-gray-900" id="modal-title">
                                {$_('knowledgeBases.detail.jobModal.title', { default: 'Ingestion Job Details' })}
                            </h3>
                            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ring-1 ring-inset {colors.bg} {colors.text} {colors.ring}">
                                {selectedJob.status}
                            </span>
                        </div>
                        <button
                            type="button"
                            onclick={closeJobModal}
                            class="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-[#2271b3]"
                        >
                            <span class="sr-only">Close</span>
                            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>

                <!-- Modal body -->
                <div class="px-4 py-5 sm:px-6 max-h-[60vh] overflow-y-auto">
                    <!-- File info -->
                    <div class="mb-6">
                        <h4 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">File Information</h4>
                        <dl class="grid grid-cols-2 gap-x-4 gap-y-3">
                            <div>
                                <dt class="text-xs text-gray-500">Filename</dt>
                                <dd class="mt-0.5 text-sm font-medium text-gray-900">{selectedJob.original_filename}</dd>
                            </div>
                            <div>
                                <dt class="text-xs text-gray-500">Size</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">{selectedJob.file_size ? formatFileSize(selectedJob.file_size) : 'N/A'}</dd>
                            </div>
                            <div>
                                <dt class="text-xs text-gray-500">Content Type</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">{selectedJob.content_type || 'N/A'}</dd>
                            </div>
                            <div>
                                <dt class="text-xs text-gray-500">Plugin</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">{selectedJob.plugin_name}</dd>
                            </div>
                        </dl>
                    </div>

                    <!-- Processing info -->
                    <div class="mb-6">
                        <h4 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">Processing Details</h4>
                        <dl class="grid grid-cols-2 gap-x-4 gap-y-3">
                            <div>
                                <dt class="text-xs text-gray-500">Job ID</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">#{selectedJob.id}</dd>
                            </div>
                            <div>
                                <dt class="text-xs text-gray-500">Documents Created</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">{selectedJob.document_count || 0}</dd>
                            </div>
                            <div>
                                <dt class="text-xs text-gray-500">Created</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">{formatDate(selectedJob.created_at)}</dd>
                            </div>
                            <div>
                                <dt class="text-xs text-gray-500">Duration</dt>
                                <dd class="mt-0.5 text-sm text-gray-900">{formatDuration(selectedJob.processing_duration_seconds)}</dd>
                            </div>
                            {#if selectedJob.processing_started_at}
                                <div>
                                    <dt class="text-xs text-gray-500">Started</dt>
                                    <dd class="mt-0.5 text-sm text-gray-900">{formatDate(selectedJob.processing_started_at)}</dd>
                                </div>
                            {/if}
                            {#if selectedJob.processing_completed_at}
                                <div>
                                    <dt class="text-xs text-gray-500">Completed</dt>
                                    <dd class="mt-0.5 text-sm text-gray-900">{formatDate(selectedJob.processing_completed_at)}</dd>
                                </div>
                            {/if}
                        </dl>
                    </div>

                    <!-- Progress info (if available) -->
                    {#if selectedJob.progress && selectedJob.status === 'processing'}
                        <div class="mb-6">
                            <h4 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">Progress</h4>
                            <div class="w-full bg-gray-200 rounded-full h-2.5 mb-2">
                                <div class="bg-[#2271b3] h-2.5 rounded-full transition-all duration-300" style="width: {selectedJob.progress.percentage || 0}%"></div>
                            </div>
                            <p class="text-sm text-gray-600">{selectedJob.progress.message || `${selectedJob.progress.current || 0} / ${selectedJob.progress.total || 0}`}</p>
                        </div>
                    {/if}

                    <!-- Processing Statistics (only for completed jobs with stats) -->
                    {#if selectedJob.processing_stats}
                        {@const stats = selectedJob.processing_stats}
                        <div class="mb-6">
                            <h4 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <svg class="h-4 w-4 text-[#2271b3]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                                </svg>
                                Processing Statistics
                            </h4>
                            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                <dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                                    <div>
                                        <dt class="text-xs text-blue-600">Content Length</dt>
                                        <dd class="font-medium text-blue-900">{formatNumber(stats.content_length)} characters</dd>
                                    </div>
                                    {#if stats.chunk_stats}
                                        <div>
                                            <dt class="text-xs text-blue-600">Chunks</dt>
                                            <dd class="font-medium text-blue-900">{stats.chunk_stats.count} (avg {Math.round(stats.chunk_stats.avg_size)} chars)</dd>
                                        </div>
                                    {/if}
                                    {#if stats.chunking_strategy}
                                        <div>
                                            <dt class="text-xs text-blue-600">Chunking Strategy</dt>
                                            <dd class="font-medium text-blue-900">{stats.chunking_strategy}</dd>
                                        </div>
                                    {/if}
                                    <div>
                                        <dt class="text-xs text-blue-600">Images Extracted</dt>
                                        <dd class="font-medium text-blue-900">{stats.images_extracted}</dd>
                                    </div>
                                    {#if stats.llm_calls && stats.llm_calls.length > 0}
                                        <div>
                                            <dt class="text-xs text-blue-600">LLM API Calls</dt>
                                            <dd class="font-medium text-blue-900">{stats.llm_calls.length} ({stats.images_with_llm_descriptions} successful)</dd>
                                        </div>
                                        <div>
                                            <dt class="text-xs text-blue-600">Total LLM Time</dt>
                                            <dd class="font-medium text-blue-900">{formatMilliseconds(stats.total_llm_duration_ms)}</dd>
                                        </div>
                                    {/if}
                                </dl>

                                <!-- LLM Call Details (expandable) -->
                                {#if stats.llm_calls && stats.llm_calls.length > 0}
                                    <details class="mt-3 text-xs">
                                        <summary class="cursor-pointer text-blue-700 hover:text-blue-900 font-medium">Show LLM call details ({stats.llm_calls.length} calls)</summary>
                                        <div class="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                                            {#each stats.llm_calls as call, i}
                                                <div class="flex justify-between items-center bg-white/50 rounded px-2 py-1 {call.success ? '' : 'text-red-600'}">
                                                    <span class="font-mono truncate flex-1">{call.image}</span>
                                                    <span class="ml-2 whitespace-nowrap">
                                                        {formatMilliseconds(call.duration_ms)}
                                                        {#if call.tokens_used}
                                                            <span class="text-blue-500 ml-1">({call.tokens_used} tokens)</span>
                                                        {/if}
                                                        {#if !call.success}
                                                            <span class="text-red-500 ml-1">✗</span>
                                                        {:else}
                                                            <span class="text-green-500 ml-1">✓</span>
                                                        {/if}
                                                    </span>
                                                </div>
                                            {/each}
                                        </div>
                                    </details>
                                {/if}
                            </div>
                        </div>

                        <!-- Processing Log / Stage Timings -->
                        {#if stats.stage_timings && stats.stage_timings.length > 0}
                            <div class="mb-6">
                                <h4 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                    Processing Log
                                </h4>
                                <div class="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden">
                                    <table class="min-w-full text-sm divide-y divide-gray-200">
                                        <thead class="bg-gray-100">
                                            <tr>
                                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Stage</th>
                                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                                            </tr>
                                        </thead>
                                        <tbody class="divide-y divide-gray-200">
                                            {#each stats.stage_timings as stage}
                                                <tr>
                                                    <td class="px-3 py-2 font-medium text-gray-900 capitalize">{stage.stage.replace(/_/g, ' ')}</td>
                                                    <td class="px-3 py-2 text-gray-600 font-mono">{formatMilliseconds(stage.duration_ms)}</td>
                                                    <td class="px-3 py-2 text-gray-600">{stage.message}</td>
                                                </tr>
                                            {/each}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        {/if}

                        <!-- Output Files / Artifacts -->
                        {#if stats.output_files && (stats.output_files.markdown_url || stats.output_files.images_folder_url || stats.output_files.original_file_url)}
                            <div class="mb-6">
                                <h4 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <svg class="h-4 w-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                                    </svg>
                                    Output Artifacts
                                </h4>
                                <div class="flex flex-wrap gap-2">
                                    {#if stats.output_files.markdown_url}
                                        <a 
                                            href={stats.output_files.markdown_url} 
                                            target="_blank" 
                                            rel="noopener noreferrer"
                                            class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md hover:bg-emerald-100 transition-colors text-sm"
                                        >
                                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                            </svg>
                                            Markdown
                                        </a>
                                    {/if}
                                    {#if stats.output_files.images_folder_url}
                                        <a 
                                            href={stats.output_files.images_folder_url} 
                                            target="_blank" 
                                            rel="noopener noreferrer"
                                            class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-50 text-purple-700 border border-purple-200 rounded-md hover:bg-purple-100 transition-colors text-sm"
                                        >
                                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                                            </svg>
                                            Images ({stats.images_extracted})
                                        </a>
                                    {/if}
                                    {#if stats.output_files.original_file_url}
                                        <a 
                                            href={stats.output_files.original_file_url} 
                                            target="_blank" 
                                            rel="noopener noreferrer"
                                            class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 text-gray-700 border border-gray-200 rounded-md hover:bg-gray-100 transition-colors text-sm"
                                        >
                                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                                            </svg>
                                            Original
                                        </a>
                                    {/if}
                                </div>
                            </div>
                        {/if}

                        <!-- Markdown Preview -->
                        {#if stats.markdown_preview}
                            <div class="mb-6">
                                <details class="text-sm">
                                    <summary class="cursor-pointer text-gray-500 hover:text-gray-700 font-medium flex items-center gap-2">
                                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                                        </svg>
                                        Markdown Preview (first 2000 chars)
                                    </summary>
                                    <pre class="mt-2 whitespace-pre-wrap text-xs bg-gray-800 text-gray-100 p-4 rounded-lg overflow-x-auto max-h-64 font-mono leading-relaxed">{stats.markdown_preview}</pre>
                                </details>
                            </div>
                        {/if}
                    {/if}

                    <!-- Error info (if failed) -->
                    {#if selectedJob.status === 'failed' && (selectedJob.error_message || selectedJob.error_details)}
                        <div class="mb-6">
                            <h4 class="text-sm font-medium text-red-600 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                                </svg>
                                Error Details
                            </h4>
                            <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                                {#if selectedJob.error_message}
                                    <p class="text-sm text-red-800 font-medium mb-2">{selectedJob.error_message}</p>
                                {/if}
                                {#if selectedJob.error_details}
                                    <details class="text-xs">
                                        <summary class="cursor-pointer text-red-700 hover:text-red-900 font-medium">Show technical details</summary>
                                        <pre class="mt-2 whitespace-pre-wrap text-xs bg-red-100 text-red-900 p-3 rounded overflow-x-auto">{JSON.stringify(selectedJob.error_details, null, 2)}</pre>
                                    </details>
                                {/if}
                            </div>
                        </div>
                    {/if}

                    <!-- Plugin parameters (collapsed by default) -->
                    {#if selectedJob.plugin_params && Object.keys(selectedJob.plugin_params).length > 0}
                        <div class="mb-4">
                            <details class="text-sm">
                                <summary class="cursor-pointer text-gray-500 hover:text-gray-700 font-medium">Plugin Parameters</summary>
                                <pre class="mt-2 whitespace-pre-wrap text-xs bg-gray-50 text-gray-700 p-3 rounded overflow-x-auto">{JSON.stringify(selectedJob.plugin_params, null, 2)}</pre>
                            </details>
                        </div>
                    {/if}
                </div>

                <!-- Modal footer -->
                <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse border-t border-gray-200 gap-2">
                    <!-- Refresh button -->
                    <button
                        type="button"
                        onclick={refreshSelectedJob}
                        disabled={jobActionLoading}
                        class="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] sm:w-auto sm:text-sm disabled:opacity-50"
                        title="Refresh job status"
                    >
                        <svg class="h-4 w-4 {jobActionLoading ? 'animate-spin' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                    </button>
                    
                    {#if selectedJob.status === 'failed' && kb?.can_modify === true}
                        <button
                            type="button"
                            onclick={() => selectedJob && handleRetryJob(selectedJob.id)}
                            disabled={jobActionLoading}
                            class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-[#2271b3] text-base font-medium text-white hover:bg-[#195a91] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
                        >
                            {#if jobActionLoading}
                                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            {/if}
                            Retry Ingestion
                        </button>
                    {/if}
                    {#if (selectedJob.status === 'pending' || selectedJob.status === 'processing') && kb?.can_modify === true}
                        <button
                            type="button"
                            onclick={() => selectedJob && handleCancelJob(selectedJob.id)}
                            disabled={jobActionLoading}
                            class="w-full inline-flex justify-center rounded-md border border-red-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
                        >
                            Cancel Job
                        </button>
                    {/if}
                    <button
                        type="button"
                        onclick={closeJobModal}
                        class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2271b3] sm:mt-0 sm:w-auto sm:text-sm"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    </div>
{/if}