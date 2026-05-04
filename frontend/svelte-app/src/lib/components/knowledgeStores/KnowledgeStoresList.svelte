<!--
  @component KnowledgeStoresList
  Displays owned and shared Knowledge Stores with tabs, search, sort,
  pagination, and actions (share, delete). Mirrors LibrariesList.svelte
  structure so users moving between the two surfaces have the same UX.

  Creation goes through the unified wizard launcher on the parent page —
  this component does NOT host its own create modal.
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
	import FilterBar from '$lib/components/common/FilterBar.svelte';
	import Pagination from '$lib/components/common/Pagination.svelte';

	const dispatch = createEventDispatcher();

	let stores = $state([]);
	let displayStores = $state([]);
	let loading = $state(true);
	let error = $state('');
	let successMessage = $state('');

	let currentTab = $state('my');

	let searchTerm = $state('');
	let sortBy = $state('created_at');
	let sortOrder = $state('desc');
	let currentPage = $state(1);
	let itemsPerPage = $state(10);
	let totalPages = $state(1);
	let totalItems = $state(0);

	let showDeleteModal = $state(false);
	let isDeleting = $state(false);
	let deleteTarget = $state({ id: '', name: '' });

	let ownedStores = $derived(stores.filter((s) => s.is_owner !== false));
	let sharedStores = $derived(stores.filter((s) => s.is_owner === false));
	let currentTabStores = $derived(currentTab === 'my' ? ownedStores : sharedStores);

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
		const result = processListData(currentTabStores, {
			search: searchTerm,
			searchFields: ['name', 'description', 'id', 'embedding_vendor', 'embedding_model'],
			filters: {},
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

	$effect(() => {
		currentTab;
		currentPage = 1;
		applyFiltersAndPagination();
	});

	function handleTabSwitch(tab) {
		currentTab = tab;
		searchTerm = '';
		currentPage = 1;
		applyFiltersAndPagination();
	}

	function handleSearchChange(event) {
		searchTerm = event.detail.value;
		currentPage = 1;
		applyFiltersAndPagination();
	}

	function handleSortChange(event) {
		sortBy = event.detail.sortBy;
		sortOrder = event.detail.sortOrder;
		applyFiltersAndPagination();
	}

	function handlePageChange(event) {
		currentPage = event.detail.page;
		applyFiltersAndPagination();
	}

	function viewStore(id) {
		dispatch('view', { id });
	}

	function showSuccess(msg) {
		successMessage = msg;
		setTimeout(() => {
			successMessage = '';
		}, 4000);
	}

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

	async function handleToggleSharing(ks) {
		if (!ks.is_owner && ks.is_owner !== undefined) return;
		const newState = !ks.is_shared;
		try {
			await toggleSharing(ks.id, newState);
			ks.is_shared = newState;
			const idx = stores.findIndex((s) => s.id === ks.id);
			if (idx !== -1) stores[idx].is_shared = newState;
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

	function formatDate(ts) {
		if (!ts) return '';
		const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
		return d.toLocaleDateString(undefined, {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}
</script>

<div class="overflow-hidden rounded-lg bg-white shadow">
	<div class="flex items-center justify-between border-b border-gray-200 px-4 py-4 sm:px-6">
		<div class="flex gap-4">
			<button
				type="button"
				class="border-b-2 pb-1 text-sm font-medium {currentTab === 'my'
					? 'border-[#2271b3] text-[#2271b3]'
					: 'border-transparent text-gray-500 hover:text-gray-700'}"
				onclick={() => handleTabSwitch('my')}
			>
				{$_('knowledgeStores.myStores', { default: 'My Knowledge Stores' })}
				<span class="ml-1 text-xs text-gray-400">({ownedStores.length})</span>
			</button>
			<button
				type="button"
				class="border-b-2 pb-1 text-sm font-medium {currentTab === 'shared'
					? 'border-[#2271b3] text-[#2271b3]'
					: 'border-transparent text-gray-500 hover:text-gray-700'}"
				onclick={() => handleTabSwitch('shared')}
			>
				{$_('knowledgeStores.sharedStores', { default: 'Shared' })}
				<span class="ml-1 text-xs text-gray-400">({sharedStores.length})</span>
			</button>
		</div>
	</div>

	{#if successMessage}
		<div
			class="border-b border-green-100 bg-green-50 px-4 py-3 text-sm text-green-700"
			role="status"
		>
			{successMessage}
		</div>
	{/if}

	{#if currentTabStores.length > 0}
		<div class="border-b border-gray-100 px-4 py-3">
			<FilterBar
				bind:searchTerm
				on:search={handleSearchChange}
				on:sort={handleSortChange}
				sortOptions={[
					{ value: 'name', label: $_('knowledgeStores.name', { default: 'Name' }) },
					{ value: 'created_at', label: $_('knowledgeStores.createdAt', { default: 'Created' }) }
				]}
				{sortBy}
				{sortOrder}
			/>
		</div>
	{/if}

	{#if loading}
		<div class="p-6 text-center">
			<div class="animate-pulse text-gray-500">
				{$_('knowledgeStores.loading', { default: 'Loading Knowledge Stores...' })}
			</div>
		</div>
	{:else if error}
		<div class="p-6 text-center" role="alert">
			<p class="text-red-500">{error}</p>
			<button
				onclick={() => loadStores()}
				class="mt-3 rounded-md bg-[#2271b3] px-4 py-2 text-sm font-medium text-white hover:bg-[#195a91]"
			>
				{$_('common.retry', { default: 'Retry' })}
			</button>
		</div>
	{:else if displayStores.length === 0}
		<div class="p-6 text-center text-gray-500">
			{#if currentTabStores.length === 0}
				{currentTab === 'my'
					? $_('knowledgeStores.noOwned', {
							default:
								'You have no Knowledge Stores yet. Create one to start indexing library content.'
						})
					: $_('knowledgeStores.noShared', {
							default: 'No shared Knowledge Stores available.'
						})}
			{:else}
				{$_('knowledgeStores.noResults', {
					default: 'No Knowledge Stores match your search.'
				})}
			{/if}
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.name', { default: 'Name' })}
						</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.embedding', { default: 'Embedding' })}
						</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.chunking', { default: 'Chunking' })}
						</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.contentCount', { default: 'Content' })}
						</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.sharing.label', { default: 'Sharing' })}
						</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.createdAt', { default: 'Created' })}
						</th>
						<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
							{$_('knowledgeStores.actions', { default: 'Actions' })}
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 bg-white">
					{#each displayStores as ks (ks.id)}
						<tr class="hover:bg-gray-50">
							<td class="px-4 py-3">
								<button
									type="button"
									onclick={() => viewStore(ks.id)}
									class="cursor-pointer border-0 bg-transparent p-0 text-left font-medium text-[#2271b3] hover:underline"
								>
									{ks.name}
								</button>
								{#if ks.description}
									<p class="mt-0.5 max-w-xs truncate text-xs text-gray-500">
										{ks.description}
									</p>
								{/if}
							</td>
							<td class="px-4 py-3 text-xs text-gray-600">
								<div>{ks.embedding_vendor}</div>
								<div class="text-gray-400">{ks.embedding_model}</div>
							</td>
							<td class="px-4 py-3 text-xs text-gray-600">{ks.chunking_strategy}</td>
							<td class="px-4 py-3 text-sm text-gray-500">{ks.content_count ?? 0}</td>
							<td class="px-4 py-3">
								{#if currentTab === 'my'}
									<button
										type="button"
										onclick={() => handleToggleSharing(ks)}
										class="rounded border px-2 py-1 text-xs {ks.is_shared
											? 'border-green-300 bg-green-50 text-green-700 hover:bg-green-100'
											: 'border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100'}"
									>
										{ks.is_shared
											? $_('knowledgeStores.sharing.shared', { default: 'Shared' })
											: $_('knowledgeStores.sharing.private', { default: 'Private' })}
									</button>
								{:else}
									<span class="text-xs text-gray-500">
										{ks.owner_name || ks.owner_email || ''}
									</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-sm text-gray-500">{formatDate(ks.created_at)}</td>
							<td class="px-4 py-3 text-right">
								<button
									type="button"
									onclick={() => viewStore(ks.id)}
									class="mr-3 text-sm text-[#2271b3] hover:underline"
								>
									{$_('knowledgeStores.view', { default: 'View' })}
								</button>
								{#if currentTab === 'my'}
									<button
										type="button"
										onclick={() => requestDelete(ks)}
										class="text-sm text-red-600 hover:text-red-900"
									>
										{$_('knowledgeStores.delete', { default: 'Delete' })}
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if totalPages > 1}
			<div class="border-t border-gray-100 px-4 py-3">
				<Pagination
					{currentPage}
					{totalPages}
					{totalItems}
					{itemsPerPage}
					on:pageChange={handlePageChange}
				/>
			</div>
		{/if}
	{/if}
</div>

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
