<!--
  @component PagesRenderer
  Capability renderer for ``Capability.PAGES`` — per-page markdown for
  paginated documents (PDF, DOCX, PPTX). Shows one page at a time with
  prev/next navigation.

  Props:
    - payload: { mime: "application/json", body: [{page, markdown}, ...] }
    - item:    optional LibraryItem (unused; kept for parity)
-->
<script>
	import { renderMarkdownStrict } from '$lib/utils/sanitize';
	import { _ } from '$lib/i18n';
	import { IconButton, EmptyState } from '$lib/components/ui';
	import { ChevronLeft, ChevronRight, FileText } from 'lucide-svelte';

	/**
	 * @typedef {{ page: number, markdown: string }} PageRow
	 */

	/** @type {{ payload?: { body?: unknown }, item?: any }} */
	let { payload = { body: [] }, item = null } = $props();

	/** @type {PageRow[]} */
	let pages = $derived(Array.isArray(payload?.body) ? /** @type {PageRow[]} */ (payload.body) : []);

	let index = $state(0);

	// Keep ``index`` in bounds even if the payload changes after mount.
	$effect(() => {
		if (index >= pages.length) index = Math.max(0, pages.length - 1);
	});

	let current = $derived(pages[index]);
	let renderedHtml = $derived(current ? renderMarkdownStrict(current.markdown || '') : '');

	function prev() {
		if (index > 0) index -= 1;
	}
	function next() {
		if (index < pages.length - 1) index += 1;
	}
</script>

{#if pages.length === 0}
	<EmptyState
		size="sm"
		icon={FileText}
		title={$_('libraries.capabilities.noPages', { default: 'No pages available.' })}
	/>
{:else}
	<div class="space-y-3">
		<div class="flex items-center justify-between">
			<IconButton
				icon={ChevronLeft}
				ariaLabel={$_('libraries.capabilities.prev', { default: 'Previous' })}
				tooltip={$_('libraries.capabilities.prev', { default: 'Previous' })}
				variant="ghost"
				size="sm"
				disabled={index === 0}
				onclick={prev}
				inModal
			/>
			<span class="text-text-muted px-2 text-sm">
				{$_('libraries.capabilities.pageOf', {
					default: 'Page {n} of {total}',
					values: { n: current?.page ?? index + 1, total: pages.length }
				})}
			</span>
			<IconButton
				icon={ChevronRight}
				ariaLabel={$_('libraries.capabilities.next', { default: 'Next' })}
				tooltip={$_('libraries.capabilities.next', { default: 'Next' })}
				variant="ghost"
				size="sm"
				disabled={index >= pages.length - 1}
				onclick={next}
				inModal
			/>
		</div>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		<div class="prose prose-sm border-border bg-surface-muted max-w-none rounded-md border p-4">
			{@html renderedHtml}
		</div>
	</div>
{/if}
