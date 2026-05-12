// src/lib/components/assistants/AssistantForm.svelte.test.js
import { describe, test, expect, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';

// Mock the assistantConfigStore before any imports
vi.mock('$lib/stores/assistantConfigStore', async () => {
	const { writable } = await import('svelte/store');
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
				}
			},
			rag_processors: [
				'simple_rag',
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
		lastLoadedTimestamp: Date.now()
	};
	const store = writable(defaultState);
	return {
		assistantConfigStore: {
			subscribe: store.subscribe,
			loadConfig: vi.fn(),
			reset: vi.fn(),
			clearCache: vi.fn()
		}
	};
});

vi.mock('$lib/i18n', async () => {
	const { readable } = await import('svelte/store');
	return {
		_: readable((key, opts) => opts?.default || key),
		locale: readable('en'),
		waitLocale: vi.fn().mockResolvedValue(undefined),
		setupI18n: vi.fn()
	};
});

vi.mock('$lib/services/knowledgeBaseService', () => ({
	getUserKnowledgeBases: vi.fn().mockResolvedValue([]),
	getSharedKnowledgeBases: vi.fn().mockResolvedValue([])
}));

vi.mock('$lib/services/assistantService', () => ({
	createAssistant: vi.fn().mockResolvedValue({ assistant_id: 99 }),
	updateAssistant: vi.fn().mockResolvedValue({ id: 1 }),
	getSystemCapabilities: vi.fn().mockResolvedValue({})
}));

vi.mock('$lib/services/rubricService', () => ({
	fetchAccessibleRubrics: vi.fn().mockResolvedValue({ rubrics: [] })
}));

vi.mock('$lib/services/apiClient', () => ({
	apiFetch: vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) })
}));

vi.mock('$lib/stores/templateStore', async () => {
	const { writable } = await import('svelte/store');
	return {
		openTemplateSelectModal: vi.fn(),
		templateSelectModalOpen: writable(false)
	};
});

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/paths', () => ({ base: '' }));
vi.mock('$app/environment', () => ({ browser: true }));

describe('AssistantForm.svelte — baseline contract tests', () => {
	describe('Create mode (assistant=null)', () => {
		test('renders the create mode title', async () => {
			const component = await import('./AssistantForm.svelte');
			const { container } = render(component.default, {
				props: { assistant: null }
			});

			await waitFor(() => {
				const heading = container.querySelector('h2');
				expect(heading).toBeInTheDocument();
			});
		});

		test('renders name input as editable', async () => {
			const component = await import('./AssistantForm.svelte');
			render(component.default, { props: { assistant: null } });

			await waitFor(() => {
				const nameInput =
					screen.queryByLabelText(/name/i) || document.getElementById('assistant-name');
				expect(nameInput).toBeInTheDocument();
			});
		});

		test('renders description textarea', async () => {
			const component = await import('./AssistantForm.svelte');
			render(component.default, { props: { assistant: null } });

			await waitFor(() => {
				const desc = document.getElementById('assistant-description');
				expect(desc).toBeInTheDocument();
			});
		});

		test('renders system prompt textarea', async () => {
			const component = await import('./AssistantForm.svelte');
			render(component.default, { props: { assistant: null } });

			await waitFor(() => {
				const sp = document.getElementById('system-prompt');
				expect(sp).toBeInTheDocument();
			});
		});

		test('renders LLM dropdown', async () => {
			const component = await import('./AssistantForm.svelte');
			render(component.default, { props: { assistant: null } });

			await waitFor(() => {
				const llm = document.getElementById('llm');
				expect(llm).toBeInTheDocument();
			});
		});

		test('renders save button', async () => {
			const component = await import('./AssistantForm.svelte');
			render(component.default, { props: { assistant: null } });

			await waitFor(() => {
				const saveBtn = screen.getByRole('button', { name: /save/i });
				expect(saveBtn).toBeInTheDocument();
			});
		});
	});

	describe('Edit mode (assistant with data)', () => {
		test('renders with edit title when assistant is provided', async () => {
			const component = await import('./AssistantForm.svelte');
			const { container } = render(component.default, {
				props: {
					assistant: {
						id: 1,
						name: '1_test_assistant',
						description: 'Test',
						system_prompt: 'You are helpful.',
						prompt_template: 'Template',
						RAG_Top_k: 5,
						metadata: JSON.stringify({
							prompt_processor: 'default_processor',
							connector: 'openai',
							llm: 'gpt-4',
							rag_processor: 'simple_rag',
							capabilities: { vision: false, image_generation: false }
						})
					}
				}
			});

			await waitFor(() => {
				const heading = container.querySelector('h2');
				expect(heading).toBeInTheDocument();
			});
		});
	});

	describe('Form submission', () => {
		test('calls createAssistant on submit in create mode with valid data', async () => {
			const { createAssistant } = await import('$lib/services/assistantService');
			const component = await import('./AssistantForm.svelte');
			render(component.default, { props: { assistant: null } });

			await waitFor(() => {
				const nameInput = document.getElementById('assistant-name');
				expect(nameInput).toBeInTheDocument();
			});

			const nameInput = document.getElementById('assistant-name');
			await fireEvent.input(nameInput, { target: { value: 'test_assistant' } });

			const form = document.getElementById('assistant-form-main');
			expect(form).toBeInTheDocument();

			await fireEvent.submit(form);

			await waitFor(
				() => {
					expect(createAssistant).toHaveBeenCalled();
				},
				{ timeout: 5000 }
			);
		});
	});
});
