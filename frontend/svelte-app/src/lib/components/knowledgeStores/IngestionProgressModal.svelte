<!--
  @component IngestionProgressModal
  Shows live ingestion status for items just added to a Knowledge Store.
  Fetches all statuses immediately on open, then polls every 4 s for
  anything still in-flight — same interval as KSDetail.

  Phase C consistency contract:
    * Canonical `<Modal size="md">`.
    * Top progress strip showing "{completedCount} of {total} items
      ingested" + ETA (heuristic until ≥1 completes, then derived).
    * Status badges via shared `statusBadgeProps`.
    * Failed items expose a `<IconButton icon={RefreshCw}>` retry — the
      backend endpoint is not implemented yet, so the stub surfaces a
      `toast.info("Coming soon.")`.
    * Footer: ghost "Close" or "Run in background" + primary "View
      Knowledge Store". "Run in background" fires a `toast.info`.
    * Polling continues after close so the parent list can show a
      "ingesting" hint badge next to the row.
-->
<script>
	import { onDestroy } from 'svelte';
	import { base } from '$app/paths';
	import { getContentLinkStatus, retryIngestion } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import { toast } from '$lib/stores/toast.js';
	import { statusBadgeProps } from '$lib/utils/statusBadge.js';
	import { Modal, Banner, Button, IconButton, Badge } from '$lib/components/ui';
	import { ArrowRight, RefreshCw, FileText } from '$lib/components/ui/icons.js';

	/**
	 * @type {{
	 *   isOpen: boolean,
	 *   ksId: string,
	 *   ksName: string,
	 *   items: Array<{ id: string, title: string }>,
	 *   onclose?: () => void,
	 *   onprogress?: (progress: { ingesting: number, completed: number, total: number }) => void
	 * }}
	 */
	let { isOpen = $bindable(false), ksId, ksName, items = [], onclose, onprogress } = $props();

	/** @type {Record<string, { status: string, chunks?: number, error?: string }>} */
	let statuses = $state({});
	/** @type {ReturnType<typeof setTimeout>|null} */
	let pollTimer = null;
	/** Monotonic clock value at first poll start — used to derive ETA. */
	let startedAt = $state(0);

	$effect(() => {
		if (isOpen && items.length) {
			// Seed first poll with cached statuses so the modal isn't blank
			// for the first 4 seconds. AddContentToKSModal passes items
			// already queued, so 'processing' is a fair default — the real
			// status arrives within the first fetchAll().
			statuses = Object.fromEntries(items.map((i) => [i.id, { status: 'processing' }]));
			startedAt = Date.now();
			fetchAll();
		}
		return () => {
			if (pollTimer) {
				clearTimeout(pollTimer);
				pollTimer = null;
			}
		};
	});

	async function fetchAll() {
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
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
		notifyProgress();
		schedulePoll();
	}

	function schedulePoll() {
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
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
			notifyProgress();
			schedulePoll();
		}, 4000);
	}

	function notifyProgress() {
		if (typeof onprogress !== 'function') return;
		onprogress({
			ingesting: items.filter(
				(i) => statuses[i.id]?.status === 'pending' || statuses[i.id]?.status === 'processing'
			).length,
			completed: completedCount,
			total: items.length
		});
	}

	let completedCount = $derived(
		items.filter((i) => {
			const s = statuses[i.id]?.status;
			return s === 'ready' || s === 'failed';
		}).length
	);

	let allDone = $derived(items.length > 0 && completedCount === items.length);

	let progressPct = $derived(
		items.length === 0 ? 0 : Math.round((completedCount / items.length) * 100)
	);

	// ETA heuristic: until at least one item completes, show "~1–2 min per
	// item"; after that, derive from the average elapsed time per completion.
	let etaLabel = $derived.by(() => {
		if (allDone) return '';
		const total = items.length;
		const remaining = total - completedCount;
		if (remaining <= 0) return '';
		if (completedCount === 0) {
			return $_('knowledgeStores.ingestionProgress.etaHeuristic', {
				default: '~1–2 min per item'
			});
		}
		const elapsed = Date.now() - startedAt;
		const avgPerItem = elapsed / Math.max(completedCount, 1);
		const estimatedMs = avgPerItem * remaining;
		const seconds = Math.round(estimatedMs / 1000);
		if (seconds < 60) {
			return $_('knowledgeStores.ingestionProgress.etaSeconds', {
				default: '~{n}s remaining',
				values: { n: seconds }
			});
		}
		const minutes = Math.round(seconds / 60);
		return $_('knowledgeStores.ingestionProgress.etaMinutes', {
			default: '~{n} min remaining',
			values: { n: minutes }
		});
	});

	function close() {
		// Stop polling locally — the parent list will refresh once when the
		// modal closes (via onclose). We don't want a background poll loop
		// after the user dismisses the modal.
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
		isOpen = false;
		onclose?.();
	}

	function closeRunInBackground() {
		toast.info(
			$_('knowledgeStores.ingestionProgress.backgroundToast', {
				default:
					'Ingestion continues in the background. Track progress on the Knowledge Store page.'
			})
		);
		close();
	}

	/** @param {string} itemId */
	async function handleRetry(itemId) {
		try {
			await retryIngestion(ksId, itemId);
			// Optimistic: flip back to processing so the spinner returns.
			statuses[itemId] = { ...statuses[itemId], status: 'processing' };
			schedulePoll();
			toast.success(
				$_('knowledgeStores.ingestionProgress.retryQueued', {
					default: 'Retry queued.'
				})
			);
		} catch (/** @type {any} */ err) {
			if (err?.code === 'not_implemented') {
				toast.info(
					$_('knowledgeStores.ingestionProgress.retryComingSoon', {
						default: 'Retry feature coming soon.'
					})
				);
				return;
			}
			toast.error(err?.message || 'Retry failed.');
		}
	}

	onDestroy(() => {
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
	});
</script>

<Modal
	open={isOpen}
	onclose={close}
	size="md"
	title={allDone
		? $_('knowledgeStores.ingestionProgress.done', { default: 'Ingestion complete' })
		: $_('knowledgeStores.ingestionProgress.processing', { default: 'Processing content…' })}
	closeAriaLabel={$_('common.close', { default: 'Close' })}
>
	<!-- eslint-disable-next-line svelte/no-useless-children-snippet -->
	{#snippet children()}
		<p class="type-caption mb-3">{ksName}</p>

		<!-- Top progress strip. Stays visible while polling so the user can
		     always see "N of M" + ETA. -->
		<div class="border-border bg-surface-muted -mx-6 mb-4 border-y px-6 py-3">
			<div class="text-text-muted mb-1 flex items-center justify-between text-xs">
				<span>
					{completedCount}
					{$_('knowledgeStores.ingestionProgress.ofConnector', { default: 'of' })}
					{items.length}
					{$_('knowledgeStores.ingestionProgress.itemsIngested', { default: 'items ingested' })}
				</span>
				<span>{etaLabel}</span>
			</div>
			<div
				class="rounded-pill bg-surface-sunken h-2 w-full overflow-hidden"
				role="progressbar"
				aria-valuenow={progressPct}
				aria-valuemin="0"
				aria-valuemax="100"
			>
				<div class="bg-brand h-full transition-all" style="width: {progressPct}%"></div>
			</div>
		</div>

		<ul class="divide-border max-h-72 divide-y overflow-y-auto">
			{#each items as item (item.id)}
				{@const st = statuses[item.id] ?? { status: 'processing' }}
				{@const badge = statusBadgeProps(st.status)}
				<li class="py-2.5 text-sm">
					<div class="flex items-center justify-between gap-3">
						<div class="flex min-w-0 items-center gap-2">
							<FileText size={14} class="text-text-muted shrink-0" aria-hidden="true" />
							<span class="text-text min-w-0 truncate" title={item.title}>{item.title}</span>
						</div>
						<div class="flex shrink-0 items-center gap-2">
							{#if st.chunks != null && st.status === 'ready'}
								<span class="text-text-muted text-xs">{st.chunks} chunks</span>
							{/if}
							<Badge variant={badge.variant} icon={badge.icon} spin={badge.spin}>
								{badge.label}
							</Badge>
							{#if st.status === 'failed'}
								<IconButton
									icon={RefreshCw}
									ariaLabel={$_('knowledgeStores.ingestionProgress.retry', {
										default: 'Retry ingestion'
									})}
									tooltip={$_('knowledgeStores.ingestionProgress.retry', {
										default: 'Retry ingestion'
									})}
									variant="ghost"
									size="sm"
									inModal
									onclick={() => handleRetry(item.id)}
								/>
							{/if}
						</div>
					</div>
					{#if st.error}
						<Banner variant="danger" size="sm" class="mt-1" description={st.error} />
					{/if}
				</li>
			{/each}
		</ul>
	{/snippet}

	{#snippet footer()}
		<!-- footer is flex-row-reverse — primary first lands on the right. -->
		<Button
			variant="primary"
			iconRightComponent={ArrowRight}
			href={`${base}/libraries?section=knowledge-stores&view=detail&id=${ksId}`}
			onclick={close}
		>
			{$_('knowledgeStores.ingestionProgress.viewKs', { default: 'View Knowledge Store' })}
		</Button>
		<Button variant="ghost" onclick={allDone ? close : closeRunInBackground}>
			{allDone
				? $_('common.close', { default: 'Close' })
				: $_('knowledgeStores.ingestionProgress.runInBackground', {
						default: 'Run in background'
					})}
		</Button>
	{/snippet}
</Modal>
