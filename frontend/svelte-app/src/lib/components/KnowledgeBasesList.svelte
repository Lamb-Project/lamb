<script>
    import { onMount } from 'svelte';
    import { getUserKnowledgeBases, getSharedKnowledgeBases, deleteKnowledgeBase, toggleKBSharing } from '$lib/services/knowledgeBaseService';
    import { _ } from '$lib/i18n';
    import { user } from '$lib/stores/userStore';
    import { base } from '$app/paths';
    import CreateKnowledgeBaseModal from '$lib/components/modals/CreateKnowledgeBaseModal.svelte';
    import { createEventDispatcher } from 'svelte';
    
    // Import filtering/pagination components
    import Pagination from './common/Pagination.svelte';
    import FilterBar from './common/FilterBar.svelte';
    import { processListData } from '$lib/utils/listHelpers';
    
    /**
     * @typedef {Object} KnowledgeBase
     * @property {string} id
     * @property {string} name
     * @property {string} [description]
     * @property {string} owner
     * @property {number} created_at
     * @property {Object} [metadata]
     * @property {string} [metadata.access_control]
     * @property {boolean} [is_owner] - Whether user owns this KB
     * @property {boolean} [is_shared] - Whether KB is shared
     * @property {boolean} [can_modify] - Whether user can modify KB
     * @property {string} [shared_by] - Name of user who shared this KB
     */
    
    // Tab state
    let currentTab = $state('my'); // 'my' | 'shared'
    
    // State management
    /** @type {KnowledgeBase[]} */
    let allKnowledgeBases = $state([]);
    /** @type {KnowledgeBase[]} */
    let ownedKnowledgeBases = $state([]);
    /** @type {KnowledgeBase[]} */
    let sharedKnowledgeBases = $state([]);
    /** @type {KnowledgeBase[]} */
    let displayKnowledgeBases = $state([]);
    let loading = $state(true);
    let error = $state('');
    let serverOffline = $state(false);
    let successMessage = $state('');
    
    // Filter/sort state
    let searchTerm = $state('');
    let sortBy = $state('created_at');
    let sortOrder = $state('desc');
    
    // Pagination state
    let currentPage = $state(1);
    let itemsPerPage = $state(10);
    let totalPages = $state(1);
    let totalItems = $state(0);
    
    // Component references
    /** @type {CreateKnowledgeBaseModal} */
    let createModal;
    
    // Event dispatcher to communicate with parent
    const dispatch = createEventDispatcher();
    
    // Load knowledge bases on component mount
    onMount(async () => {
        await loadKnowledgeBases();
    });
    
    // Function to load knowledge bases from API
    async function loadKnowledgeBases() {
        // Reset states
        loading = true;
        error = '';
        serverOffline = false;
        
        try {
            // Check if user is logged in
            if (!$user.isLoggedIn) {
                error = "You must be logged in to view knowledge bases.";
                loading = false;
                return;
            }
            
            // Fetch owned and shared KBs separately
            const [ownedData, sharedData] = await Promise.all([
                getUserKnowledgeBases().catch(err => {
                    console.warn('Error fetching owned KBs:', err);
                    return [];
                }),
                getSharedKnowledgeBases().catch(err => {
                    console.warn('Error fetching shared KBs:', err);
                    return [];
                })
            ]);
            
            ownedKnowledgeBases = ownedData || [];
            sharedKnowledgeBases = sharedData || [];
            
            // Combine for allKnowledgeBases (for backward compatibility if needed)
            allKnowledgeBases = [...ownedKnowledgeBases, ...sharedKnowledgeBases];
            
            console.log(`Owned: ${ownedKnowledgeBases.length}, Shared: ${sharedKnowledgeBases.length}`);
            
            // Apply filters and pagination after data is loaded
            applyFiltersAndPagination();
            
        } catch (/** @type {unknown} */ err) {
            console.error('Error loading knowledge bases:', err);
            error = err instanceof Error ? err.message : 'Failed to load knowledge bases';
            
            // Check if server is offline based on error message
            if (err instanceof Error && err.message.includes('server offline')) {
                serverOffline = true;
            }
            allKnowledgeBases = [];
            ownedKnowledgeBases = [];
            sharedKnowledgeBases = [];
            displayKnowledgeBases = [];
        } finally {
            loading = false;
        }
    }
    
    // Get current tab's KBs
    let currentTabKBs = $derived(
        currentTab === 'my' ? ownedKnowledgeBases : sharedKnowledgeBases
    );
    
    // Apply filters, sorting, and pagination
    function applyFiltersAndPagination() {
        // Get the current tab's KBs array (derived value is reactive)
        const kbList = currentTab === 'my' ? ownedKnowledgeBases : sharedKnowledgeBases;
        const result = processListData(kbList, {
            search: searchTerm,
            searchFields: ['name', 'description', 'id'],
            filters: {},
            sortBy,
            sortOrder,
            page: currentPage,
            itemsPerPage
        });
        
        displayKnowledgeBases = result.items;
        totalItems = result.filteredCount;
        totalPages = result.totalPages;
        currentPage = result.currentPage;
    }
    
    // Watch for tab changes
    $effect(() => {
        currentTab; // Trigger on tab change
        currentPage = 1;
        applyFiltersAndPagination();
    });
    
    // Handle tab switch
    function handleTabSwitch(tab) {
        currentTab = tab;
        searchTerm = '';
        currentPage = 1;
        applyFiltersAndPagination();
    }
    
    // Filter/Sort/Pagination event handlers
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
    
    function handleItemsPerPageChange(event) {
        itemsPerPage = event.detail.itemsPerPage;
        currentPage = 1;
        applyFiltersAndPagination();
    }
    
    function handleClearFilters() {
        searchTerm = '';
        sortBy = 'created_at';
        sortOrder = 'desc';
        currentPage = 1;
        applyFiltersAndPagination();
    }
    
    /**
     * Format timestamp to readable date
     * @param {number} timestamp - Unix timestamp in seconds
     * @returns {string} Formatted date string
     */
    function formatDate(timestamp) {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
    
    // Show the create modal
    function showCreateModal() {
        createModal.open();
    }
    
    /**
     * Navigate to knowledge base detail view by dispatching an event to parent
     * @param {string} id - Knowledge base ID
     */
    function viewKnowledgeBase(id) {
        dispatch('view', { id });
    }

    async function handleDeleteKnowledgeBase(kb) {
        if (!kb) return;
        if (!confirm($_('knowledgeBases.list.confirmDelete', { default: `Delete knowledge base "${kb.name}" and all its data? This cannot be undone.` }))) {
            return;
        }
        try {
            await deleteKnowledgeBase(kb.id);
            // Optimistic removal
            allKnowledgeBases = allKnowledgeBases.filter(k => k.id !== kb.id);
            ownedKnowledgeBases = ownedKnowledgeBases.filter(k => k.id !== kb.id);
            sharedKnowledgeBases = sharedKnowledgeBases.filter(k => k.id !== kb.id);
            applyFiltersAndPagination();
            successMessage = $_('knowledgeBases.list.deleteSuccess', { default: 'Knowledge base deleted.' });
            setTimeout(() => { successMessage = ''; }, 4000);
        } catch (e) {
            alert(e instanceof Error ? e.message : 'Deletion failed');
        }
    }
    
    async function handleToggleSharing(kb) {
        if (!kb || !kb.is_owner) return;
        
        const newSharingState = !kb.is_shared;
        
        try {
            await toggleKBSharing(kb.id, newSharingState);
            
            // Optimistic update
            kb.is_shared = newSharingState;
            
            // Update local arrays
            const index = allKnowledgeBases.findIndex(k => k.id === kb.id);
            if (index !== -1) {
                allKnowledgeBases[index].is_shared = newSharingState;
            }
            
            // Re-split arrays
            ownedKnowledgeBases = allKnowledgeBases.filter(k => k.is_owner === true);
            sharedKnowledgeBases = allKnowledgeBases.filter(k => k.is_owner === false && k.is_shared === true);
            
            // Update display
            applyFiltersAndPagination();
            
            successMessage = newSharingState 
                ? $_('knowledgeBases.list.shareSuccess', { default: `"${kb.name}" is now shared with your organization.` })
                : $_('knowledgeBases.list.unshareSuccess', { default: `"${kb.name}" is now private.` });
            setTimeout(() => { successMessage = ''; }, 4000);
        } catch (e) {
            // Extract error message from response
            const errorMsg = e instanceof Error ? e.message : 
                (e.response?.data?.detail || e.response?.data?.message || 'Failed to toggle sharing');
            error = errorMsg;
            setTimeout(() => { error = ''; }, 8000);
        }
    }
    
    /**
     * Handle successful knowledge base creation event
     * @param {CustomEvent<{id: string, name: string, message?: string}>} event - The creation event
     */
    function handleKnowledgeBaseCreated(event) {
        const { id, name, message } = event.detail;
        
        // Show success message
        successMessage = message || $_('knowledgeBases.createSuccess', { 
            values: { name }, 
            default: `Knowledge base "${name}" created successfully!` 
        });
        
        // Hide message after 5 seconds
        setTimeout(() => {
            successMessage = '';
        }, 5000);
        
        // Refresh the list
        loadKnowledgeBases();
    }
</script>

<div class="bg-white shadow overflow-hidden sm:rounded-md">
    <div class="p-4 border-b border-gray-200 sm:flex sm:items-center sm:justify-between">
        <h3 class="text-lg leading-6 font-medium text-gray-900">
            {$_('knowledgeBases.list.title', { default: 'Knowledge Bases' })}
        </h3>
        <div class="mt-3 sm:mt-0 sm:ml-4">
            <button
                onclick={showCreateModal}
                class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
            >
                {$_('knowledgeBases.list.createButton', { default: 'Create Knowledge Base' })}
            </button>
        </div>
    </div>

    {#if successMessage}
        <div class="p-4 bg-green-50 border-b border-green-100">
            <div class="text-sm text-green-700">
                {successMessage}
            </div>
        </div>
    {/if}

    {#if loading}
        <div class="p-6 text-center">
            <div class="animate-pulse text-gray-500">
                {$_('knowledgeBases.list.loading', { default: 'Loading knowledge bases...' })}
            </div>
        </div>
    {:else if error}
        <div class="p-6 text-center">
            <div class="text-red-500">
                {#if serverOffline}
                    <div>
                        <p class="font-bold mb-2">
                            {$_('knowledgeBases.list.serverOffline', { default: 'Knowledge Base Server Offline' })}
                        </p>
                        <p>
                            {$_('knowledgeBases.list.tryAgainLater', { default: 'Please try again later or contact an administrator.' })}
                        </p>
                    </div>
                {:else}
                    {error}
                {/if}
            </div>
            <button
                onclick={() => loadKnowledgeBases()}
                class="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
            >
                {$_('knowledgeBases.list.retry', { default: 'Retry' })}
            </button>
        </div>
    {:else}
        <!-- Tabs -->
        <div class="border-b border-gray-200">
            <div class="flex space-x-4 px-6 pt-4">
                <button
                    onclick={() => handleTabSwitch('my')}
                    class="px-4 py-2 text-sm font-medium rounded-md {currentTab === 'my' ? 'bg-brand text-white' : 'text-gray-600 hover:text-gray-900'}"
                >
                    {$_('knowledgeBases.list.myKBs', { default: 'My Knowledge Bases' })}
                    {#if currentTab === 'my'}
                        <span class="ml-2 bg-white bg-opacity-30 text-white py-0.5 px-2 rounded-full text-xs">
                            {ownedKnowledgeBases.length}
                        </span>
                    {/if}
                </button>
                <button
                    onclick={() => handleTabSwitch('shared')}
                    class="px-4 py-2 text-sm font-medium rounded-md {currentTab === 'shared' ? 'bg-brand text-white' : 'text-gray-600 hover:text-gray-900'}"
                >
                    {$_('knowledgeBases.list.sharedKBs', { default: 'Shared Knowledge Bases' })}
                    {#if currentTab === 'shared'}
                        <span class="ml-2 bg-white bg-opacity-30 text-white py-0.5 px-2 rounded-full text-xs">
                            {sharedKnowledgeBases.length}
                        </span>
                    {/if}
                </button>
            </div>
        </div>
        
        <!-- Filter Bar -->
        <FilterBar
            searchPlaceholder={$_('knowledgeBases.searchPlaceholder', { default: 'Search knowledge bases...' })}
            searchValue={searchTerm}
            filters={[]}
            filterValues={{}}
            sortOptions={[
                { value: 'name', label: $_('common.sortByName', { default: 'Name' }) },
                { value: 'created_at', label: $_('common.sortByCreated', { default: 'Created Date' }) }
            ]}
            {sortBy}
            {sortOrder}
            on:searchChange={handleSearchChange}
            on:sortChange={handleSortChange}
            on:clearFilters={handleClearFilters}
        />
        
        <!-- Results count -->
        <div class="flex justify-between items-center mb-4 px-6">
            <div class="text-sm text-gray-600">
                {#if searchTerm}
                    Showing <span class="font-medium">{totalItems}</span> of <span class="font-medium">{currentTabKBs.length}</span> {currentTab === 'my' ? 'owned' : 'shared'} knowledge bases
                {:else}
                    <span class="font-medium">{totalItems}</span> {currentTab === 'my' ? 'owned' : 'shared'} knowledge {totalItems === 1 ? 'base' : 'bases'}
                {/if}
            </div>
        </div>
        
        {#if displayKnowledgeBases.length === 0}
            {#if currentTabKBs.length === 0}
                <!-- No knowledge bases in this tab -->
                <div class="p-6 text-center">
                    <div class="text-gray-500">
                        {currentTab === 'my' 
                            ? $_('knowledgeBases.list.noOwned', { default: 'You have no knowledge bases yet. Create one to get started!' })
                            : $_('knowledgeBases.list.noShared', { default: 'No shared knowledge bases available.' })
                        }
                    </div>
                </div>
            {:else}
                <!-- No results match filters -->
                <div class="p-6 text-center">
                    <p class="text-gray-500 mb-4">No knowledge bases match your search</p>
                    <button 
                        onclick={handleClearFilters}
                        class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1"
                    >
                        Clear search
                    </button>
                </div>
            {/if}
        {:else}
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {$_('knowledgeBases.list.nameColumn', { default: 'Name' })}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {$_('knowledgeBases.list.descriptionColumn', { default: 'Description' })}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {$_('knowledgeBases.list.createdColumn', { default: 'Created' })}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {$_('knowledgeBases.list.statusColumn', { default: 'Status' })}
                        </th>
                        <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {$_('knowledgeBases.list.actionsColumn', { default: 'Actions' })}
                        </th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {#each displayKnowledgeBases as kb (kb.id)}
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-medium text-gray-900">
                                    <button 
                                      type="button"
                                      onclick={() => viewKnowledgeBase(kb.id)}
                                      class="text-brand hover:text-brand-hover hover:underline text-left font-medium p-0 bg-transparent border-0 cursor-pointer"
                                    >
                                      {kb.name}
                                    </button>
                                </div>
                                <div class="text-sm text-gray-500">{kb.id}</div>
                                {#if kb.shared_by && !kb.is_owner}
                                    <div class="text-xs text-gray-400 mt-1">
                                        {$_('knowledgeBases.list.sharedBy', { values: { name: kb.shared_by }, default: `Shared by ${kb.shared_by}` })}
                                    </div>
                                {/if}
                            </td>
                            <td class="px-6 py-4 whitespace-normal">
                                <div class="text-sm text-gray-900">{kb.description || '-'}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-900">{formatDate(kb.created_at)}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                {#if kb.is_owner}
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {kb.is_shared ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                                        {kb.is_shared ? $_('knowledgeBases.list.shared', { default: 'Shared' }) : $_('knowledgeBases.list.private', { default: 'Private' })}
                                    </span>
                                {:else}
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                                        {$_('knowledgeBases.list.readOnly', { default: 'Read-Only' })}
                                    </span>
                                {/if}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <div class="flex items-center justify-end gap-2">
                                    {#if kb.is_owner}
                                        <!-- Sharing toggle for owners -->
                                        <button
                                            onclick={() => handleToggleSharing(kb)}
                                            class="text-sm px-2 py-1 rounded border {kb.is_shared ? 'border-green-300 text-green-700 bg-green-50 hover:bg-green-100' : 'border-gray-300 text-gray-700 bg-gray-50 hover:bg-gray-100'}"
                                            title={kb.is_shared ? $_('knowledgeBases.list.makePrivate', { default: 'Make private' }) : $_('knowledgeBases.list.shareWithOrg', { default: 'Share with organization' })}
                                        >
                                            {kb.is_shared ? '🔒 Unshare' : '🔓 Share'}
                                        </button>
                                    {/if}
                                    <button 
                                        onclick={() => viewKnowledgeBase(kb.id)}
                                        class="text-brand hover:text-brand-hover"
                                    >
                                        {$_('knowledgeBases.list.viewButton', { default: 'View' })}
                                    </button>
                                    {#if kb.is_owner}
                                        <button 
                                            type="button"
                                            onclick={() => viewKnowledgeBase(kb.id)}
                                            class="text-brand hover:text-brand-hover"
                                        >
                                            {$_('knowledgeBases.list.editButton', { default: 'Edit' })}
                                        </button>
                                        <button 
                                            type="button"
                                            class="text-red-600 hover:text-red-900" 
                                            onclick={() => handleDeleteKnowledgeBase(kb)}>
                                            {$_('knowledgeBases.list.deleteButton', { default: 'Delete' })}
                                        </button>
                                    {/if}
                                </div>
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
        
        <!-- Pagination -->
        {#if totalPages > 1}
            <Pagination
                {currentPage}
                {totalPages}
                {totalItems}
                {itemsPerPage}
                itemsPerPageOptions={[5, 10, 25, 50]}
                on:pageChange={handlePageChange}
                on:itemsPerPageChange={handleItemsPerPageChange}
            />
        {/if}
        {/if}
    {/if}
    
    <!-- Create Knowledge Base Modal -->
    <CreateKnowledgeBaseModal 
        bind:this={createModal} 
        on:created={handleKnowledgeBaseCreated}
    />
</div> 