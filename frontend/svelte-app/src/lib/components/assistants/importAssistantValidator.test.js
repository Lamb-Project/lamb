// importAssistantValidator.test.js — Edge-case tests for modelExtractor and validation
import { describe, test, expect } from 'vitest';
import { validateImportedAssistant } from './importAssistantValidator.js';
import { extractModelsFromConnectorData } from './assistantFormUtils.svelte.js';

describe('modelExtractor edge cases', () => {
	const capabilities = {
		prompt_processors: ['default'],
		connectors: {
			openai: { models: ['gpt-4'] },
			empty_connector: null
		},
		rag_processors: ['no_rag']
	};

	test('handles modelExtractor returning empty for undefined connector data', () => {
		const json = JSON.stringify({
			name: 'Test',
			system_prompt: 'prompt',
			metadata: JSON.stringify({
				prompt_processor: 'default',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag'
			})
		});
		const result = validateImportedAssistant(json, capabilities, extractModelsFromConnectorData);
		expect(result.hasErrors).toBe(false);
	});

	test('handles modelExtractor with null connector data gracefully', () => {
		const caps = {
			prompt_processors: ['default'],
			connectors: {
				openai: null
			},
			rag_processors: ['no_rag']
		};
		const json = JSON.stringify({
			name: 'Test',
			system_prompt: 'prompt',
			metadata: JSON.stringify({
				prompt_processor: 'default',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag'
			})
		});
		const result = validateImportedAssistant(json, caps, extractModelsFromConnectorData);
		// null connector value is treated as invalid connector (not as retrieval failure)
		expect(result.validationLog.some(log => log.includes('Invalid connector'))).toBe(true);
	});

	test('handles modelExtractor with empty models array', () => {
		const caps = {
			prompt_processors: ['default'],
			connectors: {
				openai: { models: [] }
			},
			rag_processors: ['no_rag']
		};
		const json = JSON.stringify({
			name: 'Test',
			system_prompt: 'prompt',
			metadata: JSON.stringify({
				prompt_processor: 'default',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag'
			})
		});
		const result = validateImportedAssistant(json, caps, extractModelsFromConnectorData);
		expect(result.hasErrors).toBe(false);
	});

	test('modelExtractor handles undefined', () => {
		expect(extractModelsFromConnectorData(undefined)).toEqual([]);
	});

	test('modelExtractor handles null', () => {
		expect(extractModelsFromConnectorData(null)).toEqual([]);
	});
});
