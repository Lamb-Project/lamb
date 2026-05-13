<!--
  @component ItemContentModal
  Tabbed viewer for a library item. "Markdown" tab shows the rendered content;
  "Original" tab shows the source URL (for url/youtube imports) or original
  file (for file imports). For failed items the error is shown in the Markdown
  tab.
-->
<script>
	import { _, locale } from '$lib/i18n';
	import { renderMarkdownStrict } from '$lib/utils/sanitize';

	let {
		isOpen = $bindable(false),
		isLoading = $bindable(false),
		title = '',
		content = '',
		/** @type {string|null} */
		error = null,
		sourceType = '',
		sourceUrl = '',
		originalFilename = '',
		/** @type {(() => void) | null} */
		onviewOriginal = null,
		onclose = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);
	let renderedHtml = $derived(content ? renderMarkdownStrict(content) : '');

	/** @type {'markdown' | 'original'} */
	let activeTab = $state('markdown');

	// Reset to markdown tab each time the modal opens.
	$effect(() => {
		if (isOpen) {
			activeTab = 'markdown';
		}
	});

	// Show the Original tab only when we have useful source data.
	let hasOriginal = $derived(
		!!(sourceType === 'url' || sourceType === 'youtube'
			? sourceUrl
			: sourceType === 'file' && onviewOriginal)
	);

	function close() {
		onclose();
		isOpen = false;
	}

	function handleOverlayClick() {
		close();
	}

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (!isOpen) return;
		if (event.key === 'Escape') close();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<div
		class="fixed inset-0 z-40 bg-gray-500/75 transition-opacity"
		onclick={handleOverlayClick}
		aria-hidden="true"
	></div>

	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div
			class="relative mx-2 flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-gray-300 bg-white shadow-xl"
			role="dialog"
			aria-modal="true"
			aria-labelledby="modal-title-item-content"
		>
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-blue-200 bg-blue-50 px-4 py-3 sm:px-6">
				<h3
					id="modal-title-item-content"
					class="truncate text-lg leading-6 font-medium text-blue-900"
				>
					{title ||
						(localeLoaded
							? $_('libraries.itemContentModal.title', { default: 'Item Content' })
							: 'Item Content')}
				</h3>
				<button
					type="button"
					onclick={close}
					class="ml-4 shrink-0 rounded p-1 text-blue-400 hover:bg-blue-100 hover:text-blue-600"
					aria-label="Close"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
					</svg>
				</button>
			</div>

			<!-- Tabs (only shown when there is original source data) -->
			{#if hasOriginal}
				<div class="flex border-b border-gray-200 bg-white px-4" role="tablist">
					<button
						type="button"
						role="tab"
						aria-selected={activeTab === 'markdown'}
						onclick={() => (activeTab = 'markdown')}
						class="mr-6 border-b-2 py-3 text-sm font-medium transition-colors {activeTab === 'markdown'
							? 'border-blue-600 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700'}"
					>
						{localeLoaded
							? $_('libraries.itemContentModal.tabMarkdown', { default: 'Markdown' })
							: 'Markdown'}
					</button>
					<button
						type="button"
						role="tab"
						aria-selected={activeTab === 'original'}
						onclick={() => (activeTab = 'original')}
						class="border-b-2 py-3 text-sm font-medium transition-colors {activeTab === 'original'
							? 'border-blue-600 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700'}"
					>
						{localeLoaded
							? $_('libraries.itemContentModal.tabOriginal', { default: 'Original' })
							: 'Original'}
					</button>
				</div>
			{/if}

			<!-- Content -->
			<div class="max-h-[70vh] flex-1 overflow-y-auto px-4 py-5 sm:p-6">
				{#if activeTab === 'markdown' || !hasOriginal}
					{#if isLoading}
						<div class="flex items-center justify-center py-10 text-sm text-gray-500">
							<svg
								class="mr-2 h-5 w-5 animate-spin"
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
							>
								<circle
									class="opacity-25"
									cx="12"
									cy="12"
									r="10"
									stroke="currentColor"
									stroke-width="4"
								></circle>
								<path
									class="opacity-75"
									fill="currentColor"
									d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
								></path>
							</svg>
							{localeLoaded ? $_('common.processing', { default: 'Loading...' }) : 'Loading...'}
						</div>
					{:else if error}
						<div class="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
							{error}
						</div>
					{:else if content}
						<!-- eslint-disable-next-line svelte/no-at-html-tags -->
						<div class="prose prose-sm max-w-none">{@html renderedHtml}</div>
					{:else}
						<p class="text-sm text-gray-500">
							{localeLoaded
								? $_('libraries.itemContentModal.empty', { default: 'No content.' })
								: 'No content.'}
						</p>
					{/if}
				{:else}
					<!-- Original tab -->
					<div class="space-y-4">
						{#if sourceType === 'url' || sourceType === 'youtube'}
							<p class="text-sm text-gray-500">
								{sourceType === 'youtube'
									? (localeLoaded ? $_('libraries.itemContentModal.sourceYoutube', { default: 'YouTube video' }) : 'YouTube video')
									: (localeLoaded ? $_('libraries.itemContentModal.sourceUrl', { default: 'Web page' }) : 'Web page')}
							</p>
							<a
								href={sourceUrl}
								target="_blank"
								rel="noopener noreferrer"
								class="block break-all text-sm text-blue-600 hover:underline"
							>{sourceUrl}</a>
							<button
								type="button"
								onclick={() => window.open(sourceUrl, '_blank', 'noopener,noreferrer')}
								class="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 shadow-sm hover:bg-blue-50"
							>
								{localeLoaded
									? $_('libraries.itemContentModal.openInTab', { default: 'Open in new tab' })
									: 'Open in new tab'}
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
									<path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
									<path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
								</svg>
							</button>
						{:else if sourceType === 'file'}
							{#if originalFilename}
								<p class="text-sm text-gray-500">
									{localeLoaded
										? $_('libraries.itemContentModal.originalFile', { default: 'Original file' })
										: 'Original file'}:
									<span class="ml-1 font-mono text-gray-800">{originalFilename}</span>
								</p>
							{/if}
							{#if onviewOriginal}
								<button
									type="button"
									onclick={() => onviewOriginal && onviewOriginal()}
									class="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 shadow-sm hover:bg-blue-50"
								>
									{localeLoaded
										? $_('libraries.itemContentModal.openOriginal', { default: 'Open original file' })
										: 'Open original file'}
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
										<path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
										<path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
									</svg>
								</button>
							{/if}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-end border-t border-gray-200 bg-gray-50 px-4 py-3 sm:px-6">
				<button
					type="button"
					class="inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none"
					onclick={close}
					style="min-width:100px"
				>
					{localeLoaded ? $_('libraries.itemContentModal.close', { default: 'Close' }) : 'Close'}
				</button>
			</div>
		</div>
	</div>
{/if}
