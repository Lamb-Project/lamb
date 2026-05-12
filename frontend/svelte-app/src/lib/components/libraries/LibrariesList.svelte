<!--
  @component LibrariesList
  Displays libraries with combinable filter chips, resizable columns,
  skeleton loading, icon-button actions, and localStorage-persisted page size.
-->
<script>
	import { onMount, createEventDispatcher } from 'svelte';
	import { getLibraries, deleteLibrary, toggleSharing } from '$lib/services/libraryService';
	import { removeContent as removeKsContent } from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { processListData } from '$lib/utils/listHelpers';
	import CreateLibraryModal from '$lib/components/modals/CreateLibraryModal.svelte';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import EntityListShell from '$lib/components/common/EntityListShell.svelte';
	import ResizableTable from '$lib/components/common/ResizableTable.svelte';

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
	let successMessage = $state('');

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

	// Overflow menu state (sharing toggle)
	let openMenuId = $state(/** @type {string|null} */ (null));

	// Refs
	/** @type {any} */
	let createModal;

	// --- Filter predicates ---
	let activePredicates = $derived.by(() => {
		/** @type {Array<(item: any) => boolean>} */
		const preds = [];
		if (sharingFilter === 'my') preds.push((l) => l.is_owner !== false);
		if (sharingFilter === 'shared') preds.push((l) => l.is_owner === false);
		if (hasItemsFilter === 'with-items') preds.push((l) => (l.item_count ?? 0) > 0);
		if (hasItemsFilter === 'empty') preds.push((l) => (l.item_count ?? 0) === 0);
		if (createdFilter !== 'any') {
			const now = Date.now();
			const DAY = 86400000;
			const todayStart = now - (now % DAY);
			if (createdFilter === 'today') {
				preds.push((l) => {
					const t =
						typeof l.created_at === 'number'
							? l.created_at * 1000
							: Date.parse(String(l.created_at));
					return t >= todayStart;
				});
			} else if (createdFilter === 'this-week') {
				preds.push((l) => {
					const t =
						typeof l.created_at === 'number'
							? l.created_at * 1000
							: Date.parse(String(l.created_at));
					return now - t <= 7 * DAY;
				});
			} else if (createdFilter === 'this-month') {
				preds.push((l) => {
					const t =
						typeof l.created_at === 'number'
							? l.created_at * 1000
							: Date.parse(String(l.created_at));
					return now - t <= 30 * DAY;
				});
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
		{ key: 'name', label: $_('libraries.name', { default: 'Name' }), defaultWidth: 260 },
		{ key: 'items', label: $_('libraries.items.title', { default: 'Items' }), defaultWidth: 80 },
		{
			key: 'sharing',
			label: $_('libraries.sharing.label', { default: 'Sharing' }),
			defaultWidth: 120
		},
		{ key: 'created', label: $_('libraries.createdAt', { default: 'Created' }), defaultWidth: 120 },
		{ key: 'actions', label: $_('libraries.actions', { default: 'Actions' }), defaultWidth: 100 }
	];

	let isFiltered = $derived(
		searchTerm.trim() !== '' ||
			sharingFilter !== 'all' ||
			hasItemsFilter !== 'any' ||
			createdFilter !== 'any'
	);

	onMount(async () => {
		await loadLibraries();
	});

	async function loadLibraries() {
		loading = true;
		error = '';
		try {
			if (!$user.isLoggedIn) {
				error = $_('libraries.loginRequired', {
					default: 'You must be logged in to view libraries.'
				});
				return;
			}
			libraries = await getLibraries();
			applyFiltersAndPagination();
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading libraries:', err);
			error = err instanceof Error ? err.message : 'Failed to load libraries';
			libraries = [];
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

	/** @param {string} msg */
	function showSuccess(msg) {
		successMessage = msg;
		setTimeout(() => {
			successMessage = '';
		}, 4000);
	}

	/** @param {CustomEvent<{id: string, name: string}>} event */
	async function handleCreated(event) {
		showSuccess(
			$_('libraries.createSuccess', { default: `Library "${event.detail.name}" created.` })
		);
		await loadLibraries();
	}

	/** @param {import('$lib/services/libraryService').Library} lib */
	function requestDelete(lib) {
		deleteTarget = { id: lib.id, name: lib.name };
		deleteError = '';
		deleteBlockers = [];
		showDeleteModal = true;
	}

	async function handleDeleteConfirm() {
		isDeleting = true;
		deleteError = '';
		try {
			await deleteLibrary(deleteTarget.id);
			showDeleteModal = false;
			deleteBlockers = [];
			showSuccess(
				$_('libraries.deleteSuccess', { default: `Library "${deleteTarget.name}" deleted.` })
			);
			await loadLibraries();
		} catch (/** @type {unknown} */ err) {
			// FR-10: backend returns 409 when items in the library are still
			// referenced by Knowledge Stores. Render the blockers inside the
			// modal so the user can remove them one by one and retry.
			const isAxios = !!(err && typeof err === 'object' && /** @type {any} */ (err).isAxiosError);
			const status = isAxios ? /** @type {any} */ (err).response?.status : null;
			const detail = isAxios ? /** @type {any} */ (err).response?.data?.detail : null;
			if (status === 409 && detail && typeof detail === 'object') {
				deleteError =
					typeof detail.message === 'string'
						? detail.message
						: $_('libraries.deleteModal.blockedMessage', {
								default:
									'This library cannot be deleted: some items are still referenced by Knowledge Stores. Remove them from each Knowledge Store first.'
							});
				const ksNameById = new Map();
				const ksList = Array.isArray(detail.knowledge_stores) ? detail.knowledge_stores : [];
				for (const k of ksList) {
					if (k?.id) ksNameById.set(String(k.id), k?.name || k?.id);
				}
				const items = Array.isArray(detail.items) ? detail.items : [];
				deleteBlockers = items.map((/** @type {any} */ it) => {
					const itemId = String(it?.id || '');
					const ksId = String(it?.knowledge_store_id || '');
					const title = it?.title || itemId || 'Untitled item';
					const ksName = ksNameById.get(ksId) || ksId || 'Knowledge Store';
					return {
						id: `${ksId}::${itemId}`,
						name: `${title} — ${ksName}`,
						itemId,
						ksId,
						removing: false
					};
				});
			} else {
				// Non-409 errors: surface in the modal too, not in the page
				// background, so the modal stays the single source of truth.
				deleteError = err instanceof Error ? err.message : 'Delete failed';
			}
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
		deleteBlockers = deleteBlockers.map((b) =>
			b.id === blockerId ? { ...b, removing: true } : b
		);
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
		openMenuId = null;
		try {
			await toggleSharing(lib.id, newState);
			const idx = libraries.findIndex((l) => l.id === lib.id);
			if (idx !== -1) libraries[idx].is_shared = newState;
			libraries = [...libraries];
			applyFiltersAndPagination();
			showSuccess(
				newState
					? $_('libraries.shareSuccess', { default: 'Library shared with organization.' })
					: $_('libraries.unshareSuccess', { default: 'Library is now private.' })
			);
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to toggle sharing';
		}
	}

	/** @param {number|string|null|undefined} ts */
	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
	}

	/** @param {string} id */
	function toggleMenu(id) {
		openMenuId = openMenuId === id ? null : id;
	}
</script>

<!-- Close overflow menu on outside click -->
<svelte:window
	onclick={(e) => {
		if (!(/** @type {Element} */ (e.target)?.closest?.('[data-overflow-menu]'))) openMenuId = null;
	}}
/>

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
	activeChips={activeChips}
	searchValue={searchTerm}
	searchPlaceholder={$_('list.searchPlaceholder', { default: 'Search libraries...' })}
	sortOptions={[
		{ value: 'name', label: $_('libraries.name', { default: 'Name' }) },
		{ value: 'created_at', label: $_('libraries.createdAt', { default: 'Created' }) }
	]}
	{sortBy}
	{sortOrder}
	onRetry={loadLibraries}
	onSearchChange={handleSearchChange}
	onFilterChange={handleFilterChange}
	onSortChange={handleSortChange}
	onClearFilters={handleClearFilters}
	onClearAllChips={handleClearAllChips}
	onPageChange={handlePageChange}
	onItemsPerPageChange={handleItemsPerPageChange}
>
	{#snippet headerActions()}
		<button
			type="button"
			onclick={() => createModal.open()}
			title={$_('libraries.createNewTitle', {
				default: 'Create a new Library'
			})}
			class="inline-flex items-center rounded-md bg-[#2271b3] px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91]"
		>
			+ {$_('libraries.createNew', { default: 'New Library' })}
		</button>
	{/snippet}

	{#snippet emptyState()}
		<p class="text-sm font-medium text-gray-700">
			{isFiltered
				? $_('libraries.noResults', { default: 'No libraries match your filters.' })
				: $_('libraries.noOwned', {
						default: 'You have no libraries yet. Create one to get started!'
					})}
		</p>
		{#if !isFiltered}
			<button
				type="button"
				onclick={() => createModal.open()}
				class="mt-4 inline-flex items-center rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91]"
			>
				+ {$_('libraries.createNew', { default: 'New Library' })}
			</button>
		{/if}
	{/snippet}

	{#snippet table()}
		{#if successMessage}
			<div
				class="border-b border-green-100 bg-green-50 px-4 py-3 text-sm text-green-700"
				role="status"
			>
				{successMessage}
			</div>
		{/if}
		<ResizableTable tableId="libraries" {columns}>
			<tbody class="divide-y divide-gray-200 bg-white">
				{#each displayLibraries as lib, rowIdx (lib.id)}
					<tr class="hover:bg-gray-50">
						<!-- Name -->
						<td class="overflow-hidden px-4 py-2">
							<button
								type="button"
								onclick={() => viewLibrary(lib.id)}
								class="block max-w-full cursor-pointer truncate border-0 bg-transparent p-0 text-left font-medium text-[#2271b3] hover:underline"
							>
								{lib.name}
							</button>
							{#if lib.description}
								<p class="mt-0.5 truncate text-xs text-gray-500">{lib.description}</p>
							{/if}
						</td>
						<!-- Items -->
						<td class="px-4 py-2 text-sm text-gray-500">{lib.item_count ?? 0}</td>
						<!-- Sharing badge -->
						<td class="px-4 py-2">
							{#if lib.is_owner !== false}
								<span
									class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {lib.is_shared
										? 'bg-green-100 text-green-700'
										: 'bg-gray-100 text-gray-600'}"
								>
									{lib.is_shared
										? $_('libraries.sharing.shared', { default: 'Shared' })
										: $_('libraries.sharing.private', { default: 'Private' })}
								</span>
							{:else}
								<span class="text-xs text-gray-400">{lib.owner_name || lib.owner_email || ''}</span>
							{/if}
						</td>
						<!-- Created -->
						<td class="px-4 py-2 text-sm text-gray-500">{formatDate(lib.created_at)}</td>
						<!-- Actions -->
						<td class="px-4 py-2">
							<div class="flex items-center justify-end gap-1">
								<!-- View icon button -->
								<button
									type="button"
									onclick={() => viewLibrary(lib.id)}
									title={$_('libraries.view', { default: 'View' })}
									aria-label="{$_('libraries.view', { default: 'View' })} {lib.name}"
									class="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-[#2271b3]"
								>
									<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
										/>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
										/>
									</svg>
								</button>

								<!-- Overflow menu (share + delete) -->
								{#if lib.is_owner !== false}
									<div class="relative" data-overflow-menu>
										<button
											type="button"
											onclick={() => toggleMenu(lib.id)}
											title={$_('list.moreActions', { default: 'More actions' })}
											aria-label="{$_('list.moreActions', {
												default: 'More actions'
											})} for {lib.name}"
											class="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
										>
											<svg class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
												<path
													d="M12 5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM12 13.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM12 22a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"
												/>
											</svg>
										</button>
										{#if openMenuId === lib.id}
											<div
												class="absolute right-0 z-10 w-40 rounded-md border border-gray-200 bg-white shadow-lg {rowIdx >=
												displayLibraries.length - 2
													? 'bottom-full mb-1'
													: 'top-full mt-1'}"
												data-overflow-menu
											>
												<button
													type="button"
													onclick={() => handleToggleSharing(lib)}
													class="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
												>
													<svg
														class="h-4 w-4"
														fill="none"
														stroke="currentColor"
														viewBox="0 0 24 24"
													>
														<path
															stroke-linecap="round"
															stroke-linejoin="round"
															stroke-width="2"
															d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
														/>
													</svg>
													{lib.is_shared
														? $_('libraries.sharing.makePrivate', { default: 'Make private' })
														: $_('libraries.sharing.share', { default: 'Share' })}
												</button>
												<hr class="border-gray-100" />
												<button
													type="button"
													onclick={() => {
														openMenuId = null;
														requestDelete(lib);
													}}
													class="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
												>
													<svg
														class="h-4 w-4"
														fill="none"
														stroke="currentColor"
														viewBox="0 0 24 24"
													>
														<path
															stroke-linecap="round"
															stroke-linejoin="round"
															stroke-width="2"
															d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
														/>
													</svg>
													{$_('libraries.delete', { default: 'Delete' })}
												</button>
											</div>
										{/if}
									</div>
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
	bind:isLoading={isDeleting}
	title={$_('libraries.deleteModal.title', { default: 'Delete Library' })}
	message={$_('libraries.deleteModal.message', {
		default: `Are you sure you want to delete "${deleteTarget.name}"? All content will be permanently removed.`
	})}
	confirmText={$_('libraries.deleteModal.confirm', { default: 'Delete' })}
	cancelText={deleteBlockers.length > 0
		? $_('common.close', { default: 'Close' })
		: $_('common.cancel', { default: 'Cancel' })}
	variant="danger"
	error={deleteError}
	blockers={deleteBlockers}
	blockersTitle={$_('libraries.deleteModal.blockersTitle', {
		default: 'Items blocking deletion'
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
