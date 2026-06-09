<!--
  @component KnowledgeStoresList
  Displays Knowledge Stores with combinable filter chips, skeleton
  loading, canonical IconButton actions, and localStorage-persisted
  page size.

  Phase C consistency contract:
    * 5 columns (Name, Items, Sharing, Created, Actions). Embedding /
      Chunking / Vector DB / Total chunks move into a row-expansion row.
    * Action group: <IconButton icon={Eye}> + <OverflowMenu> with
      [Add content, Share, divider, Delete (danger)] — mirrors
      LibrariesList exactly.
    * Toast notifications replace inline success banner.
    * Paint-from-cache on mount, optimistic share toggle / delete with
      rollback + toast on failure.
    * `<Badge variant="warning" icon={AlertCircle}>Empty</Badge>` when
      `content_count === 0`.
-->
<script>
	import { onMount, createEventDispatcher } from 'svelte';
	import { slide } from 'svelte/transition';
	import { cubicInOut } from 'svelte/easing';
	import {
		getKnowledgeStores,
		deleteKnowledgeStore,
		toggleSharing
	} from '$lib/services/knowledgeStoreService';
	import { _ } from '$lib/i18n';
	import { user } from '$lib/stores/userStore';
	import { processListData } from '$lib/utils/listHelpers';
	import { toast } from '$lib/stores/toast.js';
	import {
		readKsCache,
		writeKsCache,
		patchKsInCache,
		removeKsFromCache
	} from '$lib/stores/ksCache.js';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
	import CreateKnowledgeStoreModal from '$lib/components/modals/CreateKnowledgeStoreModal.svelte';
	import AddContentToKSModal from '$lib/components/knowledgeStores/AddContentToKSModal.svelte';
	import IngestionProgressModal from '$lib/components/knowledgeStores/IngestionProgressModal.svelte';
	import EntityListShell from '$lib/components/common/EntityListShell.svelte';
	import ResizableTable from '$lib/components/common/ResizableTable.svelte';
	import { Button, IconButton, OverflowMenu, Badge, EmptyState } from '$lib/components/ui';
	import {
		Plus,
		Eye,
		Trash2,
		Share2,
		Users,
		Lock,
		Database,
		AlertCircle,
		ChevronRight,
		Loader2
	} from '$lib/components/ui/icons.js';

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
	let deleteError = $state('');

	let showAddContentModal = $state(false);
	let addContentKsId = $state('');

	let showProgressModal = $state(false);
	let progressKsId = $state('');
	let progressKsName = $state('');
	/** @type {Array<{ id: string, title: string }>} */
	let progressItems = $state([]);

	/** Set of KS ids the current user has an active in-flight ingestion on
	 *  (perceived-performance hint — surfaces a small "{n} ingesting" badge
	 *  next to the KS row even after the IngestionProgressModal is closed
	 *  via "Run in background"). */
	let ingestingByKsId = $state(/** @type {Record<string, number>} */ ({}));

	// Row-expansion: ids of rows the user has expanded to see the locked-config
	// detail. Stored as a plain object so reassignment triggers reactivity.
	let expanded = $state(/** @type {Record<string, boolean>} */ ({}));

	// Create modal handle
	/** @type {any} */
	let createModal;

	// Column definitions — reduced to 5 per Phase C plan section C.1.
	/** @type {Array<{ key: string, label: string, defaultWidth: number, align?: 'left'|'center'|'right' }>} */
	const columns = [
		{ key: 'name', label: $_('knowledgeStores.name', { default: 'Name' }), defaultWidth: 0 },
		{
			key: 'items',
			label: $_('knowledgeStores.items.title', { default: 'Items' }),
			defaultWidth: 90,
			align: 'center'
		},
		{
			key: 'sharing',
			label: $_('knowledgeStores.sharing.label', { default: 'Sharing' }),
			defaultWidth: 95,
			align: 'center'
		},
		{
			key: 'created',
			label: $_('knowledgeStores.createdAt', { default: 'Created' }),
			defaultWidth: 145
		},
		{
			key: 'actions',
			label: $_('knowledgeStores.actions', { default: 'Actions' }),
			defaultWidth: 130,
			align: 'right'
		}
	];

	// --- Filter predicates ---
	let activePredicates = $derived.by(() => {
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
			// Use local midnight so "Today" matches the user's timezone, not
			// UTC. The Date instance is never stored in state.
			// eslint-disable-next-line svelte/prefer-svelte-reactivity
			const localMidnight = new Date();
			localMidnight.setHours(0, 0, 0, 0);
			const todayStart = localMidnight.getTime();
			/** @param {any} s */
			const ts = (s) =>
				typeof s.created_at === 'number' ? s.created_at * 1000 : Date.parse(String(s.created_at));
			if (createdFilter === 'today') {
				preds.push((s) => ts(s) >= todayStart);
			} else if (createdFilter === 'this-week') {
				preds.push((s) => now - ts(s) <= 7 * DAY);
			} else if (createdFilter === 'this-month') {
				preds.push((s) => now - ts(s) <= 30 * DAY);
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

	let orgId = $derived(/** @type {any} */ ($user)?.organization_id || '');

	onMount(async () => {
		await loadStores({ paintFromCacheFirst: true });
	});

	export async function refresh() {
		await loadStores();
	}

	/**
	 * Load Knowledge Stores. When `paintFromCacheFirst` is set, the cached
	 * array (if any) is rendered immediately while a fresh fetch runs in
	 * the background. The skeleton is hidden for at most 300ms via a min-show
	 * guard so a fast cache hit doesn't flicker.
	 *
	 * @param {{ paintFromCacheFirst?: boolean }} [opts]
	 */
	async function loadStores(opts = {}) {
		error = '';
		const cached = readKsCache(orgId);
		if (opts.paintFromCacheFirst && cached) {
			stores = cached.stores;
			loading = false;
			applyFiltersAndPagination();
		} else {
			loading = true;
		}

		try {
			if (!$user.isLoggedIn) {
				error = $_('knowledgeStores.loginRequired', {
					default: 'You must be logged in to view Knowledge Stores.'
				});
				return;
			}
			const fresh = (await getKnowledgeStores()) || [];
			stores = fresh;
			writeKsCache(orgId, fresh);
			applyFiltersAndPagination();
		} catch (/** @type {unknown} */ err) {
			console.error('Error loading Knowledge Stores:', err);
			error = err instanceof Error ? err.message : 'Failed to load Knowledge Stores';
			if (!cached) stores = [];
		} finally {
			loading = false;
		}
	}

	function applyFiltersAndPagination() {
		const result = processListData(stores, {
			search: searchTerm,
			searchFields: ['name', 'description', 'id', 'embedding_vendor', 'embedding_model'],
			filters: {},
			predicates: activePredicates,
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

	/** @param {string} id */
	function toggleExpanded(id) {
		expanded = { ...expanded, [id]: !expanded[id] };
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	function openAddContent(ks) {
		addContentKsId = ks.id;
		showAddContentModal = true;
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	function requestDelete(ks) {
		deleteTarget = { id: ks.id, name: ks.name };
		deleteError = '';
		showDeleteModal = true;
	}

	async function handleDeleteConfirm() {
		isDeleting = true;
		deleteError = '';
		const targetId = deleteTarget.id;
		const targetName = deleteTarget.name;
		try {
			await deleteKnowledgeStore(targetId);
			showDeleteModal = false;
			// Optimistic: drop from local list + cache so the row disappears
			// instantly, then revalidate in the background.
			stores = stores.filter((s) => s.id !== targetId);
			removeKsFromCache(orgId, targetId);
			applyFiltersAndPagination();
			toast.success(
				$_('knowledgeStores.deleteSuccess', {
					default: `Knowledge Store "${targetName}" deleted.`
				})
			);
			loadStores(); // background revalidate
		} catch (/** @type {unknown} */ err) {
			deleteError = err instanceof Error ? err.message : 'Delete failed';
		} finally {
			isDeleting = false;
		}
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	async function handleToggleSharing(ks) {
		if (!ks.is_owner && ks.is_owner !== undefined) return;
		const newState = !ks.is_shared;
		// Optimistic: flip immediately, rollback on failure.
		const idx = stores.findIndex((s) => s.id === ks.id);
		if (idx !== -1) {
			stores[idx].is_shared = newState;
			stores = [...stores];
			patchKsInCache(orgId, ks.id, { is_shared: newState });
			applyFiltersAndPagination();
		}
		try {
			await toggleSharing(ks.id, newState);
			toast.success(
				newState
					? $_('knowledgeStores.shareSuccess', {
							default: 'Knowledge Store shared with organization.'
						})
					: $_('knowledgeStores.unshareSuccess', {
							default: 'Knowledge Store is now private.'
						})
			);
		} catch (/** @type {unknown} */ err) {
			// Rollback
			if (idx !== -1) {
				stores[idx].is_shared = !newState;
				stores = [...stores];
				patchKsInCache(orgId, ks.id, { is_shared: !newState });
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

	/** @param {CustomEvent<{id: string, name: string}>} event */
	async function handleCreated(event) {
		toast.success(
			$_('knowledgeStores.createSuccess', {
				default: `Knowledge Store "${event.detail.name}" created.`
			})
		);
		await loadStores();
	}

	/** @param {import('$lib/services/knowledgeStoreService').KnowledgeStore} ks */
	function buildMenuItems(ks) {
		/** @type {Array<{label?: string, onClick?: () => void, icon?: any, danger?: boolean, divider?: boolean}>} */
		const items = [];
		items.push({
			label: $_('knowledgeStores.addContent', { default: 'Add Content' }),
			icon: Plus,
			onClick: () => openAddContent(ks)
		});
		items.push({
			label: ks.is_shared
				? $_('knowledgeStores.sharing.makePrivate', { default: 'Make private' })
				: $_('knowledgeStores.sharing.share', { default: 'Share' }),
			icon: ks.is_shared ? Lock : Share2,
			onClick: () => handleToggleSharing(ks)
		});
		items.push({ divider: true });
		items.push({
			label: $_('knowledgeStores.delete', { default: 'Delete' }),
			icon: Trash2,
			danger: true,
			onClick: () => requestDelete(ks)
		});
		return items;
	}
</script>

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
	{activeChips}
	searchValue={searchTerm}
	searchPlaceholder={$_('list.searchPlaceholder', { default: 'Search knowledge stores...' })}
	sortOptions={[
		{ value: 'name', label: $_('knowledgeStores.name', { default: 'Name' }) },
		{ value: 'created_at', label: $_('knowledgeStores.createdAt', { default: 'Created' }) }
	]}
	{sortBy}
	{sortOrder}
	onRetry={() => loadStores()}
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
			onclick={() => createModal?.open()}
			ariaLabel={$_('knowledgeStores.createNewTitle', {
				default: 'Create a Knowledge Store from existing library content'
			})}
		>
			{$_('knowledgeStores.createNew', { default: 'New Knowledge Store' })}
		</Button>
	{/snippet}

	{#snippet emptyState()}
		{#if isFiltered}
			<EmptyState
				icon={Database}
				title={$_('knowledgeStores.noResults', {
					default: 'No Knowledge Stores match your filters.'
				})}
			/>
		{:else}
			<EmptyState
				icon={Database}
				title={$_('knowledgeStores.empty.title', { default: 'No Knowledge Stores yet' })}
				description={$_('knowledgeStores.empty.description', {
					default: 'Create one to start indexing library content.'
				})}
			>
				{#snippet actions()}
					<Button variant="primary" iconLeftComponent={Plus} onclick={() => createModal?.open()}>
						{$_('knowledgeStores.createNew', { default: 'New Knowledge Store' })}
					</Button>
				{/snippet}
			</EmptyState>
		{/if}
	{/snippet}

	{#snippet table()}
		<ResizableTable tableId="knowledgeStores" {columns}>
			<tbody class="divide-border bg-surface divide-y">
				{#each displayStores as ks (ks.id)}
					{@const isExpanded = !!expanded[ks.id]}
					{@const ingestingCount = ingestingByKsId[ks.id] ?? 0}
					<tr class="hover:bg-surface-sunken">
						<!-- Name (with embedding model as subtitle + trailing Lock icon to
						     hint the locked-config story without listing each value). -->
						<td class="overflow-hidden px-4 py-2">
							<div class="flex items-center gap-2">
								<button
									type="button"
									onclick={() => viewStore(ks.id)}
									title={ks.name}
									class="text-brand min-w-0 cursor-pointer truncate border-0 bg-transparent p-0 text-left font-medium hover:underline"
								>
									{ks.name}
								</button>
								<Lock
									size={12}
									class="text-text-subtle shrink-0"
									aria-label={$_('knowledgeStores.lockedConfigHint', {
										default: 'Configuration is locked after creation'
									})}
								/>
								{#if ingestingCount > 0}
									<Badge variant="info" icon={Loader2} spin>
										{ingestingCount}
										{$_('knowledgeStores.ingestionProgress.ingesting', {
											default: 'ingesting'
										})}
									</Badge>
								{/if}
							</div>
							<p class="type-caption mt-0.5 truncate">
								{ks.embedding_vendor}
								<span class="text-text-subtle">·</span>
								{ks.embedding_model}
							</p>
						</td>
						<!-- Items: badge "Empty" when 0, count otherwise. -->
						<td class="px-4 py-2" style:text-align="center">
							{#if (ks.content_count ?? 0) === 0}
								<Badge variant="warning" icon={AlertCircle}>
									{$_('knowledgeStores.empty.badge', { default: 'Empty' })}
								</Badge>
							{:else}
								<span class="type-body-muted">{ks.content_count}</span>
							{/if}
						</td>
						<!-- Sharing badge -->
						<td class="px-4 py-2" style:text-align="center">
							{#if ks.is_owner !== false}
								<Badge
									variant={ks.is_shared ? 'success' : 'neutral'}
									icon={ks.is_shared ? Users : Lock}
								>
									{ks.is_shared
										? $_('knowledgeStores.sharing.shared', { default: 'Shared' })
										: $_('knowledgeStores.sharing.private', { default: 'Private' })}
								</Badge>
							{:else}
								<span class="type-caption">{ks.owner_name || ks.owner_email || ''}</span>
							{/if}
						</td>
						<!-- Created -->
						<td class="type-body-muted px-4 py-2">{formatDate(ks.created_at)}</td>
						<!-- Actions: Expand chevron + View + OverflowMenu -->
						<td class="px-4 py-2">
							<div class="flex items-center justify-end gap-1">
								<IconButton
									icon={ChevronRight}
									ariaLabel={isExpanded
										? $_('knowledgeStores.collapseDetail', {
												default: 'Hide locked configuration'
											})
										: $_('knowledgeStores.expandDetail', {
												default: 'Show locked configuration'
											})}
									tooltip={isExpanded
										? $_('knowledgeStores.collapseDetail', {
												default: 'Hide locked configuration'
											})
										: $_('knowledgeStores.expandDetail', {
												default: 'Show locked configuration'
											})}
									variant="ghost"
									size="sm"
									class={isExpanded ? 'rotate-90 transition-transform' : 'transition-transform'}
									onclick={() => toggleExpanded(ks.id)}
								/>
								<IconButton
									icon={Eye}
									ariaLabel={`${$_('knowledgeStores.view', { default: 'View' })} ${ks.name}`}
									tooltip={$_('knowledgeStores.view', { default: 'View' })}
									variant="ghost"
									size="sm"
									onclick={() => viewStore(ks.id)}
								/>
								{#if ks.is_owner !== false}
									<OverflowMenu
										items={buildMenuItems(ks)}
										ariaLabel={$_('list.moreActions', { default: 'More actions' })}
										tooltip={$_('list.moreActions', { default: 'More actions' })}
										size="sm"
									/>
								{/if}
							</div>
						</td>
					</tr>
					{#if isExpanded}
						<tr class="bg-surface-muted">
							<td colspan={columns.length} class="p-0">
								<div
									class="px-4 py-3"
									transition:slide={{ duration: 240, easing: cubicInOut, axis: 'y' }}
								>
									<dl class="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
										<div>
											<dt class="type-label flex items-center gap-1">
												<Lock size={10} aria-hidden="true" />
												{$_('knowledgeStores.embeddingVendor', { default: 'Embedding' })}
											</dt>
											<dd class="text-text mt-0.5">{ks.embedding_vendor}</dd>
										</div>
										<div>
											<dt class="type-label flex items-center gap-1">
												<Lock size={10} aria-hidden="true" />
												{$_('knowledgeStores.embeddingModel', { default: 'Model' })}
											</dt>
											<dd class="text-text mt-0.5 break-all">{ks.embedding_model}</dd>
										</div>
										<div>
											<dt class="type-label flex items-center gap-1">
												<Lock size={10} aria-hidden="true" />
												{$_('knowledgeStores.chunking', { default: 'Chunking' })}
											</dt>
											<dd class="text-text mt-0.5">{ks.chunking_strategy}</dd>
										</div>
										<div>
											<dt class="type-label flex items-center gap-1">
												<Lock size={10} aria-hidden="true" />
												{$_('knowledgeStores.vectorDb', { default: 'Vector DB' })}
											</dt>
											<dd class="text-text mt-0.5">{ks.vector_db_backend}</dd>
										</div>
										{#if typeof ks.chunk_count === 'number'}
											<div>
												<dt class="type-label">
													{$_('knowledgeStores.totalChunks', { default: 'Total chunks' })}
												</dt>
												<dd class="text-text mt-0.5">{ks.chunk_count}</dd>
											</div>
										{/if}
									</dl>
								</div>
							</td>
						</tr>
					{/if}
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
		ingestingByKsId = { ...ingestingByKsId, [progressKsId]: progressItems.length };
		showProgressModal = true;
	}}
	on:close={() => {
		showAddContentModal = false;
	}}
/>

<IngestionProgressModal
	bind:isOpen={showProgressModal}
	ksId={progressKsId}
	ksName={progressKsName}
	items={progressItems}
	onclose={() => {
		// When the modal closes (Close or Run in background), drop the
		// hint. The next loadStores() picks up fresh counts.
		ingestingByKsId = (() => {
			const next = { ...ingestingByKsId };
			delete next[progressKsId];
			return next;
		})();
		loadStores();
	}}
	onprogress={(/** @type {{ ingesting: number }} */ progress) => {
		ingestingByKsId = {
			...ingestingByKsId,
			[progressKsId]: progress.ingesting
		};
	}}
/>

<ConfirmationModal
	bind:isOpen={showDeleteModal}
	bind:isLoading={isDeleting}
	title={$_('knowledgeStores.deleteModal.title', { default: 'Delete Knowledge Store' })}
	message={$_('knowledgeStores.deleteModal.message', {
		default: `Delete Knowledge Store "${deleteTarget.name}"? This action cannot be undone. All vectors will be permanently removed. The library items linked to it will not be affected.`,
		values: { name: deleteTarget.name }
	})}
	confirmText={$_('knowledgeStores.deleteModal.confirm', { default: 'Delete' })}
	variant="danger"
	error={deleteError}
	onconfirm={handleDeleteConfirm}
	oncancel={() => {
		showDeleteModal = false;
		deleteError = '';
	}}
/>
