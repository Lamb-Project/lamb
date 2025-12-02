<script>
	console.log('AssistantForm.svelte: Initializing script...'); // Log component init
	// Placeholder for Assistant Creation Form
	import { _ } from '$lib/i18n';
	import { assistantConfigStore } from '$lib/stores/assistantConfigStore'; // Import the store
	import { tick } from 'svelte'; // Import tick for $effect timing
	import { get } from 'svelte/store'; // Import get
	import { getUserKnowledgeBases, getSharedKnowledgeBases } from '$lib/services/knowledgeBaseService'; // Import KB service
	import { createAssistant, updateAssistant } from '$lib/services/assistantService'; // Import create service and update service
	import { fetchAccessibleRubrics } from '$lib/services/rubricService'; // Import rubric service
	import { goto } from '$app/navigation'; // Import for redirect
	import { base } from '$app/paths'; // Import base path
	import { createEventDispatcher } from 'svelte'; // Import event dispatcher
	import { onMount } from 'svelte';
	import { getSystemCapabilities } from '$lib/services/assistantService'; // Import service
	import { locale } from '$lib/i18n';
	import TemplateSelectModal from '$lib/components/modals/TemplateSelectModal.svelte'; // Import template modal
	import { openTemplateSelectModal } from '$lib/stores/templateStore'; // Import template store function
	import { sanitizeName } from '$lib/utils/nameSanitizer'; // Import sanitization utility

	const dispatch = createEventDispatcher(); // For dispatching success event

	// --- Props --- 
	// Use $props for Svelte 5 runes mode
	let { 
		assistant = null,
		startInEdit = false // Add the new prop
	} = $props(); 
	console.log(`[AssistantForm] Received props: assistant=${!!assistant}, startInEdit=${startInEdit}`); // Log received props

	// --- Component State ---
	/** @type {'edit' | 'create'} */
	// Initialize formState based on assistant and startInEdit prop
	let initialMode = assistant ? 'edit' : 'create';
	console.log(`[AssistantForm] Calculated initialMode: ${initialMode}`); // Log calculated initial mode
	let formState = $state(initialMode); 
	/** @type {any | null} */ // Store initial data for cancel/revert
	let initialAssistantData = $state(null); 

	// --- Form Field State Variables ---
	let name = $state('');
	// Derived: Sanitized name preview
	let sanitizedNameInfo = $derived(sanitizeName(name));
	let showSanitizationPreview = $derived(formState === 'create' && sanitizedNameInfo.wasModified);
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
	let availableModels = $state([]);
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

	// Tools State
	/** @type {Array<{name: string, description: string, category: string, function_name: string}>} */
	let availableTools = $state([]);
	/** @type {string[]} */
	let selectedTools = $state([]); // Array of selected tool names
	let loadingTools = $state(false);
	let toolsError = $state('');
	let toolsFetchAttempted = $state(false);

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
	let fileUploadLoading = $state(false);
	let fileUploadError = $state('');
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
	let rubricSearchQuery = $state(''); // Search filter for rubrics

	// Loading/error/success state
	let formError = $state('');
	let formLoading = $state(false); 
	let generatingDescription = $state(false);
	let configInitialized = $state(false); 
	let successMessage = $state('');
	
	// Handler for template selection
	function handleTemplateSelected(/** @type {any} */ template) {
		// Only populate system_prompt and prompt_template
		system_prompt = template.system_prompt || '';
		prompt_template = template.prompt_template || '';
		// Mark form as dirty since we're making changes
		formDirty = true;
	}
	
	// Handler to open template selection modal
	function handleLoadTemplate() {
		openTemplateSelectModal(handleTemplateSelected);
	} 

	// Initialize with default, will be set correctly by populate/reset functions later
	let ragProcessor = $state('simple_rag'); 
	let isProcessing = $state(false);
	let serverError = $state('');
	let importError = $state(''); // State for import errors
	let localeLoaded = $state(false);

	// Form dirty state tracking to prevent overwriting user edits
	// See: Documentation/lamb_architecture.md Section 16.1
	let formDirty = $state(false);
	let previousAssistantId = $state(null);

	/** @type {HTMLTextAreaElement | null} */
	let textareaRef = $state(null);
	/** @type {string[]} */
	let ragPlaceholders = $state([]);  // Initialize as empty array to be filled from config
	// Plain text placeholder to avoid template interpolation issues
	const promptPlaceholderText = "e.g. Use the {context} to answer the question: {user_input}";

	/**
	 * Determines if a field should be editable based on current form state
	 * @param {string} fieldName - The name of the field to check
	 * @returns {boolean} Whether the field should be editable
	 */
	function isFieldEditable(fieldName) {
		// In create mode, all fields are editable
		if (formState === 'create') return true;
		
		// In edit mode, certain fields may be restricted
		// Add specific field restrictions here if needed
		// For now, make all fields editable
		return true;
	}

	/**
	 * Mark form as dirty when user makes changes
	 * This prevents automatic repopulation from overwriting user edits
	 */
	function handleFieldChange() {
		if (!formDirty) {
			console.log('[AssistantForm] Form marked as dirty - user made changes');
		}
		formDirty = true;
	}

	/**
	 * Highlights placeholders in the prompt template text
	 * @param {string} text - The text to process
	 * @returns {string} HTML string with highlighted placeholders
	 */
	function highlightPlaceholders(text) {
		if (!text) return '';
		let result = text;
		// Escape HTML to prevent XSS
		result = result.replace(/&/g, '&amp;')
					  .replace(/</g, '&lt;')
					  .replace(/>/g, '&gt;')
					  .replace(/"/g, '&quot;')
					  .replace(/'/g, '&#039;');
		
		// Replace placeholders with highlighted spans
		for (const placeholder of ragPlaceholders) {
			const escapedPlaceholder = placeholder.replace(/&/g, '&amp;')
											   .replace(/</g, '&lt;')
											   .replace(/>/g, '&gt;')
											   .replace(/"/g, '&quot;')
											   .replace(/'/g, '&#039;');
			
			result = result.replace(
				new RegExp(escapedPlaceholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), 
				`<span class="bg-blue-100 text-blue-800 font-medium px-1 rounded">${escapedPlaceholder}</span>`
			);
		}
		return result;
	}

	// --- Store Integration and Initialization ---
	$effect(() => {
		console.log('AssistantForm.svelte: $effect (assistant prop) running...');

		const assistantIdChanged = assistant?.id !== initialAssistantData?.id;
		const assistantNullStatusChanged = (assistant === null && initialAssistantData !== null) || (assistant !== null && initialAssistantData === null);

		// Check if the assistant data content has changed (not just ID)
		const assistantDataChanged = assistant && initialAssistantData &&
			(assistant.system_prompt !== initialAssistantData.system_prompt ||
			 assistant.prompt_template !== initialAssistantData.prompt_template ||
			 assistant.name !== initialAssistantData.name ||
			 assistant.description !== initialAssistantData.description);

		if (assistantIdChanged || assistantNullStatusChanged || assistantDataChanged) {
			console.log(`[AssistantForm] Assistant change detected (ID changed: ${assistantIdChanged}, Null status changed: ${assistantNullStatusChanged}, Data changed: ${assistantDataChanged})`);
			if (assistant) {
				console.log('[AssistantForm] Assistant prop received or changed:', assistant);
				console.log('Assistant prop received or changed:', assistant);
				initialAssistantData = { ...assistant };
				console.log('Stored initial assistant data:', initialAssistantData);
				// Always set to edit mode when assistant changes
				formState = 'edit';
				console.log(`Initial formState set to: ${formState}`);

				// Track assistant ID for dirty state management
				previousAssistantId = assistant.id;
				// Reset dirty state when loading a different assistant
				formDirty = false;
				console.log('[AssistantForm] Loading new assistant, formDirty reset to false');

				populateFormFields(assistant);
				formError = '';
				successMessage = '';
			} else {
				console.log('No assistant prop, setting create mode.');
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
				console.log('[AssistantForm] Skipping full repopulation - form is clean but only assistant reference changed. Protecting user selections.');
				// We intentionally do NOT call populateFormFields here to protect dropdown selections
				// The only case where we'd repopulate is on actual ID change (handled above)
			} else if (assistant && formDirty) {
				console.log('[AssistantForm] Skipping repopulation - form is dirty (user has unsaved changes)');
			}
		}
	});

	// Effect for loading config and applying defaults
	$effect.pre(() => {
		if (!configInitialized && !$assistantConfigStore.loading && !$assistantConfigStore.systemCapabilities) {
			console.log('AssistantForm.svelte: $effect.pre - Explicitly calling loadConfig()...');
			assistantConfigStore.loadConfig();
		}

		const unsubscribe = assistantConfigStore.subscribe(state => {
			// console.log(`AssistantForm.svelte: Store subscribed - State (Loading: ${state.loading}, Caps: ${!!state.systemCapabilities}, Defaults: ${!!state.configDefaults}, Initialized: ${configInitialized})`);

			if (!state.loading && state.systemCapabilities && state.configDefaults && !configInitialized) {
				const capabilities = state.systemCapabilities;
				
				console.log('Populating dropdown options from capabilities...');
				promptProcessors = capabilities.prompt_processors || [];
				connectorsList = Object.keys(capabilities.connectors || {});
				ragProcessors = capabilities.rag_processors || [];
				// console.log('Options populated:', { promptProcessors, connectorsList, ragProcessors });

				configInitialized = true; 

				// Fetch available tools when config initializes
				tick().then(fetchAvailableTools);

				if (formState === 'create') {
					console.log('Applying defaults for CREATE mode...');
					resetFormFieldsToDefaults(); // Use helper
				} else {
					console.log('Config loaded for VIEW/EDIT mode. Repopulating fields.');
					// Use initialAssistantData here as assistant prop might not be stable yet
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
			console.log('Effect: KB fetch complete, applying pending selections:', pendingKBSelections);
			console.log('Effect: Available KBs - Owned:', ownedKnowledgeBases.length, 'Shared:', sharedKnowledgeBases.length);
			selectedKnowledgeBases = pendingKBSelections;
			pendingKBSelections = null; // Clear pending state
			console.log('Effect: KB selections applied:', selectedKnowledgeBases);
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
		let defaultRag = defaults.rag_processor?.trim().toLowerCase();
		if (defaultRag === 'no rag') defaultRag = 'no_rag';
		selectedRagProcessor = defaultRag || (ragProcessors.length > 0 ? ragProcessors[0] : '');
		
		// Load the placeholders from config
		// Using a more robust approach to handle the property access
		try {
			// @ts-ignore - Property exists at runtime but not in type definition
			ragPlaceholders = Array.isArray(defaults.rag_placeholders) ? defaults.rag_placeholders : ["{context}", "{user_input}"];
		} catch (e) {
			console.warn("Could not load rag_placeholders from config, using defaults:", e);
			ragPlaceholders = ["{context}", "{user_input}"];
		}
		
		// Update available models based on selected connector
		updateAvailableModels();
		// Set LLM with fallback to first available model if default not available
		const defaultLlm = defaults.llm || '';
		if (defaultLlm && availableModels.includes(defaultLlm)) {
			selectedLlm = defaultLlm;
		} else {
			selectedLlm = availableModels.length > 0 ? availableModels[0] : '';
		}
		
		selectedKnowledgeBases = [];
		selectedFilePath = '';
		visionEnabled = false; // Reset vision capability for new assistants
		selectedTools = []; // Reset tools for new assistants
		imageGenerationEnabled = false; // Reset image generation capability for new assistants
		imageGenerationEnabled = false; // Reset image generation capability for new assistants
		// Reset name/description only if truly starting fresh?
		// name = '';
		// description = ''; 
		console.log('Form reset to defaults for CREATE:', { selectedPromptProcessor, selectedConnector, selectedLlm, selectedRagProcessor, availableModels });
		if (selectedRagProcessor === 'simple_rag') {
			tick().then(fetchKnowledgeBases);
		}
		if (selectedRagProcessor === 'single_file_rag') {
			tick().then(fetchUserFiles);
		}
		if (selectedRagProcessor === 'rubric_rag') {
			tick().then(fetchRubricsList);
		}
	}

	// --- Mode Switching Functions ---
	function switchToEditMode() {
		formState = 'edit';
		formError = '';
		successMessage = '';
		console.log('Switched to EDIT mode');
	}

	function switchToViewMode() {
		// Revert fields to initial state
		if (initialAssistantData) {
			populateFormFields(initialAssistantData);
		}
		// Reset dirty state when canceling (user discarded changes)
		formDirty = false;
		console.log('[AssistantForm] User canceled changes, formDirty reset to false');
		formError = '';
		successMessage = '';
		console.log('Switched back to VIEW mode');
		
		// Dispatch cancel event to parent to handle navigation
		dispatch('cancel');
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
		console.log('[populateFormFields] Called with data:', data);
		console.log('[populateFormFields] configInitialized:', configInitialized);
		
		name = data.name?.replace(/^\d+_/, '') || '';
		// Only update description if not preserving current edits
		if (!preserveDescription) {
			description = data.description || ''; 
		}
		system_prompt = data.system_prompt || '';
		prompt_template = data.prompt_template || '';
		RAG_Top_k = data.RAG_Top_k ?? 3;
		
		if (configInitialized) {
			// Use direct properties from the data object
			selectedPromptProcessor = data.prompt_processor || (promptProcessors.length > 0 ? promptProcessors[0] : '');
			console.log('[populateFormFields] Set selectedPromptProcessor:', selectedPromptProcessor);
			
			selectedConnector = data.connector || (connectorsList.length > 0 ? connectorsList[0] : '');
			console.log('[populateFormFields] Set selectedConnector:', selectedConnector);
			
			selectedRagProcessor = data.rag_processor || (ragProcessors.length > 0 ? ragProcessors[0] : '');
			console.log('[populateFormFields] Set selectedRagProcessor:', selectedRagProcessor);
			
			// Update available models based on the selected connector
			updateAvailableModels();
			console.log('[populateFormFields] Updated availableModels:', availableModels);
			
			// Set LLM - ensure we check if the data.llm exists in availableModels
			const targetLlm = data.llm;
			if (targetLlm && availableModels.includes(targetLlm)) {
				selectedLlm = targetLlm;
				console.log('[populateFormFields] Set selectedLlm to saved value:', selectedLlm);
			} else if (targetLlm) {
				// Model not available in current connector, fallback to first available
				selectedLlm = availableModels.length > 0 ? availableModels[0] : '';
				console.warn(`[populateFormFields] LLM '${targetLlm}' not available for connector '${selectedConnector}'. Using fallback:`, selectedLlm);
			} else {
				// No LLM in data, use first available
				selectedLlm = availableModels.length > 0 ? availableModels[0] : '';
				console.log('[populateFormFields] No LLM in data, using first available:', selectedLlm);
			}

			// Load placeholders from config for edit mode as well
			const defaults = get(assistantConfigStore).configDefaults?.config || {};
			try {
				// @ts-ignore - Property exists at runtime but not in type definition
				ragPlaceholders = Array.isArray(defaults.rag_placeholders) ? defaults.rag_placeholders : ["{context}", "{user_input}"];
			} catch (e) {
				console.warn("Could not load rag_placeholders from config in edit mode, using defaults:", e);
				ragPlaceholders = ["{context}", "{user_input}"];
			}
			
			// FIX FOR ISSUE #96: Deferred Selection Pattern
			// Store pending selections that will be applied when options are ready
			if (selectedRagProcessor === 'simple_rag') {
				// Store selections to be applied later
				pendingKBSelections = data.RAG_collections?.split(',').filter(Boolean) || [];
				console.log('Populate: Stored pending KB selections:', pendingKBSelections);
				
				// Trigger fetch if needed (don't wait)
				if (!kbFetchAttempted && !loadingKnowledgeBases) {
					console.log('Populate: Triggering KB fetch');
					tick().then(fetchKnowledgeBases);
				}
			} else {
				// Clear pending selections if not using simple_rag
				pendingKBSelections = null;
			}

			// Handle rubric fields if rubric_rag is selected
			if (selectedRagProcessor === 'rubric_rag') {
				try {
					// Parse metadata if it's a string
					let metadata = data.metadata;
					if (typeof metadata === 'string') {
						metadata = JSON.parse(metadata);
					}

					selectedRubricId = metadata?.rubric_id || '';
					rubricFormat = metadata?.rubric_format || 'markdown';

					// Fetch rubrics if needed
					if (!rubricsFetchAttempted && !loadingRubrics) {
						console.log('Populate: Triggering rubrics fetch');
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
				let metadata = data.metadata;
				if (typeof metadata === 'string') {
					metadata = JSON.parse(metadata);
				}

				visionEnabled = metadata?.capabilities?.vision || false;
				imageGenerationEnabled = metadata?.capabilities?.image_generation || false;
				console.log('Populate: Vision capability loaded:', visionEnabled);
				console.log('Populate: Image generation capability loaded:', imageGenerationEnabled);
			} catch (e) {
				console.warn('Failed to parse vision capability from metadata:', e);
				visionEnabled = false;
			}

			// Handle tools selection
			try {
				let metadata = data.metadata;
				if (typeof metadata === 'string') {
					metadata = JSON.parse(metadata);
				}

				selectedTools = Array.isArray(metadata?.tools) ? metadata.tools : [];
				console.log('Populate: Tools loaded:', selectedTools);
			} catch (e) {
				console.warn('Failed to parse tools from metadata:', e);
				selectedTools = [];
			}

			// TODO: Handle file selection for single_file_rag if needed
			// selectedFilePath = data.file_path || '';
		} else {
			console.warn('[populateFormFields] Config not initialized yet, skipping dropdown population');
		}
		console.log('[populateFormFields] Complete. Final values:', { 
			name, 
			description: description.substring(0, 50) + '...', 
			selectedPromptProcessor, 
			selectedConnector, 
			selectedLlm, 
			selectedRagProcessor 
		});
	}

	/** 
	 * Extracts models from potentially varied connector data structures 
	 * @param {any} connectorData - The connector data object (structure may vary)
	 */
	function extractModelsFromConnectorData(connectorData) {
		if (!connectorData) return [];
		if (Array.isArray(connectorData.models)) return connectorData.models;
		if (Array.isArray(connectorData.available_llms)) return connectorData.available_llms;
		if (typeof connectorData.models === 'object' && connectorData.models !== null) return Object.keys(connectorData.models);
		return [];
	}

	/** Updates the available LLMs based on the selected connector */
	function updateAvailableModels() {
		const state = get(assistantConfigStore); // Use get() to read store value non-reactively
		if (!state || !state.systemCapabilities || !state.systemCapabilities.connectors) {
			availableModels = [];
			return;
		}
		const connectorData = state.systemCapabilities.connectors[selectedConnector];
		availableModels = extractModelsFromConnectorData(connectorData);
	}

	/** Handles connector dropdown change */
	async function handleConnectorChange() {
		console.log('Connector changed to:', selectedConnector);
		updateAvailableModels();
		await tick();
		if (!availableModels.includes(selectedLlm)) {
			selectedLlm = availableModels.length > 0 ? availableModels[0] : '';
			console.log('Resetting LLM to:', selectedLlm);
		}

		// Validate vision capability - only available for OpenAI
		if (selectedConnector !== 'openai' && visionEnabled) {
			console.log('Disabling vision capability - not supported for connector:', selectedConnector);
			visionEnabled = false;
		}

		// Validate image generation capability - only available for banana-img
		if (selectedConnector !== 'banana-img' && imageGenerationEnabled) {
			console.log('Disabling image generation capability - not supported for connector:', selectedConnector);
			imageGenerationEnabled = false;
		}
	}

	/** Fetches accessible knowledge bases */
	async function fetchKnowledgeBases() {
		// Prevent fetch if already loading OR if already attempted for this selection
		if (loadingKnowledgeBases || kbFetchAttempted) {
			console.log(`Skipping KB fetch (Loading: ${loadingKnowledgeBases}, Attempted: ${kbFetchAttempted})`);
			return;
		}
		// Ensure we actually need KBs
		if (selectedRagProcessor !== 'simple_rag') {
			console.log('Skipping KB fetch (RAG processor is not simple_rag)');
			return;
		}

		console.log('Fetching knowledge bases...');
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
			
			// Sort each separately
			owned.sort((a, b) => a.name.localeCompare(b.name));
			shared.sort((a, b) => a.name.localeCompare(b.name));
			
			ownedKnowledgeBases = owned;
			sharedKnowledgeBases = shared;
		} catch (err) {
			console.error('Error fetching knowledge bases:', err);
			knowledgeBaseError = err instanceof Error ? err.message : 'Failed to load knowledge bases';
			ownedKnowledgeBases = [];
			sharedKnowledgeBases = [];
		} finally {
			loadingKnowledgeBases = false;
			kbFetchAttempted = true; // Mark fetch as attempted
			console.log(`KB Fetch complete (Attempted: ${kbFetchAttempted}, Error: '${knowledgeBaseError}', Owned: ${ownedKnowledgeBases.length}, Shared: ${sharedKnowledgeBases.length})`);
		}
	}

	async function fetchRubricsList() {
		// Prevent fetch if already loading OR if already attempted for this selection
		if (loadingRubrics || rubricsFetchAttempted) {
			console.log(`Skipping rubrics fetch (Loading: ${loadingRubrics}, Attempted: ${rubricsFetchAttempted})`);
			return;
		}
		// Ensure we actually need rubrics
		if (selectedRagProcessor !== 'rubric_rag') {
			console.log('Skipping rubrics fetch (RAG processor is not rubric_rag)');
			return;
		}

		console.log('Fetching accessible rubrics...');
		loadingRubrics = true;
		rubricError = '';

		try {
			const response = await fetchAccessibleRubrics();
			const rubrics = response.rubrics || [];
			accessibleRubrics = rubrics;
			console.log(`Loaded ${rubrics.length} accessible rubrics`);
		} catch (err) {
			console.error('Error fetching accessible rubrics:', err);
			rubricError = err instanceof Error ? err.message : 'Failed to load rubrics';
			accessibleRubrics = []; // Ensure list is empty on error
		} finally {
			loadingRubrics = false;
			rubricsFetchAttempted = true; // Mark fetch as attempted
			console.log(`Rubrics Fetch complete (Attempted: ${rubricsFetchAttempted}, Error: '${rubricError}', Count: ${accessibleRubrics.length})`);
		}
	}

	/** Fetches available tools from the backend */
	async function fetchAvailableTools() {
		// Prevent fetch if already loading OR if already attempted
		if (loadingTools || toolsFetchAttempted) {
			console.log(`Skipping tools fetch (Loading: ${loadingTools}, Attempted: ${toolsFetchAttempted})`);
			return;
		}

		console.log('Fetching available tools...');
		loadingTools = true;
		toolsError = '';

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

			// Call the tools endpoint
			const endpointPath = '/lamb/v1/completions/tools';
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
			availableTools = data.tools || [];
			console.log(`Loaded ${availableTools.length} available tools`);
		} catch (err) {
			console.error('Error fetching available tools:', err);
			toolsError = err instanceof Error ? err.message : 'Failed to load tools';
			availableTools = [];
		} finally {
			loadingTools = false;
			toolsFetchAttempted = true;
			console.log(`Tools Fetch complete (Attempted: ${toolsFetchAttempted}, Error: '${toolsError}', Count: ${availableTools.length})`);
		}
	}

	/** Fetches the user's files from the server */
	async function fetchUserFiles() {
		if (loadingFiles) {
			console.log('Skipping files fetch (already loading)');
			return;
		}

		console.log('Fetching user files...');
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
			
			// Set selected file if it exists in metadata (fallback to api_callback)
			const metadataStr = assistant?.metadata || assistant?.api_callback;
			if (metadataStr) {
				try {
					const callbackData = JSON.parse(metadataStr);
					if (callbackData.file_path && userFiles.some(file => file.path === callbackData.file_path)) {
						selectedFilePath = callbackData.file_path;
					}
				} catch (e) {
					console.error('Error parsing metadata for file path:', e);
				}
			}
			
			console.log(`Fetched ${userFiles.length} files`);
		} catch (err) {
			console.error('Error fetching user files:', err);
			fileError = err instanceof Error ? err.message : 'Failed to load files';
			userFiles = []; // Ensure list is empty on error
		} finally {
			loadingFiles = false;
			filesFetchAttempted = true;
		}
	}

	/** Handles file upload to the server 
	 * @param {Event} event - The change event
	 */
	async function handleFileUpload(event) {
		// Extract the file from the input element
		const input = event.target;
		if (!input || !(input instanceof HTMLInputElement) || !input.files || input.files.length === 0) {
			return;
		}

		const file = input.files[0];
		if (!file) {
			return;
		}

		fileUploadLoading = true;
		fileUploadError = '';

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found');
			}

			// Get the lamb server URL
			const lambServerUrl = window.LAMB_CONFIG?.api?.lambServer;
			if (!lambServerUrl) {
				throw new Error('LAMB server URL not configured');
			}

			// Create FormData object
			const formData = new FormData();
			formData.append('file', file);

			// Call the files/upload endpoint
			const endpointPath = '/creator/files/upload';
			const apiUrl = `${lambServerUrl.replace(/\/$/, '')}${endpointPath}`;
			
			const response = await fetch(apiUrl, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${token}`
				},
				body: formData
			});

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`API error: ${response.status} - ${errorText || 'Unknown error'}`);
			}

			const data = await response.json();
			console.log('File uploaded successfully:', data);
			
			// Refresh the file list
			await fetchUserFiles();
			
			// Auto-select the newly uploaded file
			if (data.path) {
				selectedFilePath = data.path;
			}
			
			// Clear the file input
			input.value = '';
		} catch (err) {
			console.error('Error uploading file:', err);
			fileUploadError = err instanceof Error ? err.message : 'Failed to upload file';
		} finally {
			fileUploadLoading = false;
		}
	}

	/** Extract auth token from correct storage location */
	function getAuthToken() {
		// Get token from localStorage first (which is how other service calls are authenticating)
		if (typeof localStorage !== 'undefined') {
			const token = localStorage.getItem('userToken');
			if (token) {
				console.debug('Auth token found in localStorage');
				return token;
			}
		}
		
		// Fallback to cookie if localStorage doesn't have the token
		console.debug('Token not found in localStorage, checking cookie');
		return document.cookie.replace(/(?:(?:^|.*;\\s*)token\\s*=\\s*([^;]*).*$)|^.*$/, "$1");
	}

	/**
	 * Calls the lamb_helper_assistant API to generate a description for the assistant
	 */
	async function handleGenerateDescription() {
		// Validation check - require name at minimum
		if (!name.trim()) {
			alert($_('assistants.form.description.nameRequired', { default: 'Please provide an assistant name first' }));
			return;
		}

		// Check if auth token is available
		const token = getAuthToken();
		console.debug('Auth token found:', token ? 'Yes (length: ' + token.length + ')' : 'No');
		
		if (!token) {
			console.error('Authentication token not found');
			alert($_('assistants.form.description.authError', { default: 'Authentication error. Please try logging in again.' }));
			return;
		}

		// Set loading state
		generatingDescription = true;
		let descriptionError = '';
		
		try {
			// Get the lamb server URL from window.LAMB_CONFIG
			const lambServerUrl = window.LAMB_CONFIG?.api?.lambServer;
			if (!lambServerUrl) {
				throw new Error('LAMB server URL not configured in window.LAMB_CONFIG.api.lambServer');
			}

			// Add a timeout for better UX
			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout

			// Construct the absolute URL for the new endpoint
			const endpointPath = '/creator/assistant/generate_assistant_description';
			const apiUrl = `${lambServerUrl.replace(/\/$/, '')}${endpointPath}`;
			console.debug('Calling generate_assistant_description at URL:', apiUrl);

			// Prepare the request body in the format expected by the new endpoint
			const requestBody = {
				name: name,
				instructions: system_prompt || "",
				prompt_template: prompt_template || "",
				connector: selectedConnector || "",
				llm: selectedLlm || "",
				rag_processor: selectedRagProcessor || ""
			};

			// Call the description generation API
			const response = await fetch(apiUrl, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${token}`
				},
				body: JSON.stringify(requestBody),
				signal: controller.signal
			});

			clearTimeout(timeoutId); // Clear timeout if request completes

			if (!response.ok) {
				const errorText = await response.text();
				console.error('API error response:', errorText);
				if (response.status === 403 || response.status === 401) {
					throw new Error(`Authentication error (${response.status}): Please try logging in again.`);
				}
				throw new Error(`API error: ${response.status} - ${errorText || 'Unknown error'}`);
			}

			const data = await response.json();
			
			if (data.description) {
				// Process the response: trim, fix quotes, ensure reasonable length
				let processedDescription = data.description.trim().replace(/^["']|["']$/g, '');
				
				// If too long, truncate to reasonable size
				if (processedDescription.length > 500) {
					processedDescription = processedDescription.substring(0, 497) + '...';
				}
				
				description = processedDescription;
				console.log('Description generated successfully');
			} else {
				throw new Error(data.error || 'Failed to generate description');
			}
		} catch (err) {
			console.error('Error generating description:', err);
			if (err instanceof Error && err.name === 'AbortError') {
				descriptionError = $_('assistants.form.description.timeout', { default: 'Request timed out. Please try again.' });
			} else {
				descriptionError = err instanceof Error ? err.message : $_('assistants.form.description.error', { default: 'Failed to generate description' });
			}
			// Show error to user
			alert(descriptionError);
		} finally {
			generatingDescription = false;
		}
	}

	// --- Reactive UI Logic (Mostly Unchanged) ---
	const showRagOptions = $derived(selectedRagProcessor && selectedRagProcessor !== 'no_rag');
	const showKnowledgeBaseSelector = $derived(selectedRagProcessor === 'simple_rag');
	const showSingleFileSelector = $derived(selectedRagProcessor === 'single_file_rag');
	const showRubricSelector = $derived(selectedRagProcessor === 'rubric_rag');
	
	// Filtered rubrics based on search query
	const filteredRubrics = $derived(() => {
		if (!rubricSearchQuery.trim()) {
			return accessibleRubrics;
		}
		const query = rubricSearchQuery.toLowerCase();
		return accessibleRubrics.filter(rubric => 
			rubric.title.toLowerCase().includes(query) || 
			(rubric.description && rubric.description.toLowerCase().includes(query))
		);
	});

	// Effect to fetch KBs/Files when RAG processor changes (Mostly Unchanged)
	$effect(() => {
		console.log(`Effect: RAG processor changed to ${selectedRagProcessor}`);
		if (selectedRagProcessor === 'simple_rag' && configInitialized) {
			// Trigger fetch only if we land on simple_rag and haven't attempted the fetch yet
			console.log(`Effect: Checking KB fetch need (Attempted: ${kbFetchAttempted})`);
			if (!kbFetchAttempted && !loadingKnowledgeBases) { // Check attempted flag, ignore error here
				console.log('Effect: Conditions met (simple_rag, not attempted), calling fetchKnowledgeBases()');
				fetchKnowledgeBases();
			} else {
				console.log('Effect: Skipping KB fetch (already attempted or loading).');
			}
		} else if (selectedRagProcessor === 'single_file_rag' && configInitialized) {
			// Fetch files when switching to single_file_rag
			if (!filesFetchAttempted && !loadingFiles) {
				console.log('Effect: Conditions met (single_file_rag, not attempted), calling fetchUserFiles()');
				fetchUserFiles();
			} else {
				console.log('Effect: Skipping files fetch (already attempted or loading).');
			}
		} else if (selectedRagProcessor === 'rubric_rag' && configInitialized) {
			// Fetch rubrics when switching to rubric_rag
			if (!rubricsFetchAttempted && !loadingRubrics) {
				console.log('Effect: Conditions met (rubric_rag, not attempted), calling fetchRubricsList()');
				tick().then(fetchRubricsList);
			} else {
				console.log('Effect: Skipping rubrics fetch (already attempted or loading).');
			}
		} else {
			// Clear KB state AND reset attempted flag if RAG processor changes away
			if (accessibleKnowledgeBases.length > 0 || selectedKnowledgeBases.length > 0 || knowledgeBaseError || kbFetchAttempted) {
				console.log('Effect: Clearing KB state and fetch attempt flag');
				ownedKnowledgeBases = [];
				sharedKnowledgeBases = [];
				selectedKnowledgeBases = [];
				knowledgeBaseError = '';
				kbFetchAttempted = false; // Reset flag
			}
			
			// Reset file selection if we moved away from single_file_rag
			if (selectedRagProcessor !== 'single_file_rag' && (selectedFilePath || userFiles.length > 0)) {
				selectedFilePath = '';
				// Note: We don't clear userFiles or filesFetchAttempted to avoid refetching if user switches back
			}

			// Reset rubric selection if we moved away from rubric_rag
			if (selectedRagProcessor !== 'rubric_rag' && (selectedRubricId || accessibleRubrics.length > 0)) {
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
		if (selectedRagProcessor === 'rubric_rag' && !selectedRubricId) {
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
			updateAvailableModels();
			// Reset LLM if needed with the new models list
			if (!availableModels.includes(selectedLlm)) {
				selectedLlm = defaults.llm || (availableModels.length > 0 ? availableModels[0] : '');
			}
		}

		// Construct the data for the metadata field
		const metadataObj = {
			prompt_processor: selectedPromptProcessor,
			connector: selectedConnector,
			llm: selectedLlm,
			rag_processor: selectedRagProcessor,
			file_path: selectedRagProcessor === 'single_file_rag' ? selectedFilePath : '',
			capabilities: {
				vision: visionEnabled,
				image_generation: imageGenerationEnabled
			},
			// Add tools if any are selected (only for OpenAI connector)
			tools: selectedConnector === 'openai' && selectedTools.length > 0 ? selectedTools : undefined
		};

		// Add rubric fields if rubric_rag is selected
		if (selectedRagProcessor === 'rubric_rag') {
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
			RAG_collections: selectedRagProcessor === 'simple_rag' ? selectedKnowledgeBases.join(',') : '',
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
				console.log('Submitting UPDATE for assistant:', initialAssistantData.id, assistantDataPayload);
				const updateResponse = await updateAssistant(initialAssistantData.id.toString(), assistantDataPayload); // Ensure ID is string
				successMessage = 'Assistant updated successfully!';
				// Reset dirty state after successful save
				formDirty = false;
				console.log('[AssistantForm] Changes saved successfully, formDirty reset to false');
				// After update, store the updated data as the new initial state
				// Preserve the original metadata structure (object) instead of using the payload's stringified version
				initialAssistantData = {
					...initialAssistantData,
					...assistantDataPayload,
					metadata: metadataObj // Use the parsed metadata object, not the stringified version
				};
				populateFormFields(initialAssistantData); // Update form with potentially modified response data
				dispatch('formSuccess', { assistantId: initialAssistantData.id }); // Dispatch success for update
			} else if (formState === 'create') {
				// Handle create case here
				const createResponse = await createAssistant(assistantDataPayload);
				if (!createResponse?.assistant_id) {
					throw new Error('Create assistant response did not include an assistant_id.');
				}
				successMessage = 'Assistant created successfully!';
				// Reset dirty state after successful create
				formDirty = false;
				console.log('[AssistantForm] Assistant created successfully, formDirty reset to false');
				dispatch('formSuccess', { assistantId: createResponse.assistant_id });
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
	 * Triggers the hidden file input click.
	 */
	function triggerFileInput() {
		document.getElementById('import-assistant-json')?.click();
	}

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
			console.log('Selected file:', file.name, file.type, file.size);

			// Basic validation
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
					console.log('--- Imported Assistant JSON Content ---');
					console.log('-------------------------------------');

					// --- Start Validation ---
					let parsedData;
					try {
						parsedData = JSON.parse(content);
						validationLog.push('✅ JSON parsed successfully.');
					} catch (jsonError) {
						validationLog.push(`❌ Invalid JSON format: ${jsonError instanceof Error ? jsonError.message : 'Unknown JSON error'}`);
						parsedData = null;
					}

					let callbackData = null; // Declare here, after confirming parsedData is object

					if (parsedData && typeof parsedData === 'object') {
						// Get capabilities from store
						const storeState = get(assistantConfigStore);
						const capabilities = storeState.systemCapabilities;

						if (!capabilities) {
							validationLog.push('⚠️ System capabilities not loaded. Skipping detailed validation.');
						} else {
							validationLog.push('ℹ️ System capabilities loaded. Performing detailed checks...');
							// Validate required fields
							const requiredFields = ['name', 'system_prompt', 'metadata']; // Add more if needed
							for (const field of requiredFields) {
								if (!(field in parsedData)) {
									validationLog.push(`❌ Missing required field: ${field}`);
								}
							}

							// Validate metadata content (fallback to api_callback for backward compatibility)
							const metadataStr = parsedData.metadata || parsedData.api_callback;
							if (metadataStr && typeof metadataStr === 'string') {
								try {
									callbackData = JSON.parse(metadataStr);
									validationLog.push('✅ Parsed metadata successfully.');

									// Validate against capabilities
									if (callbackData.prompt_processor && !capabilities.prompt_processors?.includes(callbackData.prompt_processor)) {
										validationLog.push(`⚠️ Invalid prompt_processor: ${callbackData.prompt_processor}. Available: ${capabilities.prompt_processors?.join(', ')}`);
									}
									if (callbackData.connector && !capabilities.connectors?.[callbackData.connector]) {
										validationLog.push(`⚠️ Invalid connector: ${callbackData.connector}. Available: ${Object.keys(capabilities.connectors || {}).join(', ')}`);
									} else if (callbackData.connector && callbackData.llm) {
										// Use optional chaining and check result
										const connectorCaps = capabilities.connectors?.[callbackData.connector]; 
										if (connectorCaps) {
											const availableLLMs = extractModelsFromConnectorData(connectorCaps);
											if (!availableLLMs.includes(callbackData.llm)) {
												validationLog.push(`⚠️ Invalid llm for connector ${callbackData.connector}: ${callbackData.llm}. Available: ${availableLLMs.join(', ')}`);
											}
										} else {
											// Handle case where connector capabilities were not found (though connector name was valid)
											validationLog.push(`⚠️ Could not retrieve capabilities for connector ${callbackData.connector}.`);
										}
									}
									if (callbackData.rag_processor && !capabilities.rag_processors?.includes(callbackData.rag_processor)) {
										validationLog.push(`⚠️ Invalid rag_processor: ${callbackData.rag_processor}. Available: ${capabilities.rag_processors?.join(', ')}`);
									}

									// Specific checks based on rag_processor
									if (callbackData.rag_processor === 'single_file_rag' && !callbackData.file_path) {
										validationLog.push('❌ Missing file_path in metadata for single_file_rag processor.');
									}

									// Validate tools if present
									if (callbackData.tools && Array.isArray(callbackData.tools)) {
										validationLog.push(`ℹ️ Found ${callbackData.tools.length} tool(s) in import: ${callbackData.tools.join(', ')}`);
									}

								} catch (callbackError) {
									validationLog.push(`❌ Error parsing metadata JSON: ${callbackError instanceof Error ? callbackError.message : 'Unknown error'}`);
								}
							} else {
								validationLog.push('❌ metadata field is missing or not a string.');
							}

							// Validate top-level RAG fields if processor requires them
							if (callbackData?.rag_processor === 'simple_rag') {
								if (parsedData.RAG_Top_k === undefined || typeof parsedData.RAG_Top_k !== 'number') {
									validationLog.push(`⚠️ RAG_Top_k is missing or not a number (Required for simple_rag). Found: ${typeof parsedData.RAG_Top_k}`);
								}
								if (parsedData.RAG_collections === undefined || typeof parsedData.RAG_collections !== 'string') {
									validationLog.push(`⚠️ RAG_collections is missing or not a string (Required for simple_rag). Found: ${typeof parsedData.RAG_collections}`);
								}
							}
						}
					} else if (parsedData !== null) {
						validationLog.push('❌ Imported data is not a valid JSON object.');
					}

					// --- Log Validation Summary ---
					console.log('--- Assistant Import Validation Results ---');
					validationLog.forEach(log => console.log(log));
					console.log('-------------------------------------------');

					const hasErrors = validationLog.some(log => log.startsWith('❌'));

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
							updateAvailableModels(); // Update the list first
							await tick(); // Ensure DOM/state updates before setting LLM
							if (availableModels.includes(callbackData.llm)) {
								selectedLlm = callbackData.llm;
							} else {
								selectedLlm = availableModels.length > 0 ? availableModels[0] : '';
								validationLog.push(`⚠️ Imported LLM '${callbackData.llm}' not available for connector '${selectedConnector}'. Defaulting to '${selectedLlm}'.`);
							}

						// Populate RAG specific fields
						// FIX FOR ISSUE #96: Apply Load-Then-Select pattern for imports too
						if (selectedRagProcessor === 'simple_rag') {
							selectedFilePath = ''; // Clear file path if switching to simple RAG
							// Fetch KBs BEFORE setting selections
							if (!kbFetchAttempted) {
								console.log('Import: Awaiting KB fetch to complete before setting selections');
								await fetchKnowledgeBases(); // ✅ WAIT for KBs to load
							}
							// NOW set selections when KB list is ready
							selectedKnowledgeBases = parsedData.RAG_collections?.split(',').filter(Boolean) || [];
							console.log('Import: KB selections set after fetch:', selectedKnowledgeBases);
						} else if (selectedRagProcessor === 'single_file_rag') {
							selectedKnowledgeBases = []; // Clear KBs if switching to single file RAG
							// Fetch files BEFORE setting selection
							if (!filesFetchAttempted) {
								console.log('Import: Awaiting files fetch to complete before setting selection');
								await fetchUserFiles(); // ✅ WAIT for files to load
							}
							// NOW set selection when file list is ready
							selectedFilePath = callbackData.file_path || '';
							console.log('Import: File selection set after fetch:', selectedFilePath);
						} else { // No RAG
							selectedKnowledgeBases = [];
							selectedFilePath = '';
						}

							// Populate vision and tools from metadata
							visionEnabled = callbackData.capabilities?.vision || false;
							selectedTools = Array.isArray(callbackData.tools) ? callbackData.tools : [];
							console.log('Import: Vision enabled:', visionEnabled, 'Tools:', selectedTools);

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

	/** @param {string} placeholder */
	function insertPlaceholder(placeholder) {
		if (textareaRef) {
			const start = textareaRef.selectionStart;
			const end = textareaRef.selectionEnd;
			const text = prompt_template;
			prompt_template = text.substring(0, start) + placeholder + text.substring(end);
			textareaRef.focus();
			tick().then(() => {
				if (textareaRef) {
					textareaRef.selectionStart = textareaRef.selectionEnd = start + placeholder.length;
				}
			});
		}
	}

</script>

	<div class="p-4 md:p-6 border rounded-md shadow-sm bg-white">
	<!-- Header Section (Title and Top Buttons) -->
	<div class="mb-6 pb-4 border-b border-gray-200">
		<div class="flex justify-between items-center">
			<h2 class="text-2xl font-semibold text-brand">
				{#if formState === 'create'}
					{$_('assistants.form.titleCreate', { default: 'Create New Assistant' })}
				{:else}
					{$_('assistants.form.titleViewEdit', { default: 'Assistant Details' })}
					{#if initialAssistantData?.id} (ID: {initialAssistantData.id}){/if}
				{/if}
			</h2>
			
			<!-- Import Button - Only show in create mode -->
			{#if formState === 'create'}
				<div>
					<button 
						type="button" 
						onclick={triggerFileInput}
						class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
					>
						<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"></path>
						</svg>
						{$_('assistants.form.import.button', { default: 'Import from JSON' })}
					</button>
				</div>
			{/if}
		</div>
		
		<!-- Import Error Message -->
		{#if importError}
			<div class="mt-3 p-3 border border-red-200 bg-red-50 rounded-md">
				<div class="flex">
					<div class="flex-shrink-0">
						<svg class="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
						</svg>
					</div>
					<div class="ml-3">
						<h3 class="text-sm font-medium text-red-800">
							{$_('assistants.form.import.error', { default: 'Import Error' })}
						</h3>
						<p class="mt-1 text-sm text-red-700">{importError}</p>
					</div>
				</div>
			</div>
		{/if}
	</div>

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
					<!-- Name -->
					<div>
						<label for="assistant-name" class="block text-sm font-medium text-gray-700">{$_('assistants.form.name.label')} <span class="text-red-600">*</span></label>
						{#if formState === 'edit'}
							<input type="text" id="assistant-name" name="name" bind:value={name} 
							disabled={true}
							class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-gray-100 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm text-gray-900"
							placeholder={$_('assistants.form.name.placeholder')}>
						{:else}
							<input type="text" id="assistant-name" name="name" bind:value={name} 
							disabled={false}
							class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
							placeholder={$_('assistants.form.name.placeholder')}>
							{#if showSanitizationPreview}
								<div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-md">
									<p class="text-sm text-blue-800">
										<span class="font-semibold">{$_('assistants.form.name.willBeSaved', { default: 'Will be saved as:' })}</span>
										<code class="ml-2 px-2 py-1 bg-blue-100 rounded text-blue-900 font-mono">{sanitizedNameInfo.sanitized}</code>
									</p>
								</div>
							{:else if !name.trim()}
								<p class="mt-1 text-xs text-gray-500">
									{$_('assistants.form.name.hint', { default: 'Special characters and spaces will be converted to underscores' })}
								</p>
							{/if}
						{/if}
					</div>

					<!-- Description -->
					<div>
						<label for="assistant-description" class="block text-sm font-medium text-gray-700">{$_('assistants.form.description.label', { default: 'Description' })}</label>
						<div class="mt-1 flex rounded-md shadow-sm">
						<!-- Description is ALWAYS fully editable -->
						<textarea 
							id="assistant-description" 
							name="description"
							bind:value={description}
							oninput={handleFieldChange}
							rows="3"
							disabled={false}
							class="flex-1 block w-full px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
							placeholder={$_('assistants.form.description.placeholder', { default: 'A brief summary of the assistant' })}></textarea>
							<button type="button" onclick={handleGenerateDescription} disabled={generatingDescription}
								class="relative -ml-px inline-flex items-center space-x-2 rounded-r-md border border-gray-300 bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed">
								<span>{generatingDescription ? $_('assistants.form.description.generating', { default: 'Generating...' }) : $_('assistants.form.description.generateButton', { default: 'Generate' })}</span>
							</button>
						</div>
						<p class="mt-1 text-xs text-gray-500">{$_('assistants.form.description.help', { default: 'Click Generate after filling in name and prompts.' })}</p>
					</div>

				<!-- System Prompt -->
				<div>
					<div class="flex items-center justify-between mb-2">
						<label for="system-prompt" class="block text-sm font-medium text-gray-700">{$_('assistants.form.systemPrompt.label', { default: 'System Prompt' })}</label>
						{#if formState === 'create'}
							<button
								type="button"
								onclick={handleLoadTemplate}
								class="inline-flex items-center px-3 py-1 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
							>
								<svg class="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
								</svg>
								{$_('promptTemplates.loadTemplate', { default: 'Load Template' })}
							</button>
						{/if}
					</div>
				<textarea id="system-prompt" name="system_prompt" bind:value={system_prompt} oninput={handleFieldChange} rows="4"
						  disabled={false}
						  class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
						  placeholder={$_('assistants.form.systemPrompt.placeholder', { default: 'Define the assistant\'s role and personality...' })}></textarea>
				</div>

					<!-- Prompt Template -->
					<div>
						<label for="prompt-template" class="block text-sm font-medium text-gray-700">{$_('assistants.form.promptTemplate.label', { default: 'Prompt Template' })}</label>
						<div class="mt-1 mb-2">
							<span class="text-xs text-gray-600 dark:text-gray-400">{$_('insert_placeholder') || 'Insert placeholder:'}:</span>
							{#each ragPlaceholders as placeholder}
								<button type="button"
									class="ml-1 px-2 py-0.5 text-xs bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-brand"
									onclick={() => insertPlaceholder(placeholder)}
								>
									{placeholder}
								</button>
							{/each}
							{#if selectedPromptProcessor === 'moodle_augment'}
								<button type="button"
									class="ml-1 px-2 py-0.5 text-xs bg-blue-100 hover:bg-blue-200 dark:bg-blue-800 dark:hover:bg-blue-700 text-blue-800 dark:text-blue-100 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
									onclick={() => insertPlaceholder('{moodle_user}')}
									title="Insert Moodle user identifier"
								>
									{'{moodle_user}'}
								</button>
							{/if}
						</div>
				<textarea 
					bind:this={textareaRef}
					bind:value={prompt_template}
					oninput={handleFieldChange}
					id="prompt_template" 
					rows="6"
					class="mt-1 block w-full shadow-sm sm:text-sm border border-gray-300 rounded-md bg-white text-gray-900"
					placeholder={promptPlaceholderText}
					disabled={!isFieldEditable('prompt_template')}
				></textarea>

						<!-- Add preview box with highlighted placeholders -->
						{#if prompt_template}
							<div class="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-sm">
								<div class="text-xs text-gray-500 mb-1">{$_('preview') || 'Preview with highlighted placeholders:'}</div>
								<div class="whitespace-pre-wrap" data-testid="prompt-preview">
									{@html highlightPlaceholders(prompt_template)}
								</div>
							</div>
						{/if}

						{#if selectedPromptProcessor === 'template_validator_processor'}
							<p class="mt-1 text-xs text-gray-500">{$_('assistants.form.promptTemplate.help', { default: 'This processor requires a valid prompt template.' })}</p>
						{/if}
					</div>

					<!-- Rubric Selector (Moved below prompt template) -->
					{#if showRubricSelector}
						<div class="mt-6 pt-6 border-t border-gray-200">
							<h4 class="text-lg font-medium text-gray-900 mb-4">
								{$_('assistants.form.rubric.label', { default: 'Select Rubric' })}
							</h4>

							{#if loadingRubrics}
								<p class="text-sm text-gray-500">{$_('assistants.form.rubric.loading', { default: 'Loading rubrics...' })}</p>
							{:else if rubricError}
								<p class="text-sm text-red-600">{$_('assistants.form.rubric.error', { default: 'Error loading rubrics:' })} {rubricError}</p>
							{:else if accessibleRubrics.length === 0}
								<p class="text-sm text-gray-500">
									{$_('assistants.form.rubric.noneFound', { default: 'No rubrics available.' })}
									<a href="/evaluaitor" class="text-blue-600 hover:underline" target="_blank">
										{$_('assistants.form.rubric.createLink', { default: 'Create a rubric' })} →
									</a>
								</p>
							{:else}
								<!-- Search Bar -->
								<div class="mb-4">
									<label for="rubric-search" class="sr-only">{$_('assistants.form.rubric.search.label', { default: 'Search rubrics' })}</label>
									<input
										type="text"
										id="rubric-search"
										bind:value={rubricSearchQuery}
										placeholder={$_('assistants.form.rubric.search.placeholder', { default: 'Search rubrics by title or description...' })}
										class="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900"
									/>
								</div>

								<!-- Display selected rubric if one is chosen -->
								{#if selectedRubricId}
									{@const selectedRubric = accessibleRubrics.find(r => r.rubric_id === selectedRubricId)}
									{#if selectedRubric}
										<div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
											<div class="flex items-start justify-between">
												<div class="flex-1">
													<div class="flex items-center gap-2">
														<span class="text-sm font-semibold text-blue-900">{$_('assistants.form.rubric.selected', { default: 'Selected:' })}</span>
														<span class="text-sm font-medium text-blue-800">{selectedRubric.title}</span>
														{#if selectedRubric.is_showcase}
															<span class="text-xs">🌟</span>
														{/if}
													</div>
													{#if selectedRubric.description}
														<p class="mt-1 text-xs text-blue-700">{selectedRubric.description}</p>
													{/if}
												</div>
												<a 
													href="/evaluaitor/{selectedRubric.rubric_id}" 
													target="_blank"
													rel="noopener noreferrer"
													class="ml-2 text-sm text-blue-600 hover:text-blue-800 hover:underline whitespace-nowrap"
												>
													{$_('assistants.form.rubric.view', { default: 'View' })} →
												</a>
											</div>
										</div>
									{/if}
								{/if}

								<!-- Rubric List/Table -->
								<div class="border rounded-md overflow-hidden">
									<div class="max-h-96 overflow-y-auto">
										<table class="min-w-full divide-y divide-gray-200">
											<thead class="bg-gray-50 sticky top-0">
												<tr>
													<th scope="col" class="w-12 px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
														{$_('assistants.form.rubric.table.select', { default: 'Select' })}
													</th>
													<th scope="col" class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
														{$_('assistants.form.rubric.table.title', { default: 'Title' })}
													</th>
													<th scope="col" class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
														{$_('assistants.form.rubric.table.description', { default: 'Description' })}
													</th>
													<th scope="col" class="w-24 px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
														{$_('assistants.form.rubric.table.type', { default: 'Type' })}
													</th>
													<th scope="col" class="w-20 px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
														{$_('assistants.form.rubric.table.actions', { default: 'Actions' })}
													</th>
												</tr>
											</thead>
											<tbody class="bg-white divide-y divide-gray-200">
												{#if filteredRubrics().length === 0}
													<tr>
														<td colspan="5" class="px-3 py-4 text-sm text-gray-500 text-center">
															{$_('assistants.form.rubric.noMatches', { default: 'No rubrics match your search.' })}
														</td>
													</tr>
												{:else}
													{#each filteredRubrics() as rubric (rubric.rubric_id)}
														<tr class="hover:bg-gray-50 {selectedRubricId === rubric.rubric_id ? 'bg-blue-50' : ''}">
															<td class="px-3 py-3 whitespace-nowrap text-center">
																<input
																	type="radio"
																	name="rubric-selector"
																	value={rubric.rubric_id}
																	bind:group={selectedRubricId}
																	class="h-4 w-4 text-brand focus:ring-brand"
																/>
															</td>
															<td class="px-3 py-3">
																<div class="flex items-center gap-2">
																	<span class="text-sm font-medium text-gray-900">{rubric.title}</span>
																	{#if rubric.is_showcase}
																		<span class="text-xs" title="Showcase rubric">🌟</span>
																	{/if}
																</div>
															</td>
															<td class="px-3 py-3">
																<p class="text-sm text-gray-600 line-clamp-2">{rubric.description || ''}</p>
															</td>
															<td class="px-3 py-3 whitespace-nowrap">
																{#if rubric.is_mine}
																	<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
																		{$_('assistants.form.rubric.mine', { default: 'Mine' })}
																	</span>
																{:else}
																	<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
																		{$_('assistants.form.rubric.public', { default: 'Public' })}
																	</span>
																{/if}
															</td>
															<td class="px-3 py-3 whitespace-nowrap text-center">
																<a
																	href="/evaluaitor/{rubric.rubric_id}"
																	target="_blank"
																	rel="noopener noreferrer"
																	class="text-sm text-blue-600 hover:text-blue-800 hover:underline"
																>
																	{$_('assistants.form.rubric.view', { default: 'View' })} →
																</a>
															</td>
														</tr>
													{/each}
												{/if}
											</tbody>
										</table>
									</div>
								</div>

								{#if !selectedRubricId}
									<p class="mt-2 text-xs text-red-500">{$_('assistants.form.rubric.required', { default: 'Please select a rubric' })}</p>
								{/if}

								<!-- Format selector -->
								<div class="mt-6 pt-4 border-t border-gray-200">
									<div class="block text-sm font-medium text-gray-700 mb-3">{$_('assistants.form.rubric.format.label', { default: 'Rubric Format for LLM' })}</div>
									<div class="flex gap-6">
										<label class="flex items-center cursor-pointer">
											<input
												type="radio"
												bind:group={rubricFormat}
												value="markdown"
												class="h-4 w-4 text-brand focus:ring-brand mr-2"
											/>
											<span class="text-sm text-gray-900">{$_('assistants.form.rubric.format.markdown', { default: 'Markdown (table format)' })}</span>
										</label>
										<label class="flex items-center cursor-pointer">
											<input
												type="radio"
												bind:group={rubricFormat}
												value="json"
												class="h-4 w-4 text-brand focus:ring-brand mr-2"
											/>
											<span class="text-sm text-gray-900">{$_('assistants.form.rubric.format.json', { default: 'JSON (structured data)' })}</span>
										</label>
									</div>
									<p class="mt-2 text-xs text-gray-500">{$_('assistants.form.rubric.format.help', { default: 'Choose the format that works best with your selected LLM. You can test both to see which produces better results.' })}</p>
								</div>
							{/if}
						</div>
					{/if}
				</div>

				<!-- Right Column: Configuration -->
				<div class="md:w-1/3">
					<!-- Advanced Mode Toggle -->
					{#if formState === 'create'}
						<div class="mb-3">
							<label class="inline-flex items-center cursor-pointer">
								<input 
									type="checkbox" 
									bind:checked={isAdvancedMode} 
									class="sr-only peer"
								/>
								<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
								<span class="ms-3 text-sm font-medium text-gray-900 dark:text-gray-300">
									{$_('assistants.form.advancedMode') || 'Advanced Mode'}
								</span>
							</label>
						</div>
					{/if}

					<!-- Configuration Dropdowns -->
					<fieldset class="border p-4 rounded-md space-y-4 h-full">
						<legend class="text-lg font-medium text-brand px-1">{$_('assistants.form.configSection.title', { default: 'Configuration' })}</legend>

						<!-- Prompt Processor - Only show in advanced mode or edit mode -->
						{#if isAdvancedMode || formState === 'edit'}
							<div>
								<label for="prompt-processor" class="block text-sm font-medium text-gray-700">{$_('assistants.form.promptProcessor.label', { default: 'Prompt Processor' })}</label>
								<select id="prompt-processor" name="prompt_processor" bind:value={selectedPromptProcessor} onchange={handleFieldChange}
										disabled={false}
										class="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900">
									{#each promptProcessors as processor}
										<option value={processor}>{processor}</option>
									{/each}
								</select>
							</div>
						{/if}

						<!-- Connector - Only show in advanced mode or edit mode -->
						{#if isAdvancedMode || formState === 'edit'}
							<div>
								<label for="connector" class="block text-sm font-medium text-gray-700">{$_('assistants.form.connector.label', { default: 'Connector' })}</label>
								<select id="connector" name="connector" bind:value={selectedConnector} onchange={(e) => { handleFieldChange(); handleConnectorChange(e); }}
										disabled={false}
										class="mt-1 block w-full pl-3 pr-10 py-2 text-base border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900">
									{#each connectorsList as connectorName}
										<option value={connectorName}>{connectorName}</option>
									{/each}
								</select>
							</div>
						{/if}

					<!-- LLM (Always visible) -->
					<div>
						<label for="llm" class="block text-sm font-medium text-gray-700">{$_('assistants.form.llm.label', { default: 'Language Model (LLM)' })}</label>
						<select id="llm" name="llm" bind:value={selectedLlm} onchange={handleFieldChange}
									  disabled={availableModels.length === 0}
								  class="mt-1 block w-full pl-3 pr-10 py-2 text-base text-gray-900 border border-gray-300 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm rounded-md bg-white">
							{#if availableModels.length > 0}
								{#each availableModels as model}
									<option value={model}>{model}</option>
								{/each}
							{:else}
								<option value="" disabled>{$_('assistants.form.llm.noneAvailable', { default: 'No models available for selected connector' })}</option>
							{/if}
						</select>
					</div>

					<!-- Vision Capability (Only for OpenAI connector) -->
					{#if selectedConnector === 'openai' || visionEnabled}
					<div class="mb-3">
						<label class="inline-flex items-center cursor-pointer">
							<input
								type="checkbox"
								bind:checked={visionEnabled}
								onchange={handleFieldChange}
								class="sr-only peer"
							/>
							<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
							<div class="ms-3">
								<span class="text-sm font-medium text-gray-900 dark:text-gray-300">
									{$_('assistants.form.vision.label', { default: 'Enable Vision Capability' })}
								</span>
								<p class="text-xs text-gray-500 mt-1">
									{$_('assistants.form.vision.description', { default: 'Allow this assistant to process images alongside text messages' })}
								</p>
							</div>
						</label>
					</div>
					{/if}

					<!-- Image Generation Capability (Only for banana-img connector) -->
					{#if selectedConnector === 'banana-img' || imageGenerationEnabled}
					<div class="mb-3">
						<label class="inline-flex items-center cursor-pointer">
							<input
								type="checkbox"
								bind:checked={imageGenerationEnabled}
								onchange={handleFieldChange}
								class="sr-only peer"
							/>
							<div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 dark:peer-focus:ring-green-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-green-600"></div>
							<div class="ms-3">
								<span class="text-sm font-medium text-gray-900 dark:text-gray-300">
									Enable Image Generation
								</span>
								<p class="text-xs text-gray-500 mt-1">
									Allow this assistant to generate images using Google Gemini
								</p>
							</div>
						</label>
					</div>
					{/if}

					<!-- Tools Section (Only for OpenAI connector in advanced mode or edit mode) -->
					{#if (isAdvancedMode || formState === 'edit') && selectedConnector === 'openai'}
					<div class="pt-4 border-t border-gray-200">
						<h4 class="block text-sm font-medium text-gray-700 mb-2">
							{$_('assistants.form.tools.label', { default: 'Tools (Function Calling)' })}
						</h4>
						<p class="text-xs text-gray-500 mb-3">
							{$_('assistants.form.tools.description', { default: 'Enable tools that the assistant can use during conversations' })}
						</p>
						
						{#if loadingTools}
							<p class="text-sm text-gray-500">{$_('assistants.form.tools.loading', { default: 'Loading tools...' })}</p>
						{:else if toolsError}
							<p class="text-sm text-red-600">{$_('assistants.form.tools.error', { default: 'Error loading tools:' })} {toolsError}</p>
						{:else if availableTools.length === 0}
							<p class="text-sm text-gray-500">{$_('assistants.form.tools.noneFound', { default: 'No tools available.' })}</p>
						{:else}
							<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group" aria-labelledby="tools-group-label">
								<span id="tools-group-label" class="sr-only">{$_('assistants.form.tools.label', { default: 'Tools' })}</span>
								{#each availableTools as tool (tool.name)}
									<label class="flex items-start space-x-2 cursor-pointer p-1 hover:bg-gray-50 rounded">
										<input 
											type="checkbox" 
											bind:group={selectedTools} 
											value={tool.name}
											onchange={handleFieldChange}
											class="mt-0.5 rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50"
										/>
										<div class="flex-1 min-w-0">
											<span class="text-sm font-medium text-gray-700 capitalize">{tool.name}</span>
											<span class="ml-2 text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{tool.category}</span>
											<p class="text-xs text-gray-500 mt-0.5">{tool.description}</p>
										</div>
									</label>
								{/each}
							</div>
							{#if selectedTools.length > 0}
								<p class="mt-2 text-xs text-gray-600">
									{$_('assistants.form.tools.selected', { default: 'Selected:' })} {selectedTools.join(', ')}
								</p>
							{/if}
						{/if}
					</div>
					{/if}

					<!-- RAG Processor -->
					<div>
						<label for="rag-processor" class="block text-sm font-medium text-gray-700">{$_('assistants.form.ragProcessor.label')}</label>
						<select id="rag-processor" bind:value={selectedRagProcessor} onchange={handleFieldChange}
								disabled={formState === 'edit'}
								class="mt-1 block w-full pl-3 pr-10 py-2 text-base text-gray-900 border border-gray-300 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm rounded-md bg-white disabled:bg-gray-100 disabled:cursor-not-allowed">
							{#each ragProcessors as processor}
								<option value={processor}>{processor.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
							{/each}
						</select>
					</div>

						<!-- RAG Options (Conditional) -->
						{#if showRagOptions}
							<div class="pt-4 border-t border-gray-200 space-y-4">
								<h4 class="text-md font-medium text-gray-700">{$_('assistants.form.ragOptions.title', { default: 'RAG Options' })}</h4>
								
								<!-- Rubric RAG Info Message -->
								{#if selectedRagProcessor === 'rubric_rag'}
									<div class="p-3 bg-blue-50 border border-blue-200 rounded-md">
										<p class="text-sm text-blue-800">
											📋 {$_('assistants.form.rubric.configLocation', { default: 'See rubric options below the Prompt Template section' })}
										</p>
									</div>
								{/if}
								
								<!-- RAG Top K (Only for simple_rag) -->
								{#if selectedRagProcessor === 'simple_rag'}
									<div>
										<label for="rag-top-k" class="block text-sm font-medium text-gray-700">{$_('assistants.form.ragTopK.label', { default: 'RAG Top K' })}</label>
										<input type="number" id="rag-top-k" name="RAG_Top_k" bind:value={RAG_Top_k} min="1" max="10" 
											   disabled={false}
											   class="mt-1 block w-24 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand sm:text-sm bg-white text-gray-900 disabled:bg-gray-100 disabled:cursor-not-allowed">
										<p class="mt-1 text-xs text-gray-500">{$_('assistants.form.ragTopK.help', { default: 'Number of relevant documents to retrieve (1-10).' })}</p>
									</div>
								{/if}

								<!-- Knowledge Base Selector (Conditional) -->
								{#if showKnowledgeBaseSelector}
									<div>
										<h4 class="block text-sm font-medium text-gray-700 mb-1">{$_('assistants.form.knowledgeBases.label', { default: 'Knowledge Bases' })}</h4>
										{#if loadingKnowledgeBases}
											<p class="text-sm text-gray-500">{$_('assistants.form.knowledgeBases.loading', { default: 'Loading knowledge bases...' })}</p>
										{:else if knowledgeBaseError}
											<p class="text-sm text-red-600">{$_('assistants.form.knowledgeBases.error', { default: 'Error loading knowledge bases:' })} {knowledgeBaseError}</p>
										{:else if accessibleKnowledgeBases.length === 0}
											<p class="text-sm text-gray-500">{$_('assistants.form.knowledgeBases.noneFound', { default: 'No accessible knowledge bases found.' })}</p>
										{:else}
											<div class="mt-2 space-y-4">
												<!-- Owned Knowledge Bases Section -->
												{#if ownedKnowledgeBases.length > 0}
													<div>
														<h5 class="text-sm font-semibold text-gray-700 mb-2">{$_('assistants.form.knowledgeBases.myKB', { default: 'My Knowledge Bases' })}</h5>
														<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group" aria-labelledby="kb-owned-group-label">
															<span id="kb-owned-group-label" class="sr-only">{$_('assistants.form.knowledgeBases.myKB', { default: 'My Knowledge Bases' })}</span>
															{#each ownedKnowledgeBases as kb (kb.id)}
																<label class="flex items-center space-x-2 cursor-pointer">
																	<input type="checkbox" bind:group={selectedKnowledgeBases} value={kb.id} 
																		   disabled={false}
																		   class="rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50">
																	<span class="text-sm text-gray-700">{kb.name}</span>
																</label>
															{/each}
														</div>
													</div>
												{/if}
												
												<!-- Shared Knowledge Bases Section -->
												{#if sharedKnowledgeBases.length > 0}
													<div>
														<h5 class="text-sm font-semibold text-gray-700 mb-2">{$_('assistants.form.knowledgeBases.sharedKB', { default: 'Shared Knowledge Bases' })}</h5>
														<div class="space-y-2 max-h-48 overflow-y-auto border rounded p-2" role="group" aria-labelledby="kb-shared-group-label">
															<span id="kb-shared-group-label" class="sr-only">{$_('assistants.form.knowledgeBases.sharedKB', { default: 'Shared Knowledge Bases' })}</span>
															{#each sharedKnowledgeBases as kb (kb.id)}
																<label class="flex items-center space-x-2 cursor-pointer">
																	<input type="checkbox" bind:group={selectedKnowledgeBases} value={kb.id} 
																		   disabled={false}
																		   class="rounded border-gray-300 text-brand shadow-sm focus:border-brand focus:ring focus:ring-offset-0 focus:ring-brand focus:ring-opacity-50">
																	<span class="text-sm text-gray-700">
																		{kb.name}
																		<span class="ml-2 text-xs text-gray-500">
																			({$_('assistants.form.knowledgeBases.shared', { values: { owner: kb.shared_by || 'Unknown' }, default: `Shared by ${kb.shared_by || 'Unknown'}` })})
																		</span>
																	</span>
																</label>
															{/each}
														</div>
													</div>
												{/if}
											</div>
										{/if}
									</div>
								{/if}

								<!-- Single File Selector (Conditional) -->
								{#if showSingleFileSelector}
									<div>
										<h4 class="block text-sm font-medium text-gray-700 mb-1">{$_('assistants.form.singleFile.label', { default: 'Select File' })}</h4>
										
										<!-- File upload -->
										<div class="mb-4">
											<label for="file-upload" class="block text-sm text-gray-700">{$_('assistants.form.singleFile.upload', { default: 'Upload New File' })}</label>
											<div class="mt-1 flex items-center">
												<input 
													id="file-upload"
													type="file" 
													accept=".txt,.json,.md,.pdf,.doc,.docx" 
													class="block w-full text-sm text-gray-500
														file:mr-4 file:py-2 file:px-4
														file:rounded-md file:border-0
														file:text-sm file:font-semibold
														file:bg-gray-50 file:text-gray-700
														hover:file:bg-gray-100 disabled:cursor-not-allowed"
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
										<!-- File selection -->
										{#if loadingFiles}
											<p class="text-sm text-gray-500">{$_('assistants.form.singleFile.loading', { default: 'Loading files...' })}</p>
										{:else if fileError}
											<p class="text-sm text-red-600">{$_('assistants.form.singleFile.error', { default: 'Error loading files:' })} {fileError}</p>
										{:else if userFiles.length === 0}
											<p class="text-sm text-gray-500">{$_('assistants.form.singleFile.noneFound', { default: 'No files found. Please upload a file.' })}</p>
										{:else}
											<div class="mt-2 space-y-2 max-h-48 overflow-y-auto border rounded p-2">
												{#each userFiles as file (file.path)}
													<label class="flex items-center space-x-2 p-1 cursor-pointer {selectedFilePath === file.path ? 'bg-blue-50' : 'hover:bg-gray-50'}">
														<input 
															type="radio" 
															name="file-selector" 
															value={file.path} 
															bind:group={selectedFilePath}
															disabled={false}
															class="h-4 w-4 text-brand rounded focus:ring-brand"
														/>
														<span class="text-sm text-gray-700">{file.name}</span>
													</label>
												{/each}
											</div>
											{#if !selectedFilePath && formState === 'edit'}
												<p class="mt-1 text-xs text-red-500">{$_('assistants.form.singleFile.required', { default: 'Please select a file' })}</p>
											{/if}
										{/if}
									</div>
								{/if}


							</div>
						{/if}

					</fieldset>
				</div>
			</div> 
			
			<!-- Messages -->
			{#if formError}
				<p class="text-sm text-red-600 mt-4 p-2 border border-red-200 bg-red-50 rounded">Error: {formError}</p>
			{/if}
			{#if successMessage && formState !== 'edit'}
				<p class="text-sm text-green-600 mt-4 p-2 border border-green-200 bg-green-50 rounded">{successMessage}</p>
			{/if}

			<!-- Bottom Action Button Area -->
			<div class="pt-5">
				<div class="flex justify-end space-x-3">
					{#if formState === 'edit'}
						<!-- Bottom Cancel Button (Edit Mode) -->
						<button 
							type="button" 
							onclick={switchToViewMode}
							disabled={formLoading}
							class="py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{$_('common.cancel', { default: 'Cancel' })}
						</button>
					{/if}
					
					<!-- Sanitization Preview (above save button) -->
					{#if showSanitizationPreview}
						<div class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
							<div class="flex items-center">
								<svg class="w-5 h-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
								</svg>
								<div class="flex-1">
									<p class="text-sm font-semibold text-blue-800">
										{$_('assistants.form.name.willBeSaved', { default: 'Will be saved as:' })}
									</p>
									<code class="inline-block mt-1 px-3 py-1 bg-blue-100 rounded text-blue-900 font-mono text-sm">{sanitizedNameInfo.sanitized}</code>
								</div>
							</div>
						</div>
					{/if}
					
					<!-- Bottom Save / Save Changes Button -->
					<button 
						type="submit" 
						form="assistant-form-main" 
						disabled={formLoading || (formState === 'create' && !$assistantConfigStore.systemCapabilities)} 
						class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
					>
						{#if formState === 'create'}
							{formLoading ? $_('common.saving', { default: 'Saving...' }) : $_('common.save', { default: 'Save' })}
						{:else} <!-- formState === 'edit' -->
							{formLoading ? $_('common.saving', { default: 'Saving...' }) : $_('common.saveChanges', { default: 'Save Changes' })}
						{/if}
					</button>
				</div>
			</div>

		</form>
	{/if} 

	<!-- Hidden file input for import functionality -->
	<input 
		type="file" 
		id="import-assistant-json" 
		accept=".json" 
		onchange={handleFileSelect}
		style="display: none;"
	/>

	<!-- Template Selection Modal -->
	<TemplateSelectModal onSelect={handleTemplateSelected} />

</div> 