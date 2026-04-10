<!--
  @component LibrariesList
  Displays owned and shared libraries with search, sort, pagination,
  and actions (create, share, delete). Emits 'view' event to parent.
-->
<script>
    import { onMount, createEventDispatcher } from 'svelte';
    import { getLibraries, deleteLibrary, toggleSharing } from '$lib/services/libraryService';
    import { _ } from '$lib/i18n';
    import { user } from '$lib/stores/userStore';
    import { processListData } from '$lib/utils/listHelpers';
    import CreateLibraryModal from '$lib/components/modals/CreateLibraryModal.svelte';
    import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
    import FilterBar from '$lib/components/common/FilterBar.svelte';
    import Pagination from '$lib/components/common/Pagination.svelte';

    const dispatch = createEventDispatcher();

    // Data
    let libraries = $state([]);
    let displayLibraries = $state([]);
    let loading = $state(true);
    let error = $state('');
    let successMessage = $state('');

    // Tabs
    let currentTab = $state('my');

    // Filter / sort / pagination
    let searchTerm = $state('');
    let sortBy = $state('created_at');
    let sortOrder = $state('desc');
    let currentPage = $state(1);
    let itemsPerPage = $state(10);
    let totalPages = $state(1);
    let totalItems = $state(0);

    // Delete modal
    let showDeleteModal = $state(false);
    let isDeleting = $state(false);
    let deleteTarget = $state({ id: '', name: '' });

    // Refs
    let createModal;

    let ownedLibraries = $derived(libraries.filter(l => l.is_owner !== false));
    let sharedLibraries = $derived(libraries.filter(l => l.is_owner === false));
    let currentTabLibraries = $derived(currentTab === 'my' ? ownedLibraries : sharedLibraries);

    onMount(async () => {
        await loadLibraries();
    });

    async function loadLibraries() {
        loading = true;
        error = '';
        try {
            if (!$user.isLoggedIn) {
                error = $_('libraries.loginRequired', { default: 'You must be logged in to view libraries.' });
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
        const result = processListData(currentTabLibraries, {
            search: searchTerm,
            searchFields: ['name', 'description', 'id'],
            filters: {},
            sortBy,
            sortOrder,
            page: currentPage,
            itemsPerPage,
        });
        displayLibraries = result.items;
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

    function viewLibrary(id) {
        dispatch('view', { id });
    }

    function showSuccess(msg) {
        successMessage = msg;
        setTimeout(() => { successMessage = ''; }, 4000);
    }

    async function handleCreated(event) {
        showSuccess($_('libraries.createSuccess', { default: `Library "${event.detail.name}" created.` }));
        await loadLibraries();
    }

    function requestDelete(lib) {
        deleteTarget = { id: lib.id, name: lib.name };
        showDeleteModal = true;
    }

    async function handleDeleteConfirm() {
        isDeleting = true;
        try {
            await deleteLibrary(deleteTarget.id);
            showDeleteModal = false;
            showSuccess($_('libraries.deleteSuccess', { default: `Library "${deleteTarget.name}" deleted.` }));
            await loadLibraries();
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Delete failed';
        } finally {
            isDeleting = false;
        }
    }

    async function handleToggleSharing(lib) {
        if (!lib.is_owner && lib.is_owner !== undefined) return;
        const newState = !lib.is_shared;
        try {
            await toggleSharing(lib.id, newState);
            lib.is_shared = newState;
            const idx = libraries.findIndex(l => l.id === lib.id);
            if (idx !== -1) libraries[idx].is_shared = newState;
            applyFiltersAndPagination();
            showSuccess(newState
                ? $_('libraries.shareSuccess', { default: 'Library shared with organization.' })
                : $_('libraries.unshareSuccess', { default: 'Library is now private.' }));
        } catch (/** @type {unknown} */ err) {
            error = err instanceof Error ? err.message : 'Failed to toggle sharing';
        }
    }

    function formatDate(ts) {
        if (!ts) return '';
        const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    }
</script>

<div class="bg-white shadow rounded-lg overflow-hidden">
    <div class="px-4 py-4 sm:px-6 flex items-center justify-between border-b border-gray-200">
        <div class="flex gap-4">
            <button
                type="button"
                class="text-sm font-medium pb-1 border-b-2 {currentTab === 'my' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700'}"
                onclick={() => handleTabSwitch('my')}
            >
                {$_('libraries.myLibraries', { default: 'My Libraries' })}
                <span class="ml-1 text-xs text-gray-400">({ownedLibraries.length})</span>
            </button>
            <button
                type="button"
                class="text-sm font-medium pb-1 border-b-2 {currentTab === 'shared' ? 'border-[#2271b3] text-[#2271b3]' : 'border-transparent text-gray-500 hover:text-gray-700'}"
                onclick={() => handleTabSwitch('shared')}
            >
                {$_('libraries.sharedLibraries', { default: 'Shared' })}
                <span class="ml-1 text-xs text-gray-400">({sharedLibraries.length})</span>
            </button>
        </div>
        <button
            type="button"
            onclick={() => createModal.open()}
            class="inline-flex items-center px-3 py-2 text-sm font-medium text-white rounded-md shadow-sm bg-[#2271b3] hover:bg-[#195a91]"
        >
            + {$_('libraries.createNew', { default: 'New Library' })}
        </button>
    </div>

    {#if successMessage}
        <div class="px-4 py-3 bg-green-50 border-b border-green-100 text-sm text-green-700">{successMessage}</div>
    {/if}

    {#if currentTabLibraries.length > 0}
        <div class="px-4 py-3 border-b border-gray-100">
            <FilterBar
                bind:searchTerm
                on:search={handleSearchChange}
                on:sort={handleSortChange}
                sortOptions={[
                    { value: 'name', label: $_('libraries.name', { default: 'Name' }) },
                    { value: 'created_at', label: $_('libraries.createdAt', { default: 'Created' }) },
                ]}
                {sortBy}
                {sortOrder}
            />
        </div>
    {/if}

    {#if loading}
        <div class="p-6 text-center">
            <div class="animate-pulse text-gray-500">{$_('libraries.loading', { default: 'Loading libraries...' })}</div>
        </div>
    {:else if error}
        <div class="p-6 text-center">
            <p class="text-red-500">{error}</p>
            <button
                onclick={() => loadLibraries()}
                class="mt-3 px-4 py-2 text-sm font-medium text-white rounded-md bg-[#2271b3] hover:bg-[#195a91]"
            >
                {$_('common.retry', { default: 'Retry' })}
            </button>
        </div>
    {:else if displayLibraries.length === 0}
        <div class="p-6 text-center text-gray-500">
            {#if currentTabLibraries.length === 0}
                {currentTab === 'my'
                    ? $_('libraries.noOwned', { default: 'You have no libraries yet. Create one to get started!' })
                    : $_('libraries.noShared', { default: 'No shared libraries available.' })}
            {:else}
                {$_('libraries.noResults', { default: 'No libraries match your search.' })}
            {/if}
        </div>
    {:else}
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.name', { default: 'Name' })}</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.items.title', { default: 'Items' })}</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.sharing.label', { default: 'Sharing' })}</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{$_('libraries.createdAt', { default: 'Created' })}</th>
                        <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">{$_('libraries.actions', { default: 'Actions' })}</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {#each displayLibraries as lib (lib.id)}
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-3">
                                <button
                                    type="button"
                                    onclick={() => viewLibrary(lib.id)}
                                    class="text-left font-medium text-[#2271b3] hover:underline bg-transparent border-0 cursor-pointer p-0"
                                >
                                    {lib.name}
                                </button>
                                {#if lib.description}
                                    <p class="text-xs text-gray-500 mt-0.5 truncate max-w-xs">{lib.description}</p>
                                {/if}
                            </td>
                            <td class="px-4 py-3 text-sm text-gray-500">{lib.item_count ?? ''}</td>
                            <td class="px-4 py-3">
                                {#if currentTab === 'my'}
                                    <button
                                        type="button"
                                        onclick={() => handleToggleSharing(lib)}
                                        class="text-xs px-2 py-1 rounded border {lib.is_shared ? 'border-green-300 text-green-700 bg-green-50 hover:bg-green-100' : 'border-gray-300 text-gray-600 bg-gray-50 hover:bg-gray-100'}"
                                    >
                                        {lib.is_shared
                                            ? $_('libraries.sharing.shared', { default: 'Shared' })
                                            : $_('libraries.sharing.private', { default: 'Private' })}
                                    </button>
                                {:else}
                                    <span class="text-xs text-gray-500">
                                        {lib.owner_name || lib.owner_email || ''}
                                    </span>
                                {/if}
                            </td>
                            <td class="px-4 py-3 text-sm text-gray-500">{formatDate(lib.created_at)}</td>
                            <td class="px-4 py-3 text-right">
                                <button
                                    type="button"
                                    onclick={() => viewLibrary(lib.id)}
                                    class="text-sm text-[#2271b3] hover:underline mr-3"
                                >
                                    {$_('libraries.view', { default: 'View' })}
                                </button>
                                {#if currentTab === 'my'}
                                    <button
                                        type="button"
                                        onclick={() => requestDelete(lib)}
                                        class="text-sm text-red-600 hover:text-red-900"
                                    >
                                        {$_('libraries.delete', { default: 'Delete' })}
                                    </button>
                                {/if}
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>

        {#if totalPages > 1}
            <div class="px-4 py-3 border-t border-gray-100">
                <Pagination {currentPage} {totalPages} {totalItems} {itemsPerPage} on:pageChange={handlePageChange} />
            </div>
        {/if}
    {/if}
</div>

<CreateLibraryModal bind:this={createModal} on:created={handleCreated} />

<ConfirmationModal
    bind:isOpen={showDeleteModal}
    bind:isLoading={isDeleting}
    title={$_('libraries.deleteModal.title', { default: 'Delete Library' })}
    message={$_('libraries.deleteModal.message', { default: `Are you sure you want to delete "${deleteTarget.name}"? All content will be permanently removed.` })}
    confirmText={$_('libraries.deleteModal.confirm', { default: 'Delete' })}
    variant="danger"
    onconfirm={handleDeleteConfirm}
    oncancel={() => { showDeleteModal = false; }}
/>
