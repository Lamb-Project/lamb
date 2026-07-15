import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { writable } from 'svelte/store';
import ConfigurationPanel from './components/ConfigurationPanel.svelte';

vi.mock('$lib/stores/assistantConfigStore', () => {
	return {
		assistantConfigStore: writable({
			systemCapabilities: { connectors: {} },
			configDefaults: { config: {} },
			loading: false,
			error: null
		})
	};
});

vi.mock('@lamb/ui', () => ({
	_: vi.fn((key, opts) => opts?.default || key)
}));

const baseProps = {
	formState: 'create',
	isAdvancedMode: true,
	promptProcessors: ['simple_augment', 'kvcache_augment'],
	connectorsList: ['openai'],
	ragProcessors: ['no_rag', 'simple_rag', 'query_rewriting_ks_rag'],
	selectedPromptProcessor: 'kvcache_augment',
	selectedConnector: 'openai',
	selectedLlm: 'gpt-4o-mini',
	selectedRagProcessor: 'no_rag',
	availableModels: ['gpt-4o-mini'],
	ownedKnowledgeBases: [],
	sharedKnowledgeBases: [],
	selectedKnowledgeBases: [],
	ownedKnowledgeStores: [],
	sharedKnowledgeStores: [],
	selectedKnowledgeStores: [],
	libraries: [],
	libraryItems: [],
	userFiles: [],
	selectedFilePath: '',
	documentRagEnabled: false,
	selectedLibraryId: '',
	selectedItemId: '',
	visionEnabled: false,
	imageGenerationEnabled: false,
	RAG_Top_k: 3,
	loadingKnowledgeBases: false,
	knowledgeBaseError: '',
	loadingKnowledgeStores: false,
	knowledgeStoreError: '',
	loadingLibraries: false,
	libraryError: '',
	loadingItems: false,
	itemsError: '',
	loadingFiles: false,
	fileError: ''
};

describe('ConfigurationPanel - PPS dropdown in create mode', () => {
	it('shows both PPS options in create mode', () => {
		render(ConfigurationPanel, { props: { ...baseProps, formState: 'create' } });
		const select = document.getElementById('prompt-processor');
		const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
		expect(options).toContain('simple_augment');
		expect(options).toContain('kvcache_augment');
	});

	it('shows simple_augment in PPS dropdown in edit mode (disabled)', () => {
		render(ConfigurationPanel, { props: { ...baseProps, formState: 'edit' } });
		const select = document.getElementById('prompt-processor');
		const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
		expect(options).toContain('simple_augment');
		expect(options).toContain('kvcache_augment');
		expect(select).toBeDisabled();
	});
});

describe('ConfigurationPanel - legacy edit mode', () => {
	it('passes isLegacyEdit=true to RagOptionsPanel when editing legacy PPS', () => {
		const { container } = render(ConfigurationPanel, {
			props: {
				...baseProps,
				formState: 'edit',
				selectedPromptProcessor: 'simple_augment',
				selectedRagProcessor: 'simple_rag',
				ownedKnowledgeBases: [{ id: 'kb1', name: 'Test KB' }]
			}
		});
		const legacyBanner = container.querySelector('.bg-amber-50');
		expect(legacyBanner).toBeTruthy();
	});
});
