<script>
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { goto } from '$app/navigation';
  import PublishModal from './PublishModal.svelte';
  import { createEventDispatcher } from 'svelte';
  import { publishModalOpen, selectedAssistant } from '$lib/stores/assistantPublish';
  import { user } from '$lib/stores/userStore';
  import { getAssistants, getSharedAssistants, deleteAssistant, downloadAssistant, unpublishAssistant } from '$lib/services/assistantService';
  import { base } from '$app/paths';
  import { browser } from '$app/environment';
  import { _, locale } from '$lib/i18n';
  
  // Import new components and utilities
  import Pagination from './common/Pagination.svelte';
  import FilterBar from './common/FilterBar.svelte';
    import DeleteConfirmationModal from './modals/DeleteConfirmationModal.svelte';
    import { processListData } from '$lib/utils/listHelpers';
    import { formatDateForTable } from '$lib/utils/dateHelpers';

    // State for the delete confirmation modal
    let showDeleteModal = $state(false);
    /** @type {{ id: number|null, name: string, published: boolean }} */
    let deleteTarget = $state({ id: null, name: '', published: false });
    let isDeleting = $state(false);
    // Handler to open the delete confirmation modal
    function handleDelete(assistant) {
        deleteTarget = {
            id: assistant.id,
            name: assistant.name ?? '',
            published: !!assistant.published
        };
        showDeleteModal = true;
    }

    // Handler to confirm deletion from the modal
    async function handleDeleteConfirm() {
        if (!deleteTarget.id || isDeleting) return;
        isDeleting = true;
        try {
            await deleteAssistant(deleteTarget.id);
            await loadAllAssistants(); // Refresh the list automatically
        } catch (err) {
            console.error('Error deleting assistant:', err);
            // Optional: show error to user
        } finally {
            isDeleting = false;
            showDeleteModal = false;
            deleteTarget = { id: null, name: '', published: false };
        }
    }

    // Handler to cancel deletion from the modal
    function handleDeleteCancel() {
        showDeleteModal = false;
        deleteTarget = { id: null, name: '', published: false };
    }
  
  // ✅ CORRECT: Props using $props()
  let { showShared = false } = $props();
  
  // Default text for when i18n isn't loaded yet
  let localeLoaded = $state(!!get(locale));
  const dispatch = createEventDispatcher();
  
  // All assistants (fetched once)
  /** @type {Array<any>} */
  let allAssistants = $state([]);
  
  // Filtered and paginated assistants (for display)
  /** @type {Array<any>} */
  let displayAssistants = $state([]);
  
  // Loading and error states
  let loading = $state(true);
  /** @type {string | null} */
  let error = $state(null);
  let isRefreshing = $state(false);
  
  // Filter state
  let searchTerm = $state('');
  let filterStatus = $state(''); // '', 'published', 'unpublished'
  
  // Sort state
  let sortBy = $state('updated_at');
  let sortOrder = $state('desc');
  
  // Pagination state
  let currentPage = $state(1);
  let itemsPerPage = $state(10);
  let totalPages = $state(1);
  let totalItems = $state(0);
  
  // Lifecycle and Data Loading
  let localeUnsubscribe = () => {};
  let userUnsubscribe = () => {};

  onMount(() => {
    localeUnsubscribe = locale.subscribe(value => {
      if (value) {
        localeLoaded = true;
      }
    });
    
    if (browser) {
      userUnsubscribe = user.subscribe(userData => {
        if (userData.isLoggedIn) {
          if (allAssistants.length === 0 && !loading) {
             console.log('User logged in, loading assistants...');
             loadAllAssistants();
          }
        } else {
          console.log('User logged out, clearing assistants.');
          allAssistants = [];
          displayAssistants = [];
          totalItems = 0;
          currentPage = 1;
          error = null;
          loading = false; 
        }
      });

      const initialUserData = $user;
      if(initialUserData.isLoggedIn) {
        console.log('User already logged in on mount, loading assistants...');
        loadAllAssistants();
      }
    }
    
    return () => {
      localeUnsubscribe();
      if (userUnsubscribe) userUnsubscribe();
    };
  });

  // Load all assistants (with high limit for client-side processing)
  async function loadAllAssistants() {
    loading = true;
    error = null;
    try {
      console.log(showShared ? 'Fetching shared assistants...' : 'Fetching all assistants...');
      const response = showShared 
        ? await getSharedAssistants() 
        : await getAssistants(100, 0); // Backend max is 100 items
      console.log('Received assistants:', response);
      
      allAssistants = response.assistants || [];
      applyFiltersAndPagination();
    } catch (err) {
      console.error('Error loading assistants:', err);
      error = err instanceof Error ? err.message : String(err);
      allAssistants = [];
      displayAssistants = [];
      totalItems = 0;
    } finally {
      loading = false;
    }
  }
  
  // Apply filters, sorting, and pagination
  function applyFiltersAndPagination() {
    const result = processListData(allAssistants, {
      search: searchTerm,
      searchFields: ['name', 'description', 'owner'],
      filters: {
        published: filterStatus === '' ? null : (filterStatus === 'published')
      },
      sortBy,
      sortOrder,
      page: currentPage,
      itemsPerPage
    });
    
    displayAssistants = result.items;
    totalItems = result.filteredCount;
    totalPages = result.totalPages;
    currentPage = result.currentPage; // Use safe page from result
  }
  
  // Refresh function
  async function handleRefresh() {
    if (isRefreshing) return;
    console.log('Manual refresh triggered...');
    isRefreshing = true;
    await loadAllAssistants();
    isRefreshing = false;
  }
  
  // --- Filter and Pagination Event Handlers ---
  
  function handleSearchChange(event) {
    searchTerm = event.detail.value;
    currentPage = 1; // Reset to first page
    applyFiltersAndPagination();
  }
  
  function handleFilterChange(event) {
    const { key, value } = event.detail;
    if (key === 'status') {
      filterStatus = value;
    }
    currentPage = 1; // Reset to first page
    applyFiltersAndPagination();
  }
  
  function handleSortChange(event) {
    sortBy = event.detail.sortBy;
    sortOrder = event.detail.sortOrder;
    applyFiltersAndPagination();
  }
  
  // Handle column header click for sorting
  function handleColumnSort(column) {
    if (sortBy === column) {
      // Toggle order if clicking same column
      sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      // Set new column with default descending order
      sortBy = column;
      sortOrder = 'desc';
    }
    applyFiltersAndPagination();
  }
  
  // Handle date column sort - toggles between created_at and updated_at
  function handleDateColumnSort() {
    if (sortBy === 'created_at' || sortBy === 'updated_at') {
      // Toggle between created_at and updated_at
      if (sortBy === 'created_at') {
        sortBy = 'updated_at';
      } else {
        sortBy = 'created_at';
      }
      // Keep the same sort order
    } else {
      // Start with updated_at (default)
      sortBy = 'updated_at';
      sortOrder = 'desc';
    }
    applyFiltersAndPagination();
  }
  
  function handlePageChange(event) {
    currentPage = event.detail.page;
    applyFiltersAndPagination();
  }
  
  function handleItemsPerPageChange(event) {
    itemsPerPage = event.detail.itemsPerPage;
    currentPage = 1; // Reset to first page
    applyFiltersAndPagination();
  }
  
  function handleClearFilters() {
    searchTerm = '';
    filterStatus = '';
    sortBy = 'updated_at';
    sortOrder = 'desc';
    currentPage = 1;
    applyFiltersAndPagination();
  }
  
  // --- Action Handlers --- 

  /**
   * Handle view button click
   * @param {number} id - The ID of the assistant to view
   */
  function handleView(id) { 
    console.log(`View assistant (navigate to detail view): ${id}`);
    const targetUrl = `${base}/assistants?view=detail&id=${id}`;
    console.log('[AssistantsList] Navigating to view:', targetUrl);
    goto(targetUrl); 
  }
  
  /**
   * Handle edit button click
   * @param {number} id - The ID of the assistant to edit
   */
  function handleEdit(id) { 
    console.log(`Edit assistant (navigate to detail view in edit mode): ${id}`);
    const targetUrl = `${base}/assistants?view=detail&id=${id}&startInEdit=true`;
    console.log('[AssistantsList] Navigating to edit:', targetUrl);
    goto(targetUrl); 
  }
  
  /** @param {{ detail: { id: number } }} event */
  function handleClone(event) { 
      const id = Number(event.detail.id);
      console.log('Clone assistant (not implemented):', id);
      alert(localeLoaded ? $_('assistants.actions.cloneNotImplemented', { default: 'Clone functionality not yet implemented.' }) : 'Clone functionality not yet implemented.');
  }
  
  /** @param {{ detail: { assistantId: number; groupId: string | null | undefined; ownerEmail: string } }} event */
  async function handleUnpublish(event) { 
      const assistantId = Number(event.detail.assistantId);
      const { groupId, ownerEmail } = event.detail;
      if (!groupId || !ownerEmail) {
          alert(localeLoaded ? $_('assistants.unpublishErrorMissingData') : 'Cannot unpublish: Missing group ID or owner email.');
          return;
      }
      const assistantToUnpublish = allAssistants.find(a => a.id === assistantId);
      const confirmMessage = localeLoaded ? $_('assistants.unpublishConfirm', { values: { name: assistantToUnpublish?.name || assistantId } }) : `Are you sure you want to unpublish assistant ${assistantId}?`;
      if (confirm(confirmMessage)) {
          try {
              await unpublishAssistant(assistantId.toString(), groupId, ownerEmail);
              await loadAllAssistants();
              alert(localeLoaded ? $_('assistants.unpublishSuccess') : 'Assistant unpublished successfully!');
          } catch (err) {
              console.error('Error unpublishing assistant:', err);
              const errorMsg = err instanceof Error ? err.message : 'Failed to unpublish assistant';
              error = errorMsg;
              alert(localeLoaded ? $_('assistants.unpublishError', { values: { error: errorMsg } }) : `Error: ${errorMsg}`);
          }
      }
  }
  
  // --- Helper Functions ---
  /** @param {string | undefined | null} jsonString */
  function parseMetadata(jsonString) {
    if (!jsonString) return {};
    try {
      return JSON.parse(jsonString);
    } catch (e) {
      console.error('Error parsing metadata:', e, jsonString);
      return {};
    }
  }

  // --- SVG Icons (Ensure definitions are present) --- 
  const IconView = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>`;
  const IconEdit = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>`;
  const IconClone = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75c-.621 0-1.125-.504-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" /></svg>`;
  const IconDelete = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>`;
  const IconRefresh = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>`;
  const IconExport = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>`;
  const IconUnpublish = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75c-.621 0-1.125-.504-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" /></svg>`;
</script>

<!-- Container for the list -->
<div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">

    {#if loading}
        <p class="text-center text-gray-500 py-4">{localeLoaded ? $_('assistants.loading', { default: 'Loading assistants...' }) : 'Loading assistants...'}</p>
    {:else if error}
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <strong class="font-bold">{localeLoaded ? $_('assistants.errorTitle') : 'Error:'}</strong>
            <span class="block sm:inline">{error}</span>
        </div>
    {:else}
        <!-- Filter Bar -->
        <FilterBar
            searchPlaceholder={localeLoaded ? $_('assistants.searchPlaceholder', { default: 'Search assistants by name, description...' }) : 'Search assistants by name, description...'}
            searchValue={searchTerm}
            filters={[
                {
                    key: 'status',
                    label: localeLoaded ? $_('assistants.filters.status', { default: 'Status' }) : 'Status',
                    options: [
                        { value: 'published', label: localeLoaded ? $_('assistants.status.published', { default: 'Published' }) : 'Published' },
                        { value: 'unpublished', label: localeLoaded ? $_('assistants.status.unpublished', { default: 'Not Published' }) : 'Not Published' }
                    ]
                }
            ]}
            filterValues={{ status: filterStatus }}
            sortOptions={[
                { value: 'name', label: localeLoaded ? $_('assistants.sort.name', { default: 'Name' }) : 'Name' },
                { value: 'updated_at', label: localeLoaded ? $_('assistants.sort.updated', { default: 'Last Modified' }) : 'Last Modified' },
                { value: 'created_at', label: localeLoaded ? $_('assistants.sort.created', { default: 'Created Date' }) : 'Created Date' }
            ]}
            {sortBy}
            {sortOrder}
            on:searchChange={handleSearchChange}
            on:filterChange={handleFilterChange}
            on:sortChange={handleSortChange}
            on:clearFilters={handleClearFilters}
        />
        
        <!-- Results count and refresh button -->
        <div class="flex justify-between items-center mb-4 px-4">
            <div class="text-sm text-gray-600">
                {#if searchTerm || filterStatus}
                    {localeLoaded ? $_('assistants.showingFiltered', { default: 'Showing' }) : 'Showing'} <span class="font-medium">{totalItems}</span> {localeLoaded ? $_('assistants.of', { default: 'of' }) : 'of'} <span class="font-medium">{allAssistants.length}</span> {localeLoaded ? $_('assistants.items', { default: 'assistants' }) : 'assistants'}
                {:else}
                    <span class="font-medium">{totalItems}</span> {localeLoaded ? $_('assistants.totalItems', { default: 'assistants' }) : 'assistants'}
                {/if}
            </div>
            
            <!-- Refresh button -->
            <button 
                onclick={handleRefresh} 
                disabled={loading || isRefreshing} 
                title={localeLoaded ? $_('common.refresh', { default: 'Refresh' }) : 'Refresh'}
                class="p-2 text-sm font-medium bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <span class:animate-spin={isRefreshing}>
                    {@html IconRefresh}
                </span>
            </button>
        </div>

        {#if displayAssistants.length === 0}
            {#if allAssistants.length === 0}
                <!-- No assistants at all -->
                <div class="text-center py-12 bg-white border border-gray-200 rounded-lg">
                    <p class="text-gray-500">{localeLoaded ? $_('assistants.noAssistants', { default: 'No assistants found.' }) : 'No assistants found.'}</p>
                </div>
            {:else}
                <!-- No results match filters -->
                <div class="text-center py-12 bg-white border border-gray-200 rounded-lg">
                    <p class="text-gray-500 mb-4">{localeLoaded ? $_('assistants.noMatches', { default: 'No assistants match your filters' }) : 'No assistants match your filters'}</p>
                    <button 
                        onclick={handleClearFilters}
                        class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1"
                    >
                        {localeLoaded ? $_('common.clearFilters', { default: 'Clear filters' }) : 'Clear filters'}
                    </button>
                </div>
            {/if}
        {:else}
        <!-- Responsive Table Wrapper -->
        <div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200">
            <table class="min-w-full divide-y divide-gray-200 table-fixed">
                <colgroup>
                    <col class="w-1/5">
                    <col class="w-2/5">
                    <col class="w-1/5">
                    <col class="w-1/5">
                </colgroup>
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none" onclick={() => handleColumnSort('name')}>
                            <div class="flex items-center gap-1">
                                {localeLoaded ? $_('assistants.table.name', { default: 'Assistant Name' }) : 'Assistant Name'}
                                {#if sortBy === 'name'}
                                    {#if sortOrder === 'asc'}
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
                                        </svg>
                                    {:else}
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
                                        </svg>
                                    {/if}
                                {/if}
                            </div>
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('assistants.table.description', { default: 'Description' }) : 'Description'}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap" onclick={handleDateColumnSort}>
                            <div class="flex items-center gap-1">
                                {localeLoaded ? $_('assistants.table.createdUpdated', { default: 'Created / Updated' }) : 'Created / Updated'}
                                {#if sortBy === 'created_at' || sortBy === 'updated_at'}
                                    <span class="text-xs text-gray-500 ml-1">
                                        ({sortBy === 'created_at' ? 'Created' : 'Updated'})
                                    </span>
                                    {#if sortOrder === 'asc'}
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
                                        </svg>
                                    {:else}
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
                                        </svg>
                                    {/if}
                                {/if}
                            </div>
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('assistants.table.actions', { default: 'Actions' }) : 'Actions'}
                        </th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {#each displayAssistants as assistant (assistant.id)}
                        <!-- Main row with name, description, actions -->
                        <tr class="hover:bg-gray-50">
                            <!-- Assistant Name -->
                            <td class="px-6 py-4 whitespace-normal align-top">
                                <button onclick={() => handleView(assistant.id)} class="text-sm font-medium text-brand hover:underline break-words text-left">
                                    {assistant.name || '-'}
                                </button>
                                <!-- Status badge -->
                                <div class="mt-1">
                                    {#if assistant.published}
                                        <span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 px-2 py-0.5">{localeLoaded ? $_('assistants.status.published', { default: 'Published' }) : 'Published'}</span>
                                    {:else}
                                        <span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5">{localeLoaded ? $_('assistants.status.unpublished', { default: 'Unpublished' }) : 'Unpublished'}</span>
                                    {/if}
                                    {#if showShared}
                                        <span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 ml-1">{localeLoaded ? $_('assistants.status.sharedWithYou', { default: 'Shared with you' }) : 'Shared with you'}</span>
                                    {/if}
                                </div>
                            </td>
                            
                            <!-- Description with more space -->
                            <td class="px-6 py-4 align-top">
                                <div class="text-sm text-gray-500 break-words">{assistant.description || (localeLoaded ? $_('assistants.noDescription', { default: 'No description provided' }) : 'No description provided')}</div>
                            </td>
                            
                            <!-- Created / Updated Dates (combined column) -->
                            <td class="px-6 py-4 text-sm text-gray-500 align-top">
                                <div class="flex flex-col gap-1">
                                    <div>
                                        <span class="text-xs text-gray-400 font-medium">Created:</span>
                                        <div class="text-xs">{formatDateForTable(assistant.created_at)}</div>
                                    </div>
                                    <div>
                                        <span class="text-xs text-gray-400 font-medium">Updated:</span>
                                        <div class="text-xs">{formatDateForTable(assistant.updated_at)}</div>
                                    </div>
                                </div>
                            </td>
                            
                            <!-- Actions -->
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium align-top">
                                <div class="flex items-center space-x-1 sm:space-x-2">
                                    <!-- View Button -->
                                    <button onclick={() => handleView(assistant.id)} title={localeLoaded ? $_('assistants.actions.view', { default: 'View' }) : 'View'} class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150">
                                        {@html IconView}
                                    </button>
                                    <!-- Export Button -->
                                    <button 
                                        onclick={() => dispatch('export', { id: assistant.id })} 
                                        title={localeLoaded ? $_('assistants.actions.export', { default: 'Export JSON' }) : 'Export JSON'} 
                                        class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150"
                                    >
                                        {@html IconExport}
                                    </button>
                                    <!-- Publish/Unpublish Button -->
                                    {#if assistant.published}
                                        <button onclick={() => handleUnpublish({ detail: { assistantId: assistant.id, groupId: assistant.group_id, ownerEmail: assistant.owner } })} title={localeLoaded ? $_('assistants.actions.unpublish', { default: 'Unpublish' }) : 'Unpublish'} class="text-yellow-600 hover:text-yellow-900 p-1 rounded hover:bg-yellow-100 transition-colors duration-150">
                                            {@html IconUnpublish}
                                        </button>
                                    {:else}
                                        <!-- Delete Button (Only show if not published) -->
                                        <button 
                                            onclick={() => handleDelete(assistant)}
                                            title={localeLoaded ? $_('assistants.actions.delete', { default: 'Delete' }) : 'Delete'} 
                                            class="text-red-600 hover:text-red-900 p-1 rounded hover:bg-red-100 transition-colors duration-150"
                                        >
                                            {@html IconDelete}
                                        </button>
<!-- Delete Confirmation Modal -->
<DeleteConfirmationModal
    isOpen={showDeleteModal}
    assistantName={deleteTarget.name}
    isDeleting={isDeleting}
    on:confirm={handleDeleteConfirm}
    on:close={handleDeleteCancel}
/>
                                    {/if}
                                </div>
                                <div class="text-xs text-gray-400 mt-2">ID: {assistant.id}</div>
                            </td>
                        </tr>
                        
                        <!-- Configuration rows -->
                                      {#if assistant.metadata}
                {@const callback = parseMetadata(assistant.metadata)}
                            <!-- Single configuration row with all details -->
                            <tr class="bg-gray-50 border-b border-gray-200">
                                <td colspan="2" class="px-6 py-2 text-sm">
                                    <div class="flex flex-wrap items-center">
                                        <span class="text-brand font-medium mr-1">{localeLoaded ? $_('assistants.table.promptProcessor', { default: 'Prompt Processor' }) : 'Prompt Processor'}:</span>
                                        <span class="mr-3">{callback.prompt_processor || (localeLoaded ? $_('assistants.notSet', { default: 'Not set' }) : 'Not set')}</span>
                                        
                                        <span class="text-brand font-medium mr-1">{localeLoaded ? $_('assistants.table.connector', { default: 'Connector' }) : 'Connector'}:</span>
                                        <span class="mr-3">{callback.connector || (localeLoaded ? $_('assistants.notSet', { default: 'Not set' }) : 'Not set')}</span>
                                        
                                        <span class="text-brand font-medium mr-1">{localeLoaded ? $_('assistants.table.llm', { default: 'LLM' }) : 'LLM'}:</span>
                                        <span class="mr-3">{callback.llm || (localeLoaded ? $_('assistants.notSet', { default: 'Not set' }) : 'Not set')}</span>
                                        
                                        <span class="text-brand font-medium mr-1">{localeLoaded ? $_('assistants.table.ragProcessor', { default: 'RAG Processor' }) : 'RAG Processor'}:</span>
                                        <span>{callback.rag_processor || (localeLoaded ? $_('assistants.notSet', { default: 'Not set' }) : 'Not set')}</span>
                                    </div>
                                </td>
                                <td class="px-6 py-2"></td> <!-- Empty cell to maintain table structure -->
                            </tr>
                            
                            <!-- Conditional row for simple_rag details -->
                            {#if callback.rag_processor === 'simple_rag'}
                                <tr class="bg-gray-50 border-b border-gray-200">
                                    <td colspan="2" class="px-6 py-2 text-sm">
                                        <div class="flex flex-wrap">
                                            <div class="mr-6 mb-1">
                                                <span class="text-brand font-medium">{localeLoaded ? $_('assistants.table.ragTopK', { default: 'RAG Top K' }) : 'RAG Top K'}:</span>
                                                <span class="ml-1">{assistant.RAG_Top_k ?? (localeLoaded ? $_('assistants.notSet', { default: 'Not set' }) : 'Not set')}</span>
                                            </div>
                                            <div>
                                                <span class="text-brand font-medium">{localeLoaded ? $_('assistants.table.ragCollections', { default: 'RAG Collections' }) : 'RAG Collections'}:</span>
                                                <span class="ml-1 truncate" title={assistant.RAG_collections || ''}>{assistant.RAG_collections || (localeLoaded ? $_('assistants.notSet', { default: 'Not set' }) : 'Not set')}</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td class="px-6 py-2"></td> <!-- Empty cell to maintain table structure -->
                                </tr>
                            {/if}
                        {:else}
                            <!-- Placeholder row for when no metadata is available -->
                            <tr class="bg-gray-50 border-b border-gray-200">
                                <td colspan="2" class="px-6 py-2 text-sm text-gray-500">
                                    <span class="text-brand font-medium">{localeLoaded ? $_('assistants.table.config', { default: 'Configuration' }) : 'Configuration'}:</span>
                                    <span class="ml-1">{localeLoaded ? $_('assistants.notSet', { default: 'Not available' }) : 'Not available'}</span>
                                </td>
                                <td class="px-6 py-2"></td> <!-- Empty cell to maintain table structure -->
                            </tr>
                        {/if}
                    {/each}
                </tbody>
            </table>
        </div>

        <!-- Pagination Controls -->
        {#if totalPages > 1}
            <Pagination
                {currentPage}
                {totalPages}
                {totalItems}
                {itemsPerPage}
                itemsPerPageOptions={[5, 10, 25, 50, 100]}
                on:pageChange={handlePageChange}
                on:itemsPerPageChange={handleItemsPerPageChange}
            />
        {/if}
        {/if}
    {/if}
</div>

<!-- Publish Modal -->
{#if $publishModalOpen}
    <!-- <PublishModal on:assistantPublished={handleAssistantPublished} /> -->
{/if} 