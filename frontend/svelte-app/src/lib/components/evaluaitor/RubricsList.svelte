<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { createEventDispatcher } from 'svelte';
  import { _, locale } from '$lib/i18n';
  import { getApiUrl } from '$lib/config';
  import {
    fetchRubrics,
    fetchPublicRubrics,
    fetchShowcaseRubrics,
    createRubric,
    duplicateRubric,
    deleteRubric,
    exportRubricJSON,
    exportRubricMarkdown,
    importRubric,
    toggleRubricVisibility
  } from '$lib/services/rubricService';
  
  // Import filtering/pagination components
  import Pagination from '../common/Pagination.svelte';
  import FilterBar from '../common/FilterBar.svelte';
  import { processListData } from '$lib/utils/listHelpers';

  // Default text for when i18n isn't loaded yet
  let localeLoaded = $state(!!$locale);

  // Create dispatcher for events
  const dispatch = createEventDispatcher();

  // State
  let allRubrics = $state([]);
  let displayRubrics = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let activeTab = $state('my-rubrics'); // 'my-rubrics' | 'templates'
  
  // Filter/sort state
  let searchTerm = $state('');
  let sortBy = $state('updated_at');
  let sortOrder = $state('desc');
  
  // Pagination state
  let currentPage = $state(1);
  let itemsPerPage = $state(10);
  let totalPages = $state(1);
  let totalItems = $state(0);

  // Load all rubrics based on active tab
  async function loadRubrics() {
    loading = true;
    error = null;

    try {
      // Fetch all rubrics (high limit for client-side processing)
      let response;
      
      if (activeTab === 'my-rubrics') {
        response = await fetchRubrics(1000, 0, {});
      } else {
        response = await fetchPublicRubrics(1000, 0, {});
      }
      
      allRubrics = response.rubrics || [];
      applyFiltersAndPagination();
    } catch (err) {
      error = err.message || `Failed to load ${activeTab === 'my-rubrics' ? 'rubrics' : 'templates'}`;
      console.error(`Error loading ${activeTab}:`, err);
      allRubrics = [];
      displayRubrics = [];
    } finally {
      loading = false;
    }
  }
  
  // Apply filters, sorting, and pagination
  function applyFiltersAndPagination() {
    const result = processListData(allRubrics, {
      search: searchTerm,
      searchFields: ['title', 'description'],
      filters: {},
      sortBy,
      sortOrder,
      page: currentPage,
      itemsPerPage
    });
    
    displayRubrics = result.items;
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
    sortBy = 'updated_at';
    sortOrder = 'desc';
    currentPage = 1;
    applyFiltersAndPagination();
  }

  // Handle rubric actions
  function handleView(rubric) {
    goto(`/evaluaitor/${rubric.rubric_id}`);
  }

  function handleEdit(rubric) {
    goto(`/evaluaitor/${rubric.rubric_id}?edit=true`);
  }

  function handleDelete(rubric) {
    dispatch('delete', { id: rubric.rubric_id, title: rubric.title });
  }

  async function handleExport(rubric) {
    try {
      // Export both JSON and Markdown formats
      await handleExportJSON(rubric);
      await handleExportMarkdown(rubric);
    } catch (error) {
      console.error('Export failed:', error);
      // You could show a toast notification here
    }
  }

  async function handleExportJSON(rubric) {
    try {
      const token = localStorage.getItem('userToken');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const apiUrl = getApiUrl(`/rubrics/${rubric.rubric_id}/export/json`);
      const response = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
        }
      });

      if (!response.ok) {
        throw new Error('Failed to export rubric as JSON');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      // Get filename from Content-Disposition header or create default
      const disposition = response.headers.get('Content-Disposition');
      const filename = disposition ?
        disposition.split('filename=')[1]?.replace(/"/g, '') :
        `rubric-${rubric.rubric_id}.json`;

      // Trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

    } catch (error) {
      console.error('JSON export failed:', error);
      throw error;
    }
  }

  async function handleExportMarkdown(rubric) {
    try {
      const token = localStorage.getItem('userToken');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const apiUrl = getApiUrl(`/rubrics/${rubric.rubric_id}/export/markdown`);
      const response = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
        }
      });

      if (!response.ok) {
        throw new Error('Failed to export rubric as Markdown');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      // Get filename from Content-Disposition header or create default
      const disposition = response.headers.get('Content-Disposition');
      const filename = disposition ?
        disposition.split('filename=')[1]?.replace(/"/g, '') :
        `rubric-${rubric.rubric_id}.md`;

      // Trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Markdown export failed:', error);
      throw error;
    }
  }

  async function handleToggleVisibility(rubric) {
    try {
      const newVisibility = !rubric.is_public;
      console.log(`Toggling rubric ${rubric.rubric_id} visibility to ${newVisibility ? 'public' : 'private'}`);
      
      await toggleRubricVisibility(rubric.rubric_id, newVisibility);
      
      // Update local state
      rubric.is_public = newVisibility;
      
      console.log(`Rubric visibility updated successfully to ${newVisibility ? 'public' : 'private'}`);
      
      // Refresh the list to ensure consistency
      loadRubrics();
    } catch (error) {
      console.error('Error toggling visibility:', error);
      // You could show a toast notification here
    }
  }

  async function handleCreateCopy(rubric) {
    try {
      const newRubric = await duplicateRubric(rubric.rubric_id);
      // Navigate to the new rubric for editing
      goto(`/evaluaitor/${newRubric.rubric.rubricId}?edit=true`);
    } catch (error) {
      console.error('Error creating copy:', error);
      // You could show a toast notification here
    }
  }

  function switchTab(tab) {
    if (tab !== activeTab) {
      activeTab = tab;
      searchTerm = ''; // Reset search on tab switch
      currentPage = 1;
      loadRubrics();
    }
  }

  function handleRefresh() {
    loadRubrics();
  }

  // Initialize
  onMount(() => {
    loadRubrics();
  });

  // SVG Icons
  const IconView = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>`;
  const IconEdit = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>`;
  const IconClone = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75c-.621 0-1.125-.504-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" /></svg>`;
  const IconDelete = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>`;
  const IconExport = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>`;
  const IconRefresh = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>`;
  const IconPublic = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3s-4.5 4.03-4.5 9 2.015 9 4.5 9Z" /></svg>`;
  const IconPrivate = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" /></svg>`;
</script>

<!-- Container for the list -->
<div class="container mx-auto px-4 py-8">

    <!-- Tab Navigation -->
    <div class="border-b border-gray-200 mb-6">
        <nav class="-mb-px flex space-x-8" aria-label="Tabs">
            <button
                onclick={() => switchTab('my-rubrics')}
                class={`py-2 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'my-rubrics'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
            >
                {localeLoaded ? $_('rubrics.tabs.myRubrics', { default: 'My Rubrics' }) : 'My Rubrics'}
            </button>
            <button
                onclick={() => switchTab('templates')}
                class={`py-2 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'templates'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
            >
                {localeLoaded ? $_('rubrics.tabs.templates', { default: 'Templates' }) : 'Templates'}
            </button>
        </nav>
    </div>

    {#if loading}
        <p class="text-center text-gray-500 py-4">{localeLoaded ? $_('rubrics.loading', { default: 'Loading rubrics...' }) : 'Loading rubrics...'}</p>
    {:else if error}
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <strong class="font-bold">{localeLoaded ? $_('rubrics.errorTitle', { default: 'Error:' }) : 'Error:'}</strong>
            <span class="block sm:inline">{error}</span>
        </div>
    {:else}
        <!-- Filter Bar -->
        <FilterBar
            searchPlaceholder={localeLoaded ? $_('rubrics.searchPlaceholder', { default: 'Search rubrics by title, description...' }) : 'Search rubrics by title, description...'}
            searchValue={searchTerm}
            filters={[]}
            filterValues={{}}
            sortOptions={[
                { value: 'title', label: localeLoaded ? $_('common.sortByName', { default: 'Title' }) : 'Title' },
                { value: 'updated_at', label: localeLoaded ? $_('common.sortByUpdated', { default: 'Last Modified' }) : 'Last Modified' },
                { value: 'created_at', label: localeLoaded ? $_('common.sortByCreated', { default: 'Created Date' }) : 'Created Date' }
            ]}
            {sortBy}
            {sortOrder}
            on:searchChange={handleSearchChange}
            on:sortChange={handleSortChange}
            on:clearFilters={handleClearFilters}
        />
        
        <!-- Results count and refresh button -->
        <div class="flex justify-between items-center mb-4 px-4">
            <div class="text-sm text-gray-600">
                {#if searchTerm}
                    Showing <span class="font-medium">{totalItems}</span> of <span class="font-medium">{allRubrics.length}</span> rubrics
                {:else}
                    <span class="font-medium">{totalItems}</span> rubrics
                {/if}
            </div>
            
            <!-- Refresh button -->
            <button 
                onclick={handleRefresh} 
                disabled={loading} 
                title={localeLoaded ? $_('common.refresh', { default: 'Refresh' }) : 'Refresh'}
                class="p-2 text-sm font-medium bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {@html IconRefresh}
            </button>
        </div>

        {#if displayRubrics.length === 0}
            {#if allRubrics.length === 0}
                <!-- No rubrics at all -->
                <div class="text-center py-12 bg-white border border-gray-200 rounded-lg">
                    <p class="text-gray-500">{localeLoaded ? $_('rubrics.noRubrics', { default: 'No rubrics found.' }) : 'No rubrics found.'}</p>
                </div>
            {:else}
                <!-- No results match filters -->
                <div class="text-center py-12 bg-white border border-gray-200 rounded-lg">
                    <p class="text-gray-500 mb-4">{localeLoaded ? $_('rubrics.noMatches', { default: 'No rubrics match your search' }) : 'No rubrics match your search'}</p>
                    <button 
                        onclick={handleClearFilters}
                        class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1"
                    >
                        {localeLoaded ? $_('common.clearFilters', { default: 'Clear search' }) : 'Clear search'}
                    </button>
                </div>
            {/if}
        {:else}
        <!-- Responsive Table Wrapper -->
        <div class="overflow-x-auto shadow-md sm:rounded-lg mb-6 border border-gray-200">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('rubrics.table.name', { default: 'Rubric Name' }) : 'Rubric Name'}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('rubrics.table.description', { default: 'Description' }) : 'Description'}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('rubrics.table.subject', { default: 'Subject' }) : 'Subject'}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('rubrics.table.gradeLevel', { default: 'Grade Level' }) : 'Grade Level'}
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-brand uppercase tracking-wider">
                            {localeLoaded ? $_('rubrics.table.actions', { default: 'Actions' }) : 'Actions'}
                        </th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {#each displayRubrics as rubric (rubric.id)}
                        <!-- Main row with name, description, subject, grade level, actions -->
                        <tr class="hover:bg-gray-50">
                            <!-- Rubric Name -->
                            <td class="px-6 py-4 whitespace-normal align-top">
                                <button onclick={() => handleView(rubric)} class="text-sm font-medium text-brand hover:underline break-words text-left">
                                    {rubric.title}
                                </button>
                                <!-- Status badge -->
                                <div class="mt-1">
                                    {#if rubric.is_showcase}
                                        <span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5">
                                            {localeLoaded ? $_('rubrics.status.showcase', { default: 'Showcase' }) : 'Showcase'}
                                        </span>
                                    {:else if rubric.is_public}
                                        <span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 px-2 py-0.5">
                                            {localeLoaded ? $_('rubrics.status.public', { default: 'Public' }) : 'Public'}
                                        </span>
                                    {:else}
                                        <span class="inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 px-2 py-0.5">
                                            {localeLoaded ? $_('rubrics.status.private', { default: 'Private' }) : 'Private'}
                                        </span>
                                    {/if}
                                </div>
                            </td>

                            <!-- Description with max width -->
                            <td class="px-6 py-4 align-top">
                                <div class="text-sm text-gray-500 break-words max-w-md">{rubric.description || (localeLoaded ? $_('rubrics.noDescription', { default: 'No description provided' }) : 'No description provided')}</div>
                            </td>

                            <!-- Subject -->
                            <td class="px-6 py-4 align-top">
                                <div class="text-sm text-gray-500">{rubric.subject || (localeLoaded ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}</div>
                            </td>

                            <!-- Grade Level -->
                            <td class="px-6 py-4 align-top">
                                <div class="text-sm text-gray-500">{rubric.gradeLevel || (localeLoaded ? $_('common.notSpecified', { default: 'Not specified' }) : 'Not specified')}</div>
                            </td>

                            <!-- Actions -->
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium align-top">
                                <div class="flex items-center space-x-1 sm:space-x-2">
                                    <!-- View Button (always shown) -->
                                    <button onclick={() => handleView(rubric)} title={localeLoaded ? $_('rubrics.actions.view', { default: 'View' }) : 'View'} class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150">
                                        {@html IconView}
                                    </button>
                                    
                                    {#if activeTab === 'my-rubrics'}
                                        <!-- My Rubrics actions: Edit, Export, Toggle Visibility, Delete -->
                                        <button onclick={() => handleEdit(rubric)} title={localeLoaded ? $_('rubrics.actions.edit', { default: 'Edit' }) : 'Edit'} class="text-blue-600 hover:text-blue-900 p-1 rounded hover:bg-blue-100 transition-colors duration-150">
                                            {@html IconEdit}
                                        </button>
                                        <button
                                            onclick={() => handleExport(rubric)}
                                            title={localeLoaded ? $_('rubrics.actions.export', { default: 'Export (JSON & Markdown)' }) : 'Export (JSON & Markdown)'}
                                            class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150"
                                        >
                                            {@html IconExport}
                                        </button>
                                        <button
                                            onclick={() => handleToggleVisibility(rubric)}
                                            title={rubric.is_public ? (localeLoaded ? $_('rubrics.actions.makePrivate', { default: 'Make Private' }) : 'Make Private') : (localeLoaded ? $_('rubrics.actions.makePublic', { default: 'Make Public' }) : 'Make Public')}
                                            class="text-yellow-600 hover:text-yellow-900 p-1 rounded hover:bg-yellow-100 transition-colors duration-150"
                                        >
                                            {#if rubric.is_public}
                                                {@html IconPrivate}
                                            {:else}
                                                {@html IconPublic}
                                            {/if}
                                        </button>
                                        <button
                                            onclick={() => handleDelete(rubric)}
                                            title={localeLoaded ? $_('rubrics.actions.delete', { default: 'Delete' }) : 'Delete'}
                                            class="text-red-600 hover:text-red-900 p-1 rounded hover:bg-red-100 transition-colors duration-150"
                                        >
                                            {@html IconDelete}
                                        </button>
                                    {:else}
                                        <!-- Templates actions: Export, Create Copy -->
                                        <button
                                            onclick={() => handleExport(rubric)}
                                            title={localeLoaded ? $_('rubrics.actions.export', { default: 'Export (JSON & Markdown)' }) : 'Export (JSON & Markdown)'}
                                            class="text-green-600 hover:text-green-900 p-1 rounded hover:bg-green-100 transition-colors duration-150"
                                        >
                                            {@html IconExport}
                                        </button>
                                        <button
                                            onclick={() => handleCreateCopy(rubric)}
                                            title={localeLoaded ? $_('rubrics.actions.createCopy', { default: 'Create Copy' }) : 'Create Copy'}
                                            class="text-purple-600 hover:text-purple-900 p-1 rounded hover:bg-purple-100 transition-colors duration-150"
                                        >
                                            {@html IconClone}
                                        </button>
                                    {/if}
                                </div>
                                <div class="text-xs text-gray-400 mt-2">
                                    {localeLoaded ? $_('rubrics.lastModified', { default: 'Modified' }) : 'Modified'}: {new Date(rubric.updated_at * 1000).toLocaleDateString()}
                                </div>
                                <div class="text-xs text-gray-400">ID: {rubric.rubric_id}</div>
                            </td>
                        </tr>
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
                itemsPerPageOptions={[5, 10, 25, 50]}
                on:pageChange={handlePageChange}
                on:itemsPerPageChange={handleItemsPerPageChange}
            />
        {/if}
        {/if}
    {/if}
</div>
