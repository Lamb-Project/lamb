<script>
	// Placeholder for Assistant Creation Form
	import { _ } from '$lib/i18n';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore'; // Import the store
	import { tick } from 'svelte'; // Import tick for $effect timing
	import { get } from 'svelte/store'; // Import get
	import { getUserKnowledgeBases, getSharedKnowledgeBases } from '$lib/services/knowledgeBaseService'; // Import KB service
	import { createAssistant, updateAssistant } from '$lib/services/assistantService'; // Import create service and update service
	import { fetchAccessibleRubrics } from '$lib/services/rubricService'; // Import rubric service
	import { onDestroy } from 'svelte';
	import TemplateSelectModal from '$lib/components/modals/TemplateSelectModal.svelte'; // Import template modal
import { extractModelsFromConnectorData, getAuthToken, loadRagPlaceholders, createModelSelector } from './assistantFormUtils.svelte.js';
import { isKbBasedRag, isSingleFileRag, isRubricRag, normalizeRagProcessor, hasRagOptions } from '$lib/utils/ragProcessorHelpers.js';
import { validateImportedAssistant } from './importAssistantValidator.js';
import AssistantFormHeader from './AssistantFormHeader.svelte';
import AssistantNameField from './AssistantNameField.svelte';
import AssistantDescriptionField from './AssistantDescriptionField.svelte';
import AssistantPromptFields from './AssistantPromptFields.svelte';
import RubricSelector from './RubricSelector.svelte';
import ConfigurationPanel from './ConfigurationPanel.svelte';
import FormActions from './FormActions.svelte';
	import { getAssistantMetadataObject } from '$lib/utils/assistantData';

	// Track mount status so async fetches that resolve after the user
	// navigates away don't write state to a destroyed component. (#352, M13)
	let isMounted = true;
	onDestroy(() => { isMounted = false; });

	// --- Props --- 
	// Use $props for Svelte 5 runes mode
	let { 
		assistant = null,
		startInEdit = false, // Add the new prop
		onFormSuccess = /** @type {(e: { assistantId: number }) => void} */ (() => {}),
		onCancel = /** @type {() => void} */ (() => {})
	} = $props(); 

	// --- Component State ---
	let formState = $state(/** @type {'edit' | 'create'} */ ('create')); 
	/** @type {any | null} */ // Store initial data for cancel/revert
	let initialAssistantData = $state(null); 

	// --- Form Field State Variables ---
	let name = $state('');
	// Derived: Sanitized name preview
	// Description must be fully editable even in edit mode
	let description = $state('');

	let system_prompt = $state('');
	let prompt_template = $state('');
	let RAG_Top_k = $state(3);
	let isAdvancedMode = $state(false); // New state for advanced mode toggle 

	// State for dynamic options 
	/** @type {string[]} */
	let promptProcessors = $state([]);
	/** @type {string[]} */
	let connectorsList = $state([]); // List of connector names
	/** @type {string[]} */
	/** @type {string[]} */
	let ragProcessors = $state([]);

	// Selected values for dropdowns
	let selectedPromptProcessor = $state('');
	let selectedConnector = $state('');
	let selectedLlm = $state('');
	let selectedRagProcessor = $state('');

	// Vision capability
	let visionEnabled = $state(false);
	// Image generation capability
	let imageGenerationEnabled = $state(false);
	
	// Connector and model metadata (for forced capabilities and descriptions)
	/** @type {any} */
	// Knowledge Base State - separate owned and shared
	/** @type {import('$lib/services/knowledgeBaseService').KnowledgeBase[]} */
	let ownedKnowledgeBases = $state([]);
	/** @type {import('$lib/services/knowledgeBaseService').KnowledgeBase[]} */
	let sharedKnowledgeBases = $state([]);
	/** @type {string[]} */
	let selectedKnowledgeBases = $state([]); // Array of selected KB IDs
	let loadingKnowledgeBases = $state(false);
	let knowledgeBaseError = $state('');
	let kbFetchAttempted = $state(false); // Track if fetch was attempted
	
	// FIX FOR ISSUE #96: Deferred selection pattern
	// Pending selections that will be applied when options are ready
	let pendingKBSelections = $state(null);
	
	// Computed: combined list for backward compatibility
	let accessibleKnowledgeBases = $derived([...ownedKnowledgeBases, ...sharedKnowledgeBases]);

	// File State for single_file_rag
	/** @type {Array<{name: string, path: string}>} */
	let userFiles = $state([]);
	let selectedFilePath = $state('');
	let loadingFiles = $state(false);
	let fileError = $state('');
	let filesFetchAttempted = $state(false);

	// Rubric State
	/** @type {Array<{rubric_id: string, title: string, description: string, is_mine: boolean, is_showcase: boolean, is_public: boolean}>} */
	let accessibleRubrics = $state([]);
	/** @type {string} */
	let selectedRubricId = $state('');
	/** @type {'markdown' | 'json'} */
	let rubricFormat = $state('markdown');
	let loadingRubrics = $state(false);
	let rubricError = $state('');
	let rubricsFetchAttempted = $state(false);

	/** @type {import('./ConfigurationPanel.svelte').default | null} */
	/** @type {any} */
	let configPanel = $state(null);
	let availableModels = $derived(configPanel?.getAvailableModels() || []);

	// Loading/error/success state
	let formError = $state('');
	let formLoading = $state(false); 
	let configInitialized = $state(false); 
	let successMessage = $state('');
	
	// Handler for template selection
	let importError = $state(''); // State for import errors

	// Form dirty state tracking to prevent overwriting user edits
	// See: Documentation/lamb_architecture.md Section 16.1
	let formDirty = $state(false);
	let previousAssistantId = $state(null);

	/** @type {string[]} */
	let ragPlaceholders = $state([]);  // Initialize as empty array to be filled from config

	/**
	 * Mark form as dirty when user makes changes
	 * This prevents automatic repopulation from overwriting user edits
	 */
	function handleFieldChange() {
		if (!formDirty) {

		}
		formDirty = true;
	}

	/**
	 * Highlights placeholders in the prompt template text
	 * @param {string} text - The text to process
	 * @returns {string} HTML string with highlighted placeholders
	 */
	// --- Store Integration and Initialization ---
	$effect(() => {

		const assistantIdChanged = assistant?.id !== initialAssistantData?.id;
		const assistantNullStatusChanged = (assistant === null && initialAssistantData !== null) || (assistant !== null && initialAssistantData === null);

		// Check if the assistant data content has changed (not just ID)
		const assistantDataChanged = assistant && initialAssistantData &&
			(assistant.system_prompt !== initialAssistantData.system_prompt ||
			 assistant.prompt_template !== initialAssistantData.prompt_template ||
			 assistant.name !== initialAssistantData.name ||
			 assistant.description !== initialAssistantData.description);

		if (assistantIdChanged || assistantNullStatusChanged || assistantDataChanged) {

			if (assistant) {

				initialAssistantData = { ...assistant };

				formState = 'edit';

				previousAssistantId = assistant.id;
				// Reset dirty state when loading a different assistant
				formDirty = false;

				populateFormFields(assistant);
				formError = '';
				successMessage = '';
			} else {

				formState = 'create';
				initialAssistantData = null;
				previousAssistantId = null;
				formDirty = false;
				if (configInitialized) {
					resetFormFieldsToDefaults();
				}
			}
		} else {
			// FIX: Prevent unnecessary repopulation that causes field resets
			// Svelte 5's reactivity can cause prop reference changes even when data hasn't changed
			// Only repopulate basic text fields, NOT the configuration dropdowns
			// Configuration dropdowns (connector, llm, rag processor, etc.) should only be
			// populated on initial load or explicit assistant change (handled above)
			if (assistant && !formDirty) {

				// The only case where we'd repopulate is on actual ID change (handled above)
			} else if (assistant && formDirty) {

			}
		}
	});

	// Effect for loading config and applying defaults
	$effect.pre(() => {
		if (!configInitialized && !$assistantConfigStore.loading && !$assistantConfigStore.systemCapabilities) {

			assistantConfigStore.loadConfig();
		}

		const unsubscribe = assistantConfigStore.subscribe(state => {

			if (!state.loading && state.systemCapabilities && state.configDefaults && !configInitialized) {
				const capabilities = state.systemCapabilities;

				promptProcessors = capabilities.prompt_processors || [];
				connectorsList = Object.keys(capabilities.connectors || {});
				ragProcessors = capabilities.rag_processors || [];

				configInitialized = true; 

				if (formState === 'create') {

					resetFormFieldsToDefaults(); // Use helper
				} else {

					populateFormFields(initialAssistantData); 
				}
			}
		});

		return unsubscribe;
	});

	// FIX FOR ISSUE #96: Effect to apply pending KB selections when list becomes available
	$effect(() => {
		// Apply pending selections AFTER fetch completes (not just when arrays have items)
		// This handles cases where user has no KBs or KBs were deleted
		if (pendingKBSelections !== null && kbFetchAttempted && !loadingKnowledgeBases) {

			selectedKnowledgeBases = pendingKBSelections;
			pendingKBSelections = null; // Clear pending state

		}
	});

	// --- Helper to reset form fields to defaults (for create mode) ---
	function resetFormFieldsToDefaults() {
		const defaults = get(assistantConfigStore).configDefaults?.config || {};
		system_prompt = defaults.system_prompt || '';
		prompt_template = defaults.prompt_template || '';
		RAG_Top_k = parseInt(defaults.RAG_Top_k || '3', 10) || 3;
		selectedPromptProcessor = defaults.prompt_processor || (promptProcessors.length > 0 ? promptProcessors[0] : '');
		selectedConnector = defaults.connector || (connectorsList.length > 0 ? connectorsList[0] : '');
		let defaultRag = normalizeRagProcessor(defaults.rag_processor);
		selectedRagProcessor = defaultRag || (ragProcessors.length > 0 ? ragProcessors[0] : '');
		
		// Load the placeholders from config
		ragPlaceholders = loadRagPlaceholders(defaults);
		
		// Update available models based on selected connector
		configPanel?.updateAvailableModels();
		// Set LLM with fallback to first available model if default not available
		selectedLlm = createModelSelector(defaults.llm || '', availableModels);
		
		selectedKnowledgeBases = [];
		selectedFilePath = '';
		visionEnabled = false; // Reset vision capability for new assistants
		imageGenerationEnabled = false; // Reset image generation capability for new assistants
		// Reset name/description only if truly starting fresh?
		// name = '';
		// description = ''; 

		if (isKbBasedRag(selectedRagProcessor)) {
			tick().then(fetchKnowledgeBases);
		}
		if (isSingleFileRag(selectedRagProcessor)) {
			tick().then(fetchUserFiles);
		}
		if (isRubricRag(selectedRagProcessor)) {
			tick().then(fetchRubricsList);
		}
	}

	// --- Mode Switching Functions ---
	function switchToEditMode() {
		formState = 'edit';
		formError = '';
		successMessage = '';

	}

	function switchToViewMode() {
		// Revert fields to initial state
		if (initialAssistantData) {
			populateFormFields(initialAssistantData);
		}
		// Reset dirty state when canceling (user discarded changes)
		formDirty = false;

		formError = '';
		successMessage = '';

		onCancel();
	}

	// --- Helper Functions ---
	/**
	 * Populates the form fields from a given assistant data object.
	 * @param {any} data The assistant data object.
	 * @param {boolean} [preserveDescription=false] - Whether to preserve the current description value
	 * 
	 * FIX FOR ISSUE #96: Uses Deferred Selection pattern to avoid race conditions.
	 * Basic fields populate synchronously (no blank page), async-dependent selections 
	 * are stored as pending and applied when options become available via $effect.
	 * See Architecture Doc Section 17.2 for details.
	 */
	function populateFormFields(data, preserveDescription = false) {
		if (!data) return;

		const metadata = getAssistantMetadataObject(data);
		
		name = data.name?.replace(/^\d+_/, '') || '';
		// Only update description if not preserving current edits
		if (!preserveDescription) {
			description = data.description || ''; 
		}
		system_prompt = data.system_prompt || '';
		prompt_template = data.prompt_template || '';
		RAG_Top_k = data.RAG_Top_k ?? 3;
		
		if (configInitialized) {
			// Read plugin settings from top-level fields first, then fallback to metadata.
			selectedPromptProcessor = data.prompt_processor || metadata.prompt_processor || (promptProcessors.length > 0 ? promptProcessors[0] : '');

			selectedConnector = data.connector || metadata.connector || (connectorsList.length > 0 ? connectorsList[0] : '');

			selectedRagProcessor = data.rag_processor || metadata.rag_processor || (ragProcessors.length > 0 ? ragProcessors[0] : '');

			configPanel?.updateAvailableModels();

			const targetLlm = data.llm || metadata.llm;
			selectedLlm = createModelSelector(targetLlm, availableModels);

			// Load placeholders from config for edit mode as well
			const defaults = get(assistantConfigStore).configDefaults?.config || {};
			ragPlaceholders = loadRagPlaceholders(defaults);
			
			// FIX FOR ISSUE #96: Deferred Selection Pattern
			// Store pending selections that will be applied when options are ready
			if (isKbBasedRag(selectedRagProcessor)) {
				// Store selections to be applied later
				pendingKBSelections = data.RAG_collections?.split(',').filter(Boolean) || [];

				if (!kbFetchAttempted && !loadingKnowledgeBases) {

					tick().then(fetchKnowledgeBases);
				}
			} else {
				// Clear pending selections if not using simple_rag, context_aware_rag, or hierarchical_rag
				pendingKBSelections = null;
			}

			// Handle rubric fields if rubric_rag is selected
			if (isRubricRag(selectedRagProcessor)) {
				try {
					selectedRubricId = metadata?.rubric_id || '';
					rubricFormat = metadata?.rubric_format || 'markdown';

					// Fetch rubrics if needed
					if (!rubricsFetchAttempted && !loadingRubrics) {

						tick().then(fetchRubricsList);
					}
				} catch (e) {
					console.warn('Failed to parse rubric metadata:', e);
					selectedRubricId = '';
					rubricFormat = 'markdown';
				}
			}

			// Handle vision capability
			try {
				visionEnabled = metadata?.capabilities?.vision || false;
				imageGenerationEnabled = metadata?.capabilities?.image_generation || false;

			} catch (e) {
				console.warn('Failed to parse vision capability from metadata:', e);
				visionEnabled = false;
			}

			// TODO: Handle file selection for single_file_rag if needed
			// selectedFilePath = data.file_path || '';
		} else {
			console.warn('[populateFormFields] Config not initialized yet, skipping dropdown population');
		}
	}

	/** Fetches accessible knowledge bases */
	async function fetchKnowledgeBases() {
		// Prevent fetch if already loading OR if already attempted for this selection
		if (loadingKnowledgeBases || kbFetchAttempted) {

			return;
		}
		// Ensure we actually need KBs
		if (!isKbBasedRag(selectedRagProcessor)) {

			return;
		}

		loadingKnowledgeBases = true;
		knowledgeBaseError = '';
		// Don't clear selected KBs here on refetch
		// selectedKnowledgeBases = []; 

		try {
			// Fetch owned and shared KBs separately
			const [owned, shared] = await Promise.all([
				getUserKnowledgeBases().catch(err => {
					console.warn('Error fetching owned KBs:', err);
					return [];
				}),
				getSharedKnowledgeBases().catch(err => {
					console.warn('Error fetching shared KBs:', err);
					return [];
				})
			]);

			if (!isMounted) return; // user navigated away while fetching (#352, M13)

			// Sort each separately
			owned.sort((a, b) => a.name.localeCompare(b.name));
			shared.sort((a, b) => a.name.localeCompare(b.name));

			ownedKnowledgeBases = owned;
			sharedKnowledgeBases = shared;
		} catch (err) {
			if (!isMounted) return;
			if (err instanceof Error && err.message.startsWith('Session expired')) return;
			console.error('Error fetching knowledge bases:', err);
			knowledgeBaseError = err instanceof Error ? err.message : 'Failed to load knowledge bases';
			ownedKnowledgeBases = [];
			sharedKnowledgeBases = [];
		} finally {
			if (isMounted) {
				loadingKnowledgeBases = false;
				kbFetchAttempted = true;

			}
		}
	}

	async function fetchRubricsList() {
		// Prevent fetch if already loading OR if already attempted for this selection
		if (loadingRubrics || rubricsFetchAttempted) {

			return;
		}
		// Ensure we actually need rubrics
		if (!isRubricRag(selectedRagProcessor)) {

			return;
		}

		loadingRubrics = true;
		rubricError = '';

		try {
			const response = await fetchAccessibleRubrics();
			const rubrics = response.rubrics || [];
			accessibleRubrics = rubrics;

		} catch (err) {
			console.error('Error fetching accessible rubrics:', err);
			rubricError = err instanceof Error ? err.message : 'Failed to load rubrics';
			accessibleRubrics = []; // Ensure list is empty on error
		} finally {
			loadingRubrics = false;
			rubricsFetchAttempted = true; // Mark fetch as attempted

		}
	}

	/** Fetches the user's files from the server */
	async function fetchUserFiles() {
		if (loadingFiles) {

			return;
		}

		loadingFiles = true;
		fileError = '';

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found');
			}

			// Get the lamb server URL
			const lambServerUrl = window.LAMB_CONFIG?.api?.lambServer;
			if (!lambServerUrl) {
				throw new Error('LAMB server URL not configured in window.LAMB_CONFIG.api.lambServer');
			}

			// Call the files/list endpoint
			const endpointPath = '/creator/files/list';
			const apiUrl = `${lambServerUrl.replace(/\/$/, '')}${endpointPath}`;
			
			const response = await fetch(apiUrl, {
				headers: {
					'Authorization': `Bearer ${token}`
				}
			});

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`API error: ${response.status} - ${errorText || 'Unknown error'}`);
			}

			const data = await response.json();
			userFiles = data; // API returns array of {name, path} objects
			
			// Set selected file if it exists in metadata.
			const callbackData = getAssistantMetadataObject(assistant);
			if (callbackData.file_path && userFiles.some(file => file.path === callbackData.file_path)) {
				selectedFilePath = callbackData.file_path;
			}

		} catch (err) {
			console.error('Error fetching user files:', err);
			fileError = err instanceof Error ? err.message : 'Failed to load files';
			userFiles = []; // Ensure list is empty on error
		} finally {
			loadingFiles = false;
			filesFetchAttempted = true;
		}
	}

	// --- Reactive UI Logic (Mostly Unchanged) ---
	const showRagOptions = $derived(hasRagOptions(selectedRagProcessor));
	const showKnowledgeBaseSelector = $derived(isKbBasedRag(selectedRagProcessor));
	const showSingleFileSelector = $derived(isSingleFileRag(selectedRagProcessor));
	const showRubricSelector = $derived(isRubricRag(selectedRagProcessor));
	
	// Effect to fetch KBs/Files when RAG processor changes (Mostly Unchanged)
	$effect(() => {

		if ((isKbBasedRag(selectedRagProcessor)) && configInitialized) {
			// Trigger fetch only if we land on simple_rag, context_aware_rag, or hierarchical_rag and haven't attempted the fetch yet

			if (!kbFetchAttempted && !loadingKnowledgeBases) { // Check attempted flag, ignore error here

				fetchKnowledgeBases();
			} else {

			}
		} else if (isSingleFileRag(selectedRagProcessor) && configInitialized) {
			// Fetch files when switching to single_file_rag
			if (!filesFetchAttempted && !loadingFiles) {

				fetchUserFiles();
			} else {

			}
		} else if (isRubricRag(selectedRagProcessor) && configInitialized) {
			// Fetch rubrics when switching to rubric_rag
			if (!rubricsFetchAttempted && !loadingRubrics) {

				tick().then(fetchRubricsList);
			} else {

			}
		} else {
			// Clear KB state AND reset attempted flag if RAG processor changes away
			if (accessibleKnowledgeBases.length > 0 || selectedKnowledgeBases.length > 0 || knowledgeBaseError || kbFetchAttempted) {

				ownedKnowledgeBases = [];
				sharedKnowledgeBases = [];
				selectedKnowledgeBases = [];
				knowledgeBaseError = '';
				kbFetchAttempted = false; // Reset flag
			}
			
			// Reset file selection if we moved away from single_file_rag
			if (!isSingleFileRag(selectedRagProcessor) && (selectedFilePath || userFiles.length > 0)) {
				selectedFilePath = '';
				// Note: We don't clear userFiles or filesFetchAttempted to avoid refetching if user switches back
			}

			// Reset rubric selection if we moved away from rubric_rag
			if (!isRubricRag(selectedRagProcessor) && (selectedRubricId || accessibleRubrics.length > 0)) {
				selectedRubricId = '';
				rubricFormat = 'markdown'; // Reset to default
				// Note: We don't clear accessibleRubrics or rubricsFetchAttempted to avoid refetching if user switches back
			}
		}
	});

	// --- Event Handlers ---

	/**
	 * @typedef {import('$lib/services/knowledgeBaseService').KnowledgeBase} KnowledgeBase
	 */

	/**
	 * @typedef {Object} AssistantResponse - Defines the structure of an assistant object from API
	 * @property {number} id
	 * @property {string} name
	 * @property {string} [description]
	 * // Add other expected fields from the createAssistant/updateAssistant response if known
	 */

	/** 
	 * Handles form submission (Create or Update).
	 * @param {Event} event - The form submission event.
	 */
	async function handleSubmit(event) {
		event.preventDefault();
		formError = '';
		successMessage = '';
		formLoading = true;

		if (!name?.trim()) {
			formError = 'Assistant Name is required.';
			formLoading = false;
			return;
		}

		// Validate rubric selection if rubric_rag is selected
		if (isRubricRag(selectedRagProcessor) && !selectedRubricId) {
			formError = 'Please select a rubric when using Rubric RAG.';
			formLoading = false;
			return;
		}

		// In non-advanced mode, ensure defaults are used
		if (formState === 'create' && !isAdvancedMode) {
			const defaults = get(assistantConfigStore).configDefaults?.config || {};
			selectedPromptProcessor = defaults.prompt_processor || (promptProcessors.length > 0 ? promptProcessors[0] : '');
			selectedConnector = defaults.connector || (connectorsList.length > 0 ? connectorsList[0] : '');
			// Update available models based on the default connector
			await tick();
			configPanel?.updateAvailableModels();
			// Reset LLM if needed with the new models list
			if (!availableModels.includes(selectedLlm)) {
				selectedLlm = defaults.llm || (availableModels.length > 0 ? availableModels[0] : '');
			}
		}

		// Construct the data for the metadata field
		/** @type {Record<string, any>} */
		const metadataObj = {
			prompt_processor: selectedPromptProcessor,
			connector: selectedConnector,
			llm: selectedLlm,
			rag_processor: selectedRagProcessor,
			file_path: isSingleFileRag(selectedRagProcessor) ? selectedFilePath : '',
			capabilities: {
				vision: visionEnabled,
				image_generation: imageGenerationEnabled
			}
		};

		// Add rubric fields if rubric_rag is selected
		if (isRubricRag(selectedRagProcessor)) {
			metadataObj.rubric_id = selectedRubricId;
			metadataObj.rubric_format = rubricFormat;
		}

		// Construct payload according to the expected API structure
		const assistantDataPayload = {
			name: name.trim(),
			description: description,
			system_prompt: system_prompt,
			prompt_template: prompt_template,
			RAG_Top_k: Number(RAG_Top_k) || 3,
			RAG_collections: (isKbBasedRag(selectedRagProcessor)) ? selectedKnowledgeBases.join(',') : '',
			// Add metadata with the stringified JSON
			metadata: JSON.stringify(metadataObj),
			pre_retrieval_endpoint: '',
			post_retrieval_endpoint: '',
			RAG_endpoint: ''
		};

		try {
			/** @type {AssistantResponse} */
			let response;
			if (formState === 'edit' && initialAssistantData?.id) { // Check formState and ID from initial data

				const updateResponse = await updateAssistant(initialAssistantData.id.toString(), assistantDataPayload); // Ensure ID is string
				successMessage = 'Assistant updated successfully!';
				// Reset dirty state after successful save
				formDirty = false;

				// and stay in edit mode. The parent page handles list refresh via the event.
				// Preserve the original metadata structure (object) instead of using the payload's stringified version
				initialAssistantData = {
					...initialAssistantData,
					...assistantDataPayload,
					metadata: metadataObj // Use the parsed metadata object, not the stringified version
				};
				populateFormFields(initialAssistantData); // Update form with potentially modified response data
				onFormSuccess({ assistantId: initialAssistantData.id });
			} else if (formState === 'create') {
				// Handle create case here
				const createResponse = await createAssistant(assistantDataPayload);
				if (!createResponse?.assistant_id) {
					throw new Error('Create assistant response did not include an assistant_id.');
				}
				successMessage = 'Assistant created successfully!';
				// Reset dirty state after successful create
				formDirty = false;

				onFormSuccess({ assistantId: createResponse.assistant_id });
			} else {
				throw new Error('Invalid form state for submission.');
			}
		} catch (error) {
			console.error(`Error ${formState === 'edit' ? 'updating' : 'creating'} assistant:`, error);
			formError = error instanceof Error ? error.message : `Failed to ${formState === 'edit' ? 'update' : 'create'} assistant`;
			successMessage = ''; // Clear success on error
		} finally {
			formLoading = false;
		}
	}

	// --- Import Functionality ---

	/**
	 * Handles file selection for import.
	 * @param {Event} event
	 */
	function handleFileSelect(event) {
		const inputElement = /** @type {HTMLInputElement} */ (event.target);
		const files = inputElement.files;
		importError = ''; // Clear previous import errors
		let validationLog = ['Starting validation...'];

		if (files && files.length > 0) {
			const file = files[0];

			if (file.type !== 'application/json' && !file.name.toLowerCase().endsWith('.json')) {
				importError = $_('assistants.form.import.invalidFile', { default: 'Invalid file type. Please select a .json file.' });
				console.error(importError);
				inputElement.value = ''; // Clear the input
				return;
			}

			const reader = new FileReader();

			reader.onload = async (e) => {
				const content = e.target?.result;
				if (typeof content === 'string') {

					const storeState = get(assistantConfigStore);
					const capabilities = storeState.systemCapabilities;
					const { parsedData, callbackData, validationLog, hasErrors } = validateImportedAssistant(
						content, capabilities, extractModelsFromConnectorData
					);

					// --- Validation Summary ---

					if (!hasErrors && parsedData && callbackData) {
						try {
							validationLog.push('ℹ️ Populating form fields...');

							// Populate basic fields
							name = parsedData.name || ''; // Keep original name for now, user can change
							description = parsedData.description || '';
							system_prompt = parsedData.system_prompt || '';
							prompt_template = parsedData.prompt_template || '';
							RAG_Top_k = parsedData.RAG_Top_k ?? 3;

							// Populate selections from metadata
							selectedPromptProcessor = callbackData.prompt_processor || (promptProcessors.length > 0 ? promptProcessors[0] : '');
							selectedConnector = callbackData.connector || (connectorsList.length > 0 ? connectorsList[0] : '');
							selectedRagProcessor = callbackData.rag_processor || (ragProcessors.length > 0 ? ragProcessors[0] : '');

							// Update models based on connector, then set LLM
							configPanel?.updateAvailableModels();
							selectedLlm = createModelSelector(callbackData.llm, availableModels);
							if (callbackData.llm && !availableModels.includes(callbackData.llm)) {
								validationLog.push(`⚠️ Imported LLM '${callbackData.llm}' not available for connector '${selectedConnector}'. Defaulting to '${selectedLlm}'.`);
							}

						// Populate RAG specific fields
						// FIX FOR ISSUE #96: Apply Load-Then-Select pattern for imports too
						if (isKbBasedRag(selectedRagProcessor)) {
							selectedFilePath = ''; // Clear file path if switching to simple RAG, context_aware_rag, or hierarchical_rag
							// Fetch KBs BEFORE setting selections
							if (!kbFetchAttempted) {

								await fetchKnowledgeBases(); // ✅ WAIT for KBs to load
							}
							// NOW set selections when KB list is ready
							selectedKnowledgeBases = parsedData.RAG_collections?.split(',').filter(Boolean) || [];

						} else if (isSingleFileRag(selectedRagProcessor)) {
							selectedKnowledgeBases = []; // Clear KBs if switching to single file RAG
							// Fetch files BEFORE setting selection
							if (!filesFetchAttempted) {

								await fetchUserFiles(); // ✅ WAIT for files to load
							}
							// NOW set selection when file list is ready
							selectedFilePath = callbackData.file_path || '';

						} else { // No RAG
							selectedKnowledgeBases = [];
							selectedFilePath = '';
						}
							validationLog.push('✅ Form fields populated successfully.');
							importError = ''; // Clear any previous error
							// Show success message briefly
							successMessage = $_('assistants.form.import.success', { default: 'Assistant data imported successfully! Please review and save.' });
							setTimeout(() => { successMessage = ''; }, 5000); // Clear success after 5 seconds

						} catch (populationError) {
							validationLog.push(`❌ Error populating form: ${populationError instanceof Error ? populationError.message : 'Unknown population error'}`);
							importError = $_('assistants.form.import.populationError', { default: 'Error populating form from imported data. Check console.' });
						}
					} else {
						importError = $_('assistants.form.import.validationFailed', { default: 'Import validation failed. Form not populated. Check console for details.' });
					}

				} else {
					console.error('Failed to read file content as string.');
					importError = $_('assistants.form.import.readError', { default: 'Could not read file content.' });
					validationLog.push(`❌ ${importError}`);
				}
			};

			reader.onerror = (e) => {
				console.error('Error reading file:', e);
				importError = $_('assistants.form.import.fileReadError', { default: 'Error reading the selected file.' });
				validationLog.push(`❌ ${importError}`);
			};

			reader.readAsText(file);
		}

		// Clear the file input value so the same file can be selected again
		inputElement.value = '';
	}

</script>

	<div class="p-4 md:p-6 border rounded-md shadow-sm bg-white">

	<AssistantFormHeader
		{formState}
		assistantId={initialAssistantData?.id}
		{importError}
		onImportFile={handleFileSelect}
	/>

	{#if $assistantConfigStore.loading && !configInitialized}
		<p class="text-center text-gray-600 py-10">{$_('assistants.loadingConfig', { default: 'Loading configuration...' })}</p>
	{:else if $assistantConfigStore.error}
		<p class="text-center text-red-600 py-10">{$_('assistants.errorConfig', { default: 'Error loading configuration:' })} {$assistantConfigStore.error}</p>
	{:else if !configInitialized}
		<p class="text-center text-gray-600 py-10">{$_('assistants.initializingForm', { default: 'Initializing form...' })}</p>
	{:else}
		<!-- Form starts here -->
		<form 
			onsubmit={handleSubmit} 
			class="space-y-6"
			id="assistant-form-main" 
		>
			<div class="flex flex-col md:flex-row md:space-x-6">
				<!-- Left Column: Main Fields -->
				<div class="md:w-2/3 space-y-6">
					<AssistantNameField bind:value={name} {formState} onchange={handleFieldChange} />

					<AssistantDescriptionField
						bind:value={description}
						generationContext={{
							name,
							system_prompt,
							prompt_template,
							connector: selectedConnector,
							llm: selectedLlm,
							rag_processor: selectedRagProcessor
						}}
						onchange={handleFieldChange}
					/>

				<AssistantPromptFields
					bind:systemPrompt={system_prompt}
					bind:promptTemplate={prompt_template}
					{ragPlaceholders}
					{selectedPromptProcessor}
					{formState}
					onchange={handleFieldChange}
					onTemplateApplied={() => {
						formDirty = true;
					}}
				/>

				{#if showRubricSelector}
					<RubricSelector
						rubrics={accessibleRubrics}
						loading={loadingRubrics}
						error={rubricError}
						bind:selectedRubricId
						bind:rubricFormat
					/>
				{/if}
			</div>

			<!-- Right Column: Configuration -->
			<div class="md:w-1/3">
				<ConfigurationPanel
					bind:this={configPanel}
					{formState}
					bind:isAdvancedMode
					{promptProcessors}
					{connectorsList}
					{ragProcessors}
					bind:selectedPromptProcessor
					bind:selectedConnector
					bind:selectedLlm
					bind:selectedRagProcessor
					bind:visionEnabled
					bind:imageGenerationEnabled
					bind:RAG_Top_k
					{ownedKnowledgeBases}
					{sharedKnowledgeBases}
					bind:selectedKnowledgeBases
					{loadingKnowledgeBases}
					{knowledgeBaseError}
					{userFiles}
					bind:selectedFilePath
					{loadingFiles}
					{fileError}
					onFilesChanged={fetchUserFiles}
					onchange={handleFieldChange}
				/>
			</div>
			</div> 
			
			<FormActions
				{formState}
				{formLoading}
				{formError}
				{successMessage}
				{name}
				oncancel={switchToViewMode}
			/>

		</form>
	{/if} 

	<!-- Template Selection Modal -->
	<TemplateSelectModal />

</div> 