<script>
	import { onMount } from 'svelte';
	import { _ } from '@lamb/ui';
	import { Button } from '$lib/components/ui';
	import { RefreshCw } from '$lib/components/ui/icons';
	import { fetchAssistantUsageByModel } from '$lib/services/adminService';
	import { user } from '@lamb/ui';

	let { assistantId } = $props();

	let breakdown = $state([]);
	let isLoading = $state(true);
	let error = $state(null);

	async function loadBreakdown() {
		isLoading = true;
		error = null;
		try {
			const data = await fetchAssistantUsageByModel(assistantId);
			breakdown = data.breakdown || [];
		} catch (e) {
			error = e?.message || 'Unknown error';
		} finally {
			isLoading = false;
		}
	}

	onMount(loadBreakdown);
</script>

<div class="mt-2 p-4 bg-surface-secondary rounded-lg border border-border">
	{#if isLoading}
		<p class="text-sm text-muted">{$_('admin.costManagement.breakdown.loading', { default: 'Loading breakdown...' })}</p>
	{:else if error}
		<div class="flex items-center gap-2">
			<p class="text-sm text-danger">{error}</p>
			<Button variant="secondary" size="sm" iconLeftComponent={RefreshCw} onclick={loadBreakdown}>
				{$_('admin.costManagement.retry', { default: 'Retry' })}
			</Button>
		</div>
	{:else if breakdown.length === 0}
		<p class="text-sm text-muted">{$_('admin.costManagement.breakdown.empty', { default: 'No usage data for this assistant.' })}</p>
	{:else}
		<table class="w-full text-sm">
			<thead>
				<tr class="text-left text-muted border-b border-border">
					<th class="pb-1 pr-3">{$_('admin.costManagement.breakdown.provider', { default: 'Provider' })}</th>
					<th class="pb-1 pr-3">{$_('admin.costManagement.breakdown.model', { default: 'Model' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.breakdown.requests', { default: 'Requests' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.table.promptTokens', { default: 'Prompt Tokens' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.breakdown.nonCachedPrompt', { default: 'Non-cached' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.breakdown.cacheRead', { default: 'Cache read' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.breakdown.cacheWrite', { default: 'Cache write' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.table.completionTokens', { default: 'Completion' })}</th>
					<th class="pb-1 pr-3 text-right">{$_('admin.costManagement.table.cost', { default: 'Cost' })}</th>
				</tr>
			</thead>
			<tbody>
				{#each breakdown as row}
					<tr class="border-b border-border/50">
						<td class="py-1.5 pr-3">{row.provider}</td>
						<td class="py-1.5 pr-3 font-medium">{row.model_name}</td>
						<td class="py-1.5 pr-3 text-right">{row.request_count}</td>
						<td class="py-1.5 pr-3 text-right">{row.prompt_tokens.toLocaleString()}</td>
						<td class="py-1.5 pr-3 text-right">{row.non_cached_prompt_tokens.toLocaleString()}</td>
						<td class="py-1.5 pr-3 text-right">{row.cache_read_tokens.toLocaleString()}</td>
						<td class="py-1.5 pr-3 text-right">{row.cache_write_tokens.toLocaleString()}</td>
						<td class="py-1.5 pr-3 text-right">{row.completion_tokens.toLocaleString()}</td>
						<td class="py-1.5 pr-3 text-right">${row.cost_usd.toFixed(4)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="text-xs text-muted mt-2">
			{$_('admin.costManagement.breakdown.identityNote', { default: 'Prompt = non-cached + cache read + cache write' })}
		</p>
	{/if}
</div>
