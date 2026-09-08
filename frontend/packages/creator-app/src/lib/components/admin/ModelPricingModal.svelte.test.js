import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, waitFor, fireEvent } from '@testing-library/svelte';
import ModelPricingModal from './ModelPricingModal.svelte';

vi.mock('$lib/services/adminService', () => ({
	fetchModelPricing: vi.fn(),
	createModelPricing: vi.fn(),
	updateModelPricing: vi.fn(),
	deleteModelPricing: vi.fn()
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
vi.mock('$lib/stores/toast', () => ({
	toast: { success: vi.fn(), error: vi.fn() }
}));

import { fetchModelPricing, updateModelPricing } from '$lib/services/adminService';

describe('ModelPricingModal', () => {
	beforeEach(() => vi.clearAllMocks());

	it('loads and displays pricing rows on mount', async () => {
		fetchModelPricing.mockResolvedValueOnce({
			pricing: [
				{ id: 1, provider: 'openai', model_name: 'gpt-4o', input_per_1m: 2.5, cached_input_per_1m: 1.25, output_per_1m: 10.0, updated_at: 1000 }
			]
		});

		const { getByText } = render(ModelPricingModal, { props: { onClose: vi.fn() } });
		await waitFor(() => {
			expect(getByText('gpt-4o')).toBeInTheDocument();
			expect(getByText('openai')).toBeInTheDocument();
		});
	});

	it('shows error when fetch fails', async () => {
		fetchModelPricing.mockRejectedValueOnce(new Error('Network error'));
		const { getByText } = render(ModelPricingModal, { props: { onClose: vi.fn() } });
		await waitFor(() => {
			expect(getByText(/Network error/)).toBeInTheDocument();
		});
	});

	it('edits pricing row inline and saves', async () => {
		fetchModelPricing.mockResolvedValueOnce({
			pricing: [
				{ id: 1, provider: 'openai', model_name: 'gpt-4o', input_per_1m: 2.5, cached_input_per_1m: 1.25, output_per_1m: 10.0, updated_at: 1000 }
			]
		});
		updateModelPricing.mockResolvedValueOnce({
			id: 1, provider: 'openai', model_name: 'gpt-4o', input_per_1m: 3.0, cached_input_per_1m: 1.5, output_per_1m: 12.0, updated_at: 2000
		});

		const { getByText, getAllByRole } = render(ModelPricingModal, { props: { onClose: vi.fn() } });
		await waitFor(() => expect(getByText('gpt-4o')).toBeInTheDocument());

		const editButtons = getAllByRole('button', { name: /edit/i });
		await fireEvent.click(editButtons[0]);

		await waitFor(() => expect(getAllByRole('spinbutton').length).toBeGreaterThan(0));

		const saveButtons = getAllByRole('button', { name: /save/i });
		await fireEvent.click(saveButtons[0]);

		await waitFor(() => {
			expect(updateModelPricing).toHaveBeenCalledWith(1, expect.objectContaining({
				input_per_1m: expect.any(Number),
				output_per_1m: expect.any(Number)
			}));
		});
	});
});
