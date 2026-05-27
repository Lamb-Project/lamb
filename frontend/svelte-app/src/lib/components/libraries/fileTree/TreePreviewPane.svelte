<!--
  @component TreePreviewPane
  Right pane of the FileTreeModal. Shows ItemContentTabs for a single-item
  selection, folder stats for a folder selection, and a placeholder
  otherwise.
-->
<script>
	import { _, locale } from '$lib/i18n';
	import { getItemContent } from '$lib/services/libraryService';
	import ItemContentTabs from '../ItemContentTabs.svelte';
	import { EmptyState, Card } from '$lib/components/ui';
	import { FolderTree, Folder } from 'lucide-svelte';

	let {
		libraryId,
		/** @type {import('./treeOps.js').TreeNode|null} */
		selectedNode = null,
		selectionCount = 0
	} = $props();

	let localeLoaded = $derived(!!$locale);

	/** @type {string} */
	let content = $state('');
	/** @type {string|null} */
	let error = $state(null);
	let isLoading = $state(false);
	/** @type {string} */
	let loadedItemId = $state('');

	$effect(() => {
		// Reset and lazy-load whenever the selected item changes.
		if (!selectedNode || selectedNode.kind !== 'item') {
			content = '';
			error = null;
			isLoading = false;
			loadedItemId = '';
			return;
		}
		const itemId = selectedNode.id;
		if (itemId === loadedItemId) return;
		loadedItemId = itemId;
		content = '';
		error = null;

		// If the item's import failed (or is still pending), the markdown
		// content file doesn't exist on disk — fetching it would 404. Surface
		// the item's own error_message / status instead of letting the
		// network error bubble up.
		const raw = selectedNode.raw || {};
		const status = raw.status;
		if (status === 'failed') {
			error =
				raw.error_message ||
				(localeLoaded
					? $_('libraries.fileTree.errors.importFailed', {
							default: 'Import failed for this item. No content is available.'
						})
					: 'Import failed for this item. No content is available.');
			isLoading = false;
			return;
		}
		if (status && status !== 'ready' && status !== 'completed') {
			// pending / processing — content not yet available
			error = localeLoaded
				? $_('libraries.fileTree.errors.notReady', {
						default: 'This item is still being processed. Try again in a moment.'
					})
				: 'This item is still being processed. Try again in a moment.';
			isLoading = false;
			return;
		}

		isLoading = true;
		getItemContent(libraryId, itemId)
			.then((text) => {
				content = typeof text === 'string' ? text : '';
			})
			.catch((err) => {
				// Best-effort: prefer the item's own error_message if we have one.
				const msg =
					raw.error_message || (err instanceof Error ? err.message : 'Failed to load content.');
				error = msg;
			})
			.finally(() => {
				isLoading = false;
			});
	});

	let raw = $derived(selectedNode?.raw || {});
</script>

<div class="bg-surface flex h-full min-h-0 flex-col">
	{#if selectionCount > 1}
		<div class="flex flex-1 items-center justify-center">
			<EmptyState
				icon={FolderTree}
				title={localeLoaded
					? $_('libraries.fileTree.multiSelected', {
							default: '{count} items selected',
							values: { count: selectionCount }
						})
					: `${selectionCount} items selected`}
				description={localeLoaded
					? $_('libraries.fileTree.multiSelectedHint', {
							default: 'Use Move to… or drag the selection into a folder.'
						})
					: 'Use Move to… or drag the selection into a folder.'}
			/>
		</div>
	{:else if selectionCount === 0 || !selectedNode}
		<div class="flex flex-1 items-center justify-center">
			<EmptyState
				icon={FolderTree}
				title={localeLoaded
					? $_('libraries.fileTree.noSelectionTitle', { default: 'Nothing selected' })
					: 'Nothing selected'}
				description={localeLoaded
					? $_('libraries.fileTree.noSelectionDesc', {
							default: 'Pick a folder or item from the tree to preview it here.'
						})
					: 'Pick a folder or item from the tree to preview it here.'}
			/>
		</div>
	{:else if selectedNode.kind === 'folder'}
		<div class="space-y-4 p-6">
			<div class="flex items-start gap-3">
				<div
					class="bg-warning-subtle text-warning flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
					aria-hidden="true"
				>
					<Folder size={20} aria-hidden="true" />
				</div>
				<div class="min-w-0 flex-1">
					<h3 class="type-section-title truncate">{selectedNode.name}</h3>
					<p class="type-caption">
						{localeLoaded ? $_('libraries.fileTree.folderLabel', { default: 'Folder' }) : 'Folder'}
					</p>
				</div>
			</div>
			<div class="grid grid-cols-2 gap-3">
				<Card padded={false} divided={false} class="p-4">
					<p class="type-label">
						{localeLoaded ? $_('libraries.fileTree.stats.items', { default: 'Items' }) : 'Items'}
					</p>
					<p class="text-text mt-1 text-2xl font-semibold">{selectedNode.descendantItemCount}</p>
				</Card>
				<Card padded={false} divided={false} class="p-4">
					<p class="type-label">
						{localeLoaded
							? $_('libraries.fileTree.stats.subfolders', { default: 'Subfolders' })
							: 'Subfolders'}
					</p>
					<p class="text-text mt-1 text-2xl font-semibold">
						{selectedNode.children.filter((c) => c.kind === 'folder').length}
					</p>
				</Card>
			</div>
		</div>
	{:else}
		<!-- Item: embed shared tabs component -->
		<ItemContentTabs
			{libraryId}
			itemId={selectedNode.id}
			{isLoading}
			{content}
			{error}
			sourceType={raw.source_type || ''}
			sourceUrl={raw.source_url || ''}
			originalFilename={raw.original_filename || ''}
			resetKey={selectedNode.id}
		/>
	{/if}
</div>
