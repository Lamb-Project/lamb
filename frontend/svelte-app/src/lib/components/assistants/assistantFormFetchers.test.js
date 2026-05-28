import { describe, test, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/services/knowledgeBaseService', () => ({
	getUserKnowledgeBases: vi.fn(),
	getSharedKnowledgeBases: vi.fn()
}));

vi.mock('$lib/services/rubricService', () => ({
	fetchAccessibleRubrics: vi.fn()
}));

vi.mock('$lib/services/apiClient', () => ({
	apiJson: vi.fn()
}));

vi.mock('$lib/services/libraryService', () => ({
	getLibraries: vi.fn(),
	getItems: vi.fn()
}));

vi.mock('$lib/utils/ragProcessorHelpers.js', () => ({
	isKbBasedRag: (p) => ['simple_rag', 'context_aware_rag', 'hierarchical_rag'].includes(p),
	isSingleFileRag: (p) => p === 'single_file_rag',
	isRubricRag: (p) => p === 'rubric_rag'
}));

vi.mock('$lib/utils/assistantData', () => ({
	getAssistantMetadataObject: (data) => {
		if (!data) return {};
		if (typeof data.metadata === 'string') {
			try { return JSON.parse(data.metadata); } catch { return {}; }
		}
		return data.metadata || {};
	}
}));

import { fetchKnowledgeBases, fetchRubricsList, fetchUserFiles } from './logic/assistantFormFetchers.js';
import { getUserKnowledgeBases, getSharedKnowledgeBases } from '$lib/services/knowledgeBaseService';
import { fetchAccessibleRubrics } from '$lib/services/rubricService';
import { apiJson } from '$lib/services/apiClient';

function createMockForm(overrides = {}) {
	return {
		selectedRagProcessor: 'simple_rag',
		loadingKnowledgeBases: false,
		kbFetchAttempted: false,
		knowledgeBaseError: '',
		ownedKnowledgeBases: [],
		sharedKnowledgeBases: [],
		loadingRubrics: false,
		rubricsFetchAttempted: false,
		rubricError: '',
		accessibleRubrics: [],
		loadingFiles: false,
		filesFetchAttempted: false,
		fileError: '',
		userFiles: [],
		selectedFilePath: '',
		...overrides
	};
}

describe('fetchKnowledgeBases', () => {
	beforeEach(() => { vi.clearAllMocks(); });

	test('fetches and sorts owned + shared KBs', async () => {
		getUserKnowledgeBases.mockResolvedValue([{ id: '2', name: 'Zeta' }, { id: '1', name: 'Alpha' }]);
		getSharedKnowledgeBases.mockResolvedValue([{ id: '3', name: 'Beta' }]);
		const form = createMockForm();

		await fetchKnowledgeBases(form);

		expect(form.ownedKnowledgeBases).toEqual([{ id: '1', name: 'Alpha' }, { id: '2', name: 'Zeta' }]);
		expect(form.sharedKnowledgeBases).toEqual([{ id: '3', name: 'Beta' }]);
		expect(form.loadingKnowledgeBases).toBe(false);
		expect(form.kbFetchAttempted).toBe(true);
	});

	test('guards against duplicate calls', async () => {
		const form = createMockForm({ kbFetchAttempted: true });
		await fetchKnowledgeBases(form);
		expect(getUserKnowledgeBases).not.toHaveBeenCalled();
	});

	test('handles errors gracefully', async () => {
		getUserKnowledgeBases.mockRejectedValue(new Error('Network error'));
		getSharedKnowledgeBases.mockResolvedValue([]);
		const form = createMockForm();

		await fetchKnowledgeBases(form);

		expect(form.knowledgeBaseError).toContain('Network error');
		expect(form.kbFetchAttempted).toBe(true);
	});
});

describe('fetchRubricsList', () => {
	beforeEach(() => { vi.clearAllMocks(); });

	test('fetches rubrics', async () => {
		fetchAccessibleRubrics.mockResolvedValue({ rubrics: [{ rubric_id: 'r1', title: 'R1' }] });
		const form = createMockForm({ selectedRagProcessor: 'rubric_rag' });

		await fetchRubricsList(form);

		expect(form.accessibleRubrics).toEqual([{ rubric_id: 'r1', title: 'R1' }]);
		expect(form.loadingRubrics).toBe(false);
		expect(form.rubricsFetchAttempted).toBe(true);
	});
});

describe('fetchUserFiles', () => {
	beforeEach(() => { vi.clearAllMocks(); });

	test('fetches files', async () => {
		apiJson.mockResolvedValue([{ name: 'a.pdf', path: '/a.pdf' }]);
		const form = createMockForm({ selectedRagProcessor: 'single_file_rag' });

		await fetchUserFiles(form, {});

		expect(form.userFiles).toEqual([{ name: 'a.pdf', path: '/a.pdf' }]);
		expect(form.filesFetchAttempted).toBe(true);
	});

	test('force flag bypasses filesFetchAttempted guard', async () => {
		apiJson.mockResolvedValue([]);
		const form = createMockForm({ filesFetchAttempted: true });

		await fetchUserFiles(form, { force: true });

		expect(apiJson).toHaveBeenCalled();
	});
});
