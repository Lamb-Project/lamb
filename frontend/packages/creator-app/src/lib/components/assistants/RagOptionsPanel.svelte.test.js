import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import RagOptionsPanel from './components/RagOptionsPanel.svelte';

vi.mock('@lamb/ui', () => ({
	_: vi.fn((key, opts) => opts?.default || key)
}));

const baseProps = {
	selectedRagProcessor: 'no_rag',
	RAG_Top_k: 3,
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
	selectedLibraryId: '',
	selectedItemId: '',
	formState: 'edit',
	isLegacyEdit: false
};

describe('RagOptionsPanel - legacy edit mode', () => {
	it('shows legacy notice banner when isLegacyEdit is true', () => {
		render(RagOptionsPanel, {
			props: {
				...baseProps,
				selectedRagProcessor: 'simple_rag',
				isLegacyEdit: true,
				ownedKnowledgeBases: [{ id: 'kb1', name: 'Test KB' }]
			}
		});
		expect(screen.getByText(/legacy configuration/i)).toBeTruthy();
	});

	it('does not show legacy notice when isLegacyEdit is false', () => {
		render(RagOptionsPanel, {
			props: {
				...baseProps,
				selectedRagProcessor: 'query_rewriting_ks_rag',
				isLegacyEdit: false,
				ownedKnowledgeStores: [
					{
						id: 'ks1',
						name: 'Test KS',
						embedding_vendor: 'openai',
						embedding_model: 'text-embedding-3-small'
					}
				]
			}
		});
		expect(screen.queryByText(/legacy configuration/i)).toBeNull();
	});

	it('disables KB selector when isLegacyEdit is true', () => {
		render(RagOptionsPanel, {
			props: {
				...baseProps,
				selectedRagProcessor: 'simple_rag',
				isLegacyEdit: true,
				ownedKnowledgeBases: [{ id: 'kb1', name: 'Test KB' }]
			}
		});
		const checkboxes = document.querySelectorAll('input[type="checkbox"]');
		checkboxes.forEach((cb) => {
			expect(cb.disabled).toBe(true);
		});
	});

	it('disables KS selector when isLegacyEdit is true', () => {
		render(RagOptionsPanel, {
			props: {
				...baseProps,
				selectedRagProcessor: 'query_rewriting_ks_rag',
				isLegacyEdit: true,
				ownedKnowledgeStores: [
					{
						id: 'ks1',
						name: 'Test KS',
						embedding_vendor: 'openai',
						embedding_model: 'text-embedding-3-small'
					}
				]
			}
		});
		const checkboxes = document.querySelectorAll('input[type="checkbox"]');
		checkboxes.forEach((cb) => {
			expect(cb.disabled).toBe(true);
		});
	});
});
