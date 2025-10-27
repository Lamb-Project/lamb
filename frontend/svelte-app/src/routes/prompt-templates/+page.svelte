<script>
  import { onMount } from 'svelte';
  import { _, locale } from '$lib/i18n';
  import { user } from '$lib/stores/userStore';
  import { goto } from '$app/navigation';
  import { base } from '$app/paths';
  import {
    currentTab,
    currentTemplates,
    currentLoading,
    currentTotal,
    userTemplatesPage,
    sharedTemplatesPage,
    loadUserTemplates,
    loadSharedTemplates,
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
  
  // View state
  let view = $state('list'); // 'list' | 'create' | 'edit'
  let editingTemplate = $state(null);
  let showDeleteModal = $state(false);
  let templateToDelete = $state(null);
  
  // Form state
  let formData = $state({
    name: '',
    description: '',
    system_prompt: '',
    prompt_template: '',
    is_shared: false
  });
  
  // Check authentication
  onMount(() => {
    if (!$user.isLoggedIn) {
      goto(`${base}/`);
      return;
    }
    
    // Load initial templates
    loadUserTemplates();
  });
  
  // Handle tab switch
  async function handleTabSwitch(tab) {
    await switchTab(tab);
  }
  
  function handleMyTabClick() {
    handleTabSwitch('my');
  }
  
  function handleSharedTabClick() {
    handleTabSwitch('shared');
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
      try {
        await deleteTemplate(templateToDelete.id);
        showDeleteModal = false;
        templateToDelete = null;
      } catch (error) {
        // Error is handled by store
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
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">
        {$locale ? $_('promptTemplates.title', { default: 'Prompt Templates' }) : 'Prompt Templates'}
      </h1>
      <p class="mt-2 text-sm text-gray-600">
        {$locale ? $_('promptTemplates.description', { default: 'Create and manage reusable prompt templates for your assistants' }) : 'Create and manage reusable prompt templates for your assistants'}
      </p>
    </div>

    <!-- Error Message -->
    {#if $templateError}
      <div class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
        <span class="block sm:inline">{$templateError}</span>
      </div>
    {/if}

    {#if view === 'list'}
      <!-- List View -->
      <div class="bg-white shadow rounded-lg">
        <!-- Tabs and Actions -->
        <div class="border-b border-gray-200">
          <div class="flex justify-between items-center px-6 py-4">
            <div class="flex space-x-4">
              <button
                onclick={handleMyTabClick}
                class="px-4 py-2 text-sm font-medium rounded-md {$currentTab === 'my' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-900'}"
              >
                {$locale ? $_('promptTemplates.myTemplates', { default: 'My Templates' }) : 'My Templates'}
                {#if $currentTab === 'my'}
                  <span class="ml-2 bg-blue-200 text-blue-800 py-0.5 px-2 rounded-full text-xs">
                    {$currentTotal}
                  </span>
                {/if}
              </button>
              <button
                onclick={handleSharedTabClick}
                class="px-4 py-2 text-sm font-medium rounded-md {$currentTab === 'shared' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-900'}"
              >
                {$locale ? $_('promptTemplates.sharedTemplates', { default: 'Shared Templates' }) : 'Shared Templates'}
                {#if $currentTab === 'shared'}
                  <span class="ml-2 bg-blue-200 text-blue-800 py-0.5 px-2 rounded-full text-xs">
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
                  class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md"
                >
                  + {$locale ? $_('promptTemplates.createNew', { default: 'New Template' }) : 'New Template'}
                </button>
              {/if}
            </div>
          </div>
        </div>

        <!-- Templates List -->
        <div class="divide-y divide-gray-200">
          {#if $currentLoading}
            <div class="px-6 py-12 text-center text-gray-500">
              {$locale ? $_('common.loading', { default: 'Loading...' }) : 'Loading...'}
            </div>
          {:else if $currentTemplates.length === 0}
            <div class="px-6 py-12 text-center">
              <p class="text-gray-500">
                {$currentTab === 'my' 
                  ? ($locale ? $_('promptTemplates.noTemplates', { default: 'No templates yet. Create your first template!' }) : 'No templates yet. Create your first template!')
                  : ($locale ? $_('promptTemplates.noShared', { default: 'No shared templates available' }) : 'No shared templates available')}
              </p>
            </div>
          {:else}
            {#each $currentTemplates as template (template.id)}
              <div class="px-6 py-4 hover:bg-gray-50">
                <div class="flex items-start justify-between">
                  <div class="flex items-start space-x-3 flex-1">
                    <input
                      type="checkbox"
                      checked={$selectedTemplateIds.includes(template.id)}
                      onchange={handleSelectionChange}
                      data-template-id={template.id}
                      class="mt-1 h-4 w-4 text-blue-600 rounded"
                    />
                    <div class="flex-1">
                      <h3 class="text-lg font-medium text-gray-900">{template.name}</h3>
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
                    </div>
                  </div>
                  
                  <div class="flex space-x-2 ml-4">
                    {#if template.is_owner}
                      <button
                        onclick={handleEditClick}
                        data-template-id={template.id}
                        class="px-3 py-1 text-sm text-blue-600 hover:text-blue-700"
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
      </div>

    {:else if view === 'create' || view === 'edit'}
      <!-- Create/Edit Form -->
      <div class="bg-white shadow rounded-lg px-6 py-6">
        <h2 class="text-2xl font-bold mb-6">
          {editingTemplate 
            ? ($locale ? $_('promptTemplates.editTemplate', { default: 'Edit Template' }) : 'Edit Template')
            : ($locale ? $_('promptTemplates.createTemplate', { default: 'Create Template' }) : 'Create Template')}
        </h2>
        
        <form onsubmit={(e) => { e.preventDefault(); handleSave(); }} class="space-y-6">
          <!-- Name -->
          <div>
            <label for="name" class="block text-sm font-medium text-gray-700">
              {$locale ? $_('promptTemplates.name', { default: 'Name' }) : 'Name'} *
            </label>
            <input
              type="text"
              id="name"
              bind:value={formData.name}
              required
              class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
          </div>

          <!-- Description -->
          <div>
            <label for="description" class="block text-sm font-medium text-gray-700">
              {$locale ? $_('promptTemplates.description', { default: 'Description' }) : 'Description'}
            </label>
            <textarea
              id="description"
              bind:value={formData.description}
              rows="3"
              class="mt-1 block w-full px-3 py-2 rounded-md border border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
              placeholder="Brief description of this template's purpose"
            ></textarea>
          </div>

          <!-- System Prompt -->
          <div>
            <label for="system_prompt" class="block text-sm font-medium text-gray-700">
              {$locale ? $_('promptTemplates.systemPrompt', { default: 'System Prompt' }) : 'System Prompt'}
            </label>
            <textarea
              id="system_prompt"
              bind:value={formData.system_prompt}
              rows="8"
              class="mt-1 block w-full px-3 py-2 rounded-md border border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono"
              placeholder="Define the assistant's role and personality..."
            ></textarea>
          </div>

          <!-- Prompt Template -->
          <div>
            <label for="prompt_template" class="block text-sm font-medium text-gray-700">
              {$locale ? $_('promptTemplates.promptTemplate', { default: 'Prompt Template' }) : 'Prompt Template'}
            </label>
            <textarea
              id="prompt_template"
              bind:value={formData.prompt_template}
              rows="8"
              class="mt-1 block w-full px-3 py-2 rounded-md border border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono"
              placeholder="e.g. Use the {context} to answer the question: {user_input}"
            ></textarea>
            <p class="mt-1 text-xs text-gray-500">
              {$locale ? $_('promptTemplates.templateHint', { default: 'Use {context} and {user_input} as placeholders' }) : 'Use {context} and {user_input} as placeholders'}
            </p>
          </div>

          <!-- Share Toggle -->
          {#if !editingTemplate || editingTemplate.is_owner}
            <div class="flex items-center">
              <input
                type="checkbox"
                id="is_shared"
                bind:checked={formData.is_shared}
                class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label for="is_shared" class="ml-2 block text-sm text-gray-900">
                {$locale ? $_('promptTemplates.shareWithOrg', { default: 'Share with organization' }) : 'Share with organization'}
              </label>
            </div>
          {/if}

          <!-- Actions -->
          <div class="flex justify-end space-x-3">
            <button
              type="button"
              onclick={handleCancel}
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md"
            >
              {$locale ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
            </button>
            <button
              type="submit"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md"
            >
              {$locale ? $_('common.save', { default: 'Save' }) : 'Save'}
            </button>
          </div>
        </form>
      </div>
    {/if}

    <!-- Delete Confirmation Modal -->
    {#if showDeleteModal}
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg p-6 max-w-md w-full">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            {$locale ? $_('promptTemplates.confirmDelete', { default: 'Delete Template?' }) : 'Delete Template?'}
          </h3>
          <p class="text-sm text-gray-500 mb-6">
            {$locale ? $_('promptTemplates.deleteWarning', { default: 'This action cannot be undone. The template will be permanently deleted.' }) : 'This action cannot be undone. The template will be permanently deleted.'}
          </p>
          <div class="flex justify-end space-x-3">
            <button
              onclick={handleCancelDeleteModal}
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md"
            >
              {$locale ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
            </button>
            <button
              onclick={handleDeleteConfirm}
              class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md"
            >
              {$locale ? $_('common.delete', { default: 'Delete' }) : 'Delete'}
            </button>
          </div>
        </div>
      </div>
    {/if}

  </div>
</div>

