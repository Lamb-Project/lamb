// src/lib/components/assistants/__tests__/helpers.js
import { vi } from 'vitest';
import { readable, writable } from 'svelte/store';

/**
 * Creates a mock assistantConfigStore with configurable state.
 * @param {object} overrides - Override default store state
 * @returns {object} Mock store
 */
export function createMockConfigStore(overrides = {}) {
	const defaultState = {
		loading: false,
		error: null,
		systemCapabilities: {
			prompt_processors: ['default_processor', 'template_validator_processor'],
			connectors: {
				openai: {
					models: [
						{ id: 'gpt-4', forced_capabilities: {} },
						{ id: 'gpt-3.5-turbo', forced_capabilities: {} }
					],
					metadata: {
						description: 'OpenAI connector',
						capabilities: { vision_input: true }
					}
				},
				ollama: {
					models: [{ id: 'llama2', forced_capabilities: {} }],
					metadata: { description: 'Ollama connector', capabilities: {} }
				}
			},
			rag_processors: [
				'simple_rag',
				'context_aware_rag',
				'no_rag',
				'single_file_rag',
				'rubric_rag',
				'hierarchical_rag'
			]
		},
		configDefaults: {
			config: {
				system_prompt: 'Default system prompt',
				prompt_template: '',
				prompt_processor: 'default_processor',
				connector: 'openai',
				llm: 'gpt-4',
				rag_processor: 'no_rag',
				RAG_Top_k: '3',
				rag_placeholders: ['{context}', '{user_input}']
			}
		},
		lastLoadedTimestamp: Date.now(),
		...overrides
	};

	const store = writable(defaultState);

	return {
		subscribe: store.subscribe,
		loadConfig: vi.fn(),
		reset: vi.fn(),
		clearCache: vi.fn()
	};
}

/**
 * Creates a mock i18n $_ function that returns the key or default.
 */
export function createMockTranslate() {
	return vi.fn((key, opts) => opts?.default || key);
}

/**
 * Creates a sample assistant object for edit mode tests.
 */
export function createSampleAssistant(overrides = {}) {
	return {
		id: 1,
		name: '1_test_assistant',
		description: 'A test assistant',
		system_prompt: 'You are a helpful assistant.',
		prompt_template: 'Use {context} to answer: {user_input}',
		RAG_Top_k: 5,
		RAG_collections: 'kb1,kb2',
		metadata: JSON.stringify({
			prompt_processor: 'default_processor',
			connector: 'openai',
			llm: 'gpt-4',
			rag_processor: 'simple_rag',
			capabilities: { vision: false, image_generation: false }
		}),
		...overrides
	};
}

/**
 * Creates a sample knowledge base list.
 */
export function createSampleKnowledgeBases() {
	return {
		owned: [
			{ id: 'kb1', name: 'My KB 1' },
			{ id: 'kb2', name: 'My KB 2' }
		],
		shared: [{ id: 'kb3', name: 'Shared KB', shared_by: 'user@example.com' }]
	};
}

/**
 * Creates sample rubric data.
 */
export function createSampleRubrics() {
	return [
		{
			rubric_id: 'r1',
			title: 'Rubric 1',
			description: 'First rubric',
			is_mine: true,
			is_showcase: false,
			is_public: false
		},
		{
			rubric_id: 'r2',
			title: 'Rubric 2',
			description: 'Second rubric',
			is_mine: false,
			is_showcase: true,
			is_public: true
		}
	];
}
