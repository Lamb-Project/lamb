<script>
  import { onMount } from 'svelte';
  import { _, locale } from '$lib/i18n';
  import {
    currentTab,
    currentTemplates,
    currentLoading,
    userTemplates,
    sharedTemplates,
    loadUserTemplates,
    loadSharedTemplates,
    templateSelectModalOpen,
    closeTemplateSelectModal,
    selectTemplateFromModal
  } from '$lib/stores/templateStore';
  
  // Props
  let {
    onSelect = (/** @type {any} */ template) => {}
  } = $props();
  
  // Local state
  let searchQuery = $state('');
  /** @type {any | null} */
  let selectedTemplate = $state(null);
  
  // Load templates when modal opens
  $effect(() => {
    if ($templateSelectModalOpen) {
      loadUserTemplates();
      loadSharedTemplates();
    }
  });
  
  // Filtered templates based on search
  let filteredUserTemplates = $derived(
    searchQuery
      ? $userTemplates.filter(t =>
          t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (t.description && t.description.toLowerCase().includes(searchQuery.toLowerCase()))
        )
      : $userTemplates
  );
  
  let filteredSharedTemplates = $derived(
    searchQuery
      ? $sharedTemplates.filter(t =>
          t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (t.description && t.description.toLowerCase().includes(searchQuery.toLowerCase()))
        )
      : $sharedTemplates
  );
  
  // Handle apply
  function handleApply() {
    if (selectedTemplate) {
      selectTemplateFromModal(selectedTemplate);
      onSelect(selectedTemplate);
      handleClose();
    }
  }
  
  // Handle close
  function handleClose() {
    closeTemplateSelectModal();
    selectedTemplate = null;
    searchQuery = '';
  }
  
  // Handle click outside to close
  function handleBackdropClick(/** @type {MouseEvent} */ event) {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }
  
  // Tab handlers
  function handleMyTabClick() {
    currentTab.set('my');
  }
  
  function handleSharedTabClick() {
    currentTab.set('shared');
  }
  
  // Template selection handler
  function handleTemplateClick(event) {
    const templateId = parseInt(event.currentTarget.dataset.templateId);
    const template = [...filteredUserTemplates, ...filteredSharedTemplates].find(t => t.id === templateId);
    if (template) {
      selectedTemplate = template;
    }
  }
</script>

{#if $templateSelectModalOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50"
    onclick={handleBackdropClick}
    role="button"
    tabindex="-1"
  >
    <div class="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-gray-200">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-bold text-gray-900">
            {$locale ? $_('promptTemplates.selectTemplate', { default: 'Select Prompt Template' }) : 'Select Prompt Template'}
          </h2>
          <button
            onclick={handleClose}
            class="text-gray-400 hover:text-gray-500"
            aria-label="Close modal"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        
        <!-- Search -->
        <div class="mt-4">
          <input
            type="text"
            bind:value={searchQuery}
            placeholder={$locale ? $_('promptTemplates.search', { default: 'Search templates...' }) : 'Search templates...'}
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex border-b border-gray-200 px-6">
        <button
          onclick={handleMyTabClick}
          class="px-4 py-3 text-sm font-medium border-b-2 {$currentTab === 'my' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
        >
          {$locale ? $_('promptTemplates.myTemplates', { default: 'My Templates' }) : 'My Templates'}
          <span class="ml-2 text-xs">({filteredUserTemplates.length})</span>
        </button>
        <button
          onclick={handleSharedTabClick}
          class="px-4 py-3 text-sm font-medium border-b-2 {$currentTab === 'shared' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
        >
          {$locale ? $_('promptTemplates.sharedTemplates', { default: 'Shared Templates' }) : 'Shared Templates'}
          <span class="ml-2 text-xs">({filteredSharedTemplates.length})</span>
        </button>
      </div>

      <!-- Templates List -->
      <div class="flex-1 overflow-y-auto px-6 py-4">
        {#if $currentLoading}
          <div class="text-center py-8 text-gray-500">
            {$locale ? $_('common.loading', { default: 'Loading...' }) : 'Loading...'}
          </div>
        {:else}
          {#if $currentTab === 'my'}
            {#if filteredUserTemplates.length === 0}
              <div class="text-center py-8 text-gray-500">
                {searchQuery
                  ? ($locale ? $_('promptTemplates.noResults', { default: 'No templates found' }) : 'No templates found')
                  : ($locale ? $_('promptTemplates.noTemplates', { default: 'No templates yet' }) : 'No templates yet')}
              </div>
            {:else}
              <div class="space-y-2">
                {#each filteredUserTemplates as template (template.id)}
                  <button
                    onclick={handleTemplateClick}
                    data-template-id={template.id}
                    class="w-full text-left px-4 py-3 rounded-lg border-2 transition-colors {selectedTemplate?.id === template.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h3 class="font-medium text-gray-900">{template.name}</h3>
                        {#if template.description}
                          <p class="mt-1 text-sm text-gray-600">{template.description}</p>
                        {/if}
                        <div class="mt-2 flex items-center space-x-2 text-xs text-gray-500">
                          {#if template.is_shared}
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                              Shared
                            </span>
                          {/if}
                          <span>Updated: {new Date(template.updated_at * 1000).toLocaleDateString()}</span>
                        </div>
                      </div>
                      {#if selectedTemplate?.id === template.id}
                        <svg class="h-5 w-5 text-blue-500 flex-shrink-0 ml-2" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                        </svg>
                      {/if}
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
          {:else}
            {#if filteredSharedTemplates.length === 0}
              <div class="text-center py-8 text-gray-500">
                {searchQuery
                  ? ($locale ? $_('promptTemplates.noResults', { default: 'No templates found' }) : 'No templates found')
                  : ($locale ? $_('promptTemplates.noShared', { default: 'No shared templates available' }) : 'No shared templates available')}
              </div>
            {:else}
              <div class="space-y-2">
                {#each filteredSharedTemplates as template (template.id)}
                  <button
                    onclick={handleTemplateClick}
                    data-template-id={template.id}
                    class="w-full text-left px-4 py-3 rounded-lg border-2 transition-colors {selectedTemplate?.id === template.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h3 class="font-medium text-gray-900">{template.name}</h3>
                        {#if template.description}
                          <p class="mt-1 text-sm text-gray-600">{template.description}</p>
                        {/if}
                        <div class="mt-2 flex items-center space-x-2 text-xs text-gray-500">
                          {#if template.owner_name}
                            <span>By: {template.owner_name}</span>
                          {/if}
                          <span>Updated: {new Date(template.updated_at * 1000).toLocaleDateString()}</span>
                        </div>
                      </div>
                      {#if selectedTemplate?.id === template.id}
                        <svg class="h-5 w-5 text-blue-500 flex-shrink-0 ml-2" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                        </svg>
                      {/if}
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
          {/if}
        {/if}
      </div>

      <!-- Footer Actions -->
      <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
        <button
          onclick={handleClose}
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md"
        >
          {$locale ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
        </button>
        <button
          onclick={handleApply}
          disabled={!selectedTemplate}
          class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed rounded-md"
        >
          {$locale ? $_('promptTemplates.applyTemplate', { default: 'Apply Template' }) : 'Apply Template'}
        </button>
      </div>
    </div>
  </div>
{/if}

