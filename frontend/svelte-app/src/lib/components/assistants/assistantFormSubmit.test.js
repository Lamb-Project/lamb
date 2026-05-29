import { describe, test, it, expect, vi } from 'vitest';

vi.mock('$lib/utils/ragProcessorHelpers.js', () => ({
	isKbBasedRag: (p) => ['simple_rag', 'context_aware_rag', 'hierarchical_rag'].includes(p),
	isSingleFileRag: (p) => p === 'single_file_rag',
	isRubricRag: (p) => p === 'rubric_rag'
}));

import { validateSubmission, buildAssistantPayload } from './logic/assistantFormSubmit.js';

describe('validateSubmission', () => {
	test('returns error when name is empty', () => {
		const result = validateSubmission({ name: '', selectedRagProcessor: 'no_rag', selectedRubricId: '' });
		expect(result).toContain('Name');
	});

	test('returns error when rubric_rag selected without rubric', () => {
		const result = validateSubmission({ name: 'test', selectedRagProcessor: 'rubric_rag', selectedRubricId: '' });
		expect(result).toContain('rubric');
	});

	test('returns null when valid', () => {
		const result = validateSubmission({ name: 'test', selectedRagProcessor: 'no_rag', selectedRubricId: '' });
		expect(result).toBeNull();
	});
});

describe('buildAssistantPayload', () => {
	test('builds payload with metadata', () => {
		const form = {
			name: ' test ',
			description: 'desc',
			system_prompt: 'sys',
			prompt_template: 'tmpl',
			RAG_Top_k: 3,
			selectedPromptProcessor: 'default_processor',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4',
			selectedRagProcessor: 'no_rag',
			selectedLibraryId: '',
			selectedItemId: '',
			visionEnabled: false,
			imageGenerationEnabled: false,
			selectedKnowledgeBases: [],
			selectedRubricId: '',
			rubricFormat: 'markdown'
		};
		const payload = buildAssistantPayload(form);
		expect(payload.name).toBe('test');
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.connector).toBe('openai');
		expect(metadata.library_id).toBeUndefined();
		expect(metadata.item_id).toBeUndefined();
	});

	test('includes rubric fields when rubric_rag is selected', () => {
		const form = {
			name: 'test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			RAG_Top_k: 3,
			selectedPromptProcessor: 'default',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4',
			selectedRagProcessor: 'rubric_rag',
			selectedLibraryId: '',
			selectedItemId: '',
			visionEnabled: false,
			imageGenerationEnabled: false,
			selectedKnowledgeBases: [],
			selectedRubricId: 'rubric-123',
			rubricFormat: 'json'
		};
		const payload = buildAssistantPayload(form);
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.rubric_id).toBe('rubric-123');
		expect(metadata.rubric_format).toBe('json');
	});

	test('includes KB collections when kb-based RAG is selected', () => {
		const form = {
			name: 'test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			RAG_Top_k: 5,
			selectedPromptProcessor: 'default',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4',
			selectedRagProcessor: 'simple_rag',
			selectedLibraryId: '',
			selectedItemId: '',
			visionEnabled: true,
			imageGenerationEnabled: false,
			selectedKnowledgeBases: ['kb1', 'kb2'],
			selectedRubricId: '',
			rubricFormat: 'markdown'
		};
		const payload = buildAssistantPayload(form);
		expect(payload.RAG_collections).toBe('kb1,kb2');
		expect(payload.RAG_Top_k).toBe(5);
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.capabilities.vision).toBe(true);
	});

	test('legacy single_file_rag without documentRagEnabled does not include library refs', () => {
		const form = {
			name: 'test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			RAG_Top_k: 3,
			selectedPromptProcessor: 'simple_augment',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4o-mini',
			selectedRagProcessor: 'single_file_rag',
			selectedLibraryId: 'lib-123',
			selectedItemId: 'item-456',
			selectedFilePath: '',
			documentRagEnabled: false,
			visionEnabled: false,
			imageGenerationEnabled: false,
			selectedKnowledgeBases: [],
			selectedRubricId: '',
			rubricFormat: 'markdown'
		};
		const payload = buildAssistantPayload(form);
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.library_id).toBeUndefined();
		expect(metadata.item_id).toBeUndefined();
		expect(metadata.file_path).toBeUndefined();
		expect(metadata.document_rag).toBeUndefined();
	});
});

describe('buildAssistantPayload with document_rag', () => {
	it('includes document_rag and library refs when documentRagEnabled', () => {
		const form = {
			name: 'Test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			selectedPromptProcessor: 'simple_augment',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4o-mini',
			selectedRagProcessor: 'no_rag',
			documentRagEnabled: true,
			selectedLibraryId: 'lib-1',
			selectedItemId: 'item-1',
			selectedFilePath: '',
			visionEnabled: false,
			imageGenerationEnabled: false,
			RAG_Top_k: 3,
			selectedKnowledgeBases: []
		};
		const payload = buildAssistantPayload(form);
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.document_rag).toBe('single_file_rag');
		expect(metadata.library_id).toBe('lib-1');
		expect(metadata.item_id).toBe('item-1');
		expect(metadata.rag_processor).toBe('no_rag');
	});

	it('omits document_rag when documentRagEnabled is false', () => {
		const form = {
			name: 'Test',
			description: '',
			system_prompt: '',
			prompt_template: '',
			selectedPromptProcessor: 'simple_augment',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4o-mini',
			selectedRagProcessor: 'context_aware_rag',
			documentRagEnabled: false,
			selectedLibraryId: '',
			selectedItemId: '',
			selectedFilePath: '',
			visionEnabled: false,
			imageGenerationEnabled: false,
			RAG_Top_k: 3,
			selectedKnowledgeBases: ['kb-1']
		};
		const payload = buildAssistantPayload(form);
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.document_rag).toBeUndefined();
		expect(metadata.library_id).toBeUndefined();
	});

	it('legacy single_file_rag with file_path preserves file_path', () => {
		const form = {
			name: 'Legacy Old',
			description: '',
			system_prompt: '',
			prompt_template: '',
			selectedPromptProcessor: 'simple_augment',
			selectedConnector: 'openai',
			selectedLlm: 'gpt-4o-mini',
			selectedRagProcessor: 'single_file_rag',
			documentRagEnabled: false,
			selectedLibraryId: '',
			selectedItemId: '',
			selectedFilePath: 'docs/mi_documento.md',
			visionEnabled: false,
			imageGenerationEnabled: false,
			RAG_Top_k: 3,
			selectedKnowledgeBases: []
		};
		const payload = buildAssistantPayload(form);
		const metadata = JSON.parse(payload.metadata);
		expect(metadata.rag_processor).toBe('single_file_rag');
		expect(metadata.file_path).toBe('docs/mi_documento.md');
		expect(metadata.document_rag).toBeUndefined();
	});
});
