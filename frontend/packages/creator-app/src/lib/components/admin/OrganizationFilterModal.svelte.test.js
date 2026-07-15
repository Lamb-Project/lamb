import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, waitFor, fireEvent } from '@testing-library/svelte';
import OrganizationFilterModal from './OrganizationFilterModal.svelte';

vi.mock('$lib/services/adminService', () => ({
	searchOrganizations: vi.fn()
}));
vi.mock('@lamb/ui', async () => {
	const { readable } = await import('svelte/store');
	return {
		user: { subscribe: vi.fn((fn) => { fn({ isLoggedIn: true, token: 'tok' }); return vi.fn(); }) },
		_: readable((k, o) => o?.default || k),
		locale: readable('en'),
		waitLocale: vi.fn(),
		setupI18n: vi.fn()
	};
});

import { searchOrganizations } from '$lib/services/adminService';

describe('OrganizationFilterModal', () => {
	const onApply = vi.fn();
	const onClose = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders search input and calls API on search', async () => {
		searchOrganizations.mockResolvedValueOnce({
			organizations: [{ id: 3, name: 'PEPESITO', slug: 'pepesito' }]
		});

		const { getByPlaceholderText, getByText } = render(OrganizationFilterModal, {
			props: { onApply, onClose }
		});

		const input = getByPlaceholderText(/organization/i);
		await fireEvent.input(input, { target: { value: 'pepe' } });

		const searchBtn = getByText(/Search/i);
		await fireEvent.click(searchBtn);

		await waitFor(() => {
			expect(getByText('PEPESITO')).toBeInTheDocument();
		});
	});

	it('calls onApply with selected org', async () => {
		searchOrganizations.mockResolvedValueOnce({
			organizations: [{ id: 3, name: 'PEPESITO', slug: 'pepesito' }]
		});

		const { getByPlaceholderText, getByText } = render(OrganizationFilterModal, {
			props: { onApply, onClose }
		});

		const input = getByPlaceholderText(/organization/i);
		await fireEvent.input(input, { target: { value: 'pepe' } });
		await fireEvent.click(getByText(/Search/i));

		await waitFor(() => expect(getByText('PEPESITO')).toBeInTheDocument());

		await fireEvent.click(getByText('PEPESITO'));
		await fireEvent.click(getByText(/Apply/i));

		expect(onApply).toHaveBeenCalledWith({ id: 3, name: 'PEPESITO', slug: 'pepesito' });
	});
});
