// src/lib/components/assistants/assistantFormState.svelte.test.js
import { describe, test, expect, vi } from 'vitest';

// Mock stores and services
vi.mock('$lib/stores/assistantConfigStore', async () => {
	const { writable } = await import('svelte/store');
	const store = writable({
		configDefaults: {
			config: {
				system_prompt: 'Default system prompt',
				prompt_template: 'Default template',
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag',
				RAG_Top_k: '3',
				rag_placeholders: ['{context}', '{user_input}']
			}
		}
	});
	return {
		assistantConfigStore: {
			subscribe: store.subscribe,
			loadConfig: vi.fn()
		}
	};
});

vi.mock('$lib/utils/ragProcessorHelpers.js', () => ({
	isKbBasedRag: (p) => ['simple_rag', 'context_aware_rag', 'hierarchical_rag'].includes(p),
	isSingleFileRag: (p) => p === 'single_file_rag',
	isRubricRag: (p) => p === 'rubric_rag',
	normalizeRagProcessor: (p) => p || 'no_rag'
}));

vi.mock('$lib/utils/assistantData', () => ({
	getAssistantMetadataObject: (data) => {
		if (typeof data.metadata === 'string') {
			try {
				return JSON.parse(data.metadata);
			} catch {
				return {};
			}
		}
		return data.metadata || {};
	}
}));

import {
	createAssistantFormState,
	handleFieldChange,
	resetFormFieldsToDefaults,
	populateFormFields,
	revertToInitial,
	clearRagDependentState
} from './logic/assistantFormState.svelte.js';

const getAvailableModels = () => ['gpt-4', 'gpt-3.5-turbo'];

describe('createAssistantFormState', () => {
	test('returns an object with all expected properties', () => {
		const form = createAssistantFormState();

		expect(form.formState).toBe('create');
		expect(form.initialAssistantData).toBe(null);
		expect(form.name).toBe('');
		expect(form.description).toBe('');
		expect(form.system_prompt).toBe('');
		expect(form.prompt_template).toBe('');
		expect(form.RAG_Top_k).toBe(3);
		expect(form.isAdvancedMode).toBe(false);
		expect(form.promptProcessors).toEqual([]);
		expect(form.connectorsList).toEqual([]);
		expect(form.ragProcessors).toEqual([]);
		expect(form.selectedPromptProcessor).toBe('');
		expect(form.selectedConnector).toBe('');
		expect(form.selectedLlm).toBe('');
		expect(form.selectedRagProcessor).toBe('');
		expect(form.visionEnabled).toBe(false);
		expect(form.imageGenerationEnabled).toBe(false);
		expect(form.ownedKnowledgeBases).toEqual([]);
		expect(form.sharedKnowledgeBases).toEqual([]);
		expect(form.selectedKnowledgeBases).toEqual([]);
		expect(form.loadingKnowledgeBases).toBe(false);
		expect(form.knowledgeBaseError).toBe('');
		expect(form.kbFetchAttempted).toBe(false);
		expect(form.pendingKBSelections).toBe(null);
		expect(form.userFiles).toEqual([]);
		expect(form.selectedFilePath).toBe('');
		expect(form.loadingFiles).toBe(false);
		expect(form.fileError).toBe('');
		expect(form.filesFetchAttempted).toBe(false);
		expect(form.accessibleRubrics).toEqual([]);
		expect(form.selectedRubricId).toBe('');
		expect(form.rubricFormat).toBe('markdown');
		expect(form.loadingRubrics).toBe(false);
		expect(form.rubricError).toBe('');
		expect(form.rubricsFetchAttempted).toBe(false);
		expect(form.formError).toBe('');
		expect(form.formLoading).toBe(false);
		expect(form.configInitialized).toBe(false);
		expect(form.successMessage).toBe('');
		expect(form.importError).toBe('');
		expect(form.formDirty).toBe(false);
		expect(form.previousAssistantId).toBe(null);
		expect(form.ragPlaceholders).toEqual([]);
	});

	test('each call returns an independent instance', () => {
		const form1 = createAssistantFormState();
		const form2 = createAssistantFormState();

		form1.name = 'form1';
		form2.name = 'form2';

		expect(form1.name).toBe('form1');
		expect(form2.name).toBe('form2');
	});

	test('accessibleKnowledgeBases combines owned + shared', () => {
		const form = createAssistantFormState();
		form.ownedKnowledgeBases = [{ id: '1', name: 'A' }];
		form.sharedKnowledgeBases = [{ id: '2', name: 'B' }];

		expect(form.accessibleKnowledgeBases).toEqual([
			{ id: '1', name: 'A' },
			{ id: '2', name: 'B' }
		]);
	});
});

describe('handleFieldChange', () => {
	test('sets formDirty to true', () => {
		const form = createAssistantFormState();
		expect(form.formDirty).toBe(false);

		handleFieldChange(form);

		expect(form.formDirty).toBe(true);
	});
});

describe('resetFormFieldsToDefaults', () => {
	test('resets form fields to config defaults', () => {
		const form = createAssistantFormState();
		form.promptProcessors = ['default_processor', 'other'];
		form.connectorsList = ['openai', 'ollama'];
		form.ragProcessors = ['no_rag', 'simple_rag'];
		form.name = 'existing'; // should NOT be reset
		form.description = 'existing'; // should NOT be reset

		resetFormFieldsToDefaults(form, getAvailableModels);

		expect(form.system_prompt).toBe('Default system prompt');
		expect(form.prompt_template).toBe('Default template');
		expect(form.RAG_Top_k).toBe(3);
		expect(form.selectedPromptProcessor).toBe('default_processor');
		expect(form.selectedConnector).toBe('openai');
		expect(form.selectedRagProcessor).toBe('no_rag');
		expect(form.selectedLlm).toBe('gpt-4');
		expect(form.selectedKnowledgeBases).toEqual([]);
		expect(form.selectedFilePath).toBe('');
		expect(form.visionEnabled).toBe(false);
		expect(form.imageGenerationEnabled).toBe(false);
		// name and description are not reset by this function
		expect(form.name).toBe('existing');
		expect(form.description).toBe('existing');
	});
});

describe('populateFormFields', () => {
	test('populates basic fields from assistant data', () => {
		const form = createAssistantFormState();
		form.configInitialized = true;
		form.promptProcessors = ['default_processor'];
		form.connectorsList = ['openai'];
		form.ragProcessors = ['simple_rag', 'no_rag'];

		const assistantData = {
			name: '1_test_assistant',
			description: 'Test description',
			system_prompt: 'You are helpful.',
			prompt_template: 'Template',
			RAG_Top_k: 5,
			metadata: JSON.stringify({
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag',
				capabilities: { vision: false, image_generation: false }
			})
		};

		populateFormFields(form, assistantData, getAvailableModels);

		expect(form.name).toBe('test_assistant'); // prefix stripped
		expect(form.description).toBe('Test description');
		expect(form.system_prompt).toBe('You are helpful.');
		expect(form.prompt_template).toBe('Template');
		expect(form.RAG_Top_k).toBe(5);
		expect(form.selectedPromptProcessor).toBe('default_processor');
		expect(form.selectedConnector).toBe('openai');
		expect(form.selectedRagProcessor).toBe('no_rag');
		expect(form.selectedLlm).toBe('gpt-4');
	});

	test('preserves description when preserveDescription is true', () => {
		const form = createAssistantFormState();
		form.configInitialized = true;
		form.promptProcessors = ['default_processor'];
		form.connectorsList = ['openai'];
		form.ragProcessors = ['no_rag'];
		form.description = 'User edited';

		const assistantData = {
			name: 'test',
			description: 'Original description',
			system_prompt: 'sys',
			prompt_template: 'tmpl',
			metadata: JSON.stringify({
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag',
				capabilities: { vision: false, image_generation: false }
			})
		};

		populateFormFields(form, assistantData, getAvailableModels, true);

		expect(form.description).toBe('User edited');
	});

	test('does nothing when data is null', () => {
		const form = createAssistantFormState();
		form.name = 'existing';

		populateFormFields(form, null, getAvailableModels);

		expect(form.name).toBe('existing');
	});

	test('sets pendingKBSelections for kb-based RAG', () => {
		const form = createAssistantFormState();
		form.configInitialized = true;
		form.promptProcessors = ['default_processor'];
		form.connectorsList = ['openai'];
		form.ragProcessors = ['simple_rag', 'no_rag'];

		const assistantData = {
			name: 'test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			RAG_Top_k: 3,
			RAG_collections: 'kb1,kb2',
			metadata: JSON.stringify({
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'simple_rag',
				capabilities: { vision: false, image_generation: false }
			})
		};

		populateFormFields(form, assistantData, getAvailableModels);

		expect(form.pendingKBSelections).toEqual(['kb1', 'kb2']);
	});

	test('clears pendingKBSelections for non-kb RAG', () => {
		const form = createAssistantFormState();
		form.configInitialized = true;
		form.promptProcessors = ['default_processor'];
		form.connectorsList = ['openai'];
		form.ragProcessors = ['no_rag'];
		form.pendingKBSelections = ['old-kb'];

		const assistantData = {
			name: 'test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			metadata: JSON.stringify({
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag',
				capabilities: { vision: false, image_generation: false }
			})
		};

		populateFormFields(form, assistantData, getAvailableModels);

		expect(form.pendingKBSelections).toBe(null);
	});
});

describe('revertToInitial', () => {
	test('reverts to initialAssistantData and resets dirty/error/success', () => {
		const form = createAssistantFormState();
		form.configInitialized = true;
		form.promptProcessors = ['default_processor'];
		form.connectorsList = ['openai'];
		form.ragProcessors = ['no_rag'];
		form.formDirty = true;
		form.formError = 'Some error';
		form.successMessage = 'Some success';

		form.initialAssistantData = {
			name: '1_original',
			description: 'Original desc',
			system_prompt: 'Original sys',
			prompt_template: 'Original tmpl',
			RAG_Top_k: 5,
			metadata: JSON.stringify({
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag',
				capabilities: { vision: false, image_generation: false }
			})
		};

		// Mutate form to simulate user edits
		form.name = 'edited_name';
		form.description = 'edited desc';

		revertToInitial(form, getAvailableModels);

		expect(form.name).toBe('original'); // prefix stripped
		expect(form.description).toBe('Original desc');
		expect(form.formDirty).toBe(false);
		expect(form.formError).toBe('');
		expect(form.successMessage).toBe('');
	});

	test('does nothing when initialAssistantData is null', () => {
		const form = createAssistantFormState();
		form.name = 'existing';

		revertToInitial(form, getAvailableModels);

		expect(form.name).toBe('existing');
	});
});

describe('clearRagDependentState', () => {
	test('clears KB state when called (caller ensures not on kb-based RAG)', () => {
		const form = createAssistantFormState();
		// Note: clearRagDependentState is called by the $effect only when
		// switching AWAY from all RAG types. It doesn't check the RAG type itself.
		form.ownedKnowledgeBases = [{ id: '1' }];
		form.sharedKnowledgeBases = [{ id: '2' }];
		form.selectedKnowledgeBases = ['1'];
		form.knowledgeBaseError = 'error';
		form.kbFetchAttempted = true;

		clearRagDependentState(form);

		expect(form.ownedKnowledgeBases).toEqual([]);
		expect(form.sharedKnowledgeBases).toEqual([]);
		expect(form.selectedKnowledgeBases).toEqual([]);
		expect(form.knowledgeBaseError).toBe('');
		expect(form.kbFetchAttempted).toBe(false);
	});

	test('clears file selection when called (caller ensures not on single_file_rag)', () => {
		const form = createAssistantFormState();
		form.selectedFilePath = '/path/to/file.pdf';
		form.userFiles = [{ name: 'file.pdf', path: '/path/to/file.pdf' }];

		clearRagDependentState(form);

		expect(form.selectedFilePath).toBe('');
		// userFiles are NOT cleared (to avoid refetching)
		expect(form.userFiles.length).toBe(1);
	});

	test('clears rubric selection when called (caller ensures not on rubric_rag)', () => {
		const form = createAssistantFormState();
		form.selectedRubricId = 'r1';
		form.accessibleRubrics = [{ rubric_id: 'r1', title: 'R1' }];

		clearRagDependentState(form);

		expect(form.selectedRubricId).toBe('');
		expect(form.rubricFormat).toBe('markdown');
		// accessibleRubrics are NOT cleared (to avoid refetching)
		expect(form.accessibleRubrics.length).toBe(1);
	});
});
