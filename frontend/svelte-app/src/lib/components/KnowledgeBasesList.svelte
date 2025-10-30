<script>
    import { onMount } from 'svelte';
    import { getKnowledgeBases, deleteKnowledgeBase } from '$lib/services/knowledgeBaseService';
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
     */
    
    // State management
    /** @type {KnowledgeBase[]} */
    let allKnowledgeBases = $state([]);
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
            
            // Fetch knowledge bases
            const data = await getKnowledgeBases();
            allKnowledgeBases = data || [];
            console.log('Knowledge bases loaded:', allKnowledgeBases.length);
            applyFiltersAndPagination();
            
        } catch (/** @type {unknown} */ err) {
            console.error('Error loading knowledge bases:', err);
            error = err instanceof Error ? err.message : 'Failed to load knowledge bases';
            
            // Check if server is offline based on error message
            if (err instanceof Error && err.message.includes('server offline')) {
                serverOffline = true;
            }
            allKnowledgeBases = [];
            displayKnowledgeBases = [];
        } finally {
            loading = false;
        }
    }
    
    // Apply filters, sorting, and pagination
    function applyFiltersAndPagination() {
        const result = processListData(allKnowledgeBases, {
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
            applyFiltersAndPagination();
            successMessage = $_('knowledgeBases.list.deleteSuccess', { default: 'Knowledge base deleted.' });
            setTimeout(() => { successMessage = ''; }, 4000);
        } catch (e) {
            alert(e instanceof Error ? e.message : 'Deletion failed');
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
                    Showing <span class="font-medium">{totalItems}</span> of <span class="font-medium">{allKnowledgeBases.length}</span> knowledge bases
                {:else}
                    <span class="font-medium">{totalItems}</span> knowledge bases
                {/if}
            </div>
        </div>
        
        {#if displayKnowledgeBases.length === 0}
            {#if allKnowledgeBases.length === 0}
                <!-- No knowledge bases at all -->
                <div class="p-6 text-center">
                    <div class="text-gray-500">
                        {$_('knowledgeBases.list.empty', { default: 'No knowledge bases found.' })}
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
                            {$_('knowledgeBases.list.accessColumn', { default: 'Access' })}
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
                            </td>
                            <td class="px-6 py-4 whitespace-normal">
                                <div class="text-sm text-gray-900">{kb.description || '-'}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm text-gray-900">{formatDate(kb.created_at)}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {kb.metadata?.access_control === 'private' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}">
                                    {kb.metadata?.access_control || 'public'}
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button 
                                    onclick={() => viewKnowledgeBase(kb.id)}
                                    class="text-brand hover:text-brand-hover mr-2"
                                >
                                    {$_('knowledgeBases.list.viewButton', { default: 'View' })}
                                </button>
                                <button 
                                    type="button"
                                    onclick={() => viewKnowledgeBase(kb.id)}
                                    class="text-brand hover:text-brand-hover mr-2"
                                >
                                    {$_('knowledgeBases.list.editButton', { default: 'Edit' })}
                                </button>
                                <button 
                                    type="button"
                                    class="text-red-600 hover:text-red-900" 
                                    onclick={() => handleDeleteKnowledgeBase(kb)}>
                                    {$_('knowledgeBases.list.deleteButton', { default: 'Delete' })}
                                </button>
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