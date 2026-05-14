// src/lib/components/assistants/assistantFormUtils.svelte.test.js
import { describe, test, expect, vi } from 'vitest';
import {
	selectModel,
	loadRagPlaceholders,
	extractModelsFromConnectorData,
	extractModelsMetadata,
	highlightPlaceholders
} from './assistantFormUtils.svelte.js';



describe('selectModel', () => {
	test('selects target LLM when available', () => {
		const result = selectModel('gpt-4', ['gpt-3.5-turbo', 'gpt-4']);
		expect(result).toBe('gpt-4');
	});
	test('falls back to first model when target not available', () => {
		const result = selectModel('nonexistent', ['gpt-3.5-turbo', 'gpt-4']);
		expect(result).toBe('gpt-3.5-turbo');
	});
	test('returns empty string when no models available', () => {
		const result = selectModel('gpt-4', []);
		expect(result).toBe('');
	});
});

describe('loadRagPlaceholders', () => {
	test('returns placeholders from config', () => {
		const config = { rag_placeholders: ['{context}', '{user_input}', '{custom}'] };
		expect(loadRagPlaceholders(config)).toEqual(['{context}', '{user_input}', '{custom}']);
	});
	test('returns defaults when config has no placeholders', () => {
		expect(loadRagPlaceholders({})).toEqual(['{context}', '{user_input}']);
	});
	test('returns defaults when config is null', () => {
		expect(loadRagPlaceholders(null)).toEqual(['{context}', '{user_input}']);
	});
});

describe('extractModelsFromConnectorData', () => {
	test('extracts model IDs from object array', () => {
		const data = { models: [{ id: 'gpt-4' }, { id: 'gpt-3.5' }] };
		expect(extractModelsFromConnectorData(data)).toEqual(['gpt-4', 'gpt-3.5']);
	});
	test('returns string array as-is', () => {
		const data = { models: ['gpt-4', 'gpt-3.5'] };
		expect(extractModelsFromConnectorData(data)).toEqual(['gpt-4', 'gpt-3.5']);
	});
	test('handles available_llms', () => {
		const data = { available_llms: ['llama2'] };
		expect(extractModelsFromConnectorData(data)).toEqual(['llama2']);
	});
	test('returns empty for null', () => {
		expect(extractModelsFromConnectorData(null)).toEqual([]);
	});
});


describe('highlightPlaceholders', () => {
	test('highlights placeholders in text', () => {
		const result = highlightPlaceholders('Hello {context}', ['{context}']);
		expect(result).toContain('<span class="bg-blue-100');
		expect(result).toContain('{context}');
	});
	test('returns empty string for falsy input', () => {
		expect(highlightPlaceholders('', ['{context}'])).toBe('');
	});
});
