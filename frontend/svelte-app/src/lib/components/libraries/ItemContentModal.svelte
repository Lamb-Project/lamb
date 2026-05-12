<!--
  @component ItemContentModal
  Read-only viewer for a library item's rendered markdown. Sanitizes the
  body through renderMarkdownStrict before rendering it via `{@html}`.
-->
<script>
	import { _, locale } from '$lib/i18n';
	import { renderMarkdownStrict } from '$lib/utils/sanitize';

	let {
		isOpen = $bindable(false),
		isLoading = $bindable(false),
		title = '',
		content = '',
		error = null,
		onclose = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);

	let renderedHtml = $derived(content ? renderMarkdownStrict(content) : '');

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
			<div class="flex items-center border-b border-blue-200 bg-blue-50 px-4 py-3 sm:px-6">
				<h3
					id="modal-title-item-content"
					class="truncate text-lg leading-6 font-medium text-blue-900"
				>
					{title ||
						(localeLoaded
							? $_('libraries.itemContentModal.title', { default: 'Item Content' })
							: 'Item Content')}
				</h3>
			</div>

			<div class="max-h-[70vh] flex-1 overflow-y-auto px-4 py-5 sm:p-6">
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
			</div>

			<div class="flex justify-end border-t border-gray-200 bg-gray-50 px-4 py-3 sm:px-6">
				<button
					type="button"
					class="focus:ring-brand inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none"
					onclick={close}
					style="min-width:100px"
				>
					{localeLoaded ? $_('libraries.itemContentModal.close', { default: 'Close' }) : 'Close'}
				</button>
			</div>
		</div>
	</div>
{/if}
