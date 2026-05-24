<!--
  @component ItemContentTabs
  Tab body for an item's content (Original / Markdown / capability tabs).
  Extracted from ItemContentModal so the new FileTreeModal preview pane
  can embed the same tab UI without re-implementing capability rendering.

  Capability content is lazy-loaded — fetched only when its tab is activated.
-->
<script>
	import { _, locale } from '$lib/i18n';
	import { renderMarkdownStrict } from '$lib/utils/sanitize';
	import { getItemCapabilities, getItemContentByCapability } from '$lib/services/libraryService';
	import { getRenderer } from '$lib/components/libraries/capabilities/index.js';
	import { Tabs, Banner, Button, EmptyState } from '$lib/components/ui';
	import { Loader2, ExternalLink, FileText } from 'lucide-svelte';

	let {
		libraryId = '',
		itemId = '',
		isLoading = false,
		content = '',
		/** @type {string|null} */
		error = null,
		sourceType = '',
		sourceUrl = '',
		originalFilename = '',
		/** @type {(() => void) | null} */
		onviewOriginal = null,
		/** Resets internal tab state when this key changes (e.g. new item). */
		resetKey = ''
	} = $props();

	let localeLoaded = $derived(!!$locale);
	let renderedHtml = $derived(content ? renderMarkdownStrict(content) : '');

	/** @type {string} */
	let activeTab = $state('original');

	/** @type {string[]} */
	let capabilities = $state([]);
	/** @type {Record<string, { mime: string, body: unknown } | null>} */
	let capabilityPayloads = $state({});
	/** @type {Record<string, string|null>} */
	let capabilityErrors = $state({});
	/** @type {Record<string, boolean>} */
	let capabilityLoading = $state({});

	async function loadCapabilities() {
		if (!libraryId || !itemId) {
			capabilities = [];
			return;
		}
		try {
			const list = await getItemCapabilities(libraryId, itemId);
			// The ``text`` capability is intentionally hidden from the tabs —
			// the static "Markdown" tab already renders the same ``full.md``
			// content with the same sanitiser. Showing both creates two
			// identical tabs and confuses users. The backend capability
			// (``GET /content/text``) and its registration are kept so
			// non-UI consumers still work.
			capabilities = Array.isArray(list)
				? list
						.map((c) => String(c).toLowerCase())
						.filter((c) => c !== 'text')
				: [];
		} catch (err) {
			console.warn('ItemContentTabs: failed to load capabilities', err);
			capabilities = [];
		}
	}

	/** @param {string} cap */
	async function ensureCapabilityLoaded(cap) {
		if (!libraryId || !itemId) return;
		if (capabilityPayloads[cap] != null) return;
		capabilityLoading = { ...capabilityLoading, [cap]: true };
		capabilityErrors = { ...capabilityErrors, [cap]: null };
		try {
			const payload = await getItemContentByCapability(libraryId, itemId, cap);
			capabilityPayloads = { ...capabilityPayloads, [cap]: payload };
		} catch (err) {
			capabilityErrors = {
				...capabilityErrors,
				[cap]: err instanceof Error ? err.message : 'Failed to load capability.'
			};
		} finally {
			capabilityLoading = { ...capabilityLoading, [cap]: false };
		}
	}

	/** @param {string} v */
	function handleTabChange(v) {
		activeTab = v;
		if (v.startsWith('cap:')) {
			ensureCapabilityLoaded(v.slice(4));
		}
	}

	/**
	 * Classify a YouTube-related error string into a bucket for hinting.
	 * @param {string|null} msg
	 * @returns {'rate_limit' | 'no_subtitles' | 'generic'}
	 */
	function classifyError(msg) {
		if (!msg) return 'generic';
		const lower = msg.toLowerCase();
		if (
			lower.includes('rate-limit') ||
			lower.includes('rate limit') ||
			lower.includes('429') ||
			lower.includes('too many requests')
		)
			return 'rate_limit';
		if (lower.includes('no subtitles') || lower.includes('subtitles available'))
			return 'no_subtitles';
		return 'generic';
	}

	let errorKind = $derived(classifyError(error));

	let tabsList = $derived(
		(() => {
			/** @type {Array<{value: string, label: string}>} */
			const t = [
				{
					value: 'original',
					label: localeLoaded
						? $_('libraries.itemContentModal.tabOriginal', { default: 'Original' })
						: 'Original'
				},
				{
					value: 'markdown',
					label: localeLoaded
						? $_('libraries.itemContentModal.tabMarkdown', { default: 'Markdown' })
						: 'Markdown'
				}
			];
			for (const cap of capabilities) {
				t.push({
					value: `cap:${cap}`,
					label: localeLoaded ? $_(`capability.${cap}`, { default: cap }) : cap
				});
			}
			return t;
		})()
	);

	$effect(() => {
		// Reset whenever the parent passes a new key (typically itemId).
		// eslint-disable-next-line no-unused-expressions
		resetKey;
		activeTab = 'original';
		capabilities = [];
		capabilityPayloads = {};
		capabilityErrors = {};
		capabilityLoading = {};
		loadCapabilities();
	});
</script>

<div class="flex h-full min-h-0 flex-col">
	<!-- Tabs -->
	<div class="bg-surface px-4">
		<Tabs tabs={tabsList} value={activeTab} onchange={handleTabChange} />
	</div>

	<!-- Content -->
	<div class="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:p-6">
		{#if activeTab.startsWith('cap:')}
			{@const cap = activeTab.slice(4)}
			{@const Renderer = getRenderer(cap)}
			{#if capabilityLoading[cap]}
				<div class="flex justify-center py-10">
					<Loader2 class="text-text-muted h-5 w-5 animate-spin" aria-hidden="true" />
				</div>
			{:else if capabilityErrors[cap]}
				<Banner variant="danger" description={capabilityErrors[cap]} />
			{:else if Renderer && capabilityPayloads[cap]}
				<Renderer
					payload={capabilityPayloads[cap]}
					item={{ id: itemId, library_id: libraryId }}
					{libraryId}
				/>
			{:else if capabilityPayloads[cap]}
				<div class="space-y-3">
					<p class="type-body-muted">
						{localeLoaded
							? $_('libraries.capabilities.noRenderer', {
									default: 'No viewer is registered for the "{cap}" capability yet.',
									values: { cap }
								})
							: `No viewer for "${cap}".`}
					</p>
					<Button
						variant="secondary"
						href={`/creator/libraries/${libraryId}/items/${itemId}/content/${cap}`}
						target="_blank"
						rel="noopener noreferrer"
						iconRightComponent={ExternalLink}
					>
						{localeLoaded
							? $_('libraries.capabilities.viewRaw', { default: 'View raw payload' })
							: 'View raw payload'}
					</Button>
				</div>
			{/if}
		{:else if activeTab === 'markdown'}
			{#if isLoading}
				<div class="flex justify-center py-10">
					<Loader2 class="text-text-muted h-5 w-5 animate-spin" aria-hidden="true" />
				</div>
			{:else if error}
				{#if errorKind === 'rate_limit'}
					<Banner
						variant="danger"
						title={localeLoaded
							? $_('libraries.itemContentModal.errorRateLimit', {
									default: 'YouTube rate-limited this request.'
								})
							: 'YouTube rate-limited this request.'}
						description={localeLoaded
							? $_('libraries.itemContentModal.errorRateLimitHint', {
									default:
										'Wait a few minutes, then delete this item and try importing it again.'
								})
							: 'Wait a few minutes, then delete this item and try importing it again.'}
					/>
				{:else if errorKind === 'no_subtitles'}
					<Banner
						variant="danger"
						title={localeLoaded
							? $_('libraries.itemContentModal.errorNoSubtitles', {
									default: 'No subtitles found for the requested language.'
								})
							: 'No subtitles found for the requested language.'}
						description={localeLoaded
							? $_('libraries.itemContentModal.errorNoSubtitlesHint', {
									default:
										'Delete this item and try again with a different language code (e.g. "es", "fr", "auto").'
								})
							: 'Delete this item and try again with a different language code (e.g. "es", "fr", "auto").'}
					/>
				{:else}
					<Banner variant="danger" description={error} />
				{/if}
			{:else if content}
				<!-- eslint-disable-next-line svelte/no-at-html-tags -->
				<div class="prose prose-sm max-w-none">{@html renderedHtml}</div>
			{:else}
				<EmptyState
					size="sm"
					icon={FileText}
					title={localeLoaded
						? $_('libraries.itemContentModal.empty', { default: 'No content available' })
						: 'No content available'}
				/>
			{/if}
		{:else}
			<!-- Original tab -->
			<div class="space-y-4">
				{#if sourceType === 'url' || sourceType === 'youtube'}
					<a
						href={sourceUrl}
						target="_blank"
						rel="noopener noreferrer"
						class="border-border bg-surface-muted hover:border-brand/30 hover:bg-brand-subtle group flex items-center justify-between gap-4 rounded-lg border px-4 py-3 transition-colors"
					>
						<div class="min-w-0 flex-1">
							<p class="type-label mb-0.5">
								{sourceType === 'youtube' ? 'YouTube' : 'URL'}
							</p>
							<p class="text-text group-hover:text-brand truncate text-sm">
								{sourceUrl}
							</p>
						</div>
						<span
							class="border-border-strong bg-surface text-brand group-hover:border-brand group-hover:bg-brand group-hover:text-brand-fg shadow-card inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors"
						>
							{localeLoaded
								? $_('libraries.itemContentModal.openInTab', { default: 'Open in new tab' })
								: 'Open in new tab'}
							<ExternalLink size={14} aria-hidden="true" />
						</span>
					</a>
				{:else if sourceType === 'file'}
					{#if originalFilename}
						<p class="type-body-muted">
							{localeLoaded
								? $_('libraries.itemContentModal.originalFile', { default: 'Original file' })
								: 'Original file'}:
							<span class="text-text ml-1 font-mono">{originalFilename}</span>
						</p>
					{/if}
					{#if onviewOriginal}
						<Button
							variant="secondary"
							iconRightComponent={ExternalLink}
							onclick={() => onviewOriginal && onviewOriginal()}
						>
							{localeLoaded
								? $_('libraries.itemContentModal.openOriginal', {
										default: 'Open original file'
									})
								: 'Open original file'}
						</Button>
					{/if}
				{/if}
			</div>
		{/if}
	</div>
</div>
