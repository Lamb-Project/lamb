import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, waitFor, fireEvent } from '@testing-library/svelte';
import CostManagementPanel from './CostManagementPanel.svelte';

vi.mock('axios', () => ({
	default: {
		get: vi.fn(),
		put: vi.fn(),
		isAxiosError: vi.fn(() => false),
		create: vi.fn(() => ({
			interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } }
		}))
	}
}));

vi.mock('$lib/config', () => ({
	getApiUrl: (endpoint) => `/creator${endpoint}`
}));

vi.mock('@lamb/ui', async () => {
	const { readable } = await import('svelte/store');
	return {
		user: {
			subscribe: vi.fn((fn) => {
				fn({ isLoggedIn: true, token: 'test-token' });
				return vi.fn();
			})
		},
		_: readable((key, opts) => opts?.default || key),
		locale: readable('en'),
		waitLocale: vi.fn().mockResolvedValue(undefined),
		setupI18n: vi.fn()
	};
});

import { apiAxios as axios } from '$lib/services/apiClient';

describe('CostManagementPanel', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows loading state initially then renders summary cards', async () => {
		axios.get.mockResolvedValueOnce({
			data: {
				assistants: [
					{
						id: 1,
						name: 'Test Bot',
						owner: 'alice@test.com',
						organization_name: 'MIT',
						model_name: 'gpt-4o',
						cost_usd: 1.2345,
						total_tokens: 5000,
						prompt_tokens: 3000,
						completion_tokens: 2000,
						quota_enabled: false,
						quota_exceeded: false,
						cost_limit_usd: null,
						alert_thresholds: []
					}
				]
			}
		});

		const { getAllByText, getByText } = render(CostManagementPanel);

		await waitFor(() => {
			expect(getByText('Test Bot')).toBeInTheDocument();
			expect(getAllByText('$1.2345').length).toBeGreaterThanOrEqual(1);
		});
	});

	it('shows error state when fetch fails', async () => {
		axios.get.mockRejectedValueOnce(new Error('Network error'));

		const { getByText } = render(CostManagementPanel);

		await waitFor(() => {
			expect(getByText('Network error')).toBeInTheDocument();
		});
	});

	it('filters table rows when typing in search input', async () => {
		axios.get.mockResolvedValueOnce({
			data: {
				assistants: [
					{
						id: 1, name: 'Math Tutor', owner: 'alice@test.com', organization_name: 'MIT',
						model_name: 'gpt-4o', cost_usd: 1.0, total_tokens: 1000, prompt_tokens: 600,
						completion_tokens: 400, quota_enabled: false, quota_exceeded: false,
						cost_limit_usd: null, alert_thresholds: []
					},
					{
						id: 2, name: 'History Bot', owner: 'bob@test.com', organization_name: 'Stanford',
						model_name: 'gpt-3.5', cost_usd: 2.0, total_tokens: 2000, prompt_tokens: 1200,
						completion_tokens: 800, quota_enabled: false, quota_exceeded: false,
						cost_limit_usd: null, alert_thresholds: []
					}
				]
			}
		});

		const { getByText, queryByText, getByPlaceholderText } = render(CostManagementPanel);

		await waitFor(() => {
			expect(getByText('Math Tutor')).toBeInTheDocument();
			expect(getByText('History Bot')).toBeInTheDocument();
		});

		const searchInput = getByPlaceholderText(/Search by assistant name/i);
		await fireEvent.input(searchInput, { target: { value: 'Math' } });

		await waitFor(() => {
			expect(getByText('Math Tutor')).toBeInTheDocument();
			expect(queryByText('History Bot')).not.toBeInTheDocument();
		});
	});
});
