<script>
    import AssistantsList from '$lib/components/AssistantsList.svelte';
    import AssistantForm from '$lib/components/assistants/AssistantForm.svelte'; 
    import ChatInterface from '$lib/components/ChatInterface.svelte';
    import MCPTesting from '$lib/components/MCPTesting.svelte';
    import { _, locale } from '$lib/i18n';
    import DuplicateAssistantModal from '$lib/components/modals/DuplicateAssistantModal.svelte'; // Placeholder for modal
    import DeleteConfirmationModal from '$lib/components/modals/DeleteConfirmationModal.svelte'; // Import delete modal
    import { onMount, onDestroy } from 'svelte';
    import { page } from '$app/stores'; // Import page store to read URL params
    import { getAssistantById, createAssistant, deleteAssistant, setAssistantPublishStatus } from '$lib/services/assistantService'; // Import service
    import { getKnowledgeBases } from '$lib/services/knowledgeBaseService'; // <<< Import KB service
    import { fetchRubricMarkdown } from '$lib/services/rubricService'; // <<< Import rubric service
    import { goto } from '$app/navigation'; // <<< Add import for goto
    import { base } from '$app/paths'; // <<< Add import for base path
    import { writable } from 'svelte/store'; // Import from svelte/store instead of type import
    import { getConfig } from '$lib/config'; // <<< Import config helper
    import { browser } from '$app/environment'; // <<< Import browser

    // --- State Management --- 
    /** @type {'list' | 'create' | 'detail' | 'mcp'} */
    let currentView = $state('list'); // Revert back to 'list'
    /** @type {string | null | undefined} */
    let currentLocale = $state(null);
    /** @type {any | null} */ // Revert to 'any' as workaround for persistent type issues
    let selectedAssistantData = $state(null);
    /** @type {number | null} */
    let lastAttemptedId = $state(null); // Correct Svelte 5 rune syntax
    let loadingDetail = $state(false); 
    let detailError = $state('');
    /** @type {boolean} */
    let startEditMode = $state(false); // New state for initial edit mode

    // --- Detail View Sub-Tab State ---
    /** @type {'properties' | 'chat' | 'edit'} */
    let detailSubView = $state($page.url.searchParams.get('startInEdit') === 'true' ? 'edit' : 'properties');

    // --- API Configuration State ---
    let lambServerUrl = $state('');
    // Note: lambApiKey removed for security - now using user authentication tokens
    let userToken = $state('');
    let configError = $state('');

    // --- URL Handling --- 
    /** @type {Function|null} */
    let unsubscribePage = null;

    // --- Duplicate State ---
    let isDuplicateModalOpen = $state(false);
    /** @type {number | null} */
    let assistantToDuplicateId = $state(null);
    /** @type {string | null} */
    let assistantToDuplicateName = $state(null); // Original name for display
    /** @type {any | null} */
    let assistantToDuplicateData = $state(null); // Full data fetched for duplication
    let isFetchingDuplicateDetails = $state(false);
    let isSubmittingDuplicate = $state(false); // For modal submission loading
    let defaultDuplicateName = $state('');
    let duplicateError = $state('');

    // --- Delete State ---
    let isDeleteModalOpen = $state(false);
    /** @type {number | null} */
    let assistantToDeleteId = $state(null);
    /** @type {string | null} */
    let assistantToDeleteName = $state(null);
    let isDeletingAssistant = $state(false);
    let deleteError = $state(''); // For errors displayed in the delete modal

    // --- Export State ---
    let isExporting = $state(false);
    /** @type {number | null} */
    let exportingId = $state(null);

    // --- Publish State ---
    let isPublishing = $state(false);
    let publishError = $state('');

    // --- Knowledge Base State (for detail view) ---
    /** @type {import('$lib/services/knowledgeBaseService').KnowledgeBase[]} */
	let accessibleKnowledgeBases = $state([]);
	let loadingKnowledgeBases = $state(false);
	let knowledgeBaseError = $state('');
	let kbFetchTriggered = $state(false); // Flag to ensure fetch runs only once per applicable assistant load

    // --- Rubric State (for detail view) ---
    let rubricMarkdown = $state('');
    let loadingRubric = $state(false);
    let rubricError = $state('');
    let rubricFetchTriggered = $state(false);

    // --- Functions --- 
    /** Sets the view to the assistant creation form */
    function showCreateForm() {
        console.log("Navigating to create form");
        selectedAssistantData = null; // Clear any selected data
        currentView = 'create';
        startEditMode = false; // Ensure not starting in edit for create
        // Navigate to assistants path with query param
        goto(`${base}/assistants?view=create`, { replaceState: true });
    }

    /** Sets the view to MCP Testing */
    function showMCPTesting() {
        console.log("Navigating to MCP Testing");
        selectedAssistantData = null; // Clear any selected data
        currentView = 'mcp';
        startEditMode = false; // Reset edit mode flag
        detailSubView = 'properties'; // Reset detail sub-view
        // Navigate to assistants path with query param
        goto(`${base}/assistants?view=mcp`, { replaceState: true });
    }

    /** Sets the view back to the list */
    function showList() {
        console.log("Navigating back to list view (assistants base path)");
        currentView = 'list';
        startEditMode = false; // Ensure not starting in edit for list
        // Navigate to assistants base path without query params
        goto(`${base}/assistants`, { replaceState: true });
    }

    /** Fetches assistant details */
    /** @param {number} id */
    // Remove shouldStartInEdit parameter
    async function fetchAssistantDetail(id) { 
        if (lastAttemptedId === id) return; // Simpler check now
        lastAttemptedId = id;
        // startEditMode is already set by the subscription callback
        loadingDetail = true;
        detailError = '';
        selectedAssistantData = null;
        currentView = 'detail';

        try {
            console.log(`Fetching assistant ID: ${id}.`); // Removed edit log here
            const assistantData = await getAssistantById(id);
            if (assistantData) {
                // Parse metadata (fallback to api_callback for backward compatibility)
                let parsedCallbackData = {};
                const metadataStr = assistantData.metadata || assistantData.api_callback;
                if (metadataStr) {
                    try {
                        parsedCallbackData = JSON.parse(metadataStr);
                    } catch (e) { console.error("Error parsing metadata JSON:", e); }
                }
                // Merge assistant data with parsed callback data
                const fullAssistantData = { 
                    ...assistantData, 
                    ...parsedCallbackData, 
                    id: assistantData.id.toString() // Ensure ID is string and overwrites any potential callback ID
                };
                selectedAssistantData = fullAssistantData;
                console.log("Assigned selectedAssistantData:", selectedAssistantData);
                // Update URL (remove startInEdit param if it was there) - this is fine now
                goto(`${base}/assistants?view=detail&id=${id}`, { replaceState: true, noScroll: true });
            } else {
                detailError = $_('assistant_not_found', { values: { id } });
                console.error(detailError);
                showList();
            }
        } catch (error) {
            console.error('Error fetching assistant details:', error);
            detailError = error instanceof Error ? error.message : $_('error_fetching_assistant');
            showList();
        } finally {
            loadingDetail = false;
        }
    }

    // --- Lifecycle --- 
    onMount(() => {
        console.log("Assistants page mounted");
        // Load config
        try {
            const config = getConfig();
            console.log('[DEBUG] Assistants page onMount: Config object received:', JSON.stringify(config, null, 2));
            if (config && config.api && config.api.baseUrl) {
                lambServerUrl = config.api.lambServer.replace(/\/$/, ''); // Remove trailing slash  
                console.log("LAMB config loaded for chat - API URL:", lambServerUrl);
                console.log("LAMB config loaded for chat - Using user authentication");
            } else {
                throw new Error('Missing required LAMB configuration (baseUrl).');
            }
        } catch (error) {
            configError = error instanceof Error ? error.message : 'Failed to load LAMB configuration.';
            console.error(configError);
            // Optionally disable chat tab if config fails
        }

        // Initialize user token from localStorage
        if (browser) {
            userToken = localStorage.getItem('userToken') || '';
            if (userToken) {
                console.log("User token loaded for chat authentication");
            } else {
                console.warn("No user token found - chat functionality may be limited");
            }
        }

        currentLocale = $locale ?? null; // Handle potential undefined value from $locale

        unsubscribePage = page.subscribe(currentPage => {
            console.log("Page store updated:", currentPage.url.searchParams.toString());
            const viewParam = currentPage.url.searchParams.get('view');
            const idParam = currentPage.url.searchParams.get('id');
            const startInEditParam = currentPage.url.searchParams.get('startInEdit');
            console.log(`[+page.svelte] URL Params: view=${viewParam}, id=${idParam}, startInEdit=${startInEditParam}`);
            
            const requestedStartEdit = startInEditParam === 'true';
            console.log(`[+page.svelte] requestedStartEdit evaluated to: ${requestedStartEdit}`);

            if (viewParam === 'create') {
                if (currentView !== 'create') {
                    console.log("URL indicates 'create' view.");
                    showCreateForm();
                }
            } else if (viewParam === 'mcp') {
                if (currentView !== 'mcp') {
                    console.log("URL indicates 'mcp' view.");
                    currentView = 'mcp';
                }
            } else if (viewParam === 'detail' && idParam) { 
                const assistantId = parseInt(idParam, 10);
                if (!isNaN(assistantId)) {
                    // Always update the desired edit mode state based on the URL
                    startEditMode = requestedStartEdit;
                    console.log(`[+page.svelte] Set startEditMode state to: ${startEditMode}`);

                    // Set the view to detail if not already there
                    if (currentView !== 'detail') {
                        currentView = 'detail';
                        detailSubView = 'properties'; // Reset subview when entering detail
                    }
                    
                    // Fetch only if the ID is different from the currently loaded one
                    if (selectedAssistantData?.id !== assistantId.toString()) {
                        console.log(`[+page.svelte] Fetching detail for new ID: ${assistantId}`); 
                        fetchAssistantDetail(assistantId); // Call without edit flag
                    } else {
                         console.log(`[+page.svelte] ID ${assistantId} already loaded. Skipping fetch.`);
                         // Ensure loading state is false if we skip fetch but are in detail view
                         loadingDetail = false;
                    }
                } else {
                    console.warn('Invalid assistant ID in URL parameter.');
                    showList();
                }
            } else if (currentView !== 'list') {
                console.log("URL indicates 'list' view.");
                showList();
            }
        });
    });

    onDestroy(() => {
        console.log("Assistants page unmounting");
        if (unsubscribePage) {
            unsubscribePage();
        }
    });

    // --- Reactive Effects --- 
    $effect(() => {
        // Update locale if it changes in the store
        if (($locale ?? null) !== currentLocale) { // Also handle potential undefined here
            console.log(`Locale changed from ${currentLocale} to ${$locale}`);
            currentLocale = $locale ?? null;
        }
    });

    // Effect to handle programmatic navigation to detail view (e.g., after creation)
    /**
     * Handles the custom event dispatched when an assistant is successfully created.
     * Navigates to the list view.
     * @param {CustomEvent<{ assistantId: number }>} event - The custom event containing the new assistant's ID.
     */
    function handleAssistantCreated(event) {
        // Add check for event.detail
        if (event.detail && typeof event.detail.assistantId === 'number') {
            const newAssistantId = event.detail.assistantId;
            console.log(`Assistant created with ID: ${newAssistantId}, navigating to list view.`);
            // Navigate to assistants base path without query params
            goto(`${base}/assistants`, { replaceState: true });
        } else {
            console.error('handleAssistantCreated received event without expected detail:', event);
            // Optionally show an error message to the user or navigate to list view
            detailError = 'Failed to navigate to new assistant. Event detail missing.'; 
            showList(); // Go back to list as a fallback
        }
    }

    /**
     * Handles the custom event dispatched when an assistant is successfully updated.
     * Navigates back to the list view.
     * @param {CustomEvent<{ assistantId: number }>} event - The custom event containing the updated assistant's ID.
     */
    function handleAssistantUpdated(event) {
        const updatedAssistantId = event.detail.assistantId;
        console.log(`Assistant updated with ID: ${updatedAssistantId}, navigating back to list view.`);
        showList(); 
    }

    /**
     * Handles the request to duplicate an assistant. Fetches details and opens the modal.
     * @param {CustomEvent<{ id: number, name: string }>} event - The custom event from AssistantsList.
     */
    async function handleDuplicateRequest(event) {
        const { id, name } = event.detail;
        console.log(`Duplicate request received for ID: ${id}, Name: ${name}`);

        assistantToDuplicateId = id;
        assistantToDuplicateName = name;
        assistantToDuplicateData = null; // Clear previous data
        isFetchingDuplicateDetails = true;
        isDuplicateModalOpen = false; // Ensure modal is closed initially
        duplicateError = '';

        try {
            // Fetch full details required for duplication
            const fullData = await getAssistantById(id);
            if (fullData) {
                assistantToDuplicateData = fullData;
                // Prepare default name, stripping potential creator prefix if needed for display
                const baseName = name.includes('_') ? name.substring(name.indexOf('_') + 1) : name;
                defaultDuplicateName = `Copy_${baseName}`;
                isDuplicateModalOpen = true; // Open modal only after successful fetch
            } else {
                throw new Error(`Assistant with ID ${id} not found.`);
            }
        } catch (error) {
            console.error('Error fetching assistant details for duplication:', error);
            duplicateError = error instanceof Error ? error.message : $_('error_fetching_assistant');
            // Optionally display this error to the user via a toast/notification
            alert(`Error preparing duplication: ${duplicateError}`); // Simple alert for now
        } finally {
            isFetchingDuplicateDetails = false;
        }
    }

    /**
     * Handles the submission of the duplicate assistant modal.
     * Creates a new assistant using the data from the original and the new name.
     * @param {CustomEvent<{ newName: string }>} event
     */
    async function handleDuplicateSubmit(event) {
        const newName = event.detail.newName;
        if (!assistantToDuplicateData || !newName) {
            duplicateError = 'Missing data for duplication.'; // Should not happen
            return;
        }

        isSubmittingDuplicate = true;
        duplicateError = '';

        try {
            // Prepare the data for the new assistant
            // Use all relevant fields from the original assistant data
            const originalData = assistantToDuplicateData;
            const newData = {
                name: newName, // Use the new name provided by the user
                description: originalData.description || '',
                // Use system_prompt first, fallback to instructions if needed (as per backend logic)
                system_prompt: originalData.system_prompt || originalData.instructions || '',
                prompt_template: originalData.prompt_template || '',
                                    metadata: originalData.metadata || originalData.api_callback || '',
                pre_retrieval_endpoint: originalData.pre_retrieval_endpoint || '',
                post_retrieval_endpoint: originalData.post_retrieval_endpoint || '',
                RAG_endpoint: originalData.RAG_endpoint || '',
                RAG_Top_k: originalData.RAG_Top_k ?? 3, // Use ?? for nullish coalescing
                RAG_collections: originalData.RAG_collections || ''
            };

            console.log('Creating duplicate assistant with data:', newData);
            const createResponse = await createAssistant(newData);

            if (createResponse && createResponse.assistant_id) {
                console.log('Duplicate created successfully, ID:', createResponse.assistant_id);
                // Close modal and reset state
                isDuplicateModalOpen = false;
                assistantToDuplicateId = null;
                assistantToDuplicateData = null;
                assistantToDuplicateName = null;
                defaultDuplicateName = '';
                // Optionally refresh the list or add locally before navigation
                // For simplicity, navigate directly
                goto(`${base}/assistants?view=detail&id=${createResponse.assistant_id}`, { replaceState: true });
            } else {
                throw new Error('Create operation did not return a valid assistant ID.');
            }
        } catch (error) {
            console.error('Error creating duplicate assistant:', error);
            duplicateError = error instanceof Error ? error.message : $_('assistants.duplicateModal.submitError', { default: 'Failed to create duplicate.' });
            // Keep modal open to show error
        } finally {
            isSubmittingDuplicate = false;
        }
    }

    /**
     * Handles the delete request from list or detail view.
     * Checks if the assistant is published and opens the confirmation modal.
     * @param {object} detail - Details of the assistant to delete.
     * @param {number} detail.id
     * @param {string} detail.name
     * @param {boolean | null | undefined} detail.published
     */
    function handleDeleteRequest({ detail }) { 
        const { id, name, published } = detail;
        console.log(`Delete request received for ID: ${id}, Name: ${name}, Published: ${published}`);

        if (published) {
            alert(currentLocale ? $_('assistants.deleteErrorPublished') : 'Cannot delete a published assistant. Please unpublish it first.');
            return;
        }

        // Set state for the modal
        assistantToDeleteId = id;
        assistantToDeleteName = name;
        deleteError = ''; // Clear previous errors
        isDeleteModalOpen = true;
    }

    /**
     * Handles the confirmation of the delete action.
     */
    async function handleDeleteConfirm() {
        console.log('[Delete Modal] handleDeleteConfirm called');
        if (!assistantToDeleteId) {
            console.log('[Delete Modal] No assistantToDeleteId, aborting delete');
            return;
        }

        isDeletingAssistant = true;
        deleteError = '';

        try {
            console.log(`[Delete Modal] Attempting to delete assistant ID: ${assistantToDeleteId}`);
            await deleteAssistant(assistantToDeleteId);
            console.log(`[Delete Modal] Assistant ${assistantToDeleteId} deleted successfully.`);

            // Close modal and reset state
            isDeleteModalOpen = false;
            const deletedId = assistantToDeleteId;
            assistantToDeleteId = null;
            assistantToDeleteName = null;

            // Check if we were deleting the currently viewed assistant
            if (currentView === 'detail' && selectedAssistantData?.id === deletedId.toString()) {
                // If deleting from detail view, navigate back to list
                console.log('[Delete Modal] Deleted from detail view, navigating to list');
                showList(); 
            } else {
                // If deleting from list view, reload the current page of the list
                console.log('[Delete Modal] Deleted from list view, navigating to list');
                showList(); 
                // Alternatively: await loadPaginatedAssistants(currentPage, ITEMS_PER_PAGE); // requires currentPage and ITEMS_PER_PAGE from AssistantsList
            }

            // Optional: Show success message (e.g., toast notification)

        } catch (error) {
            console.error(`[Delete Modal] Error deleting assistant ${assistantToDeleteId}:`, error);
            deleteError = error instanceof Error ? error.message : $_('assistants.deleteModal.deleteError', { default: 'Failed to delete assistant.' });
            // Keep modal open to show error
        } finally {
            isDeletingAssistant = false;
            console.log('[Delete Modal] handleDeleteConfirm finished');
        }
    }

    /**
     * Extracts filename from Content-Disposition header.
     * @param {string | null} dispositionHeader
     * @returns {string} The filename or a default value.
     */
    function getFilenameFromDisposition(dispositionHeader) {
        if (!dispositionHeader) return 'assistant_export.json';
        const filenameMatch = dispositionHeader.match(/filename=["']?([^"';]+)["']?/);
        return filenameMatch?.[1] || 'assistant_export.json';
    }

    /**
     * Handles the export request from list or detail view.
     * Calls the backend export endpoint and triggers download.
     * @param {object} detail - Details of the assistant to export.
     * @param {number} detail.id
     */
    async function handleExportRequest({ detail }) {
        const { id } = detail;
        console.log(`Export request received for ID: ${id}`);

        if (isExporting) return; // Prevent concurrent exports

        exportingId = id;
        isExporting = true;
        let userToken = null;

        try {
            // Get token
            if (browser) {
                userToken = localStorage.getItem('userToken');
            }
            if (!userToken) {
                throw new Error('Authentication token not found.');
            }

            // Get base URL (handle potential issues getting config)
            let serverUrl = '';
            try {
                const config = getConfig();
                serverUrl = config?.api?.lambServer;
                if (!serverUrl) throw new Error(); // Trigger catch block
            } catch (configErr) {
                 console.error('Failed to get server URL from config for export');
                 throw new Error('Configuration error, cannot determine export URL.');
            }

            const exportUrl = `${serverUrl.replace(/\/$/, '')}/creator/assistant/export/${id}`;
            console.log(`Fetching export from: ${exportUrl}`);

            // Make authenticated request
            const response = await fetch(exportUrl, {
                headers: {
                    'Authorization': `Bearer ${userToken}`
                }
            });

            if (!response.ok) {
                let errorDetail = `Failed to export assistant ${id}`;
                try {
                  const errorData = await response.json();
                  errorDetail = errorData?.detail || `${errorDetail} (Status: ${response.status})`;
                } catch (e) {
                    errorDetail = `${errorDetail} (Status: ${response.status})`;
                }
                throw new Error(errorDetail);
            }

            // Get filename from header
            const disposition = response.headers.get('Content-Disposition');
            const filename = getFilenameFromDisposition(disposition);

            // Get data as blob
            const blob = await response.blob();

            // Create download link and trigger click
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            console.log(`Successfully triggered download for ${filename}`);

        } catch (error) {
            console.error('Error during assistant export:', error);
            alert(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            isExporting = false;
            exportingId = null;
        }
    }

    /**
     * Handles toggling the publish status of the currently viewed assistant.
     */
    async function handlePublishToggle() {
        if (!selectedAssistantData || !selectedAssistantData.id) return;
        
        const assistantId = parseInt(selectedAssistantData.id, 10);
        const currentStatus = selectedAssistantData.published;
        const desiredStatus = !currentStatus;
        
        isPublishing = true;
        publishError = '';
        let userToken = null;

        try {
            if (browser) {
                userToken = localStorage.getItem('userToken');
            }
            if (!userToken) {
                throw new Error('Authentication token not found.');
            }
            
            console.log(`Attempting to set publish status for ${assistantId} to ${desiredStatus}`);
            const updatedAssistant = await setAssistantPublishStatus(assistantId, desiredStatus);

            // Update the local state with the full response from the API
            selectedAssistantData = updatedAssistant;
            console.log('Publish status updated successfully.');

            // Optional: Show success message (e.g., toast)

        } catch (error) {
            console.error('Error toggling publish status:', error);
            publishError = error instanceof Error ? error.message : 'Failed to update publish status.';
            // Display error to user (e.g., alert or inline message)
            alert(`Error: ${publishError}`); 
        } finally {
            isPublishing = false;
        }
    }

    /** Fetches accessible knowledge bases if needed for the detail view */
	async function fetchKnowledgeBasesForDetail() {
		if (loadingKnowledgeBases || kbFetchTriggered) return; // Don't refetch if loading or already triggered for this assistant

        // Check if the currently displayed assistant uses simple_rag
        let ragProcessor = '';
        const metadataStr = selectedAssistantData?.metadata || selectedAssistantData?.api_callback;
        if (metadataStr) {
            try {
                const callbackData = JSON.parse(metadataStr);
                ragProcessor = callbackData.rag_processor;
            } catch(e) {
                console.error("Error parsing metadata for KB fetch check:", e);
            }
        }

		if (ragProcessor !== 'simple_rag') {
			console.log('Skipping KB fetch for detail view (not simple_rag)');
            accessibleKnowledgeBases = []; // Clear if not needed
            knowledgeBaseError = '';
            kbFetchTriggered = true; // Mark as checked for this load
			return;
		}

		console.log('Fetching knowledge bases for detail view...');
		loadingKnowledgeBases = true;
		knowledgeBaseError = '';
		accessibleKnowledgeBases = []; // Clear previous list

		try {
			const kbs = await getKnowledgeBases();
			kbs.sort((a, b) => a.name.localeCompare(b.name)); 
			accessibleKnowledgeBases = kbs;
			console.log('Fetched KBs for detail view:', accessibleKnowledgeBases);
		} catch (err) {
			console.error('Error fetching knowledge bases for detail view:', err);
			knowledgeBaseError = err instanceof Error ? err.message : 'Failed to load knowledge bases';
		} finally {
			loadingKnowledgeBases = false;
            kbFetchTriggered = true; // Mark fetch as completed/attempted for this assistant load
		}
	}

    /** Fetches rubric markdown if needed for the detail view */
    async function fetchRubricForDetail() {
        if (loadingRubric || rubricFetchTriggered) return; // Don't refetch if loading or already triggered

        // Check if the currently displayed assistant uses rubric_rag
        let ragProcessor = '';
        let rubricId = '';
        const metadataStr = selectedAssistantData?.metadata || selectedAssistantData?.api_callback;
        if (metadataStr) {
            try {
                const callbackData = JSON.parse(metadataStr);
                ragProcessor = callbackData.rag_processor;
                rubricId = callbackData.rubric_id;
            } catch(e) {
                console.error("Error parsing metadata for rubric fetch check:", e);
            }
        }

        if (ragProcessor !== 'rubric_rag' || !rubricId) {
            console.log('Skipping rubric fetch for detail view (not rubric_rag or no rubric_id)');
            rubricMarkdown = ''; // Clear if not needed
            rubricError = '';
            rubricFetchTriggered = true; // Mark as checked for this load
            return;
        }

        console.log('Fetching rubric markdown for detail view...');
        loadingRubric = true;
        rubricError = '';
        rubricMarkdown = ''; // Clear previous content

        try {
            const markdown = await fetchRubricMarkdown(rubricId);
            rubricMarkdown = markdown;
            console.log('Fetched rubric markdown for detail view');
        } catch (err) {
            console.error('Error fetching rubric markdown for detail view:', err);
            rubricError = err instanceof Error ? err.message : 'Failed to load rubric';
        } finally {
            loadingRubric = false;
            rubricFetchTriggered = true; // Mark fetch as completed/attempted for this assistant load
        }
    }

    // Effect to trigger KB and Rubric fetch when detail view is shown and assistant data is available
    $effect(() => {
        // Only run in browser
        if (!browser) return; 

        const assistantIdStr = selectedAssistantData?.id?.toString(); // Current assistant ID as string
        const lastAttemptedIdStr = lastAttemptedId?.toString(); // Last attempted ID as string

        if (currentView === 'detail' && assistantIdStr) {
            // Fetch only if the ID matches the last attempted one AND fetch hasn't been triggered for this ID
            // This prevents fetching if selectedAssistantData updates but the ID is still the one we are working on.
            if (assistantIdStr === lastAttemptedIdStr && !kbFetchTriggered) {
                 console.log(`$effect triggering KB fetch for detail view (ID: ${assistantIdStr})`);
                 fetchKnowledgeBasesForDetail(); // This sets kbFetchTriggered = true
            }
            if (assistantIdStr === lastAttemptedIdStr && !rubricFetchTriggered) {
                 console.log(`$effect triggering Rubric fetch for detail view (ID: ${assistantIdStr})`);
                 fetchRubricForDetail(); // This sets rubricFetchTriggered = true
            }
        } 
        
        // Reset trigger ONLY if the relevant ID changes OR we navigate away from detail
        // Check if the view is no longer detail OR if the loaded assistant ID is different from the one we last tried to load details for.
        if (currentView !== 'detail' || (assistantIdStr && lastAttemptedIdStr && assistantIdStr !== lastAttemptedIdStr)) { 
             if (kbFetchTriggered) { // Only reset if it was previously triggered
                 console.log(`$effect resetting KB fetch trigger. CurrentView: ${currentView}, assistantIdStr: ${assistantIdStr}, lastAttemptedIdStr: ${lastAttemptedIdStr}`);
                 kbFetchTriggered = false;
                 accessibleKnowledgeBases = []; // Clear KBs
                 knowledgeBaseError = ''; // Clear any previous errors
             }
             if (rubricFetchTriggered) { // Reset rubric fetch trigger as well
                 console.log(`$effect resetting Rubric fetch trigger`);
                 rubricFetchTriggered = false;
                 rubricMarkdown = ''; // Clear rubric markdown
                 rubricError = ''; // Clear any previous errors
             }
        }
    });

</script>

<h1 class="text-3xl font-bold mb-4 text-brand">{currentLocale ? $_('assistants.title') : 'Learning Assistants'}</h1>

<!-- Tabs/View Navigation -->
<div class="mb-6 border-b border-gray-200">
    <nav class="-mb-px flex space-x-8" aria-label="Tabs">
        <!-- List View Button (Acts like a tab) -->
        <button
            class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md transition-colors duration-150 {currentView === 'list' ? 'bg-brand text-white border-brand' : 'border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400'}"
            style={currentView === 'list' ? 'background-color: #2271b3; color: white; border-color: #2271b3;' : ''}
            onclick={showList} 
        >
            {currentLocale ? $_('assistants.myAssistantsTab') : 'My Assistants'}
        </button>
        <!-- Create View Button -->
        <button
            class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md {currentView === 'create' ? 'bg-brand text-white border-brand' : 'border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400'}"
            style={currentView === 'create' ? 'background-color: #2271b3; color: white; border-color: #2271b3;' : ''}
            onclick={showCreateForm}
        >
            {currentLocale ? $_('assistants.createAssistantTab') : 'Create Assistant'}
        </button>
        <!-- MCP Testing View Button -->
        <button
            class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md {currentView === 'mcp' ? 'bg-brand text-white border-brand' : 'border-transparent text-gray-800 hover:text-gray-900 hover:border-gray-400'}"
            style={currentView === 'mcp' ? 'background-color: #2271b3; color: white; border-color: #2271b3;' : ''}
            onclick={showMCPTesting}
        >
            {currentLocale ? $_('assistants.mcpTestingTab', { default: 'MCP Testing' }) : 'MCP Testing'}
        </button>
        <!-- Detail View Tab (Only visible when active) -->
        {#if currentView === 'detail' && (selectedAssistantData || loadingDetail)}
             <div class="relative">
                <!-- Simplified Detail Tab Button (No Dropdown) -->
                <button
                    class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm rounded-t-md bg-brand text-white border-brand cursor-default" 
                    style='background-color: #2271b3; color: white; border-color: #2271b3;'
                    disabled
                >
                    {currentLocale ? $_('assistants.detailViewTab') : 'Assistant Detail'}
                    {#if selectedAssistantData} ({selectedAssistantData.name?.replace(/^\d+_/, '') || '...'}){/if}
                </button>
             </div>
        {/if}
    </nav>
</div>

<!-- Conditional Content Rendering -->
{#if currentView === 'list'}
    <div class="mt-6">
        <div class="bg-white shadow rounded-lg p-4 border border-gray-200">
            <AssistantsList 
               on:duplicate={handleDuplicateRequest} 
               on:delete={handleDeleteRequest} 
               on:export={handleExportRequest} 
            />
        </div>
    </div>
{:else if currentView === 'create'}
    <!-- Pass null to indicate creation mode -->
    <AssistantForm assistant={null} on:formSuccess={handleAssistantCreated} />
{:else if currentView === 'mcp'}
    <!-- MCP Testing Interface -->
    <div class="mt-6">
        <div class="bg-white shadow rounded-lg p-6 border border-gray-200">
            <MCPTesting />
        </div>
    </div> 
{:else if currentView === 'detail'}
    <!-- Detail View Sub-Tabs -->
    <div class="mb-4 border-b border-gray-300 flex space-x-4">
        <button
            class="py-2 px-4 text-sm font-medium rounded-t-md {detailSubView === 'properties' ? 'bg-gray-100 border border-b-0 border-gray-300 text-brand' : 'text-gray-600 hover:text-gray-800'}"
            onclick={() => detailSubView = 'properties'}
        >
            {currentLocale ? $_('assistants.detail.propertiesTab', { default: 'Properties' }) : 'Properties'}
        </button>
        <button
            class="py-2 px-4 text-sm font-medium rounded-t-md {detailSubView === 'edit' ? 'bg-gray-100 border border-b-0 border-gray-300 text-brand' : 'text-gray-600 hover:text-gray-800'}"
            onclick={() => detailSubView = 'edit'}
        >
            {currentLocale ? $_('assistants.detail.editTab', { default: 'Edit' }) : 'Edit'}
        </button>
        <button
            class="py-2 px-4 text-sm font-medium rounded-t-md {detailSubView === 'chat' ? 'bg-gray-100 border border-b-0 border-gray-300 text-brand' : 'text-gray-600 hover:text-gray-800'}"
            onclick={() => detailSubView = 'chat'}
        >
            {currentLocale ? $_('assistants.detail.chatTab', { default: 'Chat' }) : 'Chat'} 
            {#if selectedAssistantData && selectedAssistantData.name}
                {currentLocale ? $_('assistants.detail.chatWith', { default: 'with' }) : 'with'} {selectedAssistantData.name.replace(/^\d+_/, '')}
            {/if}
        </button>
    </div>

    <!-- Wrapper for Detail Content -->
    <div class="bg-white shadow rounded-lg border border-gray-200"> 
    {#if loadingDetail}
        <p>{currentLocale ? $_('assistants.loadingDetail') : 'Loading assistant details...'}</p>
    {:else if detailError}
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <strong class="font-bold">{currentLocale ? $_('assistants.errorTitle') : 'Error:'}</strong>
            <span class="block sm:inline">{detailError}</span>
            <button class="ml-4 underline" onclick={showList}>{currentLocale ? $_('common.backToList') : 'Back to list'}</button>
        </div>
    {:else if selectedAssistantData}
        <!-- Render content based on the active sub-tab -->
        {#if detailSubView === 'properties'}
            <!-- Header for Properties View -->
            <div class="flex justify-between items-center px-6 py-4 border-b border-gray-200">
                <h2 class="text-xl font-semibold text-gray-800">
                    {currentLocale ? $_('assistants.detail.propertiesTitle', { default: 'Assistant Properties' }) : 'Assistant Properties'}
                </h2>
                <div class="flex space-x-2">
                    <!-- Edit Button -->
                    <button 
                        type="button" 
                        class="px-3 py-1 text-sm font-medium rounded text-indigo-600 bg-white border border-indigo-600 hover:bg-indigo-100 transition-colors"
                        onclick={() => detailSubView = 'edit'}
                    >
                        {currentLocale ? $_('common.edit', { default: 'Edit' }) : 'Edit'}
                    </button>
                    
                    <!-- Duplicate Button -->
                    <button 
                        type="button" 
                        class="px-3 py-1 text-sm font-medium rounded text-white hover:bg-opacity-90 transition-colors"
                        style="background-color: #2271b3;"
                        onclick={() => handleDuplicateRequest({ detail: { id: selectedAssistantData.id, name: selectedAssistantData.name } })}
                        disabled={isFetchingDuplicateDetails} 
                    >
                        {currentLocale ? $_('common.duplicate') : 'Duplicate'}
                    </button>
                    
                    <!-- Export Button -->
                    <button 
                        type="button" 
                        class="px-3 py-1 text-sm font-medium rounded bg-green-600 text-white hover:bg-green-700 transition-colors"
                        onclick={() => handleExportRequest({ detail: { id: selectedAssistantData.id } })}
                        disabled={isExporting && exportingId === selectedAssistantData.id} 
                    >
                        {#if isExporting && exportingId === selectedAssistantData.id}
                             <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                             {currentLocale ? $_('common.exporting', { default: 'Exporting...' }) : 'Exporting...'}
                        {:else}
                            {currentLocale ? $_('common.export', { default: 'Export' }) : 'Export'}
                        {/if}
                    </button>
                    
                    <!-- Publish/Unpublish Button -->
                    <button 
                        type="button" 
                        class={`px-3 py-1 text-sm font-medium rounded text-white transition-colors ${selectedAssistantData?.published 
                            ? 'bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-400 disabled:cursor-not-allowed' 
                            : 'bg-green-600 hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed'}`}
                        onclick={handlePublishToggle}
                        disabled={isPublishing} 
                    >
                        {#if isPublishing}
                           <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                           {currentLocale ? $_('common.updating', { default: 'Updating...' }) : 'Updating...'}
                        {:else if selectedAssistantData?.published}
                            {currentLocale ? $_('common.unpublish', { default: 'Unpublish' }) : 'Unpublish'}
                        {:else}
                            {currentLocale ? $_('common.publish', { default: 'Publish' }) : 'Publish'} 
                        {/if}
                    </button>
                    
                    <!-- Delete Button -->
                    <button 
                        type="button" 
                        class="px-3 py-1 text-sm font-medium rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                        onclick={() => handleDeleteRequest({ detail: { id: selectedAssistantData.id, name: selectedAssistantData.name, published: selectedAssistantData.published }})}
                    >
                        {currentLocale ? $_('common.delete') : 'Delete'}
                    </button>
                </div>
            </div>
            
            <!-- Flex container for Form and LTI/Config Box -->
            <div class="flex flex-col md:flex-row md:space-x-6 px-6 py-4">
                <!-- Main Details Display (Read-only) -->
                <div class="flex-grow md:w-2/3 space-y-4">
                    <!-- Name -->
                    <div>
                        <div class="block text-sm font-medium text-gray-700">{$_('assistants.form.name.label')} <span class="text-red-600">*</span></div>
                        <div class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-100 cursor-not-allowed sm:text-sm">
                            {selectedAssistantData.name?.replace(/^\d+_/, '') || (currentLocale ? $_('common.notAvailable', { default: 'N/A' }) : 'N/A')}
                        </div>
                    </div>
                    <!-- Description -->
                    <div>
                        <div class="block text-sm font-medium text-gray-700">{$_('assistants.form.description.label', { default: 'Description' })}</div>
                        <div class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-100 sm:text-sm min-h-[6em] whitespace-pre-wrap select-text cursor-text">
                            {selectedAssistantData.description || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                        </div>
                    </div>
                     <!-- System Prompt -->
                    <div>
                        <div class="block text-sm font-medium text-gray-700">{$_('assistants.form.systemPrompt.label', { default: 'System Prompt' })}</div>
                        <div class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-100 sm:text-sm min-h-[8em] whitespace-pre-wrap select-text cursor-text">
                            {selectedAssistantData.system_prompt || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                        </div>
                    </div>
                    <!-- Prompt Template -->
                    <div>
                        <div class="block text-sm font-medium text-gray-700">{$_('assistants.form.promptTemplate.label', { default: 'Prompt Template' })}</div>
                        <div class="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm bg-gray-100 sm:text-sm max-h-96 overflow-y-auto whitespace-pre-wrap select-text cursor-text">
                            {selectedAssistantData.prompt_template || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                        </div>
                    </div>

                    <!-- Selected Rubric (if rubric_rag) - Moved here below prompt template -->
                    {#if selectedAssistantData}
                        {@const apiCallback = (() => {
                            try {
                                const metadataStr = selectedAssistantData.metadata || selectedAssistantData.api_callback;
                                return typeof metadataStr === 'string' 
                                    ? JSON.parse(metadataStr) 
                                    : metadataStr || {};
                            } catch (e) {
                                console.error("Error parsing metadata:", e);
                                return {};
                            }
                        })()}
                        {#if apiCallback.rag_processor === 'rubric_rag'}
                            <div class="mt-6 pt-6 border-t border-gray-200">
                                <div class="block text-sm font-medium text-gray-700 mb-2">{$_('assistants.form.rubric.selectedLabel', { default: 'Selected Rubric' })}</div>
                                {#if loadingRubric}
                                    <div class="bg-white border border-gray-200 p-3 rounded-md text-gray-500 italic text-sm">
                                        {$_('assistants.form.rubric.loading', { default: 'Loading rubric...' })}
                                    </div>
                                {:else if rubricError}
                                    <div class="bg-red-50 border border-red-200 p-3 rounded-md text-red-600 text-sm">
                                        <strong>{$_('assistants.form.rubric.error', { default: 'Error loading rubric:' })}</strong> {rubricError}
                                    </div>
                                {:else if rubricMarkdown}
                                    <div class="bg-white border border-gray-300 rounded-md p-4">
                                        <!-- Rubric metadata -->
                                        <div class="mb-3 pb-3 border-b border-gray-200">
                                            <div class="text-xs text-gray-600 space-y-1">
                                                <div>
                                                    <span class="font-medium">{$_('assistants.form.rubric.id', { default: 'Rubric ID:' })}</span> 
                                                    <code class="ml-1 text-xs bg-gray-100 px-1 py-0.5 rounded">{apiCallback.rubric_id || 'N/A'}</code>
                                                </div>
                                                <div>
                                                    <span class="font-medium">{$_('assistants.form.rubric.format.label', { default: 'Format:' })}</span> 
                                                    <span class="ml-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                                        {apiCallback.rubric_format || 'markdown'}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                        <!-- Rubric Markdown Content in collapsible -->
                                        <details open>
                                            <summary class="cursor-pointer text-sm font-medium text-blue-600 hover:text-blue-800 mb-2">
                                                {$_('assistants.form.rubric.viewRubric', { default: 'View Rubric Content' })}
                                            </summary>
                                            <div class="mt-3 p-4 bg-gray-50 border border-gray-200 rounded max-h-96 overflow-y-auto">
                                                <pre class="text-xs whitespace-pre-wrap font-mono text-gray-800">{rubricMarkdown}</pre>
                                            </div>
                                        </details>
                                    </div>
                                {:else}
                                    <div class="bg-white border border-gray-200 p-3 rounded-md text-gray-500 italic text-sm">
                                        {apiCallback.rubric_id || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                                    </div>
                                {/if}
                            </div>
                        {/if}
                    {/if}
                </div>

                <!-- Right Column: LTI and Configuration -->
                {#if selectedAssistantData}
                    <div class="md:w-1/3 mt-6 md:mt-0 space-y-4"> 
                        <!-- LTI Publish Details (Conditional) -->
                        {#if selectedAssistantData.published}
                            <div class="p-4 border border-blue-200 rounded bg-blue-50">
                                <h3 class="text-lg font-semibold text-blue-800 mb-2">
                                    {currentLocale ? $_('assistants.detail.ltiTitle', { default: 'LTI Publish Details' }) : 'LTI Publish Details'}
                                </h3>
                                {console.log('Checking selectedAssistantData for LTI box:', selectedAssistantData)}
                                <div class="space-y-1 text-sm text-blue-700 break-words">
                                    <div>
                                        <span class="font-medium">{currentLocale ? $_('assistants.detail.ltiToolUrl', { default: 'Tool URL' }) : 'Tool URL'}:</span> 
                                        <code class="ml-1 bg-blue-100 px-1 rounded">{lambServerUrl}/lamb/v1/lti_users/lti</code>
                                    </div>
                                    <div>
                                        <span class="font-medium">{currentLocale ? $_('assistants.detail.ltiConsumerKey', { default: 'Consumer Key' }) : 'Consumer Key'}:</span> 
                                        <code class="ml-1 bg-blue-100 px-1 rounded">{selectedAssistantData.oauth_consumer_name || (currentLocale ? $_('common.notAvailable', { default: 'N/A' }) : 'N/A')}</code>
                                    </div>
                                    <div>
                                        <span class="font-medium">{currentLocale ? $_('assistants.detail.ltiSecret', { default: 'Secret' }) : 'Secret'}:</span> 
                                        <code class="ml-1 bg-blue-100 px-1 rounded">ASK ADMIN FOR THE SECRET</code>
                                    </div>
                                </div>
                            </div>
                        {/if}
                        
                        <!-- Configuration Section -->
                        <div class="p-4 border border-gray-200 rounded bg-gray-50">
                            <h3 class="text-lg font-semibold text-gray-800 mb-2">
                                {currentLocale ? $_('assistants.detail.configuration', { default: 'Configuration' }) : 'Configuration'}
                            </h3>

                            <!-- Parse metadata -->
                            {#if selectedAssistantData}
                                {@const apiCallback = (() => {
                                    try {
                                        const metadataStr = selectedAssistantData.metadata || selectedAssistantData.api_callback;
                                        return typeof metadataStr === 'string' 
                                            ? JSON.parse(metadataStr) 
                                            : metadataStr || {};
                                    } catch (e) {
                                        console.error("Error parsing metadata:", e);
                                        return {};
                                    }
                                })()}

                                <div class="space-y-3 text-sm">
                                    <!-- Prompt Processor -->
                                    <div>
                                        <div class="font-medium text-gray-700 mb-1">
                                            {currentLocale ? $_('assistants.form.promptProcessor.label', { default: 'Prompt Processor' }) : 'Prompt Processor'}
                                        </div>
                                        <div class="bg-white border border-gray-200 p-2 rounded">
                                            {apiCallback.prompt_processor || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                                        </div>
                                    </div>

                                    <!-- Connector -->
                                    <div>
                                        <div class="font-medium text-gray-700 mb-1">
                                            {currentLocale ? $_('assistants.form.connector.label', { default: 'Connector' }) : 'Connector'}
                                        </div>
                                        <div class="bg-white border border-gray-200 p-2 rounded">
                                            {apiCallback.connector || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                                        </div>
                                    </div>

                                    <!-- Language Model -->
                                    <div>
                                        <div class="font-medium text-gray-700 mb-1">
                                            {currentLocale ? $_('assistants.form.llm.label', { default: 'Language Model (LLM)' }) : 'Language Model (LLM)'}
                                        </div>
                                        <div class="bg-white border border-gray-200 p-2 rounded">
                                            {apiCallback.llm || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                                        </div>
                                    </div>

                                    <!-- RAG Processor -->
                                    <div>
                                        <div class="font-medium text-gray-700 mb-1">
                                            {currentLocale ? $_('assistants.form.ragProcessor.label', { default: 'RAG Processor' }) : 'RAG Processor'}
                                        </div>
                                        <div class="bg-white border border-gray-200 p-2 rounded">
                                            {apiCallback.rag_processor?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                                        </div>
                                    </div>
                                    
                                    <!-- Conditional RAG Options -->
                                    {#if apiCallback.rag_processor && apiCallback.rag_processor !== 'no_rag'}
                                        <div class="pt-3 mt-3 border-t border-gray-300 space-y-3">
                                            <h4 class="text-md font-medium text-gray-700">{$_('assistants.form.ragOptions.title', { default: 'RAG Options' })}</h4>
                                            
                                            <!-- RAG Top K (Hide if single_file_rag or rubric_rag) -->
                                            {#if apiCallback.rag_processor !== 'single_file_rag' && apiCallback.rag_processor !== 'rubric_rag'}
                                                <div>
                                                    <div class="font-medium text-gray-700 mb-1">{$_('assistants.form.ragTopK.label', { default: 'RAG Top K' })}</div>
                                                    <div class="bg-white border border-gray-200 p-2 rounded w-24 text-center">
                                                        {selectedAssistantData.RAG_Top_k ?? 3}
                                                    </div>
                                                </div>
                                            {/if}

                                            <!-- Knowledge Bases (if simple_rag) -->
                                            {#if apiCallback.rag_processor === 'simple_rag'}
                                                <div>
                                                    <div class="font-medium text-gray-700 mb-1">{$_('assistants.form.knowledgeBases.label', { default: 'Knowledge Bases' })}</div>
                                                    {#if loadingKnowledgeBases}
                                                        <div class="bg-white border border-gray-200 p-2 rounded text-gray-500 italic">
                                                            {$_('assistants.form.knowledgeBases.loading', { default: 'Loading...' })}
                                                        </div>
                                                    {:else if knowledgeBaseError}
                                                         <div class="bg-red-50 border border-red-200 p-2 rounded text-red-600 italic">
                                                             {$_('assistants.form.knowledgeBases.error', { default: 'Error loading KBs' })}
                                                         </div>
                                                    {:else if selectedAssistantData.RAG_collections}
                                                        <div class="bg-white border border-gray-200 p-2 rounded space-y-1">
                                                            {#each selectedAssistantData.RAG_collections.split(',') as kbId}
                                                                {@const kb = accessibleKnowledgeBases.find(k => k.id === kbId)}
                                                                <span class="inline-block bg-gray-200 rounded px-2 py-0.5 text-xs font-medium text-gray-700">
                                                                    {kb ? kb.name : `${kbId} (Not Found)`}
                                                                </span>
                                                            {/each}
                                                        </div>
                                                    {:else}
                                                        <div class="bg-white border border-gray-200 p-2 rounded text-gray-500 italic">
                                                            {$_('common.none', { default: 'None' })}
                                                        </div>
                                                    {/if}
                                                </div>
                                            {/if}

                                            <!-- Selected File (if single_file_rag) -->
                                            {#if apiCallback.rag_processor === 'single_file_rag'}
                                                <div>
                                                    <div class="font-medium text-gray-700 mb-1">{$_('assistants.form.singleFile.selectedLabel', { default: 'Selected File' })}</div>
                                                    <div class="bg-white border border-gray-200 p-2 rounded break-all">
                                                        {apiCallback.file_path || (currentLocale ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}
                                                    </div>
                                                </div>
                                            {/if}
                                        </div>
                                    {/if}
                                </div>
                            {/if}
                        </div>
                    </div>
                {/if}
            </div>

        {:else if detailSubView === 'edit'}
            <!-- Edit View -->
            <div class="px-6 py-4">
                <div class="mb-6 pb-4 border-b border-gray-200">
                    <h2 class="text-xl font-semibold text-gray-800">
                        {currentLocale ? $_('assistants.detail.editTitle', { default: 'Edit Assistant' }) : 'Edit Assistant'}
                    </h2>
                </div>
                
                <!-- Assistant Form -->
                <div class="w-full">
                    <AssistantForm 
                        assistant={selectedAssistantData}
                        on:formSuccess={() => {
                            // Refresh the assistant data after successful update
                            fetchAssistantDetail(selectedAssistantData.id);
                            detailSubView = 'properties'; // Switch back to properties view
                        }}
                        id="assistant-edit-form"
                    />
                </div>
            </div>
        {:else if detailSubView === 'chat'}
            {#if configError}
                <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                    <strong class="font-bold">{currentLocale ? $_('assistants.detail.configErrorTitle', { default: 'Configuration Error:' }) : 'Configuration Error:'}</strong>
                    <span class="block sm:inline">{configError} - {currentLocale ? $_('assistants.chatDisabled') : 'Chat functionality is disabled.'}</span>
                </div>
            {:else if lambServerUrl && userToken}
                <!-- Header for Chat View (Optional: can add title or keep it clean) -->
                <div class="px-6 py-4 border-b border-gray-200">
                     <h2 class="text-xl font-semibold text-gray-800">
                        {currentLocale ? $_('assistants.detail.chatTitle', { default: 'Chat' }) : 'Chat'}
                     </h2>
                </div>
                <ChatInterface 
                    apiUrl={lambServerUrl} 
                    userToken={userToken} 
                    assistantId={selectedAssistantData.id} 
                    initialModel={selectedAssistantData.llm}
                />
            {:else}
                <!-- Should not happen if configError is handled, but as fallback -->
                <p>{currentLocale ? $_('assistants.chatLoadingConfig') : 'Loading chat configuration...'}</p>
            {/if}
        {/if}
    {/if}
    </div> <!-- Closes Wrapper for Detail Content -->
<!-- End of detail view content -->
{:else}
    <!-- Fallback for when currentView is not list, create, or detail (should not happen) -->
    <p>{currentLocale ? $_('assistants.noAssistantData') : 'Assistant data not available.'}</p>
{/if} 

<!-- Duplicate Assistant Modal -->
{#if isDuplicateModalOpen}
   <DuplicateAssistantModal 
       bind:isOpen={isDuplicateModalOpen} 
       originalName={assistantToDuplicateName} 
       defaultNewName={defaultDuplicateName} 
       bind:isSubmitting={isSubmittingDuplicate} 
       on:submit={handleDuplicateSubmit} 
       on:close={() => {
           isDuplicateModalOpen = false;
           assistantToDuplicateId = null;
           assistantToDuplicateData = null;
           duplicateError = ''; // Clear errors on close
       }}
       error={duplicateError}
   />
{/if}

<!-- Delete Confirmation Modal -->
{#if isDeleteModalOpen}
   <DeleteConfirmationModal
       bind:isOpen={isDeleteModalOpen}
       assistantName={assistantToDeleteName || ''}
       bind:isDeleting={isDeletingAssistant}
       on:confirm={handleDeleteConfirm}
       on:close={() => {
           isDeleteModalOpen = false;
           assistantToDeleteId = null;
           assistantToDeleteName = null;
           deleteError = ''; // Clear errors on close
       }}
   />
{/if}

<!-- Loading state for detail view -->
{#if loadingDetail}
    <p>{currentLocale ? $_('assistants.loadingDetail') : 'Loading assistant details...'}</p>
{/if} 