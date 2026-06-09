import { describe, test, expect, vi } from 'vitest';

vi.mock('$lib/utils/ragProcessorHelpers.js', () => ({
	isKbBasedRag: (p) => ['simple_rag', 'context_aware_rag', 'hierarchical_rag'].includes(p),
	isSingleFileRag: (p) => p === 'single_file_rag',
	isRubricRag: (p) => p === 'rubric_rag'
}));

import { validateSubmission, buildAssistantPayload } from './logic/assistantFormSubmit.js';

describe('validateSubmission', () => {
	test('returns error when name is empty', () => {
		const result = validateSubmission({
			name: '',
			selectedRagProcessor: 'no_rag',
			selectedRubricId: ''
		});
		expect(result).toContain('Name');
	});

	test('returns error when rubric_rag selected without rubric', () => {
		const result = validateSubmission({
			name: 'test',
			selectedRagProcessor: 'rubric_rag',
			selectedRubricId: ''
		});
		expect(result).toContain('rubric');
	});

	test('returns null when valid', () => {
		const result = validateSubmission({
			name: 'test',
			selectedRagProcessor: 'no_rag',
			selectedRubricId: ''
		});
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
