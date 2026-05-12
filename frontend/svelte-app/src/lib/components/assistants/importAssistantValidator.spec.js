// importAssistantValidator.spec.js — TDD for import validation logic
import { describe, test, expect } from 'vitest';
import { validateImportedAssistant } from './importAssistantValidator.js';
import { extractModelsFromConnectorData } from './assistantFormUtils.svelte.js';

const BASE_CAPABILITIES = {
    prompt_processors: ['default_processor', 'custom_processor'],
    connectors: {
        openai: { models: ['gpt-4', 'gpt-3.5-turbo'] },
        banana_img: { models: ['banana-v1'] },
    },
    rag_processors: ['no_rag', 'simple_rag', 'single_file_rag', 'rubric_rag']
};

function validAssistantJSON(overrides = {}) {
    const data = {
        name: 'Test Assistant',
        system_prompt: 'You are helpful.',
        metadata: JSON.stringify({
            prompt_processor: 'default_processor',
            connector: 'openai',
            llm: 'gpt-4',
            rag_processor: 'no_rag',
            capabilities: { vision: false, image_generation: false }
        }),
        ...overrides
    };
    return JSON.stringify(data);
}

describe('validateImportedAssistant', () => {
    test('returns valid result for a well-formed assistant JSON', () => {
        const result = validateImportedAssistant(
            validAssistantJSON(),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.hasErrors).toBe(false);
        expect(result.parsedData).toBeDefined();
        expect(result.callbackData).toBeDefined();
        expect(result.callbackData.rag_processor).toBe('no_rag');
    });

    test('reports error for invalid JSON', () => {
        const result = validateImportedAssistant(
            '{invalid',
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.hasErrors).toBe(true);
        expect(result.parsedData).toBeNull();
        expect(result.validationLog.some(log => log.startsWith('❌'))).toBe(true);
    });

    test('reports error for non-object JSON (array)', () => {
        const result = validateImportedAssistant(
            '[1,2,3]',
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.hasErrors).toBe(true);
        expect(result.parsedData).toEqual([1, 2, 3]);
        expect(result.validationLog.some(log => log.includes('not a valid JSON object'))).toBe(true);
    });

    test('reports missing required fields', () => {
        const result = validateImportedAssistant(
            JSON.stringify({ description: 'only desc' }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.hasErrors).toBe(true);
        expect(result.validationLog.some(log => log.startsWith('❌') && log.includes('name'))).toBe(true);
        expect(result.validationLog.some(log => log.startsWith('❌') && log.includes('metadata'))).toBe(true);
    });

    test('skips detailed checks when capabilities is null', () => {
        const result = validateImportedAssistant(
            validAssistantJSON(),
            null,
            extractModelsFromConnectorData
        );
        expect(result.hasErrors).toBe(false);
        expect(result.validationLog.some(log => log.includes('System capabilities not loaded'))).toBe(true);
    });

    test('reports invalid prompt_processor', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'fake_processor', connector: 'openai', llm: 'gpt-4', rag_processor: 'no_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('⚠️') && log.includes('prompt_processor'))).toBe(true);
    });

    test('reports invalid connector', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'fake_conn', llm: 'gpt-4', rag_processor: 'no_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('⚠️') && log.includes('connector'))).toBe(true);
    });

    test('reports invalid LLM for valid connector', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'openai', llm: 'fake-llm', rag_processor: 'no_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('⚠️') && log.includes('llm'))).toBe(true);
    });

    test('does NOT report invalid LLM when connector is also invalid (no double warning)', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'fake_conn', llm: 'gpt-4', rag_processor: 'no_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        // Should have connector warning but no LLM warning (branch only runs when connector IS valid)
        const warnings = result.validationLog.filter(log => log.startsWith('⚠️'));
        expect(warnings.length).toBe(1);
        expect(warnings[0]).toContain('connector');
    });

    test('reports invalid rag_processor', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'openai', llm: 'gpt-4', rag_processor: 'fake_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('⚠️') && log.includes('rag_processor'))).toBe(true);
    });

    test('reports missing file_path for single_file_rag', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'openai', llm: 'gpt-4', rag_processor: 'single_file_rag', file_path: '' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('❌') && log.includes('file_path'))).toBe(true);
    });

    test('warns about RAG_Top_k when KB-based RAG used without it', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'openai', llm: 'gpt-4', rag_processor: 'simple_rag' })
            }),
            { ...BASE_CAPABILITIES, rag_processors: [...BASE_CAPABILITIES.rag_processors, 'simple_rag'] },
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('⚠️') && log.includes('RAG_Top_k'))).toBe(true);
    });

    test('warns about RAG_collections when KB-based RAG used without it', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({
                metadata: JSON.stringify({ prompt_processor: 'default_processor', connector: 'openai', llm: 'gpt-4', rag_processor: 'simple_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('⚠️') && log.includes('RAG_collections'))).toBe(true);
    });

    test('handles missing metadata field', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({ metadata: undefined }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('❌') && log.includes('metadata'))).toBe(true);
        expect(result.hasErrors).toBe(true);
    });

    test('handles invalid metadata JSON', () => {
        const result = validateImportedAssistant(
            validAssistantJSON({ metadata: '{not valid' }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        expect(result.validationLog.some(log => log.startsWith('❌') && log.includes('metadata JSON'))).toBe(true);
        expect(result.hasErrors).toBe(true);
    });

    test('falls back to api_callback when metadata is missing', () => {
        const result = validateImportedAssistant(
            JSON.stringify({
                name: 'Test',
                system_prompt: 'prompt',
                metadata: '',
                api_callback: JSON.stringify({ prompt_processor: 'default_processor', connector: 'openai', llm: 'gpt-4', rag_processor: 'no_rag' })
            }),
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        // metadata field exists (required field check passes), but falls back to api_callback for parsing
        expect(result.hasErrors).toBe(false);
        expect(result.callbackData).toBeDefined();
        expect(result.callbackData.rag_processor).toBe('no_rag');
    });

    test('handles content that is not a string gracefully', () => {
        const result = validateImportedAssistant(
            null,
            BASE_CAPABILITIES,
            extractModelsFromConnectorData
        );
        // Should handle non-string gracefully — parsedData = null, hasErrors = true
        expect(result.hasErrors).toBe(true);
        expect(result.parsedData).toBeNull();
    });
});
