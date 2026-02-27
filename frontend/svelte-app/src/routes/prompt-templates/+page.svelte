<script>
  import { onMount } from 'svelte';
  import { _, locale } from '$lib/i18n';
  import {
    currentTab,
    currentTemplates,
    currentLoading,
    currentTotal,
    userTemplates,
    sharedTemplates,
    loadAllUserTemplates,
    loadAllSharedTemplates,
    switchTab,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    duplicateTemplate,
    toggleSharing,
    selectedTemplateIds,
    toggleTemplateSelection,
    clearSelection,
    exportSelected,
    templateError
  } from '$lib/stores/templateStore';
  
  // Import filtering/pagination components
  import Pagination from '$lib/components/common/Pagination.svelte';
  import FilterBar from '$lib/components/common/FilterBar.svelte';
  import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';
  import { processListData } from '$lib/utils/listHelpers';
  import { getAssistants } from '$lib/services/assistantService';
  
  // View state
  let view = $state('list'); // 'list' | 'create' | 'edit' | 'view'
  let editingTemplate = $state(null);
  let showDeleteModal = $state(false);
  let templateToDelete = $state(null);
  let isDeleting = $state(false);
  let showImportModal = $state(false);
  let userAssistants = $state([]);
  
  // Form state
  let formData = $state({
    name: '',
    description: '',
    system_prompt: '',
    prompt_template: '',
    is_shared: false
  });
  
  // Client-side filtering/sorting/pagination state
  let displayTemplates = $state([]);
  let searchTerm = $state('');
  let sortBy = $state('updated_at');
  let sortOrder = $state('desc');
  let currentPage = $state(1);
  let itemsPerPage = $state(10);
  let totalPages = $state(1);
  let totalItems = $state(0);
  
  // Load templates on mount (auth is handled by layout-level guard)
  onMount(() => {
    // Load all templates for client-side filtering
    loadAllUserTemplates();
  });
  
  // Apply client-side filtering/sorting/pagination
  function applyFiltersAndPagination() {
    const allTemplates = $currentTab === 'my' ? $userTemplates : $sharedTemplates;
    
    const result = processListData(allTemplates, {
      search: searchTerm,
      searchFields: ['name', 'description', 'system_prompt', 'prompt_template'],
      filters: {},
      sortBy,
      sortOrder,
      page: currentPage,
      itemsPerPage
    });
    
    displayTemplates = result.items;
    totalItems = result.filteredCount;
    totalPages = result.totalPages;
    currentPage = result.currentPage;
  }
  
  // Watch for template store changes and reapply filters
  $effect(() => {
    // Trigger when templates or tab changes
    $userTemplates;
    $sharedTemplates;
    $currentTab;
    if (view === 'list') {
      applyFiltersAndPagination();
    }
  });
  
  // Handle tab switch
  async function handleTabSwitch(tab) {
    currentTab.set(tab);
    clearSelection();
    searchTerm = ''; // Reset search on tab switch
    currentPage = 1;
    
    // Load all templates for the new tab
    if (tab === 'my') {
      await loadAllUserTemplates();
    } else {
      await loadAllSharedTemplates();
    }
  }
  
  function handleMyTabClick() {
    handleTabSwitch('my');
  }
  
  function handleSharedTabClick() {
    handleTabSwitch('shared');
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
  
  function handleCancelDeleteModal() {
    showDeleteModal = false;
    templateToDelete = null;
  }
  
  // Handle create new template
  function handleCreate() {
    formData = {
      name: '',
      description: '',
      system_prompt: '',
      prompt_template: '',
      is_shared: false
    };
    editingTemplate = null;
    view = 'create';
  }
  
  // Handle view template (clicking on template in list)
  function handleView(template) {
    editingTemplate = template;
    formData = {
      name: template.name,
      description: template.description || '',
      system_prompt: template.system_prompt || '',
      prompt_template: template.prompt_template || '',
      is_shared: template.is_shared
    };
    view = 'view';
  }
  
  // Handle edit template
  function handleEdit(template) {
    editingTemplate = template;
    formData = {
      name: template.name,
      description: template.description || '',
      system_prompt: template.system_prompt || '',
      prompt_template: template.prompt_template || '',
      is_shared: template.is_shared
    };
    view = 'edit';
  }
  
  // Event handler that finds template by ID from event
  function handleEditClick(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    const template = $currentTemplates.find(t => t.id === templateId);
    if (template) handleEdit(template);
  }
  
  function handleToggleSharingClick(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    const template = $currentTemplates.find(t => t.id === templateId);
    if (template) handleToggleSharing(template);
  }
  
  function handleDeleteRequestClick(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    const template = $currentTemplates.find(t => t.id === templateId);
    if (template) handleDeleteRequest(template);
  }
  
  function handleDuplicateClick(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    const template = $currentTemplates.find(t => t.id === templateId);
    if (template) handleDuplicate(template);
  }
  
  function handleSelectionChange(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    toggleTemplateSelection(templateId);
  }
  
  function handleViewClick(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    const template = $currentTemplates.find(t => t.id === templateId);
    if (template) handleView(template);
  }
  
  // Import from assistant
  async function handleImportFromAssistant() {
    // Load user's assistants
    try {
      const response = await getAssistants(100, 0);
      userAssistants = response.assistants || [];
      showImportModal = true;
    } catch (error) {
      console.error('Error loading assistants:', error);
    }
  }
  
  function handleSelectAssistant(assistant) {
    formData.system_prompt = assistant.system_prompt || '';
    formData.prompt_template = assistant.prompt_template || '';
    if (!formData.name) {
      formData.name = `Template from ${assistant.name}`;
    }
    showImportModal = false;
  }
  
  // Handle save (create or update)
  async function handleSave() {
    try {
      if (editingTemplate) {
        // Update
        await updateTemplate(editingTemplate.id, formData);
      } else {
        // Create
        await createTemplate(formData);
      }
      view = 'list';
      editingTemplate = null;
    } catch (error) {
      // Error is handled by store
    }
  }
  
  // Handle cancel
  function handleCancel() {
    view = 'list';
    editingTemplate = null;
  }
  
  // Handle delete request
  function handleDeleteRequest(template) {
    templateToDelete = template;
    showDeleteModal = true;
  }
  
  // Handle delete confirm
  async function handleDeleteConfirm() {
    if (templateToDelete) {
      isDeleting = true;
      try {
        await deleteTemplate(templateToDelete.id);
        showDeleteModal = false;
        templateToDelete = null;
      } catch (error) {
        // Error is handled by store
      } finally {
        isDeleting = false;
      }
    }
  }
  
  // Handle duplicate
  async function handleDuplicate(template) {
    try {
      await duplicateTemplate(template.id);
    } catch (error) {
      // Error is handled by store
    }
  }
  
  // Handle share toggle
  async function handleToggleSharing(template) {
    try {
      await toggleSharing(template.id, !template.is_shared);
    } catch (error) {
      // Error is handled by store
    }
  }
  
  // Handle export
  async function handleExport() {
    try {
      await exportSelected();
    } catch (error) {
      // Error is handled by store
    }
  }
</script>

<div class="min-h-screen bg-gray-50 py-8">
  <div class="w-full mx-auto">
    
    {#if view === 'list'}
    <!-- Header -->
    <div class="mb-8 px-6">
      <h1 class="text-3xl font-bold text-gray-900">
        {$locale ? $_('promptTemplates.title', { default: 'Prompt Templates' }) : 'Prompt Templates'}
      </h1>
      <p class="mt-2 text-sm text-gray-600">
        {$locale ? $_('promptTemplates.description', { default: 'Create and manage reusable prompt templates for your assistants' }) : 'Create and manage reusable prompt templates for your assistants'}
      </p>
    </div>

    <!-- Error Message -->
    {#if $templateError}
      <div class="mb-4 mx-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
        <span class="block sm:inline">{$templateError}</span>
      </div>
    {/if}
      <!-- List View -->
      <div class="bg-white shadow rounded-lg">
        <!-- Tabs and Actions -->
        <div class="border-b border-gray-200">
          <div class="flex justify-between items-center px-6 py-4">
            <div class="flex space-x-4">
              <button
                onclick={handleMyTabClick}
                class="px-4 py-2 text-sm font-medium rounded-md {$currentTab === 'my' ? 'bg-brand text-white' : 'text-gray-600 hover:text-gray-900'}"
              >
                {$locale ? $_('promptTemplates.myTemplates', { default: 'My Templates' }) : 'My Templates'}
                {#if $currentTab === 'my'}
                  <span class="ml-2 bg-white bg-opacity-30 text-white py-0.5 px-2 rounded-full text-xs">
                    {$currentTotal}
                  </span>
                {/if}
              </button>
              <button
                onclick={handleSharedTabClick}
                class="px-4 py-2 text-sm font-medium rounded-md {$currentTab === 'shared' ? 'bg-brand text-white' : 'text-gray-600 hover:text-gray-900'}"
              >
                {$locale ? $_('promptTemplates.sharedTemplates', { default: 'Shared Templates' }) : 'Shared Templates'}
                {#if $currentTab === 'shared'}
                  <span class="ml-2 bg-white bg-opacity-30 text-white py-0.5 px-2 rounded-full text-xs">
                    {$currentTotal}
                  </span>
                {/if}
              </button>
            </div>
            
            <div class="flex space-x-2">
              {#if $selectedTemplateIds.length > 0}
                <button
                  onclick={handleExport}
                  class="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md"
                >
                  {$locale ? $_('promptTemplates.export', { default: 'Export' }) : 'Export'} ({$selectedTemplateIds.length})
                </button>
                <button
                  onclick={clearSelection}
                  class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md"
                >
                  {$locale ? $_('common.clearSelection', { default: 'Clear' }) : 'Clear'}
                </button>
              {/if}
              {#if $currentTab === 'my'}
                <button
                  onclick={handleCreate}
                  class="px-4 py-2 text-sm font-medium text-white bg-brand hover:bg-brand-hover rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
                >
                  + {$locale ? $_('promptTemplates.createNew', { default: 'New Template' }) : 'New Template'}
                </button>
              {/if}
            </div>
          </div>
        </div>

        <!-- Info message for shared tab -->
        {#if $currentTab === 'shared'}
          <div class="mx-6 mt-4 mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                </svg>
              </div>
              <div class="ml-3">
                <p class="text-sm text-blue-700">
                  {$locale ? $_('promptTemplates.sharedTabInfo', { default: 'Note: Templates you own will not appear in this list, even if they are shared. Your own shared templates can be found in the "My Templates" tab.' }) : 'Note: Templates you own will not appear in this list, even if they are shared. Your own shared templates can be found in the "My Templates" tab.'}
                </p>
              </div>
            </div>
          </div>
        {/if}

        <!-- Filter Bar -->
        <FilterBar
          searchPlaceholder={$locale ? $_('promptTemplates.searchPlaceholder', { default: 'Search templates...' }) : 'Search templates...'}
          searchValue={searchTerm}
          filters={[]}
          filterValues={{}}
          sortOptions={[
            { value: 'name', label: $locale ? $_('common.sortByName', { default: 'Name' }) : 'Name' },
            { value: 'updated_at', label: $locale ? $_('common.sortByUpdated', { default: 'Last Modified' }) : 'Last Modified' },
            { value: 'created_at', label: $locale ? $_('common.sortByCreated', { default: 'Created Date' }) : 'Created Date' }
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
              Showing <span class="font-medium">{totalItems}</span> of <span class="font-medium">{$currentTab === 'my' ? $userTemplates.length : $sharedTemplates.length}</span> templates
            {:else}
              <span class="font-medium">{totalItems}</span> templates
            {/if}
          </div>
        </div>

        <!-- Templates List -->
        <div class="divide-y divide-gray-200">
          {#if $currentLoading}
            <div class="px-6 py-12 text-center text-gray-500">
              {$locale ? $_('common.loading', { default: 'Loading...' }) : 'Loading...'}
            </div>
          {:else if displayTemplates.length === 0}
            {#if ($currentTab === 'my' ? $userTemplates.length : $sharedTemplates.length) === 0}
              <!-- No templates at all -->
              <div class="px-6 py-12 text-center">
                <p class="text-gray-500">
                  {$currentTab === 'my' 
                    ? ($locale ? $_('promptTemplates.noTemplates', { default: 'No templates yet. Create your first template!' }) : 'No templates yet. Create your first template!')
                    : ($locale ? $_('promptTemplates.noShared', { default: 'No shared templates available' }) : 'No shared templates available')}
                </p>
              </div>
            {:else}
              <!-- No results match filters -->
              <div class="px-6 py-12 text-center">
                <p class="text-gray-500 mb-4">No templates match your search</p>
                <button 
                  onclick={handleClearFilters}
                  class="text-brand hover:text-brand-hover hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand rounded-md px-3 py-1"
                >
                  Clear search
                </button>
              </div>
            {/if}
          {:else}
            {#each displayTemplates as template (template.id)}
              <div class="px-6 py-4 hover:bg-gray-50">
                <div class="flex items-start justify-between">
                  <div class="flex items-start space-x-3 flex-1">
                    <input
                      type="checkbox"
                      checked={$selectedTemplateIds.includes(template.id)}
                      onchange={handleSelectionChange}
                      data-template-id={template.id}
                      class="mt-1 h-4 w-4 text-brand rounded"
                    />
                    <button
                      onclick={handleViewClick}
                      data-template-id={template.id}
                      class="flex-1 text-left hover:bg-gray-50 rounded p-2 -m-2"
                    >
                      <h3 class="text-lg font-medium text-gray-900 hover:text-brand-hover">{template.name}</h3>
                      {#if template.description}
                        <p class="mt-1 text-sm text-gray-600">{template.description}</p>
                      {/if}
                      <div class="mt-2 flex items-center space-x-4 text-xs text-gray-500">
                        {#if template.owner_name}
                          <span>By: {template.owner_name}</span>
                        {/if}
                        {#if template.is_shared}
                          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            Shared
                          </span>
                        {/if}
                        <span>Updated: {new Date(template.updated_at * 1000).toLocaleDateString()}</span>
                      </div>
                    </button>
                  </div>
                  
                  <div class="flex space-x-2 ml-4">
                    {#if template.is_owner}
                      <button
                        onclick={handleEditClick}
                        data-template-id={template.id}
                        class="px-3 py-1 text-sm text-brand hover:text-brand-hover"
                      >
                        {$locale ? $_('common.edit', { default: 'Edit' }) : 'Edit'}
                      </button>
                      <button
                        onclick={handleToggleSharingClick}
                        data-template-id={template.id}
                        class="px-3 py-1 text-sm text-gray-600 hover:text-gray-700"
                      >
                        {template.is_shared ? 'Unshare' : 'Share'}
                      </button>
                      <button
                        onclick={handleDeleteRequestClick}
                        data-template-id={template.id}
                        class="px-3 py-1 text-sm text-red-600 hover:text-red-700"
                      >
                        {$locale ? $_('common.delete', { default: 'Delete' }) : 'Delete'}
                      </button>
                    {/if}
                    <button
                      onclick={handleDuplicateClick}
                      data-template-id={template.id}
                      class="px-3 py-1 text-sm text-gray-600 hover:text-gray-700"
                    >
                      {$locale ? $_('common.duplicate', { default: 'Duplicate' }) : 'Duplicate'}
                    </button>
                  </div>
                </div>
              </div>
            {/each}
          {/if}
        </div>
        
        <!-- Pagination -->
        {#if totalPages > 1}
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={totalItems}
            itemsPerPage={itemsPerPage}
            itemsPerPageOptions={[5, 10, 25, 50, 100]}
            on:pageChange={handlePageChange}
            on:itemsPerPageChange={handleItemsPerPageChange}
          />
        {/if}
      </div>

    {:else if view === 'create' || view === 'edit' || view === 'view'}
      <!-- Create/Edit/View Form - WIDE LAYOUT -->
      <div class="bg-white shadow rounded-lg p-8 w-full mx-auto" style="max-width: 900px;">
        
        
        <!-- Header -->
        <div class="mb-6 pb-4 border-b border-gray-200 flex justify-between items-center">
          <h2 class="text-2xl font-bold text-gray-900">
            {view === 'view' ? 'View Template' : editingTemplate ? 'Edit Template' : 'Create Template'}
          </h2>
          {#if view === 'create'}
            <button
              onclick={handleImportFromAssistant}
              class="px-4 py-2 border border-gray-300 text-sm rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              Import from Assistant
            </button>
          {/if}
        </div>
        
        <!-- Form -->
        <form onsubmit={(e) => { e.preventDefault(); handleSave(); }}>
          
          <!-- Name -->
          <div class="mb-6">
            <label for="name" class="block text-sm font-semibold text-gray-700 mb-2">
              Name *
            </label>
            <input
              type="text"
              id="name"
              bind:value={formData.name}
              required
              disabled={view === 'view'}
              class="w-full px-4 py-3 text-base rounded-md border border-gray-300 shadow-sm focus:border-brand focus:ring-brand sm:text-sm {view === 'view' ? 'bg-gray-50' : ''}"
            />
          </div>

          <!-- Description -->
          <div class="mb-6">
            <label for="description" class="block text-sm font-semibold text-gray-700 mb-2">
              Description
            </label>
            <textarea
              id="description"
              bind:value={formData.description}
              rows="3"
              disabled={view === 'view'}
              class="w-full px-4 py-3 text-base rounded-md border border-gray-300 shadow-sm focus:border-brand focus:ring-brand sm:text-sm {view === 'view' ? 'bg-gray-50' : ''}"
              placeholder="Brief description of this template's purpose"
            ></textarea>
          </div>

          <!-- System Prompt -->
          <div class="mb-6">
            <label for="system_prompt" class="block text-sm font-semibold text-gray-700 mb-2">
              System Prompt
            </label>
            <textarea
              id="system_prompt"
              bind:value={formData.system_prompt}
              rows="10"
              disabled={view === 'view'}
              class="w-full px-4 py-3 text-base rounded-md border border-gray-300 shadow-sm focus:border-brand focus:ring-brand font-mono sm:text-sm {view === 'view' ? 'bg-gray-50' : ''}"
              placeholder="Define the assistant's role and personality..."
            ></textarea>
          </div>

          <!-- Prompt Template -->
          <div class="mb-6">
            <label for="prompt_template" class="block text-sm font-semibold text-gray-700 mb-2">
              Prompt Template
            </label>
            <textarea
              id="prompt_template"
              bind:value={formData.prompt_template}
              rows="10"
              disabled={view === 'view'}
              class="w-full px-4 py-3 text-base rounded-md border border-gray-300 shadow-sm focus:border-brand focus:ring-brand font-mono sm:text-sm {view === 'view' ? 'bg-gray-50' : ''}"
              placeholder="e.g. Use the context to answer the question: user_input"
            ></textarea>
            <p class="mt-2 text-xs text-gray-500">
              Use &#123;context&#125; and &#123;user_input&#125; as placeholders
            </p>
          </div>

          <!-- Share Toggle -->
          {#if !editingTemplate || editingTemplate.is_owner}
            <div class="mb-8 flex items-center">
              <input
                type="checkbox"
                id="is_shared"
                bind:checked={formData.is_shared}
                disabled={view === 'view'}
                class="h-4 w-4 text-brand border-gray-300 rounded focus:ring-brand"
              />
              <label for="is_shared" class="ml-3 text-sm text-gray-700">
                Share with organization
              </label>
            </div>
          {/if}

          <!-- Action Buttons -->
          <div class="pt-6 border-t border-gray-200 flex justify-end gap-3">
            {#if view === 'view'}
              <button
                type="button"
                onclick={handleCancel}
                class="px-6 py-2 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
              >
                Back
              </button>
              {#if editingTemplate && editingTemplate.is_owner}
                <button
                  type="button"
                  onclick={() => { view = 'edit'; }}
                  class="px-6 py-2 text-sm font-medium text-white bg-brand hover:bg-brand-hover rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
                >
                  Edit
                </button>
              {/if}
            {:else}
              <button
                type="button"
                onclick={handleCancel}
                class="px-6 py-2 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
              >
                Cancel
              </button>
              <button
                type="submit"
                class="px-6 py-2 text-sm font-medium text-white bg-brand hover:bg-brand-hover rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
              >
                Save
              </button>
            {/if}
          </div>
        </form>
      </div>
    {/if}

    <!-- Delete Confirmation Modal -->
    <ConfirmationModal
      bind:isOpen={showDeleteModal}
      bind:isLoading={isDeleting}
      title={$locale ? $_('promptTemplates.confirmDelete', { default: 'Delete Template?' }) : 'Delete Template?'}
      message={$locale ? $_('promptTemplates.deleteWarning', { default: 'This action cannot be undone. The template will be permanently deleted.' }) : 'This action cannot be undone. The template will be permanently deleted.'}
      confirmText={$locale ? $_('common.delete', { default: 'Delete' }) : 'Delete'}
      cancelText={$locale ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
      variant="danger"
      onconfirm={handleDeleteConfirm}
      oncancel={handleCancelDeleteModal}
    />

    <!-- Import from Assistant Modal -->
    {#if showImportModal}
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[80vh] flex flex-col">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-medium text-gray-900">
              {$locale ? $_('promptTemplates.selectAssistant', { default: 'Select Assistant to Import' }) : 'Select Assistant to Import'}
            </h3>
            <button
              onclick={() => showImportModal = false}
              class="text-gray-400 hover:text-gray-500"
              aria-label="Close modal"
            >
              <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto">
            {#if userAssistants.length === 0}
              <p class="text-center text-gray-500 py-8">No assistants found</p>
            {:else}
              <div class="space-y-2">
                {#each userAssistants as assistant (assistant.id)}
                  <button
                    onclick={() => handleSelectAssistant(assistant)}
                    class="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:border-brand hover:bg-gray-50"
                  >
                    <h4 class="font-medium text-gray-900">{assistant.name}</h4>
                    {#if assistant.description}
                      <p class="text-sm text-gray-600 mt-1">{assistant.description}</p>
                    {/if}
                  </button>
                {/each}
              </div>
            {/if}
          </div>
          <div class="mt-4 flex justify-end">
            <button
              onclick={() => showImportModal = false}
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md"
            >
              {$locale ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
            </button>
          </div>
        </div>
      </div>
    {/if}

  </div>
</div>

