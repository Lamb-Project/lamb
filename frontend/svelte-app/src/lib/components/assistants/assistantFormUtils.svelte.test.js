// src/lib/components/assistants/assistantFormUtils.svelte.test.js
import { describe, test, expect, vi } from 'vitest';
import {
	createAsyncResource,
	createModelSelector,
	loadRagPlaceholders,
	extractModelsFromConnectorData,
	extractModelsMetadata,
	escapeHtml,
	highlightPlaceholders
} from './assistantFormUtils.svelte.js';

describe('createAsyncResource', () => {
	test('initializes with correct default state', () => {
		const resource = createAsyncResource(vi.fn());
		expect(resource.data).toEqual([]);
		expect(resource.loading).toBe(false);
		expect(resource.error).toBe('');
		expect(resource.attempted).toBe(false);
	});
	test('sets loading during fetch', async () => {
		const fetcher = vi.fn(
			() => new Promise((resolve) => setTimeout(() => resolve(['item1']), 10))
		);
		const resource = createAsyncResource(fetcher);
		const fetchPromise = resource.fetch();
		expect(resource.loading).toBe(true);
		await fetchPromise;
		expect(resource.loading).toBe(false);
		expect(resource.data).toEqual(['item1']);
		expect(resource.attempted).toBe(true);
	});
	test('sets error on fetch failure', async () => {
		const fetcher = vi.fn(() => Promise.reject(new Error('Network error')));
		const resource = createAsyncResource(fetcher);
		await resource.fetch();
		expect(resource.error).toBe('Network error');
		expect(resource.attempted).toBe(true);
		expect(resource.data).toEqual([]);
	});
	test('skips fetch if already attempted', async () => {
		const fetcher = vi.fn(() => Promise.resolve(['data']));
		const resource = createAsyncResource(fetcher);
		await resource.fetch();
		await resource.fetch();
		expect(fetcher).toHaveBeenCalledTimes(1);
	});
	test('reset clears all state', async () => {
		const fetcher = vi.fn(() => Promise.resolve(['data']));
		const resource = createAsyncResource(fetcher);
		await resource.fetch();
		resource.reset();
		expect(resource.data).toEqual([]);
		expect(resource.loading).toBe(false);
		expect(resource.error).toBe('');
		expect(resource.attempted).toBe(false);
	});
});

describe('createModelSelector', () => {
	test('selects target LLM when available', () => {
		const result = createModelSelector('gpt-4', ['gpt-3.5-turbo', 'gpt-4']);
		expect(result).toBe('gpt-4');
	});
	test('falls back to first model when target not available', () => {
		const result = createModelSelector('nonexistent', ['gpt-3.5-turbo', 'gpt-4']);
		expect(result).toBe('gpt-3.5-turbo');
	});
	test('returns empty string when no models available', () => {
		const result = createModelSelector('gpt-4', []);
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

describe('escapeHtml', () => {
	test('escapes < and >', () => {
		expect(escapeHtml('<div>')).toBe('&lt;div&gt;');
	});
	test('escapes &', () => {
		expect(escapeHtml('a & b')).toBe('a &amp; b');
	});
	test('escapes quotes', () => {
		expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;');
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
