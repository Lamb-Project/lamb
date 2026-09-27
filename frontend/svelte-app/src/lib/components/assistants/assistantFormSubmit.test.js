import { describe, test, expect, vi } from 'vitest';

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

	test('RAG configurations need their placeholders and sources (#335)', () => {
		const base = { name: 'test', selectedRubricId: '', selectedPromptProcessor: 'simple_augment' };
		const full = 'Context: {context}\n\nUser: {user_input}';
		expect(validateSubmission({ ...base, selectedRagProcessor: 'no_rag', prompt_template: '' })).toBeNull();
		expect(validateSubmission({ ...base, selectedRagProcessor: 'no_rag', prompt_template: 'Answer: {user_input}' })).toBeNull();
		expect(validateSubmission({ ...base, selectedRagProcessor: 'no_rag', prompt_template: 'Be kind.' })).toContain('{user_input}');
		expect(validateSubmission({ ...base, selectedRagProcessor: 'simple_rag', prompt_template: full, selectedKnowledgeBases: ['3'] })).toBeNull();
		expect(validateSubmission({ ...base, selectedRagProcessor: 'simple_rag', prompt_template: full, selectedKnowledgeBases: [] })).toContain('knowledge base');
		expect(validateSubmission({ ...base, selectedRagProcessor: 'context_aware_rag', prompt_template: 'User: {user_input}', selectedKnowledgeBases: ['3'] })).toContain('{context}');
		expect(validateSubmission({ ...base, selectedRagProcessor: 'single_file_rag', prompt_template: full, selectedFilePath: '' })).toContain('needs a file');
		expect(validateSubmission({ ...base, selectedRagProcessor: 'simple_rag', prompt_template: '', selectedKnowledgeBases: ['3'], selectedPromptProcessor: 'custom' })).toBeNull();
	});

	test('an edit that keeps the stored configuration is not blocked (#335)', () => {
		const stored = { id: 5, prompt_template: '', RAG_collections: '',
			metadata: JSON.stringify({ prompt_processor: 'simple_augment', rag_processor: 'simple_rag', connector: 'openai', llm: 'm', file_path: '' }) };
		const form = { name: 'renamed', description: '', system_prompt: '', RAG_Top_k: 3, formState: 'edit', initialAssistantData: stored,
			selectedPromptProcessor: 'simple_augment', selectedConnector: 'openai', selectedLlm: 'm', selectedRagProcessor: 'simple_rag',
			prompt_template: '', selectedKnowledgeBases: [], selectedRubricId: '', selectedFilePath: '' };
		expect(validateSubmission(form)).toBeNull();
		expect(validateSubmission({ ...form, prompt_template: 'User: {user_input}' })).toContain('{context}');
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
			selectedFilePath: '',
			visionEnabled: false,
			imageGenerationEnabled: false,
			selectedKnowledgeBases: [],
			selectedRubricId: '',
			rubricFormat: 'markdown'
		};
		const payload = buildAssistantPayload(form);
		expect(payload.name).toBe('test');
		expect(JSON.parse(payload.metadata).connector).toBe('openai');
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
			selectedFilePath: '',
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
			selectedFilePath: '',
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
});
