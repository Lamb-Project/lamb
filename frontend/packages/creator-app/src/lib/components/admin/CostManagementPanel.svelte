<script>
	import { onMount, onDestroy } from 'svelte';
	import { _ } from '@lamb/ui';
	import { apiAxios as axios } from '$lib/services/apiClient';
	import { getApiUrl } from '$lib/config';
	import { user } from '@lamb/ui';
	import {
		filterCostData,
		computeCostTotals,
		validateQuotaLimit,
		parseQuotaLimit,
		validateAlertThresholds,
		parseAlertThresholds
	} from '$lib/utils/costManagementHelpers';
	import AssistantUsageBreakdown from './AssistantUsageBreakdown.svelte';
	import OrganizationFilterModal from './OrganizationFilterModal.svelte';
	import ModelPricingModal from './ModelPricingModal.svelte';
	import { fetchCostSummaryByOrg } from '$lib/services/adminService';
	import { toast } from '$lib/stores/toast';

	let { localeLoaded = true } = $props();

	/** @type {Array<any>} */
	let costData = $state([]);
	let isLoadingCostData = $state(false);
	/** @type {string | null} */
	let costDataError = $state(null);
	let costSearch = $state('');

	let expandedAssistantId = $state(null);

	function toggleBreakdown(assistantId) {
		expandedAssistantId = expandedAssistantId === assistantId ? null : assistantId;
	}

	let showOrgFilterModal = $state(false);
	let showPricingModal = $state(false);
	let orgFilterActive = $state(false);
	let orgFilterName = $state('');
	let orgFilterId = $state(null);
	let orgSummary = $state(null);

	let tableData = $derived(
		orgFilterActive && orgFilterId
			? costData.filter((a) => a.organization_id === orgFilterId)
			: costData
	);

	let displayData = $derived(filterCostData(tableData, costSearch));
	let filteredCostData = $derived(filterCostData(costData, costSearch));
	let costTotals = $derived(computeCostTotals(costData));

	/** @type {object | null} */
	let serverSummary = $state(null);

	// Replace the activeSummary block from Step 5.6 with this updated version
	let activeSummary = $derived(
		orgFilterActive
			? (orgSummary ?? { total_cost_usd: 0, total_tokens: 0, prompt_tokens: 0, completion_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, assistant_count: 0, quota_exceeded_count: 0 })
			: serverSummary || {
				total_cost_usd: costTotals.total_cost,
				total_tokens: costTotals.total_tokens,
				prompt_tokens: costTotals.prompt_tokens,
				completion_tokens: costTotals.completion_tokens,
				cache_read_tokens: costTotals.cache_read_tokens ?? 0,
				cache_write_tokens: costTotals.cache_write_tokens ?? 0,
				assistant_count: costData.length,
				quota_exceeded_count: costData.filter(a => a.quota_exceeded).length
			}
	);

	async function handleOrgApply(org) {
		orgFilterId = org.id;
		orgFilterName = org.name;
		orgFilterActive = true;
		showOrgFilterModal = false;
		try {
			const resp = await fetchCostSummaryByOrg(org.id);
			orgSummary = resp.summary;
		} catch (e) {
			console.error('Failed to fetch org summary:', e);
			toast.error('Failed to load organization summary');
			clearOrgFilter();
		}
	}

	function clearOrgFilter() {
		orgFilterActive = false;
		orgFilterId = null;
		orgFilterName = '';
		orgSummary = null;
	}

	// --- Quota Edit Modal State ---
	/** @type {any | null} */
	let quotaEditAssistant = $state(null);
	let quotaEditEnabled = $state(false);
	let quotaEditLimitStr = $state('');
	let quotaEditAlertThresholdsStr = $state('');
	let isSavingQuota = $state(false);
	/** @type {string | null} */
	let quotaSaveError = $state(null);
	/** @type {string | null} */
	let quotaSaveSuccess = $state(null);

	function getAuthToken() {
		const userData = $user;
		if (!userData.isLoggedIn || !userData.token) {
			console.error('No authentication token available. User must be logged in.');
			return null;
		}
		return userData.token;
	}

	async function fetchCostData() {
		if (isLoadingCostData) return;
		isLoadingCostData = true;
		costDataError = null;
		try {
			const token = getAuthToken();
			if (!token) throw new Error('Authentication token not found.');
			const response = await axios.get(getApiUrl('/admin/cost-overview'), {
				headers: { Authorization: `Bearer ${token}` }
			});
			costData = response.data?.assistants || [];
			serverSummary = response.data?.summary || null;
		} catch (err) {
			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				costDataError = err.response.data.detail;
			} else if (err instanceof Error) {
				costDataError = err.message;
			} else {
				costDataError = 'Failed to load cost data.';
			}
			costData = [];
		} finally {
			isLoadingCostData = false;
		}
	}

	/** @param {any} assistant */
	function openQuotaEditModal(assistant) {
		quotaEditAssistant = assistant;
		quotaEditEnabled = !!assistant.quota_enabled;
		quotaEditLimitStr = assistant.cost_limit_usd != null ? String(assistant.cost_limit_usd) : '';
		const thresholds = assistant.alert_thresholds || [];
		quotaEditAlertThresholdsStr = thresholds.length > 0 ? thresholds.join(', ') : '';
		quotaSaveError = null;
		quotaSaveSuccess = null;
	}

	function closeQuotaEditModal() {
		quotaEditAssistant = null;
		quotaSaveError = null;
		quotaSaveSuccess = null;
	}

	async function saveQuota() {
		if (!quotaEditAssistant) return;
		isSavingQuota = true;
		quotaSaveError = null;
		quotaSaveSuccess = null;
		try {
			const token = getAuthToken();
			if (!token) throw new Error('Authentication token not found.');

			const limitError = validateQuotaLimit(quotaEditLimitStr);
			if (limitError) {
				quotaSaveError = limitError;
				return;
			}
			const cost_limit_usd = parseQuotaLimit(quotaEditLimitStr);

			const thresholdsError = validateAlertThresholds(quotaEditAlertThresholdsStr);
			if (thresholdsError) {
				quotaSaveError = thresholdsError;
				return;
			}
			const alert_thresholds = parseAlertThresholds(quotaEditAlertThresholdsStr);

			const response = await axios.put(
				getApiUrl(`/admin/assistant/${quotaEditAssistant.id}/quota`),
				{ enabled: quotaEditEnabled, cost_limit_usd, alert_thresholds },
				{ headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } }
			);
			const updated = response.data;
			costData = costData.map((a) =>
				a.id === quotaEditAssistant.id
					? {
							...a,
							quota_enabled: updated.quota.enabled,
							cost_limit_usd: updated.quota.cost_limit_usd,
							alert_thresholds: updated.quota.alert_thresholds || [],
							quota_exceeded: updated.quota_exceeded
						}
					: a
			);
			quotaSaveSuccess = 'Quota saved successfully.';
			setTimeout(() => {
				closeQuotaEditModal();
			}, 1200);
		} catch (err) {
			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				quotaSaveError = err.response.data.detail;
			} else if (err instanceof Error) {
				quotaSaveError = err.message;
			} else {
				quotaSaveError = 'Failed to save quota.';
			}
		} finally {
			isSavingQuota = false;
		}
	}

	function handleKeydown(event) {
		if (event.key === 'Escape' && quotaEditAssistant) {
			closeQuotaEditModal();
		}
	}

	onMount(() => {
		document.addEventListener('keydown', handleKeydown);
		fetchCostData();
	});

	onDestroy(() => {
		if (typeof document !== 'undefined') {
			document.removeEventListener('keydown', handleKeydown);
		}
	});
</script>

<!-- Header -->
<div class="mb-6 flex items-center justify-between">
	<div>
		<h1 class="text-2xl font-semibold text-gray-800">
			{localeLoaded
				? $_('admin.costManagement.title', { default: 'Cost Management' })
				: 'Cost Management'}
		</h1>
		<p class="mt-1 text-sm text-gray-500">
			{localeLoaded
				? $_('admin.costManagement.subtitle', {
						default: 'Token usage and estimated cost per assistant across the platform.'
					})
				: 'Token usage and estimated cost per assistant across the platform.'}
		</p>
	</div>
	<button
		onclick={fetchCostData}
		class="bg-brand hover:bg-brand/90 inline-flex items-center gap-2 rounded px-4 py-2 text-sm text-white transition-colors"
		disabled={isLoadingCostData}
	>
		<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
			/>
		</svg>
		{localeLoaded ? $_('admin.costManagement.retry', { default: 'Retry' }) : 'Refresh'}
	</button>
	<button
		onclick={() => showPricingModal = true}
		class="ml-2 inline-flex items-center gap-2 rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-50"
	>
		{localeLoaded ? $_('admin.costManagement.pricing.manageButton', { default: 'Manage model pricing' }) : 'Manage model pricing'}
	</button>
</div>

{#if isLoadingCostData}
	<div class="overflow-hidden rounded-lg bg-white p-8 shadow">
		<div class="flex items-center justify-center">
			<div
				class="border-brand mr-3 inline-block h-6 w-6 animate-spin rounded-full border-b-2"
			></div>
			<span class="text-gray-500"
				>{localeLoaded
					? $_('admin.costManagement.loading', { default: 'Loading usage data...' })
					: 'Loading usage data...'}</span
			>
		</div>
	</div>
{:else if costDataError}
	<div
		class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
		role="alert"
	>
		<strong class="font-bold"
			>{localeLoaded ? $_('admin.costManagement.errorTitle', { default: 'Error:' }) : 'Error:'}
		</strong>
		<span>{costDataError}</span>
		<button onclick={fetchCostData} class="ml-4 text-sm underline"
			>{localeLoaded ? $_('admin.costManagement.retry', { default: 'Retry' }) : 'Retry'}</button
		>
	</div>
{:else}
	<!-- Summary cards -->
	<div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
		<div class="rounded-lg bg-white p-4 shadow">
			<p class="mb-1 text-xs tracking-wide text-gray-500 uppercase">Total Estimated Cost</p>
			<p class="text-2xl font-bold text-gray-800">${activeSummary.total_cost_usd.toFixed(4)}</p>
		</div>
		<div class="rounded-lg bg-white p-4 shadow">
			<p class="mb-1 text-xs tracking-wide text-gray-500 uppercase">Total Tokens</p>
			<p class="text-2xl font-bold text-gray-800">{activeSummary.total_tokens.toLocaleString()}</p>
			<p class="mt-0.5 text-xs text-gray-400">
				Prompt: {activeSummary.prompt_tokens.toLocaleString()} · Completion: {activeSummary.completion_tokens.toLocaleString()}
			</p>
			<p class="text-xs text-gray-400">
				{$_('admin.costManagement.summary.cacheRead', { default: 'Cache read' })}: {(activeSummary.cache_read_tokens ?? 0).toLocaleString()} · {$_('admin.costManagement.summary.cacheWrite', { default: 'Cache write' })}: {(activeSummary.cache_write_tokens ?? 0).toLocaleString()}
			</p>
		</div>
		<div class="rounded-lg bg-white p-4 shadow">
			<p class="mb-1 text-xs tracking-wide text-gray-500 uppercase">Assistants</p>
			<p class="text-2xl font-bold text-gray-800">{activeSummary.assistant_count}</p>
			<p class="mt-0.5 text-xs text-gray-400">
				{activeSummary.quota_exceeded_count} quota exceeded
			</p>
		</div>
	</div>

	<!-- Search filter -->
	<div class="mb-4 flex items-center gap-2">
		<input
			type="text"
			bind:value={costSearch}
			placeholder="Search by assistant name, owner, organization or model..."
			class="focus:ring-brand w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:outline-none sm:w-80"
		/>
		<button
			onclick={() => showOrgFilterModal = true}
			class="whitespace-nowrap rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
		>
			{localeLoaded ? $_('admin.costManagement.filterByOrg', { default: 'Filter by organization' }) : 'Filter by organization'}
		</button>
		{#if orgFilterActive}
			<span class="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">
				{$_('admin.costManagement.filteredOrg', { default: 'Filtered: {name}' }).replace('{name}', orgFilterName)}
				<button onclick={clearOrgFilter} class="ml-1 text-blue-500 hover:text-blue-700">&times;</button>
			</span>
		{/if}
	</div>

	{#if displayData.length === 0}
		<div class="rounded-lg bg-white p-8 text-center text-gray-500 shadow">
			{costData.length === 0
				? localeLoaded
					? $_('admin.costManagement.noData', { default: 'No assistants found.' })
					: 'No assistants found.'
				: 'No assistants match your search.'}
		</div>
	{:else}
		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.assistant', { default: 'Assistant' }) : 'Assistant'}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.organization', { default: 'Organization' }) : 'Organization'}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.model', { default: 'Model' }) : 'Model'}
							</th>
							<th class="px-4 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.promptTokens', { default: 'Prompt Tokens' }) : 'Prompt Tokens'}
							</th>
							<th class="px-4 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.completionTokens', { default: 'Completion Tokens' }) : 'Completion Tokens'}
							</th>
							<th class="px-4 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.cost', { default: 'Estimated Cost' }) : 'Estimated Cost'}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.quota', { default: 'Quota' }) : 'Quota'}
							</th>
							<th class="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">
								{localeLoaded ? $_('admin.costManagement.table.status', { default: 'Status' }) : 'Status'}
							</th>
							<th class="px-4 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase">
								Actions
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 bg-white">
						{#each displayData as assistant (assistant.id)}
							<tr
								class="cursor-pointer hover:bg-blue-50 {assistant.quota_exceeded ? 'bg-red-50 hover:bg-red-100' : ''}"
								onclick={() => openQuotaEditModal(assistant)}
								title="Click to edit quota"
							>
								<td class="px-4 py-3">
									<div class="font-medium text-gray-900">{assistant.name}</div>
									<div class="text-xs text-gray-400">{assistant.owner}</div>
								</td>
								<td class="px-4 py-3 text-gray-600">{assistant.organization_name || '—'}</td>
								<td class="px-4 py-3">
									{#if assistant.model_name}
										<span class="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">{assistant.model_name}</span>
									{:else}
										<span class="text-gray-400">—</span>
									{/if}
								</td>
								<td class="px-4 py-3 text-right text-gray-600 tabular-nums">{assistant.prompt_tokens.toLocaleString()}</td>
								<td class="px-4 py-3 text-right text-gray-600 tabular-nums">{assistant.completion_tokens.toLocaleString()}</td>
								<td class="px-4 py-3 text-right font-medium tabular-nums {assistant.cost_usd > 0 ? 'text-gray-800' : 'text-gray-400'}">
									${assistant.cost_usd.toFixed(4)}
								</td>
								<td class="px-4 py-3">
									{#if !assistant.quota_enabled}
										<span class="text-xs text-gray-400">{localeLoaded ? $_('admin.costManagement.quota.noQuota', { default: 'No quota' }) : 'No quota'}</span>
									{:else if assistant.cost_limit_usd != null}
										{@const tablePct = (assistant.cost_usd / assistant.cost_limit_usd) * 100}
										{@const hasAlert = assistant.alert_thresholds && assistant.alert_thresholds.some((t) => t <= tablePct)}
										<span class="text-xs text-gray-600">${assistant.cost_limit_usd.toFixed(2)}</span>
										<div class="mt-1 h-1.5 w-full rounded-full bg-gray-200">
											<div
												class="h-1.5 rounded-full {assistant.quota_exceeded ? 'bg-red-500' : hasAlert ? 'bg-yellow-400' : 'bg-green-500'}"
												style="width: {Math.min(100, tablePct).toFixed(1)}%"
											></div>
										</div>
										<div class="mt-0.5 text-xs text-gray-400">
											{((assistant.cost_usd / assistant.cost_limit_usd) * 100).toFixed(1)}% used
										</div>
									{/if}
								</td>
								<td class="px-4 py-3">
									{#if assistant.quota_exceeded}
										<span class="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
											{localeLoaded ? $_('admin.costManagement.quota.exceeded', { default: 'Exceeded' }) : 'Exceeded'}
										</span>
									{:else if assistant.quota_enabled}
										<span class="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
											{localeLoaded ? $_('admin.costManagement.quota.active', { default: 'Active' }) : 'Active'}
										</span>
									{:else}
										<span class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
											{localeLoaded ? $_('admin.costManagement.quota.disabled', { default: 'Disabled' }) : 'No quota'}
										</span>
									{/if}
								</td>
								<td class="px-4 py-3 text-right">
									<button
										onclick={(e) => { e.stopPropagation(); toggleBreakdown(assistant.id); }}
										class="text-xs text-blue-600 hover:text-blue-800"
									>
										{expandedAssistantId === assistant.id
											? (localeLoaded ? $_('admin.costManagement.lessDetails', { default: 'Less details' }) : 'Less details')
											: (localeLoaded ? $_('admin.costManagement.moreDetails', { default: 'More details' }) : 'More details')
										}
									</button>
								</td>
							</tr>
							{#if expandedAssistantId === assistant.id}
								<tr>
									<td colspan="9" class="p-0">
										<AssistantUsageBreakdown assistantId={assistant.id} />
									</td>
								</tr>
							{/if}
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
{/if}

<!-- Organization Filter Modal -->
{#if showOrgFilterModal}
	<OrganizationFilterModal onApply={handleOrgApply} onClose={() => showOrgFilterModal = false} />
{/if}

<!-- Model Pricing Modal -->
{#if showPricingModal}
	<ModelPricingModal onClose={() => showPricingModal = false} />
{/if}

<!-- Quota Edit Modal -->
{#if quotaEditAssistant}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
		role="dialog"
		aria-modal="true"
	>
		<div class="relative mx-auto w-full max-w-md rounded-md border bg-white p-6 shadow-lg">
			<!-- Header -->
			<div class="mb-4 flex items-start justify-between">
				<div>
					<h3 class="text-lg font-medium text-gray-900">Quota Settings</h3>
					<p class="mt-0.5 text-sm break-all text-gray-500">{quotaEditAssistant.name}</p>
				</div>
				<button
					onclick={closeQuotaEditModal}
					class="ml-4 flex-shrink-0 text-gray-400 transition-colors hover:text-gray-600"
					aria-label="Close"
				>
					<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<!-- Current spend info -->
			<div class="mb-5 grid grid-cols-2 gap-3 rounded-md bg-gray-50 px-4 py-3 text-sm">
				<div>
					<div class="mb-0.5 text-xs tracking-wide text-gray-400 uppercase">Current spend</div>
					<div class="font-semibold text-gray-800">${quotaEditAssistant.cost_usd.toFixed(4)}</div>
				</div>
				<div>
					<div class="mb-0.5 text-xs tracking-wide text-gray-400 uppercase">Total tokens</div>
					<div class="font-semibold text-gray-800">
						{quotaEditAssistant.total_tokens.toLocaleString()}
					</div>
				</div>
				{#if quotaEditAssistant.model_name}
					<div class="col-span-2">
						<div class="mb-0.5 text-xs tracking-wide text-gray-400 uppercase">Model</div>
						<div class="text-gray-700">{quotaEditAssistant.model_name}</div>
					</div>
				{/if}
			</div>

			<!-- Form -->
			<form
				onsubmit={(e) => {
					e.preventDefault();
					saveQuota();
				}}
			>
				<!-- Enable toggle -->
				<div class="mb-5 flex items-center justify-between">
					<div>
						<label for="quota-enabled" class="text-sm font-medium text-gray-700">Enable quota enforcement</label>
						<p class="mt-0.5 text-xs text-gray-400">
							When enabled, completions are blocked once the limit is reached.
						</p>
					</div>
					<button
						type="button"
						id="quota-enabled"
						role="switch"
						aria-checked={quotaEditEnabled}
						onclick={() => { quotaEditEnabled = !quotaEditEnabled; }}
						class="focus:ring-brand relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:ring-2 focus:ring-offset-2 focus:outline-none {quotaEditEnabled ? 'bg-brand' : 'bg-gray-200'}"
					>
						<span class="sr-only">Enable quota</span>
						<span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {quotaEditEnabled ? 'translate-x-5' : 'translate-x-0'}"></span>
					</button>
				</div>

				<!-- Cost limit input -->
				<div class="mb-5">
					<label for="quota-limit" class="mb-1 block text-sm font-medium text-gray-700">
						Cost limit (USD)
						<span class="font-normal text-gray-400">— leave blank for unlimited</span>
					</label>
					<div class="relative">
						<span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-sm text-gray-400">$</span>
						<input
							type="number"
							id="quota-limit"
							min="0"
							step="0.01"
							placeholder="e.g. 5.00"
							bind:value={quotaEditLimitStr}
							disabled={!quotaEditEnabled}
							class="focus:ring-brand block w-full rounded-md border border-gray-300 py-2 pr-3 pl-7 text-sm focus:ring-2 focus:outline-none disabled:bg-gray-50 disabled:text-gray-400"
						/>
					</div>
					{#if quotaEditEnabled && quotaEditLimitStr && quotaEditAssistant.cost_usd > 0}
						{@const limit = parseFloat(quotaEditLimitStr)}
						{#if !isNaN(limit) && limit > 0}
							{@const currentPct = (quotaEditAssistant.cost_usd / limit) * 100}
							{@const breakpoints = quotaEditAlertThresholdsStr
								.split(',')
								.map((s) => parseFloat(s.trim()))
								.filter((p) => !isNaN(p))}
							{@const breached = breakpoints
								.filter((p) => p <= currentPct)
								.sort((a, b) => b - a)[0]}
							<div class="mt-2">
								<div class="mb-1 flex h-1.5 w-full rounded-full bg-gray-200">
									<div
										class="h-1.5 rounded-full {quotaEditAssistant.cost_usd >= limit ? 'bg-red-500' : breached ? 'bg-yellow-400' : 'bg-green-500'}"
										style="width: {Math.min(100, currentPct).toFixed(1)}%"
									></div>
								</div>
								<div class="mt-1 flex items-center justify-between text-xs">
									<span class="text-gray-400">{currentPct.toFixed(1)}% of limit used</span>
									{#if quotaEditAssistant.cost_usd >= limit}
										<span class="flex items-center font-medium text-red-600">
											<svg class="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
											</svg>
											Limit exceeded
										</span>
									{:else if breached}
										<span class="flex items-center rounded bg-yellow-50 px-1.5 py-0.5 font-medium text-yellow-600">
											<svg class="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
											</svg>
											Threshold {breached}% reached
										</span>
									{/if}
								</div>
							</div>
						{/if}
					{/if}
				</div>

				<!-- Alert Thresholds input -->
				<div class="mb-5">
					<label for="quota-alerts" class="mb-1 block text-sm font-medium text-gray-700">
						Alert thresholds (%)
						<span class="font-normal text-gray-400">— comma separated percentages</span>
					</label>
					<div class="relative">
						<span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-sm text-gray-400">
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-4 w-4">
								<path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
							</svg>
						</span>
						<input
							type="text"
							id="quota-alerts"
							placeholder="e.g. 50, 80"
							bind:value={quotaEditAlertThresholdsStr}
							class="focus:ring-brand block w-full rounded-md border border-gray-300 py-2 pr-3 pl-9 text-sm focus:ring-2 focus:outline-none"
						/>
					</div>
					<p class="mt-1 text-xs text-gray-400">
						Receive notifications when usage reaches these percentages of the cost limit.
					</p>
				</div>

				<!-- Feedback messages -->
				{#if quotaSaveError}
					<div class="mb-4 rounded border border-red-400 bg-red-100 px-3 py-2 text-sm text-red-700">
						{quotaSaveError}
					</div>
				{/if}
				{#if quotaSaveSuccess}
					<div class="mb-4 rounded border border-green-400 bg-green-100 px-3 py-2 text-sm text-green-700">
						{quotaSaveSuccess}
					</div>
				{/if}

				<!-- Actions -->
				<div class="flex justify-end gap-3">
					<button
						type="button"
						onclick={closeQuotaEditModal}
						class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
						disabled={isSavingQuota}
					>
						Cancel
					</button>
					<button
						type="submit"
						class="bg-brand hover:bg-brand/90 inline-flex items-center gap-2 rounded-md border border-transparent px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-60"
						disabled={isSavingQuota}
					>
						{#if isSavingQuota}
							<svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
							</svg>
							Saving...
						{:else}
							Save quota
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
