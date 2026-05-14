<!--
  @component KnowledgeStoresList
  Displays Knowledge Stores with combinable filter chips, resizable columns,
  skeleton loading, icon-button actions, and localStorage-persisted page size.
-->
<script>
	import { onMount, createEventDispatcher } from 'svelte';
	import {
		getKnowledgeStores,
		deleteKnowledgeStore,
		toggleSharing
	} from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { processListData } from '$lib/utils/listHelpers';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import CreateKnowledgeStoreModal from '$lib/components/modals/CreateKnowledgeStoreModal.svelte';
	import AddContentToKSModal from '$lib/components/knowledgeStores/AddContentToKSModal.svelte';
	import IngestionProgressModal from '$lib/components/knowledgeStores/IngestionProgressModal.svelte';
	import EntityListShell from '$lib/components/common/EntityListShell.svelte';
	import ResizableTable from '$lib/components/common/ResizableTable.svelte';

	const dispatch = createEventDispatcher();

	const LS_PAGE_SIZE = 'lamb.list.knowledgeStores.itemsPerPage';

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

	/** @type {import('$lib/services/knowledgeStoreService').KnowledgeStore[]} */
	let stores = $state([]);
	/** @type {import('$lib/services/knowledgeStoreService').KnowledgeStore[]} */
	let displayStores = $state([]);
	let loading = $state(true);
	let error = $state('');
	let successMessage = $state('');

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
	let embeddingFilter = $state('any'); // 'openai' | 'ollama' | 'local' | 'any'
	let chunkingFilter = $state('any'); // 'simple' | 'hierarchical' | 'by_page' | 'by_section' | 'any'
	let contentFilter = $state('any'); // 'empty' | 'has-content' | 'any'
	let createdFilter = $state('any'); // 'today' | 'this-week' | 'this-month' | 'any'

	// Delete modal
	let showDeleteModal = $state(false);
	let isDeleting = $state(false);
	let deleteTarget = $state({ id: '', name: '' });

	let showAddContentModal = $state(false);
	let addContentKsId = $state('');

	let showProgressModal = $state(false);
	let progressKsId = $state('');
	let progressKsName = $state('');
	/** @type {Array<{ id: string, title: string }>} */
	let progressItems = $state([]);

	// Overflow menu state
	let openMenuId = $state(/** @type {string|null} */ (null));

	// Create modal handle — replaces the dispatch('createWithInitialState')
	// flow that opened the full multi-step wizard, in favor of the simple
	// CreateLibraryModal-style single-page form.
	/** @type {any} */
	let createModal;

	// Column definitions for ResizableTable
	const columns = [
		{ key: 'name', label: $_('knowledgeStores.name', { default: 'Name' }), defaultWidth: 200 },
		{
			key: 'embedding',
			label: $_('knowledgeStores.embedding', { default: 'Embedding' }),
			defaultWidth: 120
		},
		{
			key: 'chunking',
			label: $_('knowledgeStores.chunking', { default: 'Chunking' }),
			defaultWidth: 120
		},
		{
			key: 'content',
			label: $_('knowledgeStores.contentCount', { default: 'Content' }),
			defaultWidth: 80
		},
		{
			key: 'sharing',
			label: $_('knowledgeStores.sharing.label', { default: 'Sharing' }),
			defaultWidth: 100
		},
		{
			key: 'created',
			label: $_('knowledgeStores.createdAt', { default: 'Created' }),
			defaultWidth: 100
		},
		{
			key: 'actions',
			label: $_('knowledgeStores.actions', { default: 'Actions' }),
			defaultWidth: 80
		}
	];

	// --- Filter predicates ---
	let activePredicates = $derived(() => {
		/** @type {Array<(item: any) => boolean>} */
		const preds = [];
		if (sharingFilter === 'my') preds.push((s) => s.is_owner !== false && !s.is_shared);
		if (sharingFilter === 'shared') preds.push((s) => s.is_shared === true);
		if (embeddingFilter !== 'any') {
			preds.push((s) => (s.embedding_vendor || '').toLowerCase() === embeddingFilter);
		}
		if (chunkingFilter !== 'any') {
			preds.push((s) => (s.chunking_strategy || '') === chunkingFilter);
		}
		if (contentFilter === 'empty') preds.push((s) => (s.content_count ?? 0) === 0);
		if (contentFilter === 'has-content') preds.push((s) => (s.content_count ?? 0) > 0);
		if (createdFilter !== 'any') {
			const now = Date.now();
			const DAY = 86400000;
			const todayStart = now - (now % DAY);
			if (createdFilter === 'today') {
				preds.push((s) => {
					const t =
						typeof s.created_at === 'number'
							? s.created_at * 1000
							: Date.parse(String(s.created_at));
					return t >= todayStart;
				});
			} else if (createdFilter === 'this-week') {
				preds.push((s) => {
					const t =
						typeof s.created_at === 'number'
							? s.created_at * 1000
							: Date.parse(String(s.created_at));
					return now - t <= 7 * DAY;
				});
			} else if (createdFilter === 'this-month') {
				preds.push((s) => {
					const t =
						typeof s.created_at === 'number'
							? s.created_at * 1000
							: Date.parse(String(s.created_at));
					return now - t <= 30 * DAY;
				});
			}
		}
		return preds;
	});

	// --- Active filter chips ---
	let activeChips = $derived(() => {
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
		if (embeddingFilter !== 'any') {
			chips.push({
				id: 'embedding',
				label: $_('list.filters.embedding', { default: 'Embedding' }),
				value: embeddingFilter,
				onClear: () => {
					embeddingFilter = 'any';
					currentPage = 1;
					applyFiltersAndPagination();
				}
			});
		}
		if (chunkingFilter !== 'any') {
			chips.push({
				id: 'chunking',
				label: $_('list.filters.chunking', { default: 'Chunking' }),
				value: chunkingFilter,
				onClear: () => {
					chunkingFilter = 'any';
					currentPage = 1;
					applyFiltersAndPagination();
				}
			});
		}
		if (contentFilter !== 'any') {
			chips.push({
				id: 'content',
				label: $_('list.filters.content', { default: 'Content' }),
				value:
					contentFilter === 'empty'
						? $_('list.filters.empty', { default: 'Empty' })
						: $_('list.filters.hasContent', { default: 'Has content' }),
				onClear: () => {
					contentFilter = 'any';
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
			key: 'embedding',
			label: $_('list.filters.embedding', { default: 'Embedding' }),
			options: [
				{ value: 'openai', label: 'OpenAI' },
				{ value: 'ollama', label: 'Ollama' },
				{ value: 'local', label: $_('list.filters.local', { default: 'Local' }) }
			]
		},
		{
			key: 'chunking',
			label: $_('list.filters.chunking', { default: 'Chunking' }),
			options: [
				{ value: 'simple', label: $_('list.filters.chunkingSimple', { default: 'Simple' }) },
				{
					value: 'hierarchical',
					label: $_('list.filters.chunkingHierarchical', { default: 'Hierarchical' })
				},
				{ value: 'by_page', label: $_('list.filters.chunkingByPage', { default: 'By page' }) },
				{
					value: 'by_section',
					label: $_('list.filters.chunkingBySection', { default: 'By section' })
				}
			]
		},
		{
			key: 'content',
			label: $_('list.filters.content', { default: 'Content' }),
			options: [
				{ value: 'empty', label: $_('list.filters.empty', { default: 'Empty' }) },
				{ value: 'has-content', label: $_('list.filters.hasContent', { default: 'Has content' }) }
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
		embedding: embeddingFilter !== 'any' ? embeddingFilter : '',
		chunking: chunkingFilter !== 'any' ? chunkingFilter : '',
		content: contentFilter !== 'any' ? contentFilter : '',
		created: createdFilter !== 'any' ? createdFilter : ''
	});

	let isFiltered = $derived(
		searchTerm.trim() !== '' ||
			sharingFilter !== 'all' ||
			embeddingFilter !== 'any' ||
			chunkingFilter !== 'any' ||
			contentFilter !== 'any' ||
			createdFilter !== 'any'
	);

	onMount(async () => {
		await loadStores();
	});

	export async function refresh() {
		await loadStores();
	}

	async function loadStores() {
		loading = true;
		error = '';
		try {
			if (!$user.isLoggedIn) {
				error = $_('knowledgeStores.loginRequired', {
					default: 'You must be logged in to view Knowledge Stores.'
				});
				return;
			}
			stores = (await getKnowledgeStores()) || [];
			applyFiltersAndPagination();
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading Knowledge Stores:', err);
			error = err instanceof Error ? err.message : 'Failed to load Knowledge Stores';
			stores = [];
		} finally {
			loading = false;
		}
	}

	function applyFiltersAndPagination() {
		const result = processListData(stores, {
			search: searchTerm,
			searchFields: ['name', 'description', 'id', 'embedding_vendor', 'embedding_model'],
			filters: {},
			predicates: activePredicates(),
			sortBy,
			sortOrder,
			page: currentPage,
			itemsPerPage
		});
		displayStores = result.items;
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
		if (key === 'embedding') embeddingFilter = value || 'any';
		if (key === 'chunking') chunkingFilter = value || 'any';
		if (key === 'content') contentFilter = value || 'any';
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
		embeddingFilter = 'any';
		chunkingFilter = 'any';
		contentFilter = 'any';
		createdFilter = 'any';
		currentPage = 1;
		applyFiltersAndPagination();
	}

	function handleClearAllChips() {
		sharingFilter = 'all';
		embeddingFilter = 'any';
		chunkingFilter = 'any';
		contentFilter = 'any';
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
	function viewStore(id) {
		dispatch('view', { id });
	}

	/** @param {string} msg */
	function showSuccess(msg) {
		successMessage = msg;
		setTimeout(() => {
			successMessage = '';
		}, 4000);
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	function openAddContent(ks) {
		addContentKsId = ks.id;
		showAddContentModal = true;
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	function requestDelete(ks) {
		deleteTarget = { id: ks.id, name: ks.name };
		showDeleteModal = true;
	}

	async function handleDeleteConfirm() {
		isDeleting = true;
		try {
			await deleteKnowledgeStore(deleteTarget.id);
			showDeleteModal = false;
			showSuccess(
				$_('knowledgeStores.deleteSuccess', {
					default: `Knowledge Store "${deleteTarget.name}" deleted.`
				})
			);
			await loadStores();
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Delete failed';
		} finally {
			isDeleting = false;
		}
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	async function handleToggleSharing(ks) {
		if (!ks.is_owner && ks.is_owner !== undefined) return;
		const newState = !ks.is_shared;
		openMenuId = null;
		try {
			await toggleSharing(ks.id, newState);
			const idx = stores.findIndex((s) => s.id === ks.id);
			if (idx !== -1) stores[idx].is_shared = newState;
			stores = [...stores];
			applyFiltersAndPagination();
			showSuccess(
				newState
					? $_('knowledgeStores.shareSuccess', {
							default: 'Knowledge Store shared with organization.'
						})
					: $_('knowledgeStores.unshareSuccess', {
							default: 'Knowledge Store is now private.'
						})
			);
		} catch (/** @type {unknown} */ err) {
			error = err instanceof Error ? err.message : 'Failed to toggle sharing';
		}
	}

	/** @param {number|string|null|undefined} ts */
	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleDateString(undefined, {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	/** @param {string} id */
	function toggleMenu(id) {
		openMenuId = openMenuId === id ? null : id;
	}

	/** @param {CustomEvent<{id: string, name: string}>} event */
	async function handleCreated(event) {
		showSuccess(
			$_('knowledgeStores.createSuccess', {
				default: `Knowledge Store "${event.detail.name}" created.`
			})
		);
		await loadStores();
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
	isEmpty={displayStores.length === 0 && !loading && !error}
	{isFiltered}
	{currentPage}
	{totalPages}
	{totalItems}
	{itemsPerPage}
	filters={filterDefs}
	{filterValues}
	activeChips={activeChips()}
	searchValue={searchTerm}
	searchPlaceholder={$_('list.searchPlaceholder', { default: 'Search knowledge stores...' })}
	sortOptions={[
		{ value: 'name', label: $_('knowledgeStores.name', { default: 'Name' }) },
		{ value: 'created_at', label: $_('knowledgeStores.createdAt', { default: 'Created' }) }
	]}
	{sortBy}
	{sortOrder}
	onRetry={loadStores}
	onSearchChange={handleSearchChange}
	onFilterChange={handleFilterChange}
	onSortChange={handleSortChange}
	onClearFilters={handleClearFilters}
	onClearAllChips={handleClearAllChips}
	onPageChange={handlePageChange}
	onItemsPerPageChange={handleItemsPerPageChange}
>
	{#snippet headerActions()}
		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={() => createModal?.open()}
				title={$_('knowledgeStores.createNewTitle', {
					default: 'Create a Knowledge Store from existing library content'
				})}
				class="inline-flex items-center rounded-md bg-[#2271b3] px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91]"
			>
				+ {$_('knowledgeStores.createNew', { default: 'New Knowledge Store' })}
			</button>
		</div>
	{/snippet}

	{#snippet emptyState()}
		<p class="text-sm font-medium text-gray-700">
			{isFiltered
				? $_('knowledgeStores.noResults', { default: 'No Knowledge Stores match your filters.' })
				: $_('knowledgeStores.noOwned', {
						default:
							'You have no Knowledge Stores yet. Create one to start indexing library content.'
					})}
		</p>
		{#if !isFiltered}
			<button
				type="button"
				onclick={() => createModal?.open()}
				title={$_('knowledgeStores.createNewTitle', {
					default: 'Create a Knowledge Store from existing library content'
				})}
				class="mt-4 inline-flex items-center rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91]"
			>
				+ {$_('knowledgeStores.createNew', { default: 'New Knowledge Store' })}
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
		<ResizableTable tableId="knowledgeStores" {columns}>
			<tbody class="divide-y divide-gray-200 bg-white">
				{#each displayStores as ks, rowIdx (ks.id)}
					<tr class="hover:bg-gray-50">
						<!-- Name -->
						<td class="overflow-hidden px-4 py-2">
							<button
								type="button"
								onclick={() => viewStore(ks.id)}
								class="block max-w-full cursor-pointer truncate border-0 bg-transparent p-0 text-left font-medium text-[#2271b3] hover:underline"
							>
								{ks.name}
							</button>
							{#if ks.description}
								<p class="mt-0.5 truncate text-xs text-gray-500">{ks.description}</p>
							{/if}
						</td>
						<!-- Embedding -->
						<td class="overflow-hidden px-4 py-2 text-xs text-gray-600">
							<div class="truncate">{ks.embedding_vendor}</div>
							<div class="truncate text-gray-400">{ks.embedding_model}</div>
						</td>
						<!-- Chunking -->
						<td class="truncate px-4 py-2 text-xs text-gray-600">{ks.chunking_strategy}</td>
						<!-- Content count -->
						<td class="px-4 py-2 text-sm text-gray-500">{ks.content_count ?? 0}</td>
						<!-- Sharing badge -->
						<td class="px-4 py-2">
							{#if ks.is_owner !== false}
								<span
									class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {ks.is_shared
										? 'bg-green-100 text-green-700'
										: 'bg-gray-100 text-gray-600'}"
								>
									{ks.is_shared
										? $_('knowledgeStores.sharing.shared', { default: 'Shared' })
										: $_('knowledgeStores.sharing.private', { default: 'Private' })}
								</span>
							{:else}
								<span class="text-xs text-gray-400">{ks.owner_name || ks.owner_email || ''}</span>
							{/if}
						</td>
						<!-- Created -->
						<td class="px-4 py-2 text-sm text-gray-500">{formatDate(ks.created_at)}</td>
						<!-- Actions -->
						<td class="px-4 py-2">
							<div class="flex items-center justify-end gap-1">
								<!-- View icon button -->
								<button
									type="button"
									onclick={() => viewStore(ks.id)}
									title={$_('knowledgeStores.view', { default: 'View' })}
									aria-label="{$_('knowledgeStores.view', { default: 'View' })} {ks.name}"
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

								<!-- Add content -->
								{#if ks.is_owner !== false}
									<button
										type="button"
										onclick={() => openAddContent(ks)}
										title={$_('knowledgeStores.addContent', { default: 'Add Content' })}
										aria-label="{$_('knowledgeStores.addContent', { default: 'Add Content' })} to {ks.name}"
										class="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
									>
										<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												stroke-width="2"
												d="M12 4v16m8-8H4"
											/>
										</svg>
									</button>
								{/if}

								<!-- Overflow menu -->
								{#if ks.is_owner !== false}
									<div class="relative" data-overflow-menu>
										<button
											type="button"
											onclick={() => toggleMenu(ks.id)}
											title={$_('list.moreActions', { default: 'More actions' })}
											aria-label="{$_('list.moreActions', {
												default: 'More actions'
											})} for {ks.name}"
											class="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
										>
											<svg class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
												<path
													d="M12 5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM12 13.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM12 22a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"
												/>
											</svg>
										</button>
										{#if openMenuId === ks.id}
											<div
												class="absolute right-0 z-10 w-44 rounded-md border border-gray-200 bg-white shadow-lg {rowIdx >=
												displayStores.length - 2
													? 'bottom-full mb-1'
													: 'top-full mt-1'}"
												data-overflow-menu
											>
												<button
													type="button"
													onclick={() => handleToggleSharing(ks)}
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
													{ks.is_shared
														? $_('knowledgeStores.sharing.makePrivate', { default: 'Make private' })
														: $_('knowledgeStores.sharing.share', { default: 'Share' })}
												</button>
												<hr class="border-gray-100" />
												<button
													type="button"
													onclick={() => {
														openMenuId = null;
														requestDelete(ks);
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
													{$_('knowledgeStores.delete', { default: 'Delete' })}
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

<CreateKnowledgeStoreModal bind:this={createModal} on:created={handleCreated} />

<AddContentToKSModal
	bind:isOpen={showAddContentModal}
	ksId={addContentKsId}
	on:done={(e) => {
		showAddContentModal = false;
		progressKsId = e.detail.ksId;
		progressKsName = stores.find((s) => s.id === e.detail.ksId)?.name ?? '';
		progressItems = e.detail.items ?? [];
		showProgressModal = true;
	}}
	on:close={() => { showAddContentModal = false; }}
/>

<IngestionProgressModal
	bind:isOpen={showProgressModal}
	ksId={progressKsId}
	ksName={progressKsName}
	items={progressItems}
	onclose={loadStores}
/>

<ConfirmationModal
	bind:isOpen={showDeleteModal}
	bind:isLoading={isDeleting}
	title={$_('knowledgeStores.deleteModal.title', { default: 'Delete Knowledge Store' })}
	message={$_('knowledgeStores.deleteModal.message', {
		default: `Are you sure you want to delete "${deleteTarget.name}"? All vectors will be permanently removed. The library items will not be affected.`
	})}
	confirmText={$_('knowledgeStores.deleteModal.confirm', { default: 'Delete' })}
	variant="danger"
	onconfirm={handleDeleteConfirm}
	oncancel={() => {
		showDeleteModal = false;
	}}
/>
