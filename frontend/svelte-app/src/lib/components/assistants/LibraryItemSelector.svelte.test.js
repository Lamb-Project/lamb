// src/lib/components/assistants/LibraryItemSelector.svelte.test.js
import { describe, it, expect, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/svelte';
import LibraryItemSelector from './components/LibraryItemSelector.svelte';

vi.mock('$lib/i18n', async () => {
	const { readable } = await import('svelte/store');
	return {
		_: readable((key, opts) => opts?.default || key),
		locale: readable('en'),
		waitLocale: vi.fn().mockResolvedValue(undefined),
		setupI18n: vi.fn()
	};
});

const mockLibraries = [
	{ id: 'lib-1', name: 'My Library' },
	{ id: 'lib-2', name: 'Shared Library' }
];

const mockItems = [
	{ id: 'item-1', title: 'Document A', original_filename: 'doc_a.pdf', status: 'ready' },
	{ id: 'item-2', title: 'Document B', original_filename: 'doc_b.md', status: 'ready' },
	{
		id: 'item-3',
		title: 'Processing Doc',
		original_filename: 'processing.pdf',
		status: 'processing'
	}
];

const defaultProps = {
	libraries: mockLibraries,
	items: mockItems,
	selectedLibraryId: '',
	selectedItemId: '',
	loadingLibraries: false,
	loadingItems: false,
	formState: 'create'
};

describe('LibraryItemSelector', () => {
	it('renders library dropdown with options', () => {
		render(LibraryItemSelector, { props: { ...defaultProps } });
		expect(screen.getByLabelText(/library/i)).toBeTruthy();
	});

	it('renders item dropdown when library is selected', () => {
		render(LibraryItemSelector, {
			props: { ...defaultProps, selectedLibraryId: 'lib-1' }
		});
		expect(screen.getByLabelText(/document/i)).toBeTruthy();
	});

	it('filters out non-ready items', () => {
		const { container } = render(LibraryItemSelector, {
			props: { ...defaultProps, selectedLibraryId: 'lib-1' }
		});
		const itemOptions = container.querySelectorAll('select[name="item-selector"] option');
		const readyOptions = Array.from(itemOptions).filter((o) => o.value && o.value !== '');
		expect(readyOptions.length).toBe(2);
	});

	it('shows link to libraries page', () => {
		render(LibraryItemSelector, {
			props: { ...defaultProps, items: [] }
		});
		const link = screen.getByRole('link', { name: /manage libraries/i });
		expect(link).toBeTruthy();
		expect(link.getAttribute('href')).toBe('/libraries');
	});

	it('shows loading state for libraries', () => {
		render(LibraryItemSelector, {
			props: { ...defaultProps, libraries: [], loadingLibraries: true }
		});
		expect(screen.getByText(/loading libraries/i)).toBeTruthy();
	});

	it('shows message when no libraries available', () => {
		render(LibraryItemSelector, {
			props: { ...defaultProps, libraries: [], items: [] }
		});
		expect(screen.getByText(/no libraries/i)).toBeTruthy();
	});

	it('shows required message in edit mode when no item selected', () => {
		render(LibraryItemSelector, {
			props: { ...defaultProps, formState: 'edit', selectedLibraryId: 'lib-1' }
		});
		expect(screen.getByText(/please select a document/i)).toBeTruthy();
	});
});
