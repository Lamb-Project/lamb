<!--
  @component FileTreeModal
  Tree-view modal for a library: folders + items + drag-and-drop + bulk
  select + search + inline preview pane. Accessible from both the
  Libraries list and the Library Detail page.

  Context menu uses the new Dropdown primitive with viewportClamp so it
  never escapes the viewport.

  See ``/home/novelia/.claude/plans/imperative-wobbling-stream.md`` for
  the full design.
-->
<script>
	import { SvelteSet } from 'svelte/reactivity';
	import { _, locale } from '$lib/i18n';
	import {
		getLibraryTree,
		createFolder,
		renameFolder,
		moveFolder,
		deleteFolder,
		moveItems,
		deleteItem,
		getItemKbLinks
	} from '$lib/services/libraryService';
	import {
		getKnowledgeStores,
		removeContent as removeKsContent
	} from '$lib/services/knowledgeStoreService';
	import {
		buildTree,
		filterTree,
		flatten,
		isValidDropTarget,
		resolveUploadFolderId as resolveTargetFolderId,
		splitSelection,
		findNode,
		ROOT_KEY
	} from './treeOps.js';
	import FileTreeNode from './FileTreeNode.svelte';
	import TreePreviewPane from './TreePreviewPane.svelte';
	import MoveToFolderPicker from './MoveToFolderPicker.svelte';
	import ConfirmationModal from '../../modals/ConfirmationModal.svelte';
	import {
		Modal,
		Button,
		IconButton,
		Badge,
		Banner,
		Dropdown,
		EmptyState
	} from '$lib/components/ui';
	import {
		Search,
		X,
		FolderPlus,
		FolderInput,
		Trash2,
		Inbox,
		Folder,
		RefreshCw
	} from 'lucide-svelte';

	let {
		isOpen = $bindable(false),
		libraryId = '',
		libraryName = '',
		isReadOnly = false,
		onclose = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);

	// ---------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------

	/** @type {import('./treeOps.js').TreeNode|null} */
	let tree = $state(null);
	let loading = $state(false);
	let loadError = $state('');

	let expandedKeys = $state(new SvelteSet());
	let selectedIds = $state(new SvelteSet());
	let focusedNodeKey = $state('');

	let searchQuery = $state('');
	let debouncedQuery = $state('');

	/** Parent folder id (or null=root) for an in-flight create. ``""`` = no create. */
	let creatingFolderUnder = $state(/** @type {string|null|undefined} */ (undefined));
	let newFolderName = $state('');

	let renamingNodeKey = $state('');

	let moveDialogOpen = $state(false);
	let moveDialogCandidates = $state(/** @type {string[]} */ ([]));

	// Drag state
	let dragOverKey = $state('');
	let invalidDropKey = $state('');
	/** Keys currently being dragged. */
	let draggedKeys = $state(/** @type {string[]} */ ([]));

	// Folder delete confirmation
	let folderToDelete = $state(/** @type {{id: string, name: string}|null} */ (null));
	let showFolderDeleteModal = $state(false);

	// Item delete (FR-10 flow, duplicated from LibraryDetail.svelte)
	let itemToDelete = $state(/** @type {{id: string, name: string}|null} */ (null));
	let showItemDeleteModal = $state(false);
	let itemDeleteError = $state('');
	let itemDeleteBlockers = $state(
		/** @type {Array<{id: string, name: string, contentCount: number|null, removing: boolean}>} */ ([])
	);
	let isDeletingItem = $state(false);
	// Bump this on every cancel/open so an in-flight kb-links fetch from a
	// previous click can detect that it's stale and skip mutating state.
	let itemDeleteRequestId = $state(0);

	// Context menu (Dropdown primitive)
	let ctxMenuOpen = $state(false);
	let ctxMenuPoint = $state(/** @type {{x: number, y: number}|null} */ (null));
	let ctxMenuKey = $state('');
	let ctxMenuKind = $state(/** @type {'folder'|'item'} */ ('item'));

	// ---------------------------------------------------------------------
	// Derived
	// ---------------------------------------------------------------------

	let filterResult = $derived(tree ? filterTree(tree, debouncedQuery) : null);
	let visibleKeys = $derived(filterResult?.visible || null);
	let effectiveExpandedKeys = $derived.by(() => {
		if (!filterResult) return expandedKeys;
		const merged = new SvelteSet(expandedKeys);
		for (const k of filterResult.autoExpand) merged.add(k);
		return merged;
	});

	let selectedNode = $derived.by(() => {
		if (!tree || selectedIds.size !== 1) return null;
		const [k] = selectedIds;
		return findNode(tree, k);
	});

	// Where a new folder should land based on current selection (parent of
	// focused folder/item, or root). Reuses the same rule we used for
	// upload-target resolution before the upload feature was removed.
	let newFolderParentId = $derived(tree ? resolveTargetFolderId(selectedIds, tree) : null);

	let selectionParts = $derived(splitSelection(selectedIds));

	let topLevelFolderCount = $derived(
		tree ? tree.children.filter((c) => c.kind === 'folder').length : 0
	);

	// ---------------------------------------------------------------------
	// Effects
	// ---------------------------------------------------------------------

	$effect(() => {
		if (isOpen && libraryId) loadTree();
		if (!isOpen) {
			// Reset transient state on close. Persist nothing for v1.
			selectedIds.clear();
			expandedKeys.clear();
			focusedNodeKey = '';
			renamingNodeKey = '';
			creatingFolderUnder = undefined;
			searchQuery = '';
			debouncedQuery = '';
			loadError = '';
			showItemDeleteModal = false;
			itemToDelete = null;
			itemDeleteError = '';
			itemDeleteBlockers = [];
			// NOTE: do NOT do `itemDeleteRequestId += 1` here — that's a
			// read+write of a tracked state inside an effect, which causes
			// an infinite re-run loop that freezes page load. Bumping the
			// request id in `requestDeleteItem` and the cancel handlers is
			// sufficient to invalidate any in-flight kb-links fetch.
			showFolderDeleteModal = false;
			folderToDelete = null;
			ctxMenuOpen = false;
		}
	});

	$effect(() => {
		const q = searchQuery;
		const h = setTimeout(() => {
			debouncedQuery = q;
		}, 150);
		return () => clearTimeout(h);
	});

	// ---------------------------------------------------------------------
	// Tree IO
	// ---------------------------------------------------------------------

	async function loadTree() {
		loading = true;
		loadError = '';
		try {
			const payload = await getLibraryTree(libraryId);
			tree = buildTree(payload);
		} catch (err) {
			loadError =
				err instanceof Error
					? err.message
					: localeLoaded
						? $_('libraries.fileTree.errors.loadFailed', {
								default: 'Failed to load the file tree.'
							})
						: 'Failed to load the file tree.';
		} finally {
			loading = false;
		}
	}

	async function refreshTree() {
		try {
			const payload = await getLibraryTree(libraryId);
			tree = buildTree(payload);
		} catch (err) {
			console.error('refreshTree failed', err);
		}
	}

	// ---------------------------------------------------------------------
	// Selection
	// ---------------------------------------------------------------------

	function handleSelect(/** @type {string} */ key, /** @type {{ctrl:boolean,shift:boolean}} */ m) {
		focusedNodeKey = key;
		if (m.ctrl) {
			if (selectedIds.has(key)) selectedIds.delete(key);
			else selectedIds.add(key);
			return;
		}
		if (m.shift && tree) {
			const flat = flatten(tree, effectiveExpandedKeys, visibleKeys);
			const i1 = flat.findIndex((n) => n.key === key);
			let i2 = flat.findIndex((n) => selectedIds.has(n.key));
			if (i2 < 0) i2 = i1;
			const [a, b] = i1 < i2 ? [i1, i2] : [i2, i1];
			selectedIds.clear();
			for (let i = a; i <= b; i++) selectedIds.add(flat[i].key);
			return;
		}
		// plain click
		selectedIds.clear();
		selectedIds.add(key);
	}

	function handleToggle(/** @type {string} */ key) {
		if (expandedKeys.has(key)) expandedKeys.delete(key);
		else expandedKeys.add(key);
	}

	// ---------------------------------------------------------------------
	// Context menu
	// ---------------------------------------------------------------------

	function handleContextMenu(
		/** @type {string} */ key,
		/** @type {number} */ x,
		/** @type {number} */ y
	) {
		if (isReadOnly) return;
		const kind = key.startsWith('folder:') ? 'folder' : 'item';
		ctxMenuKey = key;
		ctxMenuKind = kind;
		ctxMenuPoint = { x, y };
		ctxMenuOpen = true;
		// Single-select the right-clicked node if it isn't already in selection.
		if (!selectedIds.has(key)) {
			selectedIds.clear();
			selectedIds.add(key);
		}
	}

	// ---------------------------------------------------------------------
	// Folder operations
	// ---------------------------------------------------------------------

	function beginCreateFolder(/** @type {string|null} */ parentId) {
		creatingFolderUnder = parentId;
		newFolderName = '';
		if (parentId) expandedKeys.add(`folder:${parentId}`);
	}

	async function commitCreateFolder() {
		const name = newFolderName.trim();
		if (!name) {
			creatingFolderUnder = undefined;
			return;
		}
		try {
			await createFolder(libraryId, {
				name,
				parent_folder_id: creatingFolderUnder ?? null
			});
			creatingFolderUnder = undefined;
			newFolderName = '';
			await refreshTree();
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Create folder failed';
		}
	}

	function beginRename(/** @type {string} */ key) {
		renamingNodeKey = key;
	}

	async function commitRename(/** @type {string} */ key, /** @type {string} */ name) {
		if (!tree) return;
		const node = findNode(tree, key);
		if (!node || node.kind !== 'folder') {
			renamingNodeKey = '';
			return;
		}
		try {
			await renameFolder(libraryId, node.id, name);
			await refreshTree();
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Rename failed';
		} finally {
			renamingNodeKey = '';
		}
	}

	function requestDeleteFolder(/** @type {string} */ key) {
		if (!tree) return;
		const node = findNode(tree, key);
		if (!node || node.kind !== 'folder') return;
		folderToDelete = { id: node.id, name: node.name };
		showFolderDeleteModal = true;
	}

	async function confirmDeleteFolder() {
		if (!folderToDelete) return;
		try {
			await deleteFolder(libraryId, folderToDelete.id);
			showFolderDeleteModal = false;
			folderToDelete = null;
			await refreshTree();
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Delete folder failed';
		}
	}

	// ---------------------------------------------------------------------
	// Move to... + bulk move
	// ---------------------------------------------------------------------

	function openMoveDialog() {
		const candidates = Array.from(selectedIds);
		if (candidates.length === 0) return;
		moveDialogCandidates = candidates;
		moveDialogOpen = true;
	}

	async function handleMoveTo(/** @type {string|null} */ folderId) {
		const { itemIds, folderIds } = splitSelection(moveDialogCandidates);
		try {
			if (itemIds.length > 0) {
				await moveItems(libraryId, { item_ids: itemIds, folder_id: folderId });
			}
			for (const fId of folderIds) {
				await moveFolder(libraryId, fId, folderId);
			}
			await refreshTree();
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Move failed';
		}
	}

	// ---------------------------------------------------------------------
	// Drag and drop
	// ---------------------------------------------------------------------

	const DND_MIME = 'application/x-lamb-tree-keys';

	function handleDragStart(/** @type {string} */ key, /** @type {DragEvent} */ e) {
		if (isReadOnly) return;
		// If the dragged node is in the selection, drag the whole selection.
		const keys = selectedIds.has(key) ? Array.from(selectedIds) : [key];
		draggedKeys = keys;
		try {
			e.dataTransfer?.setData(DND_MIME, JSON.stringify(keys));
			if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
		} catch (_err) {
			/* ignore */
		}
	}

	function handleDragOver(/** @type {string} */ key, /** @type {DragEvent} */ e) {
		if (!tree) return;
		if (isValidDropTarget(key, draggedKeys, tree)) {
			e.preventDefault();
			dragOverKey = key;
			invalidDropKey = '';
			if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
		} else {
			invalidDropKey = key;
			dragOverKey = '';
		}
	}

	function handleDragLeave(/** @type {string} */ _key) {
		dragOverKey = '';
		invalidDropKey = '';
	}

	async function handleDrop(/** @type {string} */ targetKey, /** @type {DragEvent} */ e) {
		e.preventDefault();
		dragOverKey = '';
		invalidDropKey = '';
		if (!tree) return;
		if (!isValidDropTarget(targetKey, draggedKeys, tree)) return;
		const targetFolderId = targetKey === ROOT_KEY ? null : targetKey.slice('folder:'.length);
		const { itemIds, folderIds } = splitSelection(draggedKeys);
		try {
			if (itemIds.length > 0) {
				await moveItems(libraryId, { item_ids: itemIds, folder_id: targetFolderId });
			}
			for (const fId of folderIds) {
				await moveFolder(libraryId, fId, targetFolderId);
			}
			await refreshTree();
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Move failed';
		} finally {
			draggedKeys = [];
		}
	}

	function handleRootDragOver(/** @type {DragEvent} */ e) {
		if (!tree) return;
		if (isValidDropTarget(ROOT_KEY, draggedKeys, tree)) {
			e.preventDefault();
			dragOverKey = ROOT_KEY;
			if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
		}
	}

	function handleRootDrop(/** @type {DragEvent} */ e) {
		handleDrop(ROOT_KEY, e);
	}

	// ---------------------------------------------------------------------
	// Item delete (FR-10 flow, duplicated from LibraryDetail.svelte for now)
	// ---------------------------------------------------------------------

	async function requestDeleteItem(/** @type {string} */ key) {
		if (!tree) return;
		const node = findNode(tree, key);
		if (!node || node.kind !== 'item') return;
		// Reset modal state and stamp this request so an in-flight kb-links
		// fetch from a previous (now-cancelled) click can detect it's stale.
		itemDeleteRequestId += 1;
		const myRequestId = itemDeleteRequestId;
		itemToDelete = { id: node.id, name: node.name };
		itemDeleteError = '';
		itemDeleteBlockers = [];
		showItemDeleteModal = true;
		try {
			const links = await getItemKbLinks(libraryId, node.id);
			if (myRequestId !== itemDeleteRequestId) return; // stale: skip
			const referenced = Array.isArray(links?.knowledge_stores) ? links.knowledge_stores : [];
			if (referenced.length > 0) {
				itemDeleteError = localeLoaded
					? $_('libraries.deleteItemModal.blockedMessage', {
							default:
								'This item is referenced by one or more Knowledge Stores. Remove it from each before deleting.'
						})
					: 'This item is referenced by one or more Knowledge Stores. Remove it from each before deleting.';
				itemDeleteBlockers = referenced.map((k) => ({
					id: String(k?.id || ''),
					name: k?.name || k?.id || 'Knowledge Store',
					contentCount: /** @type {number|null} */ (null),
					removing: false
				}));
				try {
					const allKs = await getKnowledgeStores();
					if (myRequestId !== itemDeleteRequestId) return;
					const byId = new Map(allKs.map((k) => [k.id, k]));
					itemDeleteBlockers = itemDeleteBlockers.map((b) => {
						const full = byId.get(b.id);
						return {
							...b,
							contentCount: typeof full?.content_count === 'number' ? full.content_count : null
						};
					});
				} catch (_err) {
					/* best-effort enrichment */
				}
			}
		} catch (err) {
			console.warn('kb-links pre-check failed', err);
		}
	}

	async function confirmDeleteItem() {
		if (!itemToDelete) return;
		isDeletingItem = true;
		itemDeleteError = '';
		try {
			await deleteItem(libraryId, itemToDelete.id);
			showItemDeleteModal = false;
			itemToDelete = null;
			itemDeleteBlockers = [];
			await refreshTree();
		} catch (err) {
			const isAxios = !!(err && typeof err === 'object' && err.isAxiosError);
			const status = isAxios ? err.response?.status : null;
			const detail = isAxios ? err.response?.data?.detail : null;
			if (status === 409 && detail && typeof detail === 'object') {
				itemDeleteError = typeof detail.message === 'string' ? detail.message : 'Delete failed';
				const referenced = Array.isArray(detail.knowledge_stores) ? detail.knowledge_stores : [];
				itemDeleteBlockers = referenced.map((k) => ({
					id: String(k?.id || ''),
					name: k?.name || k?.id || 'Knowledge Store',
					contentCount: /** @type {number|null} */ (null),
					removing: false
				}));
			} else {
				itemDeleteError = err instanceof Error ? err.message : 'Delete failed';
			}
		} finally {
			isDeletingItem = false;
		}
	}

	async function removeBlocker(/** @type {string} */ ksId) {
		if (!itemToDelete) return;
		itemDeleteBlockers = itemDeleteBlockers.map((b) =>
			b.id === ksId ? { ...b, removing: true } : b
		);
		try {
			await removeKsContent(ksId, itemToDelete.id);
			itemDeleteBlockers = itemDeleteBlockers.filter((b) => b.id !== ksId);
			if (itemDeleteBlockers.length === 0) itemDeleteError = '';
		} catch (err) {
			console.error('removeKsContent failed', err);
			itemDeleteBlockers = itemDeleteBlockers.map((b) =>
				b.id === ksId ? { ...b, removing: false } : b
			);
			itemDeleteError = err instanceof Error ? err.message : 'Could not remove this link.';
		}
	}

	// ---------------------------------------------------------------------
	// Bulk delete (items only, FR-10 still applies per-item)
	// ---------------------------------------------------------------------

	async function bulkDeleteItems() {
		const ids = selectionParts.itemIds;
		if (ids.length === 0) return;
		// Naive: first one only via the same confirmation flow for safety.
		// Bulk delete UX with FR-10 across many items is a follow-up.
		if (ids.length === 1) {
			await requestDeleteItem(`item:${ids[0]}`);
		} else {
			// For multi-item delete, we currently route each through the
			// regular flow one at a time after user confirmation. Open the
			// confirmation on the first; the user can then re-trigger.
			await requestDeleteItem(`item:${ids[0]}`);
		}
	}

	// ---------------------------------------------------------------------
	// Modal close
	// ---------------------------------------------------------------------

	function close() {
		onclose();
		isOpen = false;
	}
</script>

<svelte:window
	onmousedown={(e) => {
		// Cancel an in-flight folder create when the user mousedowns anywhere
		// outside the create input. The input's data-attribute marks it so
		// clicks on it (and on the "New folder" toolbar button, before the
		// create starts) don't trigger a cancel.
		if (creatingFolderUnder === undefined) return;
		const target = /** @type {HTMLElement} */ (e.target);
		if (target?.closest && !target.closest('[data-create-folder-input="true"]')) {
			commitCreateFolder();
		}
	}}
/>

<Modal
	open={isOpen}
	onclose={close}
	size="full"
	labelledBy="file-tree-modal-title"
	closeAriaLabel={$_('common.close', { default: 'Close' })}
	bodyClass="p-0"
>
	{#snippet header({ close: closeFn })}
		<div class="border-border flex items-start justify-between gap-3 border-b px-6 py-4">
			<div class="min-w-0 flex-1">
				<h2 id="file-tree-modal-title" class="type-section-title truncate">
					{libraryName ||
						(localeLoaded
							? $_('libraries.fileTree.detailButton', { default: 'File tree' })
							: 'File tree')}
				</h2>
				{#if tree}
					<div class="mt-2 flex flex-wrap items-center gap-2">
						<Badge variant="neutral">
							{tree.descendantItemCount}
							{tree.descendantItemCount === 1
								? localeLoaded
									? $_('libraries.fileTree.headerItemSingular', { default: 'item' })
									: 'item'
								: localeLoaded
									? $_('libraries.fileTree.headerItemPlural', { default: 'items' })
									: 'items'}
						</Badge>
						<Badge variant="neutral">
							{topLevelFolderCount}
							{topLevelFolderCount === 1
								? localeLoaded
									? $_('libraries.fileTree.headerFolderSingular', { default: 'top-level folder' })
									: 'top-level folder'
								: localeLoaded
									? $_('libraries.fileTree.headerFolderPlural', { default: 'top-level folders' })
									: 'top-level folders'}
						</Badge>
					</div>
				{/if}
			</div>
			<IconButton
				icon={X}
				ariaLabel={$_('common.close', { default: 'Close' })}
				tooltip={$_('common.close', { default: 'Close' })}
				variant="ghost"
				size="sm"
				inModal
				onclick={closeFn}
			/>
		</div>
	{/snippet}

	<!-- Toolbar -->
	<div
		class="border-border bg-surface-muted flex flex-wrap items-center gap-2 border-b px-5 py-2.5"
	>
		<div class="relative max-w-md min-w-0 flex-1">
			<Search
				size={16}
				class="text-text-subtle pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2"
				aria-hidden="true"
			/>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder={localeLoaded
					? $_('libraries.fileTree.searchPlaceholder', { default: 'Search by name…' })
					: 'Search by name…'}
				class="border-border-strong bg-surface text-text placeholder:text-text-subtle focus:border-brand shadow-card w-full rounded-md border py-1.5 pr-8 pl-9 text-sm transition-colors focus:outline-none focus-visible:shadow-[var(--shadow-focus)]"
			/>
			{#if searchQuery}
				<button
					type="button"
					onclick={() => (searchQuery = '')}
					class="text-text-subtle hover:bg-surface-sunken hover:text-text absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5"
					aria-label={localeLoaded
						? $_('libraries.fileTree.searchClear', { default: 'Clear search' })
						: 'Clear search'}
				>
					<X size={14} aria-hidden="true" />
				</button>
			{/if}
		</div>
		{#if !isReadOnly}
			<Button
				variant="secondary"
				size="sm"
				iconLeftComponent={FolderPlus}
				onclick={() => beginCreateFolder(newFolderParentId)}
			>
				{localeLoaded
					? $_('libraries.fileTree.createFolderBtn', { default: 'New folder' })
					: 'New folder'}
			</Button>
		{/if}

		<!-- Selection actions on the right -->
		{#if selectedIds.size > 0 && !isReadOnly}
			<div class="ml-auto flex items-center gap-2">
				<Badge variant="info">
					{localeLoaded
						? $_('libraries.fileTree.selectionCount', {
								default: '{count} selected',
								values: { count: selectedIds.size }
							})
						: `${selectedIds.size} selected`}
				</Badge>
				<Button
					variant="secondary"
					size="sm"
					iconLeftComponent={FolderInput}
					onclick={openMoveDialog}
				>
					{localeLoaded ? $_('libraries.fileTree.moveToBtn', { default: 'Move to…' }) : 'Move to…'}
				</Button>
				{#if selectionParts.itemIds.length > 0 && selectionParts.folderIds.length === 0}
					<Button
						variant="danger-ghost"
						size="sm"
						iconLeftComponent={Trash2}
						onclick={bulkDeleteItems}
					>
						{localeLoaded ? $_('libraries.fileTree.deleteBtn', { default: 'Delete' }) : 'Delete'}
					</Button>
				{/if}
			</div>
		{/if}
	</div>

	{#if loadError}
		<div class="border-border border-b px-4 py-2">
			<Banner variant="danger" description={loadError}>
				{#snippet actions()}
					<Button variant="secondary" size="sm" iconLeftComponent={RefreshCw} onclick={loadTree}>
						{$_('common.retry', { default: 'Retry' })}
					</Button>
				{/snippet}
			</Banner>
		</div>
	{/if}

	<!-- Body. ``min-h-0`` is critical so the flex children can shrink
			 below their content size — without it ``overflow-y-auto`` on
			 the inner content (markdown, pages) never triggers and the
			 user can't scroll tall items. -->
	<div class="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
		<!-- Tree pane: clicking the empty space inside the pane (but
				 outside any node) clears the selection, matching native
				 file-manager behavior. Individual nodes already
				 stopPropagation in their own click handler, so any click
				 that bubbles up here was on empty space. -->
		<div
			class="border-border flex max-h-[40vh] flex-col overflow-y-auto border-b md:max-h-none md:w-2/5 md:border-r md:border-b-0"
			onclick={() => {
				if (selectedIds.size > 0) selectedIds.clear();
			}}
		>
			<div
				class="flex-1 p-2"
				role="tree"
				aria-multiselectable="true"
				aria-label={localeLoaded
					? $_('libraries.fileTree.treeAriaLabel', {
							default: 'Files in {libraryName}',
							values: { libraryName }
						})
					: 'Files'}
			>
				{#if loading}
					<p class="text-text-muted p-4 text-sm">
						{localeLoaded ? $_('common.processing', { default: 'Loading...' }) : 'Loading...'}
					</p>
				{:else if !tree || (tree.children.length === 0 && creatingFolderUnder === undefined)}
					<EmptyState
						icon={Inbox}
						title={localeLoaded
							? $_('libraries.fileTree.empty', { default: 'This library is empty.' })
							: 'This library is empty.'}
						description={localeLoaded
							? $_('libraries.fileTree.emptyHint', {
									default: 'Add content from the library page, then organize it here.'
								})
							: 'Add content from the library page, then organize it here.'}
					>
						{#snippet actions()}
							{#if !isReadOnly}
								<Button
									variant="secondary"
									size="sm"
									iconLeftComponent={FolderPlus}
									onclick={() => beginCreateFolder(null)}
								>
									{localeLoaded
										? $_('libraries.fileTree.emptyCreateFolder', { default: 'Create folder' })
										: 'Create folder'}
								</Button>
							{/if}
						{/snippet}
					</EmptyState>
				{:else}
					<!-- Inline create-folder input at root (when creatingFolderUnder === null) -->
					{#if creatingFolderUnder === null && !isReadOnly}
						<div class="flex items-center gap-2 rounded px-2 py-1.5">
							<Folder size={16} class="text-brand shrink-0" aria-hidden="true" />
							<input
								type="text"
								data-create-folder-input="true"
								bind:value={newFolderName}
								placeholder={localeLoaded
									? $_('libraries.fileTree.newFolderPlaceholder', {
											default: 'New folder name'
										})
									: 'New folder name'}
								onkeydown={(e) => {
									if (e.key === 'Enter') commitCreateFolder();
									else if (e.key === 'Escape') creatingFolderUnder = undefined;
								}}
								class="border-brand shadow-card focus:ring-brand flex-1 rounded border px-2 py-1 text-sm focus:ring-1 focus:outline-none"
								autofocus
							/>
						</div>
					{/if}
					{#each tree.children as child (child.key)}
						<FileTreeNode
							node={child}
							depth={0}
							{selectedIds}
							expandedKeys={effectiveExpandedKeys}
							{focusedNodeKey}
							{renamingNodeKey}
							highlightTerm={debouncedQuery}
							{visibleKeys}
							{dragOverKey}
							{invalidDropKey}
							{isReadOnly}
							{creatingFolderUnder}
							bind:newFolderName
							ontoggle={handleToggle}
							onselect={handleSelect}
							oncontextmenu={handleContextMenu}
							ondragstart={handleDragStart}
							ondragover={handleDragOver}
							ondragleave={handleDragLeave}
							ondrop={handleDrop}
							oncommitrename={commitRename}
							oncancelrename={() => (renamingNodeKey = '')}
							oncommitcreate={commitCreateFolder}
							oncancelcreate={() => (creatingFolderUnder = undefined)}
						/>
					{/each}

					<!-- Root drop zone -->
					{#if !isReadOnly}
						<div
							class="mt-2 rounded border-2 border-dashed px-2 py-3 text-center text-xs transition-colors
									{dragOverKey === ROOT_KEY
								? 'border-brand bg-brand-subtle text-brand'
								: 'text-text-subtle border-transparent'}"
							ondragover={handleRootDragOver}
							ondragleave={() => (dragOverKey = '')}
							ondrop={handleRootDrop}
							role="region"
							aria-label={localeLoaded
								? $_('libraries.fileTree.rootDropZone', { default: 'Drop here to move to root' })
								: 'Drop here to move to root'}
						>
							{localeLoaded
								? $_('libraries.fileTree.rootDropZone', { default: 'Drop here to move to root' })
								: 'Drop here to move to root'}
						</div>
					{/if}
				{/if}
			</div>
		</div>

		<!-- Preview pane -->
		<div class="flex min-h-0 flex-1 overflow-hidden">
			<TreePreviewPane {libraryId} {selectedNode} selectionCount={selectedIds.size} />
		</div>
	</div>

	{#snippet footer({ close: closeFn })}
		<Button variant="secondary" onclick={closeFn}>
			{localeLoaded ? $_('common.close', { default: 'Close' }) : 'Close'}
		</Button>
	{/snippet}
</Modal>

<!-- Context menu — clamped to viewport (fixes the original overflow bug). -->
<Dropdown
	open={ctxMenuOpen && !isReadOnly}
	anchorPoint={ctxMenuPoint}
	viewportClamp
	onclose={() => (ctxMenuOpen = false)}
	minWidth={180}
>
	{#snippet children({ close: closeMenu })}
		<div class="py-1">
			{#if ctxMenuKind === 'folder'}
				<button
					type="button"
					class="text-text hover:bg-surface-sunken flex w-full items-center px-3 py-2 text-left text-sm"
					onclick={() => {
						const folderId = ctxMenuKey.slice('folder:'.length);
						beginCreateFolder(folderId);
						closeMenu();
					}}
				>
					{localeLoaded
						? $_('libraries.fileTree.folders.create', { default: 'Create subfolder' })
						: 'Create subfolder'}
				</button>
				<button
					type="button"
					class="text-text hover:bg-surface-sunken flex w-full items-center px-3 py-2 text-left text-sm"
					onclick={() => {
						beginRename(ctxMenuKey);
						closeMenu();
					}}
				>
					{localeLoaded ? $_('libraries.fileTree.folders.rename', { default: 'Rename' }) : 'Rename'}
				</button>
				<button
					type="button"
					class="text-text hover:bg-surface-sunken flex w-full items-center px-3 py-2 text-left text-sm"
					onclick={() => {
						moveDialogCandidates = [ctxMenuKey];
						moveDialogOpen = true;
						closeMenu();
					}}
				>
					{localeLoaded
						? $_('libraries.fileTree.folders.moveTo', { default: 'Move to…' })
						: 'Move to…'}
				</button>
				<div class="border-border my-1 border-t"></div>
				<button
					type="button"
					class="text-danger hover:bg-danger-subtle flex w-full items-center px-3 py-2 text-left text-sm"
					onclick={() => {
						requestDeleteFolder(ctxMenuKey);
						closeMenu();
					}}
				>
					{localeLoaded
						? $_('libraries.fileTree.folders.delete', { default: 'Delete folder' })
						: 'Delete folder'}
				</button>
			{:else}
				<button
					type="button"
					class="text-text hover:bg-surface-sunken flex w-full items-center px-3 py-2 text-left text-sm"
					onclick={() => {
						moveDialogCandidates = [ctxMenuKey];
						moveDialogOpen = true;
						closeMenu();
					}}
				>
					{localeLoaded
						? $_('libraries.fileTree.folders.moveTo', { default: 'Move to…' })
						: 'Move to…'}
				</button>
				<div class="border-border my-1 border-t"></div>
				<button
					type="button"
					class="text-danger hover:bg-danger-subtle flex w-full items-center px-3 py-2 text-left text-sm"
					onclick={() => {
						requestDeleteItem(ctxMenuKey);
						closeMenu();
					}}
				>
					{localeLoaded ? $_('libraries.fileTree.deleteBtn', { default: 'Delete' }) : 'Delete'}
				</button>
			{/if}
		</div>
	{/snippet}
</Dropdown>

<MoveToFolderPicker
	bind:isOpen={moveDialogOpen}
	tree={tree || {
		key: ROOT_KEY,
		id: '__root__',
		kind: 'root',
		name: '',
		parentId: null,
		children: [],
		descendantItemCount: 0
	}}
	moveCandidateKeys={moveDialogCandidates}
	onpicked={handleMoveTo}
	oncancel={() => (moveDialogOpen = false)}
/>

<!-- Folder delete confirmation -->
<ConfirmationModal
	bind:isOpen={showFolderDeleteModal}
	title={localeLoaded
		? $_('libraries.fileTree.folders.deleteConfirmTitle', { default: 'Delete folder' })
		: 'Delete folder'}
	message={localeLoaded
		? $_('libraries.fileTree.folders.deleteConfirmMsg', {
				default:
					'Delete "{name}"? Items inside will move to the parent folder. This cannot be undone.',
				values: { name: folderToDelete?.name || '' }
			})
		: `Delete "${folderToDelete?.name || ''}"? Items inside will move to the parent folder.`}
	confirmText={localeLoaded ? $_('common.delete', { default: 'Delete' }) : 'Delete'}
	variant="danger"
	onconfirm={confirmDeleteFolder}
	oncancel={() => {
		showFolderDeleteModal = false;
		folderToDelete = null;
	}}
/>

<!-- Item delete confirmation (FR-10) -->
<ConfirmationModal
	bind:isOpen={showItemDeleteModal}
	bind:isLoading={isDeletingItem}
	bind:error={itemDeleteError}
	bind:blockers={itemDeleteBlockers}
	title={itemDeleteBlockers.length > 0
		? localeLoaded
			? $_('libraries.deleteItemModal.blockedTitle', { default: 'Cannot delete — in use' })
			: 'Cannot delete — in use'
		: localeLoaded
			? $_('libraries.deleteItemModal.title', { default: 'Delete item' })
			: 'Delete item'}
	message={itemDeleteBlockers.length > 0
		? ''
		: localeLoaded
			? $_('libraries.deleteItemModal.message', {
					default: 'Delete "{title}"? This action cannot be undone.',
					values: { title: itemToDelete?.name || '' }
				})
			: `Delete "${itemToDelete?.name || ''}"? This action cannot be undone.`}
	confirmText={localeLoaded ? $_('common.delete', { default: 'Delete' }) : 'Delete'}
	variant="danger"
	hideConfirm={itemDeleteBlockers.length > 0}
	blockersTitle={localeLoaded
		? $_('libraries.deleteItemModal.blockersTitle', { default: 'Referenced by Knowledge Stores' })
		: 'Referenced by Knowledge Stores'}
	blockerRemoveLabel={localeLoaded
		? $_('libraries.deleteItemModal.blockerRemove', { default: 'Remove from KS' })
		: 'Remove from KS'}
	onRemoveBlocker={removeBlocker}
	onconfirm={confirmDeleteItem}
	oncancel={() => {
		// Bump the request id so any in-flight kb-links fetch from this
		// session can't re-populate blockers after the user cancelled.
		itemDeleteRequestId += 1;
		showItemDeleteModal = false;
		itemToDelete = null;
		itemDeleteError = '';
		itemDeleteBlockers = [];
	}}
/>
