import { describe, it, expect, vi } from 'vitest';

vi.mock('$lib/utils/ragProcessorHelpers.js', () => ({
	isKbBasedRag: (p) => ['simple_rag', 'context_aware_rag', 'hierarchical_rag'].includes(p),
	isSingleFileRag: (p) => p === 'single_file_rag',
	isRubricRag: (p) => p === 'rubric_rag',
	normalizeRagProcessor: (p) => p
}));

vi.mock('$lib/stores/assistantConfigStore', () => ({
	assistantConfigStore: {
		subscribe: vi.fn(),
		configDefaults: { config: {} }
	}
}));

vi.mock('$lib/utils/assistantData', () => ({
	getAssistantMetadataObject: (data) => {
		if (!data.metadata) return {};
		return typeof data.metadata === 'string' ? JSON.parse(data.metadata) : data.metadata;
	}
}));

vi.mock('./logic/assistantFormUtils.svelte.js', () => ({
	loadRagPlaceholders: () => [],
	selectModel: (model) => model
}));

vi.mock('svelte/store', () => ({
	get: (store) => store.configDefaults || { config: {} }
}));

import { populateFormFields, resetFormFieldsToDefaults } from './logic/assistantFormState.svelte.js';

function makeForm(overrides = {}) {
	return {
		formState: 'create',
		initialAssistantData: null,
		name: '',
		description: '',
		system_prompt: '',
		prompt_template: '',
		RAG_Top_k: 3,
		isAdvancedMode: false,
		promptProcessors: ['simple_augment'],
		connectorsList: ['openai'],
		ragProcessors: ['no_rag', 'simple_rag', 'context_aware_rag', 'single_file_rag'],
		selectedPromptProcessor: 'simple_augment',
		selectedConnector: 'openai',
		selectedLlm: 'gpt-4o-mini',
		selectedRagProcessor: 'no_rag',
		documentRagEnabled: false,
		visionEnabled: false,
		imageGenerationEnabled: false,
		ownedKnowledgeBases: [],
		sharedKnowledgeBases: [],
		selectedKnowledgeBases: [],
		loadingKnowledgeBases: false,
		knowledgeBaseError: '',
		kbFetchAttempted: false,
		pendingKBSelections: null,
		userFiles: [],
		selectedFilePath: '',
		loadingFiles: false,
		fileError: '',
		filesFetchAttempted: false,
		libraries: [],
		selectedLibraryId: '',
		loadingLibraries: false,
		libraryError: '',
		librariesFetchAttempted: false,
		libraryItems: [],
		selectedItemId: '',
		loadingItems: false,
		itemsError: '',
		itemsFetchAttempted: false,
		accessibleRubrics: [],
		selectedRubricId: '',
		rubricFormat: 'markdown',
		loadingRubrics: false,
		rubricError: '',
		rubricsFetchAttempted: false,
		formError: '',
		formLoading: false,
		configInitialized: true,
		successMessage: '',
		importError: '',
		formDirty: false,
		previousAssistantId: null,
		ragPlaceholders: [],
		get accessibleKnowledgeBases() {
			return [...this.ownedKnowledgeBases, ...this.sharedKnowledgeBases];
		},
		...overrides
	};
}

describe('documentRagEnabled in form state', () => {
	it('populateFormFields sets documentRagEnabled from metadata', () => {
		const form = makeForm({ formState: 'edit' });
		const data = {
			name: 'Test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			RAG_Top_k: 3,
			metadata: JSON.stringify({
				prompt_processor: 'simple_augment',
				connector: 'openai',
				llm: 'gpt-4o-mini',
				rag_processor: 'no_rag',
				document_rag: 'library_file_rag',
				library_id: 'lib-1',
				item_id: 'item-1'
			})
		};

		populateFormFields(form, data, () => ['gpt-4o-mini']);

		expect(form.documentRagEnabled).toBe(true);
		expect(form.selectedLibraryId).toBe('lib-1');
		expect(form.selectedItemId).toBe('item-1');
	});

	it('populateFormFields reads file_path for legacy antiguo', () => {
		const form = makeForm({ formState: 'edit' });
		const data = {
			name: 'Legacy Old',
			description: '',
			system_prompt: '',
			prompt_template: '',
			RAG_Top_k: 3,
			metadata: JSON.stringify({
				prompt_processor: 'simple_augment',
				connector: 'openai',
				llm: 'gpt-4o-mini',
				rag_processor: 'single_file_rag',
				file_path: 'docs/mi_documento.md'
			})
		};

		populateFormFields(form, data, () => ['gpt-4o-mini']);

		expect(form.documentRagEnabled).toBe(false);
		expect(form.selectedRagProcessor).toBe('single_file_rag');
		expect(form.selectedFilePath).toBe('docs/mi_documento.md');
		expect(form.selectedLibraryId).toBe('');
		expect(form.selectedItemId).toBe('');
	});

	it('resetFormFieldsToDefaults clears documentRagEnabled', () => {
		const form = makeForm({ documentRagEnabled: true, selectedLibraryId: 'lib-1' });
		resetFormFieldsToDefaults(form, () => ['gpt-4o-mini']);
		expect(form.documentRagEnabled).toBe(false);
	});
});
