import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, waitFor } from '@testing-library/svelte';
import AssistantUsageBreakdown from './AssistantUsageBreakdown.svelte';

vi.mock('$lib/services/adminService', () => ({
	fetchAssistantUsageByModel: vi.fn()
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

import { fetchAssistantUsageByModel } from '$lib/services/adminService';

describe('AssistantUsageBreakdown', () => {
	beforeEach(() => vi.clearAllMocks());

	it('renders three prompt bucket columns', async () => {
		fetchAssistantUsageByModel.mockResolvedValueOnce({
			assistant_id: 1,
			breakdown: [
				{
					provider: 'openai', model_name: 'qwen3.6-plus',
					prompt_tokens: 19156, non_cached_prompt_tokens: 958,
					cache_read_tokens: 0, cache_write_tokens: 18198,
					completion_tokens: 957, total_tokens: 20113,
					cost_usd: 0.02, request_count: 1,
					pricing: { input_per_1m: 0.80, cache_read_per_1m: 0.16, cache_write_per_1m: 1.00, output_per_1m: 2.00, requires_explicit_cache: true }
				}
			]
		});

		const { getByText } = render(AssistantUsageBreakdown, { props: { assistantId: 1 } });
		await waitFor(() => {
			expect(getByText('qwen3.6-plus')).toBeInTheDocument();
			expect(getByText('958')).toBeInTheDocument();
			expect(getByText('18,198')).toBeInTheDocument();
		});
	});

	it('does not render the pricing recalculation disclaimer', async () => {
		fetchAssistantUsageByModel.mockResolvedValueOnce({
			assistant_id: 1,
			breakdown: [
				{
					provider: 'openai', model_name: 'gpt-4o',
					prompt_tokens: 1000, non_cached_prompt_tokens: 200,
					cache_read_tokens: 800, cache_write_tokens: 0,
					completion_tokens: 500, total_tokens: 1500,
					cost_usd: 0.01, request_count: 1,
					pricing: { input_per_1m: 2.5, cache_read_per_1m: 1.25, cache_write_per_1m: null, output_per_1m: 10.0, requires_explicit_cache: false }
				}
			]
		});

		const { queryByText } = render(AssistantUsageBreakdown, { props: { assistantId: 1 } });
		await waitFor(() => {
			expect(queryByText(/recalculated/i)).not.toBeInTheDocument();
		});
	});

	it('shows error state on fetch failure', async () => {
		fetchAssistantUsageByModel.mockRejectedValueOnce(new Error('Server error'));
		const { getByText } = render(AssistantUsageBreakdown, { props: { assistantId: 1 } });
		await waitFor(() => {
			expect(getByText(/Server error/)).toBeInTheDocument();
		});
	});
});
