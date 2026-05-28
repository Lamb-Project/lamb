import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/services/libraryService', () => ({
	getLibraries: vi.fn(),
	getItems: vi.fn()
}));

import { getLibraries, getItems } from '$lib/services/libraryService';
import { fetchLibraries, fetchLibraryItems } from './logic/assistantFormFetchers.js';

describe('fetchLibraries', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('populates form.libraries on success', async () => {
		const mockLibraries = [
			{ id: 'lib-1', name: 'My Library' },
			{ id: 'lib-2', name: 'Shared Library' }
		];
		getLibraries.mockResolvedValue(mockLibraries);

		const form = {
			libraries: [],
			loadingLibraries: false,
			libraryError: '',
			librariesFetchAttempted: false
		};

		await fetchLibraries(form);

		expect(form.libraries).toEqual(mockLibraries);
		expect(form.librariesFetchAttempted).toBe(true);
		expect(form.loadingLibraries).toBe(false);
		expect(form.libraryError).toBe('');
	});

	it('sets libraryError on failure', async () => {
		getLibraries.mockRejectedValue(new Error('Network error'));

		const form = {
			libraries: [],
			loadingLibraries: false,
			libraryError: '',
			librariesFetchAttempted: false
		};

		await fetchLibraries(form);

		expect(form.libraries).toEqual([]);
		expect(form.libraryError).toBeTruthy();
		expect(form.librariesFetchAttempted).toBe(true);
	});

	it('skips fetch if already attempted', async () => {
		const form = {
			libraries: [{ id: 'lib-1', name: 'Cached' }],
			loadingLibraries: false,
			libraryError: '',
			librariesFetchAttempted: true
		};

		await fetchLibraries(form);

		expect(getLibraries).not.toHaveBeenCalled();
	});
});

describe('fetchLibraryItems', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('populates form.libraryItems on success', async () => {
		const mockResponse = {
			items: [
				{ id: 'item-1', title: 'Doc A', status: 'ready' },
				{ id: 'item-2', title: 'Doc B', status: 'processing' }
			],
			total: 2
		};
		getItems.mockResolvedValue(mockResponse);

		const form = {
			libraryItems: [],
			loadingItems: false,
			itemsError: '',
			itemsFetchAttempted: false
		};

		await fetchLibraryItems(form, 'lib-1');

		expect(form.libraryItems).toEqual(mockResponse.items);
		expect(form.itemsFetchAttempted).toBe(true);
		expect(form.loadingItems).toBe(false);
	});

	it('clears items and sets error on failure', async () => {
		getItems.mockRejectedValue(new Error('Not found'));

		const form = {
			libraryItems: [{ id: 'old', title: 'Old' }],
			loadingItems: false,
			itemsError: '',
			itemsFetchAttempted: false
		};

		await fetchLibraryItems(form, 'lib-1');

		expect(form.libraryItems).toEqual([]);
		expect(form.itemsError).toBeTruthy();
	});
});
