<!--
  @component LibrariesList
  Displays libraries with combinable filter chips, skeleton loading,
  canonical IconButton actions, and localStorage-persisted page size.

  Perceived performance: paint page 1 immediately from the cache (if any),
  then revalidate in the background. After the fresh fetch lands, the rest
  of the rows are prefetched into the cache so pagination clicks are instant.
-->
<script>
	import { onMount, createEventDispatcher } from 'svelte';
	import {
		getLibraries,
		deleteLibrary,
		toggleSharing,
		getLibraryKbLinks
	} from '$lib/services/libraryService';
	import { removeContent as removeKsContent } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { processListData } from '$lib/utils/listHelpers';
	import { toast } from '$lib/stores/toast.js';
	import {
		readLibrariesCache,
		writeLibrariesCache,
		patchLibraryInCache,
		removeLibraryFromCache
	} from '$lib/stores/librariesCache.js';
	import CreateLibraryModal from '$lib/components/modals/CreateLibraryModal.svelte';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import EntityListShell from '$lib/components/common/EntityListShell.svelte';
	import ResizableTable from '$lib/components/common/ResizableTable.svelte';
	import FileTreeModal from './fileTree/FileTreeModal.svelte';
	import { Button, IconButton, OverflowMenu, Badge, EmptyState } from '$lib/components/ui';
	import {
		Plus,
		Eye,
		Trash2,
		Share2,
		Users,
		Lock,
		BookOpen,
		FolderTree
	} from '$lib/components/ui/icons.js';

	const dispatch = createEventDispatcher();

	const LS_PAGE_SIZE = 'lamb.list.libraries.itemsPerPage';

	/** @returns {number} */
	function loadItemsPerPage() {
		try {
			const v = localStorage.getItem(LS_PAGE_SIZE);
			if (v) return parseInt(v, 10) || 10;
		} catch {
			// ignore
		}
		return 10;
	}

	// Data
	/** @type {import('$lib/services/libraryService').Library[]} */
	let libraries = $state([]);
	/** @type {import('$lib/services/libraryService').Library[]} */
	let displayLibraries = $state([]);
	let loading = $state(true);
	let error = $state('');

	// Filter / sort / pagination
	let searchTerm = $state('');
	let sortBy = $state('created_at');
	/** @type {'asc'|'desc'} */
	let sortOrder = $state(/** @type {'asc'|'desc'} */ ('desc'));
	let currentPage = $state(1);
	let itemsPerPage = $state(loadItemsPerPage());
	let totalPages = $state(1);
	let totalItems = $state(0);

	// Combinable filters
	let sharingFilter = $state('all'); // 'my' | 'shared' | 'all'
	let hasItemsFilter = $state('any'); // 'with-items' | 'empty' | 'any'
	let createdFilter = $state('any'); // 'today' | 'this-week' | 'this-month' | 'any'

	// Delete modal
	let showDeleteModal = $state(false);
	let isDeleting = $state(false);
	let isCheckingBlockers = $state(false);
	let deleteTarget = $state({ id: '', name: '' });
	// FR-10: when a library can't be deleted because its items are still in
	// Knowledge Stores, we surface the blockers inside the delete modal
	// instead of bubbling a page-level error.
	let deleteError = $state('');
	/**
	 * @type {Array<{
	 *   id: string,             // encoded as `${ksId}::${itemId}` for onRemoveBlocker
	 *   name: string,           // "<item title> — in <KS name>"
	 *   itemId: string,
	 *   ksId: string,
	 *   removing: boolean
	 * }>}
	 */
	let deleteBlockers = $state([]);

	// Refs
	/** @type {any} */
	let createModal;

	// --- Filter predicates ---
	let activePredicates = $derived.by(() => {
		/** @type {Array<(item: any) => boolean>} */
		const preds = [];
		if (sharingFilter === 'my') preds.push((l) => l.is_owner !== false);
		if (sharingFilter === 'shared') preds.push((l) => l.is_shared === true);
		if (hasItemsFilter === 'with-items') preds.push((l) => (l.item_count ?? 0) > 0);
		if (hasItemsFilter === 'empty') preds.push((l) => (l.item_count ?? 0) === 0);
		if (createdFilter !== 'any') {
			const now = Date.now();
			const DAY = 86400000;
			// Use local midnight so "Today" matches the user's timezone, not UTC.
			const localMidnight = new Date();
			localMidnight.setHours(0, 0, 0, 0);
			const todayStart = localMidnight.getTime();
			/** @param {any} l */
			const ts = (l) =>
				typeof l.created_at === 'number' ? l.created_at * 1000 : Date.parse(String(l.created_at));
			if (createdFilter === 'today') {
				preds.push((l) => ts(l) >= todayStart);
			} else if (createdFilter === 'this-week') {
				preds.push((l) => now - ts(l) <= 7 * DAY);
			} else if (createdFilter === 'this-month') {
				preds.push((l) => now - ts(l) <= 30 * DAY);
			}
		}
		return preds;
	});

	// --- Active filter chips ---
	let activeChips = $derived.by(() => {
		/** @type {Array<{id: string, label: string, value: string, onClear: () => void}>} */
		const chips = [];
		if (sharingFilter !== 'all') {
			chips.push({
				id: 'sharing',
				label: $_('list.filters.sharing', { default: 'Sharing' }),
				value:
					sharingFilter === 'my'
						? $_('list.filters.my', { default: 'Mine' })
						: $_('list.filters.shared', { default: 'Shared' }),
				onClear: () => {
					sharingFilter = 'all';
					currentPage = 1;
					applyFiltersAndPagination();
				}
			});
		}
		if (hasItemsFilter !== 'any') {
			chips.push({
				id: 'hasItems',
				label: $_('list.filters.hasItems', { default: 'Items' }),
				value:
					hasItemsFilter === 'with-items'
						? $_('list.filters.withItems', { default: 'With items' })
						: $_('list.filters.empty', { default: 'Empty' }),
				onClear: () => {
					hasItemsFilter = 'any';
					currentPage = 1;
					applyFiltersAndPagination();
				}
			});
		}
		if (createdFilter !== 'any') {
			/** @type {Record<string, string>} */
			const createdLabels = {
				today: $_('list.filters.today', { default: 'Today' }),
				'this-week': $_('list.filters.thisWeek', { default: 'This week' }),
				'this-month': $_('list.filters.thisMonth', { default: 'This month' })
			};
			chips.push({
				id: 'created',
				label: $_('list.filters.created', { default: 'Created' }),
				value: createdLabels[createdFilter] || createdFilter,
				onClear: () => {
					createdFilter = 'any';
					currentPage = 1;
					applyFiltersAndPagination();
				}
			});
		}
		return chips;
	});

	// Filters array for FilterBar dropdowns
	let filterDefs = $derived([
		{
			key: 'sharing',
			label: $_('list.filters.sharing', { default: 'Sharing' }),
			options: [
				{ value: 'my', label: $_('list.filters.my', { default: 'Mine' }) },
				{ value: 'shared', label: $_('list.filters.shared', { default: 'Shared' }) }
			]
		},
		{
			key: 'hasItems',
			label: $_('list.filters.hasItems', { default: 'Has items' }),
			options: [
				{ value: 'with-items', label: $_('list.filters.withItems', { default: 'With items' }) },
				{ value: 'empty', label: $_('list.filters.empty', { default: 'Empty' }) }
			]
		},
		{
			key: 'created',
			label: $_('list.filters.created', { default: 'Created' }),
			options: [
				{ value: 'today', label: $_('list.filters.today', { default: 'Today' }) },
				{ value: 'this-week', label: $_('list.filters.thisWeek', { default: 'This week' }) },
				{ value: 'this-month', label: $_('list.filters.thisMonth', { default: 'This month' }) }
			]
		}
	]);

	let filterValues = $derived({
		sharing: sharingFilter !== 'all' ? sharingFilter : '',
		hasItems: hasItemsFilter !== 'any' ? hasItemsFilter : '',
		created: createdFilter !== 'any' ? createdFilter : ''
	});

	// Column definitions for ResizableTable
	const columns = [
		{ key: 'name', label: $_('libraries.name', { default: 'Name' }), defaultWidth: 0 },
		{ key: 'items', label: $_('libraries.items.title', { default: 'Items' }), defaultWidth: 80 },
		{
			key: 'sharing',
			label: $_('libraries.sharing.label', { default: 'Sharing' }),
			defaultWidth: 80,
			align: 'center'
		},
		{ key: 'created', label: $_('libraries.createdAt', { default: 'Created' }), defaultWidth: 145 },
		{
			key: 'actions',
			label: $_('libraries.actions', { default: 'Actions' }),
			defaultWidth: 100,
			align: 'right'
		}
	];

	let isFiltered = $derived(
		searchTerm.trim() !== '' ||
			sharingFilter !== 'all' ||
			hasItemsFilter !== 'any' ||
			createdFilter !== 'any'
	);

	let orgId = $derived(/** @type {any} */ ($user)?.organization_id || '');

	onMount(async () => {
		await loadLibraries({ paintFromCacheFirst: true });
	});

	/**
	 * Load libraries. When `paintFromCacheFirst` is set, the cached array (if
	 * any) is rendered immediately while a fresh fetch runs in the background.
	 * The skeleton is hidden for at most 300ms via a min-show guard so a fast
	 * cache hit doesn't flicker.
	 *
	 * @param {{ paintFromCacheFirst?: boolean }} [opts]
	 */
	async function loadLibraries(opts = {}) {
		error = '';
		// Skeleton min-show guard: only show the skeleton if the fetch takes
		// longer than 300ms. Cache hit or fast network = no skeleton.
		const cached = readLibrariesCache(orgId);
		if (opts.paintFromCacheFirst && cached) {
			libraries = cached.libraries;
			loading = false;
			applyFiltersAndPagination();
		} else {
			// Defer the loading flag so quick responses skip the skeleton.
			loading = true;
		}

		try {
			if (!$user.isLoggedIn) {
				error = $_('libraries.loginRequired', {
					default: 'You must be logged in to view libraries.'
				});
				return;
			}
			const fresh = await getLibraries();
			libraries = fresh;
			writeLibrariesCache(orgId, fresh);
			applyFiltersAndPagination();
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading libraries:', err);
			error = err instanceof Error ? err.message : 'Failed to load libraries';
			if (!cached) libraries = [];
		} finally {
			loading = false;
		}
	}

	function applyFiltersAndPagination() {
		const result = processListData(libraries, {
			search: searchTerm,
			searchFields: ['name', 'description', 'id'],
			filters: {},
			predicates: activePredicates,
			sortBy,
			sortOrder,
			page: currentPage,
			itemsPerPage
		});
		displayLibraries = result.items;
		totalItems = result.filteredCount;
		totalPages = result.totalPages;
		currentPage = result.currentPage;
	}

	/** @param {CustomEvent<{value: string}>} event */
	function handleSearchChange(event) {
		searchTerm = event.detail.value;
		currentPage = 1;
		applyFiltersAndPagination();
	}

	/** @param {CustomEvent<{key: string, value: string}>} event */
	function handleFilterChange(event) {
		const { key, value } = event.detail;
		if (key === 'sharing') sharingFilter = value || 'all';
		if (key === 'hasItems') hasItemsFilter = value || 'any';
		if (key === 'created') createdFilter = value || 'any';
		currentPage = 1;
		applyFiltersAndPagination();
	}

	/** @param {CustomEvent<{sortBy: string, sortOrder: 'asc'|'desc'}>} event */
	function handleSortChange(event) {
		sortBy = event.detail.sortBy;
		sortOrder = event.detail.sortOrder;
		applyFiltersAndPagination();
	}

	function handleClearFilters() {
		searchTerm = '';
		sharingFilter = 'all';
		hasItemsFilter = 'any';
		createdFilter = 'any';
		currentPage = 1;
		applyFiltersAndPagination();
	}

	function handleClearAllChips() {
		sharingFilter = 'all';
		hasItemsFilter = 'any';
		createdFilter = 'any';
		currentPage = 1;
		applyFiltersAndPagination();
	}

	/** @param {CustomEvent<{page: number}>} event */
	function handlePageChange(event) {
		currentPage = event.detail.page;
		applyFiltersAndPagination();
	}

	/** @param {CustomEvent<{itemsPerPage: number}>} event */
	function handleItemsPerPageChange(event) {
		itemsPerPage = event.detail.itemsPerPage;
		currentPage = 1;
		try {
			localStorage.setItem(LS_PAGE_SIZE, String(itemsPerPage));
		} catch {
			// ignore
		}
		applyFiltersAndPagination();
	}

	/** @param {string} id */
	function viewLibrary(id) {
		dispatch('view', { id });
	}

	// File-tree modal state
	let treeModalOpen = $state(false);
	let treeModalLibrary = $state(
		/** @type {{ id: string, name: string, isReadOnly: boolean }} */ ({
			id: '',
			name: '',
			isReadOnly: false
		})
	);

	/** @param {import('$lib/services/libraryService').Library} lib */
	function openTreeModal(lib) {
		treeModalLibrary = {
			id: lib.id,
			name: lib.name,
			isReadOnly: lib.is_owner === false
		};
		treeModalOpen = true;
	}

	/** @param {CustomEvent<{id: string, name: string}>} event */
	async function handleCreated(event) {
		toast.success(
			$_('libraries.createSuccess', {
				default: `Library "${event.detail.name}" created.`
			})
		);
		await loadLibraries();
	}

	/** @param {import('$lib/services/libraryService').Library} lib */
	async function requestDelete(lib) {
		deleteTarget = { id: lib.id, name: lib.name };
		deleteError = '';
		deleteBlockers = [];
		isCheckingBlockers = true;
		try {
			const data = await getLibraryKbLinks(lib.id);
			const ksNameById = new Map(
				(data.knowledge_stores ?? []).map((/** @type {any} */ k) => [String(k.id), k.name || k.id])
			);
			deleteBlockers = (data.items ?? []).map((/** @type {any} */ it) => {
				const itemId = String(it.id);
				const ksId = String(it.knowledge_store_id);
				return {
					id: `${ksId}::${itemId}`,
					name: `${it.title} — ${ksNameById.get(ksId) || ksId}`,
					itemId,
					ksId,
					removing: false
				};
			});
		} catch {
			deleteBlockers = [];
		} finally {
			isCheckingBlockers = false;
		}
		showDeleteModal = true;
	}

	async function handleDeleteConfirm() {
		isDeleting = true;
		deleteError = '';
		const targetId = deleteTarget.id;
		const targetName = deleteTarget.name;
		try {
			await deleteLibrary(targetId);
			showDeleteModal = false;
			deleteBlockers = [];
			// Optimistic: drop from local list + cache so the row disappears
			// instantly, then revalidate in the background.
			libraries = libraries.filter((l) => l.id !== targetId);
			removeLibraryFromCache(orgId, targetId);
			applyFiltersAndPagination();
			toast.success($_('libraries.deleteSuccess', { default: `Library "${targetName}" deleted.` }));
			loadLibraries(); // background revalidate
		} catch (/** @type {unknown} */ err) {
			deleteError = err instanceof Error ? err.message : 'Delete failed';
		} finally {
			isDeleting = false;
		}
	}

	/**
	 * Unlink a single (item, KS) blocker — the same operation the per-item
	 * delete modal performs. On success, drop the row; when the list empties,
	 * clear the error so the Confirm button reappears and the user can retry
	 * the library delete without closing the modal.
	 * @param {string} blockerId
	 */
	async function handleRemoveLibraryBlocker(blockerId) {
		const blocker = deleteBlockers.find((b) => b.id === blockerId);
		if (!blocker) return;
		deleteBlockers = deleteBlockers.map((b) => (b.id === blockerId ? { ...b, removing: true } : b));
		try {
			await removeKsContent(blocker.ksId, blocker.itemId);
			deleteBlockers = deleteBlockers.filter((b) => b.id !== blockerId);
			if (deleteBlockers.length === 0) {
				deleteError = '';
			}
		} catch (/** @type {unknown} */ e) {
			console.error('removeKsContent failed', e);
			deleteBlockers = deleteBlockers.map((b) =>
				b.id === blockerId ? { ...b, removing: false } : b
			);
			deleteError =
				e instanceof Error
					? e.message
					: $_('libraries.deleteModal.removeBlockerFailed', {
							default: 'Failed to remove from Knowledge Store.'
						});
		}
	}

	/** @param {import('$lib/services/libraryService').Library} lib */
	async function handleToggleSharing(lib) {
		if (!lib.is_owner && lib.is_owner !== undefined) return;
		const newState = !lib.is_shared;
		// Optimistic update: flip immediately, rollback on failure.
		const idx = libraries.findIndex((l) => l.id === lib.id);
		if (idx !== -1) {
			libraries[idx].is_shared = newState;
			libraries = [...libraries];
			patchLibraryInCache(orgId, lib.id, { is_shared: newState });
			applyFiltersAndPagination();
		}
		try {
			await toggleSharing(lib.id, newState);
			toast.success(
				newState
					? $_('libraries.shareSuccess', { default: 'Library shared with organization.' })
					: $_('libraries.unshareSuccess', { default: 'Library is now private.' })
			);
		} catch (/** @type {unknown} */ err) {
			// Rollback
			if (idx !== -1) {
				libraries[idx].is_shared = !newState;
				libraries = [...libraries];
				patchLibraryInCache(orgId, lib.id, { is_shared: !newState });
				applyFiltersAndPagination();
			}
			toast.error(err instanceof Error ? err.message : 'Failed to toggle sharing');
		}
	}

	/** @param {number|string|null|undefined} ts */
	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleString(undefined, {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	/** @param {import('$lib/services/libraryService').Library} lib */
	function buildMenuItems(lib) {
		/** @type {Array<{label?: string, onClick?: () => void, icon?: any, danger?: boolean, divider?: boolean}>} */
		const items = [];
		items.push({
			label: lib.is_shared
				? $_('libraries.sharing.makePrivate', { default: 'Make private' })
				: $_('libraries.sharing.share', { default: 'Share' }),
			icon: lib.is_shared ? Lock : Share2,
			onClick: () => handleToggleSharing(lib)
		});
		items.push({
			label: $_('libraries.fileTree.openTitle', { default: 'Open file tree' }),
			icon: FolderTree,
			onClick: () => openTreeModal(lib)
		});
		items.push({ divider: true });
		items.push({
			label: $_('libraries.delete', { default: 'Delete' }),
			icon: Trash2,
			danger: true,
			onClick: () => requestDelete(lib)
		});
		return items;
	}
</script>

<EntityListShell
	isLoading={loading}
	isError={!!error}
	errorMessage={error}
	isEmpty={displayLibraries.length === 0 && !loading && !error}
	{isFiltered}
	{currentPage}
	{totalPages}
	{totalItems}
	{itemsPerPage}
	filters={filterDefs}
	{filterValues}
	{activeChips}
	searchValue={searchTerm}
	searchPlaceholder={$_('list.searchPlaceholder', { default: 'Search libraries...' })}
	sortOptions={[
		{ value: 'name', label: $_('libraries.name', { default: 'Name' }) },
		{ value: 'created_at', label: $_('libraries.createdAt', { default: 'Created' }) }
	]}
	{sortBy}
	{sortOrder}
	onRetry={() => loadLibraries()}
	onSearchChange={handleSearchChange}
	onFilterChange={handleFilterChange}
	onSortChange={handleSortChange}
	onClearFilters={handleClearFilters}
	onClearAllChips={handleClearAllChips}
	onPageChange={handlePageChange}
	onItemsPerPageChange={handleItemsPerPageChange}
>
	{#snippet headerActions()}
		<Button
			variant="primary"
			iconLeftComponent={Plus}
			onclick={() => createModal.open()}
			ariaLabel={$_('libraries.createNewTitle', { default: 'Create a new Library' })}
		>
			{$_('libraries.createNew', { default: 'New Library' })}
		</Button>
	{/snippet}

	{#snippet emptyState()}
		{#if isFiltered}
			<EmptyState
				icon={BookOpen}
				title={$_('libraries.noResults', {
					default: 'No libraries match your filters.'
				})}
			/>
		{:else}
			<EmptyState
				icon={BookOpen}
				title={$_('libraries.empty.title', { default: 'No libraries yet' })}
				description={$_('libraries.empty.description', {
					default: 'Create one to start importing content.'
				})}
			>
				{#snippet actions()}
					<Button variant="primary" iconLeftComponent={Plus} onclick={() => createModal.open()}>
						{$_('libraries.createNew', { default: 'New Library' })}
					</Button>
				{/snippet}
			</EmptyState>
		{/if}
	{/snippet}

	{#snippet table()}
		<ResizableTable tableId="libraries" {columns}>
			<tbody class="divide-border bg-surface divide-y">
				{#each displayLibraries as lib (lib.id)}
					<tr class="hover:bg-surface-sunken">
						<!-- Name -->
						<td class="overflow-hidden px-4 py-2">
							<button
								type="button"
								onclick={() => viewLibrary(lib.id)}
								title={lib.name}
								class="text-brand block max-w-full cursor-pointer truncate border-0 bg-transparent p-0 text-left font-medium hover:underline"
							>
								{lib.name}
							</button>
							{#if lib.description}
								<p class="type-caption mt-0.5 truncate">{lib.description}</p>
							{/if}
						</td>
						<!-- Items -->
						<td class="type-body-muted px-4 py-2">{lib.item_count ?? 0}</td>
						<!-- Sharing badge -->
						<td class="px-4 py-2" style:text-align="center">
							{#if lib.is_owner !== false}
								<Badge
									variant={lib.is_shared ? 'success' : 'neutral'}
									icon={lib.is_shared ? Users : Lock}
								>
									{lib.is_shared
										? $_('libraries.sharing.shared', { default: 'Shared' })
										: $_('libraries.sharing.private', { default: 'Private' })}
								</Badge>
							{:else}
								<span class="type-caption">{lib.owner_name || lib.owner_email || ''}</span>
							{/if}
						</td>
						<!-- Created -->
						<td class="type-body-muted px-4 py-2">{formatDate(lib.created_at)}</td>
						<!-- Actions -->
						<td class="px-4 py-2">
							<div class="flex items-center justify-end gap-1">
								<IconButton
									icon={Eye}
									ariaLabel={`${$_('libraries.view', { default: 'View' })} ${lib.name}`}
									tooltip={$_('libraries.view', { default: 'View' })}
									variant="ghost"
									size="sm"
									onclick={() => viewLibrary(lib.id)}
								/>
								{#if lib.is_owner !== false}
									<OverflowMenu
										items={buildMenuItems(lib)}
										ariaLabel={$_('list.moreActions', { default: 'More actions' })}
										tooltip={$_('list.moreActions', { default: 'More actions' })}
										size="sm"
									/>
								{/if}
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</ResizableTable>
	{/snippet}
</EntityListShell>

<CreateLibraryModal bind:this={createModal} on:created={handleCreated} />

<ConfirmationModal
	bind:isOpen={showDeleteModal}
	isLoading={isDeleting || isCheckingBlockers}
	title={$_('libraries.deleteModal.title', { default: 'Delete Library' })}
	message={deleteBlockers.length > 0
		? $_('libraries.deleteModal.blockedMessage', {
				default:
					'These items are still linked to Knowledge Stores. Remove them first, then the library can be deleted.'
			})
		: $_('libraries.deleteModal.message', {
				default: `Delete library "${deleteTarget.name}"? This action cannot be undone. All items inside will be permanently removed.`,
				values: { name: deleteTarget.name }
			})}
	confirmText={$_('libraries.deleteModal.confirm', { default: 'Delete' })}
	cancelText={deleteBlockers.length > 0
		? $_('common.close', { default: 'Close' })
		: $_('common.cancel', { default: 'Cancel' })}
	variant="danger"
	error={deleteError}
	blockers={deleteBlockers}
	blockersTitle={$_('libraries.deleteModal.blockersTitle', {
		default: 'Items linked to Knowledge Stores'
	})}
	blockerRemoveLabel={$_('libraries.deleteModal.removeFromKs', {
		default: 'Remove from KS'
	})}
	hideConfirm={deleteBlockers.length > 0}
	onRemoveBlocker={handleRemoveLibraryBlocker}
	onconfirm={handleDeleteConfirm}
	oncancel={() => {
		showDeleteModal = false;
		deleteError = '';
		deleteBlockers = [];
	}}
/>

<FileTreeModal
	bind:isOpen={treeModalOpen}
	libraryId={treeModalLibrary.id}
	libraryName={treeModalLibrary.name}
	isReadOnly={treeModalLibrary.isReadOnly}
	onclose={() => (treeModalOpen = false)}
/>
