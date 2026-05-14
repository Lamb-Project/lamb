<!--
  @component IngestionProgressModal
  Shows live ingestion status for items just added to a Knowledge Store.
  Fetches all statuses immediately on open, then polls every 4 s for
  anything still in-flight — same interval as KSDetail.
-->
<script>
	import { onDestroy } from 'svelte';
	import { base } from '$app/paths';
	import { getContentLinkStatus } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';

	/**
	 * @type {{
	 *   isOpen: boolean,
	 *   ksId: string,
	 *   ksName: string,
	 *   items: Array<{ id: string, title: string }>,
	 *   onclose?: () => void
	 * }}
	 */
	let { isOpen = $bindable(false), ksId, ksName, items = [], onclose } = $props();

	/** @type {Record<string, { status: string, chunks?: number, error?: string }>} */
	let statuses = $state({});
	let pollTimer = null;

	$effect(() => {
		if (isOpen && items.length) {
			statuses = Object.fromEntries(items.map((i) => [i.id, { status: 'processing' }]));
			fetchAll();
		}
		return () => {
			if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
		};
	});

	async function fetchAll() {
		if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
		await Promise.all(
			items.map(async (item) => {
				try {
					const link = await getContentLinkStatus(ksId, item.id);
					statuses[item.id] = {
						status: link.status ?? 'processing',
						chunks: link.chunks_created ?? undefined,
						error: link.error_message ?? undefined
					};
				} catch {
					// keep last known status
				}
			})
		);
		schedulePoll();
	}

	function schedulePoll() {
		if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
		const inFlight = items.filter(
			(i) => statuses[i.id]?.status === 'pending' || statuses[i.id]?.status === 'processing'
		);
		if (inFlight.length === 0) return;
		pollTimer = setTimeout(async () => {
			await Promise.all(
				inFlight.map(async (item) => {
					try {
						const link = await getContentLinkStatus(ksId, item.id);
						statuses[item.id] = {
							status: link.status ?? 'processing',
							chunks: link.chunks_created ?? undefined,
							error: link.error_message ?? undefined
						};
					} catch {
						// keep last known status
					}
				})
			);
			schedulePoll();
		}, 4000);
	}

	let allDone = $derived(
		items.length > 0 &&
		items.every((i) => {
			const s = statuses[i.id]?.status;
			return s === 'ready' || s === 'failed';
		})
	);

	/** @param {string} status */
	function badgeClass(status) {
		switch (status) {
			case 'ready':      return 'bg-green-100 text-green-800';
			case 'failed':     return 'bg-red-100 text-red-800';
			case 'processing': return 'bg-blue-100 text-blue-800';
			default:           return 'bg-gray-100 text-gray-700';
		}
	}

	function close() {
		if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
		isOpen = false;
		onclose?.();
	}

	onDestroy(() => {
		if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
	});
</script>

{#if isOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="ingestion-progress-title">
		<!-- Backdrop — no click-to-close; use the Close button -->
		<div class="absolute inset-0 bg-black/30"></div>

		<!-- Panel — sits above the backdrop, does not close on click -->
		<div
			class="relative mx-4 w-full max-w-lg rounded-lg bg-white shadow-2xl ring-1 ring-black/10"
		>
			<!-- Header -->
			<div class="border-b border-gray-200 px-6 py-4">
				<h2 id="ingestion-progress-title" class="flex items-center gap-2 text-base font-semibold text-gray-900">
					{#if allDone}
						<svg class="h-4 w-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
						{$_('knowledgeStores.ingestionProgress.done', { default: 'Ingestion complete' })}
					{:else}
						<svg class="h-4 w-4 animate-spin text-[#2271b3]" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
						</svg>
						{$_('knowledgeStores.ingestionProgress.processing', { default: 'Processing content…' })}
					{/if}
				</h2>
				<p class="mt-0.5 text-xs text-gray-500">{ksName}</p>
			</div>

			<!-- Item list -->
			<ul class="max-h-64 divide-y divide-gray-100 overflow-y-auto px-6 py-2">
				{#each items as item (item.id)}
					{@const st = statuses[item.id] ?? { status: 'processing' }}
					<li class="py-2.5 text-sm">
						<div class="flex items-center justify-between gap-3">
							<span class="min-w-0 truncate text-gray-800">{item.title}</span>
							<div class="flex shrink-0 items-center gap-2">
								{#if st.chunks != null && st.status === 'ready'}
									<span class="text-xs text-gray-400">{st.chunks} chunks</span>
								{/if}
								<span class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium {badgeClass(st.status)}">
									{st.status}
								</span>
							</div>
						</div>
						{#if st.error}
							<p class="mt-0.5 text-xs text-red-500">{st.error}</p>
						{/if}
					</li>
				{/each}
			</ul>

			<!-- Footer -->
			<div class="flex items-center justify-end gap-3 border-t border-gray-200 px-6 py-4">
				<button
					type="button"
					onclick={close}
					class="rounded-md px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
				>
					{$_('common.close', { default: 'Close' })}
				</button>
				<a
					href="{base}/libraries?section=knowledge-stores&view=detail&id={ksId}"
					onclick={close}
					class="rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white hover:bg-[#195a91]"
				>
					{$_('knowledgeStores.ingestionProgress.viewKs', { default: 'View Knowledge Store' })}
				</a>
			</div>
		</div>
	</div>
{/if}
