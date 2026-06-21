// src/lib/components/assistants/assistantFormState.svelte.js
/**
 * Reactive state hook for AssistantForm.
 *
 * Encapsulates all $state variables and form manipulation methods
 * (reset, populate, revert, field change tracking) in a single composable unit.
 *
 * Usage:
 *   const form = createAssistantFormState();
 *   form.name;          // reactive read
 *   form.name = 'x';    // reactive write
 *   bind:value={form.name}  // works with Svelte 5 bindings
 *
 * Methods are pure functions that receive `form` as the first parameter.
 */

import { get } from 'svelte/store';
import { assistantConfigStore } from '$lib/stores/assistantConfigStore';
import {
	isKbBasedRag,
	isSingleFileRag,
	isRubricRag,
	normalizeRagProcessor
} from '$lib/utils/ragProcessorHelpers.js';
import { loadRagPlaceholders, selectModel } from './assistantFormUtils.svelte.js';
import { getAssistantMetadataObject } from '$lib/utils/assistantData';

/**
 * Creates a reactive form state instance.
 * Each call returns a fresh isolated state object.
 */
export function createAssistantFormState() {
	let form = $state({
		// --- Form mode & initial data ---
		formState: /** @type {'edit' | 'create'} */ ('create'),
		/** @type {any | null} */
		initialAssistantData: null,

		// --- Form field state ---
		name: '',
		description: '',
		system_prompt: '',
		prompt_template: '',
		RAG_Top_k: 3,
		isAdvancedMode: false,

		// --- Dynamic options (populated from config) ---
		promptProcessors: [],
		connectorsList: [],
		ragProcessors: [],

		// --- Selected values ---
		selectedPromptProcessor: '',
		selectedConnector: '',
		selectedLlm: '',
		selectedRagProcessor: '',

		// --- Capabilities ---
		visionEnabled: false,
		imageGenerationEnabled: false,

		// --- Knowledge Base state ---
		/** @type {any[]} */
		ownedKnowledgeBases: [],
		/** @type {any[]} */
		sharedKnowledgeBases: [],
		/** @type {string[]} */
		selectedKnowledgeBases: [],
		loadingKnowledgeBases: false,
		knowledgeBaseError: '',
		kbFetchAttempted: false,
		/** @type {string[] | null} */
		pendingKBSelections: null,

		// --- File state ---
		/** @type {Array<{name: string, path: string}>} */
		userFiles: [],
		selectedFilePath: '',
		loadingFiles: false,
		fileError: '',
		filesFetchAttempted: false,

		// --- Rubric state ---
		/** @type {Array<{rubric_id: string, title: string, description: string, is_mine: boolean, is_showcase: boolean, is_public: boolean}>} */
		accessibleRubrics: [],
		selectedRubricId: '',
		rubricFormat: 'markdown',
		loadingRubrics: false,
		rubricError: '',
		rubricsFetchAttempted: false,

		// --- UI / loading state ---
		formError: '',
		formLoading: false,
		configInitialized: false,
		successMessage: '',
		importError: '',
		formDirty: false,
		previousAssistantId: null,

		ragPlaceholders: [],

		// --- Derived ---
		get accessibleKnowledgeBases() {
			return [...this.ownedKnowledgeBases, ...this.sharedKnowledgeBases];
		}
	});

	return form;
}

/**
 * Mark form as dirty when user makes changes.
 * @param {ReturnType<typeof createAssistantFormState>} form
 */
export function handleFieldChange(form) {
	form.formDirty = true;
}

/**
 * Reset form fields to defaults (create mode).
 * @param {ReturnType<typeof createAssistantFormState>} form
 * @param {() => string[]} getAvailableModels - getter function (evaluated after connector is set)
 */
export function resetFormFieldsToDefaults(form, getAvailableModels) {
	const defaults = get(assistantConfigStore).configDefaults?.config || {};
	form.system_prompt = defaults.system_prompt || '';
	form.prompt_template = defaults.prompt_template || '';
	form.RAG_Top_k = parseInt(defaults.RAG_Top_k || '3', 10) || 3;
	form.selectedPromptProcessor =
		defaults.prompt_processor || (form.promptProcessors.length > 0 ? form.promptProcessors[0] : '');
	form.selectedConnector =
		defaults.connector || (form.connectorsList.length > 0 ? form.connectorsList[0] : '');
	let defaultRag = normalizeRagProcessor(defaults.rag_processor);
	form.selectedRagProcessor =
		defaultRag || (form.ragProcessors.length > 0 ? form.ragProcessors[0] : '');

	form.ragPlaceholders = loadRagPlaceholders(defaults);
	form.selectedLlm = selectModel(defaults.llm || '', getAvailableModels());

	form.selectedKnowledgeBases = [];
	form.selectedFilePath = '';
	form.visionEnabled = false;
	form.imageGenerationEnabled = false;
}

/**
 * Populate form fields from assistant data.
 * @param {ReturnType<typeof createAssistantFormState>} form
 * @param {any} data
 * @param {() => string[]} getAvailableModels - getter function (evaluated after connector is set)
 * @param {boolean} [preserveDescription]
 */
export function populateFormFields(form, data, getAvailableModels, preserveDescription = false) {
	if (!data) return;

	const metadata = getAssistantMetadataObject(data);

	form.name = data.name?.replace(/^\d+_/, '') || '';
	if (!preserveDescription) {
		form.description = data.description || '';
	}
	form.system_prompt = data.system_prompt || '';
	form.prompt_template = data.prompt_template || '';
	form.RAG_Top_k = data.RAG_Top_k ?? 3;

	if (form.configInitialized) {
		form.selectedPromptProcessor =
			data.prompt_processor ||
			metadata.prompt_processor ||
			(form.promptProcessors.length > 0 ? form.promptProcessors[0] : '');
		form.selectedConnector =
			data.connector ||
			metadata.connector ||
			(form.connectorsList.length > 0 ? form.connectorsList[0] : '');
		form.selectedRagProcessor =
			data.rag_processor ||
			metadata.rag_processor ||
			(form.ragProcessors.length > 0 ? form.ragProcessors[0] : '');

		const targetLlm = data.llm || metadata.llm;
		// Evaluate availableModels AFTER selectedConnector is set
		form.selectedLlm = selectModel(targetLlm, getAvailableModels());

		const defaults = get(assistantConfigStore).configDefaults?.config || {};
		form.ragPlaceholders = loadRagPlaceholders(defaults);

		// Deferred selection for KBs
		if (isKbBasedRag(form.selectedRagProcessor)) {
			form.pendingKBSelections = data.RAG_collections?.split(',').filter(Boolean) || [];
		} else {
			form.pendingKBSelections = null;
		}

		// Rubric fields
		if (isRubricRag(form.selectedRagProcessor)) {
			try {
				form.selectedRubricId = metadata?.rubric_id || '';
				form.rubricFormat = metadata?.rubric_format || 'markdown';
			} catch (e) {
				console.warn('Failed to parse rubric metadata:', e);
				form.selectedRubricId = '';
				form.rubricFormat = 'markdown';
			}
		}

		// Vision capability
		try {
			form.visionEnabled = metadata?.capabilities?.vision || false;
			form.imageGenerationEnabled = metadata?.capabilities?.image_generation || false;
		} catch (e) {
			console.warn('Failed to parse vision capability from metadata:', e);
			form.visionEnabled = false;
		}
	} else {
		console.warn('[populateFormFields] Config not initialized yet, skipping dropdown population');
	}
}

/**
 * Revert form fields to initial assistant data (cancel edits).
 * @param {ReturnType<typeof createAssistantFormState>} form
 * @param {() => string[]} getAvailableModels
 */
export function revertToInitial(form, getAvailableModels) {
	if (form.initialAssistantData) {
		populateFormFields(form, form.initialAssistantData, getAvailableModels, false);
	}
	form.formDirty = false;
	form.formError = '';
	form.successMessage = '';
}

/**
 * Clear RAG-dependent state when switching away from a RAG processor type.
 * @param {ReturnType<typeof createAssistantFormState>} form
 */
export function clearRagDependentState(form) {
	if (
		form.accessibleKnowledgeBases.length > 0 ||
		form.selectedKnowledgeBases.length > 0 ||
		form.knowledgeBaseError ||
		form.kbFetchAttempted
	) {
		form.ownedKnowledgeBases = [];
		form.sharedKnowledgeBases = [];
		form.selectedKnowledgeBases = [];
		form.knowledgeBaseError = '';
		form.kbFetchAttempted = false;
	}

	if (
		!isSingleFileRag(form.selectedRagProcessor) &&
		(form.selectedFilePath || form.userFiles.length > 0)
	) {
		form.selectedFilePath = '';
	}

	if (
		!isRubricRag(form.selectedRagProcessor) &&
		(form.selectedRubricId || form.accessibleRubrics.length > 0)
	) {
		form.selectedRubricId = '';
		form.rubricFormat = 'markdown';
	}
}
